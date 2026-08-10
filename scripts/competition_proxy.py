#!/usr/bin/env python3
"""Offline proxy for the public PandaAI competition A/B/C score.

The input is a normalized JSON snapshot, not a CLI command:

{
  "as_of": "2026-07-31",
  "factors": [{
    "name": "F-A17",
    "effective_date": "2026-01-10",
    "rank_ic": [{"date": "2026-01-12", "value": 0.04,
                  "sample_type": "in_sample"}],
    "portfolio_months": [{"month": "2026-07", "excess_month": 0.02,
                           "daily_excess_returns": [0.001, -0.002],
                           "turnover": 0.4, "max_drawdown": 0.05}]
  }]
}

It never calls pandaai-cli, creates factors, or claims to reproduce official points. B is
unavailable until effective-date records exist; C is a single-factor proxy unless the input is a
pool-level composite daily ledger.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


def parse_date(value: str) -> dt.date:
    text = str(value)
    if len(text) == 8 and text.isdigit():
        return dt.datetime.strptime(text, "%Y%m%d").date()
    return dt.date.fromisoformat(text[:10])


def number(value: object) -> float | None:
    if isinstance(value, str):
        text = value.strip().replace("%", "")
        if not text:
            return None
        try:
            parsed = float(text)
        except ValueError:
            return None
        return parsed / 100 if value.strip().endswith("%") else parsed
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def five_year_cutoff(as_of: dt.date) -> dt.date:
    try:
        return as_of.replace(year=as_of.year - 5)
    except ValueError:  # 29 February
        return as_of.replace(year=as_of.year - 5, day=28)


def monthly_means(records: list[dict]) -> dict[str, float]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for record in records:
        try:
            date = parse_date(record["date"])
        except (KeyError, TypeError, ValueError):
            continue
        value = number(record.get("value", record.get("rank_ic")))
        if value is not None:
            buckets[date.strftime("%Y-%m")].append(value)
    return {month: statistics.mean(values) for month, values in sorted(buckets.items())}


def stats(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"periods": 0, "mean": None, "icir": None, "win_rate": None}
    mean = statistics.mean(values)
    deviation = statistics.stdev(values) if len(values) > 1 else None
    return {
        "periods": len(values),
        "mean": mean,
        "icir": mean / deviation if deviation else None,
        "win_rate": sum(value > 0 for value in values) / len(values),
    }


def product_return(values: list[float]) -> float | None:
    if not values:
        return None
    result = 1.0
    for value in values:
        result *= 1 + value
    return result - 1


def max_drawdown(values: list[float]) -> float | None:
    if not values:
        return None
    nav = peak = 1.0
    drawdown = 0.0
    for value in values:
        nav *= 1 + value
        peak = max(peak, nav)
        drawdown = max(drawdown, 1 - nav / peak)
    return drawdown


def score_a(records: list[dict], as_of: dt.date, direction: int = 1,
            win_records: list[dict] | None = None, win_threshold: float = 0.02) -> dict:
    cutoff = five_year_cutoff(as_of)
    selected, has_marker = [], False
    for record in records:
        try:
            date = parse_date(record["date"])
        except (KeyError, TypeError, ValueError):
            continue
        sample_type = str(record.get("sample_type", "")).lower()
        is_oos = bool(record.get("out_of_sample")) or sample_type in {"oos", "out_of_sample"}
        has_marker |= "sample_type" in record or "out_of_sample" in record
        if date >= cutoff or is_oos:
            selected.append(record)
    monthly = monthly_means(selected)
    rank_values = list(monthly.values())
    metrics = stats(rank_values)
    # The rule's win rate is based on per-period IC, not monthly RankIC. When a separate IC
    # sequence is available, use it; the fallback keeps compact historical fixtures useful.
    selected_dates = set()
    for record in selected:
        try:
            selected_dates.add(parse_date(record["date"]))
        except (KeyError, TypeError, ValueError):
            continue
    source = win_records if win_records is not None else selected
    win_values = []
    for record in source:
        try:
            record_date = parse_date(record["date"])
        except (KeyError, TypeError, ValueError):
            continue
        if record_date not in selected_dates:
            continue
        value = number(record.get("value", record.get("ic")))
        if value is not None:
            win_values.append(value)
    win_values = [value for value in win_values if value is not None]
    if direction == 1:
        metrics["win_rate"] = (sum(value > win_threshold for value in win_values) / len(win_values)
                                if win_values else None)
    else:
        metrics["win_rate"] = (sum(value < -win_threshold for value in win_values) / len(win_values)
                                if win_values else None)
    metrics["win_periods"] = len(win_values)
    if metrics["mean"] is None or metrics["icir"] is None or metrics["win_rate"] is None:
        score = None
    else:
        score = abs(metrics["mean"]) * abs(metrics["icir"]) * metrics["win_rate"]
    warnings = []
    if not has_marker:
        warnings.append("OOS markers are absent; A uses the five-year proxy only")
    return {"score": score, "anchor": 0.08, "monthly_rank_ic": monthly,
            "metrics": metrics, "warnings": warnings}


def score_b(records: list[dict], effective_date: str | None) -> dict:
    if not effective_date:
        return {"available": False, "score": None, "anchor": 0.06,
                "reason": "effective_date is required; official B starts after pool entry"}
    effective = parse_date(effective_date)
    fresh = []
    for record in records:
        try:
            date = parse_date(record["date"])
        except (KeyError, TypeError, ValueError):
            continue
        if date > effective:
            fresh.append(record)
    metrics = stats(list(monthly_means(fresh).values()))
    score = None if metrics["icir"] is None else abs(metrics["mean"]) * abs(metrics["icir"]) * metrics["win_rate"]
    return {"available": bool(metrics["periods"]), "score": score, "anchor": 0.06,
            "metrics": metrics, "reason": None if metrics["periods"] else "no post-effective records"}


def score_c(months: list[dict], periods_per_year: float = 22 * 12) -> dict:
    monthly_scores = []
    warnings = []
    for month in months:
        daily = [number(value) for value in month.get("daily_excess_returns", [])]
        daily = [value for value in daily if value is not None]
        excess = number(month.get("excess_month"))
        if excess is None:
            excess = product_return(daily)
        turnover = number(month.get("turnover", month.get("turnover_month")))
        drawdown = number(month.get("max_drawdown", month.get("max_dd_month")))
        if excess is None or turnover is None or drawdown is None or len(daily) < 2:
            warnings.append(f"incomplete month: {month.get('month', '?')}")
            continue
        daily_std = statistics.stdev(daily)
        sharpe = (statistics.mean(daily) / daily_std * math.sqrt(periods_per_year)
                  if daily_std else 0.0)
        excess_ann = (1 + excess) ** 12 - 1
        # Input turnover is a fraction (0.30 means 30%). The public rule's BaseTurn is 0.3.
        raw = max(excess_ann, 0) / max(turnover, 0.3) * sharpe * (1 - 1.2 * drawdown)
        monthly_scores.append({"month": month.get("month"), "raw": raw,
                               "nc": min(max(raw / 0.6, 0), 1),
                               "excess_ann": excess_ann, "sharpe_ann": sharpe,
                               "turnover": turnover, "max_drawdown": drawdown})
    return {"available": bool(monthly_scores), "anchor": 0.6,
            "monthly": monthly_scores,
            "score": statistics.mean(item["raw"] for item in monthly_scores) if monthly_scores else None,
            "warnings": warnings}


def evaluate(snapshot: dict, as_of: str | None = None) -> dict:
    end = parse_date(as_of or snapshot.get("as_of"))
    rows = []
    for factor in snapshot.get("factors", []):
        a = score_a(factor.get("rank_ic", []), end)
        b = score_b(factor.get("rank_ic", []), factor.get("effective_date"))
        c = score_c(factor.get("portfolio_months", []))
        rows.append({"name": factor.get("name"), "A_proxy": a, "B_proxy": b, "C_proxy": c})
    return {"as_of": end.isoformat(), "official_score": False,
            "warning": "Local proxy only; official B/C require platform post-effective and pool ledgers.",
            "factors": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("snapshot", type=Path)
    parser.add_argument("--as-of", help="override snapshot as_of, YYYY-MM-DD")
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))
    print(json.dumps(evaluate(snapshot, args.as_of), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
