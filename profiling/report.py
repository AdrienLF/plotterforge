from __future__ import annotations

from collections import defaultdict
import json
from math import ceil
import os
from pathlib import Path
import pstats
from statistics import median as _median

from .model import Aggregate, Comparison, RunResult, Sample

WARNING_RATIO = 1.20
WARNING_SAMPLE_SHARE = 0.75
TOP_FUNCTIONS = 20


def nearest_rank(values, quantile: float) -> float:
    ordered = sorted(float(value) for value in values)
    index = max(0, ceil(quantile * len(ordered)) - 1)
    return ordered[index]


def summarize_values(values) -> tuple[float, float, float, float]:
    ordered = sorted(float(value) for value in values)
    return ordered[0], float(_median(ordered)), nearest_rank(ordered, 0.9), ordered[-1]


def _is_latency_sample(sample: Sample) -> bool:
    return (sample.phase == "timing" and sample.sample_kind == "warm"
            and sample.outcome == "success")


def aggregate_samples(samples: list[Sample]) -> list[Aggregate]:
    groups: dict[tuple, list[Sample]] = defaultdict(list)
    for sample in samples:
        if _is_latency_sample(sample):
            key = (sample.workload_id, sample.workload_version,
                   sample.fixture_checksum, sample.environment.segment_key())
            groups[key].append(sample)

    memory: dict[tuple, Sample] = {}
    for sample in samples:
        if sample.phase == "memory" and sample.outcome == "success":
            key = (sample.workload_id, sample.workload_version,
                   sample.fixture_checksum, sample.environment.segment_key())
            memory[key] = sample

    aggregates = []
    for key, group in sorted(groups.items()):
        durations = [item.duration_ms for item in group]
        minimum, med, p90, maximum = summarize_values(durations)
        memory_sample = memory.get(key)
        gpu_peak = None
        if memory_sample and memory_sample.gpu_metrics:
            candidates = [value for name, value in memory_sample.gpu_metrics.items()
                          if "peak" in name or "allocated" in name]
            gpu_peak = max(candidates) if candidates else None
        aggregates.append(Aggregate(
            workload_id=key[0], workload_version=key[1], fixture_checksum=key[2],
            segment_key=key[3], count=len(durations),
            samples_ms=tuple(sorted(durations)), minimum_ms=minimum, median_ms=med,
            p90_ms=p90, maximum_ms=maximum,
            peak_python_bytes=memory_sample.python_peak_bytes if memory_sample else None,
            peak_gpu_bytes=gpu_peak,
        ))
    return aggregates


def compare_aggregate(current: Aggregate, baseline: Aggregate,
                      warning_floor_ms: float) -> Comparison:
    comparable = (current.workload_id == baseline.workload_id
                  and current.workload_version == baseline.workload_version
                  and current.fixture_checksum == baseline.fixture_checksum
                  and current.segment_key == baseline.segment_key)
    if not comparable:
        return Comparison("incomparable", None, None,
                          "workload identity or environment segment differs")

    delta_ms = current.median_ms - baseline.median_ms
    if baseline.median_ms <= 0:
        return Comparison("incomparable", delta_ms, None, "baseline median is not positive")

    delta_ratio = current.median_ms / baseline.median_ms
    exceeding = sum(1 for value in current.samples_ms if value > baseline.median_ms)
    required = ceil(WARNING_SAMPLE_SHARE * current.count)

    if (delta_ratio > WARNING_RATIO and delta_ms >= warning_floor_ms
            and exceeding >= required):
        return Comparison("warning", delta_ms, delta_ratio,
                          f"median rose {delta_ratio - 1:.1%} across "
                          f"{exceeding}/{current.count} samples")
    return Comparison("stable", delta_ms, delta_ratio, None)


def _write_atomic(path: Path, payload: str) -> None:
    temporary = path.with_name(path.name + ".partial")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


def _load_baseline(baseline: Path | None) -> dict[tuple, Aggregate]:
    if baseline is None or not Path(baseline).is_file():
        return {}
    data = json.loads(Path(baseline).read_text(encoding="utf-8"))
    run = RunResult.from_dict(data)
    return {(item.workload_id, item.segment_key): item
            for item in aggregate_samples(run.samples)}


