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
        self.allowed=set(vc.ALLOWED_FEATURES)

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
        with self.assertRaises(vc.ValidationError):
            vc.canonicalize(F("inventory_ttm"),self.allowed)

    def test_negative_lag_rejected(self):
        with self.assertRaises(vc.ValidationError):
            vc.canonicalize(F("close",-1),self.allowed)

    def test_unknown_ast_key_rejected(self):
        node={"kind":"feature","name":"close","lag":0,"magic":1}
        with self.assertRaises(vc.ValidationError):
            vc.canonicalize(node,self.allowed)

    def test_zero_mask_detected(self):
        x={"kind":"conditional","condition":Q("gt",F("close"),F("open")),"if_true":F("close"),"if_false":C(0)}
        self.assertTrue(vc.contains_zero_mask(vc.canonicalize(x,self.allowed)))

    def test_parameter_skeleton(self):
        a=vc.canonicalize(B("div",F("close"),R("mean",F("close"),20)),self.allowed)
        b=vc.canonicalize(B("div",F("close"),R("mean",F("close"),60)),self.allowed)
        self.assertEqual(vc.parameter_skeleton(a),vc.parameter_skeleton(b))

    def test_dimension_mismatch_rejected(self):
        x=vc.canonicalize(B("add",F("close"),F("volume")),self.allowed)
        with self.assertRaises(vc.ValidationError):
            vc.validate_dimension(x)

    def test_output_schema_is_direct_import_schema(self):
        bank={"factors":[]}
        payload={
            "schema_version":1,
            "batch_name":"unit-test",
            "source":"test",
            "records":[{
                "source_record_id":"TEST-UNIQUE-001",
                "name":"turnover ratio",
                "source":"test",
                "source_ref":"unit test",
                "formula_provenance":"unit test",
                "original_formula":"mean(turnover,17)/mean(turnover,61)",
                "economic_rationale":"activity acceleration",
                "source_constraints":"",
                "canonical_expression":B("div",R("mean",F("turnover"),17),R("mean",F("turnover"),61))
            }]
        }
        out,report=vc.validate_batch(payload,bank)
        self.assertEqual(set(out),{"schema_version","batch_name","source","records"})
        self.assertEqual(len(out["records"]),1)
        self.assertNotIn("factor_id",out["records"][0])
        self.assertEqual(report["accepted_count"],1)

    def test_program_owned_field_rejected(self):
        bank={"factors":[]}
        payload={
            "schema_version":1,"batch_name":"unit-test","source":"test",
            "records":[{
                "source_record_id":"TEST-002","name":"bad","original_formula":"close",
                "economic_rationale":"bad","factor_id":"0000000000000550",
                "canonical_expression":F("close")
            }]
        }
        out,report=vc.validate_batch(payload,bank)
        self.assertEqual(out["records"],[])
        self.assertEqual(report["rejected_count"],1)

    def test_bundled_example_is_directly_accepted(self):
        import json
        bank=vc.load_bank(ROOT/"mother_bank"/"clean_seed_factor_bank.json")
        payload=json.loads((ROOT/"examples"/"new_factor_batch.example.json").read_text(encoding="utf-8"))
        out,report=vc.validate_batch(payload,bank)
        self.assertEqual(report["accepted_count"],1,report)
        self.assertEqual(report["rejected_count"],0,report)
        self.assertEqual(set(out),{"schema_version","batch_name","source","records"})
        self.assertEqual(len(out["records"]),1)

    def test_future_like_feature_name_rejected(self):
        with self.assertRaises(vc.ValidationError):
            vc.canonicalize(F("next_close"),self.allowed)

if __name__=="__main__":
    unittest.main()
