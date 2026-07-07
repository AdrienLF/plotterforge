"""Spatial parameter fields.

A field binding lets a numeric PFM param vary across the page: image-derived
maps (luminance / gradient magnitude / edge distance), Perlin fBm noise,
radial / linear gradients, or a hand-painted grayscale mask, combined by
weighted average (scalar) or double-angle vector blend (orientation).
Bindings ride in ``params["field_bindings"]`` (a sidecar dict, like the
shape-field generator's ``shape_layers`` — ``validate()`` strips it and the
server re-attaches the normalized copy). Resolution happens against a
``FieldContext`` built from the prepared working raster; styles consume
per-point ``(N,)`` arrays via :func:`per_point`.
"""

from __future__ import annotations

import math

import numpy as np

from . import image_ops, noise

LAYER_TYPES = ("luminance", "gradient_mag", "edge_distance",
               "noise", "radial", "linear", "paint")

_LAYER_DEFAULTS = {
    "noise": {"scale": 25.0, "octaves": 3, "seed": 0},
    "radial": {"cx": 50.0, "cy": 50.0, "inner": 0.0, "outer": 100.0},
    "linear": {"angle": 0.0},
    "paint": {"paint_id": ""},
}


def normalize_binding(raw, param):
    """Validate one raw binding dict against its Param; None when unusable."""
    if not isinstance(raw, dict):
        return None
    kind = "orientation" if (raw.get("kind") == "orientation"
                             or param.type == "angle") else "scalar"
    layers = []
    for lr in (raw.get("layers") or []):
        if not isinstance(lr, dict) or lr.get("type") not in LAYER_TYPES:
            continue
        try:
            weight = float(lr.get("weight", 0.0) or 0.0)
        except (TypeError, ValueError):
            weight = 0.0
        out = {"type": lr["type"], "weight": max(0.0, min(4.0, weight))}
        for k, dv in _LAYER_DEFAULTS.get(lr["type"], {}).items():
            v = lr.get(k, dv)
            try:
                out[k] = str(v) if k == "paint_id" else float(v)
            except (TypeError, ValueError):
                out[k] = dv
        if lr["type"] == "noise":
            out["octaves"] = int(max(1, min(6, out["octaves"])))
            out["seed"] = int(out["seed"])
        layers.append(out)
    if not any(lr["weight"] > 0 for lr in layers):
        return None
    lo = param.min if param.min is not None else 0.0
    hi = param.max if param.max is not None else 1.0

    def _num(key, fallback):
        try:
            return float(raw.get(key, fallback))
        except (TypeError, ValueError):
            return float(fallback)

    return {
        "kind": kind,
        "out_min": _num("out_min", lo),
        "out_max": _num("out_max", hi),
        "invert": bool(raw.get("invert", False)),
        "gamma": max(0.1, min(8.0, _num("gamma", 1.0) or 1.0)),
        "layers": layers,
    }


def normalize_bindings(raw, params):
    """Normalize a {param_name: binding} sidecar; unknown/non-bindable dropped."""
    if not isinstance(raw, dict):
        return {}
    by_name = {p.name: p for p in params if getattr(p, "bindable", False)}
    out = {}
    for name, b in raw.items():
        p = by_name.get(name)
        if p is None:
            continue
        nb = normalize_binding(b, p)
        if nb:
            out[name] = nb
    return out


