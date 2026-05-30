from __future__ import annotations

import os
import re
import subprocess
import sys
import textwrap
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yfinance as yf

import etf_auto_report
import etf_ma_full
import stocktrend_full_v3


LABELS = ["월", "화", "수", "목", "금"]
DIVIDER = "------------------------------"


def week_range(today: date | None = None) -> tuple[date, date]:
    current = today or datetime.now().date()
    monday = current - timedelta(days=current.weekday())
    return monday, monday + timedelta(days=4)


def short_name(name: object) -> str:
    text = str(name)
    for token in ["KODEX ", "TIGER ", "SOL ", "ACE ", "PLUS ", "HANARO ", "TIMEFOLIO ", "KIWOOM ", "RISE "]:
        text = text.replace(token, "")
    return text.strip()


def nearest(index: pd.Index, target: pd.Timestamp) -> pd.Timestamp | None:
    candidates = [pd.Timestamp(day) for day in index if pd.Timestamp(day).date() <= target.date()]
    return candidates[-1] if candidates else None


def rank_change(current: int, previous: int | None) -> str:
    if previous is None:
        return "NEW"
    diff = int(previous) - int(current)
    if diff > 0:
        return f"UP{diff}"
    if diff < 0:
        return f"DOWN{abs(diff)}"
    return "="


def compact_list(items: list[str], limit: int = 5) -> str:
    return ", ".join(items[:limit]) if items else "-"


def section_header(icon: str, title: str, subtitle: str) -> str:
    return f"{DIVIDER}\n{icon} {title}\n{subtitle}"


def bullet(text: str) -> str:
    return f"- {text}"


def metric_line(label: str, value: str) -> str:
    return f"  - {label}: {value}"


