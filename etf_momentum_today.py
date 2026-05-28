from __future__ import annotations

import math
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import yfinance as yf


KST = ZoneInfo("Asia/Seoul")
TODAY = datetime.now(KST).strftime("%Y-%m-%d")
OUTPUT_DIR = Path("results")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_REQUIRED = os.getenv("TELEGRAM_REQUIRED", "false").lower() in {"1", "true", "yes", "y"}

UNIVERSE = {
    "005930.KS": "삼성전자",
    "000660.KS": "SK하이닉스",
    "091170.KS": "KODEX 은행",
    "140700.KS": "KODEX 보험",
    "102970.KS": "KODEX 증권",
    "117700.KS": "KODEX 건설",
    "300950.KS": "KODEX 게임산업",
    "395160.KS": "KODEX 시스템반도체",
    "445290.KS": "KODEX K-로봇 액티브",
    "117460.KS": "KODEX 에너지화학",
    "091160.KS": "KODEX 반도체",
    "244580.KS": "KODEX 바이오",
    "228800.KS": "TIGER 여행레저",
    "364970.KS": "TIGER 바이오 TOP 10",
    "091180.KS": "KODEX 자동차",
    "305540.KS": "TIGER 2차전지테마",
    "462010.KS": "TIGER 2차전지소재Fn",
    "266360.KS": "KODEX 미디어&엔터테인먼트",
    "395150.KS": "KODEX 웹툰&드라마",
    "367760.KS": "RISE 5G테크",
    "228790.KS": "TIGER 화장품",
    "463250.KS": "TIGER 우주방산",
    "157490.KS": "TIGER 소프트웨어",
    "449450.KS": "PLUS K방산",
    "139230.KS": "TIGER 200 중공업",
    "150460.KS": "TIGER 중국소비테마",
    "139280.KS": "TIGER 경기방어",
    "438900.KS": "HANARO Fn K-푸드",
    "381570.KS": "HANARO Fn친환경에너지",
    "210780.KS": "KODEX 코스피고배당",
    "466920.KS": "SOL 조선TOP3플러스",
    "475300.KS": "SOL 반도체전공정",
    "475310.KS": "SOL 반도체후공정",
    "307510.KS": "TIGER 의료기기",
    "433500.KS": "ACE 원자력테마딥서치",
    "483020.KS": "KIWOOM 의료AI",
    "495040.KS": "PLUS 코리아밸류업",
    "496770.KS": "PLUS 글로벌방산",
    "395290.KS": "HANARO Fn K-POP&미디어",
    "102960.KS": "KODEX 기계장비",
    "307520.KS": "TIGER 지주회사",
    "365000.KS": "TIGER 인터넷TOP10",
    "463050.KS": "TIMEFOLIO K바이오액티브",
    "421320.KS": "PLUS 우주항공&UAM",
    "466930.KS": "SOL 자동차TOP3플러스",
    "457990.KS": "PLUS 태양광&ESS",
    "069500.KS": "KODEX 200",
}

BENCHMARK = "069500.KS"


def signed(value: float | int, digits: int = 0) -> str:
    if pd.isna(value):
        return "신규"
    if digits == 0:
        return f"{int(value):+d}"
    return f"{float(value):+.{digits}f}"


def pct_rank(s: pd.Series) -> pd.Series:
    return s.rank(pct=True) * 100


def download_panel() -> tuple[pd.DataFrame, pd.DataFrame]:
    tickers = sorted(UNIVERSE)
    raw = yf.download(
        tickers,
        period="1y",
        auto_adjust=True,
        group_by="column",
        progress=False,
        threads=True,
    )
    if raw.empty:
        raise RuntimeError("가격 데이터를 가져오지 못했습니다.")

    close = raw["Close"].copy() if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    volume = raw["Volume"].copy() if isinstance(raw.columns, pd.MultiIndex) else raw[["Volume"]]
    close = close.dropna(how="all").ffill()
    volume = volume.reindex(close.index).fillna(0)
    valid = [c for c in close.columns if close[c].notna().sum() >= 130]
    return close[valid], volume[valid]


