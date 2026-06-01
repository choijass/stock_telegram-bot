#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/Users/choijas/Documents/Codex/2026-05-29/15/stock_telegram-bot-work"
ENV_FILE="${SANGHANGA_ENV_FILE:-$REPO_DIR/.sanghanga.env}"

cd "$REPO_DIR"

if [ -f "$ENV_FILE" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$ENV_FILE"
  set +a
fi

export TZ="${TZ:-Asia/Seoul}"
export SANGHANGA_TELEGRAM_CHAT_ID="${SANGHANGA_TELEGRAM_CHAT_ID:-@sang_red}"
export PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-/private/tmp/python-pycache}"

/usr/bin/python3 scripts/send_sanghanga_report.py
