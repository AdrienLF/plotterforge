# Composition Layers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a layer-based A3 composition workflow where Path Finding, Generate, SVG import, export, and plotting all operate on visible composition layers.

**Architecture:** Add a focused backend composition module that owns layer metadata, SVG persistence, SVG normalization, composition, and split export packaging. Then replace `web.server`'s single `_current_svg`/`_placement` plotting path with composition helpers while keeping legacy globals as compatibility shims during migration. Update the Svelte store, API, viewport, workflow tabs, Generate/Path Finding panels, toolbar, and a new Composition panel to select, replace, move, hide, rename, reorder, duplicate, delete, preview, export, estimate, and plot layers.

**Tech Stack:** Python 3.14, Flask, `xml.etree.ElementTree`, `zipfile`, existing `unittest` backend tests, Svelte 5 runes, TypeScript, Vite, existing plain TypeScript helper tests.

---

## File Structure

- Create `engine/composition.py`: dataclasses and pure helpers for fixed A3 composition, SVG size parsing, SVG body extraction, layer persistence, composition SVG generation, split layer zip generation, and JSON serialization.
- Modify `engine/project.py`: add composition persistence to `Project`, create layer storage paths, and include composition in `project.json`.
- Create `tests/test_composition.py`: pure backend tests for layer bounds, A3 composed SVG, hidden-layer exclusion, split export bounds, manifest metadata, and selected-layer replacement.
- Modify `web/server.py`: expose composition API routes, convert upload/process/generate into selected-layer replacement, use composed SVG for export/estimate/plot, and keep `_current_svg` updated from composition for compatibility.
- Modify `frontend/src/lib/types.ts`: add composition and layer interfaces.
- Modify `frontend/src/lib/state.svelte.ts`: replace single-layer placement state with composition state and selected-layer derived behavior.
- Modify `frontend/src/lib/api.ts`: boot composition, add layer CRUD/placement APIs, update upload/process/generate/export/plot calls.
- Modify `frontend/src/lib/placement.ts` and `frontend/src/lib/placement.test.ts`: keep A3 constants and add selected-layer clamp helpers where needed.
- Modify `frontend/src/components/StepTabs.svelte`: add the Composition workflow step.
- Modify `frontend/src/components/Viewport.svelte`: render fixed A3 composition with all visible layers; drag selected layer in Composition step.
- Modify `frontend/src/components/Toolbar.svelte`: make alignment/readout apply to the selected layer.
- Modify `frontend/src/components/panels/GeneratePanel.svelte`: add selected-layer control and make generation target the active layer.
- Modify `frontend/src/components/panels/PathFindingPanel.svelte`: add selected-layer control and make processing target the active layer.
- Create `frontend/src/components/panels/CompositionPanel.svelte`: Photoshop-like layer list with visibility, selection, rename, duplicate, delete, reorder, and numeric x/y fields.
- Modify `frontend/src/App.svelte`: wire the new step and panel.

---

### Task 1: Backend Composition Model

**Files:**
- Create: `engine/composition.py`
- Modify: `engine/project.py`
- Test: `tests/test_composition.py`

- [ ] **Step 1: Write failing composition tests**

Add `tests/test_composition.py`:

