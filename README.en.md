# factors_lab Factor Mining Skill

This is an independent factor-mining Skill. It has no runtime dependency on factors_lab; the two projects only share the same import JSON and canonical AST contract.

Static duplicate screening uses the Skill's own `mother_bank/` directory. The initial 549-factor snapshot lives there, and human users may manually place later validated batch JSONs beside it. The validator automatically scans all JSON files in that directory except `MANIFEST.json`.

There is no automatic refresh, synchronization, or cross-project path dependency.

Validate a generated batch with:

```bash
python scripts/validate_candidates.py \
  --input generated_batch.json \
  --output ready_for_factors_lab.json \
  --report audit_report.json
```

The resulting JSON can be manually handed to factors_lab. See `HUMAN_GUIDE.zh-CN.md` for the local reference-library workflow.
