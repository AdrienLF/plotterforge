import io
import math
from unittest.mock import patch

import pytest
import svgelements as se

from web import server


def svg(body):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">{body}</svg>').encode()


def settings():
    return {**server.DEFAULTS, "reordering": "none"}


def test_resolved_native_circle_does_not_call_expensive_bbox():
    payload = svg('<g transform="translate(10 20) scale(2)"><circle cx="3" cy="4" r="5"/></g>')
    with patch.object(se.Circle, "bbox", side_effect=AssertionError("bbox called")):
        paths = server.svg_to_polylines(payload, settings(), respect_stop=False)
    assert len(paths) == 1
    assert paths[0].arc == pytest.approx({"cx": 16 * 25.4 / 96,
                                          "cy": -28 * 25.4 / 96,
                                          "r": 10 * 25.4 / 96})


def test_ellipse_and_nonuniform_circle_still_flatten():
    for body in ('<ellipse cx="50" cy="50" rx="20" ry="10"/>',
                 '<circle cx="10" cy="10" r="5" transform="scale(2 1)"/>'):
        paths = server.svg_to_polylines(svg(body), settings(), respect_stop=False)
        assert paths
        assert all(getattr(path, "arc", None) is None for path in paths)


def test_circle_fast_path_matches_bbox_geometry_with_numeric_tolerance():
    doc = se.SVG.parse(io.BytesIO(svg('<circle cx="40" cy="30" r="7"/>')))
    circle = next(item for item in doc.elements() if isinstance(item, se.Circle))
    direct = server._circle_meta(circle, se, 25.4 / 96)
    x0, y0, x1, y1 = circle.bbox()
    expected = ((x0 + x1) / 2 * 25.4 / 96,
                -((y0 + y1) / 2) * 25.4 / 96,
                (x1 - x0) / 2 * 25.4 / 96)
    assert direct == pytest.approx(expected, abs=1e-12)
    assert all(math.isfinite(value) for value in direct)
