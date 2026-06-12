from __future__ import annotations

import math
import os
import json
import re
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
ENTRY_STATE_PATH = OUTPUT_DIR / "etf_momentum_entry_state.json"

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

ETF_HOLDINGS = {
    "266360.KS": [
        ("035420", "NAVER", 27.64),
        ("036570", "NC", 9.95),
        ("035720", "카카오", 16.53),
        ("251270", "넷마블", 2.58),
        ("030000", "제일기획", 2.53),
    ],
    "300950.KS": [
        ("036570", "NC", 28.99),
        ("192080", "더블유게임즈", 5.11),
        ("251270", "넷마블", 9.82),
        ("462870", "시프트업", 7.08),
        ("095660", "네오위즈", 1.60),
    ],
    "462010.KS": [
        ("020150", "롯데에너지머티리얼즈", 0.95),
        ("051910", "LG화학", 11.55),
        ("066970", "엘앤에프", 2.90),
        ("003670", "포스코퓨처엠", 20.84),
        ("011790", "SKC", 2.62),
    ],
    "157490.KS": [
        ("064400", "LG씨엔에스", 8.77),
        ("018260", "삼성에스디에스", 17.40),
        ("035420", "NAVER", 23.39),
        ("036570", "NC", 6.53),
        ("022100", "포스코DX", 2.45),
    ],
}

ETF_ALIASES = {
    "462010.KS": "TIGER 2차전지소재Fn",
}


def signed(value: float | int, digits: int = 0) -> str:
    if pd.isna(value):
        return "신규"
    if digits == 0:
        return f"{int(value):+d}"
    return f"{float(value):+.{digits}f}"


def clean_html_text(value: str) -> str:
    text = re.sub(r"<.*?>", "", value)
    text = text.replace("&nbsp;", "").replace("\xa0", "").strip()
    return text


def to_float(value: object, default: float = math.nan) -> float:
    try:
        text = str(value).replace(",", "").replace("%", "").strip()
        if text in {"", "-", "nan", "None"}:
            return default
        return float(text)
    except Exception:
        return default


def fmt_weight(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return f"{text}%"


def stock_code_suffix(code: str) -> str:
    return str(code).split(".")[0][-6:].zfill(6)


def load_entry_state() -> dict:
    if not ENTRY_STATE_PATH.exists():
        return {"a_entries": {}}
    try:
        return json.loads(ENTRY_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"a_entries": {}}


def save_entry_state(state: dict) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    ENTRY_STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def fetch_naver_daily(code: str, min_rows: int = 25) -> pd.DataFrame:
    rows = []
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": f"https://finance.naver.com/item/main.naver?code={code}",
    }
    for page in range(1, 8):
        url = f"https://finance.naver.com/item/sise_day.naver?code={code}&page={page}"
        response = session.get(url, headers=headers, timeout=20)
        response.encoding = "euc-kr"
        for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", response.text, flags=re.S | re.I):
            cells = [clean_html_text(x) for x in re.findall(r"<td[^>]*>(.*?)</td>", row_html, flags=re.S | re.I)]
            cells = [x for x in cells if x]
            if len(cells) < 7 or not re.match(r"\d{4}\.\d{2}\.\d{2}", cells[0]):
                continue
            rows.append(
                {
                    "date": cells[0],
                    "close": to_float(cells[1]),
                    "open": to_float(cells[3]),
                    "high": to_float(cells[4]),
                    "low": to_float(cells[5]),
                    "volume": to_float(cells[6], 0),
                }
            )
        if len(rows) >= min_rows:
            break

    df = pd.DataFrame(rows).dropna(subset=["close"])
    if df.empty:
        raise RuntimeError(f"네이버 일봉 데이터 없음: {code}")
    return df.drop_duplicates("date").sort_values("date").reset_index(drop=True)


