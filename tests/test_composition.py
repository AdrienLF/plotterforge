import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from engine.composition import (
    A3_PAGE,
    Composition,
    compose_visible_svg,
    layer_svg_zip,
    parse_svg_size_mm,
    replace_selected_layer,
)
import web.server as server


LAYER_A = """<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 210 297">
  <path d="M0 0 L10 0"/>
</svg>"""

LAYER_B = """<svg xmlns="http://www.w3.org/2000/svg" width="120mm" height="80mm" viewBox="0 0 120 80">
  <path d="M5 5 L20 5"/>
</svg>"""


class CompositionTest(unittest.TestCase):
    def test_parse_svg_size_mm_reads_cm_mm_and_viewbox_fallback(self):
        self.assertEqual(
            parse_svg_size_mm('<svg width="21cm" height="297mm"></svg>'),
            (210.0, 297.0),
        )
        self.assertEqual(
            parse_svg_size_mm('<svg viewBox="0 0 120 80"></svg>'),
            (120.0, 80.0),
        )

    def test_replace_selected_layer_creates_a4_layer_at_a3_top_left(self):
        comp = Composition()

        layer = replace_selected_layer(
            comp,
            LAYER_A,
            name="A4 generator",
            kind="generate",
            source={"id": "spokes"},
        )

        self.assertEqual(comp.page, A3_PAGE)
        self.assertEqual(comp.selected_layer_id, layer.id)
        self.assertEqual(layer.x, 0.0)
        self.assertEqual(layer.y, 0.0)
        self.assertEqual(layer.width, 210.0)
        self.assertEqual(layer.height, 297.0)
        self.assertEqual(layer.kind, "generate")

    def test_replace_selected_layer_updates_only_selected_layer(self):
        comp = Composition()
        first = replace_selected_layer(
            comp,
            LAYER_A,
            name="First",
            kind="generate",
            source={"id": "a"},
        )
        second = comp.add_layer(LAYER_B, name="Second", kind="svg", source={"id": "b"})
        comp.selected_layer_id = first.id

        updated = replace_selected_layer(
            comp,
            LAYER_B,
            name="Updated",
            kind="pathfinding",
            source={"id": "pfm"},
        )

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
                self.assertEqual(
                    [n for n in names if n.endswith(".svg")],
                    ["00_A4_Layer.svg"],
                )
                layer_svg = zf.read("00_A4_Layer.svg").decode()
                manifest = json.loads(zf.read("manifest.json").decode())

        self.assertIn('width="210mm"', layer_svg)
        self.assertIn('height="297mm"', layer_svg)
        self.assertEqual(manifest["page"], A3_PAGE)
        self.assertEqual(manifest["layers"][0]["x"], 10)
        self.assertEqual(manifest["layers"][0]["y"], 20)

    def test_layer_actions_reorder_duplicate_and_delete(self):
        comp = Composition()
        a = comp.add_layer(LAYER_A, "A", "svg", {})
        b = comp.add_layer(LAYER_B, "B", "svg", {})

        self.assertTrue(comp.move_layer(b.id, -1))
        self.assertEqual([layer.id for layer in comp.layers], [b.id, a.id])

        copy = comp.duplicate_layer(b.id)

        self.assertIsNotNone(copy)
        self.assertEqual(copy.name, "B copy")
        self.assertNotEqual(copy.id, b.id)
        self.assertEqual(comp.selected_layer_id, copy.id)

        self.assertTrue(comp.delete_layer(b.id))
        self.assertNotIn(b.id, [layer.id for layer in comp.layers])
        self.assertEqual(comp.selected_layer_id, copy.id)


if __name__ == "__main__":
    unittest.main()


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

            def save_composition_layers(self):
                pass

            def save(self):
                pass

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
        self.assertNotIn("svg", payload)

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
