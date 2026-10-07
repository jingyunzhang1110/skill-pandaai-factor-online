#!/usr/bin/env python3
from __future__ import annotations
import subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
cmd=[sys.executable,"-m","unittest","discover","-s",str(ROOT/"tests"),"-v"]
raise SystemExit(subprocess.call(cmd,cwd=ROOT))
