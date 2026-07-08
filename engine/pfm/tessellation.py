"""Tessellation PFMs: raster tone drives a periodic vector pattern."""

from __future__ import annotations

from ..params import Param
from ..tessellation import TessellationPattern, render_tessellation
from ..tessellation_patterns import BUILTIN_PATTERNS
from ._params import SEED
from .base import PFM, register

PARAMS = SEED + [
    Param("columns", "int", 18, group="Lattice", min=2, max=160,
          help="Pattern repeats across the page width (more = smaller tiles)"),
    Param("rotation", "angle", 0, group="Lattice", min=-180, max=180,
          help="Rotate the whole lattice around the page"),
    Param("phase_x", "float", 0, group="Lattice", min=-1, max=1, step=0.01,
          help="Slide the lattice along its first axis, in tile units"),
    Param("phase_y", "float", 0, group="Lattice", min=-1, max=1, step=0.01,
          help="Slide the lattice along its second axis, in tile units"),
    Param("tone_response", "float", 1, group="Tone", min=0.1, max=5, step=0.05,
          help="Gamma applied to tile tone before picking a state (>1 favors light states)"),
    Param("invert_tone", "bool", False, group="Tone",
          help="Swap which states dark and light areas of the source use"),
    Param("remove_duplicates", "bool", True, group="Plot",
          help="Drop edges shared by neighboring tiles and weld the rest into longer strokes"),
]


def register_tessellation_pattern(pattern: TessellationPattern) -> PFM:
    def generate(work, values, seed, bounds):
        return render_tessellation(work, pattern, values)
    return register(PFM(id=pattern.id, name=pattern.name,
                        family="tessellation", style="tessellation",
                        params=list(PARAMS), generate=generate))


def replace_tessellation_pattern(pattern: TessellationPattern) -> PFM:
    """Register or replace the PFM for a (re)installed custom pattern.

    ``register()`` assigns ``REGISTRY[pfm.id]``, so re-registering the same
    stable ID swaps the pattern in place without touching layers already
    rendered from the previous version."""
    return register_tessellation_pattern(pattern)


for _pattern in BUILTIN_PATTERNS.values():
    register_tessellation_pattern(_pattern)
