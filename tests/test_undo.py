"""Composition undo (delete / regenerate snapshots)."""

import unittest

from engine.composition import Composition
import web.server as server

LAYER_A = """<svg xmlns="http://www.w3.org/2000/svg" width="210mm" height="297mm" viewBox="0 0 210 297">
  <path d="M0 0 L10 0"/>
</svg>"""


class UndoApiTest(unittest.TestCase):
    def setUp(self):
        self.old_project = server._project
        self.old_svg = server._current_svg

        class TempProject:
            def __init__(self):
                self.id = "undo-test"
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
        server._undo_stacks.clear()
        self.client = server.app.test_client()

    def tearDown(self):
        server._project = self.old_project
        server._current_svg = self.old_svg
        server._undo_stacks.clear()

    def test_undo_restores_deleted_layer(self):
        layer = server._project.composition.add_layer(LAYER_A, "Keep me", "svg", {})
        r = self.client.delete(f"/api/composition/layers/{layer.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(server._project.composition.layers), 0)

        r = self.client.post("/api/composition/undo")
        self.assertEqual(r.status_code, 200)
        self.assertIn("Keep me", r.get_json()["undone"])
        layers = server._project.composition.layers
        self.assertEqual(len(layers), 1)
        self.assertEqual(layers[0].name, "Keep me")
        self.assertEqual(layers[0].svg, LAYER_A)   # geometry restored, not just metadata

    def test_undo_empty_stack_is_a_clean_400(self):
        r = self.client.post("/api/composition/undo")
        self.assertEqual(r.status_code, 400)

    def test_stack_is_capped(self):
        layer = server._project.composition.add_layer(LAYER_A, "A", "svg", {})
        for i in range(server._UNDO_MAX + 5):
            server._push_undo(f"op {i}")
        self.assertEqual(len(server._undo_stacks[server._project.id]),
                         server._UNDO_MAX)
        del layer


if __name__ == "__main__":
    unittest.main()
