"""Render deterministic picker previews for PFMs added after the main gallery.

The source images are synthetic so the previews stay reproducible and make the
algorithm's characteristic structure legible at the 440 x 621 picker size.

Run from the repository root:
    .venv/bin/python tools/render_feature_previews.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine.canvas import DrawingArea  # noqa: E402
from engine.pens import DrawingSet  # noqa: E402
from engine.pfm import REGISTRY  # noqa: E402


SIZE = (440, 621)
OUT = ROOT / "web" / "static" / "pfm-previews"

PREVIEW_PARAMS = {
    "quadtree_mosaic": {
        "max_depth": 6,
        "min_cell_px": 18,
        "detail": 82,
        "padding": 7,
        "style_dark": "voronoi_stippling",
        "style_light": "hatch",
        "draw_outlines": True,
    },
    "differential_growth": {
        "seed_count": 8,
        "iterations": 700,
        "min_dist": 2.2,
        "max_dist": 4.5,
        "repulsion_radius": 13,
        "k_align": 0.4,
        "k_rep": 0.9,
        "k_dark": 0.2,
        "jitter": 0.45,
    },
}


def source_image(pfm_id: str) -> Image.Image:
    """Return a fixed tonal field that reveals the selected PFM's behavior."""
    width, height = SIZE
    y, x = np.mgrid[0:height, 0:width]
    xn = x / (width - 1)
    yn = y / (height - 1)

    if pfm_id == "quadtree_mosaic":
        field = 0.94 - 0.24 * yn
        field -= 0.62 * np.exp(-(((xn - 0.28) / 0.22) ** 2 + ((yn - 0.31) / 0.18) ** 2))
        field -= 0.44 * np.exp(-(((xn - 0.72) / 0.25) ** 2 + ((yn - 0.70) / 0.26) ** 2))
        detail = ((x // 9 + y // 9) % 2) * 0.20
        detail_mask = np.exp(-(((xn - 0.63) / 0.34) ** 2 + ((yn - 0.37) / 0.22) ** 2))
        field -= detail * detail_mask
    else:
        field = np.full((height, width), 0.97)
        for cx, cy, rx, ry, strength in (
            (0.30, 0.25, 0.23, 0.19, 0.86),
            (0.67, 0.47, 0.29, 0.25, 0.72),
            (0.35, 0.76, 0.27, 0.23, 0.78),
        ):
            field -= strength * np.exp(-(((xn - cx) / rx) ** 2 + ((yn - cy) / ry) ** 2))
        field -= 0.10 * (np.sin(xn * 22 + yn * 9) + 1) / 2

    return Image.fromarray((np.clip(field, 0, 1) * 255).astype(np.uint8), "L")


def rasterize(drawing) -> Image.Image:
    """Rasterize engine geometry without requiring an SVG renderer."""
    canvas = Image.new("RGB", SIZE, "white")
    draw = ImageDraw.Draw(canvas)
    sx = SIZE[0] / drawing.width
    sy = SIZE[1] / drawing.height
    for layer in drawing.layers:
        for dot in layer.dots:
            x, y = dot.x * sx, dot.y * sy
            radius = max(0.5, dot.r * (sx + sy) / 2)
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill="black")
        for geometry in layer.paths:
            points = [(x * sx, y * sy) for x, y in geometry.points]
            if geometry.closed and points:
                points.append(points[0])
            if len(points) >= 2:
                draw.line(points, fill="black", width=1)
    return canvas


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    area = DrawingArea(
        use_original_sizing=True,
        units="px",
        width=SIZE[0],
        height=SIZE[1],
        scaling_mode="stretch",
    )
    for pfm_id, params in PREVIEW_PARAMS.items():
        drawing = REGISTRY[pfm_id].run(
            source_image(pfm_id), area, DrawingSet(), params, seed=7
        )
        output = OUT / f"{pfm_id}.png"
        rasterize(drawing).save(output)
        print(f"wrote {output.relative_to(ROOT)} ({drawing.total()} items)")


if __name__ == "__main__":
    main()
