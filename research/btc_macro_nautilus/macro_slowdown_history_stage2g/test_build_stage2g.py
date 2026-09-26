import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np

PATH = Path(__file__).with_name("build_stage2g.py")
SPEC = importlib.util.spec_from_file_location("stage2g_history", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class CanonicalStage2GTests(unittest.TestCase):
    def test_ridge_is_finite_and_reproducible(self):
        x = np.array([[0.0], [1.0], [2.0], [3.0]])
        y = np.array([0, 0, 1, 1])
        self.assertTrue(np.array_equal(MODULE.fit_ridge(x, y), MODULE.fit_ridge(x, y)))
        self.assertTrue(np.isfinite(MODULE.fit_ridge(x, y)).all())

    def test_auc_known_order(self):
        self.assertEqual(MODULE.auc(np.array([0, 0, 1, 1]), np.array([0.1, 0.2, 0.8, 0.9])), 1.0)

    def test_rank_audit_drops_reconstructable_previous(self):
        rows = []
        for current, delta in ((3.0, 1.0), (5.0, 2.0), (8.0, 4.0), (13.0, 7.0)):
            rows.append({"current": current, "delta": delta, "previous": current - delta})
        self.assertEqual(MODULE.independent_names(rows, ["current", "delta", "previous"]), ["current", "delta"])

    def test_cluster_bootstrap_reproducible(self):
        values = np.array([1.0, 2.0, 3.0, 4.0])
        outcomes = np.array([0, 1, 0, 1])
        legs = np.array(["a", "a", "b", "b"])
        self.assertEqual(MODULE.cluster_bootstrap_median_difference(values, outcomes, legs, 7, 50), MODULE.cluster_bootstrap_median_difference(values, outcomes, legs, 7, 50))

    def test_trajectory_sign(self):
        self.assertEqual(MODULE.trajectory_sign(1.0, -1.0), "up_then_down")
        self.assertEqual(MODULE.trajectory_sign(-1.0, -2.0), "down_then_down")

    def test_checksum_index(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.txt").write_text("a")
            self.assertTrue(MODULE.write_checksums(root))
            self.assertTrue(MODULE.verify_checksum_index(root))


if __name__ == "__main__":
    unittest.main()
