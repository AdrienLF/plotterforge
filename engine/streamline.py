"""Streamline engine.

Evenly-spaced streamlines (Jobard & Lefer) traced through a vector field, with
the separation distance driven by image brightness so dark areas get denser
lines. The field can come from a flow function, the image's edge-tangent flow,
or a superformula.
"""

from __future__ import annotations

import math
from collections import deque

import numpy as np

from .geometry import Geometry, Item
from .image_ops import darkness, luminance, sobel


# ── vector fields (return angle in radians per pixel) ───────────────────────────

def flow_field(shape: tuple[int, int], p: dict) -> np.ndarray:
    h, w = shape
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    sf = float(p.get("scale_freq", 1.0))
    xf = float(p.get("x_freq", 1.0)) * sf * 0.04
    yf = float(p.get("y_freq", 1.0)) * sf * 0.04
    amp = float(p.get("amplitude", 0.5))
    base = math.radians(float(p.get("start_angle", 0.0)))
    return (base + amp * math.pi * (np.sin(xs * xf) + np.cos(ys * yf))).astype(np.float32)


def _smooth_orientation(angle: np.ndarray, iterations: int, ksize: int = 5) -> np.ndarray:
    """Blur an orientation field via its double-angle representation."""
    if iterations <= 0:
        return angle
    a2 = 2 * angle
    cx = np.cos(a2)
    sx = np.sin(a2)
    try:
        import cv2
        for _ in range(iterations):
            cx = cv2.GaussianBlur(cx, (ksize, ksize), 0)
            sx = cv2.GaussianBlur(sx, (ksize, ksize), 0)
    except Exception:
        from scipy.ndimage import gaussian_filter
        for _ in range(iterations):
            cx = gaussian_filter(cx, 1.0)
            sx = gaussian_filter(sx, 1.0)
    return (0.5 * np.arctan2(sx, cx)).astype(np.float32)


def edge_tangent_flow(gray: np.ndarray, p: dict) -> np.ndarray:
    try:
        import cv2
        gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    except Exception:
        from scipy.ndimage import sobel as nd_sobel
        gx = nd_sobel(gray, axis=1).astype(np.float32)
        gy = nd_sobel(gray, axis=0).astype(np.float32)
    tangent = np.arctan2(gy, gx) + math.pi / 2.0
    tangent = _smooth_orientation(tangent, int(p.get("etf_iterations", 4)))
    edge_power = float(p.get("edge_power", 70)) / 100.0
    if edge_power < 1.0:
        flow = flow_field(gray.shape, p)
        # blend orientations via vectors
        a2e, a2f = 2 * tangent, 2 * flow
        cx = edge_power * np.cos(a2e) + (1 - edge_power) * np.cos(a2f)
        sx = edge_power * np.sin(a2e) + (1 - edge_power) * np.sin(a2f)
        tangent = 0.5 * np.arctan2(sx, cx)
    return tangent.astype(np.float32)


def superformula_field(shape: tuple[int, int], p: dict) -> np.ndarray:
    h, w = shape
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    cx = float(p.get("centre_x", 50)) / 100.0 * w
    cy = float(p.get("centre_y", 50)) / 100.0 * h
    phi = np.arctan2(ys - cy, xs - cx)
    m = float(p.get("frequency", 6.0))
    base = math.radians(float(p.get("start_angle", 0.0)))
    # tangent to a superformula rosette: concentric direction warped by sin(m*phi)
    return (phi + math.pi / 2.0 + base + 0.6 * np.sin(m * phi)).astype(np.float32)


# ── evenly-spaced streamline placement ──────────────────────────────────────────

