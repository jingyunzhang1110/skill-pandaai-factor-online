# Deduplication policy

The purpose is to prevent the factor source from flooding factors_lab with aliases of existing exposures.

## Level 1: canonical exact duplicate

Canonicalize the AST exactly as factors_lab does, then SHA-256 the compact sorted JSON. Same canonical AST means one factor regardless of name or prose.

## Level 2: rank-equivalent duplicate

For cross-sectional selection, two formulas are duplicates when one is a statically provable strictly monotonic transform of the other, including reversed ordering.

The validator conservatively recognizes cases such as:

- `x`, `rank(x)`, `zscore(x)`, positive `scale(x)`;
- `x` and `a*x+b` for non-zero constant `a`;
- `x` and `-x`;
- `x` and `log(x)` / `sqrt(x)` when positivity is provable;
- redundant `abs(x)` when non-negativity is provable;
- positive ratio `x/y` versus `y/x`;
- `sum(condition,N)/N` versus `mean(condition,N)`;
- additive/subtractive constants around an otherwise identical signal.

Changing the name, narrative, sign convention or expected direction does not turn the same ranking exposure into a new factor.

## Level 3: parameter-only within-batch duplicate

Within one generated batch, formulas with the same features/operators/tree shape and only different windows or numeric constants are rejected after the first occurrence.

This is a mining-diversity rule, not a claim that every parameter choice produces identical values. Parameter sensitivity belongs in a separate study, not in blind factor discovery.

## Near variants against the mother bank

A candidate may share a structural skeleton with an existing mother-bank factor but use different parameters. The validator records this as a warning rather than an automatic duplicate unless exact/rank equivalence can be proved. The model should keep it only when the mechanism-level justification is genuinely distinct.

## Economic-semantic dedup still matters

Static code cannot prove every equivalence. The model must also reject formulas that merely restate the same idea through cosmetic algebra, redundant normalizations or interchangeable proxies.
