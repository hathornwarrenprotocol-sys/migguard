#!/usr/bin/env python3
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
import migguard as mg

TOOLS = [
    {
        'name': 'check',
        'description': 'Lint and sandbox-dry-run SQL against a cloned SQLite file. Never writes --db. Returns token ALL_PASS, PRESERVED, APPLY_FAILED, or INCOMPLETE.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'sql': {'type': 'string', 'description': 'Path to .sql'},
                'db': {'type': 'string', 'description': 'Path to sqlite file'},
                'code_root': {'type': 'string'},
                'table': {'type': 'string'},
                'key': {'type': 'string'},
                'from_col': {'type': 'string'},
                'to_col': {'type': 'string'},
            },
            'required': ['sql', 'db'],
        },
    },
    {
        'name': 'pack',
        'description': 'Integrity + optional query on a cloned db. Writes migguard.receipt.json. Never writes --db.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'db': {'type': 'string'},
                'code_root': {'type': 'string'},
                'sql': {'type': 'string'},
            },
            'required': ['db'],
        },
    },
    {
        'name': 'query',
        'description': 'Scan code-root for table names present in --db.',
        'inputSchema': {
            'type': 'object',
            'properties': {
                'db': {'type': 'string'},
                'code_root': {'type': 'string'},
            },
            'required': ['db', 'code_root'],
        },
    },
]

def run_main(argv):
    from io import StringIO
    buf = StringIO()
    err = StringIO()
    oldout, olderr = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = buf, err
    try:
        code = mg.main(argv)
    finally:
        sys.stdout, sys.stderr = oldout, olderr
    return code, buf.getvalue(), err.getvalue()

def call_tool(name, args):
    args = args or {}
    if name == 'check':
        argv = ['check', str(args['sql']), '--db', str(args['db'])]
        if args.get('code_root'):
            argv += ['--code-root', str(args['code_root'])]
        if args.get('table') and args.get('from_col') and args.get('to_col'):
            argv += ['--table', args['table'], '--key', args.get('key') or 'id',
                     '--from-col', args['from_col'], '--to-col', args['to_col']]
        return run_main(argv)
    if name == 'pack':
        argv = ['pack', '--db', str(args['db'])]
        if args.get('code_root'):
            argv += ['--code-root', str(args['code_root'])]
        if args.get('sql'):
            argv += [str(args['sql'])]
        return run_main(argv)
    if name == 'query':
        return run_main(['query', '--db', str(args['db']), '--code-root', str(args['code_root'])])
    return 2, '', 'unknown tool'

def reply(msg_id, result=None, error=None):
    out = {'jsonrpc': '2.0', 'id': msg_id}
    if error is not None:
        out['error'] = error
    else:
        out['result'] = result
    sys.stdout.write(json.dumps(out) + '\n')
    sys.stdout.flush()

def handle(msg):
    mid = msg.get('id')
    method = msg.get('method')
    params = msg.get('params') or {}
    if method == 'initialize':
        reply(mid, {
            'protocolVersion': '2024-11-05',
            'capabilities': {'tools': {}},
            'serverInfo': {'name': 'migguard', 'version': getattr(mg, 'TOOL_VERSION', '0.4.0')},
        })
        return
    if method == 'notifications/initialized':
        return
    if method == 'tools/list':
        reply(mid, {'tools': TOOLS})
        return
    if method == 'tools/call':
        name = params.get('name')
        arguments = params.get('arguments') or {}
        code, stdout, stderr = call_tool(name, arguments)
        text = (stdout + stderr).strip()
        reply(mid, {
            'content': [{'type': 'text', 'text': text}],
            'isError': code != 0,
        })
        return
    if mid is not None:
        reply(mid, error={'code': -32601, 'message': 'method not found'})

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        handle(msg)

if __name__ == '__main__':
    main()
