#!/usr/bin/env python3
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "real" / "dev.db"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    before = sha(DB)
    subprocess.run([sys.executable, str(ROOT / "tests" / "test_fixtures.py")], cwd=str(ROOT), check=True)
    after = sha(DB)
    print("db", before[:12], "->", after[:12])
    assert before == after, "source db mutated"
    print("PASS db frozen")


if __name__ == "__main__":
    raise SystemExit(main())