def score_on(close: pd.DataFrame, volume: pd.DataFrame, row_pos: int = -1) -> pd.DataFrame:
    day_close = close.iloc[: row_pos + 1 if row_pos != -1 else None]
    day_volume = volume.reindex(day_close.index)
    latest_idx = day_close.index[-1]

    ret5 = day_close.pct_change(5).iloc[-1]
    ret10 = day_close.pct_change(10).iloc[-1]
    ret20 = day_close.pct_change(20).iloc[-1]
    ret60 = day_close.pct_change(60).iloc[-1]
    ret120 = day_close.pct_change(120).iloc[-1]

    strength_raw = ret20 * 0.45 + ret60 * 0.35 + ret120 * 0.20
    strength = pct_rank(strength_raw)

    ma5 = day_close.rolling(5).mean().iloc[-1]
    ma20 = day_close.rolling(20).mean().iloc[-1]
    ma60 = day_close.rolling(60).mean().iloc[-1]
    trend_raw = (
        (day_close.iloc[-1] > ma5).astype(int) * 20
        + (day_close.iloc[-1] > ma20).astype(int) * 35
        + (day_close.iloc[-1] > ma60).astype(int) * 25
        + ((ma20 > ma60).astype(int) * 20)
    )
    trend = trend_raw.astype(float)

    if BENCHMARK in day_close.columns:
        bm20 = day_close[BENCHMARK].pct_change(20).iloc[-1]
        bm60 = day_close[BENCHMARK].pct_change(60).iloc[-1]
    else:
        bm20 = ret20.mean()
        bm60 = ret60.mean()
    rs_raw = (ret20 - bm20) * 0.6 + (ret60 - bm60) * 0.4
    rs = pct_rank(rs_raw)

    wroc_raw = ret5 * 0.50 + ret10 * 0.30 + ret20 * 0.20
    wroc = pct_rank(wroc_raw)

    vol_ratio = (
        day_volume.tail(5).mean() / day_volume.tail(20).mean().replace(0, np.nan)
    ).replace([np.inf, -np.inf], np.nan)

    df = pd.DataFrame(
        {
            "ticker": day_close.columns,
            "name": [UNIVERSE.get(t, t) for t in day_close.columns],
            "date": latest_idx.strftime("%Y-%m-%d"),
            "ret5": ret5,
            "ret20": ret20,
            "ret60": ret60,
            "strength": strength,
            "trend": trend,
            "rs": rs,
            "wroc": wroc,
            "vol_ratio": vol_ratio,
        }
    ).dropna(subset=["strength", "trend", "rs", "wroc"])

    df["score_no_rs"] = df["strength"] * 0.55 + df["trend"] * 0.45
    df["score_rs"] = df["strength"] * 0.35 + df["trend"] * 0.30 + df["rs"] * 0.35
    df["score_short"] = df["wroc"] * 0.50 + df["strength"] * 0.25 + df["trend"] * 0.25
    return df.reset_index(drop=True)


def ranked(df: pd.DataFrame, score_col: str) -> pd.DataFrame:
    out = df.sort_values(score_col, ascending=False).reset_index(drop=True).copy()
    out["rank"] = np.arange(1, len(out) + 1)
    return out


def rank_change_map(cur: pd.DataFrame, prev: pd.DataFrame) -> dict[str, float]:
    prev_ranks = dict(zip(prev["ticker"], prev["rank"]))
    return {
        row["ticker"]: prev_ranks.get(row["ticker"], math.nan) - row["rank"]
        for _, row in cur.iterrows()
    }


def capped_weights(df: pd.DataFrame, score_col: str, top_n: int = 10, cap: float = 8.0) -> pd.Series:
    top = df.head(top_n).copy()
    scores = top[score_col].clip(lower=0)
    if scores.sum() == 0:
        raw = pd.Series(100 / top_n, index=top.index)
    else:
        raw = scores / scores.sum() * 100
    weights = raw.clip(upper=cap)
    remain = 100 - weights.sum()
    under = weights[weights < cap].index
    while remain > 0.01 and len(under) > 0:
        add = raw.loc[under] / raw.loc[under].sum() * remain
        weights.loc[under] = (weights.loc[under] + add).clip(upper=cap)
        new_remain = 100 - weights.sum()
        if abs(new_remain - remain) < 0.01:
            break
        remain = new_remain
        under = weights[weights < cap].index
    return weights.round(1)


def section_port(title: str, subtitle: str, cur: pd.DataFrame, prev: pd.DataFrame, score_col: str) -> list[str]:
    weights = capped_weights(cur, score_col)
    prev_weights = capped_weights(prev, score_col)
    prev_by_ticker = {prev.loc[i, "ticker"]: prev_weights.loc[i] for i in prev_weights.index}
    lines = [title, f"   {subtitle}"]
    for i, (_, row) in enumerate(cur.head(10).iterrows(), start=1):
        w = weights.iloc[i - 1]
        diff = w - prev_by_ticker.get(row["ticker"], 0.0)
        lines.append(f"{i}. {row['name']} - {w:.1f}% ({signed(diff, 1)})")
    return lines


def format_ranked_top20(cur: pd.DataFrame, prev: pd.DataFrame) -> list[str]:
    changes = rank_change_map(cur, prev)
    lines = ["📋 오늘 모멘텀 순위 Top 20"]
    for _, row in cur.head(20).iterrows():
        change = changes[row["ticker"]]
        text = "신규" if pd.isna(change) or abs(change) >= 999 else signed(change)
        lines.append(f"{int(row['rank'])}. {row['name']} ({text})")
    return lines


def component_rank_diff(name: str, cur_df: pd.DataFrame, prev_df: pd.DataFrame) -> tuple[int, int, int]:
    parts = []
    for col in ["strength", "trend", "rs"]:
        c = ranked(cur_df, col)
        p = ranked(prev_df, col)
        c_rank = int(c[c["ticker"] == name]["rank"].iloc[0])
        p_match = p[p["ticker"] == name]
        p_rank = int(p_match["rank"].iloc[0]) if not p_match.empty else c_rank
        parts.append(p_rank - c_rank)
    return tuple(parts)  # type: ignore[return-value]


