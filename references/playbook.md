# Factor generation playbook

## 1. Define the mining campaign

State the desired candidate count, target families, exclusions and intended holding/rebalance horizon. The horizon informs mechanism design but does not change the static validation contract.

## 2. Inspect the mother bank

Search the 549-factor snapshot for the intended mechanism, inputs and ranking exposure. Avoid rediscovering an existing factor through a different name, reciprocal, sign flip, monotonic wrapper or nearby parameter.

## 3. Propose mechanisms before formulas

For each idea write one sentence explaining why the signal may contain cross-sectional information and why the expected direction is plausible.

## 4. Prefer orthogonal hypotheses

Spread the batch across different economic mechanisms. Do not spend the batch budget on a parameter grid.

## 5. Translate into factors_lab AST

Use only the current contract. If the idea cannot be represented faithfully, discard it. Do not widen the contract during a mining run.

## 6. Check numerical robustness

Review denominators, logarithms, square roots, long lookbacks, missing-value sensitivity and conditionals. Reject fragile formulas before validation.

## 7. Static audit

Run `validate_candidates.py`. Replace rejected candidates with genuinely new mechanisms rather than cosmetic rewrites.

## 8. Hand off to factors_lab

The Skill stops after static acceptance. Empirical quality is determined later by the normal factors_lab pipeline.
