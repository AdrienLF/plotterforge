"""SVG-native <clipPath> baking in the plot pipeline.

Cavalry's renderSVGFrame exports masks as <clipPath> + <g clip-path="url(#…)">.
svgelements does not render clips, so the flatteners (web.server.svg_to_polylines
and engine.layer_clip.clipped_layer_body) must bake them as real line clipping.
These tests mimic the Cavalry output shape (page-rect clip wrapping everything,
transforms on leaf paths, defs before use).
"""

import math
import unittest

from engine.geometry import point_in_polygon
from engine.layer_clip import clipped_layer_body
from web import server

PX = 25.4 / 96.0
SETTINGS = {"curve_step_mm": 0.5, "reordering": "none"}
EPS_MM = 0.6  # absorbs clip-ring sampling resolution


def _polys(svg: str):
    return server.svg_to_polylines(svg.encode(), SETTINGS, respect_stop=False)


def _pts(polys):
    return [p for poly in polys for p in poly]


def _ellipse_mm(cx, cy, rx, ry, grow=0.0, n=256):
    """Ellipse ring in machine mm (Y negated), optionally grown by ``grow`` mm."""
    return [
        (
            cx * PX + (rx * PX + grow) * math.cos(2 * math.pi * i / n),
            -(cy * PX) - (ry * PX + grow) * math.sin(2 * math.pi * i / n),
        )
        for i in range(n)
    ]


# Cavalry-style document: full-page rect clip around everything, ellipse clip
# around a stroked rectangle whose transform is baked on the leaf path. The
# rect's vertical edges cross the ellipse; its corners lie outside it.
CAVALRY_STYLE = """
<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1000">
  <clipPath id="page"><rect width="1000" height="1000"/></clipPath>
  <g clip-path="url(#page)">
    <clipPath id="mask">
      <path d="M200 500C200 334 334 200 500 200C666 200 800 334 800 500C800 666 666 800 500 800C334 800 200 666 200 500Z" clip-rule="evenodd"/>
    </clipPath>
    <g clip-path="url(#mask)">
      <path fill="none" stroke="#191919" transform="matrix(1 0 0 1 0 0)" d="M300 150L700 150L700 850L300 850L300 150Z"/>
    </g>
  </g>
</svg>
"""
RECT_CORNERS = [(300, 150), (700, 150), (700, 850), (300, 850)]


