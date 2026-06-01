#!/bin/zsh
set -euo pipefail

REPO_DIR="/Users/choijas/Documents/stock_telegram-bot"
cd "${REPO_DIR}"

mkdir -p logs results .pycache_tmp

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

export TZ="Asia/Seoul"
export PYTHONPYCACHEPREFIX="/tmp/stock_telegram_bot_pycache"

exec "${REPO_DIR}/.venv/bin/python" "${REPO_DIR}/telegram_news_collector.py"
