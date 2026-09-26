import importlib.util,sys,unittest
from pathlib import Path
import numpy as np
P=Path(__file__).with_name('build_macro_subsegment_types_stage2b.py');S=importlib.util.spec_from_file_location('s2b',P);M=importlib.util.module_from_spec(S);assert S.loader;sys.modules[S.name]=M;S.loader.exec_module(M)
class Tests(unittest.TestCase):
 def test_kmeans_reproducible_nonempty(self):
  x=np.vstack([np.zeros((10,2)),np.ones((10,2))*5]);a,_=M.kmeans(x,2,3);b,_=M.kmeans(x,2,3);self.assertTrue(np.array_equal(a,b));self.assertTrue(all((a==i).any() for i in range(2)))
 def test_distance_invariants(self):
  d=M.distance(np.array([[0.,0.],[3.,4.]]));self.assertTrue(np.allclose(d,d.T));self.assertTrue(np.allclose(np.diag(d),0));self.assertTrue((d>=0).all())
 def test_ari_identity(self):self.assertEqual(M.ari(np.array([0,0,1]),np.array([0,0,1])),1.)
 def test_family_balancing(self):
  x=M.balance(np.array([[1.,1.,1.],[2.,2.,3.],[3.,3.,5.]]),['body_size','upper_wick','signed_log_move']);self.assertTrue(np.isfinite(x).all())
if __name__=='__main__':unittest.main()
