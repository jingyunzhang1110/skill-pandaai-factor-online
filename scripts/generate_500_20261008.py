#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_candidates.py"

spec = importlib.util.spec_from_file_location("vc", VALIDATOR_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load validator: {VALIDATOR_PATH}")
vc = importlib.util.module_from_spec(spec)
sys.modules["vc"] = vc
spec.loader.exec_module(vc)

BATCH_NAME = "fm_20261008_500_v1"
SOURCE = "factor-mining-skill"
TARGET = 500
MAX_PER_FAMILY = 12

ROOT_OUTPUT = ROOT / "ready_for_factors_lab_20261008_500.json"
MOTHER_COPY = ROOT / "mother_bank" / "added_20261008_500.json"
AUDIT_OUTPUT = ROOT / "audit_20261008_500.json"
SELECTION_OUTPUT = ROOT / "campaign_20261008_500_selection.json"

PRICE = ["close", "open", "high", "low", "vwap", "adj_close"]
PRICE_CORE = ["close", "open", "high", "low", "vwap"]
BENCH = ["benchmark_close", "sse_composite_close", "float_cap_weighted_market_index"]
ACTIVITY = ["turnover", "volume", "amount", "illiq_3m", "stom_month", "float_shares", "mkt_freeshares"]
SIZE = [
    "market_cap", "float_market_cap", "cap", "total_assets", "avg_total_assets",
    "book_equity", "common_equity", "parent_equity_ex_minority", "total_debt",
    "interest_bearing_debt", "long_term_debt", "enterprise_value",
]
FLOW = [
    "sales_ttm", "earnings", "net_income_ttm", "parent_net_income_ttm",
    "operating_profit_ttm", "cfo_ttm", "free_cash_flow", "gross_profit",
    "ebit", "ebitda", "net_cash_flow", "capex", "dividend_1y",
    "net_income_ex_nr_ttm",
]
QUARTER = [
    "sales_q", "net_income_q", "parent_net_income_q", "operating_profit_q",
    "cfo_q", "net_income_ex_nr_q",
]
OTHER = [
    "basic_eps", "holder_avgpct", "executive_compensation_top3",
    "aggregate_earnings", "aggregate_book_value", "aggregate_market_cap",
    "dividend", "preferred_equity", "book_to_price",
]
RET = ["returns", "ret", "factor_return"]
TS_FIELDS = list(dict.fromkeys(PRICE + BENCH + ACTIVITY + FLOW + QUARTER + OTHER + RET + SIZE))
FUNDAMENTAL = set(FLOW + QUARTER + SIZE + OTHER + [
    "sales", "earnings", "net_income", "parent_net_income", "cfo",
    "net_income_ex_nr", "operating_profit_q", "operating_profit_ttm",
])


def F(name: str, lag: int = 0) -> dict[str, Any]:
    return {"kind": "feature", "name": name, "lag": lag}


def C(value: float) -> dict[str, Any]:
    return {"kind": "constant", "value": value}


def U(op: str, x: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "unary", "operator": op, "operand": x}


def B(op: str, a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "binary", "operator": op, "left": a, "right": b}


def R(op: str, x: dict[str, Any], window: int, parameter: float | int | None = None) -> dict[str, Any]:
    out = {"kind": "rolling", "operator": op, "operand": x, "window": window}
    if parameter is not None:
        out["parameter"] = parameter
    return out


def PR(op: str, a: dict[str, Any], b: dict[str, Any], window: int) -> dict[str, Any]:
    return {"kind": "pair_rolling", "operator": op, "left": a, "right": b, "window": window}


def Q(op: str, a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "comparison", "operator": op, "left": a, "right": b}


def COND(condition: dict[str, Any], a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "conditional", "condition": condition, "if_true": a, "if_false": b}


def GN(x: dict[str, Any], group: str) -> dict[str, Any]:
    return {"kind": "group_neutralize", "operand": x, "group": group}


def FN(op: str, operands: list[dict[str, Any]], window: int | None = None, parameter: float | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"kind": "function", "operator": op, "operands": operands}
    if window is not None:
        out["window"] = window
    if parameter is not None:
        out["parameter"] = parameter
    return out


def RK(x: dict[str, Any]) -> dict[str, Any]:
    return U("rank", x)


def ZS(x: dict[str, Any]) -> dict[str, Any]:
    return U("zscore", x)


def spread(a: str, b: str) -> dict[str, Any]:
    return B("sub", RK(F(a)), RK(F(b)))


def rank_roll(op: str, field: str, window: int, parameter: float | int | None = None) -> dict[str, Any]:
    return RK(R(op, F(field), window, parameter))


def window_for(i: int, offset: int = 0) -> int:
    windows = [5, 10, 20, 30, 40, 60, 90, 120, 180, 250]
    return windows[(i + offset) % len(windows)]


def pairs(a: list[str], b: list[str], limit: int = 40) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for i, x in enumerate(a):
        for j, y in enumerate(b):
            if x == y:
                continue
            item = (x, y)
            if item in seen:
                continue
            seen.add(item)
            out.append(item)
            if len(out) >= limit:
                return out
    return out


def quads(a: list[str], b: list[str], c: list[str], d: list[str], limit: int = 40) -> list[tuple[str, str, str, str]]:
    out: list[tuple[str, str, str, str]] = []
    seen = set()
    for i in range(max(len(a), len(b), len(c), len(d)) * 6):
        item = (
            a[i % len(a)],
            b[(i * 3 + 1) % len(b)],
            c[(i * 5 + 2) % len(c)],
            d[(i * 7 + 3) % len(d)],
        )
        if len(set(item)) < 3 or item in seen:
            continue
        seen.add(item)
        out.append(item)
        if len(out) >= limit:
            break
    return out


@dataclass(frozen=True)
class Proposal:
    key: str
    family: str
    family_label: str
    name: str
    expr: dict[str, Any]
    rationale: str
    constraints: str


PROPOSALS: list[Proposal] = []
_family_counts: dict[str, int] = defaultdict(int)


def constraints_for(fields: Iterable[str], extra: str = "") -> str:
    fields = set(fields)
    bits = ["仅使用当期及历史数据；滚动项需要预热，预热 NaN 不得填零。"]
    if fields & FUNDAMENTAL:
        bits.append("财务字段依赖 factors_lab 的 PIT 可得时点，低频披露可能形成阶梯型序列。")
    if extra:
        bits.append(extra)
    return "".join(bits)


def add(family: str, label: str, expr: dict[str, Any], fields: Iterable[str], rationale: str, extra: str = "") -> None:
    idx = _family_counts[family] + 1
    _family_counts[family] = idx
    field_text = "-".join(list(fields)[:4])
    key = f"{family}-{idx:03d}"
    name = f"{label}-{field_text}-{idx:02d}"
    PROPOSALS.append(Proposal(
        key=key,
        family=family,
        family_label=label,
        name=name,
        expr=expr,
        rationale=rationale,
        constraints=constraints_for(fields, extra),
    ))


# 01-12: cross-sectional relation / interaction
for a, b in pairs(FLOW, SIZE):
    add("F01", "盈利规模相对强度", spread(a, b), [a, b],
        "盈利或现金流在横截面上相对资本规模更强，可能代表更高的资本使用效率与更可持续的盈利质量。")

for a, b in pairs(FLOW, FLOW):
    add("F02", "经营流质量差", spread(a, b), [a, b],
        "不同利润与现金流口径之间的横截面相对强弱可刻画应计质量、现金兑现和利润结构差异。")

for a, b in pairs(SIZE, SIZE):
    add("F03", "资产负债结构差", spread(a, b), [a, b],
        "资产、权益、债务或企业价值之间的相对排序反映资本结构与资产负担差异。")

for a, b in pairs(ACTIVITY, ACTIVITY):
    add("F04", "交易活跃结构差", spread(a, b), [a, b],
        "不同交易活跃度、成交规模与流动性代理的横截面差异可识别拥挤、关注度和流动性结构。")

for a, b in pairs(OTHER, SIZE):
    add("F05", "另类基本面规模差", spread(a, b), [a, b],
        "每股、股东、薪酬或聚合基本面相对企业规模的横截面位置可提供传统估值之外的信息。")

for a, b in pairs(FLOW, SIZE):
    add("F06", "基本面错配幅度", U("abs", spread(a, b)), [a, b],
        "盈利能力与资本规模排序的绝对错配刻画异常配置或结构性偏离，而非简单方向暴露。")

for a, b in pairs(FLOW, SIZE):
    add("F07", "双维优势上界", B("max", RK(F(a)), RK(F(b))), [a, b],
        "两个维度中更强的一端代表至少一项显著优势，刻画单侧极强特征驱动的横截面差异。")

for a, b in pairs(FLOW, SIZE):
    add("F08", "双维短板下界", B("min", RK(F(a)), RK(F(b))), [a, b],
        "两个维度中较弱的一端作为瓶颈，刻画同时满足质量与规模结构要求的保守型信号。")

for a, b in pairs(FLOW, SIZE):
    add("F09", "质量规模交互", B("mul", B("sub", RK(F(a)), C(0.5)), B("sub", RK(F(b)), C(0.5))), [a, b],
        "去中心后的质量与规模排序相乘，区分同向强化和相互抵消的横截面状态。")

for a, b in pairs(PRICE, ACTIVITY):
    add("F10", "价格活跃交互", B("mul", B("sub", RK(F(a)), C(0.5)), B("sub", RK(F(b)), C(0.5))), [a, b],
        "价格位置与交易活跃度的联合状态可区分有成交确认的价格强弱与缺乏成交支持的偏离。")

for a, b, c, d in quads(FLOW, SIZE, ACTIVITY, PRICE):
    e1 = B("sub", RK(F(a)), RK(F(b)))
    e2 = B("sub", RK(F(c)), RK(F(d)))
    add("F11", "四维错配交互", B("mul", e1, e2), [a, b, c, d],
        "基本面-规模错配与交易-价格错配的交互可捕捉只有两个机制同时出现时才显现的横截面效应。")

for a, b, c, d in quads(FLOW, SIZE, FLOW[::-1], SIZE[::-1]):
    e1 = B("sub", RK(F(a)), RK(F(b)))
    e2 = B("sub", RK(F(c)), RK(F(d)))
    add("F12", "双质量价值合成", B("add", e1, e2), [a, b, c, d],
        "两条不同的基本面相对规模轴做加性合成，要求多个基本面维度共同支持价值或质量判断。")


# 13-24: time-series shape and persistence
for i, (a, b) in enumerate(pairs(ACTIVITY, RET + PRICE, 45)):
    w = window_for(i)
    add("F13", "均值状态差", B("sub", rank_roll("mean", a, w), rank_roll("mean", b, w)), [a, b],
        "比较两个不同维度近期均值状态的横截面排序，刻画交易环境与价格/收益状态的不一致。")

for i, (a, b) in enumerate(pairs(ACTIVITY, RET + PRICE, 45)):
    w = window_for(i, 1)
    add("F14", "波动状态差", B("sub", rank_roll("std", a, w), rank_roll("std", b, w)), [a, b],
        "比较不同变量的近期波动状态，识别交易活跃波动与价格或收益波动之间的结构性错配。")

for i, (a, b) in enumerate(pairs(PRICE, ACTIVITY, 45)):
    w = window_for(i, 2)
    add("F15", "趋势斜率差", B("sub", rank_roll("slope", a, w), rank_roll("slope", b, w)), [a, b],
        "价格趋势与交易活跃趋势的相对斜率可识别有成交确认的趋势与量价背离。")

for i, (a, b) in enumerate(pairs(RET, ACTIVITY, 45)):
    w = window_for(i, 3)
    add("F16", "分布偏度差", B("sub", rank_roll("skew", a, w), rank_roll("skew", b, w)), [a, b],
        "收益分布与交易活跃分布的偏度差异可反映尾部交易行为和非对称风险。")

for i, x in enumerate(TS_FIELDS[:45]):
    w = window_for(i, 1)
    add("F17", "中位均值偏离", B("sub", RK(R("median", F(x), w)), RK(R("mean", F(x), w))), [x],
        "滚动中位数与均值的排序差异刻画分布偏斜和极端值对近期状态的影响。")

for i, x in enumerate(TS_FIELDS[:45]):
    w = window_for(i, 2)
    add("F18", "线性衰减均值差", B("sub", RK(R("decay_linear", F(x), w)), RK(R("mean", F(x), w))), [x],
        "线性衰减统计相对等权均值的偏离强调近期信息，刻画状态加速或减速。")

for i, x in enumerate(TS_FIELDS[:45]):
    w = max(5, window_for(i, 3))
    p = max(1, min(w, w // 3))
    add("F19", "SMA等权均值差", B("sub", RK(R("sma", F(x), w, p)), RK(R("mean", F(x), w))), [x],
        "平滑移动统计与等权均值的差异刻画路径依赖和平滑方式造成的状态变化。")

for i, x in enumerate(TS_FIELDS[:45]):
    w = max(5, window_for(i, 4))
    k = max(1, min(w, max(2, w // 5)))
    add("F20", "高值均值溢价", B("sub", RK(R("topk_mean", F(x), w, k)), RK(R("mean", F(x), w))), [x],
        "窗口内高值均值相对整体均值的偏离反映尖峰强度与上尾集中程度。")

for i, x in enumerate(TS_FIELDS[:45]):
    w = window_for(i, 5)
    add("F21", "分位基准偏离", B("sub", RK(F(x)), RK(R("quantile", F(x), w, 0.7))), [x],
        "当前值相对自身滚动高分位基准的横截面偏离可刻画突破、拥挤或异常状态。")

for i, x in enumerate(TS_FIELDS[:45]):
    w = window_for(i, 6)
    add("F22", "极值时点偏置", B("sub", R("argmax", F(x), w), R("argmin", F(x), w)), [x],
        "近期高点与低点出现时点的相对位置刻画趋势方向与路径非对称性。")

for i, x in enumerate(PRICE + ACTIVITY + RET):
    w = window_for(i, 2)
    add("F23", "趋势可信度交互", B("mul", RK(R("slope", F(x), w)), R("rsquare", F(x), w)), [x],
        "趋势斜率与拟合优度联合刻画趋势方向和路径一致性，降低仅由噪声尖峰造成的假趋势。")

for i, x in enumerate(TS_FIELDS[:45]):
    w = window_for(i, 7)
    add("F24", "变化波动交互", B("mul", RK(R("delta", F(x), w)), RK(R("std", F(x), w))), [x],
        "中期变化方向与自身波动状态交互，刻画大幅且不稳定变化与稳定趋势之间的差异。")


# 25-30: rolling pair relationships
for i, (a, b) in enumerate(pairs(PRICE, ACTIVITY, 45)):
    w = window_for(i, 1)
    add("F25", "价格活跃相关", PR("corr", RK(F(a)), RK(F(b)), w), [a, b],
        "价格位置与交易活跃度在时间维度上的滚动相关性可识别量价确认或背离。")

for i, (a, b) in enumerate(pairs(RET, ACTIVITY, 45)):
    w = window_for(i, 2)
    add("F26", "收益活跃相关", PR("corr", RK(F(a)), RK(F(b)), w), [a, b],
        "收益与交易活跃度的滚动相关反映上涨/下跌是否伴随交易参与度变化。")

for i, (a, b) in enumerate(pairs(FLOW, SIZE, 45)):
    w = window_for(i, 3)
    add("F27", "基本面规模相关", PR("corr", RK(F(a)), RK(F(b)), w), [a, b],
        "基本面与规模横截面排序随时间的联动强弱可识别公司状态与资本规模之间的动态耦合。")

for i, (a, b) in enumerate(pairs(PRICE, ACTIVITY, 45)):
    w = window_for(i, 4)
    add("F28", "价格活跃协方差", PR("cov", RK(F(a)), RK(F(b)), w), [a, b],
        "标准化排序序列的滚动协方差刻画量价共同波动的强度，而不仅是方向一致性。")

for i, (a, b) in enumerate(pairs(FLOW, SIZE, 45)):
    w = window_for(i, 5)
    add("F29", "基本面规模协方差", PR("cov", RK(F(a)), RK(F(b)), w), [a, b],
        "基本面与资本规模排序的共同变化强度可识别扩张、收缩与盈利变化是否同步。")

for i, (a, b) in enumerate(pairs(PRICE, ACTIVITY, 45)):
    w = window_for(i, 6)
    corr = PR("corr", RK(F(a)), RK(F(b)), w)
    vol = R("std", F(RET[i % len(RET)]), w)
    add("F30", "相关波动交互", B("mul", RK(corr), RK(vol)), [a, b, RET[i % len(RET)]],
        "量价相关结构与收益波动状态交互，区分平稳确认和高波动拥挤下的相关性。")


# 31-37: regression families
for i, (a, b) in enumerate(pairs(FLOW + PRICE, SIZE + BENCH, 45)):
    w = window_for(i, 1)
    add("F31", "滚动回归Beta", FN("regression_beta", [RK(F(a)), RK(F(b))], w), [a, b],
        "滚动回归斜率刻画一个横截面特征对另一个特征变化的敏感度，识别动态暴露差异。")

for i, (a, b) in enumerate(pairs(FLOW + PRICE, SIZE + BENCH, 45)):
    w = window_for(i, 2)
    add("F32", "滚动回归Alpha", FN("regression_alpha", [RK(F(a)), RK(F(b))], w), [a, b],
        "控制第二个特征后剩余的滚动截距刻画无法由常见规模或基准状态解释的相对水平。")

for i, (a, b) in enumerate(pairs(RET + FLOW, BENCH + SIZE, 45)):
    w = window_for(i, 3)
    add("F33", "回归残差波动", FN("regression_resid_std", [RK(F(a)), RK(F(b))], w), [a, b],
        "回归残差标准差衡量无法被基准或规模解释的特质波动与经营不稳定性。")

for i, (a, b) in enumerate(pairs(RET + PRICE, BENCH + ACTIVITY, 45)):
    m = [3, 6, 9, 12, 18, 24][i % 6]
    add("F34", "月频回归Alpha", FN("monthly_regression_alpha", [RK(F(a)), RK(F(b))], m), [a, b],
        "月度聚合回归截距强调较低频的持续异常表现，弱化日频噪声。")

for i, (a, b) in enumerate(pairs(RET + PRICE, BENCH + ACTIVITY, 45)):
    m = [3, 6, 9, 12, 18, 24][(i + 2) % 6]
    add("F35", "月频Beta残差乘积", FN("monthly_beta_resid_product", [RK(F(a)), RK(F(b))], m), [a, b],
        "月频敏感度与残差结构的联合作用刻画系统暴露和特质偏离同时存在的状态。")

market_up = Q("gt", R("mean", F("returns"), 20), C(0))
for i, (a, b) in enumerate(pairs(RET + FLOW, BENCH + SIZE, 45)):
    w = window_for(i, 4)
    add("F36", "上行状态掩码Beta", FN("masked_regression_beta", [RK(F(a)), RK(F(b)), market_up], w), [a, b, "returns"],
        "只在近期市场收益均值为正的历史片段估计敏感度，刻画上行环境中的条件暴露。")

for i, (a, b, c, d) in enumerate(quads(FLOW, SIZE, ACTIVITY, PRICE + BENCH, 45)):
    w = window_for(i, 5)
    add("F37", "多变量残差", FN("multi_regression_residual", [RK(F(a)), RK(F(b)), RK(F(c)), RK(F(d))], w), [a, b, c, d],
        "以规模、交易活跃和价格状态共同解释基本面后保留的残差，寻找多维控制后的独立信息。")


# 38-43: special time-series functions
for i, x in enumerate(TS_FIELDS[:50]):
    w = window_for(i, 2)
    add("F38", "指数加权波动", FN("exp_weighted_std", [RK(F(x))], w, 0.94), [x],
        "指数加权标准差更重视近期状态变化，刻画最新不稳定性相对长期历史的冲击。")

for i, x in enumerate(TS_FIELDS[:50]):
    w = window_for(i, 3)
    add("F39", "指数加权累积", FN("exp_weighted_sum", [ZS(F(x))], w, 0.9), [x],
        "指数加权累积突出近期标准化信号的连续性，捕捉持续但逐渐衰减的状态影响。")

for i, x in enumerate(TS_FIELDS[:50]):
    w = window_for(i, 4)
    add("F40", "累计区间幅度", FN("cumulative_range", [RK(F(x))], w), [x],
        "累计区间范围衡量一段时间内状态扩张与收缩的幅度，刻画路径依赖的波动结构。")

for i, x in enumerate(TS_FIELDS[:50]):
    w = window_for(i, 5)
    add("F41", "加权移动状态", FN("wma", [RK(F(x))], w, 0.8), [x],
        "加权移动状态强调近期横截面位置，刻画信号从旧状态向新状态迁移的速度。")

for i, x in enumerate((RET + ["book_to_price", "illiq_3m"] + PRICE + ACTIVITY)[:35]):
    w = window_for(i, 6)
    add("F42", "累计收益区间CMRA", FN("cmra", [RK(F(x))], w, 1.0), [x],
        "CMRA 类累计区间统计刻画中期累计状态的极差与路径风险，适合识别持续性和反转边界。")

for x in TS_FIELDS[:50]:
    add("F43", "上月极值偏离", B("sub", RK(F(x)), RK(FN("previous_month_max", [RK(F(x))]))), [x],
        "当前横截面位置相对上一月极值的偏离刻画突破后延续、回撤或均值回归压力。")


# 44-49: cross-section and neutralization
for i, (a, b) in enumerate(pairs(FLOW + RET, SIZE + ACTIVITY, 45)):
    add("F44", "截面多空条件均值", FN("cross_section_long_short", [RK(F(a)), RK(F(b))], parameter=0.2), [a, b],
        "用一个特征选择截面两端，再观察另一个特征的多空差异，刻画条件化的横截面联动。")

for i, (a, b) in enumerate(pairs(FLOW + RET, SIZE + ACTIVITY, 45)):
    add("F45", "截面加权均值", FN("cross_section_weighted_mean", [RK(F(a)), RK(F(b))]), [a, b],
        "以第二个特征作为截面权重聚合第一个特征，刻画由规模或交易结构加权后的相对状态。")

for i, (a, b) in enumerate(pairs(FLOW + RET, SIZE + ACTIVITY, 45)):
    add("F46", "截面中位比", FN("cross_section_median_ratio", [RK(F(a)), RK(F(b))], parameter=0.2), [a, b],
        "比较条件截面中的中位状态比例，降低极端值影响并刻画不同特征分层后的结构差异。")

groups = ["industry", "sector", "subindustry"]
for i, (a, b) in enumerate(pairs(FLOW, SIZE, 45)):
    add("F47", "组内质量规模差", GN(spread(a, b), groups[i % 3]), [a, b],
        "在行业或层级分组内剔除共同结构后比较基本面与规模排序，降低行业组成带来的伪信号。")

for i, (a, b) in enumerate(pairs(PRICE, ACTIVITY, 45)):
    w = window_for(i, 1)
    add("F48", "组内量价相关", GN(PR("corr", RK(F(a)), RK(F(b)), w), groups[(i + 1) % 3]), [a, b],
        "在行业或层级分组内比较量价相关结构，降低行业交易习惯差异造成的系统性偏置。")

for i, (a, b) in enumerate(pairs(FLOW, SIZE + BENCH, 45)):
    w = window_for(i, 2)
    alpha = FN("regression_alpha", [RK(F(a)), RK(F(b))], w)
    add("F49", "组内回归异常项", GN(alpha, groups[(i + 2) % 3]), [a, b],
        "先控制规模或基准状态，再在行业分组内中性化残余截距，寻找更独立的公司特异信息。")


# 50-52: regime conditionals (no zero-mask)
for i, (a, b, c, d) in enumerate(quads(FLOW, SIZE, ACTIVITY, PRICE, 45)):
    cond = Q("gt", R("mean", F("returns"), window_for(i, 1)), C(0))
    add("F50", "市场状态切换信号", COND(cond, spread(a, b), spread(c, d)), [a, b, c, d, "returns"],
        "根据近期市场收益状态在基本面相对价值与交易价格错配之间切换，刻画机制的市场状态依赖。")

for i, (a, b, c, d) in enumerate(quads(FLOW, SIZE, PRICE, ACTIVITY, 45)):
    liq = ACTIVITY[i % len(ACTIVITY)]
    cond = Q("gt", RK(F(liq)), C(0.5))
    add("F51", "流动性状态切换", COND(cond, spread(a, b), spread(c, d)), [a, b, c, d, liq],
        "根据个股流动性横截面状态切换基本面与价格交易信号，允许不同流动性层级采用不同机制。")

for i, (a, b, c, d) in enumerate(quads(FLOW, SIZE, PRICE, ACTIVITY, 45)):
    retf = RET[i % len(RET)]
    cond = Q("gt", RK(R("std", F(retf), window_for(i, 2))), C(0.5))
    add("F52", "波动状态切换", COND(cond, spread(a, b), spread(c, d)), [a, b, c, d, retf],
        "根据近期收益波动的横截面状态切换质量价值与量价信号，刻画高低波动环境中的机制差异。")


# 53-60: composite mechanisms
for i, (a, b) in enumerate(pairs(FLOW, PRICE, 45)):
    w = window_for(i, 3)
    expr = B("mul", spread(a, SIZE[i % len(SIZE)]), RK(R("slope", F(b), w)))
    add("F53", "质量趋势交互", expr, [a, SIZE[i % len(SIZE)], b],
        "基本面相对资本规模的质量优势只有在价格趋势配合时才强化，捕捉质量与趋势共振。")

for i, (a, b) in enumerate(pairs(FLOW, ACTIVITY, 45)):
    p = PRICE[i % len(PRICE)]
    w = window_for(i, 4)
    expr = B("mul", spread(a, SIZE[i % len(SIZE)]), RK(PR("corr", RK(F(p)), RK(F(b)), w)))
    add("F54", "质量量价确认", expr, [a, SIZE[i % len(SIZE)], p, b],
        "基本面质量信号与量价相关结构交互，要求公司质量和交易确认同时存在。")

for i, (a, b, c, d) in enumerate(quads(FLOW, SIZE, ACTIVITY, ACTIVITY[::-1], 45)):
    expr = B("add", spread(a, b), B("sub", RK(F(c)), RK(F(d))))
    add("F55", "价值流动性合成", expr, [a, b, c, d],
        "基本面相对规模的价值轴与流动性结构轴共同决定横截面排序，兼顾估值与可交易状态。")

for i, (a, b) in enumerate(pairs(FLOW, SIZE, 45)):
    retf = RET[i % len(RET)]
    w = window_for(i, 5)
    expr = B("add", spread(a, b), RK(R("sum", F(retf), w)))
    add("F56", "价值动量合成", expr, [a, b, retf],
        "基本面相对规模的价值信息与近期累计收益状态共同作用，捕捉价值被价格逐步确认的过程。")

for i, (a, b) in enumerate(pairs(FLOW, SIZE, 45)):
    x = FLOW[(i + 3) % len(FLOW)]
    w = window_for(i, 6)
    expr = B("sub", spread(a, b), RK(R("std", RK(F(x)), w)))
    add("F57", "质量稳定性合成", expr, [a, b, x],
        "在质量或价值排序基础上惩罚自身历史不稳定性，偏好基本面优势更稳定的公司。")

for i, p in enumerate(PRICE_CORE):
    for a in ACTIVITY[:6]:
        w = window_for(i + ACTIVITY.index(a), 2)
        body = RK(B("sub", F("close"), F("open")))
        rng = RK(B("sub", F("high"), F("low")))
        act = RK(R("mean", F(a), w))
        expr = B("add", B("sub", body, rng), B("sub", act, C(0.5)))
        add("F58", "日内实体区间交易偏离", expr, ["close", "open", "high", "low", a],
            "K线实体相对日内区间的强弱与交易活跃状态共同刻画日内方向性和参与度。")
        if _family_counts["F58"] >= 45:
            break
    if _family_counts["F58"] >= 45:
        break

for i, a in enumerate(ACTIVITY * 7):
    if _family_counts["F59"] >= 45:
        break
    w = window_for(i, 3)
    disp = B("sub", RK(B("sub", F("vwap"), F("close"))), RK(B("sub", F("close"), F("open"))))
    expr = B("add", disp, B("sub", RK(R("mean", F(a), w)), C(0.5)))
    add("F59", "VWAP价格活跃偏离", expr, ["vwap", "close", "open", a],
        "VWAP相对收盘与开盘实体的偏离结合交易活跃度，刻画成交重心与价格方向是否一致。")

for i, (p, b) in enumerate(pairs(PRICE, BENCH, 45)):
    w = window_for(i, 4)
    expr = B("sub", RK(R("slope", F(p), w)), RK(R("slope", F(b), w)))
    add("F60", "基准相对趋势", expr, [p, b],
        "个股价格趋势相对市场基准趋势的差异刻画独立强弱，降低纯市场方向暴露。")


# 61-68: additional orthogonal composites/functions
for i, (p, b) in enumerate(pairs(PRICE, BENCH, 45)):
    a = ACTIVITY[i % len(ACTIVITY)]
    w = window_for(i, 5)
    corr = PR("corr", RK(F(p)), RK(F(b)), w)
    resid = FN("regression_resid_std", [RK(F(p)), RK(F(b))], w)
    expr = B("add", B("sub", RK(corr), C(0.5)), B("mul", RK(resid), B("sub", RK(F(a)), C(0.5))))
    add("F61", "基准相关残差活跃合成", expr, [p, b, a],
        "市场相关性、特质残差与交易活跃度共同刻画系统性和特质性来源的切换。")

for i, (a, b, c, d) in enumerate(quads(FLOW, SIZE, ACTIVITY, PRICE, 45)):
    expr = GN(B("mul", spread(a, b), spread(c, d)), groups[i % 3])
    add("F62", "组内四维交互", expr, [a, b, c, d],
        "将基本面-规模和交易-价格两条错配轴交互后再做分组中性化，寻找行业内的复合异常。")

for i, (a, b) in enumerate(pairs(FLOW, ACTIVITY, 45)):
    selector = B("sub", RK(F(a)), RK(F(SIZE[i % len(SIZE)])))
    value = B("sub", RK(F(b)), RK(F(PRICE[i % len(PRICE)])))
    add("F63", "截面选择器质量差", FN("cross_section_long_short", [selector, value], parameter=0.15), [a, SIZE[i % len(SIZE)], b, PRICE[i % len(PRICE)]],
        "先按质量价值轴选择截面两端，再比较交易价格错配，检验一种机制在另一种机制条件下的差异。")

for i, (a, b) in enumerate(pairs(FLOW, SIZE, 45)):
    weight = B("sub", RK(F(ACTIVITY[i % len(ACTIVITY)])), C(0.5))
    value = spread(a, b)
    add("F64", "交易权重价值状态", FN("cross_section_weighted_mean", [value, weight]), [a, b, ACTIVITY[i % len(ACTIVITY)]],
        "用交易活跃状态为质量价值信号加权，刻画市场参与度对基本面信息定价速度的影响。")

for i, (a, b) in enumerate(pairs(FLOW, SIZE, 45)):
    cond = B("sub", RK(F(ACTIVITY[i % len(ACTIVITY)])), RK(F(PRICE[i % len(PRICE)])))
    add("F65", "中位条件质量比", FN("cross_section_median_ratio", [spread(a, b), cond], parameter=0.25), [a, b, ACTIVITY[i % len(ACTIVITY)], PRICE[i % len(PRICE)]],
        "用交易价格错配对质量价值信号做截面条件分层，并以中位结构降低极端值影响。")

for i, (a, b) in enumerate(pairs(FLOW + ACTIVITY, SIZE + PRICE, 45)):
    w = window_for(i, 6)
    add("F66", "双序列加权均值", FN("weighted_mean", [RK(F(a)), RK(F(b))], w), [a, b],
        "两条不同信息序列的滚动加权均值刻画共同演化路径，减少单一变量的偶发噪声。")

for i, x in enumerate(TS_FIELDS[:45]):
    w = window_for(i, 7)
    add("F67", "时序排名变化", B("sub", R("rank", F(x), w), RK(F(x))), [x],
        "自身时间序列位置与当日横截面位置的差异区分个股历史异常和市场横截面异常。")

for i, x in enumerate(TS_FIELDS[:45]):
    w = window_for(i, 8)
    add("F68", "路径残差状态", RK(R("resi", RK(F(x)), w)), [x],
        "对标准化后的历史路径提取滚动残差，刻画不能被局部趋势解释的异常状态。")


def make_record(p: Proposal, source_record_id: str) -> dict[str, Any]:
    expr = vc.canonicalize(p.expr, set(vc.ALLOWED_FEATURES))
    return {
        "source_record_id": source_record_id,
        "name": p.name,
        "source": SOURCE,
        "source_ref": f"LLM factor mining batch {BATCH_NAME} / family {p.family}",
        "formula_provenance": "由经济/市场机制假设直接构造，并翻译为 factors_lab canonical AST；非论文或研报原文抄录。",
        "original_formula": vc.render_formula(expr),
        "economic_rationale": p.rationale,
        "source_constraints": p.constraints,
        "canonical_expression": expr,
    }


def initial_payload() -> tuple[dict[str, Any], dict[str, Proposal]]:
    records = []
    by_id: dict[str, Proposal] = {}
    for p in PROPOSALS:
        rid = f"CAND-{p.key}"
        records.append(make_record(p, rid))
        by_id[rid] = p
    return {
        "schema_version": 1,
        "batch_name": BATCH_NAME + "_proposal_pool",
        "source": SOURCE,
        "records": records,
    }, by_id


def choose_balanced(candidates: list[Proposal]) -> list[Proposal]:
    groups_map: dict[str, list[Proposal]] = defaultdict(list)
    for p in candidates:
        groups_map[p.family].append(p)

    chosen: list[Proposal] = []
    family_used: dict[str, int] = defaultdict(int)
    positions: dict[str, int] = defaultdict(int)
    families = sorted(groups_map)

    progress = True
    while len(chosen) < TARGET and progress:
        progress = False
        for family in families:
            if len(chosen) >= TARGET:
                break
            if family_used[family] >= MAX_PER_FAMILY:
                continue
            pos = positions[family]
            pool = groups_map[family]
            if pos >= len(pool):
                continue
            chosen.append(pool[pos])
            positions[family] += 1
            family_used[family] += 1
            progress = True

    if len(chosen) < TARGET:
        availability = {k: len(v) for k, v in groups_map.items()}
        raise RuntimeError(
            f"only {len(chosen)} diverse no-warning candidates available; "
            f"need {TARGET}. family availability={availability}"
        )
    return chosen


def main() -> int:
    bank = vc.load_bank(ROOT / "mother_bank")
    proposal_payload, by_id = initial_payload()
    initial_out, initial_report = vc.validate_batch(proposal_payload, bank)

    warning_candidates = {
        item["candidate"]
        for item in initial_report["findings"]
        if item["severity"] == "warning"
    }
    error_candidates = {
        item["candidate"]
        for item in initial_report["findings"]
        if item["severity"] == "error"
    }

    clean: list[Proposal] = []
    for rec in initial_out["records"]:
        rid = rec["source_record_id"]
        if rid in warning_candidates or rid in error_candidates:
            continue
        clean.append(by_id[rid])

    selected = choose_balanced(clean)

    final_records = [
        make_record(p, f"FM-20261008-500-{idx:04d}")
        for idx, p in enumerate(selected, 1)
    ]
    final_payload = {
        "schema_version": 1,
        "batch_name": BATCH_NAME,
        "source": SOURCE,
        "records": final_records,
    }

    final_out, final_report = vc.validate_batch(final_payload, bank)
    if final_report["accepted_count"] != TARGET or final_report["rejected_count"] != 0:
        raise RuntimeError(f"final validation failed: {json.dumps(final_report, ensure_ascii=False)}")
    if final_report["warning_count"] != 0:
        raise RuntimeError(f"final batch still has warnings: {json.dumps(final_report, ensure_ascii=False)}")

    family_counts: dict[str, int] = defaultdict(int)
    for p in selected:
        family_counts[p.family] += 1

    selection = {
        "schema_version": 1,
        "batch_name": BATCH_NAME,
        "proposal_count": len(PROPOSALS),
        "initial_validator_accepted": initial_report["accepted_count"],
        "initial_validator_rejected": initial_report["rejected_count"],
        "initial_validator_warnings": initial_report["warning_count"],
        "clean_no_warning_count": len(clean),
        "selected_count": len(selected),
        "max_per_family": MAX_PER_FAMILY,
        "mother_bank_factor_count": final_report["mother_bank_factor_count"],
        "reference_files": final_report["reference_files"],
        "selected_keys": [p.key for p in selected],
        "family_counts": dict(sorted(family_counts.items())),
    }

    ROOT_OUTPUT.write_text(json.dumps(final_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    MOTHER_COPY.write_text(json.dumps(final_out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    AUDIT_OUTPUT.write_text(json.dumps({
        "selection": selection,
        "final_validator_report": final_report,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    SELECTION_OUTPUT.write_text(json.dumps(selection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "proposal_count": len(PROPOSALS),
        "clean_no_warning_count": len(clean),
        "selected_count": len(selected),
        "mother_bank_factor_count": final_report["mother_bank_factor_count"],
        "warning_count": final_report["warning_count"],
        "family_count": len(family_counts),
        "max_family_size": max(family_counts.values()),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