def move_section(title: str, moves: list[tuple[str, int, tuple[int, int, int]]]) -> list[str]:
    lines = [title]
    if not moves:
        return lines + ["- 없음"]
    for name, total, parts in moves:
        a, b, c = parts
        lines.append(f"- {name} ({signed(total)}) = ({signed(a)}, {signed(b)}, {signed(c)})")
    return lines


def build_report() -> str:
    close, volume = download_panel()
    cur_scores = score_on(close, volume, -1)
    prev_scores = score_on(close, volume, -2)

    latest_date = cur_scores["date"].iloc[0]
    cur = ranked(cur_scores, "score_no_rs")
    prev = ranked(prev_scores, "score_no_rs")
    cur_rs = ranked(cur_scores, "score_rs")
    prev_rs = ranked(prev_scores, "score_rs")
    cur_short = ranked(cur_scores, "score_short")
    prev_short = ranked(prev_scores, "score_short")

    changes = rank_change_map(cur, prev)
    top20_tickers = set(cur.head(20)["ticker"])
    prev_top20_tickers = set(prev.head(20)["ticker"])

    risers = []
    fallers = []
    for _, row in cur.head(30).iterrows():
        change = changes.get(row["ticker"], math.nan)
        if pd.isna(change):
            continue
        parts = component_rank_diff(row["ticker"], cur_scores, prev_scores)
        item = (row["name"], int(change), parts)
        if change >= 3:
            risers.append(item)
        elif change <= -3:
            fallers.append(item)
    risers = sorted(risers, key=lambda x: x[1], reverse=True)[:3]
    fallers = sorted(fallers, key=lambda x: x[1])[:3]

    short_changes = rank_change_map(cur_short, prev_short)
    short_risers = []
    for _, row in cur_short.head(30).iterrows():
        change = short_changes.get(row["ticker"], math.nan)
        if pd.notna(change) and change >= 3:
            parts = component_rank_diff(row["ticker"], cur_scores, prev_scores)
            short_risers.append((row["name"], int(change), parts))
    short_risers = sorted(short_risers, key=lambda x: x[1], reverse=True)[:3]

    removed = [
        UNIVERSE.get(ticker, ticker)
        for ticker in prev_top20_tickers - top20_tickers
    ]

    new_entries = [
        row["name"]
        for _, row in cur[cur["ticker"].isin(top20_tickers - prev_top20_tickers)].head(5).iterrows()
    ]

    sections = [
        [f"📊 [오늘의 ETF 모멘텀 리포트] ({latest_date})"],
        format_ranked_top20(cur, prev),
        section_port(
            "📊 [ETF 추천 포트] RS 제외 Top 10",
            "(Strength 55% + Trend 45%)",
            cur,
            prev,
            "score_no_rs",
        ),
        move_section("📈 순위 상승이 큰 ETF", risers),
        move_section("📉 순위 하락이 큰 ETF (주의)", fallers),
        ["🗑 Top 20에서 퇴출된 ETF"] + ([f"- {x}" for x in removed] if removed else ["- 없음"]),
        section_port(
            "📊 [중장기] RS 합성 포트 Top 10",
            "(Strength 35% + Trend 30% + RS 35%)",
            cur_rs,
            prev_rs,
            "score_rs",
        ),
        section_port(
            "⚡️ [단기] wROC 기반 포트 Top 10",
            "(wROC 50% + Strength 25% + Trend 25%)",
            cur_short,
            prev_short,
            "score_short",
        ),
        move_section("📈 [단기] 순위 상승이 큰 ETF", short_risers),
        ["🔥 [A타입] 신규 진입 대장주"]
        + ([f"🔹 {name}" for name in new_entries] if new_entries else ["- 없음"]),
        ["📈 [B타입] 진입 후 상승 유지", "- 없음"],
        ["※ 상세 분석 결과는 로컬 CSV 파일로 저장되었습니다."],
    ]

    OUTPUT_DIR.mkdir(exist_ok=True)
    cur.to_csv(OUTPUT_DIR / f"etf_momentum_today_scores_{latest_date}.csv", index=False, encoding="utf-8-sig")
    report = "\n\n".join("\n".join(s) for s in sections)
    (OUTPUT_DIR / f"etf_momentum_today_report_{latest_date}.txt").write_text(report, encoding="utf-8")
    return report


def send_telegram_message(report: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        note = "[INFO] Telegram secret 없음: 메시지 발송 생략"
        if TELEGRAM_REQUIRED:
            raise RuntimeError(note)
        print(note)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    response = requests.post(
        url,
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": report,
            "disable_web_page_preview": "true",
        },
        timeout=60,
    )
    if not response.ok:
        raise RuntimeError(f"Telegram 메시지 발송 실패: {response.status_code} {response.text}")
    print("[OK] Telegram ETF 모멘텀 리포트 발송 완료")


if __name__ == "__main__":
    text = build_report()
    print(text)
    send_telegram_message(text)