def request_json(url: str, token: str) -> dict:
    response = requests.get(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def signal_from_logs(start: date, end: date) -> list[dict[str, str]]:
    repo = os.getenv("GITHUB_REPOSITORY", "choijass/stock_telegram-bot")
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        return []

    runs_url = f"https://api.github.com/repos/{repo}/actions/workflows/signal-schedule-test.yml/runs?per_page=50"
    runs = request_json(runs_url, token).get("workflow_runs", [])
    by_day: dict[str, dict[str, str]] = {}
    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(end + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)

    for run in runs:
        created = datetime.fromisoformat(str(run.get("created_at", "")).replace("Z", "+00:00"))
        if not (start_dt <= created < end_dt):
            continue
        jobs_url = run.get("jobs_url")
        if not jobs_url:
            continue
        jobs = request_json(jobs_url, token).get("jobs", [])
        if not jobs:
            continue
        job_id = jobs[0].get("id")
        if not job_id:
            continue
        log_response = requests.get(
            f"https://api.github.com/repos/{repo}/actions/jobs/{job_id}/logs",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            timeout=30,
            allow_redirects=True,
        )
        if log_response.status_code >= 400:
            continue
        row = parse_signal_log(log_response.content.decode("utf-8", errors="replace"))
        if row:
            local_day = (created + timedelta(hours=9)).date()
            key = local_day.isoformat()
            previous = by_day.get(key)
            if previous is None or str(row.get("Timestamp", "")) > str(previous.get("Timestamp", "")):
                row["Date"] = key
                by_day[key] = row
    return [by_day[key] for key in sorted(by_day)]


def parse_signal_log(text: str) -> dict[str, str]:
    keys = [
        "Timestamp",
        "Mode",
        "Signal_Count",
        "Signals",
        "Position_Level",
        "Recommended_Stock_Position",
        "Recommended_Cash_Position",
        "Buy_Count",
        "Sell_Count",
        "Top10_Names",
        "Portfolio_Sectors",
        "Portfolio_Candidates",
        "Portfolio_Replacement",
    ]
    row: dict[str, str] = {}
    for key in keys:
        match = re.search(r"(?m)^.*?" + re.escape(key) + r"\s+(.+)$", text)
        if match:
            row[key] = match.group(1).strip()
    return row


def latest_signal_fallback() -> dict[str, str]:
    out_dir = Path("results_weekend_stock")
    env = dict(os.environ)
    env["TELEGRAM_REQUIRED"] = "false"
    env["RESULTS_DIR"] = str(out_dir)
    try:
        subprocess.run([sys.executable, "macro.py"], env=env, check=True, timeout=300)
    except Exception:
        return {}
    csvs = sorted(out_dir.glob("signal_*.csv"))
    if not csvs:
        return {}
    df = pd.read_csv(csvs[-1])
    first_col = str(df.columns[0]).replace("\ufeff", "")
    df = df.rename(columns={df.columns[0]: first_col})
    if {"Item", "Value"}.issubset(df.columns):
        return {str(k): str(v) for k, v in zip(df["Item"], df["Value"])}
    return {str(k): str(v) for k, v in zip(df.iloc[:, 0], df.iloc[:, 1])}


def build_signal_section(start: date, end: date) -> tuple[str, list[str]]:
    rows = signal_from_logs(start, end)
    if rows:
        latest = rows[-1]
        lines = [
            section_header("[01]", "SIGNAL 리스크 / 포지션", "시장모드 / 위험신호 / 포트 교체"),
            "[POINT] 최신 판단",
            metric_line("시장모드", latest.get("Mode", "-").replace("_MODE", "")),
            metric_line("포지션", latest.get("Position_Level", "-")),
            metric_line("주식/현금", f"{latest.get('Recommended_Stock_Position', '-')} / {latest.get('Recommended_Cash_Position', '-')}"),
            metric_line("위험신호", latest.get("Signal_Count", "-")),
            "",
            "[WEEK] 월~금 변화",
        ]
        positions = [r.get("Position_Level", "-") for r in rows]
        lines.append(bullet(f"포지션 흐름: {' -> '.join(positions)}"))
        for row in rows:
            day = datetime.fromisoformat(row["Date"]).strftime("%m-%d")
            lines.append(
                bullet(
                    f"{day} | {row.get('Mode', '-').replace('_MODE', '')} | 위험 {row.get('Signal_Count', '-')} | "
                    f"{row.get('Position_Level', '-')} | 주식 {row.get('Recommended_Stock_Position', '-')} | "
                    f"현금 {row.get('Recommended_Cash_Position', '-')} | 매수 {row.get('Buy_Count', '-')}"
                )
            )
        lines.extend(
            [
                "",
                "[PORT] 포트폴리오 변화",
                bullet(f"섹터 구성: {latest.get('Portfolio_Sectors', '-')}"),
                bullet(f"포트 후보: {latest.get('Portfolio_Candidates', '-')}"),
                bullet(f"교체 예상: {latest.get('Portfolio_Replacement', '-')}"),
            ]
        )
        watch = [
            latest.get("Portfolio_Candidates", "").split("(")[0],
            latest.get("Portfolio_Sectors", "").split(":")[0],
        ]
        return "\n".join(lines), [item for item in watch if item]

    latest = latest_signal_fallback()
    lines = [
        section_header("[01]", "SIGNAL 리스크 / 포지션", "시장모드 / 위험신호 / 포트 교체"),
        "[POINT] 최신 SIGNAL 기준 요약",
        metric_line("시장모드", latest.get("Mode", "-")),
        metric_line("포지션", latest.get("Position_Level", "-")),
        metric_line("주식/현금", f"{latest.get('Recommended_Stock_Position', '-')} / {latest.get('Recommended_Cash_Position', '-')}"),
        metric_line("위험신호", latest.get("Signal_Count", "-")),
        "",
        "[PORT] 포트폴리오 변화",
        bullet(f"섹터 구성: {latest.get('Portfolio_Sectors', '-')}"),
        bullet(f"포트 후보: {latest.get('Portfolio_Candidates', '-')}"),
        bullet(f"교체 예상: {latest.get('Portfolio_Replacement', '-')}"),
    ]
    return "\n".join(lines), [latest.get("Portfolio_Candidates", "").split("(")[0]]


def build_etf_rs_section(start: date, end: date) -> tuple[str, list[str]]:
    _, etf_data, _, _ = etf_auto_report.download_data()
    targets = [pd.Timestamp(start + timedelta(days=i)) for i in range(5)]
    previous: dict[str, int] = {}
    daily_top3: list[str] = []
    friday_rows: list[str] = []
    final_names: list[str] = []

    for label, target in zip(LABELS, targets):
        day = nearest(etf_data.index, target)
        if day is None:
            continue
        pos = etf_data.index.get_loc(day)
        benchmark = etf_data["069500.KS"].pct_change(20).iloc[pos] if "069500.KS" in etf_data.columns else etf_data.pct_change(20).iloc[pos].mean()
        ret = etf_data.pct_change(20).iloc[pos]
        rs = ret - benchmark
        df = pd.DataFrame(
            {
                "ticker": rs.index,
                "name": [etf_auto_report.korea_industry_etfs.get(t, t) for t in rs.index],
                "ret20": (ret * 100).round(1),
                "rs": (rs * 100).round(1),
            }
        ).dropna().sort_values("rs", ascending=False).reset_index(drop=True)
        df.insert(0, "rank", range(1, len(df) + 1))
        top3 = [short_name(name) for name in df["name"].head(3).tolist()]
        daily_top3.append(bullet(f"{label} {day:%m-%d} | TOP3: {compact_list(top3, 3)}"))
        if label == "금":
            for _, row in df.head(5).iterrows():
                change = rank_change(int(row["rank"]), previous.get(str(row["ticker"])))
                friday_rows.append(f"{int(row['rank'])}. {short_name(row['name'])}  | {change} | 20D {row['ret20']}% | RS {row['rs']}")
            final_names = top3
        previous = {str(row["ticker"]): int(row["rank"]) for _, row in df.iterrows()}

    lines = [
        section_header("[02]", "ETF RS 상대강도", "월~금 TOP3 / 금요일 TOP5 / 순위변화"),
        "[WEEK] 월~금 주도 ETF",
        *daily_top3,
        "",
        "[TOP5] 금요일 TOP5",
        *friday_rows,
    ]
    return "\n".join(lines), final_names


def build_stocktrend_section(start: date, end: date) -> tuple[str, list[str]]:
    sector_tickers = {sector: [ticker for _, ticker in members] for sector, members in stocktrend_full_v3.ETF_SECTORS.items()}
    tickers = sorted({ticker for members in sector_tickers.values() for ticker in members})
    raw = yf.download(tickers, period="9mo", auto_adjust=True, progress=False, threads=True)
    close = raw["Close"].sort_index().dropna(how="all") if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]].rename(columns={"Close": tickers[0]})
    volume = raw["Volume"].sort_index().dropna(how="all") if isinstance(raw.columns, pd.MultiIndex) and "Volume" in raw.columns.get_level_values(0) else pd.DataFrame(index=close.index)

    daily_top3: list[str] = []
    friday_rows: list[str] = []
    final_names: list[str] = []
    previous: dict[str, int] = {}
    for label, target in zip(LABELS, [pd.Timestamp(start + timedelta(days=i)) for i in range(5)]):
        day = nearest(close.index, target)
        if day is None:
            continue
        pos = close.index.get_loc(day)
        rows = []
        for sector, members in sector_tickers.items():
            valid = [ticker for ticker in members if ticker in close.columns]
            if not valid or pos < 20:
                continue
            ret5 = (close[valid].pct_change(5).iloc[pos] * 100).mean()
            ret20 = (close[valid].pct_change(20).iloc[pos] * 100).mean()
            vol_ratio = np.nan
            if not volume.empty:
                vol_ratio = (volume[valid].iloc[pos] / volume[valid].rolling(20).mean().iloc[pos]).replace([np.inf, -np.inf], np.nan).mean()
            score = float(np.nan_to_num(ret5, nan=0)) * 2 + float(np.nan_to_num(ret20, nan=0)) + float(np.nan_to_num(vol_ratio, nan=1)) * 5
            rows.append((sector, score, ret5, ret20, vol_ratio))
        rows.sort(key=lambda item: item[1], reverse=True)
        top3 = [sector for sector, *_rest in rows[:3]]
        daily_top3.append(bullet(f"{label} {day:%m-%d} | TOP3: {compact_list(top3, 3)}"))
        if label == "금":
            final_names = top3
            for idx, (sector, score, ret5, ret20, vol) in enumerate(rows[:5], 1):
                level = "강관심" if score >= 20 else "관심" if score >= 10 else "관찰"
                friday_rows.append(
                    f"{idx}. {sector} | {rank_change(idx, previous.get(sector))} | {level} | "
                    f"Score {score:.1f} | 5D {ret5:.1f}% | 20D {ret20:.1f}% | 거래 {vol:.1f}x"
                )
        previous = {sector: idx for idx, (sector, *_rest) in enumerate(rows, 1)}

    lines = [
        section_header("[03]", "주식트렌드", "Boom Score / 강관심 섹터 / 확산 흐름"),
        "[WEEK] 월~금 주도 섹터",
        *daily_top3,
        "",
        "[TOP5] 금요일 TOP5",
        *friday_rows,
    ]
    return "\n".join(lines), final_names


