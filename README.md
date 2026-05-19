# Korea RS Live System

GitHub Actions scheduled runner for `macro.py`.

## Schedule

The workflow runs on weekdays at 10:00, 12:00, 14:00, and 15:00 KST.

GitHub Actions uses UTC, so the cron is:

```text
0 1,3,5,6 * * 1-5
```

You can also run it manually from GitHub Actions with `workflow_dispatch`.

## Output

The workflow now outputs only the `SIGNAL` table:

- Prints the `SIGNAL` table in the Actions log
- Saves `results/signal_YYYY-MM-DD.csv`
- Updates only the `SIGNAL` worksheet in Google Sheets
- Sends only the `SIGNAL` summary to Telegram

## Google Sheets

To save results to Google Sheets, add this repository secret:

```text
GOOGLE_SERVICE_ACCOUNT_JSON
```

Paste the full Google service account JSON as the secret value, then share the target spreadsheet with the service account email.

If the secret is missing, the job still runs and saves CSV files under `results/`.

## Telegram

To send the `SIGNAL` summary to Telegram, add these repository secrets:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
```
