"""Vectorized 2-D Perlin gradient noise + fractal Brownian motion (fBm).

Pure numpy. Rasters are float32 (h, w) in [0, 1]; a few ms at the <=1200 px
working raster.
"""

from __future__ import annotations

import numpy as np


def _fade(t):
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


def _perlin(shape, scale, seed):
    """One octave. ``scale`` = pixels per lattice cell (>= 1)."""
    h, w = shape
    rng = np.random.default_rng(int(seed))
    perm = np.concatenate([rng.permutation(256)] * 2).astype(np.int64)

    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    x = xs / max(1.0, float(scale))
    y = ys / max(1.0, float(scale))
    xi = np.floor(x).astype(np.int64)
    yi = np.floor(y).astype(np.int64)
    xf, yf = x - xi, y - yi
    u, v = _fade(xf), _fade(yf)

    def grad_dot(ix, iy, dx, dy):
        hsh = perm[perm[ix & 255] + (iy & 255)]
        ang = hsh.astype(np.float32) * (2.0 * np.pi / 256.0)
        return np.cos(ang) * dx + np.sin(ang) * dy

    n00 = grad_dot(xi, yi, xf, yf)
    n10 = grad_dot(xi + 1, yi, xf - 1.0, yf)
    n01 = grad_dot(xi, yi + 1, xf, yf - 1.0)
    n11 = grad_dot(xi + 1, yi + 1, xf - 1.0, yf - 1.0)
    nx0 = n00 + u * (n10 - n00)
    nx1 = n01 + u * (n11 - n01)
    return (nx0 + v * (nx1 - nx0)).astype(np.float32)     # roughly [-0.71, 0.71]


def fbm(shape, scale=64.0, octaves=3, lacunarity=2.0, gain=0.5, seed=0):
    """Fractal sum of Perlin octaves, normalized to [0, 1]."""
    total = np.zeros(shape, dtype=np.float32)
    amp, freq, norm = 1.0, 1.0, 0.0
    for o in range(max(1, int(octaves))):
        total += amp * _perlin(shape, scale / freq, seed + o * 101)
        norm += amp
        amp *= gain
        freq *= lacunarity
    return np.clip(0.5 + 0.5 * (total / (norm * 0.75)), 0.0, 1.0).astype(np.float32)
