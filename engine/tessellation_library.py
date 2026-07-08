"""Custom tessellation package validation and filesystem-backed library.

A "package" is a JSON manifest (name, lattice, bounds, parameter bindings)
plus exactly 32 raw SVG "states" baked by the Cavalry bridge. This module
turns that untrusted bundle into a normalized, unit-square
``engine.tessellation.TessellationPattern`` -- flattening curves to
polylines, rejecting active/external SVG content, and enforcing size limits
-- then persists validated packages atomically so they survive restarts.
"""

from __future__ import annotations

import io
import hashlib
import json
import logging
import math
import os
import re
import shutil
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import svgelements as se
from PIL import Image, ImageDraw

from .tessellation import (
    ParameterBinding,
    TessellationPattern,
    TilePath,
    TileState,
    render_tessellation,
)

logger = logging.getLogger(__name__)

FORMAT_VERSION = 1
STATE_COUNT = 32
MAX_SVG_BYTES = 8 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_PATHS = 2_000
MAX_POINTS = 200_000
MAX_BINDINGS = 16
MAX_COORD = 1_000_000
FORBIDDEN_TAGS = {"script", "image", "foreignObject", "use"}
FORBIDDEN_ATTRS = {"href", "xlink:href", "onload", "onclick"}

FLATTEN_STEP = 0.4  # max chord step, in source units, when subdividing curves
PREVIEW_SIZE = (105, 148)

ALLOWED_SHAPES = (se.Path, se.Polyline, se.Polygon, se.SimpleLine,
                  se.Rect, se.Circle, se.Ellipse)


class PatternValidationError(Exception):
    """Raised when a manifest or SVG state fails package validation."""


# --------------------------------------------------------------------------
# Slugging
# --------------------------------------------------------------------------

def slugify_pattern_name(name: str) -> str:
    """Normalize an arbitrary pattern name into a stable custom-pattern ID."""
    normalized = unicodedata.normalize("NFKD", name or "")
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_only.lower()
    slug = re.sub(r"[^a-z0-9]+", "_", lowered).strip("_")
    if not slug:
        digest = hashlib.sha256((name or "").strip().encode("utf-8")).hexdigest()[:12]
        slug = f"unicode_{digest}"
    return f"tessellation_custom_{slug}"


# --------------------------------------------------------------------------
# SVG parsing / flattening
# --------------------------------------------------------------------------

def _local_name(qualified: str) -> str:
    return qualified.split("}", 1)[1] if qualified.startswith("{") else qualified


def _reject_forbidden_content(svg_text: str) -> None:
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError as exc:
        raise PatternValidationError(f"Malformed SVG XML: {exc}") from exc
    for element in root.iter():
        tag = _local_name(element.tag)
        if tag in FORBIDDEN_TAGS:
            raise PatternValidationError(f"Forbidden SVG tag <{tag}>")
        for attr in element.attrib:
            if attr in FORBIDDEN_ATTRS or _local_name(attr) in FORBIDDEN_ATTRS:
                raise PatternValidationError(f"Forbidden SVG attribute {attr!r}")


def _checked_point(point) -> tuple[float, float]:
    x, y = float(point[0]), float(point[1])
    if not (math.isfinite(x) and math.isfinite(y)):
        raise PatternValidationError("SVG contains non-finite coordinates")
    if abs(x) > MAX_COORD or abs(y) > MAX_COORD:
        raise PatternValidationError(f"SVG coordinate exceeds {MAX_COORD}")
    return x, y


def _flatten_segments(segments):
    """Yield (points, closed) tuples, one per subpath, from svgelements
    path segments -- subdividing curves to a max chord step of FLATTEN_STEP."""
    points: list[tuple[float, float]] = []
    closed = False
    for segment in segments:
        if isinstance(segment, se.Move):
            if points:
                yield points, closed
            points = [_checked_point(segment.end)]
            closed = False
        elif isinstance(segment, se.Close):
            closed = True
        elif isinstance(segment, se.Line):
            points.append(_checked_point(segment.end))
        elif isinstance(segment, se.Curve):
            length = segment.length()
            steps = max(1, math.ceil(length / FLATTEN_STEP)) if length else 1
            sampled = segment.npoint([i / steps for i in range(1, steps + 1)])
            for xy in sampled:
                points.append(_checked_point(xy))
        # Other segment kinds (e.g. a bare PathSegment) are ignored.
    if points:
        yield points, closed


