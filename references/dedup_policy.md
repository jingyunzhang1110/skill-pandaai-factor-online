# Deduplication policy

The purpose is to prevent the factor source from flooding factors_lab with aliases of existing exposures.

## Level 1: canonical exact duplicate

Canonicalize the AST exactly as factors_lab does, then SHA-256 the compact sorted JSON. Same canonical AST means one factor, regardless of name, direction or prose.

## Level 2: rank-equivalent duplicate

For cross-sectional selection, two formulas are duplicates when one is a statically provable strictly monotonic transform of the other (same or reversed ordering).

The validator recognizes conservative cases including:

- `x`, `rank(x)`, `zscore(x)`, positive `scale(x)`;
- `x` and `a*x+b` for non-zero constant `a`;
- `x` and `-x` as reverse-order equivalents;
- `x` and `log(x)` / `sqrt(x)` when positivity can be proved;
- redundant `abs(x)` when non-negativity can be proved;
- positive ratio `x/y` versus `y/x` as reverse-order equivalents;
- `sum(condition,N)/N` versus `mean(condition,N)`;
- additive/subtractive constants around an otherwise identical signal.

Direction metadata does not rescue a duplicate. If two formulas are the same exposure and one says lower-is-better while the other says higher-is-better, they remain one underlying factor hypothesis.

## Level 3: parameter-only within-batch duplicate

Within one generated batch, formulas that have the same features/operators/tree shape and differ only in windows or numeric constants are rejected after the first occurrence by default.

This is a diversity rule, not a claim that every window produces identical values. A later dedicated parameter-sensitivity study may explicitly allow variants, but blind candidate generation should not spend its budget on them.

## Near variants against the mother bank

A candidate may share a structural skeleton with an existing mother-bank factor but use different parameters. The validator records this as a warning rather than an automatic duplicate unless exact/rank equivalence can be proved. The AI should require a clear mechanism-level justification before keeping such a candidate.

## Economic-semantic dedup still matters

Static code cannot prove every equivalence. The AI must also reject formulas that merely restate the same idea with cosmetic algebra, redundant normalizations, or interchangeable proxies.
