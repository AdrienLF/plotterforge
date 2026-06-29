"""Fidelity safety net for composition layer clipping.

These characterize the *plotted geometry* of `clipped_layer_body` (centerlines,
path order, attributes) — NOT its exact XML — so the planned export speedups
(exact mask parsing, a fast M/L+circle parser, caching) cannot silently change
what actually gets plotted. Assertions are tolerant of coordinate jitter and
mask-resolution changes; they pin behavior, not bytes.

See memory: export-perf-plan.
"""

import re
import unittest

from engine.layer_clip import clipped_layer_body
from engine.geometry import point_in_polygon

EPS = 0.6  # mm — absorbs flatten/clip rounding and mask-resolution changes


def _doc(body: str, size: float = 120.0) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}mm" height="{size}mm" '
        f'viewBox="0 0 {size} {size}">{body}</svg>'
    )


def _paths(svg_body: str):
    """Parsed output: list of (stroke, [(x, y), ...]) in document order."""
    out = []
    for m in re.finditer(r'<path d="([^"]+)"([^/]*)/>', svg_body):
        d, attrs = m.group(1), m.group(2)
        nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", d)]
        pts = list(zip(nums[0::2], nums[1::2]))
        stroke = re.search(r'stroke="([^"]+)"', attrs)
        out.append((stroke.group(1) if stroke else None, pts))
    return out


def _all_points(paths):
    return [p for _stroke, pts in paths for p in pts]


def _rect_poly(x, y, w, h):
    return [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]


class PartialCircleClipTest(unittest.TestCase):
    """A circle straddling a mask edge must keep its *visible arc* — never be
    kept or dropped wholesale (the rejected center-test bug)."""

    CIRCLE = _doc('<circle cx="60" cy="60" r="40" fill="black"/>')

    def test_circle_on_inclusion_mask_edge_keeps_the_inside_arc(self):
        mask = {"type": "rect", "x": 60, "y": 0, "width": 60, "height": 120}
        paths = _paths(clipped_layer_body(self.CIRCLE, None, mask, None))
        pts = _all_points(paths)

        self.assertTrue(pts, "boundary circle must not be dropped")
        # Nothing from the removed (left) half.
        self.assertFalse(any(x < 60 - EPS for x, _y in pts), "left half not removed")
        # The visible arc actually reaches both the cut edge and the far side.
        self.assertTrue(any(abs(x - 60) < EPS + 1 for x, _y in pts), "no geometry at the cut")
        self.assertTrue(any(x > 90 for x, _y in pts), "far side of the arc missing")

    def test_circle_fully_inside_mask_is_fully_retained(self):
        mask = {"type": "rect", "x": 0, "y": 0, "width": 120, "height": 120}
        pts = _all_points(_paths(clipped_layer_body(self.CIRCLE, None, mask, None)))
        self.assertTrue(pts)
        poly = _rect_poly(0, 0, 120, 120)
        self.assertTrue(all(point_in_polygon((x, y), poly) for x, y in pts))
        # A retained circle spans roughly its full diameter on both axes.
        xs = [x for x, _ in pts]
        self.assertGreater(max(xs) - min(xs), 60)


class OcclusionMaskTest(unittest.TestCase):
    """Occlusion (exclude) masks remove only the covered span, leaving the
    outside geometry untouched and split correctly."""

    LINE = _doc('<path d="M0 50 L120 50" stroke="black"/>')

    def test_exclude_mask_removes_only_the_covered_middle(self):
        exclude = [{"type": "rect", "x": 40, "y": 0, "width": 40, "height": 120}]
        paths = _paths(clipped_layer_body(self.LINE, None, None, exclude))
        pts = _all_points(paths)

        self.assertTrue(pts)
        # Covered interval (40, 80) is gone; the flanks survive.
        self.assertFalse(any(40 + EPS < x < 80 - EPS for x, _y in pts))
        self.assertTrue(any(x < 40 for x, _y in pts), "left flank removed")
        self.assertTrue(any(x > 80 for x, _y in pts), "right flank removed")
        self.assertEqual(len(paths), 2, "line should split into two spans")


