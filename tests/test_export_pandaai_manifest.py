from __future__ import annotations
import importlib.util, sys, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("ep", ROOT/"scripts"/"export_pandaai_manifest.py")
ep=importlib.util.module_from_spec(spec); sys.modules["ep"]=ep; assert spec.loader; spec.loader.exec_module(ep)

class Tests(unittest.TestCase):
    def test_base_formula(self):
        x={"kind":"binary","operator":"div","left":{"kind":"feature","name":"close","lag":0},"right":{"kind":"rolling","operator":"mean","operand":{"kind":"feature","name":"close","lag":0},"window":20}}
        self.assertIn("CLOSE",ep.render(x)); self.assertIn("MA(CLOSE,20)",ep.render(x))
    def test_unsupported_local_feature(self):
        with self.assertRaises(ep.Unsupported): ep.render({"kind":"feature","name":"net_income_ttm","lag":0})
if __name__=="__main__": unittest.main()
