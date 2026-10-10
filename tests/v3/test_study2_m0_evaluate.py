from __future__ import annotations

import unittest
import numpy as np

from src.v3.study2.m0_evaluate import (
    _cdf_at,
    _crps_location_scale,
    _ecdf_precompute,
    _expected_abs_to_a,
)


class TestStudy2M0Evaluate(unittest.TestCase):
    def test_ecdf_helpers_two_point_equal_weight(self):
        z = np.asarray([0.0, 2.0])
        w = np.asarray([0.5, 0.5])
        p = _ecdf_precompute(z, w)
        self.assertAlmostEqual(p["pair_abs"], 1.0)
        self.assertAlmostEqual(_expected_abs_to_a(p, 1.0), 1.0)
        self.assertAlmostEqual(_cdf_at(p, 1.0), 0.5)

    def test_crps_two_point_distribution(self):
        z = np.asarray([0.0, 2.0])
        w = np.asarray([0.5, 0.5])
        p = _ecdf_precompute(z, w)
        # At y=1, E|X-y|=1 and .5 E|X-X'|=.5, hence CRPS=.5.
        self.assertAlmostEqual(
            _crps_location_scale(y=1.0, mu=0.0, scale=1.0, pre=p),
            0.5,
        )

    def test_scale_property(self):
        z = np.asarray([-1.0, 1.0])
        w = np.asarray([0.5, 0.5])
        p = _ecdf_precompute(z, w)
        a = _crps_location_scale(y=0.0, mu=0.0, scale=1.0, pre=p)
        b = _crps_location_scale(y=0.0, mu=0.0, scale=3.0, pre=p)
        self.assertAlmostEqual(b, 3.0 * a)


if __name__ == "__main__":
    unittest.main()
