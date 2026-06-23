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
