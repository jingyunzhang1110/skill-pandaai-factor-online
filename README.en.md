# factors_lab Factor Mining Skill

A pure factor-mining skill for `jingyunzhang1110/factors_lab`.

It has one job: generate new A-share factor hypotheses that are valid in the factors_lab canonical AST and reject incompatible or redundant candidates before they reach the research pipeline.

It does not run external backtests, submit factors to third-party platforms, or depend on a specific AI runtime.

Core guarantees:

- bundled snapshot of the current 549-factor mother bank;
- only factors_lab-supported features, AST kinds and operators are allowed;
- negative lags, future-looking inputs, invalid constants and invalid windows are rejected;
- exact AST duplicates, statically provable rank-equivalent duplicates, within-batch duplicates and parameter-only batch variants are screened;
- zero-mask conditionals such as `IF(condition, signal, 0)` are rejected by default;
- formal 16-digit factor IDs are never assigned here.

Validate every batch with:

```bash
python scripts/validate_candidates.py \
  --input candidate_batch.json \
  --output accepted_candidates.json \
  --report audit_report.json
```

Only accepted candidates should be passed to factors_lab for actual value computation and evaluation.