def place_streamlines(angle: np.ndarray, dark: np.ndarray, p: dict, seed: int) -> list[Item]:
    h, w = angle.shape
    rng = np.random.default_rng(seed)

    min_sp = max(0.5, float(p["min_spacing"]))
    max_sp = max(min_sp + 0.1, float(p["max_spacing"]))
    tone = float(p["tone"])
    bright = np.clip(1.0 - dark, 0.0, 1.0)
    spacing = np.clip(min_sp + (max_sp - min_sp) * np.power(bright, 1.0 + tone / 50.0), min_sp, max_sp)

    min_len = float(p["min_length"])
    max_len = float(p["max_length"])
    distortion = float(p["distortion"]) / 100.0
    step = max(0.75, min_sp * 0.4)

    # Boolean occupancy grid at ~half the min spacing — O(1) proximity tests
    # regardless of how densely streamlines pack (edge fields can pile up).
    g = max(0.5, min_sp * 0.5)
    gw = int(w / g) + 2
    gh = int(h / g) + 2
    occ = np.zeros((gh, gw), dtype=bool)

    def add_pt(x, y):
        occ[int(y / g), int(x / g)] = True

    def local(arr, x, y):
        return float(arr[min(max(int(y), 0), h - 1), min(max(int(x), 0), w - 1)])

    def too_close(x, y, dtest):
        r = int(dtest / g) + 1
        cj, ci = int(y / g), int(x / g)
        return bool(occ[max(0, cj - r):cj + r + 1, max(0, ci - r):ci + r + 1].any())

    def integrate(sx, sy, sign):
        x, y = sx, sy
        a0 = local(angle, x, y)
        hx, hy = math.cos(a0) * sign, math.sin(a0) * sign
        pts = []
        steps = int(max_len / step) + 1
        for _ in range(steps):
            a = local(angle, x, y)
            if distortion > 0:
                a += rng.normal(0, distortion * 0.6)
            vx, vy = math.cos(a), math.sin(a)
            if vx * hx + vy * hy < 0:      # keep heading coherent (orientation field)
                vx, vy = -vx, -vy
            nx, ny = x + vx * step, y + vy * step
            if nx < 0 or nx >= w or ny < 0 or ny >= h:
                break
            if too_close(nx, ny, local(spacing, nx, ny) * 0.5):
                break
            x, y, hx, hy = nx, ny, vx, vy
            pts.append((x, y))
        return pts

    # Seed from the darkest point first, then a jittered grid so every field
    # gets full coverage even when perpendicular propagation stalls (curved /
    # convergent fields). The occupancy test still enforces even spacing.
    sy, sx = np.unravel_index(int(np.argmax(dark)), dark.shape)
    queue: deque[tuple[float, float]] = deque([(float(sx), float(sy))])
    gstep = max(min_sp, max_sp * 0.7)
    gys, gxs = np.mgrid[gstep / 2:h:gstep, gstep / 2:w:gstep]
    grid_seeds = np.stack([gxs.ravel(), gys.ravel()], axis=1)
    grid_seeds += rng.uniform(-gstep * 0.3, gstep * 0.3, grid_seeds.shape)
    rng.shuffle(grid_seeds)
    for gx_, gy_ in grid_seeds:
        queue.append((float(gx_), float(gy_)))
    items: list[Item] = []
    total_pts = 0
    MAX_PTS = 250_000
    MAX_LINES = 6000

    while queue and total_pts < MAX_PTS and len(items) < MAX_LINES:
        seed_x, seed_y = queue.popleft()
        if too_close(seed_x, seed_y, local(spacing, seed_x, seed_y) * 0.5):
            continue
        fwd = integrate(seed_x, seed_y, +1)
        bwd = integrate(seed_x, seed_y, -1)
        line = list(reversed(bwd)) + [(seed_x, seed_y)] + fwd
        if len(line) < 2:
            continue
        length = sum(
            math.hypot(line[i + 1][0] - line[i][0], line[i + 1][1] - line[i][1])
            for i in range(len(line) - 1)
        )
        if length < min_len:
            continue
        for x, y in line:
            add_pt(x, y)
        total_pts += len(line)
        d_here = local(dark, seed_x, seed_y)
        items.append(Item(lum=d_here, path=Geometry(line)))

        # spawn new seeds perpendicular to the line
        for i in range(0, len(line) - 1, 3):
            x0, y0 = line[i]
            x1, y1 = line[i + 1]
            dx, dy = x1 - x0, y1 - y0
            n = math.hypot(dx, dy) or 1.0
            px, py = -dy / n, dx / n
            sp = local(spacing, x0, y0)
            for s in (sp, -sp):
                cxp, cyp = x0 + px * s, y0 + py * s
                if 0 <= cxp < w and 0 <= cyp < h and not too_close(cxp, cyp, sp * 0.5):
                    queue.append((cxp, cyp))

    return items


def run_streamlines(work_img, p: dict, seed: int, field_kind: str) -> list[Item]:
    gray, alpha = luminance(work_img)
    dark = darkness(gray, alpha)
    if field_kind == "edge":
        angle = edge_tangent_flow(gray, p)
    elif field_kind == "superformula":
        angle = superformula_field(gray.shape, p)
    else:
        angle = flow_field(gray.shape, p)
    return place_streamlines(angle, dark, p, seed)
