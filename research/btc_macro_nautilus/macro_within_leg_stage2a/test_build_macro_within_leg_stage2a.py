import importlib.util
import sys
import unittest
from pathlib import Path
import numpy as np

P=Path(__file__).with_name("build_macro_within_leg_stage2a.py")
S=importlib.util.spec_from_file_location("stage2a",P); M=importlib.util.module_from_spec(S); assert S.loader; sys.modules[S.name]=M; S.loader.exec_module(M)

class Tests(unittest.TestCase):
    def test_change_points_are_fixed_config_reproducible(self):
        x=np.vstack([np.zeros((8,2)),np.ones((8,2))*5,np.ones((8,2))*-5])
        self.assertEqual(M.binary_segmentation(x,3,8),M.binary_segmentation(x,3,8))
    def test_change_point_finds_known_transitions(self):
        x=np.vstack([np.zeros((8,2)),np.ones((8,2))*6,np.ones((8,2))*-6])
        self.assertEqual(M.binary_segmentation(x,3,8),[8,16])
    def test_contiguous_cover_guard(self):
        seq=[{} for _ in range(5)]
        M.check_cover([{"segment_id":"L","start_index":0,"end_index_exclusive":2},{"segment_id":"L","start_index":2,"end_index_exclusive":5}],seq,"L")
        with self.assertRaises(ValueError): M.check_cover([{"segment_id":"L","start_index":0,"end_index_exclusive":2},{"segment_id":"L","start_index":3,"end_index_exclusive":5}],seq,"L")
    def test_signed_orientation_is_exact(self):
        r=M.oriented_row({"timestamp":"t","end_time":"e","source_complete":True,"pair_eligible":True,"signed_log_move":.2,"volume_body_up":1,"volume_body_down":2,"volume_body_flat":0,"volume_close_step_up":3,"volume_close_step_down":4,"volume_close_step_flat":0},"down",["signed_log_move"])
        self.assertEqual(r["signed_log_move"],-.2); self.assertEqual(r["volume_body_forward"],2)
    def test_within_leg_constant_feature_has_zero_standardized_contribution(self):
        x=M.balanced_standardize(np.array([[1., 2.], [1., 3.], [1., 4.]]), ["body_size", "signed_log_move"])
        self.assertTrue(np.allclose(x[:,0],0.0)); self.assertTrue(np.isfinite(x).all())
    def test_global_compact_space_removes_post_complete_case_constant(self):
        rows=[{"a":float(i) if i<4 else 1.,"b":None if i<4 else float(i)} for i in range(20)]
        names,audit=M.clean_features(rows,["a","b"])
        self.assertEqual(names,["b"]); self.assertIn("excluded_constant_after_complete_case",[x["status"] for x in audit])
if __name__=="__main__": unittest.main()
