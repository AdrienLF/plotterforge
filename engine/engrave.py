"""Engraving renderer: tone by line density, direction from a mixable
orientation field (edge-tangent flow + noise + radial + constant, or a bound
field), with optional crosshatch tonal bands. The copperplate look: dense
flowing lines that follow form, crossed in the shadows."""

from __future__ import annotations

import math

import numpy as np

from . import fields, noise
from .image_ops import darkness, luminance
from .streamline import edge_tangent_flow, place_streamlines

MAX_TOTAL_PTS = 500_000
_BAND_THRESHOLDS = [0.0, 0.55, 0.8]


def _direction_field(gray, v, seed):
    h, w = gray.shape
    comps = []
    ew = float(v.get("edge_weight", 1.0))
    if ew > 0:
        etf = edge_tangent_flow(gray, {"etf_iterations": int(v.get("etf_iterations", 4)),
                                       "edge_power": 100})
        comps.append((etf, ew))
    nw = float(v.get("noise_weight", 0.0))
    if nw > 0:
        px = max(2.0, float(v.get("noise_scale", 25.0)) / 100.0 * min(h, w))
        comps.append(((noise.fbm((h, w), scale=px, octaves=3, seed=seed) * math.pi)
                      .astype(np.float32), nw))
    rw = float(v.get("radial_weight", 0.0))
    if rw > 0:
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        cx = float(v.get("centre_x", 50)) / 100.0 * w
        cy = float(v.get("centre_y", 50)) / 100.0 * h
        comps.append(((np.arctan2(ys - cy, xs - cx) + math.pi / 2).astype(np.float32), rw))
    if not comps:
        ang = np.zeros((h, w), dtype=np.float32)
    else:
        # double-angle vector blend, same convention as edge_tangent_flow
        cxs = sum(wgt * np.cos(2 * a) for a, wgt in comps)
        sxs = sum(wgt * np.sin(2 * a) for a, wgt in comps)
        ang = (0.5 * np.arctan2(sxs, cxs)).astype(np.float32)
    return ang + math.radians(float(v.get("base_angle", 0.0)))


def run_engraving(work, v, seed, bounds):
    gray, alpha = luminance(work)
    dark = darkness(gray, alpha)
    binding = (v.get("field_bindings") or {}).get("direction")
    ctx = v.get("_field_ctx")
    if binding and ctx is not None:
        angle = fields.resolve_orientation(binding, ctx)
    else:
        angle = _direction_field(gray, v, seed)
    bands = max(1, min(3, int(v.get("bands", 1))))
    cross = math.radians(float(v.get("cross_angle", 60.0)))
    items = []
    total = 0
    for k in range(bands):
        t = _BAND_THRESHOLDS[k]
        # Zeroed darkness pushes spacing to max there, so band k > 0 only
        # fills zones darker than its threshold; a fresh occupancy grid per
        # place_streamlines call lets crosshatch lines actually cross.
        dk = dark if k == 0 else np.where(dark >= t, dark, 0.0).astype(np.float32)
        band_items = place_streamlines((angle + k * cross).astype(np.float32),
                                       dk, v, seed + k * 31)
        for it in band_items:
            total += len(it.path.points)
            if total > MAX_TOTAL_PTS:
                return items
            items.append(it)
    return items
