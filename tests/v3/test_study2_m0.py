from __future__ import annotations

from datetime import date
import math
import unittest

import numpy as np

from src.v3.study2.m0 import (
    BASE_FEATURES,
    date_balanced_weights,
    weighted_quantile,
)


class TestStudy2M0(unittest.TestCase):
    def test_date_balanced_weights_equal_total_mass_per_date(self):
        dates = ["a", "a", "b", "b", "b"]
        w = date_balanced_weights(dates)
        self.assertAlmostEqual(float(w[:2].sum()), 1.0)
        self.assertAlmostEqual(float(w[2:].sum()), 1.0)

    def test_weighted_quantile(self):
        v = np.asarray([0.0, 1.0, 2.0])
        w = np.asarray([0.25, 0.50, 0.25])
        self.assertEqual(weighted_quantile(v, w, 0.50), 1.0)

    def test_feature_contract_is_small(self):
        self.assertEqual(len(BASE_FEATURES), 9)
        self.assertIn("running_max_f", BASE_FEATURES)
        self.assertIn("observation_age_minutes", BASE_FEATURES)
        self.assertIn("temp_change_60m_missing", BASE_FEATURES)


if __name__ == "__main__":
    unittest.main()