class FieldContext:
    """Lazy per-generation raster cache. All rasters are float32 (h, w)."""

    def __init__(self, work_img, seed=0, paint_loader=None):
        gray, alpha = image_ops.luminance(work_img)
        self.gray, self.alpha = gray, alpha
        self.shape = gray.shape
        self.seed = int(seed)
        self._paint_loader = paint_loader
        self._cache = {}

    def _memo(self, key, fn):
        if key not in self._cache:
            self._cache[key] = fn()
        return self._cache[key]

    # ── scalar sources, all in [0, 1] ────────────────────────────────────────
    def scalar_of(self, layer):
        t = layer["type"]
        h, w = self.shape
        if t == "luminance":
            return self._memo("lum", lambda: 1.0 - self.gray)   # dark = high
        if t == "gradient_mag":
            return self._memo("grad", lambda: image_ops.sobel(self.gray))
        if t == "edge_distance":
            return self._memo("edist", self._edge_distance)
        if t == "noise":
            key = ("noise", layer["scale"], layer["octaves"], layer["seed"])
            px = max(2.0, layer["scale"] / 100.0 * min(h, w))
            return self._memo(key, lambda: noise.fbm(
                self.shape, scale=px, octaves=int(layer["octaves"]),
                seed=self.seed + int(layer["seed"])))
        if t == "radial":
            key = ("radial", layer["cx"], layer["cy"], layer["inner"], layer["outer"])
            return self._memo(key, lambda: self._radial(layer))
        if t == "linear":
            return self._memo(("linear", layer["angle"]),
                              lambda: self._linear(layer["angle"]))
        if t == "paint":
            return self._memo(("paint", layer["paint_id"]),
                              lambda: self._paint(layer["paint_id"]))
        return np.full(self.shape, 0.5, dtype=np.float32)

    # ── orientation sources, angle rasters in radians ────────────────────────
    def orientation_of(self, layer):
        t = layer["type"]
        h, w = self.shape
        if t == "gradient_mag":     # actual edge tangents, not magnitude
            return self._memo("etf", self._edge_tangent)
        if t in ("luminance", "edge_distance", "noise", "paint"):
            return (self.scalar_of(layer) * math.pi).astype(np.float32)
        if t == "radial":
            ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
            cx = layer["cx"] / 100.0 * w
            cy = layer["cy"] / 100.0 * h
            return (np.arctan2(ys - cy, xs - cx) + math.pi / 2.0).astype(np.float32)
        if t == "linear":
            return np.full(self.shape, math.radians(layer["angle"]), dtype=np.float32)
        return np.zeros(self.shape, dtype=np.float32)

    def _edge_tangent(self):
        from .streamline import edge_tangent_flow
        return edge_tangent_flow(self.gray, {"etf_iterations": 4, "edge_power": 100})

    def _edge_distance(self):
        edges = image_ops.canny(self.gray)
        try:
            import cv2
            dist = cv2.distanceTransform(
                ((1.0 - edges) * 255).astype(np.uint8), cv2.DIST_L2, 3)
        except Exception:
            from scipy.ndimage import distance_transform_edt
            dist = distance_transform_edt(edges < 0.5).astype(np.float32)
        m = float(dist.max())
        if m <= 0:
            return np.zeros(self.shape, dtype=np.float32)
        return (dist / m).astype(np.float32)

    def _radial(self, layer):
        h, w = self.shape
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        cx = layer["cx"] / 100.0 * w
        cy = layer["cy"] / 100.0 * h
        rr = np.hypot(xs - cx, ys - cy) / (0.5 * math.hypot(w, h))
        lo = layer["inner"] / 100.0
        hi = max(layer["outer"], layer["inner"] + 1.0) / 100.0
        return np.clip((rr - lo) / (hi - lo), 0.0, 1.0).astype(np.float32)

    def _linear(self, angle_deg):
        h, w = self.shape
        ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
        a = math.radians(float(angle_deg))
        t = xs * math.cos(a) + ys * math.sin(a)
        t -= t.min()
        m = float(t.max())
        if m <= 0:
            return np.zeros(self.shape, dtype=np.float32)
        return (t / m).astype(np.float32)

    def _paint(self, paint_id):
        img = self._paint_loader(paint_id) if self._paint_loader else None
        if img is None:
            return np.full(self.shape, 0.5, dtype=np.float32)
        h, w = self.shape
        img = img.convert("L").resize((w, h))
        return np.asarray(img, dtype=np.float32) / 255.0


def resolve_scalar(binding, ctx):
    """Resolve a scalar binding to an (h, w) raster in [out_min, out_max]."""
    total = np.zeros(ctx.shape, dtype=np.float32)
    wsum = 0.0
    for layer in binding["layers"]:
        wgt = float(layer["weight"])
        if wgt <= 0:
            continue
        total += wgt * ctx.scalar_of(layer)
        wsum += wgt
    val = total / wsum if wsum > 0 else np.full(ctx.shape, 0.5, dtype=np.float32)
    if binding.get("invert"):
        val = 1.0 - val
    g = float(binding.get("gamma", 1.0))
    if g != 1.0:
        val = np.power(np.clip(val, 0.0, 1.0), g)
    lo, hi = float(binding["out_min"]), float(binding["out_max"])
    return (lo + (hi - lo) * np.clip(val, 0.0, 1.0)).astype(np.float32)


def resolve_orientation(binding, ctx):
    """Resolve an orientation binding to an (h, w) angle raster in radians
    via the double-angle vector blend (matches engine.streamline)."""
    cx = np.zeros(ctx.shape, dtype=np.float32)
    sx = np.zeros(ctx.shape, dtype=np.float32)
    for layer in binding["layers"]:
        wgt = float(layer["weight"])
        if wgt <= 0:
            continue
        a2 = 2.0 * ctx.orientation_of(layer)
        cx += wgt * np.cos(a2)
        sx += wgt * np.sin(a2)
    return (0.5 * np.arctan2(sx, cx)).astype(np.float32)


def per_point(vals, name, sites, default):
    """Per-point values for a possibly-bound param.

    Returns (N,) float32 in the param's native units (degrees for angle
    params). Falls back to a constant array when the param is unbound or no
    FieldContext is attached to ``vals``.
    """
    n = len(sites)
    b = (vals.get("field_bindings") or {}).get(name)
    ctx = vals.get("_field_ctx")
    if not b or ctx is None:
        try:
            const = float(vals.get(name, default))
        except (TypeError, ValueError):
            const = float(default)
        return np.full(n, const, dtype=np.float32)
    if b.get("kind") == "orientation":
        raster = np.degrees(resolve_orientation(b, ctx)).astype(np.float32)
    else:
        raster = resolve_scalar(b, ctx)
    if n == 0:
        return np.zeros(0, dtype=np.float32)
    pts = np.asarray(sites, dtype=np.float32)
    h, w = ctx.shape
    ix = np.clip(pts[:, 0].astype(np.int64), 0, w - 1)
    iy = np.clip(pts[:, 1].astype(np.int64), 0, h - 1)
    return raster[iy, ix]
