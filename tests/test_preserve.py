#!/usr/bin/env python3
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRESERVE = ROOT / "preserve.py"
DB = ROOT / "real" / "dev.db"
EXPECT = json.loads((ROOT / "fixtures" / "preserve_expect.json").read_text())


def run(rel: str):
    proc = subprocess.run(
        [
            sys.executable, str(PRESERVE), "--json",
            "--db", str(DB), "--sql", str(ROOT / rel),
            "--table", EXPECT["table"], "--key", EXPECT["key"],
            "--from-col", EXPECT["from_col"], "--to-col", EXPECT["to_col"],
        ],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    print(proc.stderr, end="")
    return proc.returncode, json.loads(proc.stdout)


def main():
    golden = EXPECT["golden"]
    for case in EXPECT["cases"]:
        rc, payload = run(case["file"])
        print(case["file"].split("/")[-2:], payload["verdict"], "exit", rc)
        assert payload["before_sha256"] == golden
        assert payload["verdict"] in case["verdicts"]
        assert rc == case["exit"]
        if payload["verdict"] == "PRESERVED":
            assert payload["after_sha256"] == golden
    print("PASS")


if __name__ == "__main__":
    raise SystemExit(main())
