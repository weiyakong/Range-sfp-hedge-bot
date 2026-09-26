import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np


MODULE_PATH = Path(__file__).with_name("build_macro_structure_stage1.py")
SPEC = importlib.util.spec_from_file_location("macro_structure_stage1", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class StageOneTests(unittest.TestCase):
    def test_signed_stat_orientation_swaps_quantiles_for_down_leg(self):
        row = {"direction": "down", "signed_log_move__p25": -3.0, "signed_log_move__p75": 2.0}
        name, value, transform = MODULE.normalized_column(row, "signed_log_move__p25")
        self.assertEqual(name, "leg_relative_signed_log_move__p25")
        self.assertEqual(value, -2.0)
        self.assertEqual(transform, "signed_stat_leg_orientation")

    def test_redundancy_reduction(self):
        values = {"a": np.arange(30, dtype=float), "b": np.arange(30, dtype=float) * 2, "c": np.arange(30, dtype=float)[::-1]}
        names, matrix, mask, audit = MODULE.clean_compact_matrix(values)
        self.assertEqual(mask.sum(), 30)
        self.assertEqual(len(names), 1)
        self.assertEqual(matrix.shape, (30, 1))
        self.assertTrue(any(row["status"] == "excluded_near_duplicate" for row in audit))

    def test_adjusted_rand_identity(self):
        labels = np.array([0, 0, 1, 1])
        self.assertEqual(MODULE.adjusted_rand_index(labels, labels), 1.0)

    def test_kmeans_and_silhouette(self):
        matrix = np.vstack([np.random.default_rng(1).normal(-3, 0.2, (12, 2)), np.random.default_rng(2).normal(3, 0.2, (12, 2))])
        labels, _ = MODULE.kmeans(matrix, 2, 7)
        self.assertGreater(MODULE.silhouette(matrix, labels), 0.7)

    def test_fixed_seed_identical_result(self):
        matrix = np.vstack([np.random.default_rng(10).normal(-2, 0.3, (20, 3)), np.random.default_rng(11).normal(2, 0.3, (20, 3))])
        first = MODULE.clusterability(matrix, MODULE.stable_seed("4h", "speed_movement_rate"))
        second = MODULE.clusterability(matrix, MODULE.stable_seed("4h", "speed_movement_rate"))
        self.assertEqual(first[0], second[0])
        for k in first[1]:
            self.assertTrue(np.array_equal(first[1][k][0], second[1][k][0]))

    def test_svd_pca_variance_and_reconstruction(self):
        matrix = np.array([[1.0, 2.0], [2.0, 4.0], [3.0, 6.0], [4.0, 8.0]])
        standardized, scores, components, share = MODULE.svd_pca(matrix)
        reconstructed = scores @ components
        self.assertAlmostEqual(float(share.sum()), 1.0)
        self.assertTrue(np.allclose(standardized, reconstructed, atol=1e-12))
        self.assertGreater(float(share[0]), 0.999999)

    def test_kmeans_converges_without_empty_clusters(self):
        matrix = np.vstack([np.zeros((10, 2)), np.ones((10, 2)) * 10, np.ones((10, 2)) * -10])
        labels, centers = MODULE.kmeans(matrix, 3, 123)
        self.assertEqual(centers.shape, (3, 2))
        self.assertTrue(all(np.sum(labels == label) > 0 for label in range(3)))

    def test_pairwise_distance_invariants(self):
        matrix = np.array([[0.0, 0.0], [3.0, 4.0], [6.0, 8.0]])
        distances = MODULE.distance_matrix(matrix)
        self.assertTrue(np.allclose(distances, distances.T))
        self.assertTrue(np.allclose(np.diag(distances), 0.0))
        self.assertTrue(np.all(distances >= 0))

    def test_coassignment_invariants_and_reproducibility(self):
        rng = np.random.default_rng(99)
        matrix = np.vstack([rng.normal(-3, 0.3, (20, 3)), rng.normal(3, 0.3, (20, 3))])
        labels, _ = MODULE.kmeans(MODULE.standardize(matrix), 2, 5)
        first_metrics, first_matrix, first_scores = MODULE.stability(matrix, labels, 2, 88)
        second_metrics, second_matrix, second_scores = MODULE.stability(matrix, labels, 2, 88)
        self.assertEqual(first_metrics, second_metrics)
        self.assertTrue(np.allclose(first_matrix, second_matrix, equal_nan=True))
        self.assertTrue(np.allclose(first_scores, second_scores, equal_nan=True))
        self.assertTrue(np.allclose(first_matrix, first_matrix.T, equal_nan=True))
        self.assertTrue(np.allclose(np.diag(first_matrix), 1.0))
        finite = first_matrix[np.isfinite(first_matrix)]
        self.assertTrue(np.all((finite >= 0) & (finite <= 1)))

    def test_stability_skips_features_constant_in_a_subsample(self):
        # This feature is globally variable but commonly constant after
        # subsampling; the fit must use only non-constant sampled columns.
        matrix = np.column_stack([np.arange(20, dtype=float), np.tile([0.0, 1.0], 10), np.r_[1.0, np.zeros(19)]])
        labels, _ = MODULE.kmeans(MODULE.standardize(matrix), 2, 14)
        metrics, coassignment, scores = MODULE.stability(matrix, labels, 2, 15)
        self.assertEqual(metrics["repetitions"], MODULE.CONFIG["stability_repetitions"])
        self.assertTrue(np.allclose(coassignment, coassignment.T, equal_nan=True))
        self.assertEqual(len(scores), len(matrix))


if __name__ == "__main__":
    unittest.main()
