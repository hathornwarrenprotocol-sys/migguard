#!/usr/bin/env python3
import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
EXE = [sys.executable, str(ROOT / 'migguard.py')]

def main():
    p = subprocess.run(
        EXE + ['query', '--db', str(ROOT / 'real/dev.db'), '--code-root', str(ROOT / 'app_sample')],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    print(p.stdout)
    assert p.returncode == 0
    assert 'Post' in p.stdout
    assert 'ALL_PASS' in p.stdout.splitlines()[-1]
    r = subprocess.run(
        EXE + ['check', str(ROOT / 'fixtures/sql/rename_column.sql'),
               '--db', str(ROOT / 'real/dev.db'),
               '--table', 'User', '--key', 'id', '--from-col', 'name', '--to-col', 'fullName'],
        cwd=str(ROOT), capture_output=True, text=True,
    )
    print('preserve-check', r.returncode, r.stdout.splitlines()[-1] if r.stdout else r.stderr)
    assert r.returncode == 0
    assert r.stdout.strip().splitlines()[-1] == 'PRESERVED'
    print('PASS query')

if __name__ == '__main__':
    raise SystemExit(main())
