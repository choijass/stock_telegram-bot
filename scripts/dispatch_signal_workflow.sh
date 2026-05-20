#!/bin/zsh
set -euo pipefail

REPO="choijass/stock_telegram-bot"
WORKFLOW="signal-schedule-test.yml"
REF="main"

TOKEN="$(
  printf 'protocol=https\nhost=github.com\n\n' \
    | git credential-osxkeychain get \
    | awk -F= '$1 == "password" { print $2; exit }'
)"

if [[ -z "${TOKEN}" ]]; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') GitHub token not found in macOS keychain" >&2
  exit 1
fi

STATUS="$(
  curl -sS -o /tmp/stock_telegram_dispatch_response.txt -w '%{http_code}' \
    -X POST \
    -H "Accept: application/vnd.github+json" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches" \
    -d "{\"ref\":\"${REF}\"}"
)"

if [[ "${STATUS}" != "204" ]]; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') dispatch failed: HTTP ${STATUS}" >&2
  cat /tmp/stock_telegram_dispatch_response.txt >&2
  exit 1
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') dispatched ${REPO}/${WORKFLOW}"
