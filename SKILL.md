---
name: factors-lab-pandaai-factor-source
description: Generate A-share factor hypotheses in the exact canonical AST used by jingyunzhang1110/factors_lab, reject mother-bank and within-batch duplicates, and optionally export a safe subset for PandaAI online diagnostics.
---

# Factor Mining for factors_lab

This skill is **factors_lab-first**. PandaAI is optional secondary validation.

Before generating factors, read `mother_bank/MANIFEST.json`, `references/factors_lab_contract.md`, `references/dedup_policy.md`, `references/pitfalls.md`, `references/playbook.md`, and `references/output_schema.md`. If PandaAI execution is requested, also read `references/pandaai_online.md`.

Hard rules:

1. Emit factors_lab `canonical_expression` AST as the authoritative formula representation.
2. Use only allowed factors_lab features, AST kinds and operators in the bundled contract.
3. Never use future labels or negative lags.
4. Never invent PandaAI-only macros or unsupported technical indicators. Expand an idea into supported AST nodes or drop it.
5. Run `scripts/validate_candidates.py` before presenting candidates as valid.
6. Reject exact duplicates and rank-equivalent duplicates against the bundled 549-factor mother bank and the current batch.
7. Reject parameter-only variants inside a batch by default; preserve mechanism diversity.
8. Reject zero-mask conditionals such as `IF(condition, signal, 0)` by default because they create large cross-sectional ties.
9. Direction metadata does not make the same underlying exposure a new factor.
10. Do not assign formal 16-digit factor IDs; factors_lab owns ID allocation.

Useful rank-equivalence examples include positive affine transforms, sign flips, rank/zscore wrappers, log of a provably positive signal, reciprocal of a provably positive ratio, redundant ABS on positive price ratios, and `SUM(condition,N)/N` versus `MEAN(condition,N)`.

Generate hypothesis-led candidates across distinct families rather than hundreds of nearby parameter variants. Explain each candidate's economic mechanism and denominator risk.

Required validation:

```bash
python scripts/validate_candidates.py --input candidate_batch.json \
  --output accepted_candidates.json --report audit_report.json
```

For optional PandaAI diagnostics, convert only losslessly renderable candidates:

```bash
python scripts/export_pandaai_manifest.py --input accepted_candidates.json \
  --output pandaai_candidates.txt --report pandaai_export_report.json
```

Then `scripts/batch.py` may be used with the generated manifest. Authentication is always performed interactively by the user with `pandaai-cli login`; never request or store credentials.

See `SKILL.zh-CN.md` for the full operating contract.
