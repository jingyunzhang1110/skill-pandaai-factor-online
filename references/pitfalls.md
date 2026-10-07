# Research pitfalls

## Future information

Never use forward returns, labels, future prices, negative lags, restated financial values before their effective publication date, or any field whose timestamp semantics are not point-in-time safe.

## Cross-sectional versus time-series semantics

`rank` and `zscore` are cross-sectional transforms; rolling `rank` is a time-series position. Do not swap them. A syntactically valid formula can still have the wrong economic meaning.

## Warm-up

Long windows reduce early coverage. State the longest lookback and never turn warm-up NaNs into zeros.

## Zero-mask conditionals

`IF(condition, signal, 0)` creates a large tied block at zero. That is not equivalent to excluding non-matching stocks. The Skill rejects this pattern by default.

## Dangerous denominators

Profit, cash flow, slopes, spreads and changes can cross zero. Ratios involving them can explode. A tiny hard-coded epsilon is not unit invariant and should not be used as a reflexive patch.

## Balance-sheet versus flow items

Assets, liabilities, equity and cash are point-in-time stocks. Revenue, profit and cash-flow statement items are period flows. Do not invent TTM sums for balance-sheet stocks.

## Redundant monotonic transforms

If downstream selection ranks stocks, `x`, `rank(x)`, `zscore(x)`, positive affine transforms and other monotonic wrappers often encode the same ordering. Do not count them as independent discoveries.

## Size and industry exposure

Value, liquidity, turnover and many fundamental ratios can be dominated by market cap or industry structure. Use `group_neutralize` only when the hypothesis calls for it and when the group field is point-in-time valid.

## Multiple testing

A winner found after hundreds of trials is weaker evidence than the same result from ten pre-specified trials. Keep a complete campaign ledger, including rejected and failed candidates.

## Turnover and implementation

High predictive correlation does not guarantee an investable signal. High-frequency or unstable signals can be dominated by trading frictions later in the factors_lab evaluation pipeline.

## Regime dependence

A factor dominated by one historical interval should not later be treated as universally valid. Stability must be assessed by the downstream evaluation system.
