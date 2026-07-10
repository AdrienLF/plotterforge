from profiling.runner import RunConfig, selected_counts


def test_profile_modes_have_explicit_counts():
    assert selected_counts(RunConfig(mode="quick")) == (1, 3)
    assert selected_counts(RunConfig(mode="full")) == (2, 10)
    assert selected_counts(RunConfig(mode="diagnose")) == (1, 5)
