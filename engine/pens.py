"""Pens, Drawing Sets, and shape distribution.

A multi-pen plot is produced by distributing the generated geometry among the
active pens of a Drawing Set, according to a distribution *type* and *order*.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from .geometry import Item, Layer

DISTRIBUTION_TYPES = (
    "single",
    "even",
    "random",
    "random_squiggles",
    "luminance",
    "preconfigured",
)
DISTRIBUTION_ORDERS = ("darkest", "lightest", "displayed", "reversed")


# ── colour helpers ──────────────────────────────────────────────────────────────

def hex_to_rgb(c: str) -> tuple[int, int, int]:
    c = c.lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) < 6:
        return 0, 0, 0
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def colour_luminance(c: str) -> float:
    """Perceived luminance of a hex colour, 0 (black) .. 1 (white)."""
    r, g, b = hex_to_rgb(c)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255.0


# ── pen / drawing set ───────────────────────────────────────────────────────────

@dataclass
class Pen:
    name: str = "Black"
    type: str = "Generic"
    colour: str = "#000000"          # hex rgb
    weight: float = 1.0              # relative share of shapes
    stroke_mm: float = 0.5
    enabled: bool = True

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.type,
            "colour": self.colour,
            "weight": self.weight,
            "stroke_mm": self.stroke_mm,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Pen":
        known = {k: d[k] for k in cls.__dataclass_fields__ if k in d}
        return cls(**known)


@dataclass
class DrawingSet:
    pens: list[Pen] = field(default_factory=lambda: [Pen()])
    distribution_type: str = "luminance"
    distribution_order: str = "darkest"

    def active(self) -> list[Pen]:
        return [p for p in self.pens if p.enabled] or [self.pens[0]]

    def to_dict(self) -> dict:
        return {
            "pens": [p.to_dict() for p in self.pens],
            "distribution_type": self.distribution_type,
            "distribution_order": self.distribution_order,
        }

    @classmethod
    def from_dict(cls, d: dict | None) -> "DrawingSet":
        d = d or {}
        pens = [Pen.from_dict(p) for p in d.get("pens", [])] or [Pen()]
        return cls(
            pens=pens,
            distribution_type=d.get("distribution_type", "luminance"),
            distribution_order=d.get("distribution_order", "darkest"),
        )


# ── built-in pen libraries ──────────────────────────────────────────────────────

PEN_LIBRARIES: dict[str, list[dict]] = {
    "Sakura Pigma Micron": [
        {"name": "Black", "colour": "#000000"},
        {"name": "Blue", "colour": "#1f3a93"},
        {"name": "Red", "colour": "#c0392b"},
        {"name": "Green", "colour": "#1e824c"},
        {"name": "Brown", "colour": "#6b4423"},
        {"name": "Sepia", "colour": "#704214"},
    ],
    "Staedtler Fineliner": [
        {"name": "Black", "colour": "#1a1a1a"},
        {"name": "Grey", "colour": "#7f8c8d"},
        {"name": "Blue", "colour": "#2c3e9e"},
        {"name": "Cyan", "colour": "#16a3b8"},
        {"name": "Magenta", "colour": "#b0306d"},
        {"name": "Yellow", "colour": "#e6c200"},
    ],
    "Copic Sketch": [
        {"name": "100 Black", "colour": "#101010"},
        {"name": "B29 Ultramarine", "colour": "#2b4a9b"},
        {"name": "R29 Lipstick Red", "colour": "#b1122c"},
        {"name": "YG07 Acid Green", "colour": "#7ab648"},
        {"name": "E37 Sepia", "colour": "#8a5a2b"},
    ],
    "CMYK": [
        {"name": "Cyan", "colour": "#00aeef"},
        {"name": "Magenta", "colour": "#ec008c"},
        {"name": "Yellow", "colour": "#fff200"},
        {"name": "Key (Black)", "colour": "#000000"},
    ],
}


def library_pens(name: str) -> list[Pen]:
    return [Pen(name=p["name"], type=name, colour=p["colour"]) for p in PEN_LIBRARIES.get(name, [])]


# ── distribution ────────────────────────────────────────────────────────────────

def _ordered_pens(ds: DrawingSet) -> list[Pen]:
    pens = ds.active()
    order = ds.distribution_order
    if order == "darkest":
        return sorted(pens, key=lambda p: colour_luminance(p.colour))
    if order == "lightest":
        return sorted(pens, key=lambda p: -colour_luminance(p.colour))
    if order == "reversed":
        return list(reversed(pens))
    return list(pens)  # displayed


def distribute(items: list[Item], ds: DrawingSet, seed: int = 0) -> list[Layer]:
    """Split generated items among the drawing set's active pens -> layers."""
    pens = _ordered_pens(ds)
    layers = [Layer(pen=p) for p in pens]
    if not items:
        return layers
    n = len(pens)
    if n == 1 or ds.distribution_type == "single":
        for it in items:
            _add(layers[0], it)
        return layers

    weights = [max(0.0, p.weight) for p in pens]
    wsum = sum(weights) or 1.0
    norm = [w / wsum for w in weights]
    dtype = ds.distribution_type

    if dtype == "luminance":
        # Darkest items -> darkest pen. `pens` already in distribution order;
        # for luminance we want explicit dark->light buckets.
        dark_to_light = sorted(range(n), key=lambda i: colour_luminance(pens[i].colour))
        items_sorted = sorted(items, key=lambda it: -it.lum)  # darkest first
        # cumulative weight thresholds
        bounds = []
        acc = 0.0
        for i in dark_to_light:
            acc += norm[i]
            bounds.append(acc)
        k = 0
        for idx, it in enumerate(items_sorted):
            frac = (idx + 1) / len(items_sorted)
            while k < n - 1 and frac > bounds[k]:
                k += 1
            _add(layers[dark_to_light[k]], it)
        return layers

    if dtype in ("random", "random_squiggles"):
        rng = random.Random(seed)
        for it in items:
            r = rng.random()
            acc = 0.0
            chosen = n - 1
            for i in range(n):
                acc += norm[i]
                if r <= acc:
                    chosen = i
                    break
            _add(layers[chosen], it)
        return layers

    # even / preconfigured fallback: contiguous weighted blocks in order
    total = len(items)
    start = 0
    for i in range(n):
        count = total - start if i == n - 1 else int(round(norm[i] * total))
        for it in items[start:start + count]:
            _add(layers[i], it)
        start += count
    return layers


def _add(layer: Layer, item: Item) -> None:
    if item.dot is not None:
        layer.dots.append(item.dot)
    if item.path is not None:
        layer.paths.append(item.path)