class CavalryClipPathTest(unittest.TestCase):
    def test_clipped_rect_stays_inside_ellipse(self):
        polys = _polys(CAVALRY_STYLE)
        pts = _pts(polys)
        self.assertTrue(pts, "clipped rectangle must not vanish")
        ellipse = _ellipse_mm(500, 500, 300, 300, grow=EPS_MM)
        outside = [p for p in pts if not point_in_polygon(p, ellipse)]
        self.assertFalse(outside, f"points escaped the clip: {outside[:5]}")

    def test_rect_corners_are_gone(self):
        pts = _pts(_polys(CAVALRY_STYLE))
        for cx, cy in RECT_CORNERS:
            corner = (cx * PX, -(cy * PX))
            near = [p for p in pts if abs(p[0] - corner[0]) < 1 and abs(p[1] - corner[1]) < 1]
            self.assertFalse(near, f"unclipped corner {corner} plotted")

    def test_clip_def_contents_are_not_plotted(self):
        # Rect fully inside the clip: output is the rect only, no ellipse ring.
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1000">
          <clipPath id="m"><path d="M100 500C100 279 279 100 500 100C721 100 900 279 900 500C900 721 721 900 500 900C279 900 100 721 100 500Z"/></clipPath>
          <g clip-path="url(#m)">
            <path fill="none" stroke="#000" d="M400 400L600 400L600 600L400 600L400 400Z"/>
          </g>
        </svg>
        """
        polys = _polys(svg)
        self.assertEqual(len(polys), 1, "only the rectangle should plot — no ellipse ring")
        # Fully inside the clip: geometry survives intact (clip may insert
        # collinear split points; the extent is what matters).
        xs = [x for x, _ in polys[0]]
        ys = [y for _, y in polys[0]]
        self.assertAlmostEqual(min(xs), 400 * PX, delta=EPS_MM)
        self.assertAlmostEqual(max(xs), 600 * PX, delta=EPS_MM)
        self.assertAlmostEqual(min(ys), -600 * PX, delta=EPS_MM)
        self.assertAlmostEqual(max(ys), -400 * PX, delta=EPS_MM)

    def test_page_rect_clip_is_pruned_and_circle_keeps_native_arc(self):
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1000">
          <clipPath id="page"><rect width="1000" height="1000"/></clipPath>
          <g clip-path="url(#page)">
            <circle cx="500" cy="500" r="100" fill="none" stroke="#000"/>
          </g>
        </svg>
        """
        polys = _polys(svg)
        self.assertEqual(len(polys), 1)
        self.assertIsNotNone(getattr(polys[0], "arc", None), "page clip must not break the G2 arc fast path")

    def test_clipped_circle_is_flattened_and_clipped(self):
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1000">
          <clipPath id="half"><rect x="0" y="0" width="500" height="1000"/></clipPath>
          <g clip-path="url(#half)">
            <circle cx="500" cy="500" r="100" fill="none" stroke="#000"/>
          </g>
        </svg>
        """
        polys = _polys(svg)
        pts = _pts(polys)
        self.assertTrue(pts, "half of the circle must survive")
        self.assertTrue(all(getattr(p, "arc", None) is None for p in polys))
        self.assertTrue(all(x <= 500 * PX + EPS_MM for x, _ in pts))
        # left extreme of the circle survives
        self.assertTrue(any(abs(x - 400 * PX) < 1 for x, _ in pts))

    def test_nested_clips_intersect(self):
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1000">
          <clipPath id="a"><rect x="200" y="0" width="400" height="1000"/></clipPath>
          <clipPath id="b"><rect x="400" y="0" width="400" height="1000"/></clipPath>
          <g clip-path="url(#a)"><g clip-path="url(#b)">
            <path fill="none" stroke="#000" d="M0 500L1000 500"/>
          </g></g>
        </svg>
        """
        pts = _pts(_polys(svg))
        self.assertTrue(pts)
        xs = [x for x, _ in pts]
        self.assertAlmostEqual(min(xs), 400 * PX, delta=EPS_MM)
        self.assertAlmostEqual(max(xs), 600 * PX, delta=EPS_MM)

    def test_multi_shape_clip_unions(self):
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1000">
          <clipPath id="two">
            <rect x="100" y="0" width="100" height="1000"/>
            <rect x="700" y="0" width="100" height="1000"/>
          </clipPath>
          <g clip-path="url(#two)">
            <path fill="none" stroke="#000" d="M0 500L1000 500"/>
          </g>
        </svg>
        """
        polys = _polys(svg)
        self.assertEqual(len(polys), 2, "one piece per disjoint clip shape")
        spans = sorted((min(x for x, _ in p), max(x for x, _ in p)) for p in polys)
        self.assertAlmostEqual(spans[0][0], 100 * PX, delta=EPS_MM)
        self.assertAlmostEqual(spans[0][1], 200 * PX, delta=EPS_MM)
        self.assertAlmostEqual(spans[1][0], 700 * PX, delta=EPS_MM)
        self.assertAlmostEqual(spans[1][1], 800 * PX, delta=EPS_MM)


class LayerClipComposesWithAppMaskTest(unittest.TestCase):
    """A Cavalry layer with an internal <clipPath> AND an app-side mask/crop:
    clipped_layer_body must honor both (internal clip first)."""

    def test_internal_clip_applies_inside_clipped_layer_body(self):
        # Layer-local px doc; internal clip keeps x <= 48px (= 12.7mm).
        svg = """
        <svg xmlns="http://www.w3.org/2000/svg" width="96" height="96">
          <clipPath id="l"><rect x="0" y="0" width="48" height="96"/></clipPath>
          <g clip-path="url(#l)">
            <path fill="none" stroke="#000" d="M0 48L96 48"/>
          </g>
        </svg>
        """
        # App-side mask keeps x >= 5mm — intersection is 5mm..12.7mm.
        mask = {"type": "rect", "x": 5, "y": 0, "width": 100, "height": 25.4}
        body = clipped_layer_body(svg, None, mask, None)
        import re

        nums = [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", re.search(r'd="([^"]+)"', body).group(1))]
        xs = nums[0::2]
        self.assertAlmostEqual(min(xs), 5.0, delta=EPS_MM)
        self.assertAlmostEqual(max(xs), 48 * PX, delta=EPS_MM)


if __name__ == "__main__":
    unittest.main()
