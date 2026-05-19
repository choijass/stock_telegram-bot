# Korea RS Live System

GitHub Actions scheduled runner for `macro.py`.

## Schedule

The workflow runs on weekdays at 08:30 KST.

GitHub Actions uses UTC, so the cron is:

```text
30 23 * * 0-4
```

You can also run it manually from GitHub Actions with `workflow_dispatch`.

## Google Sheets

To save results to Google Sheets, add this repository secret:

```text
GOOGLE_SERVICE_ACCOUNT_JSON
```

Paste the full Google service account JSON as the secret value, then share the target spreadsheet with the service account email.

If the secret is missing, the job still runs and saves CSV files under `results/`.