def _profile_section(samples: list[Sample]) -> list[str]:
    lines: list[str] = []
    for sample in samples:
        profile_path = sample.artifacts.get("cpu_profile")
        if not profile_path or not Path(profile_path).is_file():
            continue
        stats = pstats.Stats(profile_path)
        lines.append(f"\n#### CPU profile — {sample.workload_id}\n")
        lines.append("```text")
        ordered = sorted(stats.stats.items(), key=lambda kv: kv[1][3], reverse=True)
        for (filename, lineno, name), (_cc, nc, tt, ct, _cal) in ordered[:TOP_FUNCTIONS]:
            location = f"{Path(filename).name}:{lineno}({name})"
            lines.append(f"{ct:10.6f}  {tt:10.6f}  {nc:>8}  {location}")
        lines.append("```")
    return lines


def _warning_floors() -> dict[str, float]:
    """Floors come from the registry; an unregistered workload gets no floor."""
    from .workload import iter_workloads

    return {item.id: item.warning_floor_ms for item in iter_workloads()}


def write_report(run: RunResult, output_dir: Path,
                 baseline: Path | None = None) -> list[Comparison]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    _write_atomic(output_dir / "results.json", json.dumps(run.to_dict(), indent=2))

    aggregates = aggregate_samples(run.samples)
    baselines = _load_baseline(baseline)
    floors = _warning_floors()

    comparisons: list[Comparison] = []
    rows: list[str] = []
    for item in aggregates:
        prior = baselines.get((item.workload_id, item.segment_key))
        if prior is None:
            comparison = Comparison("new", None, None, "no baseline for this segment")
        else:
            comparison = compare_aggregate(item, prior,
                                           floors.get(item.workload_id, 0.0))
        comparisons.append(comparison)

        delta = "—" if comparison.delta_ms is None else f"{comparison.delta_ms:+.1f} ms"
        ratio = "" if comparison.delta_ratio is None else f" ({comparison.delta_ratio - 1:+.1%})"
        memory = "—" if item.peak_python_bytes is None else f"{item.peak_python_bytes / 1024:.0f} KiB"
        gpu = "" if item.peak_gpu_bytes is None else f" / {item.peak_gpu_bytes / 1048576:.1f} MiB GPU"
        rows.append(
            f"| `{item.workload_id}` | {item.count} | {item.minimum_ms:.2f} | "
            f"{item.median_ms:.2f} | {item.p90_ms:.2f} | {item.maximum_ms:.2f} | "
            f"{memory}{gpu} | {delta}{ratio} | {comparison.status} |"
        )

        if comparison.status == "warning" and os.environ.get("GITHUB_ACTIONS") == "true":
            print(f"::warning title=Performance regression::{item.workload_id} "
                  f"median {item.median_ms:.1f} ms "
                  f"({comparison.delta_ratio - 1:+.1%}, {comparison.delta_ms:+.1f} ms)")

    errors = [item for item in run.samples if item.outcome == "error"]
    environments = sorted({item.environment.segment_key() for item in run.samples})

    lines = [
        "# Profiling summary", "",
        f"- Run: `{run.run_id}`", f"- Command: `{run.command}`",
        f"- Commit: `{run.commit}`", f"- Timestamp: {run.timestamp_utc}",
        f"- Environment segments: {len(environments)}",
        f"- Error samples: {len(errors)}", "",
        "| Workload | n | min ms | median ms | p90 ms | max ms | peak mem | Δ median | status |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    lines.extend(rows)

    if errors:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- `{item.workload_id}` ({item.phase}): {item.reason}"
                     for item in errors)

    lines.extend(_profile_section(run.samples))
    _write_atomic(output_dir / "summary.md", "\n".join(lines) + "\n")
    return comparisons


def update_baseline(results_path: Path, baseline_path: Path) -> None:
    """Promote a results file to a named baseline. Never called by CI."""
    data = json.loads(Path(results_path).read_text(encoding="utf-8"))
    run = RunResult.from_dict(data)

    errors = [item for item in run.samples if item.outcome == "error"]
    if errors:
        raise ValueError(
            f"Refusing to baseline a run with {len(errors)} error sample(s): "
            f"{errors[0].workload_id} — {errors[0].reason}")
    if not run.samples:
        raise ValueError("Refusing to baseline a run with no samples")

    for sample in run.samples:
        if sample.environment.requested_backend == "gpu" \
                and sample.environment.actual_backend == "numpy":
            raise ValueError(
                f"Refusing to baseline {sample.workload_id}: GPU requested but NumPy ran")

    baseline_path = Path(baseline_path)
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    _write_atomic(baseline_path, json.dumps(run.to_dict(), indent=2))
