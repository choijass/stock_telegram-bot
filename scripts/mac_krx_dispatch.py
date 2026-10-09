#!/usr/bin/env python3
"""Called every minute; dispatch early and verify durable Telegram receipts."""
import base64
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

REPO = 'choijass/stock_telegram-bot'
KST = dt.timezone(dt.timedelta(hours=9))

def api(path, *args):
    p = subprocess.run(['gh', 'api', path, *args], capture_output=True, text=True)
    if p.returncode:
        if 'HTTP 404' in p.stderr: return None
        raise RuntimeError('GitHub API failed; check gh authentication/permissions')
    return json.loads(p.stdout) if p.stdout.strip() else {}

def main():
    now = dt.datetime.now(KST)
    if now.weekday() >= 5: return
    date = now.strftime('%Y-%m-%d')
    for mode in ('1400', '1530'):
        target = now.replace(hour=int(mode[:2]), minute=int(mode[2:]), second=0, microsecond=0)
        end = target + dt.timedelta(minutes=15 if mode == '1400' else 30)
        if not target - dt.timedelta(minutes=5) <= now <= end: continue
        obj = api(f'repos/{REPO}/contents/data/delivery/krx-{date}-{mode}.json?ref=main')
        ledger = json.loads(base64.b64decode(obj['content'])) if obj else {}
        if ledger.get('status') == 'delivered':
            print(f'{date} {mode}: Telegram receipt confirmed'); continue
        if any(p['status'] == 'sending' for p in ledger.get('parts', [])):
            print(f'{date} {mode}: UNCERTAIN delivery; inspect ledger and Telegram; resend blocked', file=sys.stderr); continue
        # Persistent local cooldown also covers an accepted dispatch before its run appears.
        state = Path.home() / '.local/state/krx-dispatch'
        state.mkdir(parents=True, exist_ok=True)
        marker = state / f'{date}-{mode}'
        if marker.exists() and now.timestamp() - float(marker.read_text()) < 300: continue
        runs = api(f'repos/{REPO}/actions/workflows/krx-1430-report.yml/runs?per_page=30')['workflow_runs']
        if any(r['status'] in ('queued', 'in_progress', 'waiting', 'pending') and r['head_branch'] == 'main' for r in runs):
            print(f'{mode}: active run; waiting for receipt'); continue
        marker.write_text(str(now.timestamp()))  # ambiguous dispatch responses are not retried immediately
        api(f'repos/{REPO}/actions/workflows/krx-1430-report.yml/dispatches', '--method', 'POST', '-f', 'ref=main', '-f', f'inputs[report_mode]={mode}', '-f', f'inputs[report_date]={date}')
        print(f'{now.isoformat()} dispatch accepted for {mode}; receipt not yet confirmed')

if __name__ == '__main__': main()
