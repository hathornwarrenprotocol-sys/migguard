#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIG = ROOT / "migguard.py"
DB = ROOT / "real" / "dev.db"
EXPECT = ROOT / "fixtures" / "expect.json"


def run(name: str, extra: list[str]):
    sql = ROOT / "fixtures" / "sql" / name
    proc = subprocess.run(
        [sys.executable, str(MIG), str(sql), "--db", str(DB), *extra],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    verdict = next((ln for ln in proc.stdout.splitlines() if ln.startswith("score:")), "")
    print(f"{name:20} exit={proc.returncode}  {verdict}")
    return proc.returncode, proc.stdout


def main():
    cases = json.loads(EXPECT.read_text())
    failed = 0
    for case in cases:
        extra = []
        if case["max_row_loss"] is not None:
            extra += ["--max-row-loss", str(case["max_row_loss"])]
        extra += ["--fail-under", str(case["fail_under"])]
        rc, _ = run(case["file"], extra)
        if rc != case["exit"]:
            print(f"  FAIL expected exit {case['exit']} got {rc}")
            failed += 1
    if failed:
        raise SystemExit(f"{failed} fixture(s) missed expected exit")
    print("PASS fixtures")


if __name__ == "__main__":
    raise SystemExit(main())
