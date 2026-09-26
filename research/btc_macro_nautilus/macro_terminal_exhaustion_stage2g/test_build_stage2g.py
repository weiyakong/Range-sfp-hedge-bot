import importlib.util
import tempfile
import unittest
from pathlib import Path

import numpy as np

PATH = Path(__file__).with_name("build_stage2g.py")
SPEC = importlib.util.spec_from_file_location("stage2g", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Stage2GTests(unittest.TestCase):
    def test_paired_rank_biserial_direction(self):
        self.assertEqual(MODULE.paired_rank_biserial(np.array([1.0, 2.0, 3.0])), 1.0)
        self.assertEqual(MODULE.paired_rank_biserial(np.array([-1.0, -2.0, -3.0])), -1.0)

    def test_cluster_bootstrap_reproducible(self):
        changes = np.array([1.0, 2.0, -1.0, 3.0])
        legs = np.array(["a", "a", "b", "c"])
        self.assertEqual(MODULE.cluster_bootstrap_median(changes, legs, 7, 50), MODULE.cluster_bootstrap_median(changes, legs, 7, 50))

    def test_extreme_metrics_up(self):
        previous = [{"high": 100.0, "low": 90.0, "close": 95.0}]
        terminal = [{"high": 110.0, "low": 96.0, "close": 105.0}]
        result = MODULE.extreme_metrics(previous, terminal, "up", 0.2)
        self.assertTrue(result["new_extreme"])
        self.assertAlmostEqual(result["extension_log"], np.log(1.1))
        self.assertGreater(result["retained_extension_fraction"], 0)

    def test_extreme_metrics_down(self):
        previous = [{"high": 110.0, "low": 100.0, "close": 105.0}]
        terminal = [{"high": 104.0, "low": 90.0, "close": 95.0}]
        result = MODULE.extreme_metrics(previous, terminal, "down", 0.2)
        self.assertTrue(result["new_extreme"])
        self.assertAlmostEqual(result["extension_log"], np.log(100 / 90))

    def test_ridge_finite(self):
        x = np.array([[0.0], [1.0], [2.0], [3.0]])
        self.assertTrue(np.isfinite(MODULE.fit_ridge(x, np.array([0, 0, 1, 1]))).all())

    def test_checksums(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.txt").write_text("a")
            self.assertTrue(MODULE.write_checksums(root))


if __name__ == "__main__":
    unittest.main()
