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

SHAPE_FIELD_PARAMS = [
    Param(
        "layout",
        "enum",
        "square",
        group="Field",
        choices=["square", "brick", "hex", "triangular", "jittered"],
    ),
    Param(
        "combination_mode",
        "enum",
        "nested",
        group="Field",
        choices=["nested", "alternating", "connected", "overlapping"],
    ),
    Param("rows", "int", 7, group="Field", min=1, max=60),
    Param("columns", "int", 5, group="Field", min=1, max=60),
    Param("spacing", "float", 4.2, group="Field", min=0.2, max=40, help="cm"),
    Param(
        "field_rotation", "angle", 0.0, group="Field", min=-180, max=180
    ),
    Param(
        "field_offset_x", "float", 0.0, group="Field", min=-60, max=60, help="cm"
    ),
    Param(
        "field_offset_y", "float", 0.0, group="Field", min=-60, max=60, help="cm"
    ),
    Param("layout_jitter", "float", 0.25, group="Field", min=0, max=1),
    Param(
        "modulation_source",
        "enum",
        "none",
        group="Evolution",
        choices=["none", "row", "column", "radial", "wave", "noise"],
    ),
    Param(
        "modulation_target",
        "enum",
        "scale",
        group="Evolution",
        choices=["scale", "rotation", "offset", "combined"],
    ),
    Param(
        "modulation_amount", "float", 0.0, group="Evolution", min=0, max=2
    ),
    Param(
        "modulation_frequency", "float", 1.0, group="Evolution", min=0.05, max=12
    ),
    Param(
        "modulation_phase",
        "angle",
        0.0,
        group="Evolution",
        min=-360,
        max=360,
    ),
    Param("position_jitter", "float", 0.0, group="Random", min=0, max=1),
    Param("rotation_jitter", "float", 0.0, group="Random", min=0, max=180),
    Param("scale_jitter", "float", 0.0, group="Random", min=0, max=1),
    Param(
        "drop_probability", "float", 0.0, group="Random", min=0, max=0.95
    ),
    Param("seed", "int", 0, group="Random"),
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


def normalize_shape_field_params(schema, values):
    normalized = validate(schema, values)
    normalized["shape_layers"] = normalize_shape_layers(
        (values or {}).get("shape_layers", DEFAULT_SHAPE_LAYERS)
    )
    return normalized


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


def field_points(params, rng):
    rows, columns = int(params["rows"]), int(params["columns"])
    spacing, layout = float(params["spacing"]), params["layout"]
    raw = []
    for row in range(rows):
        for column in range(columns):
            if layout == "brick":
                x, y = (column + 0.5 * (row % 2)) * spacing, row * spacing
            elif layout == "hex":
                x = column * spacing * 1.5
                y = (row + 0.5 * (column % 2)) * spacing * math.sqrt(3)
            elif layout == "triangular":
                x = (column + 0.5 * (row % 2)) * spacing
                y = row * spacing * math.sqrt(3) / 2
            else:
                x, y = column * spacing, row * spacing
            if layout == "jittered":
                amount = params["layout_jitter"] * spacing
                x += rng.uniform(-amount, amount)
                y += rng.uniform(-amount, amount)
            raw.append(
                {
                    "row": row,
                    "column": column,
                    "index": len(raw),
                    "x": x,
                    "y": y,
                }
            )

    center_x = (min(tile["x"] for tile in raw) + max(tile["x"] for tile in raw)) / 2
    center_y = (min(tile["y"] for tile in raw) + max(tile["y"] for tile in raw)) / 2
    target_x = float(params.get("page_width", 29.7)) / 2 + params["field_offset_x"]
    target_y = float(params.get("page_height", 42.0)) / 2 + params["field_offset_y"]
    angle = math.radians(params["field_rotation"])
    cosine, sine = math.cos(angle), math.sin(angle)
    for tile in raw:
        x, y = tile["x"] - center_x, tile["y"] - center_y
        tile["x"] = target_x + x * cosine - y * sine
        tile["y"] = target_y + x * sine + y * cosine
    return raw


def modulation_value(params, tile, max_radius, seed):
    source = params["modulation_source"]
    if source == "none":
        return 0.0
    if source == "row":
        return -1.0 + 2.0 * tile["row"] / max(1, params["rows"] - 1)
    if source == "column":
        return -1.0 + 2.0 * tile["column"] / max(1, params["columns"] - 1)
    center_x = float(params.get("page_width", 29.7)) / 2 + params["field_offset_x"]
    center_y = float(params.get("page_height", 42.0)) / 2 + params["field_offset_y"]
    if source == "radial":
        distance = math.hypot(tile["x"] - center_x, tile["y"] - center_y)
        return -1.0 + 2.0 * distance / max(max_radius, 1e-9)
    if source == "noise":
        return random.Random((seed + 1) * 1_000_003 + tile["index"]).uniform(
            -1.0, 1.0
        )
    phase = math.radians(params["modulation_phase"])
    progress = tile["index"] / max(1, params["rows"] * params["columns"] - 1)
    return math.sin(
        2 * math.pi * params["modulation_frequency"] * progress + phase
    )


def transform_line(line, scale, rotation, x, y):
    angle = math.radians(rotation)
    cosine, sine = math.cos(angle), math.sin(angle)
    return [
        (
            x + scale * px * cosine - scale * py * sine,
            y + scale * px * sine + scale * py * cosine,
        )
        for px, py in line
    ]


def estimate_polylines(params, tile_count):
    layers = [layer for layer in params["shape_layers"] if layer["enabled"]]
    if params["combination_mode"] == "alternating":
        per_tile = max(layer["repeat_count"] for layer in layers)
    else:
        per_tile = sum(layer["repeat_count"] for layer in layers)
    estimate = tile_count * per_tile
    if params["combination_mode"] == "connected":
        estimate += tile_count * 3
    if estimate > 50_000:
        raise ValueError(
            f"Shape Field would emit about {estimate:,} polylines (limit 50,000); "
            "reduce rows, columns, layers, or repeats"
        )
    return estimate


def shape_field(params, seed=0):
    layers = normalize_shape_layers(params.get("shape_layers", DEFAULT_SHAPE_LAYERS))
    params = {**params, "shape_layers": layers}
    rng = random.Random(seed)
    tiles = field_points(params, rng)
    estimate_polylines(params, len(tiles))
    spacing = float(params["spacing"])
    page_width = float(params.get("page_width", 29.7))
    page_height = float(params.get("page_height", 42.0))
    center_x = page_width / 2 + params["field_offset_x"]
    center_y = page_height / 2 + params["field_offset_y"]
    max_radius = max(
        math.hypot(tile["x"] - center_x, tile["y"] - center_y) for tile in tiles
    )
    lines = []
    kept = {}
    enabled = [layer for layer in layers if layer["enabled"]]

    for tile in tiles:
        if rng.random() < params["drop_probability"]:
            continue
        x = tile["x"] + rng.uniform(-1, 1) * params["position_jitter"] * spacing
        y = tile["y"] + rng.uniform(-1, 1) * params["position_jitter"] * spacing
        rotation = rng.uniform(-1, 1) * params["rotation_jitter"]
        scale = max(0.0, 1.0 + rng.uniform(-1, 1) * params["scale_jitter"])
        modulation = modulation_value(params, tile, max_radius, seed)
        amount, target = params["modulation_amount"], params["modulation_target"]
        if target in {"scale", "combined"}:
            scale *= max(0.0, 1.0 + 0.5 * amount * modulation)
        if target in {"rotation", "combined"}:
            rotation += 180.0 * amount * modulation
        if target in {"offset", "combined"}:
            x += 0.5 * spacing * amount * modulation
            y -= 0.5 * spacing * amount * modulation
        kept[(tile["row"], tile["column"])] = (x, y)

        selected = (
            [enabled[tile["index"] % len(enabled)]]
            if params["combination_mode"] == "alternating"
            else enabled
        )
        for layer_index, layer in enumerate(selected):
            layer_x = x + layer["offset_x"] * spacing
            layer_y = y + layer["offset_y"] * spacing
            if params["combination_mode"] == "overlapping" and layer_index:
                angle = 2 * math.pi * (layer_index - 1) / max(
                    1, len(selected) - 1
                )
                layer_x += 0.5 * spacing * math.cos(angle)
                layer_y += 0.5 * spacing * math.sin(angle)
            for repeat in range(layer["repeat_count"]):
                radius = (
                    0.5
                    * spacing
                    * layer["scale"]
                    * scale
                    * layer["repeat_scale"] ** repeat
                )
                if radius <= 1e-9:
                    continue
                base = primitive(layer, radius)
                lines.append(
                    transform_line(
                        base,
                        1.0,
                        layer["rotation"]
                        + rotation
                        + layer["repeat_rotation"] * repeat,
                        layer_x,
                        layer_y,
                    )
                )

    if params["combination_mode"] == "connected":
        directions = [(0, 1), (1, 0)]
        if params["layout"] in {"hex", "triangular"}:
            directions.append((1, 1))
        for (row, column), start in kept.items():
            for row_delta, column_delta in directions:
                end = kept.get((row + row_delta, column + column_delta))
                if end is not None:
                    lines.append([start, end])
    return lines, page_width, page_height
