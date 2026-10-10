from __future__ import annotations
import importlib.util, json, sys, tempfile, unittest
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
        bank=vc.load_bank(ROOT/"mother_bank")
        payload=json.loads((ROOT/"examples"/"new_factor_batch.example.json").read_text(encoding="utf-8"))
        out,report=vc.validate_batch(payload,bank)
        self.assertEqual(report["accepted_count"],1,report)
        self.assertEqual(report["rejected_count"],0,report)
        self.assertEqual(set(out),{"schema_version","batch_name","source","records"})
        self.assertEqual(len(out["records"]),1)

    def test_lookback_over_250_rejected(self):
        bank={"factors":[]}
        payload={
            "schema_version":1,
            "batch_name":"lookback-limit-test",
            "source":"test",
            "records":[{
                "source_record_id":"TEST-LOOKBACK-251",
                "name":"too long lookback",
                "source":"test",
                "source_ref":"unit test",
                "formula_provenance":"unit test",
                "original_formula":"delay(close,251)",
                "economic_rationale":"verify hard lookback limit",
                "source_constraints":"",
                "canonical_expression":R("delay",F("close"),251)
            }]
        }
        out,report=vc.validate_batch(payload,bank)
        self.assertEqual(out["records"],[])
        self.assertEqual(report["rejected_count"],1)
        self.assertIn("lookback too long", str(report["findings"]))

    def test_excessive_statistical_nodes_rejected(self):
        bank={"factors":[]}
        x=B(
            "add",
            U("rank",R("mean",F("close"),5)),
            B(
                "add",
                U("rank",R("std",F("volume"),5)),
                B(
                    "add",
                    U("rank",R("mean",F("turnover"),5)),
                    U("rank",R("std",F("amount"),5)),
                ),
            ),
        )
        payload={
            "schema_version":1,
            "batch_name":"complexity-heavy-test",
            "source":"test",
            "records":[{
                "source_record_id":"TEST-COMPLEX-001",
                "name":"too many statistical nodes",
                "source":"test",
                "source_ref":"unit test",
                "formula_provenance":"unit test",
                "original_formula":"four rolling states",
                "economic_rationale":"verify statistical-node cap",
                "source_constraints":"",
                "canonical_expression":x,
            }]
        }
        out,report=vc.validate_batch(payload,bank)
        self.assertEqual(out["records"],[])
        self.assertEqual(report["rejected_count"],1)
        self.assertIn("too many rolling/pair_rolling/function nodes",str(report["findings"]))

    def test_excessive_statistical_nesting_rejected(self):
        bank={"factors":[]}
        x=R("mean",R("std",R("mean",F("close"),5),5),5)
        payload={
            "schema_version":1,
            "batch_name":"complexity-nesting-test",
            "source":"test",
            "records":[{
                "source_record_id":"TEST-COMPLEX-002",
                "name":"too much statistical nesting",
                "source":"test",
                "source_ref":"unit test",
                "formula_provenance":"unit test",
                "original_formula":"mean(std(mean(close)))",
                "economic_rationale":"verify statistical nesting cap",
                "source_constraints":"",
                "canonical_expression":x,
            }]
        }
        out,report=vc.validate_batch(payload,bank)
        self.assertEqual(out["records"],[])
        self.assertEqual(report["rejected_count"],1)
        self.assertIn("statistical nesting is too deep",str(report["findings"]))

    def test_too_many_distinct_features_rejected(self):
        bank={"factors":[]}
        xs=[U("rank",F(name)) for name in ("close","volume","turnover","amount","market_cap")]
        x=B("add",xs[0],B("add",xs[1],B("add",xs[2],B("add",xs[3],xs[4]))))
        payload={
            "schema_version":1,
            "batch_name":"complexity-feature-test",
            "source":"test",
            "records":[{
                "source_record_id":"TEST-COMPLEX-003",
                "name":"too many features",
                "source":"test",
                "source_ref":"unit test",
                "formula_provenance":"unit test",
                "original_formula":"five ranked inputs",
                "economic_rationale":"verify feature-count cap",
                "source_constraints":"",
                "canonical_expression":x,
            }]
        }
        out,report=vc.validate_batch(payload,bank)
        self.assertEqual(out["records"],[])
        self.assertEqual(report["rejected_count"],1)
        self.assertIn("too many distinct input features",str(report["findings"]))

    def test_long_factor_name_rejected(self):
        bank={"factors":[]}
        payload={
            "schema_version":1,
            "batch_name":"name-length-test",
            "source":"test",
            "records":[{
                "source_record_id":"TEST-NAME-001",
                "name":"x"*41,
                "source":"test",
                "source_ref":"unit test",
                "formula_provenance":"unit test",
                "original_formula":"close",
                "economic_rationale":"verify concise-name cap",
                "source_constraints":"",
                "canonical_expression":F("close"),
            }]
        }
        out,report=vc.validate_batch(payload,bank)
        self.assertEqual(out["records"],[])
        self.assertEqual(report["rejected_count"],1)
        self.assertIn("name too long",str(report["findings"]))

    def test_future_like_feature_name_rejected(self):
        with self.assertRaises(vc.ValidationError):
            vc.canonicalize(F("next_close"),self.allowed)

    def test_local_mother_bank_directory_reads_added_record_files(self):
        expression=B("div",R("mean",F("turnover"),19),R("mean",F("turnover"),73))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/"base.json").write_text(
                json.dumps({"factors":[]}), encoding="utf-8"
            )
            (root/"added_001.json").write_text(
                json.dumps({
                    "schema_version":1,
                    "batch_name":"added",
                    "source":"test",
                    "records":[{
                        "source_record_id":"ADDED-001",
                        "name":"known turnover ratio",
                        "canonical_expression":expression
                    }]
                }),
                encoding="utf-8",
            )
            (root/"MANIFEST.json").write_text(
                json.dumps({"schema_version":1}), encoding="utf-8"
            )
            bank=vc.load_bank(root)
            self.assertEqual(bank["reference_file_count"],2)
            self.assertEqual(len(bank["factors"]),1)

            payload={
                "schema_version":1,
                "batch_name":"candidate",
                "source":"test",
                "records":[{
                    "source_record_id":"NEW-001",
                    "name":"duplicate turnover ratio",
                    "source":"test",
                    "source_ref":"unit test",
                    "formula_provenance":"unit test",
                    "original_formula":"mean(turnover,19)/mean(turnover,73)",
                    "economic_rationale":"unit test duplicate",
                    "source_constraints":"",
                    "canonical_expression":expression
                }]
            }
            out,report=vc.validate_batch(payload,bank)
            self.assertEqual(out["records"],[])
            self.assertEqual(report["rejected_count"],1)
            self.assertIn("added_001.json", str(report["findings"]))

if __name__=="__main__":
    unittest.main()
