#!/usr/bin/env python3
"""Preflight for the standalone factors_lab-compatible factor-mining Skill."""
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

    manifest_path = ROOT / "mother_bank" / "MANIFEST.json"
    validator_path = ROOT / "scripts" / "validate_candidates.py"

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        initial = ROOT / "mother_bank" / str(manifest["initial_snapshot"])
        payload = json.loads(initial.read_text(encoding="utf-8"))
        initial_count = len(payload.get("factors", []))
        expected = int(manifest.get("initial_factor_count", -1))
        if initial_count != expected:
            print(
                f"[FAIL] initial snapshot factor count mismatch: "
                f"{initial_count} != {expected}"
            )
            ok = False
        else:
            print(f"[OK] initial mother bank factors={initial_count}")
        if manifest.get("auto_sync") is not False:
            print("[FAIL] auto_sync must be false")
            ok = False
    except Exception as exc:
        print(f"[FAIL] mother bank manifest: {exc}")
        ok = False

    try:
        spec = importlib.util.spec_from_file_location(
            "validate_candidates", validator_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load validator")
        module = importlib.util.module_from_spec(spec)
        sys.modules["validate_candidates"] = module
        spec.loader.exec_module(module)
        bank = module.load_bank(ROOT / "mother_bank")
        print(
            f"[OK] local reference files={bank.get('reference_file_count')} "
            f"records_with_ast={len(bank.get('factors', []))}"
        )
    except Exception as exc:
        print(f"[FAIL] local reference bank: {exc}")
        ok = False

    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
