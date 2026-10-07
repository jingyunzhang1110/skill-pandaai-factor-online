#!/usr/bin/env python3
"""Preflight for the pure factors_lab factor-mining skill."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    ok = True
    print(f"python={sys.version.split()[0]}")
    if sys.version_info < (3, 10):
        print("[FAIL] Python >=3.10 required")
        ok = False

    manifest = ROOT / "mother_bank" / "MANIFEST.json"
    bank_path = ROOT / "mother_bank" / "clean_seed_factor_bank.json"
    try:
        meta = json.loads(manifest.read_text(encoding="utf-8"))
        bank = json.loads(bank_path.read_text(encoding="utf-8"))
        count = len(bank.get("factors", []))
        print(f"[OK] mother_bank factors={count} source_commit={meta.get('source_commit')}")
        if count != int(meta.get("factor_count", -1)):
            print("[FAIL] manifest factor_count mismatch")
            ok = False
        if bank.get("factor_count") not in (None, count):
            print("[FAIL] bank factor_count mismatch")
            ok = False
    except Exception as exc:
        print(f"[FAIL] mother bank: {exc}")
        ok = False

    validator = ROOT / "scripts" / "validate_candidates.py"
    try:
        spec = importlib.util.spec_from_file_location("validate_candidates", validator)
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load validator")
        print("[OK] validator importable")
    except Exception as exc:
        print(f"[FAIL] validator: {exc}")
        ok = False

    return 0 if ok else 2

if __name__ == "__main__":
    raise SystemExit(main())
