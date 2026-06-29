"""Optimization-specific assertions for composition clipping speedups.

Fidelity is guarded separately by test_clip_fidelity; this file pins the
*mechanics* the speedups rely on (exact mask vertices, curve fallback).

See memory: export-perf-plan.
"""

import unittest

from engine.layer_clip import clipped_layer_body, mask_polygon


def _doc(body: str) -> str:
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="120mm" height="120mm" '
        f'viewBox="0 0 120 120">{body}</svg>'
    )


class ExactMaskParsingTest(unittest.TestCase):
    def test_ml_path_mask_uses_exact_vertices(self):
        # Region occlusion masks are emitted as absolute M/L/Z polygons
        # (web/server.py). They must be consumed exactly, not resampled.
        poly = mask_polygon({"type": "path", "d": "M0 0 L10 0 L10 10 L0 10 Z"})
        self.assertEqual(poly, [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)])

    def test_comma_separated_ml_path_is_parsed(self):
        poly = mask_polygon({"type": "path", "d": "M0,0 L10,0 L10,10 Z"})
        self.assertEqual(poly, [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)])

    def test_curved_mask_falls_back_to_resampling(self):
        # Anything with curves can't be taken verbatim — sample it.
        poly = mask_polygon({"type": "path", "d": "M0 0 C 5 0 5 10 0 10 Z"})
        self.assertGreater(len(poly), 8)


class BboxPrefilterTest(unittest.TestCase):
    LINE = _doc('<path d="M100 50 L120 50" stroke="black"/>')  # far right

    def test_polyline_outside_inclusion_mask_is_dropped(self):
        mask = {"type": "rect", "x": 0, "y": 0, "width": 20, "height": 120}  # far left
        body = clipped_layer_body(self.LINE, None, mask, None)
        self.assertNotIn("<path", body)

    def test_polyline_outside_occluder_is_kept_unchanged(self):
        exclude = [{"type": "rect", "x": 0, "y": 0, "width": 20, "height": 120}]
        body = clipped_layer_body(self.LINE, None, None, exclude)
        self.assertIn("<path", body)
        self.assertIn("M100 50 L120 50", body)


if __name__ == "__main__":
    unittest.main()
