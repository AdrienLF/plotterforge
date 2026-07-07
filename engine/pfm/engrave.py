"""Engraving PFM — tone by line density, direction from a mixable field."""

from __future__ import annotations

from ..engrave import run_engraving
from ..params import Param
from ._params import SEED
from .base import PFM, register
from .streamline import _STREAM_PARAMS

_ENGRAVE_PARAMS = [
    Param("edge_weight", "float", 1.0, group="Direction", min=0, max=2,
          help="How strongly lines follow the image's edge-tangent flow"),
    Param("etf_iterations", "int", 4, group="Direction", min=0, max=20,
          help="Smoothing passes on the edge-tangent field"),
    Param("noise_weight", "float", 0.0, group="Direction", min=0, max=2,
          help="Blend in coherent noise wander"),
    Param("noise_scale", "float", 25.0, group="Direction", min=2, max=100,
          help="Noise feature size as a % of image size"),
    Param("radial_weight", "float", 0.0, group="Direction", min=0, max=2,
          help="Blend in concentric direction around the centre point"),
    Param("centre_x", "float", 50.0, group="Direction", min=0, max=100,
          help="Concentric centre, as a % of image width"),
    Param("centre_y", "float", 50.0, group="Direction", min=0, max=100,
          help="Concentric centre, as a % of image height"),
    Param("base_angle", "angle", 0.0, group="Direction", min=0, max=360,
          help="Constant rotation added to the whole direction field"),
    Param("direction", "angle", 0.0, group="Direction", min=0, max=360,
          bindable=True,
          help="Bind a field here to fully override the direction mix"),
    Param("bands", "int", 1, group="Crosshatch", min=1, max=3,
          help="Tonal crosshatch bands: darker zones get extra crossed passes"),
    Param("cross_angle", "angle", 60.0, group="Crosshatch", min=10, max=170,
          help="Angle offset between crosshatch bands"),
]

register(PFM(
    id="engraving", name="Engraving", family="streamline", style="engrave",
    params=SEED + _STREAM_PARAMS + _ENGRAVE_PARAMS,
    generate=run_engraving,
))
