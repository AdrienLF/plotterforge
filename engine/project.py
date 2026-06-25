"""Project model + on-disk workspace.

A project bundles the source image, the current Drawing Area, Drawing Set, the
selected PFM + params, and an ordered list of saved Versions. Everything lives
under ``~/.plotter_studio/projects/<id>/``.
"""

from __future__ import annotations

import json
import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from PIL import Image

from .composition import Composition
from .canvas import DrawingArea
from .geometry import Drawing
from .pens import DrawingSet
from .versioning import Version, render_thumbnail

WORKSPACE = Path.home() / ".plotter_studio"
PROJECTS_DIR = WORKSPACE / "projects"


class Project:
    def __init__(self, pid: str):
        self.id = pid
        self.dir = PROJECTS_DIR / pid
        self.name = "Untitled"
        self.image_name = ""
        self.area = DrawingArea()
        self.drawing_set = DrawingSet()
        self.composition = Composition()
        self.pfm_id = "voronoi_stippling"
        self.params: dict[str, Any] = {}
        self.versions: list[Version] = []

    # ── paths ────────────────────────────────────────────────────────────────
    @property
    def versions_dir(self) -> Path:
        return self.dir / "versions"

    @property
    def layers_dir(self) -> Path:
        return self.dir / "layers"

    @property
    def image_path(self) -> Path | None:
        return self.dir / self.image_name if self.image_name else None

    # ── persistence ──────────────────────────────────────────────────────────
    def ensure_dirs(self) -> None:
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        self.layers_dir.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "image_name": self.image_name,
            "area": self.area.to_dict(),
            "drawing_set": self.drawing_set.to_dict(),
            "composition": self.composition.to_dict(),
            "pfm_id": self.pfm_id,
            "params": self.params,
            "versions": [v.to_dict() for v in self.versions],
        }

    def save(self) -> None:
        self.ensure_dirs()
        (self.dir / "project.json").write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def load(cls, pid: str) -> "Project":
        p = cls(pid)
        f = p.dir / "project.json"
        if f.exists():
            d = json.loads(f.read_text())
            p.name = d.get("name", "Untitled")
            p.image_name = d.get("image_name", "")
            p.area = DrawingArea.from_dict(d.get("area"))
            p.drawing_set = DrawingSet.from_dict(d.get("drawing_set"))
            p.composition = Composition.from_dict(d.get("composition"))
            for layer in p.composition.layers:
                layer_path = p.dir / layer.svg_path if layer.svg_path else None
                if layer_path and layer_path.exists():
                    layer.svg = layer_path.read_text()
            p.pfm_id = d.get("pfm_id", "voronoi_stippling")
            p.params = d.get("params", {})
            p.versions = [Version.from_dict(v) for v in d.get("versions", [])]
        return p

    def save_composition_layers(self) -> None:
        self.ensure_dirs()
        active_ids = {layer.id for layer in self.composition.layers}
        for layer in self.composition.layers:
            if not layer.svg_path:
                layer.svg_path = f"layers/{layer.id}.svg"
            (self.dir / layer.svg_path).write_text(layer.svg)
        for path in self.layers_dir.glob("*.svg"):
            if path.stem not in active_ids:
                path.unlink()
        self.save()

    # ── source image ─────────────────────────────────────────────────────────
    def set_image(self, data: bytes, filename: str) -> None:
        self.ensure_dirs()
        suffix = Path(filename).suffix.lower() or ".png"
        self.image_name = f"source{suffix}"
        (self.dir / self.image_name).write_bytes(data)
        self.save()

    def open_image(self) -> Image.Image | None:
        ip = self.image_path
        if ip and ip.exists():
            return Image.open(ip)
        return None

    # ── versions ─────────────────────────────────────────────────────────────
    def add_version(self, drawing: Drawing, name: str = "", notes: str = "") -> Version:
        self.ensure_dirs()
        vid = uuid.uuid4().hex[:8]
        vdir = self.versions_dir / vid
        vdir.mkdir(parents=True, exist_ok=True)
        thumb = render_thumbnail(drawing)
        thumb.save(vdir / "thumb.png")
        v = Version(
            id=vid,
            name=name or self.pfm_id.replace("_", " ").title(),
            pfm_id=self.pfm_id,
            params=dict(self.params),
            area=self.area.to_dict(),
            drawing_set=self.drawing_set.to_dict(),
            image_name=self.image_name,
            notes=notes,
            thumbnail=f"versions/{vid}/thumb.png",
        )
        self.versions.insert(0, v)
        self.save()
        return v

    def get_version(self, vid: str) -> Version | None:
        return next((v for v in self.versions if v.id == vid), None)

    def load_version(self, vid: str) -> bool:
        """Restore a version's settings into the project's current state."""
        v = self.get_version(vid)
        if not v:
            return False
        self.pfm_id = v.pfm_id
        self.params = dict(v.params)
        self.area = DrawingArea.from_dict(v.area)
        self.drawing_set = DrawingSet.from_dict(v.drawing_set)
        self.save()
        return True

    def delete_version(self, vid: str) -> bool:
        v = self.get_version(vid)
        if not v:
            return False
        self.versions = [x for x in self.versions if x.id != vid]
        shutil.rmtree(self.versions_dir / vid, ignore_errors=True)
        self.save()
        return True

    def reorder_version(self, vid: str, direction: int) -> bool:
        ids = [v.id for v in self.versions]
        if vid not in ids:
            return False
        i = ids.index(vid)
        j = i + (1 if direction > 0 else -1)
        if 0 <= j < len(self.versions):
            self.versions[i], self.versions[j] = self.versions[j], self.versions[i]
            self.save()
            return True
        return False

    def clear_versions(self) -> None:
        for v in self.versions:
            shutil.rmtree(self.versions_dir / v.id, ignore_errors=True)
        self.versions = []
        self.save()


def get_or_create(pid: str = "default") -> Project:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    p = Project.load(pid)
    p.ensure_dirs()
    if not (p.dir / "project.json").exists():
        p.save()
    return p
