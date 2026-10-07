#!/usr/bin/env python3
"""Refresh the Skill's unique-factor dedup snapshot from factors_lab append-only RAW shards."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "mother_bank" / "clean_seed_factor_bank.json"
MANIFEST = ROOT / "mother_bank" / "MANIFEST.json"


def load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"JSON top level must be an object: {path}")
    return data


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to factors_lab/common_factor/catalog/raw directory",
    )
    ap.add_argument(
        "--source-commit",
        default=None,
        help="Optional factors_lab commit recorded in MANIFEST.json",
    )
    args = ap.parse_args()

    source = args.source.resolve()
    if not source.is_dir():
        ap.error(f"RAW directory not found: {source}")
    raw_files = sorted(source.glob("*.json"))
    if not raw_files:
        ap.error(f"RAW directory contains no JSON shards: {source}")

    previous: dict[str, dict] = {}
    if DESTINATION.is_file():
        old = load_json(DESTINATION)
        for item in old.get("factors", []):
            if isinstance(item, dict) and item.get("factor_id"):
                previous[str(item["factor_id"])] = item

    chosen: dict[str, dict] = {}
    source_record_count = 0
    for raw_file in raw_files:
        payload = load_json(raw_file)
        factors = payload.get("factors")
        if not isinstance(factors, list):
            ap.error(f"RAW shard has no factors list: {raw_file}")
        source_record_count += len(factors)
        for item in factors:
            if not isinstance(item, dict):
                ap.error(f"RAW shard contains non-object factor: {raw_file}")
            factor_id = str(item.get("factor_id") or "").strip()
            if len(factor_id) != 16 or not factor_id.isdigit():
                ap.error(f"invalid factor_id {factor_id!r} in {raw_file}")
            current = chosen.get(factor_id)
            if current is None:
                chosen[factor_id] = item
            elif current.get("canonical_expression") is None and item.get("canonical_expression") is not None:
                chosen[factor_id] = item

    factors: list[dict] = []
    unresolved: list[str] = []
    for factor_id in sorted(chosen, key=int):
        item = chosen[factor_id]
        expression = item.get("canonical_expression")
        fingerprint = item.get("expression_fingerprint")
        if expression is None:
            fallback = previous.get(factor_id)
            if fallback is not None:
                expression = fallback.get("canonical_expression")
                fingerprint = fallback.get("expression_fingerprint") or fingerprint
        if expression is None:
            unresolved.append(factor_id)
            continue
        factors.append(
            {
                "factor_id": factor_id,
                "name": str(item.get("name") or previous.get(factor_id, {}).get("name") or factor_id),
                "source": str(item.get("source") or previous.get(factor_id, {}).get("source") or "unknown"),
                "canonical_expression": expression,
                "expression_fingerprint": fingerprint,
            }
        )

    if unresolved:
        ap.error(
            "RAW contains factor IDs without canonical_expression and the previous "
            "Skill snapshot cannot resolve them: " + ", ".join(unresolved[:50])
        )

    maximum = max((int(item["factor_id"]) for item in factors), default=0)
    snapshot = {
        "format_version": 3,
        "purpose": "skill-dedup-snapshot-only",
        "factor_count": len(factors),
        "source_record_count": source_record_count,
        "next_factor_id": f"{maximum + 1:016d}",
        "factors": factors,
    }
    DESTINATION.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    old_manifest = load_json(MANIFEST) if MANIFEST.is_file() else {}
    manifest = {
        "schema_version": 2,
        "source_repository": "jingyunzhang1110/factors_lab",
        "source_branch": "main",
        "source_commit": args.source_commit or old_manifest.get("source_commit"),
        "source_path": "common_factor/catalog/raw",
        "factor_count": len(factors),
        "source_record_count": source_record_count,
        "next_factor_id": f"{maximum + 1:016d}",
        "note": (
            "This file is a Skill-only unique-factor dedup snapshot derived from "
            "append-only RAW shards. It is not a factors_lab runtime clean catalog."
        ),
    }
    MANIFEST.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"refreshed dedup snapshot: raw_shards={len(raw_files)} "
        f"source_records={source_record_count} unique_factors={len(factors)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
