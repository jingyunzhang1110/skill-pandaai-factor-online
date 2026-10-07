# factors_lab expression contract

Snapshot source: `jingyunzhang1110/factors_lab`, `main` at commit `d55ed9ecc7bac9de9e472b5de103f485afdc10f0`.
Mother bank: 549 factors, next formal ID `0000000000000550` at snapshot time.

The bundled `mother_bank/clean_seed_factor_bank.json` is the authority for the existing factor universe. The AST rules below mirror `common_factor/src/factor_common/factor/ast.py` at the snapshot commit.

## Allowed numeric features

`adj_close`, `aggregate_book_value`, `aggregate_earnings`, `aggregate_market_cap`, `amount`, `avg_total_assets`, `basic_eps`, `benchmark_close`, `benchmark_open`, `book_equity`, `book_to_price`, `cap`, `capex`, `cfo`, `cfo_q`, `cfo_ttm`, `close`, `common_equity`, `dividend`, `dividend_1y`, `earnings`, `ebit`, `ebitda`, `enterprise_value`, `executive_compensation_top3`, `factor_return`, `float_cap_weighted_market_index`, `float_market_cap`, `float_shares`, `free_cash_flow`, `gross_profit`, `hd`, `high`, `holder_avgpct`, `illiq_3m`, `interest_bearing_debt`, `ld`, `long_term_debt`, `low`, `market_cap`, `mkt_freeshares`, `net_cash_flow`, `net_income`, `net_income_ex_nr`, `net_income_ex_nr_q`, `net_income_ex_nr_ttm`, `net_income_q`, `net_income_ttm`, `open`, `operating_profit_q`, `parent_equity_ex_minority`, `parent_net_income`, `parent_net_income_q`, `parent_net_income_ttm`, `preferred_equity`, `ret`, `returns`, `sales`, `sales_q`, `sales_ttm`, `self`, `sse_composite_close`, `stom_month`, `total_assets`, `total_debt`, `tr`, `turnover`, `volume`, `vwap`.

If the exact canonical feature is not listed here, it is not allowed by this Skill snapshot.

## Allowed group labels

`industry`, `sector`, `subindustry`.

Use these only as `group_neutralize.group`; do not treat them as numeric factor values.

## AST kinds and operators

### feature

```json
{"kind":"feature","name":"close","lag":0}
```

`lag` must be a non-negative integer.

### constant

Finite numeric value only.

### unary

`abs`, `neg`, `sign`, `log`, `exp`, `sqrt`, `rank`, `zscore`.

### binary

`add`, `sub`, `mul`, `div`, `pow`, `signed_power`, `max`, `min`.

`add`, `mul`, `max`, `min` are canonicalized as commutative operations.

### rolling

`mean`, `std`, `sum`, `product`, `min`, `max`, `rank`, `delta`, `delay`, `argmax`, `argmin`, `decay_linear`, `quantile`, `slope`, `rsquare`, `resi`, `sma`, `median`, `topk_mean`, `skew`.

`window` must be a positive integer. Optional `min_periods` must be in `[1, window]`.

Special parameters:

- `quantile`: parameter in `[0,1]`;
- `sma`: smoothing parameter in `(0, window]`;
- `topk_mean`: integer-like parameter in `[1, window]`;
- all other rolling operators: no parameter.

### pair_rolling

`corr`, `cov`; positive integer `window`; optional valid `min_periods`.

### comparison

`lt`, `le`, `gt`, `ge`, `eq`, `ne`.

### logical

`and`, `or`.

### conditional

`condition`, `if_true`, `if_false` children.

### scale

Positive finite `target`.

### group_neutralize

Operand plus one allowed group label.

### function

Supported operators and arities:

- `weighted_mean` — 2 operands, positive window;
- `regression_alpha` — 2 operands, positive window;
- `regression_beta` — 2 operands, positive window;
- `regression_resid_std` — 2 operands, positive window;
- `masked_regression_beta` — 3 operands, positive window;
- `multi_regression_residual` — 4 operands, positive window;
- `monthly_regression_alpha` — 2 operands, positive window;
- `monthly_beta_resid_product` — 2 operands, positive window;
- `previous_month_max` — 1 operand, no window/parameter;
- `exp_weighted_sum` — 1 operand, positive window and positive parameter;
- `exp_weighted_std` — 1 operand, positive window and positive parameter;
- `cmra` — 1 operand, positive window and positive parameter;
- `cumulative_range` — 1 operand, positive window;
- `wma` — 1 operand, positive window, parameter in `(0,1]`;
- `cross_section_long_short` — 2 operands, parameter in `(0,0.5]`;
- `cross_section_weighted_mean` — 2 operands, no window/parameter;
- `cross_section_median_ratio` — 2 operands, parameter in `(0,0.5]`.

## Refresh rule

When factors_lab changes its AST or mother bank, refresh this Skill before generating a new campaign. Never silently widen the contract during a mining run.
