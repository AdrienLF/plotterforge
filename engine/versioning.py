"""Version snapshots.

A Version is an immutable record of every setting that produced a drawing, plus
a rendered thumbnail, rating and notes — DrawingBotV3-style project history.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from PIL import Image, ImageDraw

from .geometry import Drawing
from .pens import hex_to_rgb


@dataclass
class Version:
    id: str
    name: str
    pfm_id: str
    params: dict[str, Any]
    area: dict[str, Any]
    drawing_set: dict[str, Any]
    image_name: str = ""
    rating: int = 0
    notes: str = ""
    timestamp: float = field(default_factory=time.time)
    thumbnail: str = ""          # filename relative to the version dir
    composition_snapshot: str = ""  # optional JSON filename relative to project dir

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "pfm_id": self.pfm_id,
            "params": self.params,
            "area": self.area,
            "drawing_set": self.drawing_set,
            "image_name": self.image_name,
            "rating": self.rating,
            "notes": self.notes,
            "timestamp": self.timestamp,
            "thumbnail": self.thumbnail,
            "composition_snapshot": self.composition_snapshot,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Version":
        known = {k: d[k] for k in cls.__dataclass_fields__ if k in d}
        return cls(**known)


def render_thumbnail(drawing: Drawing, max_px: int = 260) -> Image.Image:
    """Rasterise a Drawing to a small preview image in pen colours."""
    w, h = drawing.width, drawing.height
    scale = max_px / max(w, h)
    tw, th = max(1, int(w * scale)), max(1, int(h * scale))
    bg = getattr(drawing.area, "canvas_colour", "#ffffff")
    im = Image.new("RGB", (tw, th), bg)
    draw = ImageDraw.Draw(im)
    for layer in drawing.layers:
        colour = hex_to_rgb(getattr(layer.pen, "colour", "#000000"))
        for d in layer.dots:
            x, y, r = d.x * scale, d.y * scale, max(0.5, d.r * scale)
            draw.ellipse([x - r, y - r, x + r, y + r], fill=colour)
        for g in layer.paths:
            pts = [(p[0] * scale, p[1] * scale) for p in g.points]
            if g.closed and len(pts) >= 2:
                pts = pts + [pts[0]]
            if len(pts) >= 2:
                draw.line(pts, fill=colour, width=1)
    return im


def render_polyline_thumbnail(polylines, max_px: int = 260) -> Image.Image:
    """Render real-coordinate polylines into a normalized PNG preview."""
    points = [point for polyline in polylines for point in polyline]
    if not points:
        raise ValueError("Cannot render an empty polyline thumbnail")

    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)
    width = max(max_x - min_x, 1.0)
    height = max(max_y - min_y, 1.0)
    margin = min(8, max_px // 4)
    scale = max(1.0, max_px - 2 * margin) / max(width, height)
    image_width = max(1, int(round(width * scale)) + 2 * margin)
    image_height = max(1, int(round(height * scale)) + 2 * margin)
    image = Image.new("RGB", (image_width, image_height), "#ffffff")
    draw = ImageDraw.Draw(image)
    for polyline in polylines:
        if len(polyline) < 2:
            continue
        normalized = [
            (
                margin + (point[0] - min_x) * scale,
                margin + (max_y - point[1]) * scale,
            )
            for point in polyline
        ]
        draw.line(normalized, fill="#000000", width=1)
    return image