```python
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from engine.composition import (
    A3_PAGE,
    Composition,
    CompositionLayer,
    compose_visible_svg,
    layer_svg_zip,
    parse_svg_size_mm,
    replace_selected_layer,
)


LAYER_A = """<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 210 297">
  <path d="M0 0 L10 0"/>
</svg>"""

LAYER_B = """<svg xmlns="http://www.w3.org/2000/svg" width="120mm" height="80mm" viewBox="0 0 120 80">
  <path d="M5 5 L20 5"/>
</svg>"""


class CompositionTest(unittest.TestCase):
    def test_parse_svg_size_mm_reads_cm_mm_and_viewbox_fallback(self):
        self.assertEqual(parse_svg_size_mm('<svg width="21cm" height="297mm"></svg>'), (210.0, 297.0))
        self.assertEqual(parse_svg_size_mm('<svg viewBox="0 0 120 80"></svg>'), (120.0, 80.0))

    def test_replace_selected_layer_creates_a4_layer_at_a3_top_left(self):
        comp = Composition()

        layer = replace_selected_layer(comp, LAYER_A, name="A4 generator", kind="generate", source={"id": "spokes"})

        self.assertEqual(comp.page, A3_PAGE)
        self.assertEqual(comp.selected_layer_id, layer.id)
        self.assertEqual(layer.x, 0.0)
        self.assertEqual(layer.y, 0.0)
        self.assertEqual(layer.width, 210.0)
        self.assertEqual(layer.height, 297.0)
        self.assertEqual(layer.kind, "generate")

    def test_replace_selected_layer_updates_only_selected_layer(self):
        comp = Composition()
        first = replace_selected_layer(comp, LAYER_A, name="First", kind="generate", source={"id": "a"})
        second = comp.add_layer(LAYER_B, name="Second", kind="svg", source={"id": "b"})
        comp.selected_layer_id = first.id

        updated = replace_selected_layer(comp, LAYER_B, name="Updated", kind="pathfinding", source={"id": "pfm"})

        self.assertEqual(updated.id, first.id)
        self.assertEqual(comp.layers[0].name, "Updated")
        self.assertEqual(comp.layers[0].kind, "pathfinding")
        self.assertEqual(comp.layers[0].width, 120.0)
        self.assertEqual(comp.layers[1].id, second.id)
        self.assertEqual(comp.layers[1].name, "Second")

    def test_compose_visible_svg_is_a3_and_excludes_hidden_layers(self):
        comp = Composition()
        a = comp.add_layer(LAYER_A, name="A", kind="generate", source={})
        b = comp.add_layer(LAYER_B, name="B", kind="svg", source={})
        a.x = 12.5
        a.y = 7.0
        b.visible = False

        svg = compose_visible_svg(comp)

        self.assertIn('width="297mm"', svg)
        self.assertIn('height="420mm"', svg)
        self.assertIn('viewBox="0 0 297 420"', svg)
        self.assertIn('data-layer-id="' + a.id + '"', svg)
        self.assertIn('transform="translate(12.5 7)"', svg)
        self.assertNotIn('data-layer-id="' + b.id + '"', svg)

    def test_layer_zip_exports_each_visible_layer_at_own_bounds_with_manifest(self):
        comp = Composition()
        a = comp.add_layer(LAYER_A, name="A4 Layer", kind="generate", source={})
        b = comp.add_layer(LAYER_B, name="Small Layer", kind="svg", source={})
        a.x = 10
        a.y = 20
        b.visible = False

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "layers.zip"
            path.write_bytes(layer_svg_zip(comp))
            with zipfile.ZipFile(path) as zf:
                names = zf.namelist()
                self.assertIn("manifest.json", names)
                self.assertEqual([n for n in names if n.endswith(".svg")], ["00_A4_Layer.svg"])
                layer_svg = zf.read("00_A4_Layer.svg").decode()
                manifest = json.loads(zf.read("manifest.json").decode())

        self.assertIn('width="210mm"', layer_svg)
        self.assertIn('height="297mm"', layer_svg)
        self.assertEqual(manifest["page"], A3_PAGE)
        self.assertEqual(manifest["layers"][0]["x"], 10)
        self.assertEqual(manifest["layers"][0]["y"], 20)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run python -m unittest tests.test_composition
```

Expected: FAIL with `ModuleNotFoundError: No module named 'engine.composition'`.

- [ ] **Step 3: Implement composition module**

Create `engine/composition.py`:

```python
from __future__ import annotations

import io
import json
import re
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

A3_PAGE = {"width": 297.0, "height": 420.0, "units": "mm"}
_SVG_NS = "http://www.w3.org/2000/svg"
_UNIT_MM = {"mm": 1.0, "cm": 10.0, "in": 25.4, "px": 25.4 / 96.0, "pt": 25.4 / 72.0, "pc": 25.4 / 6.0}


def _fmt(value: float) -> str:
    return f"{float(value):.4f}".rstrip("0").rstrip(".")


def _parse_length(value: str | None, fallback: float) -> float:
    if not value:
        return fallback
    raw = str(value).strip()
    match = re.match(r"^([-+]?[0-9]*\.?[0-9]+)\s*([a-zA-Z]*)$", raw)
    if not match:
        return fallback
    number = float(match.group(1))
    unit = (match.group(2) or "px").lower()
    return round(number * _UNIT_MM.get(unit, _UNIT_MM["px"]), 4)


def _root(svg: str) -> ET.Element:
    return ET.fromstring(svg.encode("utf-8"))


def parse_svg_size_mm(svg: str) -> tuple[float, float]:
    root = _root(svg)
    view_box = root.attrib.get("viewBox") or root.attrib.get("viewbox")
    vb_w = vb_h = 0.0
    if view_box:
        parts = [float(p) for p in re.split(r"[\s,]+", view_box.strip()) if p]
        if len(parts) == 4:
            vb_w, vb_h = parts[2], parts[3]
    width = _parse_length(root.attrib.get("width"), vb_w or A3_PAGE["width"])
    height = _parse_length(root.attrib.get("height"), vb_h or A3_PAGE["height"])
    return width, height


def _inner_svg(svg: str) -> str:
    root = _root(svg)
    view_box = root.attrib.get("viewBox") or root.attrib.get("viewbox")
    translate = ""
    if view_box:
        parts = [float(p) for p in re.split(r"[\s,]+", view_box.strip()) if p]
        if len(parts) == 4 and (parts[0] or parts[1]):
            translate = f'<g transform="translate({_fmt(-parts[0])} {_fmt(-parts[1])})">'
    body = "".join(ET.tostring(child, encoding="unicode") for child in list(root))
    return f"{translate}{body}</g>" if translate else body


def _svg_document(width: float, height: float, body: str) -> str:
    return (
        f'<svg xmlns="{_SVG_NS}" width="{_fmt(width)}mm" height="{_fmt(height)}mm" '
        f'viewBox="0 0 {_fmt(width)} {_fmt(height)}">\n{body}\n</svg>'
    )


@dataclass
class CompositionLayer:
    id: str
    name: str
    kind: str
    visible: bool = True
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0
    svg: str = ""
    svg_path: str = ""
    source: dict = field(default_factory=dict)

    def to_dict(self, include_svg: bool = False) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "kind": self.kind,
            "visible": self.visible,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "svg_path": self.svg_path,
            "source": self.source,
        }
        if include_svg:
            data["svg"] = self.svg
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "CompositionLayer":
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex),
            name=str(data.get("name") or "Layer"),
            kind=str(data.get("kind") or "svg"),
            visible=bool(data.get("visible", True)),
            x=float(data.get("x", 0) or 0),
            y=float(data.get("y", 0) or 0),
            width=float(data.get("width", 0) or 0),
            height=float(data.get("height", 0) or 0),
            svg=str(data.get("svg") or ""),
            svg_path=str(data.get("svg_path") or ""),
            source=dict(data.get("source") or {}),
        )


@dataclass
class Composition:
    page: dict = field(default_factory=lambda: dict(A3_PAGE))
    selected_layer_id: str | None = None
    layers: list[CompositionLayer] = field(default_factory=list)

    def selected_layer(self) -> CompositionLayer | None:
        return next((layer for layer in self.layers if layer.id == self.selected_layer_id), None)

    def add_layer(self, svg: str, name: str, kind: str, source: dict) -> CompositionLayer:
        width, height = parse_svg_size_mm(svg)
        layer = CompositionLayer(
            id=uuid.uuid4().hex[:10],
            name=name,
            kind=kind,
            width=width,
            height=height,
            svg=svg,
            source=dict(source or {}),
        )
        self.layers.append(layer)
        self.selected_layer_id = layer.id
        return layer

    def to_dict(self, include_svg: bool = False) -> dict:
        return {
            "page": self.page,
            "selected_layer_id": self.selected_layer_id,
            "layers": [layer.to_dict(include_svg=include_svg) for layer in self.layers],
        }

    @classmethod
    def from_dict(cls, data: dict | None) -> "Composition":
        data = data or {}
        comp = cls(
            page=dict(data.get("page") or A3_PAGE),
            selected_layer_id=data.get("selected_layer_id"),
            layers=[CompositionLayer.from_dict(item) for item in data.get("layers", [])],
        )
        if comp.layers and not comp.selected_layer():
            comp.selected_layer_id = comp.layers[-1].id
        return comp


def replace_selected_layer(comp: Composition, svg: str, name: str, kind: str, source: dict) -> CompositionLayer:
    layer = comp.selected_layer()
    width, height = parse_svg_size_mm(svg)
    if layer is None:
        return comp.add_layer(svg, name=name, kind=kind, source=source)
    layer.name = name
    layer.kind = kind
    layer.width = width
    layer.height = height
    layer.svg = svg
    layer.source = dict(source or {})
    return layer


def compose_visible_svg(comp: Composition) -> str:
    body = []
    for layer in comp.layers:
        if not layer.visible:
            continue
        body.append(
            f'<g data-layer-id="{layer.id}" data-layer-name="{layer.name}" '
            f'transform="translate({_fmt(layer.x)} {_fmt(layer.y)})">{_inner_svg(layer.svg)}</g>'
        )
    return _svg_document(comp.page["width"], comp.page["height"], "\n".join(body))


def layer_bound_svg(layer: CompositionLayer) -> str:
    return _svg_document(layer.width, layer.height, _inner_svg(layer.svg))


def safe_name(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
    return cleaned or "Layer"


def layer_svg_zip(comp: Composition) -> bytes:
    manifest = {"page": comp.page, "layers": []}
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        visible = [layer for layer in comp.layers if layer.visible]
        for index, layer in enumerate(visible):
            filename = f"{index:02d}_{safe_name(layer.name)}.svg"
            zf.writestr(filename, layer_bound_svg(layer))
            manifest["layers"].append({**layer.to_dict(include_svg=False), "filename": filename, "order": index})
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
    return buf.getvalue()
```

- [ ] **Step 4: Wire project persistence**

Modify `engine/project.py`:

```python
from .composition import Composition
```

