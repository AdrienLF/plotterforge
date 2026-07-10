from profiling.model import Aggregate
from profiling.report import compare_aggregate, nearest_rank, summarize_values


def aggregate(workload_id, segment, median, samples):
    ordered = tuple(sorted(float(value) for value in samples))
    return Aggregate(
        workload_id=workload_id, workload_version=1, fixture_checksum="sha256:fixture",
        segment_key=segment, count=len(ordered), samples_ms=ordered,
        minimum_ms=ordered[0], median_ms=float(median), p90_ms=ordered[-1],
        maximum_ms=ordered[-1], peak_python_bytes=None, peak_gpu_bytes=None,
    )


def test_nearest_rank_and_summary_are_deterministic():
    values = [10, 20, 30, 40, 50]
    assert nearest_rank(values, 0.9) == 50
    assert summarize_values(values) == (10, 30, 50, 50)


def test_warning_requires_ratio_floor_and_sample_majority():
    baseline = aggregate("w", "segment", median=100, samples=[90, 100, 110, 100])
    warned = aggregate("w", "segment", median=130, samples=[125, 126, 130, 139])
    assert compare_aggregate(warned, baseline, 25).status == "warning"
    too_small = aggregate("w", "segment", median=124, samples=[123, 124, 125, 126])
    assert compare_aggregate(too_small, baseline, 25).status == "stable"
    noisy = aggregate("w", "segment", median=130, samples=[90, 99, 130, 150])
    assert compare_aggregate(noisy, baseline, 25).status == "stable"


def test_segment_mismatch_is_incomparable():
    current = aggregate("w", "mps-a", median=130, samples=[130])
    baseline = aggregate("w", "cuda-b", median=100, samples=[100])
    result = compare_aggregate(current, baseline, 25)
    assert result.status == "incomparable"
