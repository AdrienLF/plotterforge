"""Sketch engine.

Classic "find the darkest line, draw it, erase it, repeat" path finding. The
working ('lightened') image tracks how much ink is left to place; drawn segments
are subtracted so the same area isn't over-drawn. Squiggles are continuous runs
of segments between pen lifts.

One engine drives the Sketch Lines / Curves / Squares modules; they differ only
in the set of candidate directions and how the squiggle points become geometry.
"""

from __future__ import annotations

import math

import numpy as np
from PIL import Image

from .geometry import Geometry, Item
from .image_ops import darkness, luminance


def _catmull_rom(points: list[tuple[float, float]], tension: float, seg: int = 8) -> list[tuple[float, float]]:
    if len(points) < 3:
        return points
    p = [points[0]] + points + [points[-1]]
    alpha = max(0.01, min(1.0, tension))
    out: list[tuple[float, float]] = [points[0]]
    for i in range(1, len(p) - 2):
        p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
        for s in range(1, seg + 1):
            t = s / seg
            t2 = t * t
            t3 = t2 * t
            # Cardinal spline with tension acting as stiffness
            m = (1.0 - alpha)
            x = 0.5 * (
                (2 * p1[0])
                + (-m * p0[0] + m * p2[0]) * t
                + (2 * m * p0[0] + (m - 3) * p1[0] + (3 - 2 * m) * p2[0] - m * p3[0]) * t2
                + (-m * p0[0] + (2 - m) * p1[0] + (m - 2) * p2[0] + m * p3[0]) * t3
            )
            y = 0.5 * (
                (2 * p1[1])
                + (-m * p0[1] + m * p2[1]) * t
                + (2 * m * p0[1] + (m - 3) * p1[1] + (3 - 2 * m) * p2[1] - m * p3[1]) * t2
                + (-m * p0[1] + (2 - m) * p1[1] + (m - 2) * p2[1] + m * p3[1]) * t3
            )
            out.append((x, y))
    return out


def run_sketch(work_img: Image.Image, v: dict, seed: int, mode: str) -> list[Item]:
    gray, alpha = luminance(work_img)
    D0 = darkness(gray, alpha).astype(np.float64)

    res = float(v.get("plotting_resolution", 0.5))
    scale_back = 1.0
    if abs(res - 1.0) > 1e-3:
        hh = max(8, int(D0.shape[0] * res))
        ww = max(8, int(D0.shape[1] * res))
        D0 = (
            np.asarray(Image.fromarray((D0 * 255).astype("uint8")).resize((ww, hh)))
            .astype(np.float64)
            / 255.0
        )
        scale_back = 1.0 / res

    H, W = D0.shape
    work = D0.copy()
    total0 = float(work.sum()) or 1.0
    stop_removed = total0 * float(v["line_density"]) / 100.0

    rng = np.random.default_rng(seed)
    seg_len = float(v["line_max_length"])
    min_len = float(v["line_min_length"])
    nsamp = max(2, int(seg_len / 2))
    t_samples = np.linspace(min_len * 0.5 + 1.0, seg_len, nsamp)
    angle_tests = int(v["angle_tests"])
    delta = float(v["drawing_delta_angle"])
    dir_weight = float(v["directionality"]) / 100.0 * 0.5
    erase_val = max(1.0, float(v["erase_max"])) / 255.0
    sq_min = int(v["squiggle_min_length"])
    sq_max = max(1, int(v["squiggle_max_length"]))
    deviation = max(1.0, float(v["squiggle_max_deviation"])) / 100.0
    limit = int(v["line_max_limit"])
    start_angle = math.radians(float(v.get("start_angle", 0.0)))
    tension = float(v.get("curve_tension", 0.5))

    items: list[Item] = []
    removed = 0.0
    segments = 0
    safety = 0
    SAFETY_MAX = 80_000

    while removed < stop_removed and (limit < 0 or segments < limit) and safety < SAFETY_MAX:
        safety += 1
        sy, sx = np.unravel_index(int(np.argmax(work)), work.shape)
        start_dark = float(work[sy, sx])
        if start_dark < 0.02:
            break

        # Always erase a small disc at the start so the next argmax advances even
        # if this squiggle fails to extend — prevents re-picking the same pixel.
        y0, y1 = max(0, sy - 1), min(H, sy + 2)
        x0, x1 = max(0, sx - 1), min(W, sx + 2)
        before = work[y0:y1, x0:x1].copy()
        work[y0:y1, x0:x1] = np.maximum(0.0, work[y0:y1, x0:x1] - erase_val)
        removed += float((before - work[y0:y1, x0:x1]).sum())

        cur = np.array([float(sx), float(sy)])
        squiggle = [(cur[0], cur[1])]
        last_dir: float | None = None

        for seg_i in range(sq_max):
            if mode == "squares":
                angles = start_angle + np.array([0, math.pi / 2, math.pi, 3 * math.pi / 2])
            elif last_dir is None or delta >= 360:
                angles = np.linspace(0, 2 * math.pi, max(3, angle_tests), endpoint=False)
            else:
                half = math.radians(delta) / 2
                angles = last_dir + np.linspace(-half, half, max(3, angle_tests))

            xs = cur[0] + np.cos(angles)[:, None] * t_samples[None, :]
            ys = cur[1] + np.sin(angles)[:, None] * t_samples[None, :]
            inside = (xs >= 0) & (xs < W) & (ys >= 0) & (ys < H)
            ix = np.clip(xs.astype(int), 0, W - 1)
            iy = np.clip(ys.astype(int), 0, H - 1)
            vals = work[iy, ix] * inside
            score = vals.mean(axis=1)
            if last_dir is not None and dir_weight > 0:
                score = score + dir_weight * np.cos(angles - last_dir)

            bi = int(np.argmax(score))
            best_dark = float(vals[bi].mean())
            if best_dark < 0.02:
                break
            # Allow ending the squiggle only after the first accepted segment and
            # once past the minimum length.
            if seg_i > 0 and seg_i >= sq_min and best_dark < start_dark * (1.0 - deviation):
                break

            ang = float(angles[bi])
            end = cur + np.array([math.cos(ang), math.sin(ang)]) * seg_len
            end[0] = min(max(end[0], 0), W - 1)
            end[1] = min(max(end[1], 0), H - 1)

            # erase along the chosen segment
            ex = ix[bi]
            ey = iy[bi]
            seg_before = work[ey, ex].copy()
            work[ey, ex] = np.maximum(0.0, work[ey, ex] - erase_val)
            removed += float((seg_before - work[ey, ex]).sum())

            squiggle.append((end[0], end[1]))
            last_dir = ang
            cur = end
            segments += 1

        if len(squiggle) >= 2:
            pts = squiggle
            if mode == "curves":
                pts = _catmull_rom(pts, tension)
            if scale_back != 1.0:
                pts = [(x * scale_back, y * scale_back) for x, y in pts]
            # luminance for pen distribution: darkness at the squiggle start
            items.append(Item(lum=start_dark, path=Geometry(pts)))

    return items
