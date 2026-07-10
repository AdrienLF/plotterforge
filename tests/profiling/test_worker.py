from pathlib import Path

from profiling.model import Environment
from profiling.worker import execute_workload
from profiling.workload import Workload, WorkloadCase, WorkloadOutput


ENV = Environment("TestOS", "1", "x86_64", "CPU", "3.13.2", "abc", "cpu",
                  "numpy", None, "CPU", "numpy", "none", "one", 0)


def test_execute_workload_separates_warmup_timing_profile_and_memory(tmp_path: Path):
    calls = []
    workload = Workload(
        "test.counter", 1, "test", "counter", True, ("cpu",), 1.0,
        {"dtype": "none", "problem_size": "one", "tile": 0},
        lambda: WorkloadCase(3, "sha256:fixture"),
        lambda case: (calls.append(case.value) or WorkloadOutput({"value": case.value}, "sha256:out")),
        lambda output: None,
    )
    samples = execute_workload(workload, ENV, warmups=1, repeats=3,
                               diagnostics=True, artifact_dir=tmp_path)
    timing = [item for item in samples if item.phase == "timing"]
    assert len(timing) == 3
    assert all(item.sample_kind == "warm" for item in timing)
    assert any(item.phase == "memory" and item.python_peak_bytes is not None for item in samples)
    assert (tmp_path / "test.counter.prof").is_file()
    assert len(calls) == 6


def test_execute_workload_converts_validation_failure_to_error_sample(tmp_path: Path):
    workload = Workload(
        "test.invalid", 1, "test", "invalid", True, ("cpu",), 1.0,
        {"dtype": "none", "problem_size": "one", "tile": 0},
        lambda: WorkloadCase(1, "sha256:fixture"),
        lambda case: WorkloadOutput({"value": case.value}, "sha256:bad"),
        lambda output: (_ for _ in ()).throw(ValueError("checksum changed")),
    )
    samples = execute_workload(workload, ENV, 0, 1, False, tmp_path)
    assert samples[0].outcome == "error"
    assert "checksum changed" in samples[0].reason
