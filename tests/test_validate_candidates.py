from __future__ import annotations
import importlib.util, sys, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location("vc", ROOT/"scripts"/"validate_candidates.py")
vc=importlib.util.module_from_spec(spec); sys.modules["vc"]=vc; assert spec.loader; spec.loader.exec_module(vc)

def F(name,lag=0): return {"kind":"feature","name":name,"lag":lag}
def C(v): return {"kind":"constant","value":v}
def U(op,x): return {"kind":"unary","operator":op,"operand":x}
def B(op,a,b): return {"kind":"binary","operator":op,"left":a,"right":b}
def R(op,x,w): return {"kind":"rolling","operator":op,"operand":x,"window":w}
def Q(op,a,b): return {"kind":"comparison","operator":op,"left":a,"right":b}

class Tests(unittest.TestCase):
    def setUp(self):
        self.allowed={"open","close","high","low","amount","volume","market_cap","turnover"}
    def test_abs_positive_ratio_rank_equiv(self):
        a=B("div",F("open"),R("delay",F("close"),1))
        b=U("abs",a)
        ca=vc.canonicalize(a,self.allowed); cb=vc.canonicalize(b,self.allowed)
        self.assertEqual(vc.rank_signature(ca)[0],vc.rank_signature(cb)[0])
    def test_sum_condition_over_n_equals_mean(self):
        cond=Q("gt",F("close"),R("delay",F("close"),1))
        a=B("div",R("sum",cond,60),C(60)); b=R("mean",cond,60)
        ca=vc.canonicalize(a,self.allowed); cb=vc.canonicalize(b,self.allowed)
        self.assertEqual(vc.rank_signature(ca)[0],vc.rank_signature(cb)[0])
    def test_positive_ratio_inverse(self):
        mean=R("mean",F("close"),20)
        a=B("div",F("close"),mean); b=B("div",mean,F("close"))
        ca=vc.canonicalize(a,self.allowed); cb=vc.canonicalize(b,self.allowed)
        ka,oa=vc.rank_signature(ca); kb,ob=vc.rank_signature(cb)
        self.assertEqual(ka,kb); self.assertEqual(oa,-ob)
    def test_unknown_feature_rejected(self):
        with self.assertRaises(vc.ValidationError): vc.canonicalize(F("inventory_ttm"),self.allowed)
    def test_negative_lag_rejected(self):
        with self.assertRaises(vc.ValidationError): vc.canonicalize(F("close",-1),self.allowed)
    def test_zero_mask_detected(self):
        x={"kind":"conditional","condition":Q("gt",F("close"),F("open")),"if_true":F("close"),"if_false":C(0)}
        self.assertTrue(vc.contains_zero_mask(vc.canonicalize(x,self.allowed)))
    def test_parameter_skeleton(self):
        a=vc.canonicalize(B("div",F("close"),R("mean",F("close"),20)),self.allowed)
        b=vc.canonicalize(B("div",F("close"),R("mean",F("close"),60)),self.allowed)
        self.assertEqual(vc.parameter_skeleton(a),vc.parameter_skeleton(b))

if __name__=="__main__": unittest.main()