def build_etf_ma_section(start: date, end: date) -> tuple[str, list[str]]:
    name_by_ticker = etf_ma_full.UNIVERSE_TICKERS
    tickers = sorted(name_by_ticker)
    raw = yf.download(tickers, period="9mo", auto_adjust=True, progress=False, threads=True)
    close = raw["Close"].sort_index().dropna(how="all") if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]].rename(columns={"Close": tickers[0]})

    daily_top3: list[str] = []
    friday_rows: list[str] = []
    final_names: list[str] = []
    previous: dict[str, int] = {}
    for label, target in zip(LABELS, [pd.Timestamp(start + timedelta(days=i)) for i in range(5)]):
        day = nearest(close.index, target)
        if day is None:
            continue
        scored = []
        for ticker in close.columns:
            series = close[ticker].dropna()
            if day not in series.index:
                continue
            pos = series.index.get_loc(day)
            if pos < 60:
                continue
            ma5 = series.rolling(5).mean()
            ma10 = series.rolling(10).mean()
            ma20 = series.rolling(20).mean()
            updown = [
                "위" if series.iloc[pos] > ma5.iloc[pos] else "아래",
                "위" if series.iloc[pos] > ma10.iloc[pos] else "아래",
                "위" if series.iloc[pos] > ma20.iloc[pos] else "아래",
            ]
            if ma5.iloc[pos] > ma10.iloc[pos] > ma20.iloc[pos]:
                stack = "정배열"
            elif ma5.iloc[pos] < ma10.iloc[pos] < ma20.iloc[pos]:
                stack = "역배열"
            else:
                stack = "혼조"
            ret20 = series.pct_change(20).iloc[pos] * 100
            score = float(np.nan_to_num(ret20, nan=0)) + (10 if updown == ["위", "위", "위"] else 0) + (8 if stack == "정배열" else 0)
            scored.append((ticker, name_by_ticker.get(ticker, ticker), score, ret20, "/".join(updown), stack))
        scored.sort(key=lambda item: item[2], reverse=True)
        top3 = [short_name(name) for _ticker, name, *_rest in scored[:3]]
        daily_top3.append(bullet(f"{label} {day:%m-%d} | TOP3: {compact_list(top3, 3)}"))
        if label == "금":
            final_names = top3
            for idx, (ticker, name, score, ret20, updown, stack) in enumerate(scored[:5], 1):
                friday_rows.append(
                    f"{idx}. {short_name(name)} | {rank_change(idx, previous.get(ticker))} | "
                    f"점수 {score:.1f} | 20D {ret20:.1f}% | 이평 {updown} | {stack}"
                )
        previous = {ticker: idx for idx, (ticker, *_rest) in enumerate(scored, 1)}

    lines = [
        section_header("[04]", "ETF 20일선", "5/10/20일선 / 정배열 / 관심후보"),
        "[WEEK] 월~금 MA 후보",
        *daily_top3,
        "",
        "[TOP5] 금요일 TOP5",
        *friday_rows,
    ]
    return "\n".join(lines), final_names