def build_stock_snapshot(code: str) -> dict:
    df = fetch_naver_daily(code)
    latest = df.iloc[-1]
    close = float(latest["close"])
    ret5 = math.nan
    if len(df) >= 6:
        base = float(df["close"].iloc[-6])
        if base:
            ret5 = (close / base - 1) * 100

    vol_ratio = math.nan
    if len(df) >= 20:
        vol20 = df["volume"].tail(20).mean()
        vol5 = df["volume"].tail(5).mean()
        if vol20:
            vol_ratio = vol5 / vol20

    ma20 = df["close"].tail(20).mean() if len(df) >= 20 else math.nan
    ma_pass = bool(pd.notna(ma20) and close > float(ma20))
    return {
        "code": code,
        "close": close,
        "ret5": ret5,
        "vol_ratio": vol_ratio,
        "ma20": ma20,
        "ma_pass": ma_pass,
    }


def leader_mark(snapshot: dict) -> str:
    ret5 = snapshot.get("ret5", math.nan)
    vol_ratio = snapshot.get("vol_ratio", math.nan)
    ma_pass = bool(snapshot.get("ma_pass", False))
    if ma_pass and pd.notna(ret5) and ret5 >= 8:
        return "★★"
    if ma_pass and pd.notna(vol_ratio) and vol_ratio >= 1.5:
        return "★★"
    if pd.notna(ret5) and ret5 >= 15 and pd.notna(vol_ratio) and vol_ratio >= 1.2:
        return "★★"
    if ma_pass or (pd.notna(ret5) and ret5 >= 2) or (pd.notna(vol_ratio) and vol_ratio >= 1.5):
        return "★"
    return "-"


def format_leader_stock_line(rank: int, name: str, code: str, weight: float, snapshot: dict) -> list[str]:
    mark = leader_mark(snapshot)
    ret5 = snapshot.get("ret5", math.nan)
    vol_ratio = snapshot.get("vol_ratio", math.nan)
    ma_text = "✅" if snapshot.get("ma_pass") else "❌"
    ret_text = "-" if pd.isna(ret5) else f"{ret5:+.1f}%"
    vol_text = "-" if pd.isna(vol_ratio) else f"{vol_ratio:.1f}x"
    return [
        f"{rank}. {mark} {name} ({code})",
        f"   비중 {fmt_weight(weight)} | 5일 {ret_text} | 거래량 {vol_text} | MA {ma_text}",
    ]


def holdings_for_etf(ticker: str) -> list[tuple[str, str, float]]:
    holdings = ETF_HOLDINGS.get(ticker)
    if holdings:
        return holdings
    return [(stock_code_suffix(ticker), ETF_ALIASES.get(ticker, UNIVERSE.get(ticker, ticker)), 100.0)]


def safe_snapshot(code: str, snapshot_cache: dict[str, dict]) -> dict:
    if code not in snapshot_cache:
        try:
            snapshot_cache[code] = build_stock_snapshot(code)
        except Exception:
            snapshot_cache[code] = {
                "code": code,
                "ret5": math.nan,
                "vol_ratio": math.nan,
                "ma20": math.nan,
                "ma_pass": False,
            }
    return snapshot_cache[code]


def format_entry_leaders(title: str, etf_tickers: list[str], snapshot_cache: dict[str, dict]) -> list[str]:
    lines = [title]
    if not etf_tickers:
        return lines + ["- 없음"]
    for ticker in etf_tickers:
        lines.append(f"🔹 {ETF_ALIASES.get(ticker, UNIVERSE.get(ticker, ticker))}")
        for idx, (code, name, weight) in enumerate(holdings_for_etf(ticker)[:5], start=1):
            snapshot = safe_snapshot(code, snapshot_cache)
            lines.extend(format_leader_stock_line(idx, name, code, weight, snapshot))
    return lines


def pct_rank(s: pd.Series) -> pd.Series:
    return s.rank(pct=True) * 100


def download_panel() -> tuple[pd.DataFrame, pd.DataFrame]:
    tickers = sorted(UNIVERSE)
    raw = pd.DataFrame()
    try:
        raw = yf.download(
            tickers,
            period="1y",
            auto_adjust=True,
            group_by="column",
            progress=False,
            threads=True,
        )
    except Exception:
        raw = pd.DataFrame()

    if raw.empty:
        return download_panel_from_naver(tickers)

    close = raw["Close"].copy() if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    volume = raw["Volume"].copy() if isinstance(raw.columns, pd.MultiIndex) else raw[["Volume"]]
    close = close.dropna(how="all").ffill()
    volume = volume.reindex(close.index).fillna(0)
    valid = [c for c in close.columns if close[c].notna().sum() >= 130]
    if not valid:
        return download_panel_from_naver(tickers)
    return close[valid], volume[valid]


