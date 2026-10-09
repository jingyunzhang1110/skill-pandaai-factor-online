#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter, defaultdict
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

BATCH_NAME = "fm_20261009_500_v2"
SOURCE = "factor-mining-skill"
TARGET = 500
MAX_PER_RECIPE = 12
MAX_PER_CATEGORY_TUPLE = 24
MAX_PER_PRIMITIVE_PATTERN = 28

ROOT_OUTPUT = ROOT / "ready_for_factors_lab_20261009_500_v2.json"
AUDIT_OUTPUT = ROOT / "audit_20261009_500_v2.json"
SELECTION_OUTPUT = ROOT / "campaign_20261009_500_v2_selection.json"

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
        "total_assets", "avg_total_assets", "aggregate_market_cap",
    ],
    "equity": [
        "book_equity", "common_equity", "parent_equity_ex_minority",
        "aggregate_book_value",
    ],
    "leverage": [
        "total_debt", "interest_bearing_debt", "long_term_debt",
        "preferred_equity",
    ],
    "profit": [
        "earnings", "net_income_ttm", "parent_net_income_ttm",
        "operating_profit_ttm", "net_income_ex_nr_ttm", "gross_profit",
        "ebit", "ebitda",
    ],
    "cashflow": [
        "cfo_ttm", "free_cash_flow", "net_cash_flow", "capex",
        "dividend_1y",
    ],
    "quarter": [
        "sales_q", "net_income_q", "parent_net_income_q",
        "operating_profit_q", "cfo_q", "net_income_ex_nr_q",
    ],
    "sales": ["sales_ttm", "sales", "aggregate_earnings"],
    "other": [
        "basic_eps", "book_to_price", "executive_compensation_top3",
        "dividend", "aggregate_earnings",
    ],
}

CATEGORY_LABEL = {
    "price": "价格",
    "benchmark": "市场基准",
    "return": "收益",
    "activity": "交易活跃",
    "shares": "股本持有",
    "size": "规模资产",
    "equity": "权益资本",
    "leverage": "负债杠杆",
    "profit": "盈利质量",
    "cashflow": "现金流",
    "quarter": "季度经营",
    "sales": "收入销售",
    "other": "另类基本面",
}

FEATURE_TO_CATEGORY: dict[str, str] = {}
for _category, _fields in CATEGORIES.items():
    for _field in _fields:
        FEATURE_TO_CATEGORY.setdefault(_field, _category)

FUNDAMENTAL_CATEGORIES = {
    "size", "equity", "leverage", "profit", "cashflow",
    "quarter", "sales", "other", "shares",
}

PAIR_CATEGORIES = [
    ("price", "activity"), ("price", "return"), ("price", "benchmark"),
    ("price", "size"), ("benchmark", "return"), ("benchmark", "activity"),
    ("return", "activity"), ("return", "size"), ("return", "profit"),
    ("activity", "size"), ("activity", "profit"), ("activity", "cashflow"),
    ("size", "profit"), ("size", "cashflow"), ("size", "quarter"),
    ("size", "equity"), ("size", "leverage"), ("profit", "cashflow"),
    ("profit", "quarter"), ("profit", "equity"), ("profit", "leverage"),
    ("cashflow", "quarter"), ("equity", "leverage"), ("other", "size"),
    ("other", "profit"), ("shares", "activity"), ("shares", "size"),
    ("sales", "size"), ("sales", "activity"), ("sales", "profit"),
]

QUAD_CATEGORIES = [
    ("profit", "size", "activity", "price"),
    ("cashflow", "size", "return", "activity"),
    ("quarter", "size", "price", "activity"),
    ("profit", "leverage", "return", "benchmark"),
    ("equity", "size", "activity", "return"),
    ("sales", "size", "price", "benchmark"),
    ("profit", "cashflow", "activity", "return"),
    ("quarter", "profit", "activity", "price"),
    ("other", "size", "return", "activity"),
    ("shares", "activity", "price", "return"),
    ("leverage", "equity", "profit", "cashflow"),
    ("size", "benchmark", "return", "activity"),
    ("sales", "profit", "cashflow", "size"),
    ("price", "benchmark", "activity", "return"),
    ("profit", "equity", "size", "benchmark"),
    ("cashflow", "leverage", "activity", "price"),
    ("quarter", "cashflow", "size", "return"),
    ("other", "profit", "price", "activity"),
    ("shares", "size", "profit", "return"),
    ("equity", "leverage", "activity", "benchmark"),
]

