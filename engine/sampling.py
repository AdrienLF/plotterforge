"""Point samplers.

Each sampler turns a working raster into a set of weighted points
``(positions Nx2, weights N)`` in working-pixel coordinates. These are the
GPU-heavy stages; the nearest-site assignment + weighted-centroid relaxation run
through :mod:`engine.accel`, which uses Torch (MPS/CUDA) when available.

The same point set is consumed by every style (stippling, TSP, triangulation,
...), so three samplers x seven styles yields the whole first wave.
"""

from __future__ import annotations

import numpy as np
from PIL import Image

from . import accel
from .image_ops import apply_brightness_contrast, darkness, luminance


def _density_map(img: Image.Image, brightness: float = 1.0, contrast: float = 1.0,
                 ignore_white: bool = True) -> np.ndarray:
    gray, alpha = luminance(img)
    gray = apply_brightness_contrast(gray, brightness, contrast)
    d = darkness(gray, alpha)
    if ignore_white:
        d = np.where(d < 0.02, 0.0, d)
    return d.astype(np.float32)


def _dark_pixels(d: np.ndarray, stride: int = 1):
    """Return (positions Nx2 float32 [x,y], weights N) for non-zero density."""
    if stride > 1:
        d = d[::stride, ::stride]
        ys, xs = np.nonzero(d)
        xs = xs * stride
        ys = ys * stride
        w = d[ys // stride, xs // stride]
    else:
        ys, xs = np.nonzero(d)
        w = d[ys, xs]
    pts = np.stack([xs, ys], axis=1).astype(np.float32)
    return pts, w.astype(np.float32)


# ── Weighted Voronoi (Secord 2002) ──────────────────────────────────────────────

class WeightedVoronoiSampler:
    @staticmethod
    def run(img: Image.Image, p: dict, seed: int = 0):
        rng = np.random.default_rng(seed)
        d = _density_map(img, ignore_white=p.get("ignore_white", True))
        h, w = d.shape
        area = w * h

        n = int(p.get("point_density", 500) * area / 50000.0)
        limit = int(p.get("point_limit", 0))
        if limit > 0:
            n = min(n, limit)
        n = max(8, n)

        pts, wt = _dark_pixels(d)
        if pts.shape[0] == 0:
            return np.zeros((0, 2), np.float32), np.zeros((0,), np.float32)
        n = min(n, pts.shape[0])

        lum_power = float(p.get("luminance_power", 5))
        dens_power = float(p.get("density_power", 5))

        # initial sites ~ darkness^luminance_power
        prob = np.power(wt, lum_power)
        prob = prob / prob.sum()
        sites = pts[rng.choice(pts.shape[0], size=n, replace=False, p=prob)].astype(np.float32)

        # relaxation sample weights ~ darkness^density_power
        cw = np.power(wt, dens_power)

        accuracy = float(p.get("voronoi_accuracy", 100))
        stride = max(1, int(round((100 - accuracy) / 12)) + 1)
        spts, sw = _dark_pixels(d, stride=stride)
        scw = np.power(sw, dens_power)

        iters = int(p.get("voronoi_iterations", 8))
        for _ in range(max(1, iters)):
            labels = accel.assign_nearest(spts, sites)
            cent, mass = accel.weighted_centroids(spts, scw, labels, n)
            empty = mass <= 1e-9
            if empty.any():
                resample = rng.choice(pts.shape[0], size=int(empty.sum()), p=prob)
                cent[empty] = pts[resample]
            sites = cent.astype(np.float32)

        # final per-site weight = local density at the site
        ix = np.clip(sites[:, 0].astype(int), 0, w - 1)
        iy = np.clip(sites[:, 1].astype(int), 0, h - 1)
        weights = d[iy, ix]
        return sites, weights


# ── Adaptive (even, tone-mapped distribution) ───────────────────────────────────

class AdaptiveSampler:
    @staticmethod
    def run(img: Image.Image, p: dict, seed: int = 0):
        rng = np.random.default_rng(seed)
        d = _density_map(
            img,
            brightness=p.get("brightness", 1.0),
            contrast=p.get("contrast", 1.0),
            ignore_white=p.get("ignore_white", True),
        )
        h, w = d.shape
        min_r = max(0.5, float(p.get("min_sample_radius", 1.0)))
        max_r = max(min_r + 0.1, float(p.get("max_sample_radius", 6.0)))

        # Local spacing shrinks in dark areas. Thin a min-spacing grid by the
        # square of (min_r / local_spacing) so dark regions keep more points.
        spacing = max_r - (max_r - min_r) * d
        gy, gx = np.mgrid[0:h:min_r, 0:w:min_r]
        gy = gy.ravel().astype(int)
        gx = gx.ravel().astype(int)
        gy = np.clip(gy + rng.integers(0, max(1, int(min_r)), gy.shape), 0, h - 1)
        gx = np.clip(gx + rng.integers(0, max(1, int(min_r)), gx.shape), 0, w - 1)
        local = spacing[gy, gx]
        accept_prob = np.clip((min_r / np.maximum(local, 1e-3)) ** 2, 0.0, 1.0)
        accept = (rng.random(gx.shape) < accept_prob) & (d[gy, gx] > 0.02)
        sites = np.stack([gx[accept], gy[accept]], axis=1).astype(np.float32)
        weights = d[gy[accept], gx[accept]].astype(np.float32)
        return sites, weights


# ── LBG (Linde–Buzo–Gray adaptive split/merge) ──────────────────────────────────

class LBGSampler:
    @staticmethod
    def run(img: Image.Image, p: dict, seed: int = 0):
        rng = np.random.default_rng(seed)
        d = _density_map(img, ignore_white=True)
        h, w = d.shape
        min_r = max(0.5, float(p.get("stipple_radius_min", 1.0)))
        max_r = max(min_r + 0.1, float(p.get("stipple_radius_max", 8.0)))
        density = float(p.get("density", 50)) / 100.0
        threshold = float(p.get("threshold", 0)) / 100.0

        pts, wt = _dark_pixels(d)
        if pts.shape[0] == 0:
            return np.zeros((0, 2), np.float32), np.zeros((0,), np.float32)

        # seed sites on a coarse grid sized by the mean radius
        mean_r = (min_r + max_r) / 2.0
        gy, gx = np.mgrid[mean_r / 2:h:mean_r, mean_r / 2:w:mean_r]
        sites = np.stack([gx.ravel(), gy.ravel()], axis=1).astype(np.float32)

        # target mass per cell: dark cells (high density) should split sooner
        target_hi = float(np.pi * (min_r ** 2) * (0.4 + density))
        target_lo = float(np.pi * (max_r ** 2) * 0.08)

        max_iter = int(p.get("max_iterations", 20))
        for _ in range(max(1, max_iter)):
            if sites.shape[0] == 0:
                break
            labels = accel.assign_nearest(pts, sites)
            cent, mass = accel.weighted_centroids(pts, wt, labels, sites.shape[0])
            keep = mass > target_lo
            survivors = cent[keep]
            survivor_mass = mass[keep]
            # split heavy cells
            heavy = survivor_mass > target_hi
            new_sites = [survivors]
            if heavy.any():
                jitter = rng.normal(0, min_r, size=(int(heavy.sum()), 2)).astype(np.float32)
                new_sites.append(survivors[heavy] + jitter)
            sites = np.clip(np.concatenate(new_sites, axis=0), [0, 0], [w - 1, h - 1]).astype(np.float32)
            if sites.shape[0] == 0:
                break

        if sites.shape[0] == 0:
            return np.zeros((0, 2), np.float32), np.zeros((0,), np.float32)
        ix = np.clip(sites[:, 0].astype(int), 0, w - 1)
        iy = np.clip(sites[:, 1].astype(int), 0, h - 1)
        weights = d[iy, ix]
        if threshold > 0:
            mask = weights >= threshold
            sites, weights = sites[mask], weights[mask]
        return sites, weights


SAMPLERS = {
    "voronoi": WeightedVoronoiSampler,
    "adaptive": AdaptiveSampler,
    "lbg": LBGSampler,
}
