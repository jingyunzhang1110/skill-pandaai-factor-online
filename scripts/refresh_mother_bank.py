#!/usr/bin/env python3
"""Refresh the bundled factors_lab mother-bank snapshot from a local factors_lab checkout."""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True, help="Path to factors_lab clean_seed_factor_bank.json")
    ap.add_argument("--source-commit", default=None, help="Optional factors_lab commit recorded in MANIFEST.json")
    args = ap.parse_args()

    source = args.source.resolve()
    if not source.is_file():
        ap.error(f"source not found: {source}")

    data = json.loads(source.read_text(encoding="utf-8"))
    factors = data.get("factors")
    if not isinstance(factors, list):
        ap.error("source JSON does not contain a factors list")

    destination = ROOT / "mother_bank" / "clean_seed_factor_bank.json"
    shutil.copyfile(source, destination)

    manifest_path = ROOT / "mother_bank" / "MANIFEST.json"
    old = {}
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text(encoding="utf-8"))

    manifest = {
        "schema_version": 1,
        "source_repository": "jingyunzhang1110/factors_lab",
        "source_branch": "main",
        "source_commit": args.source_commit or old.get("source_commit"),
        "source_path": "common_factor/catalog/clean_seed_factor_bank.json",
        "git_blob_sha": None,
        "factor_count": len(factors),
        "source_record_count": data.get("source_record_count"),
        "next_factor_id": data.get("next_factor_id"),
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"refreshed mother bank: factors={len(factors)} -> {destination}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
