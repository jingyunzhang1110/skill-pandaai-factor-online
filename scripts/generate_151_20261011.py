#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts" / "validate_candidates.py"

spec = importlib.util.spec_from_file_location("vc", VALIDATOR_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"cannot load validator: {VALIDATOR_PATH}")
vc = importlib.util.module_from_spec(spec)
sys.modules["vc"] = vc
spec.loader.exec_module(vc)

BATCH_NAME = "fm_20261011_151"
SOURCE = "factor-mining-skill"
TARGET = 151

ROOT_OUTPUT = ROOT / "ready_for_factors_lab_20261011_151.json"
AUDIT_OUTPUT = ROOT / "audit_20261011_151.json"
POOL_AUDIT_OUTPUT = ROOT / "audit_pool_20261011_151.json"

CATEGORIES: dict[str, list[str]] = {
    "price": ["close", "open", "high", "low", "vwap", "adj_close"],
    "benchmark": [
        "benchmark_close", "benchmark_open", "sse_composite_close",
        "float_cap_weighted_market_index",
    ],
    "return": ["returns", "ret", "factor_return"],
    "activity": ["turnover", "volume", "amount", "illiq_3m", "stom_month"],
    "shares": ["float_shares", "mkt_freeshares", "holder_avgpct"],
    "size": [
        "market_cap", "float_market_cap", "cap", "enterprise_value",
        "total_assets", "avg_total_assets",
    ],
    "equity": ["book_equity", "common_equity", "parent_equity_ex_minority"],
    "leverage": [
        "total_debt", "interest_bearing_debt", "long_term_debt",
        "preferred_equity",
    ],
    "profit": [
        "earnings", "net_income_ttm", "parent_net_income_ttm",
        "operating_profit_ttm", "net_income_ex_nr_ttm", "gross_profit",
        "ebit", "ebitda",
    ],
    "cashflow": ["cfo_ttm", "free_cash_flow", "net_cash_flow", "capex", "dividend_1y"],
    "quarter": [
        "sales_q", "net_income_q", "parent_net_income_q",
        "operating_profit_q", "cfo_q", "net_income_ex_nr_q",
    ],
    "sales": ["sales_ttm", "sales"],
    "other": ["basic_eps", "book_to_price", "executive_compensation_top3", "dividend"],
    "risk": ["hd", "ld", "tr"],
}

CATEGORY_LABEL = {
    "price": "价格",
    "benchmark": "基准",
    "return": "收益",
    "activity": "交易",
    "shares": "股本",
    "size": "规模",
    "equity": "权益",
    "leverage": "杠杆",
    "profit": "盈利",
    "cashflow": "现金流",
    "quarter": "季度",
    "sales": "收入",
    "other": "另类",
    "risk": "波幅",
}

FUNDAMENTAL = {
    "shares", "size", "equity", "leverage", "profit",
    "cashflow", "quarter", "sales", "other",
}

PAIR_CATEGORIES: list[tuple[str, str]] = [
    ("price", "activity"),
    ("price", "return"),
    ("price", "benchmark"),
    ("price", "size"),
    ("benchmark", "return"),
    ("benchmark", "activity"),
    ("return", "activity"),
    ("return", "size"),
    ("return", "profit"),
    ("activity", "size"),
    ("activity", "profit"),
    ("activity", "cashflow"),
    ("activity", "shares"),
    ("size", "profit"),
    ("size", "cashflow"),
    ("size", "equity"),
    ("size", "leverage"),
    ("profit", "cashflow"),
    ("profit", "quarter"),
    ("profit", "equity"),
    ("profit", "leverage"),
    ("cashflow", "quarter"),
    ("cashflow", "leverage"),
    ("equity", "leverage"),
    ("shares", "activity"),
    ("shares", "size"),
    ("sales", "size"),
    ("sales", "profit"),
    ("quarter", "size"),
    ("other", "size"),
    ("other", "profit"),
    ("risk", "price"),
    ("risk", "return"),
    ("risk", "activity"),
    ("quarter", "cashflow"),
    ("cashflow", "profit"),
    ("leverage", "profit"),
    ("profit", "activity"),
    ("size", "activity"),
    ("return", "benchmark"),
]

