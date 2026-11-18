"""Pull only the usage fields out of the four seats' Claude Code session logs.
Kept per assistant message: seat, message id, model, timestamp, token counts. No message text, prompt, path or account data.
Run on the operator's machine: python3 extract.py > usage.jsonl"""
import json, glob, os, sys
ROOT = os.path.expanduser('~/.claude/projects')
USER = os.path.basename(os.path.expanduser('~'))
SEATS = ['builder', 'verifier', 'cost-auditor', 'planner']
for s in SEATS:
    for f in sorted(glob.glob(f'{ROOT}/-Users-{USER}-band-work-seats-{s}/*.jsonl')):
        for line in open(f, encoding='utf-8'):
            try: d = json.loads(line)
            except ValueError: continue
            m = d.get('message')
            if not isinstance(m, dict) or 'usage' not in m: continue
            u = m['usage']; cc = u.get('cache_creation') or {}
            w5, w1 = cc.get('ephemeral_5m_input_tokens'), cc.get('ephemeral_1h_input_tokens')
            if w5 is None and w1 is None: w5, w1 = u.get('cache_creation_input_tokens', 0), 0
            print(json.dumps({'seat': s, 'id': m.get('id') or d.get('uuid'), 'model': m.get('model'),
                              'ts': d.get('timestamp', ''), 'in': u.get('input_tokens', 0), 'out': u.get('output_tokens', 0),
                              'cache_read': u.get('cache_read_input_tokens', 0), 'w5': w5 or 0, 'w1': w1 or 0},
                             separators=(',', ':')))