Add to `Project.__init__`:

```python
self.composition = Composition()
```

Add path helper:

```python
@property
def layers_dir(self) -> Path:
    return self.dir / "layers"
```

Update `ensure_dirs`:

```python
self.layers_dir.mkdir(parents=True, exist_ok=True)
```

Add `"composition": self.composition.to_dict()` to `to_dict()`.

Update `load()` after drawing set:

```python
p.composition = Composition.from_dict(d.get("composition"))
for layer in p.composition.layers:
    if layer.svg_path and (p.dir / layer.svg_path).exists():
        layer.svg = (p.dir / layer.svg_path).read_text()
```

Add method:

```python
def save_composition_layers(self) -> None:
    self.ensure_dirs()
    for layer in self.composition.layers:
        if not layer.svg_path:
            layer.svg_path = f"layers/{layer.id}.svg"
        (self.dir / layer.svg_path).write_text(layer.svg)
    self.save()
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
uv run python -m unittest tests.test_composition
```

Expected: PASS.

- [ ] **Step 6: Commit backend model**

```bash
git add engine/composition.py engine/project.py tests/test_composition.py
git commit -m "Add composition layer model"
```

---

### Task 2: Backend Routes, Export, Estimate, and Plot

**Files:**
- Modify: `web/server.py`
- Test: `tests/test_composition.py`
- Test: `tests/test_plot_estimate.py`
- Test: `tests/test_plot_job.py`

- [ ] **Step 1: Write failing route/export tests**

Append to `tests/test_composition.py`:

```python
import io
import web.server as server


class CompositionApiTest(unittest.TestCase):
    def setUp(self):
        self.old_project = server._project
        self.old_svg = server._current_svg
        self.old_placement = server._placement
        class TempProject:
            def __init__(self):
                self.composition = Composition()
                self.drawing_set = server.DrawingSet()
                self.area = server.DrawingArea()
                self.pfm_id = "voronoi_stippling"
                self.params = {}
            def save_composition_layers(self): pass
            def save(self): pass
        server._project = TempProject()
        server._current_svg = None
        server._placement = {"x": 0.0, "y": 0.0}
        self.client = server.app.test_client()

    def tearDown(self):
        server._project = self.old_project
        server._current_svg = self.old_svg
        server._placement = self.old_placement

    def test_upload_svg_creates_composition_layer(self):
        response = self.client.post(
            "/api/upload",
            data={"file": (io.BytesIO(LAYER_A.encode()), "art.svg")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(len(payload["composition"]["layers"]), 1)
        self.assertEqual(payload["composition"]["layers"][0]["width"], 210.0)
        self.assertIn('width="297mm"', payload["svg"])

    def test_layer_visibility_controls_export(self):
        a = server._project.composition.add_layer(LAYER_A, "A", "svg", {})
        b = server._project.composition.add_layer(LAYER_B, "B", "svg", {})
        b.visible = False

        response = self.client.get("/api/export")

        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn(a.id, body)
        self.assertNotIn(b.id, body)

    def test_split_export_uses_layer_bounds(self):
        server._project.composition.add_layer(LAYER_A, "A4 Layer", "svg", {})

        response = self.client.get("/api/export?split=1")

        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.data)) as zf:
            layer_svg = zf.read("00_A4_Layer.svg").decode()
        self.assertIn('width="210mm"', layer_svg)
        self.assertNotIn('width="297mm"', layer_svg)
```

- [ ] **Step 2: Run route/export tests to verify failure**

Run:

```bash
uv run python -m unittest tests.test_composition
```

Expected: FAIL because `/api/upload` does not return composition and `/api/export` does not compose layers.

- [ ] **Step 3: Add server composition helpers**

Modify imports in `web/server.py`:

```python
from engine.composition import compose_visible_svg, layer_svg_zip, replace_selected_layer
```

Add helpers near global state:

```python
def _composition():
    return _project.composition

def _composition_has_visible_layers():
    return any(layer.visible for layer in _composition().layers)

def _composed_svg_bytes():
    if not _composition_has_visible_layers():
        return None
    return compose_visible_svg(_composition()).encode()

def _sync_current_svg_from_composition():
    global _current_svg, _placement
    _current_svg = _composed_svg_bytes()
    _placement = {"x": 0.0, "y": 0.0}
    return _current_svg

def _replace_selected_composition_layer(svg, name, kind, source):
    layer = replace_selected_layer(_composition(), svg, name=name, kind=kind, source=source)
    _project.save_composition_layers()
    _sync_current_svg_from_composition()
    return layer

def _composition_payload():
    return _composition().to_dict(include_svg=True)
```

- [ ] **Step 4: Update upload/process/generate to replace selected layer**

In `/api/upload`, replace direct `_current_svg` assignment with:

