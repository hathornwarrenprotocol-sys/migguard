#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    proc = subprocess.run(
        [
            sys.executable, str(ROOT / "migguard.py"),
            str(ROOT / "fixtures/sql/drop_table.sql"),
            "--db", str(ROOT / "real/dev.db"),
            "--code-root", str(ROOT / "app_sample"),
            "--json",
        ],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    print(proc.stdout)
    print(proc.stderr, end="")
    assert "Post" in proc.stdout
    assert "query.py" in proc.stdout
    print("PASS blast")


if __name__ == "__main__":
    raise SystemExit(main())
