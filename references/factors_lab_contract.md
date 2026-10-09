# factors_lab 字段与 AST 契约

本文件是 Skill 生成公式时的**硬约束**。快照目标为 `jingyunzhang1110/factors_lab` main，兼容 append-only RAW / `import-factors` 链路（基准提交 `9d64d0ac516af464c6ad5b3648565fe3e7f96253`）。

即使 factors_lab 底层以后能读到更多原始列，本 Skill 也不得自行扩大白名单。新增字段/算子必须先同步更新 factors_lab 与本契约。

## 1. 允许作为数值输入的字段

仅允许以下字段：

```text
adj_close
aggregate_book_value
aggregate_earnings
aggregate_market_cap
amount
avg_total_assets
basic_eps
benchmark_close
benchmark_open
book_equity
book_to_price
cap
capex
cfo
cfo_q
cfo_ttm
close
common_equity
dividend
dividend_1y
earnings
ebit
ebitda
enterprise_value
executive_compensation_top3
factor_return
float_cap_weighted_market_index
float_market_cap
float_shares
free_cash_flow
gross_profit
hd
high
holder_avgpct
illiq_3m
interest_bearing_debt
ld
long_term_debt
low
market_cap
mkt_freeshares
net_cash_flow
net_income
net_income_ex_nr
net_income_ex_nr_q
net_income_ex_nr_ttm
net_income_q
net_income_ttm
open
operating_profit_q
operating_profit_ttm
parent_equity_ex_minority
parent_net_income
parent_net_income_q
parent_net_income_ttm
preferred_equity
ret
returns
sales
sales_q
sales_ttm
self
sse_composite_close
stom_month
total_assets
total_debt
tr
turnover
volume
vwap
```

`industry`、`sector`、`subindustry` **不是数值输入字段**，只能作为 `group_neutralize.group`。

禁止使用任何不在上述表内的名字，例如 `future_return`、`next_open`、`inventory_ttm`、`RSI`、`MACD`、`ADV20` 等，除非未来先正式加入契约。

## 2. 通用 AST 规则

- 每个节点必须是 JSON object。
- 每个节点必须有准确的 `kind`。
- 不允许附加未定义 key。
- 常数必须是有限数字，不能是 NaN/Infinity。
- `lag` 必须为非负整数。
- 最大节点数 64。
- 最大树深度 12。
- 最大 lookback **250 个交易日**。这是硬上限：必须按完整 AST 的累计历史依赖计算；任何嵌套 rolling / delay / regression / monthly function 等导致总 lookback > 250 的候选因子都禁止生成、禁止通过验证。
- 禁止任何 future/forward/next/label/target 类字段。
- JSON 中不要写注释。

## 3. AST 节点规范

### feature

```json
{"kind":"feature","name":"close","lag":0}
```

只允许 key：`kind,name,lag`。lag ≥ 0。

### constant

```json
{"kind":"constant","value":1}
```

只允许有限数值。

### unary

```json
{"kind":"unary","operator":"rank","operand":{...}}
```

允许 operator：

`abs, neg, sign, log, exp, sqrt, rank, zscore`

### binary

```json
{"kind":"binary","operator":"div","left":{...},"right":{...}}
```

允许 operator：

`add, sub, mul, div, pow, signed_power, max, min`

`add/mul/max/min` 会被 canonicalize 为交换律统一顺序。

### rolling

```json
{
  "kind":"rolling",
  "operator":"mean",
  "operand":{...},
  "window":20
}
```

允许 operator：

`mean, std, sum, product, min, max, rank, delta, delay, argmax, argmin, decay_linear, quantile, slope, rsquare, resi, sma, median, topk_mean, skew`

规则：

- `window`：正整数。
- 可选 `min_periods`：整数且 1 ≤ min_periods ≤ window。
- `quantile`：必须有 `parameter`，0 ≤ parameter ≤ 1。
- `sma`：必须有 `parameter`，0 < parameter ≤ window。
- `topk_mean`：必须有整数型 `parameter`，1 ≤ parameter ≤ window。
- 其他 rolling operator 禁止 parameter。

### pair_rolling

```json
{
  "kind":"pair_rolling",
  "operator":"corr",
  "left":{...},
  "right":{...},
  "window":20
}
```

operator 仅允许 `corr,cov`；window 为正整数；可选合法 `min_periods`。

### comparison

```json
{"kind":"comparison","operator":"gt","left":{...},"right":{...}}
```

operator：`lt, le, gt, ge, eq, ne`。

### logical

```json
{"kind":"logical","operator":"and","left":{...},"right":{...}}
```

operator：`and, or`。

### conditional

```json
{
  "kind":"conditional",
  "condition":{...},
  "if_true":{...},
  "if_false":{...}
}
```

两个输出分支在 factors_lab 可推断维度时必须维度一致。Skill 默认禁止一边为信号、一边为字面量 0 的 zero-mask 条件式。

### scale

```json
{"kind":"scale","operand":{...},"target":1.0}
```

target 必须有限且 > 0。

### group_neutralize

```json
{"kind":"group_neutralize","operand":{...},"group":"industry"}
```

group 仅允许：`industry, sector, subindustry`。

### function

统一形状：

```json
{
  "kind":"function",
  "operator":"weighted_mean",
  "operands":[{...},{...}],
  "window":20
}
```

精确签名：

| operator | operands 数量 | window | parameter |
|---|---:|---|---|
| weighted_mean | 2 | 正整数 | 禁止 |
| regression_alpha | 2 | 正整数 | 禁止 |
| regression_beta | 2 | 正整数 | 禁止 |
| regression_resid_std | 2 | 正整数 | 禁止 |
| masked_regression_beta | 3 | 正整数 | 禁止 |
| multi_regression_residual | 4 | 正整数 | 禁止 |
| monthly_regression_alpha | 2 | 正整数 | 禁止 |
| monthly_beta_resid_product | 2 | 正整数 | 禁止 |
| previous_month_max | 1 | 禁止 | 禁止 |
| exp_weighted_sum | 1 | 正整数 | > 0 |
| exp_weighted_std | 1 | 正整数 | > 0 |
| cmra | 1 | 正整数 | > 0 |
| cumulative_range | 1 | 正整数 | 禁止 |
| wma | 1 | 正整数 | 0 < parameter ≤ 1 |
| cross_section_long_short | 2 | 禁止 | 0 < parameter ≤ 0.5 |
| cross_section_weighted_mean | 2 | 禁止 | 禁止 |
| cross_section_median_ratio | 2 | 禁止 | 0 < parameter ≤ 0.5 |

## 4. 维度约束

factors_lab 对已知物理维度做静态检查。尤其注意：

- 价格不能直接和成交量相加/相减。
- `add/sub/max/min` 的两边在维度已知时必须一致。
- `log/exp` 对已知维度输入要求无量纲。
- 有量纲数据使用 `pow` 时，指数必须是整数常数。
- conditional 两个结果分支在维度已知时必须一致。

推荐优先使用比值、收益率、rank/zscore 等无量纲结构，避免无经济意义的量纲混合。

## 5. canonical_expression 示例

20 日/250 日换手率比：

```json
{
  "kind": "binary",
  "operator": "div",
  "left": {
    "kind": "rolling",
    "operator": "mean",
    "operand": {"kind": "feature", "name": "turnover", "lag": 0},
    "window": 20
  },
  "right": {
    "kind": "rolling",
    "operator": "mean",
    "operand": {"kind": "feature", "name": "turnover", "lag": 0},
    "window": 250
  }
}
```

如果无法只用本文件的字段和 AST 原样表达一个想法，直接拒绝该想法。
