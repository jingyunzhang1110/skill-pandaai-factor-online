#!/usr/bin/env python3
"""Export validated factors_lab AST factors to the legacy PandaAI batch manifest when lossless."""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

BASE_FIELDS = {
    "open": "OPEN", "high": "HIGH", "low": "LOW", "close": "CLOSE",
    "volume": "VOLUME", "amount": "AMOUNT", "turnover": "TURNOVER",
    "market_cap": "MARKET_CAP", "cap": "MARKET_CAP",
}

class Unsupported(ValueError):
    pass


def num(value: Any) -> str:
    x = float(value)
    if not math.isfinite(x):
        raise Unsupported("non-finite constant")
    return str(int(x)) if x.is_integer() else repr(x)


def render(node: dict[str, Any]) -> str:
    kind = node["kind"]
    if kind == "feature":
        name = node["name"]
        lag = int(node.get("lag", 0))
        if name in {"returns", "ret"}:
            base = "RETURNS(CLOSE,1)"
        elif name in BASE_FIELDS:
            base = BASE_FIELDS[name]
        else:
            raise Unsupported(f"feature {name!r} is not in the conservative PandaAI intersection")
        return base if lag == 0 else f"DELAY({base},{lag})"
    if kind == "constant":
        return num(node["value"])
    if kind == "unary":
        op = node["operator"]
        x = render(node["operand"])
        if op == "neg": return f"(0-({x}))"
        mapping = {"abs":"ABS", "sign":"SIGN", "log":"LOG", "sqrt":"SQRT", "rank":"RANK", "zscore":"ZSCORE"}
        if op not in mapping:
            raise Unsupported(f"unary operator {op!r} is not exported")
        return f"{mapping[op]}({x})"
    if kind == "binary":
        op, a, b = node["operator"], render(node["left"]), render(node["right"])
        symbols = {"add":"+", "sub":"-", "mul":"*", "div":"/"}
        if op in symbols: return f"(({a}){symbols[op]}({b}))"
        mapping = {"pow":"POWER", "signed_power":"SIGNEDPOWER", "max":"MAX", "min":"MIN"}
        if op not in mapping: raise Unsupported(f"binary operator {op!r} is not exported")
        return f"{mapping[op]}({a},{b})"
    if kind == "rolling":
        if node.get("min_periods") is not None or node.get("parameter") is not None:
            raise Unsupported("rolling min_periods/parameter has no guaranteed PandaAI formula equivalent")
        op = node["operator"]
        x, w = render(node["operand"]), int(node["window"])
        mapping = {
            "mean":"MA", "std":"STD", "sum":"SUM", "product":"PRODUCT",
            "min":"TS_MIN", "max":"TS_MAX", "rank":"TS_RANK", "delta":"DIFF",
            "delay":"DELAY", "argmax":"TS_ARGMAX", "argmin":"TS_ARGMIN",
            "decay_linear":"DECAYLINEAR", "slope":"SLOPE", "skew":"TS_SKEW",
        }
        if op not in mapping: raise Unsupported(f"rolling operator {op!r} is not exported")
        return f"{mapping[op]}({x},{w})"
    if kind == "pair_rolling":
        if node.get("min_periods") is not None:
            raise Unsupported("pair rolling min_periods is not exported")
        mapping = {"corr":"CORR", "cov":"COV"}
        op = node["operator"]
        if op not in mapping: raise Unsupported(f"pair rolling operator {op!r} is not exported")
        return f"{mapping[op]}({render(node['left'])},{render(node['right'])},{int(node['window'])})"
    if kind == "comparison":
        symbols = {"lt":"<", "le":"<=", "gt":">", "ge":">=", "eq":"==", "ne":"!="}
        return f"(({render(node['left'])}){symbols[node['operator']]}({render(node['right'])}))"
    if kind == "logical":
        symbols = {"and":"&&", "or":"||"}
        return f"(({render(node['left'])}){symbols[node['operator']]}({render(node['right'])}))"
    if kind == "conditional":
        return f"IF({render(node['condition'])},{render(node['if_true'])},{render(node['if_false'])})"
    raise Unsupported(f"AST kind {kind!r} is not in the conservative PandaAI export subset")


def main() -> int:
    ap = argparse.ArgumentParser(description="Export validated factors_lab candidates to PandaAI batch manifest")
    ap.add_argument("--input", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--report", type=Path, required=True)
    args = ap.parse_args()
    payload = json.loads(args.input.read_text(encoding="utf-8-sig"))
    factors = payload.get("factors")
    if not isinstance(factors, list):
        print("input must be validator output with a factors list", file=sys.stderr); return 3
    lines, report = [], []
    for factor in factors:
        name = str(factor.get("source_code") or factor.get("name") or "factor").replace("~", "-")
        if not factor.get("audit", {}).get("passed"):
            report.append({"name": name, "exported": False, "reason": "candidate audit did not pass"}); continue
        try:
            formula = render(factor["canonical_expression"])
        except (KeyError, TypeError, ValueError, Unsupported) as exc:
            report.append({"name": name, "exported": False, "reason": str(exc)}); continue
        direction = factor.get("direction")
        if direction not in (0, 1):
            report.append({"name": name, "exported": False, "reason": "missing direction 0/1"}); continue
        lines.append(f"{name} ~ {formula} ~ {direction}")
        report.append({"name": name, "exported": True, "formula": formula, "direction": direction})
    args.output.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    args.report.write_text(json.dumps({"input_count":len(factors),"exported_count":len(lines),"items":report}, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"input_count":len(factors),"exported_count":len(lines)}, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
