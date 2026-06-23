"""Streamline family — evenly-spaced streamlines through a vector field."""

from __future__ import annotations

from PIL import Image

from ..params import Param
from ..streamline import run_streamlines
from .base import PFM, register
from ._params import SEED

_STREAM_PARAMS = [
    Param("min_spacing", "float", 3.0, group="Streamlines", min=0.5, max=20),
    Param("max_spacing", "float", 10.0, group="Streamlines", min=2, max=50),
    Param("min_length", "float", 6.0, group="Streamlines", min=0, max=200),
    Param("max_length", "float", 200.0, group="Streamlines", min=0, max=500),
    Param("tone", "float", 50.0, group="Streamlines", min=0, max=100),
    Param("distortion", "float", 0.0, group="Streamlines", min=0, max=100),
]

_FLOW_PARAMS = [
    Param("start_angle", "angle", 0.0, group="Flow Field", min=-360, max=360),
    Param("x_freq", "float", 1.0, group="Flow Field", min=0.001, max=4),
    Param("y_freq", "float", 1.0, group="Flow Field", min=0.001, max=4),
    Param("scale_freq", "float", 1.0, group="Flow Field", min=0.01, max=20),
    Param("amplitude", "float", 0.5, group="Flow Field", min=0.0, max=1.0),
]

_EDGE_PARAMS = [
    Param("edge_power", "float", 70.0, group="Edge Field", min=0, max=100),
    Param("etf_iterations", "int", 4, group="Edge Field", min=0, max=30),
]

_SUPER_PARAMS = [
    Param("start_angle", "angle", 0.0, group="Superformula", min=-360, max=360),
    Param("centre_x", "float", 50.0, group="Superformula", min=0, max=100),
    Param("centre_y", "float", 50.0, group="Superformula", min=0, max=100),
    Param("frequency", "float", 6.0, group="Superformula", min=0.0, max=20),
]


def _make(kind: str):
    def gen(work: Image.Image, v: dict, seed: int, bounds):
        return run_streamlines(work, v, seed, kind)
    return gen


register(PFM(
    id="streamlines_flow_field", name="Streamlines Flow Field",
    family="streamline", style="flow",
    params=SEED + _STREAM_PARAMS + _FLOW_PARAMS, generate=_make("flow"),
))

register(PFM(
    id="streamlines_edge_field", name="Streamlines Edge Field",
    family="streamline", style="edge",
    params=SEED + _STREAM_PARAMS + _EDGE_PARAMS + _FLOW_PARAMS, generate=_make("edge"),
))

register(PFM(
    id="streamlines_superformula", name="Streamlines Superformula",
    family="streamline", style="superformula",
    params=SEED + _STREAM_PARAMS + _SUPER_PARAMS, generate=_make("superformula"),
))
