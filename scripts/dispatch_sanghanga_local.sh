#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd -P)"
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