WINDOW_A = [10, 20, 30, 40, 60]
WINDOW_B = [20, 30, 40, 60, 90]
GROUPS = ["industry", "sector", "subindustry"]


def F(name: str, lag: int = 0) -> dict[str, Any]:
    return {"kind": "feature", "name": name, "lag": lag}


def C(value: float) -> dict[str, Any]:
    return {"kind": "constant", "value": value}


def U(op: str, x: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "unary", "operator": op, "operand": x}


def B(op: str, a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "binary", "operator": op, "left": a, "right": b}


def R(
    op: str,
    x: dict[str, Any],
    window: int,
    parameter: float | int | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "kind": "rolling",
        "operator": op,
        "operand": x,
        "window": window,
    }
    if parameter is not None:
        out["parameter"] = parameter
    return out


def PR(
    op: str,
    a: dict[str, Any],
    b: dict[str, Any],
    window: int,
) -> dict[str, Any]:
    return {
        "kind": "pair_rolling",
        "operator": op,
        "left": a,
        "right": b,
        "window": window,
    }


def FN(
    op: str,
    operands: list[dict[str, Any]],
    window: int | None = None,
    parameter: float | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {
        "kind": "function",
        "operator": op,
        "operands": operands,
    }
    if window is not None:
        out["window"] = window
    if parameter is not None:
        out["parameter"] = parameter
    return out


def GN(x: dict[str, Any], group: str) -> dict[str, Any]:
    return {"kind": "group_neutralize", "operand": x, "group": group}


def RK(x: dict[str, Any]) -> dict[str, Any]:
    return U("rank", x)


def center(x: dict[str, Any]) -> dict[str, Any]:
    return B("sub", x, C(0.5))


def lvl(field: str) -> dict[str, Any]:
    return RK(F(field))


def mean_state(field: str, w: int) -> dict[str, Any]:
    return RK(R("mean", F(field), w))


def std_state(field: str, w: int) -> dict[str, Any]:
    return RK(R("std", F(field), w))


def slope_state(field: str, w: int) -> dict[str, Any]:
    return RK(R("slope", F(field), w))


def delta_state(field: str, w: int) -> dict[str, Any]:
    return RK(R("delta", F(field), w))


def median_state(field: str, w: int) -> dict[str, Any]:
    return RK(R("median", F(field), w))


def q_state(field: str, w: int) -> dict[str, Any]:
    return RK(R("quantile", F(field), w, 0.75))


def tsrank_state(field: str, w: int) -> dict[str, Any]:
    return RK(R("rank", F(field), w))


def decay_state(field: str, w: int) -> dict[str, Any]:
    return RK(R("decay_linear", F(field), w))


def skew_state(field: str, w: int) -> dict[str, Any]:
    return RK(R("skew", F(field), w))


def resi_state(field: str, w: int) -> dict[str, Any]:
    return RK(R("resi", RK(F(field)), w))


def rsq_state(field: str, w: int) -> dict[str, Any]:
    return RK(R("rsquare", F(field), w))


def expstd_state(field: str, w: int) -> dict[str, Any]:
    return RK(FN("exp_weighted_std", [RK(F(field))], w, 0.94))


def wma_state(field: str, w: int) -> dict[str, Any]:
    return RK(FN("wma", [RK(F(field))], w, 0.8))


def range_state(field: str, w: int) -> dict[str, Any]:
    return RK(FN("cumulative_range", [RK(F(field))], w))


def pmax_state(field: str) -> dict[str, Any]:
    return RK(FN("previous_month_max", [RK(F(field))]))


def argmax_state(field: str, w: int) -> dict[str, Any]:
    return RK(R("argmax", F(field), w))


def argmin_state(field: str, w: int) -> dict[str, Any]:
    return RK(R("argmin", F(field), w))


TEMPLATE_LABELS: dict[str, str] = {
    "T01": "均值错配",
    "T02": "趋势错配",
    "T03": "变化错配",
    "T04": "波动错配",
    "T05": "中位错配",
    "T06": "分位错配",
    "T07": "时序位错配",
    "T08": "衰减错配",
    "T09": "偏度错配",
    "T10": "残差错配",
    "T11": "趋势可信错配",
    "T12": "指数波动错配",
    "T13": "加权状态错配",
    "T14": "区间状态错配",
    "T15": "上月极值错配",
    "T16": "均值波动差",
    "T17": "趋势波动差",
    "T18": "变化波动差",
    "T19": "趋势均值差",
    "T20": "变化均值差",
    "T21": "中位分位差",
    "T22": "偏度波动差",
    "T23": "时序位均值差",
    "T24": "状态相关",
    "T25": "均值相关",
    "T26": "变化相关",
    "T27": "状态协方差",
    "T28": "状态Beta",
    "T29": "状态Alpha",
    "T30": "状态残差风险",
    "T31": "状态加权均值",
    "T32": "组内水平错配",
    "T33": "组内均值错配",
    "T34": "错配均值持续",
    "T35": "错配波动持续",
    "T36": "错配趋势持续",
    "T37": "交互中位持续",
    "T38": "交互上尾持续",
    "T39": "保守共识",
    "T40": "强势共识",
    "T41": "绝对分歧",
    "T42": "中心交互",
    "T43": "错配指数波动",
    "T44": "错配加权移动",
    "T45": "错配区间扩张",
    "T46": "组内状态相关",
    "T47": "组内状态Beta",
    "T48": "水平均值交互",
    "T49": "双历史偏离差",
    "T50": "双趋势差",
    "T51": "双波动差",
    "T52": "双变化差",
    "T53": "残差趋势差",
    "T54": "可信趋势差",
    "T55": "偏度变化差",
    "T56": "上月极值差",
    "T57": "极大时点差",
    "T58": "极值时点错位",
    "T59": "组内趋势差",
    "T60": "组内波动差",
}

TEMPLATE_RATIONALE: dict[str, str] = {
    "T01": "比较一类信息的近期均值状态与另一类信息的当期横截面状态，捕捉慢变量与快变量不同步。",
    "T02": "比较一类信息的滚动趋势与另一类信息的当期状态，捕捉趋势尚未被另一维度确认的错位。",
    "T03": "比较一类信息的历史变化与另一类信息的当前状态，刻画增量信息与存量状态之间的错位。",
    "T04": "比较一类信息的波动状态与另一类信息的当前状态，刻画不稳定性与水平暴露之间的分歧。",
    "T05": "用滚动中位状态对比另一类当前状态，减少极端值影响并衡量稳态错位。",
    "T06": "用历史上分位状态对比另一类当前状态，捕捉相对高位/低位与外部状态的不一致。",
    "T07": "比较时间序列位置与另一类当前状态，刻画自身历史位置和横截面位置的错位。",
    "T08": "将近期信息按线性衰减聚合后与另一类状态比较，强调较近观测并刻画状态错位。",
    "T09": "比较分布偏度与另一类状态，寻找非对称变化和外部信息不一致的股票。",
    "T10": "比较自身路径残差状态与另一类当前状态，刻画偏离自身历史路径的异常程度。",
    "T11": "以滚动拟合优度衡量趋势可信度，并与另一类状态比较，区分稳定趋势和噪声趋势。",
    "T12": "以指数加权波动刻画近期冲击，再与另一类状态比较，关注短期异常波动错位。",
    "T13": "以加权移动状态对比另一类状态，捕捉近期持续性与外部信息的错位。",
    "T14": "以累计区间扩张刻画路径振幅，再与另一类状态比较，寻找扩张与外部状态不匹配。",
    "T15": "以上月极值状态对比当前另一类信息，刻画月际记忆与当前横截面状态错位。",
    "T16": "比较一类信息的均值状态和另一类信息的波动状态，测试水平与不稳定性的交叉关系。",
    "T17": "比较趋势强弱与另一维度波动状态，测试趋势是否由高不确定性驱动。",
    "T18": "比较变化状态与另一维度波动状态，捕捉突变和不稳定性之间的非对称关系。",
    "T19": "比较趋势状态与另一维度的历史均值状态，寻找趋势与稳态水平的错位。",
    "T20": "比较变化状态与另一维度历史均值，捕捉最新增量相对稳态背景的差异。",
    "T21": "比较滚动中位与上分位状态，衡量稳态水平和尾部水平之间的结构差异。",
    "T22": "比较分布偏度与波动状态，区分对称高波动和单侧异常驱动的波动。",
    "T23": "比较自身历史位置和另一维度滚动均值，连接时序位置与横截面稳态。",
    "T24": "直接度量两类横截面状态在时间上的相关性，寻找联动过强或联动破裂的股票。",
    "T25": "度量一类均值状态与另一类当前状态的滚动相关性，关注慢变量与快变量的联动。",
    "T26": "度量两类信息变化状态的滚动相关性，关注共同冲击或背离冲击。",
    "T27": "用协方差刻画两类排名状态共同变化的幅度，而不仅是标准化相关强度。",
    "T28": "用滚动回归Beta衡量一类状态对另一类状态的敏感度，寻找异常高低敏感度。",
    "T29": "用滚动回归Alpha衡量在控制另一类状态后仍然存在的相对偏离。",
    "T30": "用滚动回归残差波动衡量无法被另一类信息解释的独立不确定性。",
    "T31": "对两类排名状态做滚动加权平均，寻找共同持续强弱而非单点极值。",
    "T32": "在行业内比较两类当前状态，降低行业结构差异对横截面排序的主导。",
    "T33": "在行业内比较一类均值状态与另一类当前状态，捕捉组内慢快变量错位。",
    "T34": "对两类当前状态的错配做滚动均值，要求错配具有持续性而非单日噪声。",
    "T35": "对两类状态错配的波动进行度量，寻找错配关系是否稳定。",
    "T36": "对两类状态错配的趋势进行度量，寻找错配持续扩大或收敛的股票。",
    "T37": "将两类中心化排名交互后取滚动中位，寻找稳定的共同高低状态。",
    "T38": "将两类中心化排名交互后取历史上尾均值，关注阶段性共同极端状态。",
    "T39": "取两类状态中的较弱者，要求两类信息同时不差，避免单一维度主导。",
    "T40": "取两类状态中的较强者，寻找任一维度出现显著优势时的横截面差异。",
    "T41": "度量两类横截面状态绝对分歧，直接寻找信息维度之间的错配程度。",
    "T42": "用中心化排名乘积刻画两类状态同向或反向共振，保留交互而非简单加总。",
    "T43": "对两类状态错配本身计算指数加权波动，寻找错配关系近期是否突然不稳定。",
    "T44": "对两类状态错配做加权移动平均，要求错配在近期具有持续性。",
    "T45": "对两类状态错配计算累计区间，衡量错配路径的扩张程度。",
    "T46": "先计算两类状态相关性，再做行业中性化，寻找行业内部联动异常。",
    "T47": "先计算两类状态回归Beta，再做行业中性化，寻找行业内部敏感度异常。",
    "T48": "将一类当前状态与另一类滚动均值状态中心化交互，测试快慢变量共振。",
    "T49": "分别计算两类信息相对自身历史均值的偏离，再比较两种偏离，寻找相对失衡。",
    "T50": "比较两类信息各自趋势强弱，直接刻画跨维度趋势分歧。",
    "T51": "比较两类信息各自波动状态，刻画跨维度不确定性差异。",
    "T52": "比较两类信息各自历史变化状态，刻画跨维度增量差异。",
    "T53": "比较一类信息的路径残差和另一类信息的趋势，连接异常偏离与趋势确认。",
    "T54": "比较一类趋势拟合可信度和另一类趋势状态，识别可信趋势与表面趋势的分歧。",
    "T55": "比较一类分布偏度和另一类变化状态，连接非对称风险与最新增量。",
    "T56": "比较上月极值记忆和另一类当前状态，捕捉月际极值影响是否被当前状态确认。",
    "T57": "比较两类信息最近极大值出现时点，刻画冲击发生时序是否同步。",
    "T58": "比较一类极大值时点和另一类极小值时点，刻画相反方向极值的时间错位。",
    "T59": "在行业内比较两类趋势状态，降低行业趋势差异后寻找个股相对趋势分歧。",
    "T60": "在行业内比较两类波动状态，降低行业波动结构后寻找个股相对不稳定性。",
}


def template_expr(
    tid: str,
    a: str,
    b: str,
    seed: int,
) -> dict[str, Any]:
    wa = WINDOW_A[seed % len(WINDOW_A)]
    wb = WINDOW_B[(seed * 3 + 1) % len(WINDOW_B)]
    group = GROUPS[seed % len(GROUPS)]
    A = lvl(a)
    B0 = lvl(b)

    if tid == "T01":
        return B("sub", mean_state(a, wa), B0)
    if tid == "T02":
        return B("sub", slope_state(a, wa), B0)
    if tid == "T03":
        return B("sub", delta_state(a, wa), B0)
    if tid == "T04":
        return B("sub", std_state(a, wa), B0)
    if tid == "T05":
        return B("sub", median_state(a, wa), B0)
    if tid == "T06":
        return B("sub", q_state(a, wa), B0)
    if tid == "T07":
        return B("sub", tsrank_state(a, wa), B0)
    if tid == "T08":
        return B("sub", decay_state(a, wa), B0)
    if tid == "T09":
        return B("sub", skew_state(a, wa), B0)
    if tid == "T10":
        return B("sub", resi_state(a, wa), B0)
    if tid == "T11":
        return B("sub", rsq_state(a, wa), B0)
    if tid == "T12":
        return B("sub", expstd_state(a, wa), B0)
    if tid == "T13":
        return B("sub", wma_state(a, wa), B0)
    if tid == "T14":
        return B("sub", range_state(a, wa), B0)
    if tid == "T15":
        return B("sub", pmax_state(a), B0)
    if tid == "T16":
        return B("sub", mean_state(a, wa), std_state(b, wb))
    if tid == "T17":
        return B("sub", slope_state(a, wa), std_state(b, wb))
    if tid == "T18":
        return B("sub", delta_state(a, wa), std_state(b, wb))
    if tid == "T19":
        return B("sub", slope_state(a, wa), mean_state(b, wb))
    if tid == "T20":
        return B("sub", delta_state(a, wa), mean_state(b, wb))
    if tid == "T21":
        return B("sub", median_state(a, wa), q_state(b, wb))
    if tid == "T22":
        return B("sub", skew_state(a, wa), std_state(b, wb))
    if tid == "T23":
        return B("sub", tsrank_state(a, wa), mean_state(b, wb))
    if tid == "T24":
        return PR("corr", A, B0, wa)
    if tid == "T25":
        return PR("corr", mean_state(a, wa), B0, wb)
    if tid == "T26":
        return PR("corr", delta_state(a, 5), delta_state(b, 5), wa)
    if tid == "T27":
        return PR("cov", A, B0, wa)
    if tid == "T28":
        return FN("regression_beta", [A, B0], wa)
    if tid == "T29":
        return FN("regression_alpha", [A, B0], wa)
    if tid == "T30":
        return FN("regression_resid_std", [A, B0], wa)
    if tid == "T31":
        return FN("weighted_mean", [A, B0], wa)
    if tid == "T32":
        return GN(B("sub", A, B0), group)
    if tid == "T33":
        return GN(B("sub", mean_state(a, wa), B0), group)
    if tid == "T34":
        return RK(R("mean", B("sub", A, B0), wa))
    if tid == "T35":
        return RK(R("std", B("sub", A, B0), wa))
    if tid == "T36":
        return RK(R("slope", B("sub", A, B0), wa))
    if tid == "T37":
        return RK(R("median", B("mul", center(A), center(B0)), wa))
    if tid == "T38":
        return RK(R("topk_mean", B("mul", center(A), center(B0)), wa, max(2, wa // 5)))
    if tid == "T39":
        return B("min", A, B0)
    if tid == "T40":
        return B("max", A, B0)
    if tid == "T41":
        return U("abs", B("sub", A, B0))
    if tid == "T42":
        return B("mul", center(A), center(B0))
    if tid == "T43":
        return RK(FN("exp_weighted_std", [B("sub", A, B0)], wa, 0.94))
    if tid == "T44":
        return RK(FN("wma", [B("sub", A, B0)], wa, 0.8))
    if tid == "T45":
        return RK(FN("cumulative_range", [B("sub", A, B0)], wa))
    if tid == "T46":
        return GN(PR("corr", A, B0, wa), group)
    if tid == "T47":
        return GN(FN("regression_beta", [A, B0], wa), group)
    if tid == "T48":
        return B("mul", center(A), center(mean_state(b, wb)))
    if tid == "T49":
        return B(
            "sub",
            B("sub", A, mean_state(a, wa)),
            B("sub", B0, mean_state(b, wb)),
        )
    if tid == "T50":
        return B("sub", slope_state(a, wa), slope_state(b, wb))
    if tid == "T51":
        return B("sub", std_state(a, wa), std_state(b, wb))
    if tid == "T52":
        return B("sub", delta_state(a, wa), delta_state(b, wb))
    if tid == "T53":
        return B("sub", resi_state(a, wa), slope_state(b, wb))
    if tid == "T54":
        return B("sub", rsq_state(a, wa), slope_state(b, wb))
    if tid == "T55":
        return B("sub", skew_state(a, wa), delta_state(b, wb))
    if tid == "T56":
        return B("sub", pmax_state(a), B0)
    if tid == "T57":
        return B("sub", argmax_state(a, wa), argmax_state(b, wb))
    if tid == "T58":
        return B("sub", argmax_state(a, wa), argmin_state(b, wb))
    if tid == "T59":
        return GN(B("sub", slope_state(a, wa), slope_state(b, wb)), group)
    if tid == "T60":
        return GN(B("sub", std_state(a, wa), std_state(b, wb)), group)
    raise ValueError(tid)


@dataclass(frozen=True)
class Proposal:
    template_id: str
    categories: tuple[str, str]
    fields: tuple[str, str]
    expr: dict[str, Any]
    name: str
    rationale: str
    constraints: str


def category_for_feature(name: str) -> str:
    for category, fields in CATEGORIES.items():
        if name in fields:
            return category
    return "other"


def coarse_signature(node: dict[str, Any]) -> str:
    def walk(x: Any) -> Any:
        if isinstance(x, list):
            return [walk(v) for v in x]
        if not isinstance(x, dict):
            return x
        kind = x.get("kind")
        if kind == "feature":
            return {
                "kind": "feature_category",
                "category": category_for_feature(str(x.get("name") or "")),
                "lag": "#" if int(x.get("lag", 0)) else 0,
            }
        if kind == "constant":
            return {"kind": "constant", "value": "#"}
        out: dict[str, Any] = {}
        for key, value in x.items():
            if key in {"window", "min_periods", "parameter", "target"}:
                out[key] = "#"
            elif key == "group":
                out[key] = "group"
            else:
                out[key] = walk(value)
        return out
    return json.dumps(
        walk(node),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def used_features(node: dict[str, Any]) -> set[str]:
    out: set[str] = set()

    def walk(x: Any) -> None:
        if isinstance(x, dict):
            if x.get("kind") == "feature":
                out.add(str(x["name"]))
            for value in x.values():
                walk(value)
        elif isinstance(x, list):
            for value in x:
                walk(value)
    walk(node)
    return out


def make_constraints(expr: dict[str, Any], categories: tuple[str, str]) -> str:
    metrics = vc.expression_metrics(expr)
    bits = [
        "仅使用因子日当期及历史信息；预热期缺失值不得填零；",
        f"完整历史依赖 {metrics['lookback']} 个交易日，未超过250日硬限制；",
    ]
    if set(categories) & FUNDAMENTAL:
        bits.append("低频财务/股本字段必须沿用 factors_lab 的 PIT 可得时点；")
    bits.append("公式使用排名状态避免量纲直接混合，不设置任意epsilon。")
    return "".join(bits)


def build_proposals() -> list[Proposal]:
    allowed = set(vc.ALLOWED_FEATURES)
    proposals: list[Proposal] = []
    seen_coarse: set[str] = set()
    counter = 0

    for tid in sorted(TEMPLATE_LABELS):
        for pair_index, categories in enumerate(PAIR_CATEGORIES):
            counter += 1
            ca, cb = categories
            afields = CATEGORIES[ca]
            bfields = CATEGORIES[cb]
            a = afields[(counter * 3 + pair_index) % len(afields)]
            b = bfields[(counter * 5 + pair_index * 2) % len(bfields)]
            try:
                raw = template_expr(tid, a, b, counter)
                expr = vc.canonicalize(raw, allowed)
                vc.validate_dimension(expr)
                metrics = vc.expression_metrics(expr)
            except Exception:
                continue

            if metrics["nodes"] > 20:
                continue
            if metrics["depth"] > 8:
                continue
            if metrics["lookback"] > 250:
                continue
            if len(used_features(expr)) > 4:
                continue

            sig = coarse_signature(expr)
            if sig in seen_coarse:
                continue
            seen_coarse.add(sig)

            label = TEMPLATE_LABELS[tid]
            cat_name = f"{CATEGORY_LABEL[ca]}{CATEGORY_LABEL[cb]}"
            name = f"{label}-{cat_name}-{counter:04d}"
            if len(name) > 40:
                name = f"{label}-{counter:04d}"
            rationale = (
                TEMPLATE_RATIONALE[tid]
                + f"本候选连接{CATEGORY_LABEL[ca]}与{CATEGORY_LABEL[cb]}两类信息，"
                "目标是形成与已有单一水平、单一窗口因子不同的横截面机制。"
            )
            proposals.append(
                Proposal(
                    template_id=tid,
                    categories=categories,
                    fields=(a, b),
                    expr=expr,
                    name=name,
                    rationale=rationale,
                    constraints=make_constraints(expr, categories),
                )
            )
    return proposals


def make_record(p: Proposal, rid: str, batch_name: str) -> dict[str, Any]:
    expr = vc.canonicalize(p.expr, set(vc.ALLOWED_FEATURES))
    return {
        "source_record_id": rid,
        "name": p.name,
        "source": SOURCE,
        "source_ref": f"LLM factor mining batch {batch_name} / mechanism {p.template_id}",
        "formula_provenance": (
            "由经济/市场机制假设直接构造，并翻译为 factors_lab canonical AST；"
            "非论文或研报原文抄录。"
        ),
        "original_formula": vc.render_formula(expr),
        "economic_rationale": p.rationale,
        "source_constraints": p.constraints,
        "canonical_expression": expr,
    }


def bank_coarse_signatures(bank: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    allowed = set(vc.ALLOWED_FEATURES)
    for item in bank["factors"]:
        raw = item.get("canonical_expression")
        if not isinstance(raw, dict):
            continue
        try:
            expr = vc.canonicalize(raw, allowed)
        except Exception:
            continue
        out.add(coarse_signature(expr))
    return out


def select_balanced(
    candidates: list[Proposal],
    target: int,
) -> list[Proposal]:
    by_template: dict[str, list[Proposal]] = defaultdict(list)
    for p in candidates:
        by_template[p.template_id].append(p)

    selected: list[Proposal] = []
    used_template: Counter[str] = Counter()
    used_pair: Counter[tuple[str, str]] = Counter()
    used_feature: Counter[str] = Counter()
    seen_sig: set[str] = set()

    # First pass: at most two from each mechanism template.
    for limit in (1, 2, 3, 4):
        progress = True
        while len(selected) < target and progress:
            progress = False
            for tid in sorted(TEMPLATE_LABELS):
                if len(selected) >= target:
                    break
                if used_template[tid] >= limit:
                    continue
                for p in by_template.get(tid, []):
                    sig = coarse_signature(p.expr)
                    if sig in seen_sig:
                        continue
                    if used_pair[p.categories] >= 7:
                        continue
                    fs = used_features(p.expr)
                    if any(used_feature[f] >= 12 for f in fs):
                        continue
                    selected.append(p)
                    seen_sig.add(sig)
                    used_template[tid] += 1
                    used_pair[p.categories] += 1
                    used_feature.update(fs)
                    progress = True
                    break

    if len(selected) < target:
        raise RuntimeError(
            f"insufficient balanced candidates: {len(selected)} < {target}"
        )
    return selected[:target]


def main() -> int:
    bank = vc.load_bank(ROOT / "mother_bank")
    if len(bank["factors"]) != 1849:
        raise RuntimeError(
            f"expected current mother bank size 1849, got {len(bank['factors'])}"
        )
    bank_coarse = bank_coarse_signatures(bank)

    proposals = build_proposals()
    prefiltered = [
        p for p in proposals
        if coarse_signature(p.expr) not in bank_coarse
    ]

    # Validate a broad, still-simple proposal pool against all 1849 references.
    pool_records = [
        make_record(
            p,
            f"CAND-20261011-{idx:04d}",
            BATCH_NAME + "_pool",
        )
        for idx, p in enumerate(prefiltered, 1)
    ]
    pool_payload = {
        "schema_version": 1,
        "batch_name": BATCH_NAME + "_pool",
        "source": SOURCE,
        "records": pool_records,
    }
    pool_out, pool_report = vc.validate_batch(pool_payload, bank)

    rejected_ids = {
        finding["candidate"]
        for finding in pool_report["findings"]
        if finding["severity"] in {"error", "warning"}
    }
    proposal_by_formula = {
        vc.render_formula(vc.canonicalize(p.expr, set(vc.ALLOWED_FEATURES))): p
        for p in prefiltered
    }

    clean: list[Proposal] = []
    for rec in pool_out["records"]:
        if rec["source_record_id"] in rejected_ids:
            continue
        formula = rec["original_formula"]
        p = proposal_by_formula.get(formula)
        if p is not None:
            clean.append(p)

    selected = select_balanced(clean, TARGET)
    final_records = [
        make_record(
            p,
            f"FM-20261011-151-{idx:04d}",
            BATCH_NAME,
        )
        for idx, p in enumerate(selected, 1)
    ]
    final_payload = {
        "schema_version": 1,
        "batch_name": BATCH_NAME,
        "source": SOURCE,
        "records": final_records,
    }

    final_out, final_report = vc.validate_batch(final_payload, bank)
    if final_report["accepted_count"] != TARGET:
        raise RuntimeError(
            f"final accepted {final_report['accepted_count']} != {TARGET}"
        )
    if final_report["rejected_count"] != 0:
        raise RuntimeError(
            "final validator rejected candidates: "
            + json.dumps(final_report, ensure_ascii=False)
        )
    if final_report["warning_count"] != 0:
        raise RuntimeError(
            "final validator warnings remain: "
            + json.dumps(final_report, ensure_ascii=False)
        )

    final_sigs = [coarse_signature(p.expr) for p in selected]
    if len(set(final_sigs)) != TARGET:
        raise RuntimeError("final mechanism signatures are not unique")
    if any(sig in bank_coarse for sig in final_sigs):
        raise RuntimeError("selected mechanism collides with mother bank coarse signature")

    template_counts = Counter(p.template_id for p in selected)
    pair_counts = Counter(p.categories for p in selected)
    feature_counts = Counter()
    lookbacks = []
    node_counts = []
    depths = []
    for p in selected:
        feature_counts.update(used_features(p.expr))
        metrics = vc.expression_metrics(p.expr)
        lookbacks.append(metrics["lookback"])
        node_counts.append(metrics["nodes"])
        depths.append(metrics["depth"])

    audit = {
        "schema_version": 1,
        "batch_name": BATCH_NAME,
        "mother_bank_factor_count": len(bank["factors"]),
        "reference_files": final_report["reference_files"],
        "proposal_count": len(proposals),
        "prefiltered_noncolliding_count": len(prefiltered),
        "pool_validator_accepted": pool_report["accepted_count"],
        "pool_validator_rejected": pool_report["rejected_count"],
        "pool_validator_warnings": pool_report["warning_count"],
        "clean_pool_count": len(clean),
        "selected_count": TARGET,
        "unique_mechanism_signatures": len(set(final_sigs)),
        "max_lookback": max(lookbacks),
        "max_nodes": max(node_counts),
        "max_depth": max(depths),
        "template_count": len(template_counts),
        "template_counts": dict(sorted(template_counts.items())),
        "category_pair_count": len(pair_counts),
        "max_per_category_pair": max(pair_counts.values()),
        "top_features": feature_counts.most_common(30),
        "final_validator_report": final_report,
    }

    ROOT_OUTPUT.write_text(
        json.dumps(final_out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    AUDIT_OUTPUT.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    POOL_AUDIT_OUTPUT.write_text(
        json.dumps(pool_report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "mother_bank_factor_count": len(bank["factors"]),
        "proposal_count": len(proposals),
        "prefiltered_noncolliding_count": len(prefiltered),
        "clean_pool_count": len(clean),
        "selected_count": TARGET,
        "template_count": len(template_counts),
        "max_template_count": max(template_counts.values()),
        "category_pair_count": len(pair_counts),
        "max_per_category_pair": max(pair_counts.values()),
        "max_lookback": max(lookbacks),
        "max_nodes": max(node_counts),
        "max_depth": max(depths),
        "warning_count": final_report["warning_count"],
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
