#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/choijas/stock_telegram-bot.git}"
BRANCH="${BRANCH:-main}"
GIT_DIR_FALLBACK="${GIT_DIR_FALLBACK:-/private/tmp/stock_telegram_bot_gitdir}"

if [ -d .git ]; then
  GIT=(git)
else
  if git init >/dev/null 2>&1; then
    GIT=(git)
  else
    mkdir -p "$GIT_DIR_FALLBACK"
    git --git-dir="$GIT_DIR_FALLBACK" --work-tree="$PWD" init
    GIT=(git --git-dir="$GIT_DIR_FALLBACK" --work-tree="$PWD")
  fi
fi

"${GIT[@]}" branch -M "$BRANCH"

if "${GIT[@]}" remote get-url origin >/dev/null 2>&1; then
  "${GIT[@]}" remote set-url origin "$REPO_URL"
else
  "${GIT[@]}" remote add origin "$REPO_URL"
fi

"${GIT[@]}" add macro.py requirements.txt README.md .gitignore .github/workflows/scheduled-macro.yml results/.gitkeep
"${GIT[@]}" commit -m "Add scheduled macro GitHub Actions workflow" || true
"${GIT[@]}" push -u origin "$BRANCH"
