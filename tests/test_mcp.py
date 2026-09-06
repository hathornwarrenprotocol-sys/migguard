#!/usr/bin/env python3
import json, subprocess, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]

def main():
    payload = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}}) + '\n'
    p = subprocess.run([sys.executable, str(ROOT / 'mcp_server.py')], input=payload, capture_output=True, text=True, cwd=str(ROOT))
    print(p.stdout)
    assert p.returncode == 0
    msg = json.loads(p.stdout.strip().splitlines()[-1])
    names = [t['name'] for t in msg['result']['tools']]
    assert names == ['check', 'pack', 'query']
    call = {
        'jsonrpc': '2.0', 'id': 2, 'method': 'tools/call',
        'params': {'name': 'query', 'arguments': {
            'db': str(ROOT / 'real/dev.db'),
            'code_root': str(ROOT / 'app_sample'),
        }},
    }
    p2 = subprocess.run([sys.executable, str(ROOT / 'mcp_server.py')], input=json.dumps(call)+'\n', capture_output=True, text=True, cwd=str(ROOT))
    body = json.loads(p2.stdout.strip().splitlines()[-1])
    text = body['result']['content'][0]['text']
    print(text)
    assert 'Post' in text and 'ALL_PASS' in text
    print('PASS mcp')

if __name__ == '__main__':
    raise SystemExit(main())
