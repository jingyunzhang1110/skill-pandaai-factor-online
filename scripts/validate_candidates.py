#!/usr/bin/env python3
"""Validate and deduplicate factors_lab candidate ASTs against the bundled mother bank.

The canonical_expression AST is authoritative. Human-readable formulas are rendered from it.
This module intentionally mirrors the public contract of factor_common.factor.ast at the
snapshot recorded in mother_bank/MANIFEST.json without importing factors_lab itself.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BANK = ROOT / "mother_bank"

UNARY = {"abs", "neg", "sign", "log", "exp", "sqrt", "rank", "zscore"}
BINARY = {"add", "sub", "mul", "div", "pow", "signed_power", "max", "min"}
COMMUTATIVE_BINARY = {"add", "mul", "max", "min"}
ROLLING = {
    "mean", "std", "sum", "product", "min", "max", "rank", "delta", "delay",
    "argmax", "argmin", "decay_linear", "quantile", "slope", "rsquare", "resi",
    "sma", "median", "topk_mean", "skew",
}
PAIR_ROLLING = {"corr", "cov"}
COMPARISON = {"lt", "le", "gt", "ge", "eq", "ne"}
LOGICAL = {"and", "or"}
FUNCTION_SPECS: dict[str, tuple[int, bool, bool]] = {
    "weighted_mean": (2, True, False),
    "regression_alpha": (2, True, False),
    "regression_beta": (2, True, False),
    "regression_resid_std": (2, True, False),
    "masked_regression_beta": (3, True, False),
    "multi_regression_residual": (4, True, False),
    "monthly_regression_alpha": (2, True, False),
    "monthly_beta_resid_product": (2, True, False),
    "previous_month_max": (1, False, False),
    "exp_weighted_sum": (1, True, True),
    "exp_weighted_std": (1, True, True),
    "cmra": (1, True, True),
    "cumulative_range": (1, True, False),
    "wma": (1, True, True),
    "cross_section_long_short": (2, False, True),
    "cross_section_weighted_mean": (2, False, False),
    "cross_section_median_ratio": (2, False, True),
}
GROUPS = {"industry", "sector", "subindustry"}

# Strict factors_lab mining whitelist. This is intentionally narrower than
# "any column the loader might happen to see": every generated factor must use
# a canonical field that the current factors_lab panel layer knows how to
# materialise with point-in-time semantics.
ALLOWED_FEATURES = {
    "adj_close", "aggregate_book_value", "aggregate_earnings",
    "aggregate_market_cap", "amount", "avg_total_assets", "basic_eps",
    "benchmark_close", "benchmark_open", "book_equity", "book_to_price",
    "cap", "capex", "cfo", "cfo_q", "cfo_ttm", "close", "common_equity",
    "dividend", "dividend_1y", "earnings", "ebit", "ebitda",
    "enterprise_value", "executive_compensation_top3", "factor_return",
    "float_cap_weighted_market_index", "float_market_cap", "float_shares",
    "free_cash_flow", "gross_profit", "hd", "high", "holder_avgpct",
    "illiq_3m", "interest_bearing_debt", "ld", "long_term_debt", "low",
    "market_cap", "mkt_freeshares", "net_cash_flow", "net_income",
    "net_income_ex_nr", "net_income_ex_nr_q", "net_income_ex_nr_ttm",
    "net_income_q", "net_income_ttm", "open", "operating_profit_q",
    "operating_profit_ttm", "parent_equity_ex_minority",
    "parent_net_income", "parent_net_income_q", "parent_net_income_ttm",
    "preferred_equity", "ret", "returns", "sales", "sales_q", "sales_ttm",
    "self", "sse_composite_close", "stom_month", "total_assets",
    "total_debt", "tr", "turnover", "volume", "vwap",
}

AST_KEYS = {
    "feature": {"kind", "name", "lag"},
    "constant": {"kind", "value"},
    "unary": {"kind", "operator", "operand"},
    "binary": {"kind", "operator", "left", "right"},
    "rolling": {"kind", "operator", "operand", "window", "min_periods", "parameter"},
    "pair_rolling": {"kind", "operator", "left", "right", "window", "min_periods"},
    "comparison": {"kind", "operator", "left", "right"},
    "logical": {"kind", "operator", "left", "right"},
    "conditional": {"kind", "condition", "if_true", "if_false"},
    "scale": {"kind", "operand", "target"},
    "group_neutralize": {"kind", "operand", "group"},
    "function": {"kind", "operator", "operands", "window", "parameter"},
}

MAX_NODES = 64
MAX_DEPTH = 12
MAX_LOOKBACK = 2520

# Mirrors factors_lab FeatureDimensionCatalog.default() where the dimension is
# known. Missing entries deliberately remain "unknown", matching factors_lab.
DIMENSIONLESS_FEATURES = {
    "returns", "ret", "book_to_price", "illiq_3m", "factor_return",
}
PRICE_FEATURES = {
    "open", "high", "low", "close", "vwap", "benchmark_close",
    "benchmark_open", "sse_composite_close", "float_cap_weighted_market_index",
}
SHARES_FEATURES = {"volume"}
MONEY_FEATURES = {"amount", "cap", "market_cap", "float_market_cap", "book_equity"}

# Conservative positivity set used only for safe rank-equivalence proofs.
STRICT_POSITIVE_FEATURES = {
    "open", "high", "low", "close", "adj_close", "vwap", "market_cap",
    "float_market_cap", "cap", "mkt_freeshares", "float_shares",
}
NONNEGATIVE_FEATURES = STRICT_POSITIVE_FEATURES | {"volume", "amount", "turnover", "stom_month"}
FUTURE_TOKENS = re.compile(r"future|forward|next|label|target|return_t_plus", re.I)


class ValidationError(ValueError):
    pass


def _compact(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValidationError(f"{label} must be numeric")
    out = float(value)
    if not math.isfinite(out):
        raise ValidationError(f"{label} must be finite")
    return out


def _reference_records_from_payload(data: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    if isinstance(data.get("factors"), list):
        records = data["factors"]
    elif isinstance(data.get("records"), list):
        records = data["records"]
    else:
        raise ValidationError(
            f"reference JSON must contain a factors or records list: {path}"
        )

    output: list[dict[str, Any]] = []
    for index, raw in enumerate(records, start=1):
        if not isinstance(raw, dict):
            raise ValidationError(
                f"reference record must be an object: {path} record {index}"
            )
        expression = raw.get("canonical_expression")
        if not isinstance(expression, dict):
            # Provenance-only historical records cannot participate in AST dedup.
            continue
        item = dict(raw)
        item["_reference_file"] = path.name
        output.append(item)
    return output


def load_bank(path: Path = DEFAULT_BANK) -> dict[str, Any]:
    """Load all local reference-factor JSONs.

    The Skill is standalone. When path is a directory, every JSON file in it
    except MANIFEST.json is treated as a local reference source. Both the
    bundled 549-factor snapshot (factors list) and later direct-import batch
    files (records list) are supported.
    """
    source = Path(path)
    if source.is_file():
        files = [source]
    elif source.is_dir():
        files = sorted(
            item
            for item in source.glob("*.json")
            if item.is_file() and item.name.casefold() != "manifest.json"
        )
        if not files:
            raise ValidationError(f"reference directory contains no factor JSON: {source}")
    else:
        raise ValidationError(f"reference path not found: {source}")

    factors: list[dict[str, Any]] = []
    loaded_files: list[str] = []
    for item in files:
        try:
            data = json.loads(item.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValidationError(f"cannot read reference JSON {item}: {exc}") from exc
        if not isinstance(data, dict):
            raise ValidationError(f"reference JSON top level must be an object: {item}")
        factors.extend(_reference_records_from_payload(data, item))
        loaded_files.append(item.name)

    return {
        "factors": factors,
        "reference_files": loaded_files,
        "reference_file_count": len(loaded_files),
    }


def bank_features(bank: dict[str, Any]) -> set[str]:
    # Kept as a function for existing callers/tests; the contract is static and
    # authoritative, not inferred from whatever happens to exist in the bank.
    return set(ALLOWED_FEATURES)


def canonicalize(node: Any, allowed_features: set[str]) -> dict[str, Any]:
    if not isinstance(node, dict):
        raise ValidationError("expression node must be an object")
    kind = str(node.get("kind", "")).strip().lower()
    allowed_keys = AST_KEYS.get(kind)
    if allowed_keys is None:
        raise ValidationError(f"unknown expression kind {kind!r}")
    extra_keys = sorted(set(node) - allowed_keys)
    if extra_keys:
        raise ValidationError(
            f"{kind} contains unsupported keys: {', '.join(extra_keys)}"
        )

    if kind == "feature":
        name = str(node.get("name", "")).strip().casefold()
        if not name:
            raise ValidationError("feature name cannot be empty")
        if name not in allowed_features:
            raise ValidationError(f"unsupported feature {name!r}")
        if FUTURE_TOKENS.search(name):
            raise ValidationError(f"future/label-like feature is forbidden: {name!r}")
        lag = node.get("lag", 0)
        if isinstance(lag, bool) or not isinstance(lag, int) or lag < 0:
            raise ValidationError("feature lag must be a non-negative integer")
        return {"kind": "feature", "name": name, "lag": lag}

    if kind == "constant":
        value = _finite_number(node.get("value"), "constant")
        if value == 0:
            value = 0.0
        return {"kind": "constant", "value": value}

    if kind == "unary":
        op = str(node.get("operator", "")).strip().lower()
        if op not in UNARY:
            raise ValidationError(f"unsupported unary operator {op!r}")
        return {"kind": "unary", "operator": op,
                "operand": canonicalize(node.get("operand"), allowed_features)}

    if kind == "binary":
        op = str(node.get("operator", "")).strip().lower()
        if op not in BINARY:
            raise ValidationError(f"unsupported binary operator {op!r}")
        left = canonicalize(node.get("left"), allowed_features)
        right = canonicalize(node.get("right"), allowed_features)
        if op in COMMUTATIVE_BINARY and _compact(right) < _compact(left):
            left, right = right, left
        return {"kind": "binary", "operator": op, "left": left, "right": right}

    if kind == "rolling":
        op = str(node.get("operator", "")).strip().lower()
        if op not in ROLLING:
            raise ValidationError(f"unsupported rolling operator {op!r}")
        window = node.get("window")
        if isinstance(window, bool) or not isinstance(window, int) or window <= 0:
            raise ValidationError("rolling window must be a positive integer")
        out: dict[str, Any] = {
            "kind": "rolling", "operator": op,
            "operand": canonicalize(node.get("operand"), allowed_features),
            "window": window,
        }
        if node.get("min_periods") is not None:
            mp = node["min_periods"]
            if isinstance(mp, bool) or not isinstance(mp, int) or not 1 <= mp <= window:
                raise ValidationError("min_periods must be within [1, window]")
            out["min_periods"] = mp
        parameter = node.get("parameter")
        if op == "quantile":
            value = _finite_number(parameter, "quantile parameter")
            if not 0 <= value <= 1:
                raise ValidationError("quantile parameter must be within [0,1]")
            out["parameter"] = value
        elif op == "sma":
            value = _finite_number(parameter, "sma parameter")
            if not 0 < value <= window:
                raise ValidationError("sma parameter must be within (0,window]")
            out["parameter"] = value
        elif op == "topk_mean":
            value = _finite_number(parameter, "topk_mean parameter")
            if not 1 <= int(value) <= window or value != int(value):
                raise ValidationError("topk_mean parameter must be an integer in [1,window]")
            out["parameter"] = value
        elif parameter is not None:
            raise ValidationError(f"rolling operator {op!r} does not take a parameter")
        return out

    if kind == "pair_rolling":
        op = str(node.get("operator", "")).strip().lower()
        if op not in PAIR_ROLLING:
            raise ValidationError(f"unsupported pair_rolling operator {op!r}")
        window = node.get("window")
        if isinstance(window, bool) or not isinstance(window, int) or window <= 0:
            raise ValidationError("pair rolling window must be a positive integer")
        left = canonicalize(node.get("left"), allowed_features)
        right = canonicalize(node.get("right"), allowed_features)
        if _compact(right) < _compact(left):
            left, right = right, left
        out = {"kind": "pair_rolling", "operator": op, "left": left, "right": right,
               "window": window}
        if node.get("min_periods") is not None:
            mp = node["min_periods"]
            if isinstance(mp, bool) or not isinstance(mp, int) or not 1 <= mp <= window:
                raise ValidationError("min_periods must be within [1, window]")
            out["min_periods"] = mp
        return out

    if kind == "comparison":
        op = str(node.get("operator", "")).strip().lower()
        if op not in COMPARISON:
            raise ValidationError(f"unsupported comparison operator {op!r}")
        return {"kind": "comparison", "operator": op,
                "left": canonicalize(node.get("left"), allowed_features),
                "right": canonicalize(node.get("right"), allowed_features)}

    if kind == "logical":
        op = str(node.get("operator", "")).strip().lower()
        if op not in LOGICAL:
            raise ValidationError(f"unsupported logical operator {op!r}")
        left = canonicalize(node.get("left"), allowed_features)
        right = canonicalize(node.get("right"), allowed_features)
        if _compact(right) < _compact(left):
            left, right = right, left
        return {"kind": "logical", "operator": op, "left": left, "right": right}

    if kind == "conditional":
        return {"kind": "conditional",
                "condition": canonicalize(node.get("condition"), allowed_features),
                "if_true": canonicalize(node.get("if_true"), allowed_features),
                "if_false": canonicalize(node.get("if_false"), allowed_features)}

    if kind == "scale":
        target = _finite_number(node.get("target", 1.0), "scale target")
        if target <= 0:
            raise ValidationError("scale target must be positive")
        return {"kind": "scale", "operand": canonicalize(node.get("operand"), allowed_features),
                "target": target}

    if kind == "group_neutralize":
        group = str(node.get("group", "")).strip().casefold()
        if group not in GROUPS:
            raise ValidationError(f"unsupported neutralization group {group!r}")
        return {"kind": "group_neutralize",
                "operand": canonicalize(node.get("operand"), allowed_features),
                "group": group}

    if kind == "function":
        op = str(node.get("operator", "")).strip().lower()
        if op not in FUNCTION_SPECS:
            raise ValidationError(f"unsupported function operator {op!r}")
        arity, needs_window, needs_parameter = FUNCTION_SPECS[op]
        operands_raw = node.get("operands")
        if not isinstance(operands_raw, list) or len(operands_raw) != arity:
            raise ValidationError(f"{op} requires {arity} operands")
        out: dict[str, Any] = {"kind": "function", "operator": op,
                               "operands": [canonicalize(x, allowed_features) for x in operands_raw]}
        if needs_window:
            window = node.get("window")
            if isinstance(window, bool) or not isinstance(window, int) or window <= 0:
                raise ValidationError(f"{op} requires a positive integer window")
            out["window"] = window
        elif node.get("window") is not None:
            raise ValidationError(f"{op} does not take a window")
        if needs_parameter:
            value = _finite_number(node.get("parameter"), f"{op} parameter")
            if op in {"cross_section_long_short", "cross_section_median_ratio"}:
                if not 0 < value <= 0.5:
                    raise ValidationError(f"{op} parameter must be within (0,0.5]")
            elif op in {"exp_weighted_sum", "exp_weighted_std", "cmra"} and value <= 0:
                raise ValidationError(f"{op} parameter must be positive")
            elif op == "wma" and not 0 < value <= 1:
                raise ValidationError("wma parameter must be within (0,1]")
            out["parameter"] = value
        elif node.get("parameter") is not None:
            raise ValidationError(f"{op} does not take a parameter")
        return out

    raise ValidationError(f"unknown expression kind {kind!r}")


def fingerprint(expr: dict[str, Any]) -> str:
    return hashlib.sha256(_compact(expr).encode("utf-8")).hexdigest()


def is_constant(node: dict[str, Any], value: float | None = None) -> bool:
    if node.get("kind") != "constant":
        return False
    return value is None or float(node["value"]) == float(value)


def constant_value(node: dict[str, Any]) -> float | None:
    return float(node["value"]) if node.get("kind") == "constant" else None


def provably_positive(node: dict[str, Any]) -> bool:
    kind = node["kind"]
    if kind == "feature":
        return node["name"] in STRICT_POSITIVE_FEATURES
    if kind == "constant":
        return float(node["value"]) > 0
    if kind == "unary":
        op = node["operator"]
        if op == "exp":
            return True
        if op == "sqrt":
            return provably_positive(node["operand"])
        return False
    if kind == "scale":
        return provably_positive(node["operand"])
    if kind == "binary":
        op, left, right = node["operator"], node["left"], node["right"]
        if op in {"mul", "div"}:
            return provably_positive(left) and provably_positive(right)
        if op == "add":
            return provably_positive(left) and provably_positive(right)
        if op == "pow":
            exponent = constant_value(right)
            return provably_positive(left) and exponent is not None
        if op in {"max", "min"}:
            return provably_positive(left) and provably_positive(right)
    if kind == "rolling":
        return node["operator"] in {"mean", "sum", "min", "max", "product", "delay"} and provably_positive(node["operand"])
    return False


def provably_nonnegative(node: dict[str, Any]) -> bool:
    if provably_positive(node):
        return True
    kind = node["kind"]
    if kind == "feature":
        return node["name"] in NONNEGATIVE_FEATURES
    if kind == "constant":
        return float(node["value"]) >= 0
    if kind == "unary" and node["operator"] in {"abs", "sqrt"}:
        return True
    if kind == "binary" and node["operator"] in {"mul", "div"}:
        return provably_nonnegative(node["left"]) and provably_positive(node["right"])
    if kind == "scale":
        return provably_nonnegative(node["operand"])
    return False


def _boolean_node(node: dict[str, Any]) -> bool:
    return node["kind"] in {"comparison", "logical"}


def _rank_signature(node: dict[str, Any]) -> tuple[str, int]:
    """Return (ordering key, orientation). Orientation is +1 or -1 vs canonical key.

    The rules are deliberately conservative: only statically provable monotonic transforms
    are removed. The key ignores direction metadata so reverse-order aliases remain duplicates.
    """
    kind = node["kind"]

    if kind == "unary":
        op, child = node["operator"], node["operand"]
        key, orient = _rank_signature(child)
        if op in {"rank", "zscore", "exp"}:
            return key, orient
        if op == "neg":
            return key, -orient
        if op == "abs" and provably_nonnegative(child):
            return key, orient
        if op in {"log", "sqrt"} and provably_positive(child):
            return key, orient
        return _compact(node), 1

    if kind == "scale":
        return _rank_signature(node["operand"])

    if kind == "binary":
        op, left, right = node["operator"], node["left"], node["right"]
        lv, rv = constant_value(left), constant_value(right)
        if op == "add":
            if lv is not None:
                return _rank_signature(right)
            if rv is not None:
                return _rank_signature(left)
        if op == "sub":
            if rv is not None:
                return _rank_signature(left)
            if lv is not None:
                key, orient = _rank_signature(right)
                return key, -orient
        if op == "mul":
            if lv is not None and lv != 0:
                key, orient = _rank_signature(right)
                return key, orient if lv > 0 else -orient
            if rv is not None and rv != 0:
                key, orient = _rank_signature(left)
                return key, orient if rv > 0 else -orient
        if op == "div":
            if rv is not None and rv != 0:
                key, orient = _rank_signature(left)
                return key, orient if rv > 0 else -orient
            if lv is not None and lv != 0 and provably_positive(right):
                key, orient = _rank_signature(right)
                return key, -orient if lv > 0 else orient
            if provably_positive(left) and provably_positive(right):
                a, b = _compact(left), _compact(right)
                if a <= b:
                    return f"positive_ratio({a},{b})", 1
                return f"positive_ratio({b},{a})", -1
        if op in {"pow", "signed_power"}:
            exponent = rv
            if exponent is not None and exponent > 0:
                if op == "signed_power" or provably_positive(left):
                    return _rank_signature(left)
            if exponent is not None and exponent < 0 and provably_positive(left):
                key, orient = _rank_signature(left)
                return key, -orient
        return _compact(node), 1

    # SUM(boolean,N)/N == MEAN(boolean,N) is handled by the div branch above only when
    # the division is outermost, so normalize rolling mean/sum here to a shared key.
    if kind == "rolling":
        op = node["operator"]
        if op == "mean" and _boolean_node(node["operand"]):
            return f"boolfreq({_compact(node['operand'])},{node['window']})", 1
        return _compact(node), 1

    return _compact(node), 1


def rank_signature(node: dict[str, Any]) -> tuple[str, int]:
    # Special exact normalization: SUM(condition,N)/N versus MEAN(condition,N).
    if node.get("kind") == "binary" and node.get("operator") == "div":
        left, right = node["left"], node["right"]
        if (left.get("kind") == "rolling" and left.get("operator") == "sum"
                and _boolean_node(left["operand"]) and is_constant(right, left["window"])):
            return f"boolfreq({_compact(left['operand'])},{left['window']})", 1
    return _rank_signature(node)


def parameter_skeleton(node: dict[str, Any]) -> str:
    """Expression shape for within-batch diversity; removes windows/numeric constants."""
    def walk(x: Any) -> Any:
        if isinstance(x, list):
            return [walk(v) for v in x]
        if not isinstance(x, dict):
            return x
        kind = x.get("kind")
        if kind == "constant":
            return {"kind": "constant", "value": "#"}
        out: dict[str, Any] = {}
        for key, value in x.items():
            if key in {"window", "min_periods", "parameter", "target"}:
                out[key] = "#"
            elif key == "lag" and kind == "feature":
                out[key] = "#" if int(value) else 0
            else:
                out[key] = walk(value)
        return out
    return _compact(walk(node))


def contains_zero_mask(node: dict[str, Any]) -> bool:
    if node["kind"] == "conditional":
        t, f = node["if_true"], node["if_false"]
        if (is_constant(t, 0) and f["kind"] != "constant") or (is_constant(f, 0) and t["kind"] != "constant"):
            return True
    for value in node.values():
        if isinstance(value, dict) and contains_zero_mask(value):
            return True
        if isinstance(value, list) and any(isinstance(v, dict) and contains_zero_mask(v) for v in value):
            return True
    return False


def denominator_warnings(node: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    def walk(x: dict[str, Any]) -> None:
        if x.get("kind") == "binary" and x.get("operator") == "div":
            denom = x["right"]
            if not provably_positive(denom) and not (denom.get("kind") == "constant" and denom.get("value") != 0):
                warnings.append("division denominator is not statically proven away from zero")
        for value in x.values():
            if isinstance(value, dict):
                walk(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        walk(item)
    walk(node)
    return warnings


def expression_metrics(node: dict[str, Any]) -> dict[str, int]:
    def rec(x: dict[str, Any]) -> tuple[int, int, int, int]:
        children: list[dict[str, Any]] = []
        for value in x.values():
            if isinstance(value, dict) and "kind" in value:
                children.append(value)
            elif isinstance(value, list):
                children.extend(v for v in value if isinstance(v, dict) and "kind" in v)
        child_stats = [rec(c) for c in children]
        nodes = 1 + sum(s[0] for s in child_stats)
        depth = 1 + max((s[1] for s in child_stats), default=0)
        operators = (0 if x["kind"] in {"feature", "constant"} else 1) + sum(s[2] for s in child_stats)
        base = max((s[3] for s in child_stats), default=0)
        kind = x["kind"]
        if kind == "feature":
            lookback = int(x.get("lag", 0))
        elif kind in {"rolling", "pair_rolling"}:
            w = int(x["window"])
            extra = w if kind == "rolling" and x["operator"] in {"delta", "delay"} else w - 1
            lookback = base + extra
        elif kind == "function":
            op = x.get("operator")
            if op in {"cross_section_long_short", "cross_section_weighted_mean", "cross_section_median_ratio"}:
                lookback = base
            elif op == "previous_month_max":
                lookback = base + 62
            elif op in {"monthly_regression_alpha", "monthly_beta_resid_product"}:
                lookback = base + int(x["window"]) * 21 + 21
            elif x.get("window") is not None:
                lookback = base + int(x["window"]) - 1
            else:
                lookback = base
        else:
            lookback = base
        return nodes, depth, operators, lookback
    n, d, o, l = rec(node)
    return {"nodes": n, "depth": d, "operators": o, "lookback": l}


def render_formula(node: dict[str, Any]) -> str:
    kind = node["kind"]
    if kind == "feature":
        name = node["name"]
        return name if node.get("lag", 0) == 0 else f"delay({name},{node['lag']})"
    if kind == "constant":
        value = float(node["value"])
        return str(int(value)) if value.is_integer() else repr(value)
    if kind == "unary":
        return f"{node['operator']}({render_formula(node['operand'])})"
    if kind == "binary":
        l, r, op = render_formula(node["left"]), render_formula(node["right"]), node["operator"]
        symbols = {"add": "+", "sub": "-", "mul": "*", "div": "/", "pow": "^"}
        if op in symbols:
            return f"({l}{symbols[op]}{r})"
        return f"{op}({l},{r})"
    if kind == "rolling":
        extras = []
        if "min_periods" in node:
            extras.append(f"min_periods={node['min_periods']}")
        if "parameter" in node:
            extras.append(f"parameter={node['parameter']}")
        suffix = ("," + ",".join(extras)) if extras else ""
        return f"{node['operator']}({render_formula(node['operand'])},{node['window']}{suffix})"
    if kind == "pair_rolling":
        return f"{node['operator']}({render_formula(node['left'])},{render_formula(node['right'])},{node['window']})"
    if kind in {"comparison", "logical"}:
        symbols = {"lt": "<", "le": "<=", "gt": ">", "ge": ">=", "eq": "==", "ne": "!=", "and": "&", "or": "|"}
        return f"({render_formula(node['left'])}{symbols[node['operator']]}{render_formula(node['right'])})"
    if kind == "conditional":
        return f"if({render_formula(node['condition'])},{render_formula(node['if_true'])},{render_formula(node['if_false'])})"
    if kind == "scale":
        return f"scale({render_formula(node['operand'])},{node['target']})"
    if kind == "group_neutralize":
        return f"group_neutralize({render_formula(node['operand'])},{node['group']})"
    if kind == "function":
        args = [render_formula(x) for x in node["operands"]]
        if "window" in node:
            args.append(str(node["window"]))
        if "parameter" in node:
            args.append(str(node["parameter"]))
        return f"{node['operator']}({','.join(args)})"
    raise AssertionError(kind)


def _dim_add(a: tuple[int, int, int] | None, b: tuple[int, int, int] | None) -> tuple[int, int, int] | None:
    if a is None or b is None:
        return None
    return tuple(x + y for x, y in zip(a, b))


def _dim_sub(a: tuple[int, int, int] | None, b: tuple[int, int, int] | None) -> tuple[int, int, int] | None:
    if a is None or b is None:
        return None
    return tuple(x - y for x, y in zip(a, b))


def validate_dimension(node: dict[str, Any]) -> tuple[int, int, int] | None:
    dimless = (0, 0, 0)
    price = (1, 0, 0)
    shares = (0, 1, 0)
    money = (1, 1, 0)
    kind = node["kind"]

    if kind == "constant":
        return dimless
    if kind == "feature":
        name = node["name"]
        if name in DIMENSIONLESS_FEATURES:
            return dimless
        if name in PRICE_FEATURES:
            return price
        if name in SHARES_FEATURES:
            return shares
        if name in MONEY_FEATURES:
            return money
        return None
    if kind == "unary":
        operand = validate_dimension(node["operand"])
        op = node["operator"]
        if op in {"abs", "neg"}:
            return operand
        if op in {"sign", "rank", "zscore"}:
            return dimless
        if op in {"log", "exp"}:
            if operand is not None and operand != dimless:
                raise ValidationError(f"{op} requires dimensionless input")
            return operand
        if op == "sqrt":
            if operand is None:
                return None
            if any(value % 2 for value in operand):
                raise ValidationError("sqrt requires an exact even physical dimension")
            return tuple(value // 2 for value in operand)
    if kind == "binary":
        left = validate_dimension(node["left"])
        right = validate_dimension(node["right"])
        op = node["operator"]
        if op in {"add", "sub", "max", "min"}:
            if left is None or right is None:
                return None
            if left != right:
                raise ValidationError(
                    f"{op} requires equal dimensions, got {left} and {right}"
                )
            return left
        if op == "mul":
            return _dim_add(left, right)
        if op == "div":
            return _dim_sub(left, right)
        if op in {"pow", "signed_power"}:
            if left is None:
                return None
            if left == dimless:
                return dimless
            exponent = node["right"]
            if exponent.get("kind") != "constant":
                if op == "pow":
                    raise ValidationError("pow on dimensioned input requires integer constant exponent")
                return None
            value = float(exponent["value"])
            if int(value) != value:
                if op == "pow":
                    raise ValidationError("pow on dimensioned input requires integer constant exponent")
                return None
            return tuple(x * int(value) for x in left)
    if kind == "rolling":
        operand = validate_dimension(node["operand"])
        if node["operator"] in {"rank", "argmax", "argmin", "rsquare", "skew"}:
            return dimless
        return operand
    if kind == "pair_rolling":
        left = validate_dimension(node["left"])
        right = validate_dimension(node["right"])
        return dimless if node["operator"] == "corr" else _dim_add(left, right)
    if kind in {"comparison", "logical"}:
        if kind == "comparison":
            validate_dimension(node["left"])
            validate_dimension(node["right"])
        else:
            validate_dimension(node["left"])
            validate_dimension(node["right"])
        return dimless
    if kind == "conditional":
        validate_dimension(node["condition"])
        a = validate_dimension(node["if_true"])
        b = validate_dimension(node["if_false"])
        if a is None or b is None:
            return None
        if a != b:
            raise ValidationError(
                f"conditional branches require equal dimensions, got {a} and {b}"
            )
        return a
    if kind in {"scale", "group_neutralize"}:
        return validate_dimension(node["operand"])
    if kind == "function":
        dims = [validate_dimension(x) for x in node["operands"]]
        op = node["operator"]
        if op in {
            "weighted_mean", "previous_month_max", "exp_weighted_sum",
            "exp_weighted_std", "cumulative_range", "wma",
            "cross_section_weighted_mean", "regression_alpha",
            "regression_resid_std", "multi_regression_residual",
        }:
            return dims[0]
        if op in {"regression_beta", "masked_regression_beta"}:
            return _dim_sub(dims[0], dims[1])
        if op in {
            "monthly_regression_alpha", "monthly_beta_resid_product",
            "cmra", "cross_section_median_ratio",
        }:
            return dimless
        if op == "cross_section_long_short":
            return dims[1]
        return None
    raise ValidationError(f"cannot infer dimension for kind {kind!r}")


def _bank_indexes(bank: dict[str, Any], allowed_features: set[str]) -> tuple[dict[str, list[dict]], dict[str, list[dict]], dict[str, list[dict]]]:
    exact: dict[str, list[dict]] = {}
    ranked: dict[str, list[dict]] = {}
    skeleton: dict[str, list[dict]] = {}
    for factor in bank["factors"]:
        raw = factor.get("canonical_expression")
        if not isinstance(raw, dict):
            continue
        try:
            expr = canonicalize(raw, allowed_features)
        except ValidationError:
            # The bank itself is trusted; this protects refreshes where the local validator is older.
            continue
        exact.setdefault(fingerprint(expr), []).append(factor)
        rkey, _ = rank_signature(expr)
        ranked.setdefault(rkey, []).append(factor)
        skeleton.setdefault(parameter_skeleton(expr), []).append(factor)
    return exact, ranked, skeleton


def _candidate_label(item: dict[str, Any], index: int) -> str:
    return str(item.get("source_record_id") or item.get("name") or f"record-{index+1}")


def validate_batch(payload: dict[str, Any], bank: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValidationError("input must be a JSON object")
    allowed_top = {"schema_version", "batch_name", "source", "records"}
    extra_top = sorted(set(payload) - allowed_top)
    if extra_top:
        raise ValidationError(f"unsupported top-level keys: {', '.join(extra_top)}")
    if payload.get("schema_version") != 1:
        raise ValidationError("schema_version must be 1")
    batch_name = str(payload.get("batch_name") or "").strip()
    source = str(payload.get("source") or "").strip()
    records = payload.get("records")
    if not batch_name:
        raise ValidationError("batch_name is required")
    if not source:
        raise ValidationError("source is required")
    if not isinstance(records, list) or not records:
        raise ValidationError("records must be a non-empty list")

    allowed = set(ALLOWED_FEATURES)
    exact_bank, rank_bank, skeleton_bank = _bank_indexes(bank, allowed)
    findings: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    seen_exact: dict[str, str] = {}
    seen_rank: dict[str, tuple[str, int]] = {}
    seen_skeleton: dict[str, str] = {}
    seen_source_ids: set[str] = set()

    record_keys = {
        "source_record_id", "name", "source", "source_ref",
        "formula_provenance", "original_formula", "economic_rationale",
        "source_constraints", "canonical_expression",
    }

    for index, raw in enumerate(records):
        label = _candidate_label(raw if isinstance(raw, dict) else {}, index)
        if not isinstance(raw, dict):
            findings.append({
                "candidate": label, "severity": "error",
                "code": "INVALID_RECORD", "message": "record must be an object",
            })
            continue

        extra = sorted(set(raw) - record_keys)
        if extra:
            findings.append({
                "candidate": label, "severity": "error",
                "code": "UNSUPPORTED_RECORD_KEYS",
                "message": f"unsupported keys: {', '.join(extra)}",
            })
            continue

        try:
            source_record_id = str(raw.get("source_record_id") or "").strip()
            name = str(raw.get("name") or "").strip()
            record_source = str(raw.get("source") or source).strip()
            source_ref = str(raw.get("source_ref") or "").strip()
            formula_provenance = str(raw.get("formula_provenance") or "").strip()
            original_formula = str(raw.get("original_formula") or "").strip()
            rationale = str(raw.get("economic_rationale") or "").strip()
            constraints = str(raw.get("source_constraints") or "").strip()

            if not source_record_id:
                raise ValidationError("source_record_id is required")
            if source_record_id in seen_source_ids:
                raise ValidationError(f"duplicate source_record_id in batch: {source_record_id}")
            seen_source_ids.add(source_record_id)
            if not name:
                raise ValidationError("name is required")
            if not record_source:
                raise ValidationError("source is required")
            if not original_formula:
                raise ValidationError("original_formula is required")
            if not rationale:
                raise ValidationError("economic_rationale is required")

            expr = canonicalize(raw.get("canonical_expression"), allowed)
            metrics = expression_metrics(expr)
            if metrics["nodes"] > MAX_NODES:
                raise ValidationError(
                    f"AST has too many nodes: {metrics['nodes']} > {MAX_NODES}"
                )
            if metrics["depth"] > MAX_DEPTH:
                raise ValidationError(
                    f"AST is too deep: {metrics['depth']} > {MAX_DEPTH}"
                )
            if metrics["lookback"] > MAX_LOOKBACK:
                raise ValidationError(
                    f"AST lookback too long: {metrics['lookback']} > {MAX_LOOKBACK}"
                )
            validate_dimension(expr)
        except (ValidationError, KeyError, TypeError, ValueError) as exc:
            findings.append({
                "candidate": label, "severity": "error",
                "code": "INVALID_EXPRESSION_OR_SCHEMA", "message": str(exc),
            })
            continue

        fp = fingerprint(expr)
        rkey, orientation = rank_signature(expr)
        skey = parameter_skeleton(expr)
        rejected = False

        if fp in exact_bank:
            matches = [
                {"factor_id": f.get("factor_id"), "source_record_id": f.get("source_record_id"), "name": f.get("name"), "reference_file": f.get("_reference_file")}
                for f in exact_bank[fp][:8]
            ]
            findings.append({
                "candidate": label, "severity": "error",
                "code": "EXACT_DUPLICATE", "matches": matches,
            })
            rejected = True
        elif rkey in rank_bank:
            matches = [
                {"factor_id": f.get("factor_id"), "source_record_id": f.get("source_record_id"), "name": f.get("name"), "reference_file": f.get("_reference_file")}
                for f in rank_bank[rkey][:8]
            ]
            findings.append({
                "candidate": label, "severity": "error",
                "code": "RANK_EQUIVALENT_DUPLICATE",
                "orientation": orientation, "matches": matches,
            })
            rejected = True

        if fp in seen_exact:
            findings.append({
                "candidate": label, "severity": "error",
                "code": "BATCH_EXACT_DUPLICATE", "matches": [seen_exact[fp]],
            })
            rejected = True
        elif rkey in seen_rank:
            previous, previous_orientation = seen_rank[rkey]
            findings.append({
                "candidate": label, "severity": "error",
                "code": "BATCH_RANK_EQUIVALENT_DUPLICATE",
                "matches": [previous],
                "orientation_relation": orientation * previous_orientation,
            })
            rejected = True

        if skey in seen_skeleton and not rejected:
            findings.append({
                "candidate": label, "severity": "error",
                "code": "PARAMETER_ONLY_VARIANT",
                "matches": [seen_skeleton[skey]],
            })
            rejected = True

        if contains_zero_mask(expr):
            findings.append({
                "candidate": label, "severity": "error",
                "code": "ZERO_MASK_CONDITIONAL",
                "message": "conditional branch returns literal 0, creating a large tied cross-section",
            })
            rejected = True

        if rejected:
            continue

        near = skeleton_bank.get(skey, [])
        if near:
            findings.append({
                "candidate": label, "severity": "warning",
                "code": "MOTHER_BANK_NEAR_VARIANT",
                "matches": [
                    {"factor_id": f.get("factor_id"), "source_record_id": f.get("source_record_id"), "name": f.get("name"), "reference_file": f.get("_reference_file")}
                    for f in near[:5]
                ],
            })
        for warning in sorted(set(denominator_warnings(expr))):
            findings.append({
                "candidate": label, "severity": "warning",
                "code": "DENOMINATOR_RISK", "message": warning,
            })

        accepted.append({
            "source_record_id": source_record_id,
            "name": name,
            "source": record_source,
            "source_ref": source_ref,
            "formula_provenance": formula_provenance,
            "original_formula": original_formula,
            "economic_rationale": rationale,
            "source_constraints": constraints,
            "canonical_expression": expr,
        })
        seen_exact[fp] = label
        seen_rank[rkey] = (label, orientation)
        seen_skeleton[skey] = label

    errors = [x for x in findings if x["severity"] == "error"]
    warnings = [x for x in findings if x["severity"] == "warning"]
    output = {
        "schema_version": 1,
        "batch_name": batch_name,
        "source": source,
        "records": accepted,
    }
    report = {
        "schema_version": 1,
        "batch_name": batch_name,
        "candidate_count": len(records),
        "accepted_count": len(accepted),
        "rejected_count": len({x["candidate"] for x in errors}),
        "error_count": len(errors),
        "warning_count": len(warnings),
        "mother_bank_factor_count": len(bank["factors"]),
        "reference_file_count": int(bank.get("reference_file_count", 1)),
        "reference_files": list(bank.get("reference_files", [])),
        "allowed_feature_count": len(allowed),
        "findings": findings,
    }
    return output, report


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a direct factors_lab import batch against the AST contract and mother bank")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--bank",
        type=Path,
        default=DEFAULT_BANK,
        help="Local reference factor file or directory; default: mother_bank/",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    try:
        payload = json.loads(args.input.read_text(encoding="utf-8-sig"))
        bank = load_bank(args.bank)
        output, report = validate_batch(payload, bank)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        print(f"validation setup failed: {exc}", file=sys.stderr)
        return 3

    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("candidate_count", "accepted_count", "rejected_count", "warning_count", "mother_bank_factor_count")}, ensure_ascii=False))
    return 2 if report["rejected_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
