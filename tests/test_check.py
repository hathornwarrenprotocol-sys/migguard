#!/usr/bin/env python3
import subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
EXE = [sys.executable, str(ROOT / 'migguard.py')]

def run(args):
    return subprocess.run(EXE + args, cwd=str(ROOT), capture_output=True, text=True)

def last_line(text):
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines[-1] if lines else ''

def main():
    h = run(['check', '-h'])
    assert h.returncode == 0
    blob = h.stdout + h.stderr
    assert '--db' in blob and '--code-root' in blob
    a = run(['check', str(ROOT / 'fixtures/sql/add_index.sql'), '--db', str(ROOT / 'real/dev.db')])
    print('add_index', a.returncode, last_line(a.stdout))
    assert a.returncode == 0 and last_line(a.stdout) == 'ALL_PASS'
    r = run(['check', str(ROOT / 'fixtures/sql/rename_column.sql'), '--db', str(ROOT / 'real/dev.db')])
    print('rename', r.returncode, last_line(r.stdout))
    assert r.returncode == 0 and last_line(r.stdout) == 'PRESERVED'
    d = run(['check', str(ROOT / 'fixtures/sql/drop_table.sql'), '--db', str(ROOT / 'real/dev.db'), '--code-root', str(ROOT / 'app_sample')])
    print('drop', d.returncode, last_line(d.stdout))
    assert d.returncode == 1 and last_line(d.stdout) == 'APPLY_FAILED'
    assert 'Post' in d.stdout
    print('PASS check')

if __name__ == '__main__':
    raise SystemExit(main())
