---
name: factors-lab-factor-mining
description: Generate novel A-share factor hypotheses that are strictly compatible with jingyunzhang1110/factors_lab, using only the bundled mother-bank feature/operator contract and rejecting exact, rank-equivalent, parameter-only, future-looking, or otherwise incompatible candidates before output.
---

# Factor Mining for factors_lab

This is a **pure factor-discovery skill**. It does not run external platform backtests, create remote factors, submit factors, or depend on a vendor-specific agent runtime.

Before generating any candidate, read:

- `mother_bank/MANIFEST.json`
- `references/factors_lab_contract.md`
- `references/dedup_policy.md`
- `references/pitfalls.md`
- `references/playbook.md`
- `references/output_schema.md`

## Hard rules

1. The authoritative formula representation is factors_lab `canonical_expression` AST.
2. Use only the exact allowed features, AST kinds and operators in the bundled contract.
3. Never invent aliases, macros, technical indicators or financial fields outside that contract.
4. Never use future labels, future prices, negative lags or information unavailable at the factor date.
5. Do not assign formal 16-digit factor IDs.
6. Run `scripts/validate_candidates.py` before presenting any candidate as valid.
7. Reject exact duplicates against the mother bank and the current batch.
8. Reject statically provable rank-equivalent duplicates. Direction metadata does not make the same exposure new.
9. Reject parameter-only variants within a generation batch by default. A mining batch should explore mechanisms, not a grid of nearby windows.
10. Reject zero-mask conditionals such as `IF(condition, signal, 0)` by default because they create large cross-sectional ties.
11. Prefer simple, interpretable expressions unless added complexity has an explicit economic purpose.
12. If a denominator can cross or approach zero, either redesign the factor or explicitly flag the numerical risk; do not hide it with an arbitrary epsilon.
13. Preserve failed/rejected candidates in the audit report rather than silently rewriting them into something else.

## Mining process

### 1. Inspect the mother bank

Search for the intended economic mechanism, not only formula text. A new name or algebraic rearrangement is not a new factor.

### 2. Design hypotheses before formulas

For each candidate define:

- family;
- economic or behavioral mechanism;
- expected direction;
- required fields;
- time horizon;
- main failure mode;
- why it is not already represented in the mother bank.

### 3. Preserve diversity

A batch should span genuinely different mechanisms where possible: momentum/reversal, volatility/distribution shape, liquidity/turnover, price-volume interaction, value, profitability/quality, cash-flow quality, growth, leverage, capital investment, event/benchmark-relative structure, and cross-sectional neutralized variants.

Do not fill a batch with many windows of the same formula.

### 4. Translate to canonical AST

Use only the exact contract. If an idea cannot be expressed without unsupported fields/operators, drop it rather than approximating it with a different signal.

### 5. Static audit

Run:

```bash
python scripts/validate_candidates.py --input candidate_batch.json \
  --output accepted_candidates.json --report audit_report.json
```

Only accepted candidates are valid outputs of this Skill.

### 6. Hand off

This Skill stops after static factor-generation audit. factors_lab owns factor ID allocation, factor-value computation, single-factor testing, empirical deduplication, final-test isolation and multi-factor selection.

## What counts as duplicate

The validator conservatively recognizes, among other cases:

- identical canonical AST;
- `x`, `rank(x)`, `zscore(x)` and positive scaling when they preserve the same ordering;
- sign-flipped versions as reverse-order equivalents;
- positive affine transforms;
- `log(x)` or `sqrt(x)` when positivity is provable;
- redundant `abs(x)` when non-negativity is provable;
- reciprocal positive ratios as reverse-order equivalents;
- `sum(condition,N)/N` versus `mean(condition,N)`;
- same batch structure differing only by windows/constants.

Static checks are intentionally conservative. The model must still perform economic-semantic deduplication.
