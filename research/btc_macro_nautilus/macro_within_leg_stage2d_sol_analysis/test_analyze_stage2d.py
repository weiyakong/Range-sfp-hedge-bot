import importlib.util,sys,unittest
from pathlib import Path
P=Path(__file__).with_name('analyze_stage2d.py');S=importlib.util.spec_from_file_location('s2d',P);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_signature_is_deterministic(self):
  r={z:(i-2) for i,z in enumerate(M.Z)};r['direction_continuation']=True;self.assertEqual(M.signature(r),M.signature(r))
 def test_provisional_is_not_final_label(self):
  r={'signature':'+'*0+'+|+|+|+|+|+|C','mean_speed':1,'mean_volatility_activity':1,'mean_persistence_alternation':1,'mean_overlap':0,'mean_net_move':1};self.assertTrue(M.provisional(r).endswith('-like'))
if __name__=='__main__':unittest.main()
