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


if __name__ == "__main__":
    unittest.main()
