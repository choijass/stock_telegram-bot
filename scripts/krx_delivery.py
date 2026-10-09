"""Shared durable delivery ledger; fail closed on uncertain Telegram outcomes."""
import base64
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests

KST = timezone(timedelta(hours=9))

def window(mode, date, now=None):
    now = now or datetime.now(KST)
    target = datetime.strptime(date + mode, '%Y-%m-%d%H%M').replace(tzinfo=KST)
    return target, target + timedelta(minutes=15 if mode == '1400' else 30), now

class Ledger:
    def __init__(self, mode, date):
        self.path = f'data/delivery/krx-{date}-{mode}.json'
        self.url = f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/contents/{self.path}"
        self.headers = {'Authorization': 'Bearer ' + os.environ['GITHUB_TOKEN'], 'Accept': 'application/vnd.github+json'}
        self.sha = None
        self.data = {'status': 'pending', 'parts': [], 'date': date, 'mode': mode}
        r = requests.get(self.url, headers=self.headers, params={'ref': 'main'}, timeout=30)
        if r.status_code != 404:
            r.raise_for_status()
            self.sha = r.json()['sha']
            self.data = json.loads(base64.b64decode(r.json()['content']))

    def save(self):
        body = {'message': 'delivery: KRX receipt', 'branch': 'main', 'content': base64.b64encode(json.dumps(self.data, ensure_ascii=False).encode()).decode()}
        if self.sha: body['sha'] = self.sha
        r = requests.put(self.url, headers=self.headers, json=body, timeout=30)
        r.raise_for_status()  # CAS conflict means no Telegram call is allowed.
        self.sha = r.json()['content']['sha']
        Path('results').mkdir(exist_ok=True)
        Path('results/delivery.json').write_text(json.dumps(self.data, indent=2), encoding='utf-8')

def chunks(msg):
    # Conservative UTF-16 length for astral characters / Telegram limit.
    while msg:
        cut = min(1900, len(msg))
        if len(msg) > cut:
            q = msg.rfind('\n', 0, cut)
            if q > 500: cut = q
        yield msg[:cut]
        msg = msg[cut:].lstrip()

def send_report(msg, token, chat, mode):
    date = os.environ.get('REPORT_DATE') or datetime.now(KST).strftime('%Y-%m-%d')
    target, deadline, now = window(mode, date)
    if not target <= now <= deadline:
        raise RuntimeError('Delivery window expired; no stale report sent')
    ledger = Ledger(mode, date)
    if ledger.data['status'] == 'delivered':
        print('Already delivered'); return
    if any(p['status'] == 'sending' for p in ledger.data['parts']):
        raise RuntimeError('Ambiguous Telegram outcome: manual reconciliation required; no automatic resend')
    # Freeze content so a partial retry cannot mix different market snapshots.
    ledger.data.setdefault('text', msg)
    parts = list(chunks(ledger.data['text']))
    for i, part in enumerate(parts):
        if datetime.now(KST) > deadline: raise RuntimeError('Delivery deadline expired')
        if i < len(ledger.data['parts']) and ledger.data['parts'][i]['status'] == 'sent': continue
        record = {'status': 'sending', 'sha256': hashlib.sha256(part.encode()).hexdigest()}
        if i == len(ledger.data['parts']): ledger.data['parts'].append(record)
        else: ledger.data['parts'][i] = record
        ledger.save()  # Persist intent BEFORE calling Telegram.
        try:
            r = requests.post(f'https://api.telegram.org/bot{token}/sendMessage', json={'chat_id': chat, 'text': part, 'disable_web_page_preview': True}, timeout=20)
            payload = r.json()
        except Exception:
            raise RuntimeError('Telegram response uncertain; automatic resend blocked') from None
        if payload.get('ok') is not True:
            # Only an explicit Bot API rejection is safe to retry.
            record['status'] = 'rejected'; ledger.save()
            raise RuntimeError(f"Telegram rejected message (code={payload.get('error_code')})")
        result = payload.get('result', {})
        if not result.get('message_id') or not result.get('chat', {}).get('id'):
            raise RuntimeError('Missing Telegram receipt; automatic resend blocked')
        record.update(status='sent', message_id=result['message_id'], chat_id=result['chat']['id'], telegram_date=result.get('date'), confirmed_at=datetime.now(KST).isoformat())
        ledger.save()
        time.sleep(1)
    ledger.data.update(status='delivered', delivered_at=datetime.now(KST).isoformat())
    ledger.save()
    print(f'Telegram delivery confirmed: {len(parts)} messages')

def main():
    mode = os.environ.get('REPORT_MODE')
    if not mode:
        mode = {'0 5 * * 1-5': '1400', '30 6 * * 1-5': '1530'}.get(os.environ.get('SCHEDULE_EXPR'))
    if mode not in ('1400', '1530'): raise RuntimeError('Explicit report mode required')
    date = os.environ.get('REPORT_DATE') or datetime.now(KST).strftime('%Y-%m-%d')
    target, deadline, now = window(mode, date)
    if now.weekday() >= 5 or now > deadline or now < target - timedelta(minutes=10):
        print('SKIP: outside report window'); return
    ledger = Ledger(mode, date)
    if ledger.data['status'] == 'delivered': print('SKIP: receipt already present'); return
    while datetime.now(KST) < target:
        time.sleep(min(10, (target - datetime.now(KST)).total_seconds()))
    os.environ.update(REPORT_MODE=mode, REPORT_DATE=date)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import krx_1430_report
    krx_1430_report.main()

if __name__ == '__main__': main()