def build_message() -> str:
    start, end = week_range()
    signal_text, signal_watch = build_signal_section(start, end)
    rs_text, rs_watch = build_etf_rs_section(start, end)
    stock_text, stock_watch = build_stocktrend_section(start, end)
    ma_text, ma_watch = build_etf_ma_section(start, end)

    watch_counter = Counter(signal_watch + rs_watch + stock_watch + ma_watch)
    watch = [name for name, _count in watch_counter.most_common(8) if name and name != "-"]
    summary = [
        section_header("[05]", "전체 종합 판단", "다음 주 관찰 우선순위"),
        "[POINT] 핵심 체크",
        bullet("SIGNAL 포지션을 기준으로 주식/현금 비중을 먼저 정합니다."),
        bullet("ETF RS 상위와 ETF 20일선 정배열이 겹치는 후보를 우선 관찰합니다."),
        bullet("주식트렌드 강관심 섹터가 RS/MA 후보와 연결되면 우선순위를 올립니다."),
        bullet("교체 예상 종목은 RS 약화와 낙폭확대가 이어지는지 확인합니다."),
        "",
        "[WATCH] 다음 주 우선 관찰",
        compact_list(watch, 8),
    ]
    return "\n\n".join(
        [
            "[REPORT] 종합버젼stock",
            "주말 종합 리포트",
            f"[DATE] 기간: {start:%Y.%m.%d} ~ {end:%Y.%m.%d}",
            signal_text,
            rs_text,
            stock_text,
            ma_text,
            "\n".join(summary),
        ]
    )


def chunks(text: str, limit: int = 3500) -> list[str]:
    parts: list[str] = []
    current = ""
    for block in textwrap.dedent(text).strip().split("\n\n"):
        candidate = block if not current else f"{current}\n\n{block}"
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                parts.append(current)
            current = block
    if current:
        parts.append(current)
    return parts


def send_telegram(text: str) -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    parts = chunks(text)
    for idx, message in enumerate(parts, 1):
        prefix = f"[종합버젼stock {idx}/{len(parts)}]\n\n" if len(parts) > 1 else ""
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": prefix + message, "disable_web_page_preview": "true"},
            timeout=30,
        )
        response.raise_for_status()
        print(f"sent part {idx}/{len(parts)}")


def main() -> None:
    message = build_message()
    print(message)
    if os.getenv("TELEGRAM_REQUIRED", "true").lower() in {"1", "true", "yes", "y"}:
        send_telegram(message)


if __name__ == "__main__":
    main()