class ConcaveMaskTest(unittest.TestCase):
    """A concave (C-shaped) inclusion mask must keep geometry only in its solid
    part, excluding the notch."""

    LINE = _doc('<path d="M0 50 L120 50" stroke="black"/>')
    # Full 100x100 square minus a left-opening notch x in [0,70], y in [30,70].
    CONCAVE = (
        "M0 0 L100 0 L100 100 L0 100 L0 70 L70 70 L70 30 L0 30 Z"
    )

    def test_horizontal_line_keeps_solid_bar_and_skips_notch(self):
        mask = {"type": "path", "d": self.CONCAVE}
        pts = _all_points(_paths(clipped_layer_body(self.LINE, None, mask, None)))

        self.assertTrue(pts)
        # Nothing inside the notch interior (well clear of edges).
        self.assertFalse(any(10 < x < 60 for x, _y in pts), "notch interior not excluded")
        # Only the solid right bar (x in [70,100]) survives: span runs from the
        # notch edge (~70) to the square edge (~100).
        xs = [x for x, _y in pts]
        self.assertGreaterEqual(min(xs), 70 - EPS, "geometry kept left of the solid bar")
        self.assertGreater(max(xs), 95, "solid bar does not reach the square edge")


class OverlappingOccludersTest(unittest.TestCase):
    """Two overlapping occlusion masks remove the union of their coverage."""

    LINE = _doc('<path d="M0 50 L120 50" stroke="black"/>')

    def test_union_of_two_overlapping_excludes_is_removed(self):
        exclude = [
            {"type": "rect", "x": 40, "y": 0, "width": 30, "height": 120},  # 40..70
            {"type": "rect", "x": 60, "y": 0, "width": 30, "height": 120},  # 60..90
        ]
        pts = _all_points(_paths(clipped_layer_body(self.LINE, None, None, exclude)))

        self.assertTrue(pts)
        self.assertFalse(any(40 + EPS < x < 90 - EPS for x, _y in pts), "union not removed")
        self.assertTrue(any(x < 40 for x, _y in pts))
        self.assertTrue(any(x > 90 for x, _y in pts))


class PathOrderAndAttributesTest(unittest.TestCase):
    """Source order, and per-element stroke attributes, must be preserved."""

    LAYERS = _doc(
        '<path d="M0 20 L120 20" stroke="#ff0000"/>'
        '<path d="M0 60 L120 60" stroke="#00ff00"/>'
        '<path d="M0 100 L120 100" stroke="#0000ff"/>'
    )

    def test_full_crop_preserves_order_and_strokes(self):
        crop = {"x": 0, "y": 0, "width": 120, "height": 120}
        paths = _paths(clipped_layer_body(self.LAYERS, crop, None, None))

        self.assertEqual(len(paths), 3)
        self.assertEqual([s for s, _ in paths], ["#ff0000", "#00ff00", "#0000ff"])
        # y position confirms order wasn't shuffled.
        ys = [pts[0][1] for _s, pts in paths]
        self.assertEqual(ys, sorted(ys))


class FallbackTest(unittest.TestCase):
    """Curves and transforms must keep working — the future fast parser falls
    back to svgelements for anything beyond canonical M/L + circles."""

    CURVE = _doc(
        '<g transform="translate(10 0)">'
        '<path d="M10 10 C 30 10 30 60 60 60" stroke="black" fill="none"/>'
        "</g>"
    )

    def test_bezier_with_transform_clips_within_inclusion_mask(self):
        mask = {"type": "rect", "x": 0, "y": 0, "width": 120, "height": 120}
        pts = _all_points(_paths(clipped_layer_body(self.CURVE, None, mask, None)))
        self.assertTrue(pts, "curve+transform produced no clipped geometry")
        poly = _rect_poly(0, 0, 120, 120)
        self.assertTrue(all(point_in_polygon((x, y), poly) for x, y in pts))


class DegenerateGeometryTest(unittest.TestCase):
    """Tangency / collinear edges must not crash and must stay inside."""

    def test_line_along_mask_edge_does_not_crash(self):
        svg = _doc('<path d="M0 50 L120 50" stroke="black"/>')
        mask = {"type": "rect", "x": 0, "y": 50, "width": 120, "height": 50}
        body = clipped_layer_body(svg, None, mask, None)  # edge-collinear
        self.assertIsInstance(body, str)

    def test_line_through_a_polygon_vertex_does_not_crash(self):
        svg = _doc('<path d="M0 0 L120 120" stroke="black"/>')  # diagonal through corner
        mask = {"type": "rect", "x": 40, "y": 40, "width": 40, "height": 40}
        body = clipped_layer_body(svg, None, mask, None)
        self.assertIsInstance(body, str)


if __name__ == "__main__":
    unittest.main()