def download_panel_from_naver(tickers: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    close_frames = {}
    volume_frames = {}
    for ticker in tickers:
        code = stock_code_suffix(ticker)
        try:
            df = fetch_naver_daily(code, min_rows=130)
        except Exception:
            continue
        idx = pd.to_datetime(df["date"], format="%Y.%m.%d")
        close_frames[ticker] = pd.Series(df["close"].to_numpy(), index=idx)
        volume_frames[ticker] = pd.Series(df["volume"].to_numpy(), index=idx)

    if not close_frames:
        raise RuntimeError("가격 데이터를 가져오지 못했습니다.")
    close = pd.DataFrame(close_frames).sort_index().ffill()
    volume = pd.DataFrame(volume_frames).reindex(close.index).fillna(0)
    valid = [c for c in close.columns if close[c].notna().sum() >= 130]
    if not valid:
        raise RuntimeError("가격 데이터가 부족합니다.")
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

    new_entry_tickers = [
        row["ticker"]
        for _, row in cur[cur["ticker"].isin(top20_tickers - prev_top20_tickers)].head(5).iterrows()
    ]
    state = load_entry_state()
    previous_a_entries = set(state.get("a_entries", {}).keys())
    b_type_tickers = [
        ticker
        for ticker in cur.head(20)["ticker"].tolist()
        if ticker in previous_a_entries and ticker not in new_entry_tickers
    ]
    if not b_type_tickers and not previous_a_entries:
        b_type_tickers = [
            row["ticker"]
            for _, row in cur.head(20).iterrows()
            if row["ticker"] in prev_top20_tickers and changes.get(row["ticker"], -999) >= 0
        ][:3]
    snapshot_cache: dict[str, dict] = {}

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
        format_entry_leaders("🔥 [A타입] 신규 진입 대장주", new_entry_tickers, snapshot_cache),
        format_entry_leaders("📈 [B타입] 진입 후 상승 유지", b_type_tickers, snapshot_cache),
        ["※ 상세 분석 결과는 로컬 CSV 파일로 저장되었습니다."],
    ]

    OUTPUT_DIR.mkdir(exist_ok=True)
    cur.to_csv(OUTPUT_DIR / f"etf_momentum_today_scores_{latest_date}.csv", index=False, encoding="utf-8-sig")
    leader_rows = []
    for ticker in sorted(set(new_entry_tickers + b_type_tickers)):
        leader_type = "A" if ticker in new_entry_tickers else "B"
        for code, name, weight in holdings_for_etf(ticker)[:5]:
            snapshot = snapshot_cache.get(code) or safe_snapshot(code, snapshot_cache)
            leader_rows.append(
                {
                    "date": latest_date,
                    "type": leader_type,
                    "etf_ticker": ticker,
                    "etf_name": ETF_ALIASES.get(ticker, UNIVERSE.get(ticker, ticker)),
                    "stock_code": code,
                    "stock_name": name,
                    "weight": weight,
                    "ret5": snapshot.get("ret5"),
                    "vol_ratio": snapshot.get("vol_ratio"),
                    "ma20": snapshot.get("ma20"),
                    "ma_pass": snapshot.get("ma_pass"),
                    "mark": leader_mark(snapshot),
                }
            )
    if leader_rows:
        pd.DataFrame(leader_rows).to_csv(
            OUTPUT_DIR / f"etf_momentum_entry_leaders_{latest_date}.csv",
            index=False,
            encoding="utf-8-sig",
        )
    state["last_date"] = latest_date
    state["a_entries"] = {
        ticker: {
            "date": state.get("a_entries", {}).get(ticker, {}).get("date", latest_date),
            "name": ETF_ALIASES.get(ticker, UNIVERSE.get(ticker, ticker)),
        }
        for ticker in sorted(set(previous_a_entries).union(new_entry_tickers))
        if ticker in top20_tickers or ticker in new_entry_tickers
    }
    save_entry_state(state)
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
