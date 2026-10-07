# Factor generation playbook

## 1. Define the mining campaign

State the desired record count, target families, exclusions and intended holding/rebalance horizon. The horizon informs mechanism design but does not change the static AST contract.

## 2. Inspect the mother bank

Search the 549-factor (or refreshed) unique-factor snapshot for the intended mechanism, inputs and ranking exposure. Avoid rediscovering an existing factor through a different name, reciprocal, sign flip, monotonic wrapper or nearby parameter.

## 3. Propose mechanisms before formulas

For each idea state why the signal may contain cross-sectional information, the expected behavior, the horizon, required fields and principal failure mode.

## 4. Prefer orthogonal hypotheses

Spread the batch across genuinely different economic mechanisms. Do not spend the batch budget on a parameter grid.

## 5. Write the direct factors_lab import record

Use only `references/factors_lab_contract.md`. Fill provenance fields honestly. Never fabricate a paper/report/page reference for an LLM-originated hypothesis.

## 6. Check numerical robustness

Review denominators, logarithms, square roots, long lookbacks, missing-value sensitivity, dimensional consistency and conditionals. Reject fragile formulas before validation.

## 7. Static audit

Run `validate_candidates.py`. Replace rejected records with genuinely new mechanisms rather than cosmetic rewrites.

## 8. Hand off without conversion

The validated output already has the exact `import-factors` schema. Pass it directly to factors_lab. Empirical quality is determined later by single_factor and multi_factor.
