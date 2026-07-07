"""Vectorized Perlin/fBm noise (engine.noise)."""

import unittest

import numpy as np

from engine.noise import fbm


class FbmTest(unittest.TestCase):
    def test_deterministic_per_seed(self):
        a = fbm((64, 64), scale=16, seed=7)
        b = fbm((64, 64), scale=16, seed=7)
        self.assertTrue(np.array_equal(a, b))

    def test_different_seeds_differ(self):
        a = fbm((64, 64), scale=16, seed=7)
        b = fbm((64, 64), scale=16, seed=8)
        self.assertFalse(np.array_equal(a, b))

    def test_range_and_finite(self):
        a = fbm((80, 120), scale=24, octaves=4, seed=3)
        self.assertEqual(a.shape, (80, 120))
        self.assertEqual(a.dtype, np.float32)
        self.assertTrue(np.isfinite(a).all())
        self.assertGreaterEqual(float(a.min()), 0.0)
        self.assertLessEqual(float(a.max()), 1.0)

    def test_not_flat(self):
        a = fbm((64, 64), scale=16, seed=1)
        self.assertGreater(float(a.std()), 0.05)


if __name__ == "__main__":
    unittest.main()
