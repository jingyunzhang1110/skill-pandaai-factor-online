#!/usr/bin/env python3
"""Preflight for the factors_lab-compatible PandaAI factor source skill."""
from __future__ import annotations
import argparse, importlib.util, json, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    ap=argparse.ArgumentParser(); ap.add_argument("--pandaai", action="store_true")
    args=ap.parse_args(); ok=True
    print(f"python={sys.version.split()[0]}")
    if sys.version_info < (3,10): print("[FAIL] Python >=3.10 required"); ok=False
    manifest=ROOT/"mother_bank"/"MANIFEST.json"; bank=ROOT/"mother_bank"/"clean_seed_factor_bank.json"
    try:
        m=json.loads(manifest.read_text(encoding="utf-8")); b=json.loads(bank.read_text(encoding="utf-8"))
        count=len(b.get("factors",[])); print(f"[OK] mother_bank factors={count} source_commit={m.get('source_commit')}")
        if count != int(m.get("factor_count",-1)): print("[FAIL] manifest factor_count mismatch"); ok=False
    except Exception as exc: print(f"[FAIL] mother bank: {exc}"); ok=False
    if args.pandaai:
        cli=shutil.which("pandaai-cli")
        if not cli: print("[FAIL] pandaai-cli not found"); ok=False
        else:
            print(f"[OK] pandaai-cli={cli}")
            proc=subprocess.run([cli,"--json","balance"],capture_output=True,text=True)
            if proc.returncode: print("[WARN] PandaAI login/balance check failed; run `pandaai-cli login` interactively")
            else: print("[OK] PandaAI CLI responded")
    return 0 if ok else 2
if __name__=="__main__": raise SystemExit(main())
