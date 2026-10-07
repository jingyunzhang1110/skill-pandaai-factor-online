---
name: factors-lab-factor-mining
description: Generate novel A-share factor hypotheses and emit a JSON batch that can be passed directly to jingyunzhang1110/factors_lab common_factor import-factors. Use only the bundled factors_lab field/operator contract; reject unsupported AST, future information, exact/rank-equivalent duplicates, parameter-only variants, and structurally unsafe candidates before handoff.
---

# Factor Mining for factors_lab

This Skill has one output contract: **a validated factors_lab import batch JSON**.

The final JSON produced by this Skill must be directly usable as:

```powershell
python .\common_factor\top.py import-factors .\ready_for_factors_lab.json
```

No manual conversion is allowed between the Skill output and factors_lab.

Before generating a batch, read:

- `mother_bank/MANIFEST.json`
- `references/factors_lab_contract.md`
- `references/output_schema.md`
- `references/dedup_policy.md`
- `references/pitfalls.md`
- `references/playbook.md`
- `examples/new_factor_batch.example.json`

## Hard rules

1. The only authoritative formula representation is `canonical_expression` in the exact factors_lab AST schema.
2. Use only the feature names, AST kinds, operators and parameters explicitly listed in `references/factors_lab_contract.md`.
3. Never invent aliases, macros, technical-indicator names, vendor fields, report-specific field names or new operators.
4. Never use future labels, future prices, negative lags or data unavailable at the factor date.
5. Never write `factor_id`, `expression_fingerprint`, `duplicate_type`, `representation`, `parse_error` or `import_batch`. factors_lab owns those fields.
6. Output top-level JSON must be exactly `schema_version`, `batch_name`, `source`, `records`.
7. Each record must use only: `source_record_id`, `name`, `source`, `source_ref`, `formula_provenance`, `original_formula`, `economic_rationale`, `source_constraints`, `canonical_expression`.
8. Every `source_record_id` must be unique. Prefer `FM-YYYYMMDD-BATCH-####` or another batch-scoped globally unique pattern.
9. AST limits mirror factors_lab static audit: at most 64 nodes, depth at most 12, lookback at most 2520 trading days.
10. Reject exact duplicates against the mother bank and current batch.
11. Reject statically provable rank-equivalent duplicates. Reversing sign/direction does not create a new factor.
12. Reject parameter-only variants inside one mining batch. Do not spend a batch on nearby windows/constants.
13. Reject zero-mask conditionals such as `IF(condition, signal, 0)` or `IF(condition, 0, signal)`.
14. A denominator that can approach/cross zero must be redesigned or explicitly disclosed in `source_constraints`; never hide the problem with an arbitrary epsilon.
15. Do not approximate an unsupported idea with a different supported signal. Drop it.
16. A batch is not ready until `scripts/validate_candidates.py` accepts it.

## Required generation process

First define the economic mechanism, expected behavior, horizon, required fields and failure mode. Then build the AST from the allowed contract. Do not start from a fancy formula and invent a story afterward.

Generate the JSON directly in the schema shown in `examples/new_factor_batch.example.json`. `original_formula` is human-readable provenance; `canonical_expression` is the executable truth.

Validate every batch:

```bash
python scripts/validate_candidates.py \
  --input generated_batch.json \
  --output ready_for_factors_lab.json \
  --report audit_report.json
```

Only `ready_for_factors_lab.json` may be handed to factors_lab.

## Handoff boundary

The Skill stops after static mining validation. factors_lab then owns:

```text
ready_for_factors_lab.json
→ common_factor import-factors
→ append-only RAW shard
→ Factor Registry (factors.sqlite)
→ single_factor
→ accepted / empirical dedup
→ multi_factor
```

The Skill never allocates formal 16-digit IDs and never edits factors_lab RAW itself.
