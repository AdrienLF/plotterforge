"""Spatial parameter fields (engine.fields)."""

import math
import unittest

import numpy as np
from PIL import Image

from engine import fields
from engine.params import Param, validate


def _gradient_image(w=120, h=80):
    """Horizontal luminance ramp: black at x=0, white at x=w-1."""
    arr = np.tile(np.linspace(0, 255, w, dtype=np.uint8), (h, 1))
    return Image.fromarray(arr, "L").convert("RGB")


PARAMS = [
    Param("stipple_size", "float", 0.9, min=0.1, max=10, bindable=True),
    Param("dash_angle", "angle", 0.0, min=0, max=360, bindable=True),
    Param("plain", "float", 1.0, min=0, max=10),          # not bindable
]


def _binding(**over):
    base = {
        "kind": "scalar",
        "out_min": 0.0,
        "out_max": 1.0,
        "layers": [{"type": "luminance", "weight": 1.0}],
    }
    base.update(over)
    return base


class NormalizeTest(unittest.TestCase):
    def test_drops_unknown_and_unbindable(self):
        raw = {
            "stipple_size": _binding(),
            "plain": _binding(),          # not bindable
            "nope": _binding(),           # unknown param
        }
        out = fields.normalize_bindings(raw, PARAMS)
        self.assertEqual(set(out), {"stipple_size"})

    def test_drops_zero_weight_bindings(self):
        raw = {"stipple_size": _binding(layers=[{"type": "noise", "weight": 0}])}
        self.assertEqual(fields.normalize_bindings(raw, PARAMS), {})

    def test_clamps_and_defaults(self):
        raw = {"stipple_size": _binding(gamma=99, layers=[
            {"type": "noise", "weight": 100, "octaves": 42},
        ])}
        out = fields.normalize_bindings(raw, PARAMS)["stipple_size"]
        self.assertEqual(out["gamma"], 8.0)
        self.assertEqual(out["layers"][0]["weight"], 4.0)
        self.assertEqual(out["layers"][0]["octaves"], 6)
        self.assertIn("scale", out["layers"][0])

    def test_angle_params_are_orientation_kind(self):
        raw = {"dash_angle": _binding()}
        out = fields.normalize_bindings(raw, PARAMS)["dash_angle"]
        self.assertEqual(out["kind"], "orientation")

    def test_validate_strips_the_sidecar(self):
        vals = validate(PARAMS, {"stipple_size": 2.0,
                                 "field_bindings": {"stipple_size": _binding()}})
        self.assertNotIn("field_bindings", vals)


class ResolveTest(unittest.TestCase):
    def test_per_point_unbound_is_constant(self):
        sites = np.array([[1.0, 1.0], [50.0, 40.0]], dtype=np.float32)
        out = fields.per_point({"stipple_size": 2.5}, "stipple_size", sites, 0.9)
        self.assertTrue(np.allclose(out, 2.5))

    def test_per_point_luminance_binding_follows_tone(self):
        ctx = fields.FieldContext(_gradient_image(), seed=0)
        binding = fields.normalize_binding(_binding(), PARAMS[0])
        vals = {"field_bindings": {"stipple_size": binding}, "_field_ctx": ctx}
        xs = np.array([[5.0, 40.0], [60.0, 40.0], [115.0, 40.0]], dtype=np.float32)
        out = fields.per_point(vals, "stipple_size", xs, 0.9)
        # darkness decreases left -> right, so values must strictly decrease
        self.assertGreater(out[0], out[1])
        self.assertGreater(out[1], out[2])

    def test_resolve_at_matches_raster_lookup(self):
        ctx = fields.FieldContext(_gradient_image(), seed=0)
        binding = fields.normalize_binding(_binding(), PARAMS[0])
        raster = fields.resolve_scalar(binding, ctx)
        vals = {"field_bindings": {"stipple_size": binding}, "_field_ctx": ctx}
        sites = np.array([[10.0, 10.0], [100.0, 70.0]], dtype=np.float32)
        out = fields.per_point(vals, "stipple_size", sites, 0.9)
        self.assertAlmostEqual(float(out[0]), float(raster[10, 10]), places=6)
        self.assertAlmostEqual(float(out[1]), float(raster[70, 100]), places=6)

    def test_out_range_and_invert(self):
        ctx = fields.FieldContext(_gradient_image(), seed=0)
        b = fields.normalize_binding(
            _binding(out_min=2.0, out_max=4.0, invert=True), PARAMS[0])
        raster = fields.resolve_scalar(b, ctx)
        self.assertGreaterEqual(float(raster.min()), 2.0)
        self.assertLessEqual(float(raster.max()), 4.0)
        # inverted: dark (left) now low, bright (right) high
        self.assertLess(float(raster[40, 2]), float(raster[40, 117]))

    def test_orientation_linear_layer_is_constant_angle(self):
        ctx = fields.FieldContext(_gradient_image(), seed=0)
        b = fields.normalize_binding(
            {"kind": "orientation",
             "layers": [{"type": "linear", "weight": 1.0, "angle": 45.0}]},
            PARAMS[1])
        raster = fields.resolve_orientation(b, ctx)
        self.assertTrue(np.allclose(raster, math.radians(45.0), atol=1e-5))


class PersistenceTest(unittest.TestCase):
    def test_run_does_not_leak_context_into_style_dicts(self):
        # PFM.run injects _field_ctx into its local vals only; the params dict
        # a caller persists must never gain underscore keys.
        from engine.canvas import DrawingArea
        from engine.pens import DrawingSet
        from engine.pfm.base import get

        pfm = get("voronoi_stippling")
        params = {"seed": 1, "point_density": 30,
                  "field_bindings": {"stipple_size": _binding()}}
        pfm.run(_gradient_image(), DrawingArea(), DrawingSet(), params, seed=1)
        self.assertNotIn("_field_ctx", params)
        for key in params:
            self.assertFalse(str(key).startswith("_"))


if __name__ == "__main__":
    unittest.main()
