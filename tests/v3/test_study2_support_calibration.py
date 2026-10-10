from __future__ import annotations

import unittest
import numpy as np

from src.v3.study2.support_calibration import (
    _q_bin_label,
    _survival_probability,
)


class TestStudy2SupportCalibration(unittest.TestCase):
    def test_q_bins(self):
        self.assertIsNone(_q_bin_label(0.049))
        self.assertEqual(_q_bin_label(0.05), "0.05-0.10")
        self.assertEqual(_q_bin_label(0.149), "0.10-0.15")
        self.assertEqual(_q_bin_label(0.95), "0.90-0.95")
        self.assertIsNone(_q_bin_label(0.951))

    def test_strict_survival_probability(self):
        z = np.asarray([-1.0, 0.0, 1.0])
        w = np.asarray([0.2, 0.5, 0.3])
        # Strict Z > 0 leaves only mass at +1.
        self.assertAlmostEqual(_survival_probability(z, w, 0.0), 0.3)


if __name__ == "__main__":
    unittest.main()
