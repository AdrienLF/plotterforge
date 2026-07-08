from typing import get_type_hints

import pytest

from engine.tessellation import (
    ParameterBinding,
    TessellationPattern,
    TilePath,
    TileState,
    state_at_tone,
)


def state(x, *, closed=False, points=2):
    pts = tuple((x + i, x) for i in range(points))
    return TileState((TilePath(pts, closed),))


def pattern(states):
    return TessellationPattern(
        id="test", name="Test", source="builtin",
        a=(1.0, 0.0), b=(0.0, 1.0), bounds=(0.0, 0.0, 1.0, 1.0),
        states=tuple(states), bindings=(),
    )


def test_pattern_requires_32_states_and_nondegenerate_lattice():
    with pytest.raises(ValueError, match="32 states"):
        pattern([state(0.0)])
    with pytest.raises(ValueError, match="non-collinear"):
        TessellationPattern(
            id="bad", name="Bad", source="builtin",
            a=(1.0, 0.0), b=(2.0, 0.0), bounds=(0, 0, 1, 1),
            states=tuple(state(0.0) for _ in range(32)), bindings=(),
        )


def test_parameter_binding_curve_metadata_is_immutable():
    binding = ParameterBinding(
        layer_id="detail",
        attribute_id="spacing",
        light=0.1,
        dark=0.9,
        curve=(("bias", 0.25), ("gain", 0.75)),
    )

    assert get_type_hints(ParameterBinding)["curve"] == (
        tuple[tuple[str, float], ...] | None
    )
    with pytest.raises(TypeError):
        binding.curve[0] = ("bias", 0.5)
    with pytest.raises(TypeError):
        binding.curve[0][1] = 0.5


def test_state_at_tone_interpolates_compatible_neighbors():
    def detailed_state(offset):
        return TileState((
            TilePath(((offset, offset + 1), (offset + 2, offset + 3))),
            TilePath(
                ((offset + 4, offset + 5), (offset + 6, offset + 7)),
                closed=True,
            ),
        ))

    p = pattern([detailed_state(float(i)) for i in range(32)])
    out = state_at_tone(p, 0.5)
    expected = detailed_state(15.5)

    assert len(out.paths) == len(expected.paths)
    for actual_path, expected_path in zip(out.paths, expected.paths):
        assert actual_path.closed == expected_path.closed
        assert len(actual_path.points) == len(expected_path.points)
        for actual_point, expected_point in zip(
            actual_path.points, expected_path.points
        ):
            assert actual_point == pytest.approx(expected_point)


def test_state_at_tone_clamps_out_of_range_tones():
    p = pattern([state(float(i)) for i in range(32)])

    assert state_at_tone(p, -1.0) == p.states[0]
    assert state_at_tone(p, 2.0) == p.states[31]


@pytest.mark.parametrize("changed", [
    TileState((TilePath(((16, 16), (17, 16)), True),)),
    TileState((TilePath(((16, 16), (17, 16), (18, 16)), False),)),
    TileState((TilePath(((16, 16), (17, 16)), False), TilePath(((0, 0), (1, 1)), False))),
])
def test_state_at_tone_uses_nearest_whole_state_when_topology_changes(changed):
    states = [state(float(i)) for i in range(32)]
    states[16] = changed
    p = pattern(states)
    assert state_at_tone(p, 15.75 / 31) == changed


def test_state_at_tone_chooses_nearest_state_on_both_sides_of_midpoint():
    states = [state(float(i)) for i in range(32)]
    changed = TileState((TilePath(((16, 16), (17, 16)), True),))
    states[16] = changed
    p = pattern(states)

    assert state_at_tone(p, 15.49 / 31) == states[15]
    assert state_at_tone(p, 15.51 / 31) == changed
