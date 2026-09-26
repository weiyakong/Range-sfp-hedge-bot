import importlib.util,tempfile,unittest,numpy as np
from pathlib import Path
P=Path(__file__).with_name('build_stage2f.py');S=importlib.util.spec_from_file_location('s',P);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_cliff_identity(self):self.assertEqual(M.cliff([1,2],[1,2]),0)
 def test_logistic_finite(self):self.assertTrue(np.isfinite(M.fit(np.array([[0.],[1.],[2.],[3.]]),np.array([0,0,1,1]))).all())
 def test_bootstrap_reproducible(self):self.assertEqual(M.bootstrap(np.array([1,2]),np.array([3,4]),1,20),M.bootstrap(np.array([1,2]),np.array([3,4]),1,20))
 def test_auc_known_order(self):self.assertEqual(M.auc(np.array([0,0,1,1]),np.array([.1,.2,.8,.9])),1.0)
 def test_direction_context_not_in_model(self):self.assertTrue({'net_move','delta_net_log_move'}.isdisjoint(M.MODEL_PRED))
 def test_checksum_index_verifies(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'a.txt').write_text('a');(p/'b.txt').write_text('b')
   self.assertTrue(M.write_checksums(p));self.assertEqual(len((p/'checksums.sha256').read_text().splitlines()),2)
if __name__=='__main__':unittest.main()
