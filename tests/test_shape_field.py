import math
import unittest

from engine.shape_field import (
    DEFAULT_SHAPE_LAYERS,
    SHAPE_TYPES,
    normalize_shape_layers,
    primitive,
)


class ShapeLayerNormalizationTest(unittest.TestCase):
    def test_defaults_cover_extended_shape_palette(self):
        self.assertEqual(
            SHAPE_TYPES,
            ("circle", "polygon", "star", "diamond", "cross", "spiral", "wave"),
        )
        self.assertEqual(
            [layer["type"] for layer in DEFAULT_SHAPE_LAYERS],
            ["circle", "star", "wave"],
        )

    def test_invalid_values_are_sanitized_and_unknown_keys_are_dropped(self):
        [layer] = normalize_shape_layers(
            [
                {
                    "id": "custom",
                    "enabled": "yes",
                    "type": "bogus",
                    "scale": float("nan"),
                    "sides": 99,
                    "repeat_count": 999,
                    "unknown": "drop me",
                }
            ]
        )
        self.assertEqual(layer["id"], "custom")
        self.assertTrue(layer["enabled"])
        self.assertEqual(layer["type"], "circle")
        self.assertTrue(math.isfinite(layer["scale"]))
        self.assertEqual(layer["sides"], 24)
        self.assertEqual(layer["repeat_count"], 24)
        self.assertNotIn("unknown", layer)

    def test_empty_shape_stack_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least one enabled shape layer"):
            normalize_shape_layers([])


class ShapePrimitiveTest(unittest.TestCase):
    def test_closed_and_open_shape_contracts(self):
        layer = normalize_shape_layers([{}])[0]
        for shape_type in SHAPE_TYPES:
            with self.subTest(shape_type=shape_type):
                line = primitive({**layer, "type": shape_type}, 2.0)
                self.assertGreaterEqual(len(line), 2)
                self.assertTrue(
                    all(math.isfinite(value) for point in line for value in point)
                )
                if shape_type in {"circle", "polygon", "star", "diamond", "cross"}:
                    self.assertEqual(line[0], line[-1])
                else:
                    self.assertNotEqual(line[0], line[-1])
