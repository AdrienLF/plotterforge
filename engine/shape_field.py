"""Tiled procedural fields assembled from configurable shape layers."""

from __future__ import annotations

import math
import random

from .params import Param, validate

Point = tuple[float, float]
Line = list[Point]

SHAPE_TYPES = ("circle", "polygon", "star", "diamond", "cross", "spiral", "wave")

SHAPE_LAYER_DEFAULT = {
    "id": "shape",
    "enabled": True,
    "type": "circle",
    "scale": 0.72,
    "rotation": 0.0,
    "offset_x": 0.0,
    "offset_y": 0.0,
    "repeat_count": 1,
    "repeat_scale": 0.78,
    "repeat_rotation": 18.0,
    "segments": 48,
    "sides": 6,
    "points": 7,
    "inner_ratio": 0.45,
    "aspect": 1.0,
    "arm_width": 0.32,
    "turns": 2.5,
    "cycles": 3.0,
    "amplitude": 0.45,
}

DEFAULT_SHAPE_LAYERS = [
    {**SHAPE_LAYER_DEFAULT, "id": "circle-1", "type": "circle", "scale": 0.78},
    {
        **SHAPE_LAYER_DEFAULT,
        "id": "star-1",
        "type": "star",
        "scale": 0.58,
        "rotation": 18.0,
    },
    {
        **SHAPE_LAYER_DEFAULT,
        "id": "wave-1",
        "type": "wave",
        "scale": 0.46,
        "rotation": 45.0,
    },
]


def _number(value, default, low, high):
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    if not math.isfinite(number):
        number = default
    return max(low, min(high, number))


def _integer(value, default, low, high):
    return int(round(_number(value, default, low, high)))


def _boolean(value):
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def normalize_shape_layer(raw, index):
    raw = raw if isinstance(raw, dict) else {}
    default = SHAPE_LAYER_DEFAULT
    shape_type = str(raw.get("type", default["type"]))
    return {
        "id": str(raw.get("id") or f"shape-{index + 1}"),
        "enabled": _boolean(raw.get("enabled", default["enabled"])),
        "type": shape_type if shape_type in SHAPE_TYPES else default["type"],
        "scale": _number(raw.get("scale"), default["scale"], 0.0, 4.0),
        "rotation": _number(raw.get("rotation"), default["rotation"], -360.0, 360.0),
        "offset_x": _number(raw.get("offset_x"), default["offset_x"], -4.0, 4.0),
        "offset_y": _number(raw.get("offset_y"), default["offset_y"], -4.0, 4.0),
        "repeat_count": _integer(
            raw.get("repeat_count"), default["repeat_count"], 1, 24
        ),
        "repeat_scale": _number(
            raw.get("repeat_scale"), default["repeat_scale"], 0.05, 2.0
        ),
        "repeat_rotation": _number(
            raw.get("repeat_rotation"), default["repeat_rotation"], -360.0, 360.0
        ),
        "segments": _integer(raw.get("segments"), default["segments"], 3, 360),
        "sides": _integer(raw.get("sides"), default["sides"], 3, 24),
        "points": _integer(raw.get("points"), default["points"], 3, 24),
        "inner_ratio": _number(
            raw.get("inner_ratio"), default["inner_ratio"], 0.05, 0.95
        ),
        "aspect": _number(raw.get("aspect"), default["aspect"], 0.1, 3.0),
        "arm_width": _number(
            raw.get("arm_width"), default["arm_width"], 0.05, 0.95
        ),
        "turns": _number(raw.get("turns"), default["turns"], 0.25, 12.0),
        "cycles": _number(raw.get("cycles"), default["cycles"], 0.25, 12.0),
        "amplitude": _number(
            raw.get("amplitude"), default["amplitude"], 0.0, 1.0
        ),
    }


def normalize_shape_layers(raw_layers):
    layers = [
        normalize_shape_layer(raw, index)
        for index, raw in enumerate(raw_layers or [])
    ]
    if not any(layer["enabled"] for layer in layers):
        raise ValueError("Shape Field needs at least one enabled shape layer")
    return layers


def _polar(radius, angle):
    return radius * math.cos(angle), radius * math.sin(angle)


def _closed(points):
    return [*points, points[0]]


def primitive(layer, radius):
    kind = layer["type"]
    if kind == "circle":
        count = layer["segments"]
        return _closed(
            [_polar(radius, 2 * math.pi * i / count) for i in range(count)]
        )
    if kind == "polygon":
        count = layer["sides"]
        return _closed(
            [
                _polar(radius, 2 * math.pi * i / count - math.pi / 2)
                for i in range(count)
            ]
        )
    if kind == "star":
        count = layer["points"] * 2
        return _closed(
            [
                _polar(
                    radius if i % 2 == 0 else radius * layer["inner_ratio"],
                    math.pi * i / layer["points"] - math.pi / 2,
                )
                for i in range(count)
            ]
        )
    if kind == "diamond":
        aspect = layer["aspect"]
        return [
            (0.0, -radius),
            (radius * aspect, 0.0),
            (0.0, radius),
            (-radius * aspect, 0.0),
            (0.0, -radius),
        ]
    if kind == "cross":
        arm = radius * layer["arm_width"]
        return [
            (-arm, -radius),
            (arm, -radius),
            (arm, -arm),
            (radius, -arm),
            (radius, arm),
            (arm, arm),
            (arm, radius),
            (-arm, radius),
            (-arm, arm),
            (-radius, arm),
            (-radius, -arm),
            (-arm, -arm),
            (-arm, -radius),
        ]
    if kind == "spiral":
        count = layer["segments"]
        return [
            _polar(
                radius * i / count,
                2 * math.pi * layer["turns"] * i / count - math.pi / 2,
            )
            for i in range(count + 1)
        ]
    count = layer["segments"]
    return [
        (
            -radius + 2 * radius * i / count,
            radius
            * layer["amplitude"]
            * math.sin(2 * math.pi * layer["cycles"] * i / count),
        )
        for i in range(count + 1)
    ]