```python
svg = f.read().decode("utf-8", "replace")
_replace_selected_composition_layer(svg, f.filename, "svg", {"filename": f.filename})
return jsonify(svg=_current_svg.decode("utf-8", "replace"), name=f.filename, composition=_composition_payload())
```

In `_process_worker`, after `svg = svg_io.to_svg(drawing)`, replace `_current_svg = svg.encode()` with:

```python
_replace_selected_composition_layer(
    svg,
    p.name,
    "pathfinding",
    {"pfm_id": pfm_id, "params": validate(pfm.params, params), "area": _project.area.to_dict(), "drawing_set": _project.drawing_set.to_dict()},
)
```

In `_generate_worker`, after `svg = svg_io.lines_to_svg(...)`, replace `_current_svg = svg.encode()` with:

```python
_replace_selected_composition_layer(
    svg,
    gen["name"],
    "generate",
    {"generator_id": gid, "params": vals},
)
```

- [ ] **Step 5: Add composition API routes**

Add routes before `/api/settings`:

```python
@app.route("/api/composition")
def api_composition():
    _sync_current_svg_from_composition()
    return jsonify(composition=_composition_payload(), svg=_current_svg.decode("utf-8", "replace") if _current_svg else None)

@app.route("/api/composition/layers/<layer_id>", methods=["PATCH"])
def api_composition_layer(layer_id):
    data = request.json or {}
    layer = next((l for l in _composition().layers if l.id == layer_id), None)
    if not layer:
        return jsonify(error="Unknown layer"), 404
    for key in ("name", "visible", "x", "y"):
        if key in data:
            setattr(layer, key, data[key])
    if "selected" in data and data["selected"]:
        _composition().selected_layer_id = layer.id
    _project.save_composition_layers()
    _sync_current_svg_from_composition()
    return jsonify(ok=True, composition=_composition_payload(), svg=_current_svg.decode("utf-8", "replace") if _current_svg else None)
```

- [ ] **Step 6: Update estimate, plot, and export**

In `/api/plot/estimate`, call `_sync_current_svg_from_composition()` first, error with `"No visible layers"` when it returns `None`, then pass placement `{"x": 0.0, "y": 0.0}`.

In `/api/plot`, call `_sync_current_svg_from_composition()` first, error with `"No visible layers"` when it returns `None`, and create plot job with placement `{"x": 0.0, "y": 0.0}`.

In `/api/export`, replace legacy branches with:

```python
if not _composition_has_visible_layers():
    return jsonify(error="Nothing to export"), 400
if request.args.get("split") == "1":
    return send_file(io.BytesIO(layer_svg_zip(_composition())), mimetype="application/zip", as_attachment=True, download_name="plot_layers.zip")
svg = compose_visible_svg(_composition())
return send_file(io.BytesIO(svg.encode()), mimetype="image/svg+xml", as_attachment=True, download_name="plot.svg")
```

- [ ] **Step 7: Run backend tests**

Run:

```bash
uv run python -m unittest tests.test_composition tests.test_plot_estimate tests.test_plot_job
```

Expected: PASS after updating existing estimate tests to seed a one-layer composition instead of only `_current_svg`.

- [ ] **Step 8: Commit backend route changes**

```bash
git add web/server.py tests/test_composition.py tests/test_plot_estimate.py tests/test_plot_job.py
git commit -m "Use composition layers for export and plot"
```

---

### Task 3: Frontend State and API

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Modify: `frontend/src/lib/state.svelte.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add types**

Add to `frontend/src/lib/types.ts`:

```ts
export interface CompositionLayerT {
  id: string;
  name: string;
  kind: "generate" | "pathfinding" | "svg";
  visible: boolean;
  x: number;
  y: number;
  width: number;
  height: number;
  svg: string;
  svg_path?: string;
  source: Record<string, any>;
}

export interface CompositionT {
  page: { width: number; height: number; units: "mm" };
  selected_layer_id: string | null;
  layers: CompositionLayerT[];
}
```

- [ ] **Step 2: Add store fields and selected-layer helper**

Modify `frontend/src/lib/state.svelte.ts`:

```ts
import type { CompositionLayerT, CompositionT, ... } from "./types";
```

Add fields:

```ts
composition = $state<CompositionT>({ page: { width: 297, height: 420, units: "mm" }, selected_layer_id: null, layers: [] });
step = $state<"pathfinding" | "generate" | "composition" | "plot">("pathfinding");
selectedLayer = $derived<CompositionLayerT | null>(
  this.composition.layers.find((layer) => layer.id === this.composition.selected_layer_id) ?? this.composition.layers.at(-1) ?? null,
);
```

Keep `previewSvg` as the composed preview string for compatibility.

- [ ] **Step 3: Update API boot and composition methods**

In `frontend/src/lib/api.ts`, add `jget("/api/composition")` to `boot()` and assign:

```ts
studio.composition = composition.composition;
studio.previewSvg = composition.svg;
```

Add methods:

```ts
applyComposition(payload: any) {
  if (payload.composition) studio.composition = payload.composition;
  if ("svg" in payload) studio.previewSvg = payload.svg;
},

