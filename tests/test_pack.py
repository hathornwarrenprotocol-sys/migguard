#!/usr/bin/env python3
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
EXE = [sys.executable, str(ROOT / 'migguard.py')]

def main():
    db = str(ROOT / 'real/dev.db')
    i = subprocess.run(EXE + ['integrity', '--db', db], cwd=str(ROOT), capture_output=True, text=True)
    print(i.stdout)
    assert i.returncode == 0 and i.stdout.strip().splitlines()[-1] == 'ALL_PASS'
    p = subprocess.run(EXE + ['pack', '--db', db, '--code-root', str(ROOT / 'app_sample')], cwd=str(ROOT), capture_output=True, text=True)
    print(p.stdout)
    assert p.returncode == 0 and p.stdout.strip().splitlines()[-1] == 'ALL_PASS'
    rec = json.loads((ROOT / 'migguard.receipt.json').read_text())
    assert rec['integrity'] == 'ALL_PASS'
    assert rec['db_sha256']
    print('PASS pack')

if __name__ == '__main__':
    raise SystemExit(main())
