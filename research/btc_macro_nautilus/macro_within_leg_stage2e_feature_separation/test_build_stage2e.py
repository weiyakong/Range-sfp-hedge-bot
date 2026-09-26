import importlib.util,unittest
from pathlib import Path
P=Path(__file__).with_name('build_stage2e.py');S=importlib.util.spec_from_file_location('s',P);M=importlib.util.module_from_spec(S);S.loader.exec_module(M)
class T(unittest.TestCase):
 def test_ratio_zero_safe(self):self.assertIsNone(M.ratio(0,2))
 def test_ratio(self):self.assertEqual(M.ratio(2,3),1.5)
if __name__=='__main__':unittest.main()
