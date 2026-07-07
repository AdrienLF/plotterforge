"""Engraving PFM (engine.engrave)."""

import math
import unittest

import numpy as np
from PIL import Image

from engine.pfm.base import REGISTRY, generate_items, get


def _split_image(w=200, h=200):
    """Left half black, right half white."""
    arr = np.full((h, w), 255, dtype=np.uint8)
    arr[:, : w // 2] = 0
    return Image.fromarray(arr, "L").convert("RGB")


def _ink_by_half(items, w):
    left = right = 0.0
    for it in items:
        if it.path is None:
            continue
        pts = it.path.points
        for a, b in zip(pts, pts[1:]):
            length = math.hypot(b[0] - a[0], b[1] - a[1])
            if (a[0] + b[0]) / 2 < w / 2:
                left += length
            else:
                right += length
    return left, right


class EngravingTest(unittest.TestCase):
    def test_registered(self):
        self.assertIn("engraving", REGISTRY)

    def test_dark_side_gets_denser_lines(self):
        # The density contrast matches the shipping streamline engine: at the
        # default spacing range the dark half carries ~1.5x the ink. Assert a
        # solid margin, not the theoretical spacing ratio.
        img = _split_image()
        items = generate_items(get("engraving"), img, {"seed": 2}, 2, (200, 200))
        self.assertGreater(len(items), 5)
        left, right = _ink_by_half(items, 200)
        self.assertGreater(left, right * 1.3)

    def test_bands_add_crossing_directions(self):
        img = _split_image()
        pfm = get("engraving")
        base = {"seed": 2, "edge_weight": 0.0, "base_angle": 0.0,
                "min_spacing": 2.0, "max_spacing": 8.0}
        one = generate_items(pfm, img, {**base, "bands": 1}, 2, (200, 200))
        two = generate_items(pfm, img, {**base, "bands": 2, "cross_angle": 90.0},
                             2, (200, 200))

        def angle_histogram(items):
            """Fraction of segment length that is near-horizontal vs vertical."""
            horiz = vert = 0.0
            for it in items:
                if it.path is None:
                    continue
                pts = it.path.points
                for a, b in zip(pts, pts[1:]):
                    dx, dy = b[0] - a[0], b[1] - a[1]
                    length = math.hypot(dx, dy)
                    if length == 0:
                        continue
                    ang = abs(math.atan2(dy, dx)) % math.pi
                    if ang < math.pi / 6 or ang > 5 * math.pi / 6:
                        horiz += length
                    elif math.pi / 3 < ang < 2 * math.pi / 3:
                        vert += length
            return horiz, vert

        h1, v1 = angle_histogram(one)
        h2, v2 = angle_histogram(two)
        # one band at angle 0 -> almost all horizontal; two bands at 90deg
        # apart -> substantial vertical ink appears
        self.assertGreater(h1, v1 * 5)
        self.assertGreater(v2, v1 + 1.0)
        self.assertGreater(v2, 0.2 * h2)

    def test_direction_binding_overrides_mix(self):
        img = _split_image()
        pfm = get("engraving")
        binding = {"kind": "orientation",
                   "layers": [{"type": "linear", "weight": 1.0, "angle": 90.0}]}
        items = generate_items(
            pfm, img,
            {"seed": 2, "field_bindings": {"direction": binding}},
            2, (200, 200))

        vert = total = 0.0
        for it in items:
            if it.path is None:
                continue
            pts = it.path.points
            for a, b in zip(pts, pts[1:]):
                dx, dy = b[0] - a[0], b[1] - a[1]
                length = math.hypot(dx, dy)
                total += length
                ang = abs(math.atan2(dy, dx)) % math.pi
                if math.pi / 3 < ang < 2 * math.pi / 3:
                    vert += length
        self.assertGreater(total, 0)
        self.assertGreater(vert / total, 0.8)


if __name__ == "__main__":
    unittest.main()
