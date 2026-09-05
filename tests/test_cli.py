#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    v = subprocess.run([sys.executable, str(ROOT / "migguard.py"), "--version"], capture_output=True, text=True)
    print("version", v.stdout.strip() or v.stderr.strip())
    assert v.returncode == 0
    assert "0.4.0" in (v.stdout + v.stderr)
    q = subprocess.run(
        [
            sys.executable, str(ROOT / "migguard.py"),
            str(ROOT / "fixtures/sql/add_index.sql"),
            "--db", str(ROOT / "real/dev.db"),
            "--quiet", "--max-row-loss", "0",
        ],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    print("quiet", q.stdout.strip())
    assert q.returncode == 0
    assert "100" in q.stdout and "SAFE" in q.stdout
    bad = subprocess.run(
        [sys.executable, str(ROOT / "migguard.py"), str(ROOT / "README.md")],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    print("not-sql exit", bad.returncode, bad.stderr.strip()[:80])
    assert bad.returncode == 2
    print("PASS cli")


if __name__ == "__main__":
    raise SystemExit(main())