async refreshComposition() {
  const j = await jget("/api/composition");
  this.applyComposition(j);
  return j;
},

async patchLayer(id: string, data: Record<string, any>) {
  const j = await jpost(`/api/composition/layers/${id}`, data, "PATCH");
  this.applyComposition(j);
  await this.refreshEstimate(true);
},

async selectLayer(id: string) {
  await this.patchLayer(id, { selected: true });
},
```

Update `uploadSvg()`, process completion in `handleProc()`, and generate completion to call `api.refreshComposition()` or consume `m.composition` when backend emits it.

- [ ] **Step 4: Run frontend check**

Run:

```bash
cd frontend && npm run check
```

Expected: PASS after components are updated in later tasks. At this step it may fail because UI references still use old step types; record the failures and continue to Task 4.

- [ ] **Step 5: Commit state/API changes after UI tasks pass**

Do not commit this task alone if `npm run check` fails. Commit with Task 4 once the app compiles.

---

### Task 4: Frontend Workflow, Viewport, Toolbar, and Panels

**Files:**
- Modify: `frontend/src/components/StepTabs.svelte`
- Modify: `frontend/src/components/Viewport.svelte`
- Modify: `frontend/src/components/Toolbar.svelte`
- Modify: `frontend/src/components/panels/GeneratePanel.svelte`
- Modify: `frontend/src/components/panels/PathFindingPanel.svelte`
- Create: `frontend/src/components/panels/CompositionPanel.svelte`
- Modify: `frontend/src/App.svelte`

- [ ] **Step 1: Add Composition step**

In `StepTabs.svelte`, change the Step type and list:

```ts
type Step = "pathfinding" | "generate" | "composition" | "plot";

