"""Optimization-specific assertions for composition clipping speedups.

Fidelity is guarded separately by test_clip_fidelity; this file pins the
*mechanics* the speedups rely on (exact mask vertices, curve fallback).

See memory: export-perf-plan.
"""

import unittest

from engine.layer_clip import mask_polygon


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


if __name__ == "__main__":
    unittest.main()
