#!/usr/bin/env python3
import argparse, hashlib, json, sys
from pathlib import Path

def commit(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str).encode()).hexdigest()

def parse_laws(text):
    laws, current = {}, {}
    def flush():
        if not current: return
        law_id = current.get('id') or current.get('heading')
        if not law_id: return
        require = tuple(p.strip() for p in current.get('require', '').split(',') if p.strip())
        laws[law_id] = {'id': law_id, 'check': current.get('check', 'none'), 'require': require}
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith('## '):
            flush(); current = {'heading': line[3:].strip()}; continue
        if line.startswith('- ') and ':' in line:
            key, value = line[2:].split(':', 1); current[key.strip()] = value.strip()
    flush(); return laws

def check_balance(evidence):
    start = int(evidence.get('opening_balance', 0)); running = start
    for amount in evidence.get('withdrawals', []):
        running -= int(amount)
        if running < 0:
            return {'opening_balance': start, 'withdrawal': int(amount), 'resulting_balance': running, 'broken_law': 'balance never negative'}
    return None

def judge(law, claim):
    evidence = claim.get('evidence') or {}
    missing = [k for k in law['require'] if k not in evidence]
    if missing:
        return 'INCOMPLETE', {'missing_evidence': missing, 'producer_said_success': claim.get('claim_success')}
    if law['check'] == 'balance_never_negative':
        hit = check_balance(evidence)
        if hit:
            return 'REJECT', hit
    return 'ADMIT', None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--claim', type=Path, required=True)
    parser.add_argument('--law', type=Path, default=Path('LAW.md'))
    parser.add_argument('--out', type=Path, default=Path('out'))
    args = parser.parse_args()
    laws = parse_laws(args.law.read_text())
    claim = json.loads(args.claim.read_text())
    overall, rows = 'ADMIT', []
    rank = {'ADMIT': 0, 'INCOMPLETE': 1, 'REJECT': 2}
    for law_id in claim.get('laws') or list(laws):
        law = laws.get(law_id)
        verdict, witness = ('INCOMPLETE', {'unknown_law': law_id}) if not law else judge(law, claim)
        if rank[verdict] > rank[overall]:
            overall = verdict
        rows.append((law_id, verdict, witness, commit({'law': law_id, 'verdict': verdict, 'witness': witness})))
    args.out.mkdir(parents=True, exist_ok=True)
    lines = ['## Claim Gate', '', f'**{overall}** — producer is untrusted.', '']
    for law_id, verdict, witness, receipt in rows:
        lines.append(f'### `{law_id}` — {verdict}')
        if witness:
            lines.append(f'- witness: `{json.dumps(witness)}`')
        lines.append(f'- receipt: `{receipt}`')
        lines.append('')
    if overall != 'ADMIT':
        lines.append('_Merge stays blocked._')
    md = '\n'.join(lines) + '\n'
    (args.out / 'verdict.txt').write_text(overall + '\n')
    (args.out / 'comment.md').write_text(md)
    sys.stdout.write(md)
    return 0 if overall == 'ADMIT' else 1

if __name__ == '__main__':
    raise SystemExit(main())
