#!/usr/bin/env python3
"""Send a verified, pre-generated institution/NXT report to one Telegram channel."""
import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
KST = ZoneInfo("Asia/Seoul")
LIMIT = 3900

def split_message(text):
    while len(text) > LIMIT:
        cut = text.rfind("\n", 0, LIMIT)
        if cut < 100:
            cut = LIMIT
        yield text[:cut]
        text = text[cut:].lstrip("\n")
    if text:
        yield text

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=datetime.now(KST).strftime("%Y-%m-%d"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    report_path = ROOT / "reports" / "institution_nxt" / (args.date + ".txt")
    if not report_path.is_file():
        print(f"SKIP: no verified report at {report_path}")
        return 0
    content = report_path.read_text(encoding="utf-8").strip()
    if len(content) < 60:
        print("SKIP: report empty or too short")
        return 0
    if args.dry_run:
        print(f"DRY RUN: verified report, {len(content)} chars")
        return 0
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_TREND_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("TELEGRAM_BOT_TOKEN and TELEGRAM_TREND_CHAT_ID secrets required")
    # GitHub workflow concurrency provides at-most-one active scheduled run.
    for part in split_message(content):
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": part,
            "disable_web_page_preview": "true",
        }).encode()
        request = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage", data=data, method="POST"
        )
        with urllib.request.urlopen(request, timeout=25) as response:
            result = json.load(response)
        if not result.get("ok"):
            raise RuntimeError("Telegram did not confirm delivery")
    print("DELIVERED: institution/NXT report to trend channel")
    return 0

if __name__ == "__main__":
    sys.exit(main())
