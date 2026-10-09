#!/bin/bash
set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
command -v gh >/dev/null
command -v python3 >/dev/null
gh auth status
ROOT=$(cd "$(dirname "$0")/.." && pwd)
DEST="$HOME/.local/share/krx-dispatch"
mkdir -p "$DEST" "$HOME/Library/Logs/krx-dispatch"
cp "$ROOT/scripts/mac_krx_dispatch.py" "$DEST/dispatch.py"
PYTHON=$(command -v python3)
cat > "$DEST/run.sh" <<EOF
#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
exec "$PYTHON" "$DEST/dispatch.py"
EOF
chmod 700 "$DEST/run.sh"
# Every minute in any machine timezone; the Python guard uses Asia/Seoul.
TMP=$(mktemp)
trap 'rm -f "$TMP"' EXIT
(crontab -l 2>/dev/null || true) | sed '/# krx-dispatch-managed$/d' > "$TMP"
printf '* * * * * "%s/run.sh" >> "%s/Library/Logs/krx-dispatch/cron.log" 2>&1 # krx-dispatch-managed\n' "$DEST" "$HOME" >> "$TMP"
crontab "$TMP"
printf 'Installed. Mac must remain awake and connected. Logs: %s/Library/Logs/krx-dispatch/cron.log\n' "$HOME"
