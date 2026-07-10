from __future__ import annotations

from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from .model import Environment, RunResult, Sample
from .worker import WorkerRequest, _error_sample

REPO_ROOT = Path(__file__).resolve().parent.parent

_MODE_DEFAULTS = {"quick": (1, 3), "full": (2, 10), "diagnose": (1, 5)}


@dataclass(frozen=True)
class RunConfig:
    mode: str
    backend: str = "auto"
    repeat: int | None = None
    categories: tuple[str, ...] = ()
    excluded_categories: tuple[str, ...] = ()
    output_dir: Path = Path("artifacts/profiling")


def selected_counts(config: RunConfig) -> tuple[int, int]:
    warmups, repeats = _MODE_DEFAULTS[config.mode]
    return warmups, config.repeat if config.repeat is not None else repeats


def _gpu_available() -> bool:
    from .gpu import accelerator_available

    return accelerator_available()


def _selected_workloads(config: RunConfig):
    from .workload import iter_workloads

    workloads = iter_workloads()
    if config.mode == "quick":
        workloads = [item for item in workloads if item.quick]
    if config.categories:
        workloads = [item for item in workloads if item.category in config.categories]
    if config.excluded_categories:
        workloads = [item for item in workloads
                     if item.category not in config.excluded_categories]
    return workloads


def _backends_for(workload, config: RunConfig, gpu_available: bool) -> list[str]:
    """Resolve which backends a workload runs on.

    An explicitly requested GPU that is unavailable stays in the list so the
    worker can turn it into an error sample; `all`/`auto` skip GPU silently.
    """
    supports_gpu = "gpu" in workload.backends
    if config.backend == "cpu":
        return ["cpu"]
    if config.backend == "gpu":
        return ["gpu"]
    if config.backend == "all":
        backends = ["cpu"] if "cpu" in workload.backends else []
        if supports_gpu and gpu_available:
            backends.append("gpu")
        return backends
    return ["auto"]


def _cold_groups(workloads) -> dict[str, object]:
    """First workload of each non-empty cold_group, in registry order."""
    groups: dict[str, object] = {}
    for workload in workloads:
        group = str(workload.metadata.get("cold_group", "") or "")
        if group and group not in groups:
            groups[group] = workload
    return groups


def _isolated_env(home: str) -> dict[str, str]:
    env = dict(os.environ)
    env["HOME"] = home
    env["USERPROFILE"] = home
    env["PLOTTER_LOG_FILE"] = "0"
    return env


def _run_worker(request: WorkerRequest, artifact_dir: Path) -> list[Sample]:
    from .model import Sample as _Sample

    artifact_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="plotter-profile-") as home:
        request_path = Path(home) / "request.json"
        response_path = artifact_dir / f"{request.workload_id}.{request.requested_backend}.{request.sample_kind}.json"
        request_path.write_text(json.dumps(request.to_dict()), encoding="utf-8")

        command = [sys.executable, "-m", "profiling.worker",
                   str(request_path), str(response_path)]
        completed = subprocess.run(command, cwd=REPO_ROOT, env=_isolated_env(home),
                                   text=True, capture_output=True, check=False)

        if completed.returncode != 0 or not response_path.is_file():
            detail = (completed.stderr or completed.stdout or "").strip()
            tail = detail.splitlines()[-1] if detail else f"exit {completed.returncode}"
            return [_worker_failure_sample(request, tail)]

        raw = json.loads(response_path.read_text(encoding="utf-8"))

    samples = []
    for item in raw:
        item = dict(item)
        item["environment"] = Environment(**item["environment"])
        samples.append(_Sample(**item))
    return samples


def _worker_failure_sample(request: WorkerRequest, reason: str) -> Sample:
    from .workload import get_workload

    workload = get_workload(request.workload_id)
    environment = Environment(
        os_name="", os_version="", machine="", processor="", python="", commit="",
        requested_backend=request.requested_backend, actual_backend="unknown",
        torch_version=None, device="", runtime="", dtype="", problem_size="", tile=0,
    )
    return _error_sample(workload, None, environment, "worker", 0,
                         RuntimeError(reason), request.sample_kind)


def run_suite(workload_ids: tuple[str, ...] | list[str], config: RunConfig) -> RunResult:
    from .environment import _git_commit
    from .workload import get_workload
    from .workloads import register_all

    register_all()

    if workload_ids:
        workloads = [get_workload(item) for item in workload_ids]
    else:
        workloads = _selected_workloads(config)

    gpu_available = _gpu_available()
    warmups, repeats = selected_counts(config)
    diagnostics = config.mode == "diagnose"
    artifact_dir = Path(config.output_dir)

    samples: list[Sample] = []
    for workload in workloads:
        for backend in _backends_for(workload, config, gpu_available):
            request = WorkerRequest(workload.id, backend, warmups, repeats, diagnostics)
            samples.extend(_run_worker(request, artifact_dir))

    if config.mode == "full":
        for workload in _cold_groups(workloads).values():
            for backend in _backends_for(workload, config, gpu_available):
                request = WorkerRequest(workload.id, backend, 0, 1, False,
                                        sample_kind="cold")
                samples.extend(_run_worker(request, artifact_dir))

    return RunResult.new(config.mode, _git_commit(), samples)