def parse_state_svg(svg: str, bounds: tuple[float, float, float, float]) -> TileState:
    """Parse, flatten, and normalize one raw SVG state into a TileState.

    Points are normalized into the unit square by offsetting to ``bounds``'
    minimum corner and dividing by its width/height.
    """
    _reject_forbidden_content(svg)
    minx, miny, maxx, maxy = (float(v) for v in bounds)
    width, height = maxx - minx, maxy - miny
    if not (math.isfinite(width) and math.isfinite(height)) or width <= 0 or height <= 0:
        raise PatternValidationError("Pattern bounds must be finite with positive width/height")

    try:
        parsed = se.SVG.parse(io.StringIO(svg))
    except Exception as exc:  # svgelements can raise a variety of errors
        raise PatternValidationError(f"Could not parse SVG: {exc}") from exc

    tile_paths: list[TilePath] = []
    total_points = 0
    for element in parsed.elements():
        if not isinstance(element, ALLOWED_SHAPES):
            continue
        try:
            segments = element.segments(transformed=True)
        except Exception as exc:
            raise PatternValidationError(f"Could not flatten SVG shape: {exc}") from exc
        for points, closed in _flatten_segments(segments):
            if len(points) < 2:
                continue
            normalized = tuple(
                ((x - minx) / width, (y - miny) / height) for x, y in points
            )
            tile_paths.append(TilePath(normalized, closed))
            total_points += len(normalized)
            if len(tile_paths) > MAX_PATHS:
                raise PatternValidationError(f"State exceeds {MAX_PATHS} paths")
            if total_points > MAX_POINTS:
                raise PatternValidationError(f"State exceeds {MAX_POINTS} points")

    if not tile_paths:
        raise PatternValidationError("State SVG contains no drawable paths")
    return TileState(tuple(tile_paths))


# --------------------------------------------------------------------------
# Manifest validation
# --------------------------------------------------------------------------

