import json

from profiling.model import Environment, RunResult, Sample
from profiling.cli import main


def write_error_results(tmp_path):
    environment = Environment(
        "TestOS", "1", "x86_64", "CPU", "3.13.2", "abc", "cpu", "numpy",
        None, "CPU", "numpy", "none", "one", 0,
    )
    sample = Sample(
        "test.error", 1, "fixture", "sha256:fixture", "test", environment,
        "timing", "warm", 0, 0.0, None, {}, {}, "sha256:none", "error",
        "ValueError: broken", {},
    )
    path = tmp_path / "results.json"
    path.write_text(json.dumps(RunResult.new("quick", "abc", [sample]).to_dict()))
    return path


def test_quick_writes_json_and_markdown(tmp_path):
    code = main(["quick", "--backend", "cpu", "--repeat", "1",
                 "--category", "primitive", "--output", str(tmp_path)])
    assert code == 0
    assert (tmp_path / "results.json").is_file()
    assert (tmp_path / "summary.md").is_file()


def test_unknown_diagnose_workload_is_an_infrastructure_error(capsys):
    code = main(["diagnose", "missing.workload"])
    assert code == 2
    assert "Unknown workload" in capsys.readouterr().err


def test_baseline_update_requires_successful_results(tmp_path):
    results = write_error_results(tmp_path)
    code = main(["baseline", "update", "--from", str(results),
                 "--name", "cpu-ci", "--output", str(tmp_path / "baselines")])
    assert code == 1
    assert not (tmp_path / "baselines" / "cpu-ci.json").exists()


def test_missing_baseline_is_treated_as_incomparable(tmp_path):
    code = main(["quick", "--backend", "cpu", "--repeat", "1",
                 "--category", "primitive", "--output", str(tmp_path / "out"),
                 "--baseline", str(tmp_path / "missing.json")])
    assert code == 0
    assert "incomparable" in (tmp_path / "out" / "summary.md").read_text().lower()
