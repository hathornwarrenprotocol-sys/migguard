#!/usr/bin/env python3
import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
EXE = [sys.executable, str(ROOT / 'migguard.py')]

def main():
    db = str(ROOT / 'real/dev.db')
    p = subprocess.run(EXE + ['drift', '--db', db, '--other', db], cwd=str(ROOT), capture_output=True, text=True)
    print(p.stdout)
    assert p.returncode == 0
    assert p.stdout.strip().splitlines()[-1] == 'ALL_PASS'
    print('PASS drift')

if __name__ == '__main__':
    raise SystemExit(main())