def _number(value, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PatternValidationError(f"{label} must be a number")
    value = float(value)
    if not math.isfinite(value):
        raise PatternValidationError(f"{label} must be finite")
    return value


def _vector(value, label: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise PatternValidationError(f"{label} must be a 2-element vector")
    return (_number(value[0], f"{label}[0]"), _number(value[1], f"{label}[1]"))


def _validate_bounds(value) -> tuple[float, float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise PatternValidationError("bounds must be a 4-element [minx, miny, maxx, maxy]")
    minx, miny, maxx, maxy = (_number(v, "bounds value") for v in value)
    if maxx - minx <= 0 or maxy - miny <= 0:
        raise PatternValidationError("bounds must have positive width and height")
    return (minx, miny, maxx, maxy)


def _validate_curve(curve):
    if curve is None:
        return None
    if not isinstance(curve, (list, tuple)):
        raise PatternValidationError("binding curve must be null or a list of [name, value] pairs")
    return tuple(
        (str(name), _number(val, "binding curve value"))
        for name, val in curve
    )


def _validate_bindings(value) -> tuple[ParameterBinding, ...]:
    if not isinstance(value, (list, tuple)):
        raise PatternValidationError("bindings must be a list")
    if len(value) > MAX_BINDINGS:
        raise PatternValidationError(f"At most {MAX_BINDINGS} bindings are accepted")
    seen: set[tuple[str, str]] = set()
    bindings = []
    for entry in value:
        if not isinstance(entry, dict):
            raise PatternValidationError("Each binding must be an object")
        layer_id = entry.get("layer_id")
        attribute_id = entry.get("attribute_id")
        if not isinstance(layer_id, str) or not layer_id:
            raise PatternValidationError("binding.layer_id must be a non-empty string")
        if not isinstance(attribute_id, str) or not attribute_id:
            raise PatternValidationError("binding.attribute_id must be a non-empty string")
        key = (layer_id, attribute_id)
        if key in seen:
            raise PatternValidationError(f"Duplicate binding for {layer_id}/{attribute_id}")
        seen.add(key)
        light = _number(entry.get("light"), "binding.light")
        dark = _number(entry.get("dark"), "binding.dark")
        curve = _validate_curve(entry.get("curve"))
        bindings.append(ParameterBinding(layer_id=layer_id, attribute_id=attribute_id,
                                          light=light, dark=dark, curve=curve))
    return tuple(bindings)


def validate_package(manifest: dict, states: list[str]) -> TessellationPattern:
    """Validate a manifest + 32 raw SVG states and return a normalized
    TessellationPattern, or raise PatternValidationError."""
    if not isinstance(manifest, dict):
        raise PatternValidationError("manifest must be an object")

    format_version = manifest.get("format_version")
    if isinstance(format_version, bool) or format_version != FORMAT_VERSION:
        raise PatternValidationError(f"Unsupported format_version {format_version!r}")

    name = manifest.get("name")
    if not isinstance(name, str) or not (1 <= len(name.strip()) <= 80):
        raise PatternValidationError("Pattern name must be 1-80 visible characters")
    name = name.strip()
    pattern_id = slugify_pattern_name(name)

    lattice = manifest.get("lattice")
    if not isinstance(lattice, dict):
        raise PatternValidationError("lattice must be an object with a and b vectors")
    raw_a = _vector(lattice.get("a"), "lattice.a")
    raw_b = _vector(lattice.get("b"), "lattice.b")

    bounds = _validate_bounds(manifest.get("bounds"))
    minx, miny, maxx, maxy = bounds
    width, height = maxx - minx, maxy - miny
    a = (raw_a[0] / width, raw_a[1] / height)
    b = (raw_b[0] / width, raw_b[1] / height)
    det = a[0] * b[1] - a[1] * b[0]
    if not math.isfinite(det) or abs(det) < 1e-9:
        raise PatternValidationError("Lattice vectors must be finite and non-collinear")

    bindings = _validate_bindings(manifest.get("bindings", []))

    if len(states) != STATE_COUNT:
        raise PatternValidationError(
            f"Exactly {STATE_COUNT} states are required, got {len(states)}")

    tile_states = []
    total_bytes = 0
    for index, svg_text in enumerate(states):
        raw_bytes = svg_text.encode("utf-8") if isinstance(svg_text, str) else bytes(svg_text)
        if len(raw_bytes) > MAX_SVG_BYTES:
            raise PatternValidationError(f"State {index} exceeds {MAX_SVG_BYTES} bytes")
        total_bytes += len(raw_bytes)
        if total_bytes > MAX_TOTAL_BYTES:
            raise PatternValidationError(f"Package exceeds {MAX_TOTAL_BYTES} total bytes")
        tile_states.append(parse_state_svg(svg_text, bounds))

    try:
        return TessellationPattern(
            id=pattern_id, name=name, source="custom",
            a=a, b=b, bounds=(0.0, 0.0, 1.0, 1.0),
            states=tuple(tile_states), bindings=bindings,
        )
    except ValueError as exc:
        raise PatternValidationError(str(exc)) from exc


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------

PREVIEW_VALUES = {
    "columns": 10, "rotation": 0, "phase_x": 0, "phase_y": 0,
    "tone_response": 1, "invert_tone": False, "remove_duplicates": True,
}


def _pattern_to_json(pattern: TessellationPattern, updated_at: str) -> dict:
    return {
        "id": pattern.id,
        "name": pattern.name,
        "source": pattern.source,
        "a": list(pattern.a),
        "b": list(pattern.b),
        "bounds": list(pattern.bounds),
        "states": [
            {"paths": [{"points": [list(p) for p in path.points],
                        "closed": path.closed}
                       for path in state.paths]}
            for state in pattern.states
        ],
        "bindings": [
            {"layer_id": binding.layer_id,
             "attribute_id": binding.attribute_id,
             "light": binding.light,
             "dark": binding.dark,
             "curve": [list(pair) for pair in binding.curve]
                      if binding.curve is not None else None}
            for binding in pattern.bindings
        ],
        "updated_at": updated_at,
    }


def _pattern_from_json(data: dict) -> TessellationPattern:
    states = tuple(
        TileState(tuple(
            TilePath(tuple((float(x), float(y)) for x, y in path["points"]),
                     bool(path["closed"]))
            for path in state["paths"]
        ))
        for state in data["states"]
    )
    bindings = tuple(
        ParameterBinding(
            layer_id=str(binding["layer_id"]),
            attribute_id=str(binding["attribute_id"]),
            light=float(binding["light"]),
            dark=float(binding["dark"]),
            curve=tuple((str(name), float(value)) for name, value in binding["curve"])
                  if binding.get("curve") is not None else None,
        )
        for binding in data["bindings"]
    )
    return TessellationPattern(
        id=str(data["id"]), name=str(data["name"]), source=str(data["source"]),
        a=tuple(float(v) for v in data["a"]),
        b=tuple(float(v) for v in data["b"]),
        bounds=tuple(float(v) for v in data["bounds"]),
        states=states, bindings=bindings,
    )


def _render_preview(pattern: TessellationPattern) -> Image.Image:
    """105x148 preview: the pattern over a vertical light-to-dark gradient."""
    width, height = PREVIEW_SIZE
    gradient = Image.new("L", PREVIEW_SIZE)
    for y in range(height):
        gradient.paste(int(20 + 215 * y / (height - 1)), (0, y, width, y + 1))
    items = render_tessellation(gradient, pattern, PREVIEW_VALUES)
    canvas = Image.new("RGB", PREVIEW_SIZE, "white")
    draw = ImageDraw.Draw(canvas)
    for item in items:
        if item.path is None:
            continue
        points = [(float(x), float(y)) for x, y in item.path.points]
        if item.path.closed:
            points.append(points[0])
        if len(points) >= 2:
            draw.line(points, fill="black", width=1)
    return canvas


def _write_flushed(path: Path, data: bytes) -> None:
    with open(path, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


class TessellationLibrary:
    """Filesystem-backed store of validated custom tessellation patterns.

    Each entry lives in ``root/<pattern_id>/`` holding ``pattern.json`` (the
    normalized dataclasses) and ``preview.png``. Installation stages the new
    entry in a sibling directory and swaps it in atomically, so an existing
    package is never left half-replaced.
    """

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def install(self, manifest: dict, states: list[str]) -> TessellationPattern:
        pattern = validate_package(manifest, states)
        updated_at = datetime.now(timezone.utc).isoformat()
        staging = self.root / f"{pattern.id}.staging"
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        try:
            payload = json.dumps(_pattern_to_json(pattern, updated_at),
                                 separators=(",", ":")).encode("utf-8")
            _write_flushed(staging / "pattern.json", payload)
            preview_buffer = io.BytesIO()
            _render_preview(pattern).save(preview_buffer, format="PNG")
            _write_flushed(staging / "preview.png", preview_buffer.getvalue())
            self._atomic_replace(staging, self.root / pattern.id)
        finally:
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
        return pattern

    def _atomic_replace(self, staging: Path, target: Path) -> None:
        """Swap ``staging`` into ``target``, restoring the previous entry if
        the final rename fails."""
        backup = target.with_name(target.name + ".backup")
        if backup.exists():
            shutil.rmtree(backup)
        had_previous = target.exists()
        if had_previous:
            target.rename(backup)
        try:
            staging.rename(target)
        except BaseException:
            if had_previous:
                backup.rename(target)
            raise
        if had_previous:
            shutil.rmtree(backup, ignore_errors=True)

    def _entry_dirs(self) -> list[Path]:
        return sorted(
            entry for entry in self.root.iterdir()
            if entry.is_dir() and (entry / "pattern.json").is_file()
        )

    def _load_entry(self, entry: Path) -> TessellationPattern:
        data = json.loads((entry / "pattern.json").read_text("utf-8"))
        if data.get("id") != entry.name:
            raise PatternValidationError(
                f"Entry {entry.name!r} declares mismatched id {data.get('id')!r}")
        return _pattern_from_json(data)

    def get(self, pattern_id: str) -> TessellationPattern:
        entry = self.root / pattern_id
        if not (entry / "pattern.json").is_file():
            raise KeyError(f"Unknown tessellation pattern {pattern_id!r}")
        return self._load_entry(entry)

    def load_all(self) -> list[TessellationPattern]:
        patterns = []
        for entry in self._entry_dirs():
            try:
                patterns.append(self._load_entry(entry))
            except Exception:
                logger.exception("Skipping invalid tessellation package %s", entry)
        return patterns

    def list(self) -> list[dict]:
        records = []
        for entry in self._entry_dirs():
            try:
                data = json.loads((entry / "pattern.json").read_text("utf-8"))
                if data.get("id") != entry.name:
                    raise PatternValidationError("mismatched id")
                records.append({"id": data["id"], "name": data["name"],
                                "source": data["source"],
                                "updated_at": data["updated_at"]})
            except Exception:
                logger.exception("Skipping invalid tessellation package %s", entry)
        return sorted(records, key=lambda record: record["id"])
