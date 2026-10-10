# Factor generation playbook

## 1. Define the mining campaign

State the desired record count, target families, exclusions and intended holding/rebalance horizon. The horizon informs mechanism design but does not change the static AST contract.

## 2. Inspect the mother bank

Search the 549-factor (or refreshed) unique-factor snapshot for the intended mechanism, inputs and ranking exposure. Avoid rediscovering an existing factor through a different name, reciprocal, sign flip, monotonic wrapper or nearby parameter.

## 3. Propose mechanisms before formulas

For each idea state why the signal may contain cross-sectional information, the expected behavior, the horizon, required fields and principal failure mode.

## 4. Prefer orthogonal hypotheses

Spread the batch across genuinely different economic mechanisms. Do not spend the batch budget on a parameter grid.

Orthogonality must come from the hypothesis, not from formula inflation. Prefer one mechanism with one or two relationships over a formula that preprocesses four signals and combines them. Do not manufacture novelty by nesting rolling statistics, regressions, correlations and cross-sectional transforms. Multi-signal ensemble logic belongs in factors_lab multi_factor.

Before accepting a proposal, apply the complexity budget from `factors_lab_contract.md`: nodes <= 20, depth <= 8, <= 4 distinct input features, <= 3 rolling/pair_rolling/function nodes total, and <= 2 such nodes on any root-to-leaf path. Prefer materially simpler formulas even when both pass the hard ceiling.

## 5. Write the direct factors_lab import record

Use only `references/factors_lab_contract.md`. Fill provenance fields honestly. Never fabricate a paper/report/page reference for an LLM-originated hypothesis.

## 6. Check numerical robustness and computational simplicity

Review denominators, logarithms, square roots, long lookbacks, missing-value sensitivity, dimensional consistency and conditionals. Reject fragile formulas before validation.

Also reject unnecessary computational complexity. A candidate should have a short explanation that maps directly to its AST. If the explanation requires describing several independent sub-signals and then a combination rule, split the idea into simpler candidates or leave the combination to multi_factor.

## 7. Static audit

Run `validate_candidates.py`. Replace rejected records with genuinely new mechanisms rather than cosmetic rewrites.

## 8. Hand off without conversion

The validated output already has the exact `import-factors` schema. Pass it directly to factors_lab. Empirical quality is determined later by single_factor and multi_factor.