WINDOWS = [5, 10, 20, 30, 40, 60, 90, 120]
SMALL_WINDOWS = [5, 10, 20, 30, 40, 60]


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
        "kind": "rolling", "operator": op, "operand": x, "window": window
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
        "kind": "pair_rolling", "operator": op,
        "left": a, "right": b, "window": window,
    }


def Q(op: str, a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "comparison", "operator": op, "left": a, "right": b}


def L(op: str, a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {"kind": "logical", "operator": op, "left": a, "right": b}


def COND(
    condition: dict[str, Any],
    a: dict[str, Any],
    b: dict[str, Any],
) -> dict[str, Any]:
    return {
        "kind": "conditional",
        "condition": condition,
        "if_true": a,
        "if_false": b,
    }


def GN(x: dict[str, Any], group: str) -> dict[str, Any]:
    return {"kind": "group_neutralize", "operand": x, "group": group}


def FN(
    op: str,
    operands: list[dict[str, Any]],
    window: int | None = None,
    parameter: float | None = None,
) -> dict[str, Any]:
    out: dict[str, Any] = {"kind": "function", "operator": op, "operands": operands}
    if window is not None:
        out["window"] = window
    if parameter is not None:
        out["parameter"] = parameter
    return out


def RK(x: dict[str, Any]) -> dict[str, Any]:
    return U("rank", x)


def center(x: dict[str, Any]) -> dict[str, Any]:
    return B("sub", x, C(0.5))


PRIMITIVE_LABELS = {
    0: "均值状态",
    1: "波动状态",
    2: "趋势状态",
    3: "偏度状态",
    4: "变化状态",
    5: "衰减状态",
    6: "中位状态",
    7: "上尾状态",
    8: "分位状态",
    9: "残差状态",
    10: "时序位置",
    11: "极值时序",
    12: "现值均值偏离",
    13: "现值分位偏离",
    14: "趋势可信度",
    15: "变化波动",
    16: "上月极值偏离",
    17: "指数波动状态",
    18: "加权移动状态",
    19: "区间扩张状态",
}


def primitive(
    field: str,
    primitive_id: int,
    seed: int,
) -> dict[str, Any]:
    w = WINDOWS[(seed + primitive_id) % len(WINDOWS)]
    ws = SMALL_WINDOWS[(seed + primitive_id * 2) % len(SMALL_WINDOWS)]
    if primitive_id == 0:
        raw = R("mean", F(field), w)
    elif primitive_id == 1:
        raw = R("std", F(field), w)
    elif primitive_id == 2:
        raw = R("slope", F(field), w)
    elif primitive_id == 3:
        raw = R("skew", F(field), w)
    elif primitive_id == 4:
        raw = R("delta", F(field), w)
    elif primitive_id == 5:
        raw = R("decay_linear", F(field), w)
    elif primitive_id == 6:
        raw = R("median", F(field), w)
    elif primitive_id == 7:
        raw = R("topk_mean", F(field), w, max(1, w // 5))
    elif primitive_id == 8:
        raw = R("quantile", F(field), w, 0.75)
    elif primitive_id == 9:
        raw = R("resi", RK(F(field)), w)
    elif primitive_id == 10:
        raw = R("rank", F(field), w)
    elif primitive_id == 11:
        raw = B("sub", R("argmax", F(field), w), R("argmin", F(field), w))
    elif primitive_id == 12:
        raw = B("sub", RK(F(field)), RK(R("mean", F(field), w)))
    elif primitive_id == 13:
        raw = B(
            "sub",
            RK(F(field)),
            RK(R("quantile", F(field), w, 0.7)),
        )
    elif primitive_id == 14:
        raw = B(
            "mul",
            RK(R("slope", F(field), w)),
            R("rsquare", F(field), w),
        )
    elif primitive_id == 15:
        raw = B(
            "mul",
            RK(R("delta", F(field), ws)),
            RK(R("std", F(field), ws)),
        )
    elif primitive_id == 16:
        raw = B("sub", RK(F(field)), RK(FN("previous_month_max", [RK(F(field))])))
    elif primitive_id == 17:
        raw = FN("exp_weighted_std", [RK(F(field))], ws, 0.94)
    elif primitive_id == 18:
        raw = FN("wma", [RK(F(field))], w, 0.8)
    elif primitive_id == 19:
        raw = FN("cumulative_range", [RK(F(field))], w)
    else:
        raise ValueError(primitive_id)
    return RK(raw)


RECIPE_LABELS = {
    "R01": "双状态中心交互",
    "R02": "错配状态放大",
    "R03": "双状态瓶颈减第三状态",
    "R04": "双状态优势减第三状态",
    "R05": "状态绝对分歧",
    "R06": "双状态保守共识",
    "R07": "双状态强势共识",
    "R08": "分歧乘环境状态",
    "R09": "环境门控状态切换",
    "R10": "相对条件状态切换",
    "R11": "错配均值持续性",
    "R12": "错配波动性",
    "R13": "错配趋势性",
    "R14": "错配偏度性",
    "R15": "双状态滚动相关",
    "R16": "双状态滚动协方差",
    "R17": "相关环境交互",
    "R18": "Beta环境交互",
    "R19": "Alpha环境合成",
    "R20": "残差波动环境差",
    "R21": "四状态多回归残差",
    "R22": "条件掩码Beta",
    "R23": "双状态加权均值偏离",
    "R24": "指数波动相对状态",
    "R25": "指数累积联合状态",
    "R26": "累计区间相对状态",
    "R27": "加权移动相对状态",
    "R28": "上月极值相对状态",
    "R29": "组内双状态错配",
    "R30": "组内双状态交互",
    "R31": "组内滚动相关",
    "R32": "组内回归Alpha",
    "R33": "截面多空条件差",
    "R34": "截面加权状态差",
    "R35": "截面中位条件差",
    "R36": "双错配相关",
    "R37": "双错配协方差",
    "R38": "交互中位持续性",
    "R39": "交互上尾持续性",
    "R40": "交互路径残差",
    "R41": "双阈值联合门控",
    "R42": "双阈值择一门控",
    "R43": "双错配乘积",
    "R44": "双错配加和",
    "R45": "强弱区间交叉差",
    "R46": "双绝对错配差",
    "R47": "组内双错配乘积",
    "R48": "组内双错配加和",
    "R49": "相关减残差风险",
    "R50": "趋势相关联合确认",
}


def recipe(
    recipe_id: str,
    a: dict[str, Any],
    b: dict[str, Any],
    c: dict[str, Any],
    d: dict[str, Any],
    seed: int,
) -> dict[str, Any]:
    w = SMALL_WINDOWS[(seed + int(recipe_id[1:])) % len(SMALL_WINDOWS)]
    group = ["industry", "sector", "subindustry"][seed % 3]
    ab = B("sub", a, b)
    cd = B("sub", c, d)
    ia = B("mul", center(a), center(b))
    ic = B("mul", center(c), center(d))

    if recipe_id == "R01":
        return ia
    if recipe_id == "R02":
        return B("mul", ab, center(c))
    if recipe_id == "R03":
        return B("sub", B("min", a, b), c)
    if recipe_id == "R04":
        return B("sub", B("max", a, b), c)
    if recipe_id == "R05":
        return U("abs", ab)
    if recipe_id == "R06":
        return B("min", a, b)
    if recipe_id == "R07":
        return B("max", a, b)
    if recipe_id == "R08":
        return B("mul", U("abs", ab), center(c))
    if recipe_id == "R09":
        return COND(Q("gt", c, C(0.5)), a, b)
    if recipe_id == "R10":
        return COND(Q("gt", a, b), c, d)
    if recipe_id == "R11":
        return RK(R("mean", ab, w))
    if recipe_id == "R12":
        return RK(R("std", ab, w))
    if recipe_id == "R13":
        return RK(R("slope", ab, w))
    if recipe_id == "R14":
        return RK(R("skew", ab, w))
    if recipe_id == "R15":
        return PR("corr", a, b, w)
    if recipe_id == "R16":
        return PR("cov", a, b, w)
    if recipe_id == "R17":
        return B("mul", RK(PR("corr", a, b, w)), center(c))
    if recipe_id == "R18":
        return B(
            "mul",
            RK(FN("regression_beta", [a, b], w)),
            center(c),
        )
    if recipe_id == "R19":
        return B(
            "add",
            RK(FN("regression_alpha", [a, b], w)),
            center(c),
        )
    if recipe_id == "R20":
        return B(
            "sub",
            RK(FN("regression_resid_std", [a, b], w)),
            c,
        )
    if recipe_id == "R21":
        return RK(FN("multi_regression_residual", [a, b, c, d], w))
    if recipe_id == "R22":
        return RK(
            FN(
                "masked_regression_beta",
                [a, b, Q("gt", c, d)],
                w,
            )
        )
    if recipe_id == "R23":
        return B("sub", RK(FN("weighted_mean", [a, b], w)), c)
    if recipe_id == "R24":
        return B("sub", RK(FN("exp_weighted_std", [a], w, 0.94)), b)
    if recipe_id == "R25":
        return B(
            "add",
            RK(FN("exp_weighted_sum", [center(a)], w, 0.9)),
            center(b),
        )
    if recipe_id == "R26":
        return B("sub", RK(FN("cumulative_range", [a], w)), b)
    if recipe_id == "R27":
        return B("sub", RK(FN("wma", [a], w, 0.8)), b)
    if recipe_id == "R28":
        return B("sub", RK(FN("previous_month_max", [a])), b)
    if recipe_id == "R29":
        return GN(ab, group)
    if recipe_id == "R30":
        return GN(ia, group)
    if recipe_id == "R31":
        return GN(PR("corr", a, b, w), group)
    if recipe_id == "R32":
        return GN(FN("regression_alpha", [a, b], w), group)
    if recipe_id == "R33":
        return B(
            "sub",
            RK(FN("cross_section_long_short", [a, b], parameter=0.2)),
            c,
        )
    if recipe_id == "R34":
        return B(
            "sub",
            RK(FN("cross_section_weighted_mean", [a, b])),
            c,
        )
    if recipe_id == "R35":
        return B(
            "sub",
            RK(FN("cross_section_median_ratio", [a, b], parameter=0.2)),
            c,
        )
    if recipe_id == "R36":
        return PR("corr", ab, cd, w)
    if recipe_id == "R37":
        return PR("cov", ab, cd, w)
    if recipe_id == "R38":
        return RK(R("median", B("mul", center(a), center(b)), w))
    if recipe_id == "R39":
        return RK(
            R(
                "topk_mean",
                B("mul", center(a), center(b)),
                w,
                max(1, w // 5),
            )
        )
    if recipe_id == "R40":
        return RK(R("resi", B("mul", center(a), center(b)), w))
    if recipe_id == "R41":
        condition = L("and", Q("gt", a, C(0.5)), Q("gt", b, C(0.5)))
        return COND(condition, c, d)
    if recipe_id == "R42":
        condition = L("or", Q("gt", a, C(0.5)), Q("gt", b, C(0.5)))
        return COND(condition, c, d)
    if recipe_id == "R43":
        return B("mul", ab, cd)
    if recipe_id == "R44":
        return B("add", ab, cd)
    if recipe_id == "R45":
        return B("sub", B("max", a, b), B("min", c, d))
    if recipe_id == "R46":
        return B("sub", U("abs", ab), U("abs", cd))
    if recipe_id == "R47":
        return GN(B("mul", ab, cd), group)
    if recipe_id == "R48":
        return GN(B("add", ab, cd), group)
    if recipe_id == "R49":
        return B(
            "sub",
            RK(PR("corr", a, b, w)),
            RK(FN("regression_resid_std", [c, d], w)),
        )
    if recipe_id == "R50":
        return B(
            "mul",
            RK(R("slope", ab, w)),
            RK(PR("corr", c, d, w)),
        )
    raise ValueError(recipe_id)


@dataclass(frozen=True)
class Proposal:
    key: str
    recipe_id: str
    recipe_label: str
    categories: tuple[str, str, str, str]
    primitive_pattern: tuple[int, int, int, int]
    fields: tuple[str, str, str, str]
    name: str
    expr: dict[str, Any]
    rationale: str
    constraints: str


def used_features(node: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    def walk(value: Any) -> None:
        if isinstance(value, dict):
            if value.get("kind") == "feature":
                out.add(str(value["name"]))
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(node)
    return out


def category_for_feature(name: str) -> str:
    return FEATURE_TO_CATEGORY.get(name, "other")


def coarse_signature(node: dict[str, Any]) -> str:
    """Mechanism-level tree signature.

    Unlike validator.parameter_skeleton, this deliberately replaces concrete
    fields with broad economic categories and removes numeric parameters. It
    therefore catches 'same mechanism, nearby proxy' variants that static AST
    equality would otherwise allow.
    """
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
        walk(node), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def rationale_for(
    recipe_label: str,
    categories: tuple[str, str, str, str],
    primitive_pattern: tuple[int, int, int, int],
) -> str:
    ctext = "、".join(CATEGORY_LABEL[c] for c in categories)
    ptext = "、".join(PRIMITIVE_LABELS[p] for p in primitive_pattern)
    return (
        f"把{ctext}的{ptext}通过“{recipe_label}”机制组合。"
        "假设不同信息维度只有在其状态、持续性、错配或条件关系共同出现时，"
        "才形成更稳定的横截面预期收益差异；该结构有意避免单一字段或单一窗口的参数扫描。"
    )


def constraints_for(expr: dict[str, Any], categories: Iterable[str]) -> str:
    metrics = vc.expression_metrics(expr)
    bits = [
        "仅使用当期及历史数据；预热 NaN 不得填零；",
        f"完整 AST 最大历史依赖为 {metrics['lookback']} 个交易日（硬限制≤250）；",
    ]
    if set(categories) & FUNDAMENTAL_CATEGORIES:
        bits.append(
            "财务/股本类字段依赖 factors_lab 的 PIT 可得时点，低频披露可能形成阶梯型序列；"
        )
    bits.append("该候选通过机制级结构去重，避免仅替换相近代理变量形成同质化因子。")
    return "".join(bits)


def choose_field(category: str, seed: int) -> str:
    fields = CATEGORIES[category]
    return fields[seed % len(fields)]


PROPOSALS: list[Proposal] = []
proposal_counter = 0
recipe_ids = sorted(RECIPE_LABELS)

primitive_patterns = [
    (0, 1, 2, 4),
    (2, 5, 1, 8),
    (3, 6, 12, 13),
    (4, 1, 14, 10),
    (5, 7, 2, 9),
    (6, 8, 15, 3),
    (7, 9, 0, 11),
    (8, 10, 16, 1),
    (9, 11, 17, 4),
    (10, 12, 18, 5),
    (11, 13, 19, 6),
    (12, 14, 0, 7),
    (13, 15, 2, 8),
    (14, 16, 4, 9),
    (15, 17, 6, 10),
    (16, 18, 8, 11),
    (17, 19, 10, 12),
    (18, 0, 12, 13),
    (19, 2, 14, 15),
    (1, 4, 16, 18),
]

for r_index, recipe_id in enumerate(recipe_ids):
    for q_index, categories in enumerate(QUAD_CATEGORIES):
        for p_index, pattern in enumerate(primitive_patterns):
            proposal_counter += 1
            fields = tuple(
                choose_field(
                    category,
                    proposal_counter * (slot + 2) + r_index * 7 + p_index * 11,
                )
                for slot, category in enumerate(categories)
            )
            a = primitive(fields[0], pattern[0], proposal_counter + 1)
            b = primitive(fields[1], pattern[1], proposal_counter + 3)
            c = primitive(fields[2], pattern[2], proposal_counter + 5)
            d = primitive(fields[3], pattern[3], proposal_counter + 7)
            expr = recipe(recipe_id, a, b, c, d, proposal_counter)
            try:
                canonical = vc.canonicalize(expr, set(vc.ALLOWED_FEATURES))
                metrics = vc.expression_metrics(canonical)
                vc.validate_dimension(canonical)
            except Exception:
                continue
            if metrics["lookback"] > 250 or metrics["nodes"] > 64 or metrics["depth"] > 12:
                continue
            formula = vc.render_formula(canonical)
            label = RECIPE_LABELS[recipe_id]
            category_text = "-".join(CATEGORY_LABEL[x] for x in categories)
            primitive_text = "-".join(PRIMITIVE_LABELS[x] for x in pattern)
            name = (
                f"{label}-{category_text}-{primitive_text}-"
                f"{proposal_counter:05d}"
            )
            PROPOSALS.append(
                Proposal(
                    key=f"{recipe_id}-{proposal_counter:05d}",
                    recipe_id=recipe_id,
                    recipe_label=label,
                    categories=categories,
                    primitive_pattern=pattern,
                    fields=fields,
                    name=name,
                    expr=canonical,
                    rationale=rationale_for(label, categories, pattern),
                    constraints=constraints_for(canonical, categories),
                )
            )


def make_record(p: Proposal, source_record_id: str) -> dict[str, Any]:
    expr = vc.canonicalize(p.expr, set(vc.ALLOWED_FEATURES))
    return {
        "source_record_id": source_record_id,
        "name": p.name,
        "source": SOURCE,
        "source_ref": (
            f"LLM factor mining batch {BATCH_NAME} / "
            f"mechanism {p.recipe_id}"
        ),
        "formula_provenance": (
            "由经济/市场机制假设直接构造，并翻译为 factors_lab canonical AST；"
            "非论文或研报原文抄录。"
        ),
        "original_formula": vc.render_formula(expr),
        "economic_rationale": p.rationale,
        "source_constraints": p.constraints,
        "canonical_expression": expr,
    }


def build_bank_coarse_signatures(bank: dict[str, Any]) -> set[str]:
    signatures: set[str] = set()
    allowed = set(vc.ALLOWED_FEATURES)
    for item in bank["factors"]:
        raw = item.get("canonical_expression")
        if not isinstance(raw, dict):
            continue
        try:
            expr = vc.canonicalize(raw, allowed)
        except Exception:
            continue
        signatures.add(coarse_signature(expr))
    return signatures


def initial_payload() -> tuple[dict[str, Any], dict[str, Proposal]]:
    records: list[dict[str, Any]] = []
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
    by_recipe: dict[str, list[Proposal]] = defaultdict(list)
    for p in candidates:
        by_recipe[p.recipe_id].append(p)

    selected: list[Proposal] = []
    positions: dict[str, int] = defaultdict(int)
    recipe_used: Counter[str] = Counter()
    category_used: Counter[tuple[str, str, str, str]] = Counter()
    primitive_used: Counter[tuple[int, int, int, int]] = Counter()
    selected_coarse: set[str] = set()

    progress = True
    while len(selected) < TARGET and progress:
        progress = False
        for recipe_id in recipe_ids:
            if len(selected) >= TARGET:
                break
            if recipe_used[recipe_id] >= MAX_PER_RECIPE:
                continue
            pool = by_recipe.get(recipe_id, [])
            while positions[recipe_id] < len(pool):
                p = pool[positions[recipe_id]]
                positions[recipe_id] += 1
                sig = coarse_signature(p.expr)
                if sig in selected_coarse:
                    continue
                if category_used[p.categories] >= MAX_PER_CATEGORY_TUPLE:
                    continue
                if primitive_used[p.primitive_pattern] >= MAX_PER_PRIMITIVE_PATTERN:
                    continue
                selected.append(p)
                selected_coarse.add(sig)
                recipe_used[recipe_id] += 1
                category_used[p.categories] += 1
                primitive_used[p.primitive_pattern] += 1
                progress = True
                break

    if len(selected) < TARGET:
        raise RuntimeError(
            "insufficient diverse candidates: "
            f"selected={len(selected)} target={TARGET}; "
            f"recipe_counts={dict(recipe_used)}"
        )
    return selected


def main() -> int:
    bank = vc.load_bank(ROOT / "mother_bank")
    bank_coarse = build_bank_coarse_signatures(bank)
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

    coarse_bank_collisions = 0
    seen_clean_coarse: set[str] = set()
    clean: list[Proposal] = []
    for rec in initial_out["records"]:
        rid = rec["source_record_id"]
        if rid in warning_candidates or rid in error_candidates:
            continue
        p = by_id[rid]
        sig = coarse_signature(p.expr)
        if sig in bank_coarse:
            coarse_bank_collisions += 1
            continue
        if sig in seen_clean_coarse:
            continue
        seen_clean_coarse.add(sig)
        clean.append(p)

    selected = choose_balanced(clean)

    final_records = [
        make_record(p, f"FM-20261009-500V2-{idx:04d}")
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
            f"final validator rejected candidates: "
            f"{json.dumps(final_report, ensure_ascii=False)}"
        )
    if final_report["warning_count"] != 0:
        raise RuntimeError(
            f"final validator warnings remain: "
            f"{json.dumps(final_report, ensure_ascii=False)}"
        )

    final_coarse = [coarse_signature(p.expr) for p in selected]
    if len(set(final_coarse)) != TARGET:
        raise RuntimeError("mechanism-level coarse signatures are not unique")
    collisions = sum(sig in bank_coarse for sig in final_coarse)
    if collisions:
        raise RuntimeError(f"{collisions} selected mechanisms collide with mother bank")

    lookbacks = [vc.expression_metrics(p.expr)["lookback"] for p in selected]
    if max(lookbacks) > 250:
        raise RuntimeError(f"lookback hard limit violated: {max(lookbacks)}")

    recipe_counts = Counter(p.recipe_id for p in selected)
    category_counts = Counter(p.categories for p in selected)
    primitive_counts = Counter(p.primitive_pattern for p in selected)
    feature_counts = Counter()
    for p in selected:
        feature_counts.update(used_features(p.expr))

    selection = {
        "schema_version": 1,
        "batch_name": BATCH_NAME,
        "mother_bank_factor_count": final_report["mother_bank_factor_count"],
        "reference_files": final_report["reference_files"],
        "proposal_count": len(PROPOSALS),
        "validator_initial_accepted": initial_report["accepted_count"],
        "validator_initial_rejected": initial_report["rejected_count"],
        "validator_initial_warnings": initial_report["warning_count"],
        "mechanism_coarse_bank_collisions_removed": coarse_bank_collisions,
        "clean_unique_mechanism_count": len(clean),
        "selected_count": len(selected),
        "selected_unique_mechanism_signatures": len(set(final_coarse)),
        "selected_mother_bank_mechanism_collisions": collisions,
        "max_lookback": max(lookbacks),
        "lookback_over_250": sum(value > 250 for value in lookbacks),
        "lookback_distribution": dict(sorted(Counter(lookbacks).items())),
        "recipe_count": len(recipe_counts),
        "recipe_counts": dict(sorted(recipe_counts.items())),
        "max_per_recipe": max(recipe_counts.values()),
        "category_tuple_count": len(category_counts),
        "max_per_category_tuple": max(category_counts.values()),
        "primitive_pattern_count": len(primitive_counts),
        "max_per_primitive_pattern": max(primitive_counts.values()),
        "top_features": feature_counts.most_common(30),
    }

    ROOT_OUTPUT.write_text(
        json.dumps(final_out, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    AUDIT_OUTPUT.write_text(
        json.dumps(
            {
                "selection": selection,
                "final_validator_report": final_report,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    SELECTION_OUTPUT.write_text(
        json.dumps(selection, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "proposal_count": len(PROPOSALS),
                "mother_bank_factor_count": final_report["mother_bank_factor_count"],
                "clean_unique_mechanism_count": len(clean),
                "selected_count": len(selected),
                "recipe_count": len(recipe_counts),
                "max_recipe_size": max(recipe_counts.values()),
                "coarse_bank_collisions_removed": coarse_bank_collisions,
                "warning_count": final_report["warning_count"],
                "max_lookback": max(lookbacks),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
