#!/usr/bin/env python3
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

REPO = os.environ["GITHUB_REPOSITORY"]
TOKEN = os.environ["GITHUB_TOKEN"]
API = f"https://api.github.com/repos/{REPO}"
EVENT_PATH = os.environ.get("GITHUB_EVENT_PATH", "")

DOMESTIC = [
    "etf-auto-report.yml",
    "etf-ma-auto-report.yml",
    "etf-momentum-today.yml",
    "stocktrend-auto-report.yml",
    "signal-schedule-test.yml",
]
US = ["us-korea-market-reports.yml"]


def event_schedule():
    if not EVENT_PATH:
        return ""
    with open(EVENT_PATH, encoding="utf-8") as f:
        return json.load(f).get("schedule", "")


def request(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read()
        return json.loads(raw) if raw else {}


def recent_runs(workflow):
    wf = urllib.parse.quote(workflow, safe="")
    result = request("GET", f"/actions/workflows/{wf}/runs?event=schedule&per_page=10")
    return result.get("workflow_runs", [])


def needs_retry(workflow, now):
    cutoff = now - timedelta(minutes=55)
    relevant = []
    for run in recent_runs(workflow):
        created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
        if created >= cutoff:
            relevant.append(run)

    for run in relevant:
        if run["status"] in {"queued", "in_progress"}:
            return False, f"already {run['status']}"
        if run.get("conclusion") == "success":
            return False, "already succeeded"

    if relevant:
        return True, "recent scheduled run failed"
    return True, "scheduled run missing"


def dispatch(workflow):
    wf = urllib.parse.quote(workflow, safe="")
    request("POST", f"/actions/workflows/{wf}/dispatches", {"ref": "main"})


def main():
    schedule = event_schedule()
    if schedule in {"15 2,4 * * 1-5", "45 5 * * 1-5"}:
        targets = DOMESTIC
    elif schedule == "10 22 * * 1-5":
        targets = US
    else:
        print(f"No watchdog target for schedule: {schedule!r}")
        return 0

    now = datetime.now(timezone.utc)
    failed = []
    for workflow in targets:
        try:
            retry, reason = needs_retry(workflow, now)
            if retry:
                dispatch(workflow)
                print(f"[RETRY] {workflow}: {reason}")
            else:
                print(f"[SKIP] {workflow}: {reason}")
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            failed.append(f"{workflow}: {exc}")
            print(f"[ERROR] {workflow}: {exc}", file=sys.stderr)

    if failed:
        raise RuntimeError("; ".join(failed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
