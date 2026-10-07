---
name: factors-lab-factor-mining
description: Generate new A-share factor hypotheses and emit JSON directly compatible with factors_lab common_factor import-factors. The Skill and factors_lab are independent projects that only share a JSON/AST contract. Static dedup uses only local reference JSONs stored under this Skill's mother_bank/ directory.
---

# Factor Mining for factors_lab

This Skill and factors_lab are independent projects. They never call each other, read each other's directories, or auto-sync data. Their only interface is the shared import JSON and canonical AST contract.

Before mining, read the contract/reference files and treat every JSON in `mother_bank/` except `MANIFEST.json` as already-known factor reference material.

The bundled `mother_bank/clean_seed_factor_bank.json` contains the initial 549-factor snapshot. Human users may later place additional validated factor batch JSONs in the same `mother_bank/` directory. The validator scans them automatically. See `HUMAN_GUIDE.zh-CN.md`.

Hard rules:

1. `canonical_expression` is authoritative.
2. Use only the exact allowed fields, AST kinds, operators and parameters in `references/factors_lab_contract.md`.
3. Never invent fields, aliases, macros, indicators or operators.
4. Never use future information or negative lags.
5. Never emit factors_lab-owned identity fields such as `factor_id` or fingerprints.
6. Output must use exactly the direct import schema documented in `references/output_schema.md`.
7. Reject exact/rank-equivalent duplicates against all local `mother_bank/` references and the current batch.
8. Reject parameter-only variants and zero-mask conditionals.
9. Respect AST limits: nodes <= 64, depth <= 12, lookback <= 2520.
10. Validate before handoff.

Validate:

```bash
python scripts/validate_candidates.py \
  --input generated_batch.json \
  --output ready_for_factors_lab.json \
  --report audit_report.json
```

The output can then be manually copied to factors_lab and imported with its own `import-factors` command. The Skill never accesses factors_lab RAW or Registry state.