const steps: { id: Step; label: string }[] = [
  { id: "pathfinding", label: "Path Finding" },
  { id: "generate", label: "Generate" },
  { id: "composition", label: "Composition" },
  { id: "plot", label: "Plot" },
];
```

Make the same Step type change in `App.svelte`.

- [ ] **Step 2: Update Viewport to render composition layers**

In `Viewport.svelte`, replace `drawingSize` with selected layer size:

```ts
const page = $derived({ w: 297, h: 420, bg: areaPage.bg, canvas: "#fff" });
const selectedLayer = $derived(studio.selectedLayer);
const drawingSize = $derived.by(() => selectedLayer ? { w: selectedLayer.width, h: selectedLayer.height } : { w: page.w, h: page.h });
```

Render visible layers:

```svelte
{#if studio.composition.layers.length}
  <div class="guide a4" style:width={`${a4Guide.w * PX_PER_MM}px`} style:height={`${a4Guide.h * PX_PER_MM}px`}>
    <div class="mid-v"></div>
    <div class="mid-h"></div>
  </div>
  {#each studio.composition.layers.filter((layer) => layer.visible) as layer (layer.id)}
    <div
      class="art"
      class:selected={layer.id === studio.composition.selected_layer_id}
      style:left={`${layer.x * PX_PER_MM}px`}
      style:top={`${layer.y * PX_PER_MM}px`}
      style:width={`${layer.width * PX_PER_MM}px`}
      style:height={`${layer.height * PX_PER_MM}px`}
      onpointerdown={(e) => startPlacement(e, layer.id)}
      role="application"
      aria-label={`Layer ${layer.name}`}
    >
      <div class="svgwrap">{@html layer.svg}</div>
    </div>
  {/each}
{/if}
```

Change placement logic to update the selected layer through `api.patchLayer(layerId, { x, y })` on pointer up, while using local store updates during drag.

- [ ] **Step 3: Update Toolbar alignment**

In `Toolbar.svelte`, replace `studio.placement` readout with selected layer:

```svelte
{#if studio.selectedLayer}
  <span class="ctx">Layer Placement</span>
  ...
  <span class="readout">X {studio.selectedLayer.x.toFixed(1)} &nbsp; Y {studio.selectedLayer.y.toFixed(1)} <em>mm</em></span>
{:else}
  <span class="ctx muted">No layer selected</span>
{/if}
```

In `App.svelte`, update `align(mode)` to call the viewport's selected-layer align implementation.

- [ ] **Step 4: Add layer selector to Generate and Path Finding panels**

At the top of `GeneratePanel.svelte` and `PathFindingPanel.svelte`, add:

```svelte
<select value={studio.composition.selected_layer_id ?? ""} onchange={(e) => api.selectLayer((e.target as HTMLSelectElement).value)}>
  {#each studio.composition.layers as layer (layer.id)}
    <option value={layer.id}>{layer.name}</option>
  {/each}
</select>
```

If no layers exist, show a disabled option `"New layer will be created"`.

- [ ] **Step 5: Create CompositionPanel**

Create `frontend/src/components/panels/CompositionPanel.svelte`:

```svelte
<script lang="ts">
  import { api } from "../../lib/api";
  import { studio } from "../../lib/state.svelte";

  async function setVisible(id: string, visible: boolean) {
    await api.patchLayer(id, { visible });
  }

  async function rename(id: string, name: string) {
    await api.patchLayer(id, { name });
  }

  async function moveSelected(axis: "x" | "y", value: number) {
    const layer = studio.selectedLayer;
    if (!layer) return;
    await api.patchLayer(layer.id, { [axis]: value });
  }
</script>

<div class="layers">
  {#each [...studio.composition.layers].reverse() as layer (layer.id)}
    <div class:active={layer.id === studio.composition.selected_layer_id} class="layer">
      <input type="checkbox" checked={layer.visible} onchange={(e) => setVisible(layer.id, (e.target as HTMLInputElement).checked)} />
      <button onclick={() => api.selectLayer(layer.id)}>{layer.name}</button>
      <input value={layer.name} onchange={(e) => rename(layer.id, (e.target as HTMLInputElement).value)} />
    </div>
  {/each}
</div>

{#if studio.selectedLayer}
  <div class="grid2">
    <label>X <input type="number" step="0.1" value={studio.selectedLayer.x} onchange={(e) => moveSelected("x", Number((e.target as HTMLInputElement).value))} /></label>
    <label>Y <input type="number" step="0.1" value={studio.selectedLayer.y} onchange={(e) => moveSelected("y", Number((e.target as HTMLInputElement).value))} /></label>
  </div>
{/if}
```

Then add compact CSS for `.layers`, `.layer`, `.active`, and `.grid2` using existing panel colors.

- [ ] **Step 6: Wire Composition panel into App**

In `App.svelte`, import `CompositionPanel` and add:

```svelte
{:else if studio.step === "composition"}
  <Panel title="Layers"><CompositionPanel /></Panel>
  <Panel title="Drawing Area" open={false}><DrawingAreaPanel /></Panel>
  <Panel title="Pens" open={false}><PensPanel /></Panel>
  <Panel title="Versions" open={false}><VersionsPanel /></Panel>
{:else}
```

- [ ] **Step 7: Run frontend check**

Run:

```bash
cd frontend && npm run check
```

Expected: PASS.

- [ ] **Step 8: Commit frontend composition UI**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/state.svelte.ts frontend/src/lib/api.ts frontend/src/components/StepTabs.svelte frontend/src/components/Viewport.svelte frontend/src/components/Toolbar.svelte frontend/src/components/panels/GeneratePanel.svelte frontend/src/components/panels/PathFindingPanel.svelte frontend/src/components/panels/CompositionPanel.svelte frontend/src/App.svelte
git commit -m "Add composition layer UI"
```

---

### Task 5: Layer Management Actions

**Files:**
- Modify: `engine/composition.py`
- Modify: `web/server.py`
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/components/panels/CompositionPanel.svelte`
- Test: `tests/test_composition.py`

- [ ] **Step 1: Write failing tests for duplicate, delete, and reorder**

Add backend tests asserting:

```python
comp = Composition()
a = comp.add_layer(LAYER_A, "A", "svg", {})
b = comp.add_layer(LAYER_B, "B", "svg", {})
comp.move_layer(b.id, -1)
self.assertEqual([layer.id for layer in comp.layers], [b.id, a.id])
copy = comp.duplicate_layer(b.id)
self.assertEqual(copy.name, "B copy")
comp.delete_layer(b.id)
self.assertNotIn(b.id, [layer.id for layer in comp.layers])
self.assertEqual(comp.selected_layer_id, copy.id)
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
uv run python -m unittest tests.test_composition
```

Expected: FAIL because `move_layer`, `duplicate_layer`, and `delete_layer` do not exist.

- [ ] **Step 3: Implement layer action methods**

Add methods to `Composition`:

```python
def delete_layer(self, layer_id: str) -> bool:
    before = len(self.layers)
    self.layers = [layer for layer in self.layers if layer.id != layer_id]
    if len(self.layers) == before:
        return False
    if self.selected_layer_id == layer_id:
        self.selected_layer_id = self.layers[-1].id if self.layers else None
    return True

def duplicate_layer(self, layer_id: str) -> CompositionLayer | None:
    layer = next((item for item in self.layers if item.id == layer_id), None)
    if layer is None:
        return None
    copy = CompositionLayer.from_dict({**layer.to_dict(include_svg=True), "id": uuid.uuid4().hex[:10], "name": f"{layer.name} copy", "svg_path": ""})
    index = self.layers.index(layer) + 1
    self.layers.insert(index, copy)
    self.selected_layer_id = copy.id
    return copy

def move_layer(self, layer_id: str, direction: int) -> bool:
    ids = [layer.id for layer in self.layers]
    if layer_id not in ids:
        return False
    i = ids.index(layer_id)
    j = i + direction
    if not 0 <= j < len(self.layers):
        return False
    self.layers[i], self.layers[j] = self.layers[j], self.layers[i]
    return True
```

- [ ] **Step 4: Add API routes**

Add to `web/server.py`:

```python
@app.route("/api/composition/layers/<layer_id>/duplicate", methods=["POST"])
def api_duplicate_layer(layer_id):
    layer = _composition().duplicate_layer(layer_id)
    if not layer:
        return jsonify(error="Unknown layer"), 404
    _project.save_composition_layers()
    _sync_current_svg_from_composition()
    return jsonify(ok=True, composition=_composition_payload(), svg=_current_svg.decode("utf-8", "replace") if _current_svg else None)

@app.route("/api/composition/layers/<layer_id>", methods=["DELETE"])
def api_delete_layer(layer_id):
    if not _composition().delete_layer(layer_id):
        return jsonify(error="Unknown layer"), 404
    _project.save_composition_layers()
    _sync_current_svg_from_composition()
    return jsonify(ok=True, composition=_composition_payload(), svg=_current_svg.decode("utf-8", "replace") if _current_svg else None)

@app.route("/api/composition/layers/<layer_id>/move", methods=["POST"])
def api_move_layer(layer_id):
    direction = int((request.json or {}).get("direction", 0))
    if not _composition().move_layer(layer_id, direction):
        return jsonify(error="Cannot move layer"), 400
    _project.save_composition_layers()
    _sync_current_svg_from_composition()
    return jsonify(ok=True, composition=_composition_payload(), svg=_current_svg.decode("utf-8", "replace") if _current_svg else None)
```

- [ ] **Step 5: Add frontend API methods and panel buttons**

Add methods to `api.ts`:

```ts
async duplicateLayer(id: string) {
  const j = await jpost(`/api/composition/layers/${id}/duplicate`);
  this.applyComposition(j);
},
async deleteLayer(id: string) {
  const j = await jpost(`/api/composition/layers/${id}`, undefined, "DELETE");
  this.applyComposition(j);
},
async moveLayer(id: string, direction: number) {
  const j = await jpost(`/api/composition/layers/${id}/move`, { direction });
  this.applyComposition(j);
},
```

Add duplicate, delete, up, and down buttons to `CompositionPanel.svelte`.

- [ ] **Step 6: Run backend and frontend checks**

Run:

```bash
uv run python -m unittest tests.test_composition
cd frontend && npm run check
```

Expected: PASS.

- [ ] **Step 7: Commit layer actions**

```bash
git add engine/composition.py web/server.py tests/test_composition.py frontend/src/lib/api.ts frontend/src/components/panels/CompositionPanel.svelte
git commit -m "Add composition layer actions"
```

---

### Task 6: Final Verification and Build

**Files:**
- Modify only files needed to fix verification failures.

- [ ] **Step 1: Run backend regression tests**

Run:

```bash
uv run python -m unittest discover tests
```

Expected: PASS.

- [ ] **Step 2: Run frontend type check**

Run:

```bash
cd frontend && npm run check
```

Expected: PASS.

- [ ] **Step 3: Build frontend**

Run:

```bash
cd frontend && npm run build
```

Expected: PASS and generated assets in `web/static/app`.

- [ ] **Step 4: Smoke-test export endpoints**

Start the Flask app if needed:

```bash
uv run python -m web.server
```

Use the app to create at least one generated layer, then verify:

```bash
curl -f http://127.0.0.1:5000/api/export -o /tmp/plot.svg
curl -f 'http://127.0.0.1:5000/api/export?split=1' -o /tmp/plot_layers.zip
```

Expected: `/tmp/plot.svg` contains `width="297mm"` and `/tmp/plot_layers.zip` contains `manifest.json` plus one or more bounded layer SVGs.

- [ ] **Step 5: Inspect git diff**

Run:

```bash
git status --short
git diff --stat
```

Expected: only composition-related source, tests, docs, and current built app assets are changed. Existing unrelated dirty files from before this work remain recognizable and are not reverted.

- [ ] **Step 6: Commit final build artifacts if needed**

```bash
git add web/static/app frontend/src web/server.py engine tests docs/superpowers/plans/2026-06-25-composition-layers.md
git commit -m "Build composition layer workflow"
```

Skip this commit if all source changes were already committed and the build artifacts are intentionally left untracked.
