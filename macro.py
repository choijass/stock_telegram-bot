# Converted from Google Colab notebook
# Source notebook: 2.매크로+RS+ETF_국내판_FULL(최종)

# %% [code] cell 1
# =========================================================
# KOREA RS LIVE SYSTEM - FINAL STABLE VERSION
# =========================================================
# 기능
# - 한국 ETF/종목 RS 랭킹 시스템
# - TOP20 / ALL_RANK / BENCHMARK / SIGNAL
# - BUY_CANDIDATE / SELL_CANDIDATE
# - THEME_RANK / TURNOVER_SURGE / THEME_FLOW
# - THEME_ROTATION / THEME_FLOW_HISTORY
# - Google Sheets 자동 저장
# - Theme KeyError 방지 안정화 버전
# =========================================================

import json
import os
import time
import warnings
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import yfinance as yf
import requests
from PIL import Image, ImageDraw, ImageFont

warnings.filterwarnings("ignore")

# ---------------------------------------------------------
# 0) 기본 설정
# ---------------------------------------------------------
KST = ZoneInfo("Asia/Seoul")
TODAY = datetime.now(KST).strftime("%Y-%m-%d")
NOW_STR = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

USE_GOOGLE_SHEETS = os.getenv("USE_GOOGLE_SHEETS", "true").lower() in {"1", "true", "yes", "y"}
GSHEET_NAME = "Korea_RS_Live_System_Final_Stable"
RESULTS_DIR = Path(os.getenv("RESULTS_DIR", "results"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_REQUIRED = os.getenv("TELEGRAM_REQUIRED", "false").lower() in {"1", "true", "yes", "y"}

DOWNLOAD_PERIOD = "9mo"
DOWNLOAD_INTERVAL = "1d"
SLEEP_SEC = 0.10

# ---------------------------------------------------------
# 1) 벤치마크
# ---------------------------------------------------------
BENCHMARKS = {
    "KOSPI": "^KS11",
    "KOSDAQ": "^KQ11",
    "SP500": "^GSPC",
    "NASDAQ": "^IXIC",
    "DOW": "^DJI",
    "WTI": "CL=F",
    "BRENT": "BZ=F",
    "VIX": "^VIX",
    "DXY": "DX-Y.NYB",
    "US10Y": "^TNX",
}

# ---------------------------------------------------------
# 2) 유니버스
# 형식: (ticker, name, asset_type, market, theme)
# ---------------------------------------------------------
UNIVERSE = [
    # ETF
    ("069500.KS", "KODEX 200", "ETF", "KOSPI", "지수"),
    ("229200.KS", "KODEX 코스닥150", "ETF", "KOSDAQ", "지수"),
    ("122630.KS", "KODEX 레버리지", "ETF", "KOSPI", "지수"),
    ("252670.KS", "KODEX 200선물인버스2X", "ETF", "KOSPI", "헤지"),
    ("114800.KS", "KODEX 인버스", "ETF", "KOSPI", "헤지"),
    ("233740.KS", "KODEX 코스닥150레버리지", "ETF", "KOSDAQ", "지수"),
    ("251340.KS", "KODEX 코스닥150선물인버스", "ETF", "KOSDAQ", "헤지"),
    ("091160.KS", "KODEX 반도체", "ETF", "KOSPI", "반도체"),
    ("117460.KS", "KODEX 에너지화학", "ETF", "KOSPI", "에너지"),
    ("266420.KS", "KODEX 헬스케어", "ETF", "KOSPI", "바이오"),
    ("102960.KS", "KODEX 기계장비", "ETF", "KOSPI", "산업재"),
    ("305540.KS", "TIGER 2차전지테마", "ETF", "KOSPI", "2차전지"),
    ("381180.KS", "TIGER 미국필라델피아반도체나스닥", "ETF", "KOSPI", "반도체"),
    ("476070.KS", "PLUS K방산", "ETF", "KOSPI", "방산"),
    ("449450.KS", "TIGER K방산&우주", "ETF", "KOSPI", "방산"),
    ("132030.KS", "KODEX 골드선물(H)", "ETF", "KOSPI", "금"),
    ("304940.KS", "KODEX 은행", "ETF", "KOSPI", "금융"),

    # 반도체
    ("005930.KS", "삼성전자", "STOCK", "KOSPI", "반도체"),
    ("000660.KS", "SK하이닉스", "STOCK", "KOSPI", "반도체"),
    ("042700.KS", "한미반도체", "STOCK", "KOSPI", "반도체장비"),
    ("058470.KQ", "리노공업", "STOCK", "KOSDAQ", "반도체"),
    ("240810.KQ", "원익IPS", "STOCK", "KOSDAQ", "반도체장비"),
    ("101490.KQ", "에스앤에스텍", "STOCK", "KOSDAQ", "반도체"),
    ("084370.KQ", "유진테크", "STOCK", "KOSDAQ", "반도체장비"),

    # 방산/우주
    ("012450.KS", "한화에어로스페이스", "STOCK", "KOSPI", "방산"),
    ("272210.KQ", "한화시스템", "STOCK", "KOSDAQ", "방산"),
    ("047810.KS", "한국항공우주", "STOCK", "KOSPI", "방산"),
    ("064350.KS", "현대로템", "STOCK", "KOSPI", "방산"),
    ("079550.KS", "LIG넥스원", "STOCK", "KOSPI", "방산"),

    # 조선
    ("329180.KS", "HD현대중공업", "STOCK", "KOSPI", "조선"),
    ("042660.KS", "한화오션", "STOCK", "KOSPI", "조선"),
    ("010140.KS", "삼성중공업", "STOCK", "KOSPI", "조선"),
    ("009540.KS", "HD한국조선해양", "STOCK", "KOSPI", "조선"),
    ("443060.KS", "HD현대마린솔루션", "STOCK", "KOSPI", "조선"),
    ("082740.KS", "한화엔진", "STOCK", "KOSPI", "조선기자재"),
    ("010620.KS", "HD현대미포", "STOCK", "KOSPI", "조선"),

    # 에너지/원전/전력
    ("034020.KS", "두산에너빌리티", "STOCK", "KOSPI", "원전"),
    ("015760.KS", "한국전력", "STOCK", "KOSPI", "전력"),
    ("052690.KS", "한전기술", "STOCK", "KOSPI", "원전"),
    ("051600.KS", "한전KPS", "STOCK", "KOSPI", "원전"),
    ("036460.KS", "한국가스공사", "STOCK", "KOSPI", "가스"),
    ("267260.KS", "HD현대일렉트릭", "STOCK", "KOSPI", "전력"),
    ("130660.KS", "한전산업", "STOCK", "KOSPI", "전력"),
    ("010120.KS", "LS ELECTRIC", "STOCK", "KOSPI", "전력"),
    ("000720.KS", "현대건설", "STOCK", "KOSPI", "원전건설"),

    # 2차전지
    ("006400.KS", "삼성SDI", "STOCK", "KOSPI", "2차전지"),
    ("373220.KS", "LG에너지솔루션", "STOCK", "KOSPI", "2차전지"),
    ("051910.KS", "LG화학", "STOCK", "KOSPI", "2차전지"),
    ("066970.KS", "엘앤에프", "STOCK", "KOSPI", "2차전지"),
    ("247540.KQ", "에코프로비엠", "STOCK", "KOSDAQ", "2차전지"),
    ("086520.KQ", "에코프로", "STOCK", "KOSDAQ", "2차전지"),
    ("003670.KS", "포스코퓨처엠", "STOCK", "KOSPI", "2차전지"),
    ("078600.KQ", "대주전자재료", "STOCK", "KOSDAQ", "2차전지"),

    # 바이오
    ("068270.KS", "셀트리온", "STOCK", "KOSPI", "바이오"),
    ("207940.KS", "삼성바이오로직스", "STOCK", "KOSPI", "바이오"),
    ("326030.KS", "SK바이오팜", "STOCK", "KOSPI", "바이오"),
    ("196170.KQ", "알테오젠", "STOCK", "KOSDAQ", "바이오"),
    ("145020.KQ", "휴젤", "STOCK", "KOSDAQ", "바이오"),
    ("141080.KQ", "리가켐바이오", "STOCK", "KOSDAQ", "바이오"),

    # 인터넷/AI/SW/보안
    ("035420.KS", "NAVER", "STOCK", "KOSPI", "인터넷"),
    ("035720.KS", "카카오", "STOCK", "KOSPI", "인터넷"),
    ("053800.KQ", "안랩", "STOCK", "KOSDAQ", "보안"),
    ("304100.KQ", "솔트룩스", "STOCK", "KOSDAQ", "AI"),
    ("018260.KS", "삼성에스디에스", "STOCK", "KOSPI", "IT서비스"),

    # 금융
    ("055550.KS", "신한지주", "STOCK", "KOSPI", "금융"),
    ("105560.KS", "KB금융", "STOCK", "KOSPI", "금융"),
    ("086790.KS", "하나금융지주", "STOCK", "KOSPI", "금융"),
    ("316140.KS", "우리금융지주", "STOCK", "KOSPI", "금융"),
    ("138040.KS", "메리츠금융지주", "STOCK", "KOSPI", "금융"),
    ("000810.KS", "삼성화재", "STOCK", "KOSPI", "보험"),
]

# ---------------------------------------------------------
# 3) 공통 보조 함수
# ---------------------------------------------------------
def ensure_theme_column(df, default_value="Unknown"):
    if df is None:
        return pd.DataFrame()
    out = df.copy()
    if "Theme" in out.columns:
        return out
    if "Theme_x" in out.columns:
        out["Theme"] = out["Theme_x"]
    elif "Theme_y" in out.columns:
        out["Theme"] = out["Theme_y"]
    else:
        theme_like = [c for c in out.columns if str(c).startswith("Theme")]
        if theme_like:
            out["Theme"] = out[theme_like[0]]
        else:
            out["Theme"] = default_value
    return out

def safe_subset(df, cols):
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)
    return df[[c for c in cols if c in df.columns]].copy()

def safe_sort(df, by, ascending=False):
    if df is None or df.empty:
        return df
    existing = [c for c in by if c in df.columns]
    if not existing:
        return df
    ascending_used = ascending
    if isinstance(ascending, list):
        ascending_used = ascending[:len(existing)]
    return df.sort_values(by=existing, ascending=ascending_used)

def coerce_numeric(df, cols):
    out = df.copy()
    for c in cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out

# ---------------------------------------------------------
# 4) 구글시트 인증
# ---------------------------------------------------------
def init_gspread():
    if not USE_GOOGLE_SHEETS:
        return None
    try:
        import gspread

        service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        service_account_file = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

        if service_account_json:
            info = json.loads(service_account_json)
            return gspread.service_account_from_dict(info)

        if service_account_file:
            return gspread.service_account(filename=service_account_file)

        print("[WARN] Google Sheets secret is not configured.")
        return None
    except Exception as e:
        print(f"[WARN] Google Sheets 인증 실패: {e}")
        return None

# ---------------------------------------------------------
# 5) 데이터 다운로드
# ---------------------------------------------------------
def download_ohlcv(tickers, period=DOWNLOAD_PERIOD, interval=DOWNLOAD_INTERVAL):
    out = {}
    for ticker in tickers:
        try:
            df = yf.download(
                ticker,
                period=period,
                interval=interval,
                auto_adjust=False,
                progress=False,
                threads=False,
            )
            if df is None or df.empty:
                print(f"[WARN] 데이터 없음: {ticker}")
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]

            df.columns = [str(c).title() for c in df.columns]

            needed = ["Open", "High", "Low", "Close", "Volume"]
            for c in needed:
                if c not in df.columns:
                    df[c] = np.nan

            df = df[needed].copy()
            df.dropna(subset=["Close"], inplace=True)
            df.index = pd.to_datetime(df.index).tz_localize(None)
            out[ticker] = df
            time.sleep(SLEEP_SEC)
        except Exception as e:
            print(f"[ERROR] 다운로드 실패 {ticker}: {e}")
    return out

# ---------------------------------------------------------
# 6) 유틸
# ---------------------------------------------------------
def safe_return(series, lookback):
    if series is None or len(series) <= lookback:
        return np.nan
    prev = series.iloc[-lookback - 1]
    curr = series.iloc[-1]
    if pd.isna(prev) or pd.isna(curr) or prev == 0:
        return np.nan
    return (curr / prev) - 1

def highest_drawdown_from_high(series, lookback=60):
    if series is None or len(series) < lookback:
        return np.nan
    s = series.iloc[-lookback:]
    high = s.max()
    last = s.iloc[-1]
    if pd.isna(high) or pd.isna(last) or high == 0:
        return np.nan
    return (last / high) - 1

def rolling_ma(series, n):
    if len(series) < n:
        return np.nan
    return series.rolling(n).mean().iloc[-1]

def ma_slope_up(series, window=20, compare_back=5):
    if len(series) < window + compare_back:
        return False
    ma = series.rolling(window).mean()
    return bool(ma.iloc[-1] > ma.iloc[-compare_back])

def pct(x):
    if pd.isna(x):
        return np.nan
    return round(x * 100, 2)

def zscore(series):
    s = pd.Series(series, dtype="float64")
    mu = s.mean()
    sd = s.std(ddof=0)
    if pd.isna(sd) or sd == 0:
        sd = 1.0
    return (s - mu) / sd

def turnover_burst(close, vol, lookback=5):
    if len(close) < lookback + 1 or len(vol) < lookback + 1:
        return np.nan
    current = float(close.iloc[-1]) * float(vol.iloc[-1])
    hist = (close.iloc[-lookback-1:-1] * vol.iloc[-lookback-1:-1]).dropna()
    if hist.empty:
        return np.nan
    avg = hist.mean()
    if avg == 0 or pd.isna(avg):
        return np.nan
    return current / avg

def avg_turnover(close, vol, lookback=5):
    if len(close) < lookback or len(vol) < lookback:
        return np.nan
    hist = (close.iloc[-lookback:] * vol.iloc[-lookback:]).dropna()
    if hist.empty:
        return np.nan
    return float(hist.mean())

def turnover_ratio(close, vol, lookback=5):
    if len(close) < lookback + 1 or len(vol) < lookback + 1:
        return np.nan
    current = float(close.iloc[-1]) * float(vol.iloc[-1])
    hist = (close.iloc[-lookback-1:-1] * vol.iloc[-lookback-1:-1]).dropna()
    if hist.empty:
        return np.nan
    avg_val = hist.mean()
    if pd.isna(avg_val) or avg_val == 0:
        return np.nan
    return float(current / avg_val)

def get_close(bench_map, name):
    ticker = BENCHMARKS.get(name)
    if ticker is None:
        return None
    df = bench_map.get(ticker)
    if df is None or df.empty:
        return None
    return df["Close"]

# ---------------------------------------------------------
# 7) Google Sheets 입출력
# ---------------------------------------------------------
def write_df_to_gsheet(gc, spreadsheet_name, worksheet_name, df):
    if gc is None:
        print(f"[INFO] Google Sheets 저장 생략: {worksheet_name}")
        return
    try:
        try:
            sh = gc.open(spreadsheet_name)
        except Exception:
            sh = gc.create(spreadsheet_name)

        try:
            ws = sh.worksheet(worksheet_name)
            ws.clear()
        except Exception:
            ws = sh.add_worksheet(title=worksheet_name, rows=5000, cols=80)

        if df is None or df.empty:
            ws.update("A1", [["NO_DATA"]])
            print(f"[OK] 빈 시트 저장 완료: {worksheet_name}")
            return

        values = [df.columns.tolist()] + df.astype(str).values.tolist()
        ws.update("A1", values)
        print(f"[OK] 시트 저장 완료: {worksheet_name}")
    except Exception as e:
        print(f"[ERROR] 시트 저장 실패 ({worksheet_name}): {e}")

def append_df_to_gsheet(gc, spreadsheet_name, worksheet_name, df):
    if gc is None:
        print(f"[INFO] Google Sheets append 저장 생략: {worksheet_name}")
        return
    if df is None or df.empty:
        print(f"[INFO] append 대상 데이터 없음: {worksheet_name}")
        return
    try:
        try:
            sh = gc.open(spreadsheet_name)
        except Exception:
            sh = gc.create(spreadsheet_name)

        try:
            ws = sh.worksheet(worksheet_name)
        except Exception:
            ws = sh.add_worksheet(title=worksheet_name, rows=20000, cols=80)

        existing = ws.get_all_values()
        values = df.astype(str).values.tolist()

        if not existing:
            ws.update("A1", [df.columns.tolist()] + values)
        else:
            ws.append_rows(values)

        print(f"[OK] append 저장 완료: {worksheet_name}")
    except Exception as e:
        print(f"[ERROR] append 저장 실패 ({worksheet_name}): {e}")

def read_gsheet_as_df(gc, spreadsheet_name, worksheet_name):
    if gc is None:
        return pd.DataFrame()
    try:
        sh = gc.open(spreadsheet_name)
        ws = sh.worksheet(worksheet_name)
        values = ws.get_all_values()
        if not values or len(values) < 2:
            return pd.DataFrame()
        header = values[0]
        rows = values[1:]
        return pd.DataFrame(rows, columns=header)
    except Exception as e:
        print(f"[WARN] 시트 읽기 실패 ({worksheet_name}): {e}")
        return pd.DataFrame()

# ---------------------------------------------------------
# 8) 벤치마크
# ---------------------------------------------------------
def build_benchmark_table(bench_map):
    rows = []
    for name, ticker in BENCHMARKS.items():
        df = bench_map.get(ticker)
        if df is None or df.empty:
            continue
        close = df["Close"]
        rows.append({
            "Name": name,
            "Ticker": ticker,
            "Close": round(float(close.iloc[-1]), 2),
            "1D%": pct(safe_return(close, 1)),
            "5D%": pct(safe_return(close, 5)),
            "20D%": pct(safe_return(close, 20)),
            "60D%": pct(safe_return(close, 60)),
            "Drawdown_20D%": pct(highest_drawdown_from_high(close, 20)),
            "Drawdown_60D%": pct(highest_drawdown_from_high(close, 60)),
        })
    return pd.DataFrame(rows)

# ---------------------------------------------------------
# 9) 시장 모드
# ---------------------------------------------------------
def evaluate_market_signal(bench_map):
    kospi = get_close(bench_map, "KOSPI")
    kosdaq = get_close(bench_map, "KOSDAQ")
    spx = get_close(bench_map, "SP500")
    ndx = get_close(bench_map, "NASDAQ")
    vix = get_close(bench_map, "VIX")
    brent = get_close(bench_map, "BRENT")
    dxy = get_close(bench_map, "DXY")

    signals = []

    def add_signal(cond, text):
        if cond:
            signals.append(text)

    if kospi is not None:
        add_signal(safe_return(kospi, 5) <= -0.06, "KOSPI 5D <= -6%")
        add_signal(highest_drawdown_from_high(kospi, 20) <= -0.08, "KOSPI 20D DD <= -8%")

    if kosdaq is not None:
        add_signal(safe_return(kosdaq, 5) <= -0.08, "KOSDAQ 5D <= -8%")
        add_signal(highest_drawdown_from_high(kosdaq, 20) <= -0.10, "KOSDAQ 20D DD <= -10%")

    if spx is not None:
        add_signal(highest_drawdown_from_high(spx, 60) <= -0.08, "SPX 60D DD <= -8%")

    if ndx is not None:
        add_signal(highest_drawdown_from_high(ndx, 60) <= -0.10, "NASDAQ 60D DD <= -10%")

    if vix is not None:
        try:
            add_signal(float(vix.iloc[-1]) >= 25, "VIX >= 25")
            add_signal(float(vix.iloc[-1]) >= 30, "VIX >= 30")
        except Exception:
            pass

    if brent is not None:
        try:
            add_signal(float(brent.iloc[-1]) >= 95, "BRENT >= 95")
            add_signal(float(brent.iloc[-1]) >= 105, "BRENT >= 105")
        except Exception:
            pass

    if dxy is not None:
        add_signal(safe_return(dxy, 20) >= 0.03, "DXY 20D >= +3%")

    n = len(signals)
    if n >= 5:
        mode = "CRASH_MODE"
    elif n >= 3:
        mode = "RISK_MODE"
    else:
        mode = "NORMAL_MODE"

    return mode, signals

# ---------------------------------------------------------
# 10) 랭킹 계산
# ---------------------------------------------------------
def compute_score(row):
    score = 0.0
    score += row["RS20"] * 45
    score += row["RS60"] * 30
    score += row["Turnover_Z"] * 8
    score += row["TurnoverBurst_Z"] * 8
    score += row["Ret20_Z"] * 4
    score += row["Ret60_Z"] * 4
    score += 10 if row["Above_MA20"] else 0
    score += 10 if row["Above_MA60"] else 0
    score += 8 if row["MA20_Slope_Up"] else 0
    score += 5 if row["MA60_Slope_Up"] else 0
    return round(score, 4)

def build_rank_table(universe, data_map, bench_map):
    rows = []
    temp_rows = []
    turnovers = []
    bursts = []
    ret20s = []
    ret60s = []

    for ticker, name, asset_type, market, theme in universe:
        df = data_map.get(ticker)
        bench_df = bench_map.get(BENCHMARKS[market])

        if df is None or bench_df is None:
            continue
        if len(df) < 80 or len(bench_df) < 80:
            continue

        close = df["Close"].dropna()
        vol = df["Volume"].fillna(0)
        bclose = bench_df["Close"].dropna()

        r1 = safe_return(close, 1)
        r5 = safe_return(close, 5)
        r20 = safe_return(close, 20)
        r60 = safe_return(close, 60)

        br20 = safe_return(bclose, 20)
        br60 = safe_return(bclose, 60)

        rs20 = r20 - br20 if pd.notna(r20) and pd.notna(br20) else np.nan
        rs60 = r60 - br60 if pd.notna(r60) and pd.notna(br60) else np.nan

        ma20 = rolling_ma(close, 20)
        ma60 = rolling_ma(close, 60)
        current_turnover = float(close.iloc[-1]) * float(vol.iloc[-1])

        burst = turnover_burst(close, vol, 5)
        avg_to_5 = avg_turnover(close, vol, 5)
        avg_to_20 = avg_turnover(close, vol, 20)
        ratio_5 = turnover_ratio(close, vol, 5)
        ratio_20 = turnover_ratio(close, vol, 20)

        row = {
            "Ticker": ticker,
            "Name": name,
            "Type": asset_type,
            "Market": market,
            "Theme": theme,
            "Close": round(float(close.iloc[-1]), 2),
            "1D%": pct(r1),
            "5D%": pct(r5),
            "20D%": pct(r20),
            "60D%": pct(r60),
            "Bench20D%": pct(br20),
            "Bench60D%": pct(br60),
            "RS20": round(rs20, 4) if pd.notna(rs20) else np.nan,
            "RS60": round(rs60, 4) if pd.notna(rs60) else np.nan,
            "ApproxTurnover": current_turnover,
            "AvgTurnover5": round(float(avg_to_5), 2) if pd.notna(avg_to_5) else np.nan,
            "AvgTurnover20": round(float(avg_to_20), 2) if pd.notna(avg_to_20) else np.nan,
            "TurnoverBurst": round(float(burst), 4) if pd.notna(burst) else np.nan,
            "TurnoverRatio5": round(float(ratio_5), 4) if pd.notna(ratio_5) else np.nan,
            "TurnoverRatio20": round(float(ratio_20), 4) if pd.notna(ratio_20) else np.nan,
            "Above_MA20": bool(pd.notna(ma20) and close.iloc[-1] > ma20),
            "Above_MA60": bool(pd.notna(ma60) and close.iloc[-1] > ma60),
            "MA20_Slope_Up": ma_slope_up(close, 20, 5),
            "MA60_Slope_Up": ma_slope_up(close, 60, 5),
            "Drawdown_20D%": pct(highest_drawdown_from_high(close, 20)),
            "Drawdown_60D%": pct(highest_drawdown_from_high(close, 60)),
        }

        temp_rows.append(row)
        turnovers.append(current_turnover)
        bursts.append(burst if pd.notna(burst) else np.nan)
        ret20s.append(r20 if pd.notna(r20) else np.nan)
        ret60s.append(r60 if pd.notna(r60) else np.nan)

    if not temp_rows:
        return pd.DataFrame()

    turnover_z = zscore(turnovers)
    burst_z = zscore(bursts)
    ret20_z = zscore(ret20s)
    ret60_z = zscore(ret60s)

    for i, row in enumerate(temp_rows):
        row["Turnover_Z"] = round(float(turnover_z.iloc[i]), 4) if pd.notna(turnover_z.iloc[i]) else 0.0
        row["TurnoverBurst_Z"] = round(float(burst_z.iloc[i]), 4) if pd.notna(burst_z.iloc[i]) else 0.0
        row["Ret20_Z"] = round(float(ret20_z.iloc[i]), 4) if pd.notna(ret20_z.iloc[i]) else 0.0
        row["Ret60_Z"] = round(float(ret60_z.iloc[i]), 4) if pd.notna(ret60_z.iloc[i]) else 0.0
        row["Score"] = compute_score(row)
        rows.append(row)

    df = pd.DataFrame(rows)
    df = df.dropna(subset=["RS20", "RS60"]).copy()
    df = ensure_theme_column(df)

    df["RS_Trend"] = np.where(
        (df["RS20"] > 0) & (df["RS60"] > 0),
        "STRONG",
        np.where(df["RS20"] > 0, "WATCH", "WEAK")
    )

    df = safe_sort(df, ["Score", "RS20", "RS60", "Turnover_Z", "TurnoverBurst_Z"], ascending=False)
    df = df.reset_index(drop=True)
    df["Rank"] = df.index + 1

    col_order = [
        "Rank", "Ticker", "Name", "Type", "Market", "Theme",
        "Close", "1D%", "5D%", "20D%", "60D%",
        "Bench20D%", "Bench60D%",
        "RS20", "RS60", "RS_Trend",
        "ApproxTurnover", "AvgTurnover5", "AvgTurnover20",
        "TurnoverBurst", "TurnoverRatio5", "TurnoverRatio20",
        "Turnover_Z", "TurnoverBurst_Z",
        "Ret20_Z", "Ret60_Z",
        "Above_MA20", "Above_MA60", "MA20_Slope_Up", "MA60_Slope_Up",
        "Drawdown_20D%", "Drawdown_60D%",
        "Score"
    ]
    return safe_subset(df, col_order)

# ---------------------------------------------------------
# 11) TOP20
# ---------------------------------------------------------
def build_top20(df_all, mode):
    if df_all is None or df_all.empty:
        return pd.DataFrame()
    df_all = ensure_theme_column(df_all)

    if mode == "CRASH_MODE":
        filt = (
            (df_all["RS20"] > 0) &
            (df_all["TurnoverBurst_Z"] > 0) &
            ((df_all["Above_MA20"]) | (df_all["Above_MA60"]))
        )
    elif mode == "RISK_MODE":
        filt = (
            (df_all["RS20"] > 0) &
            (df_all["RS60"] > -0.03) &
            ((df_all["Above_MA20"]) | (df_all["Above_MA60"]))
        )
    else:
        filt = (
            (df_all["RS20"] > 0) &
            (df_all["RS60"] > 0)
        )

    top = df_all[filt].copy()
    top = safe_sort(top, ["Score", "RS20", "RS60", "TurnoverBurst_Z"], ascending=False).head(20)
    top = top.reset_index(drop=True)
    top["TopRank"] = top.index + 1
    return top

# ---------------------------------------------------------
# 12) 매수 후보
# ---------------------------------------------------------
def build_buy_candidates(df_all, mode):
    cols = [
        "BuyRank", "Name", "Ticker", "Theme", "Close", "1D%", "20D%", "60D%",
        "RS20", "RS60", "TurnoverBurst", "TurnoverBurst_Z",
        "Above_MA20", "MA20_Slope_Up", "Score", "BuyReason"
    ]
    if df_all is None or df_all.empty:
        return pd.DataFrame(columns=cols)

    df_all = ensure_theme_column(df_all)

    if mode == "CRASH_MODE":
        cond = (
            (df_all["RS20"] > 0) &
            (df_all["TurnoverBurst_Z"] > 0.2) &
            ((df_all["Above_MA20"]) | (df_all["Above_MA60"])) &
            (df_all["1D%"] <= 5.0) &
            (df_all["1D%"] >= -4.0)
        )
    elif mode == "RISK_MODE":
        cond = (
            (df_all["RS20"] > 0) &
            (df_all["RS60"] > -0.02) &
            (df_all["TurnoverBurst_Z"] > 0.0) &
            (df_all["Above_MA20"]) &
            (df_all["1D%"] <= 6.0) &
            (df_all["1D%"] >= -3.5)
        )
    else:
        cond = (
            (df_all["RS20"] > 0) &
            (df_all["RS60"] > 0) &
            (df_all["TurnoverBurst_Z"] > -0.2) &
            (df_all["Above_MA20"]) &
            (df_all["MA20_Slope_Up"]) &
            (df_all["1D%"] <= 7.0) &
            (df_all["1D%"] >= -2.5)
        )

    out = df_all[cond].copy()

    def reason(row):
        parts = []
        if row.get("RS20", np.nan) > 0:
            parts.append("RS20+")
        if row.get("RS60", np.nan) > 0:
            parts.append("RS60+")
        if row.get("TurnoverBurst_Z", np.nan) > 0:
            parts.append("거래대금증가")
        if row.get("Above_MA20", False):
            parts.append("20MA상회")
        if row.get("MA20_Slope_Up", False):
            parts.append("20MA우상향")
        return ", ".join(parts)

    if out.empty:
        return pd.DataFrame(columns=cols)

    out["BuyReason"] = out.apply(reason, axis=1)
    out = safe_sort(out, ["Score", "RS20", "TurnoverBurst_Z"], ascending=False).head(15)
    out = out.reset_index(drop=True)
    out["BuyRank"] = out.index + 1
    return safe_subset(out, cols)

# ---------------------------------------------------------
# 13) 매도 후보
# ---------------------------------------------------------
def build_sell_candidates(df_all, mode):
    cols = [
        "SellRank", "Name", "Ticker", "Theme", "Close", "1D%", "20D%", "60D%",
        "RS20", "RS60", "TurnoverBurst", "TurnoverBurst_Z",
        "Above_MA20", "Drawdown_20D%", "Score", "SellReason"
    ]
    if df_all is None or df_all.empty:
        return pd.DataFrame(columns=cols)

    df_all = ensure_theme_column(df_all)

    cond = (
        ((df_all["1D%"] >= 8.0) & (df_all["TurnoverBurst_Z"] < 0.5)) |
        ((df_all["RS20"] < 0) & (df_all["RS60"] < 0)) |
        ((~df_all["Above_MA20"]) & (df_all["1D%"] < 0)) |
        ((df_all["Drawdown_20D%"] <= -8.0) & (df_all["RS20"] < 0))
    )

    out = df_all[cond].copy()

    def reason(row):
        parts = []
        if row.get("1D%", np.nan) >= 8.0 and row.get("TurnoverBurst_Z", np.nan) < 0.5:
            parts.append("급등과열")
        if row.get("RS20", np.nan) < 0 and row.get("RS60", np.nan) < 0:
            parts.append("RS약화")
        if (not row.get("Above_MA20", False)) and row.get("1D%", np.nan) < 0:
            parts.append("20MA이탈")
        if row.get("Drawdown_20D%", np.nan) <= -8.0 and row.get("RS20", np.nan) < 0:
            parts.append("낙폭확대")
        return ", ".join(parts)

    if out.empty:
        return pd.DataFrame(columns=cols)

    out["SellReason"] = out.apply(reason, axis=1)
    out = safe_sort(out, ["1D%", "RS20", "Score"], ascending=[False, True, True]).head(15)
    out = out.reset_index(drop=True)
    out["SellRank"] = out.index + 1
    return safe_subset(out, cols)

# ---------------------------------------------------------
# 14) 테마별 랭킹
# ---------------------------------------------------------
def build_theme_rank(df_all, top_n_per_theme=5):
    cols = [
        "Theme", "ThemeRank", "Name", "Ticker", "Type", "Market",
        "Close", "1D%", "20D%", "60D%", "RS20", "RS60",
        "TurnoverBurst", "Score"
    ]
    if df_all is None or df_all.empty:
        return pd.DataFrame(columns=cols)

    df = ensure_theme_column(df_all)
    pieces = []

    for theme, sub in df.groupby("Theme", dropna=False):
        sub = safe_sort(sub, ["Score", "RS20", "RS60"], ascending=False).head(top_n_per_theme).copy()
        sub["ThemeRank"] = range(1, len(sub) + 1)
        pieces.append(sub)

    if not pieces:
        return pd.DataFrame(columns=cols)

    out = pd.concat(pieces, axis=0, ignore_index=True)
    out = ensure_theme_column(out)
    out = safe_sort(out, ["Theme", "ThemeRank"], ascending=[True, True])
    return safe_subset(out, cols)

# ---------------------------------------------------------
# 15) 거래대금 급등 랭킹
# ---------------------------------------------------------
def build_turnover_surge(df_all, mode):
    cols = [
        "SurgeRank", "Name", "Ticker", "Theme", "Close",
        "1D%", "5D%", "20D%", "RS20", "RS60",
        "ApproxTurnover", "AvgTurnover5", "AvgTurnover20",
        "TurnoverRatio5", "TurnoverRatio20",
        "Turnover_Z", "TurnoverBurst_Z", "Score", "SurgeScore", "SurgeReason"
    ]
    if df_all is None or df_all.empty:
        return pd.DataFrame(columns=cols)

    out = ensure_theme_column(df_all)

    cond = (
        (out["TurnoverRatio5"] >= 1.5) |
        (out["TurnoverRatio20"] >= 2.0)
    )
    out = out[cond].copy()

    if out.empty:
        return pd.DataFrame(columns=cols)

    if mode == "CRASH_MODE":
        out["SurgeScore"] = (
            out["TurnoverRatio5"].fillna(0) * 35 +
            out["TurnoverRatio20"].fillna(0) * 25 +
            out["RS20"].fillna(0) * 40 +
            out["TurnoverBurst_Z"].fillna(0) * 10
        )
    elif mode == "RISK_MODE":
        out["SurgeScore"] = (
            out["TurnoverRatio5"].fillna(0) * 30 +
            out["TurnoverRatio20"].fillna(0) * 20 +
            out["RS20"].fillna(0) * 35 +
            out["RS60"].fillna(0) * 20 +
            out["TurnoverBurst_Z"].fillna(0) * 10
        )
    else:
        out["SurgeScore"] = (
            out["TurnoverRatio5"].fillna(0) * 25 +
            out["TurnoverRatio20"].fillna(0) * 20 +
            out["RS20"].fillna(0) * 30 +
            out["RS60"].fillna(0) * 25 +
            out["TurnoverBurst_Z"].fillna(0) * 10
        )

    def reason(row):
        parts = []
        if pd.notna(row.get("TurnoverRatio5", np.nan)) and row["TurnoverRatio5"] >= 2:
            parts.append("5일대비 거래대금 2배+")
        elif pd.notna(row.get("TurnoverRatio5", np.nan)) and row["TurnoverRatio5"] >= 1.5:
            parts.append("5일대비 거래대금 급증")

        if pd.notna(row.get("TurnoverRatio20", np.nan)) and row["TurnoverRatio20"] >= 3:
            parts.append("20일대비 거래대금 3배+")
        elif pd.notna(row.get("TurnoverRatio20", np.nan)) and row["TurnoverRatio20"] >= 2:
            parts.append("20일대비 거래대금 급증")

        if pd.notna(row.get("RS20", np.nan)) and row["RS20"] > 0:
            parts.append("RS20+")
        if pd.notna(row.get("RS60", np.nan)) and row["RS60"] > 0:
            parts.append("RS60+")

        if pd.notna(row.get("1D%", np.nan)) and row["1D%"] >= 5:
            parts.append("당일 강세")
        elif pd.notna(row.get("1D%", np.nan)) and row["1D%"] <= -3:
            parts.append("하락 중 거래집중")

        return ", ".join(parts)

    out["SurgeReason"] = out.apply(reason, axis=1)
    out = safe_sort(out, ["SurgeScore", "TurnoverRatio5", "TurnoverRatio20", "RS20"], ascending=False).head(30)
    out = out.reset_index(drop=True)
    out["SurgeRank"] = out.index + 1
    out["SurgeScore"] = out["SurgeScore"].round(4)
    return safe_subset(out, cols)

# ---------------------------------------------------------
# 16) THEME_FLOW
# ---------------------------------------------------------
def build_theme_flow(df_all, turnover_surge_df):
    cols = [
        "Date", "ThemeRank", "Theme", "StockCount",
        "Avg_RS20", "Avg_RS60",
        "Avg_TurnoverRatio5", "Avg_TurnoverRatio20",
        "ThemeScore", "TopStocks"
    ]
    if df_all is None or df_all.empty:
        return pd.DataFrame(columns=cols)

    base = ensure_theme_column(df_all)

    if turnover_surge_df is not None and not turnover_surge_df.empty and "Ticker" in turnover_surge_df.columns:
        surge_tickers = turnover_surge_df["Ticker"].dropna().unique().tolist()
        base_filtered = base[base["Ticker"].isin(surge_tickers)].copy()
        if not base_filtered.empty:
            base = base_filtered

    rows = []
    for theme, sub in base.groupby("Theme", dropna=False):
        count = len(sub)

        avg_rs20 = sub["RS20"].mean() if "RS20" in sub.columns else np.nan
        avg_rs60 = sub["RS60"].mean() if "RS60" in sub.columns else np.nan
        avg_turnover5 = sub["TurnoverRatio5"].mean() if "TurnoverRatio5" in sub.columns else np.nan
        avg_turnover20 = sub["TurnoverRatio20"].mean() if "TurnoverRatio20" in sub.columns else np.nan

        top_sub = safe_sort(sub, ["Score", "RS20", "RS60"], ascending=False)
        top_names = ", ".join(top_sub["Name"].head(3).astype(str).tolist()) if "Name" in top_sub.columns else ""

        score = (
            (avg_turnover5 if pd.notna(avg_turnover5) else 0) * 40 +
            (avg_turnover20 if pd.notna(avg_turnover20) else 0) * 30 +
            (avg_rs20 if pd.notna(avg_rs20) else 0) * 50 +
            (avg_rs60 if pd.notna(avg_rs60) else 0) * 20 +
            count * 5
        )

        rows.append({
            "Date": TODAY,
            "Theme": theme,
            "StockCount": count,
            "Avg_RS20": round(avg_rs20, 4) if pd.notna(avg_rs20) else np.nan,
            "Avg_RS60": round(avg_rs60, 4) if pd.notna(avg_rs60) else np.nan,
            "Avg_TurnoverRatio5": round(avg_turnover5, 3) if pd.notna(avg_turnover5) else np.nan,
            "Avg_TurnoverRatio20": round(avg_turnover20, 3) if pd.notna(avg_turnover20) else np.nan,
            "TopStocks": top_names,
            "ThemeScore": round(score, 2)
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=cols)

    df = ensure_theme_column(df)
    df = safe_sort(df, ["ThemeScore"], ascending=False).reset_index(drop=True)
    df["ThemeRank"] = df.index + 1
    return safe_subset(df, cols)

# ---------------------------------------------------------
# 17) THEME_ROTATION
# ---------------------------------------------------------
def build_theme_rotation(theme_flow_today, theme_flow_hist):
    cols = [
        "RotationRank", "Theme",
        "TodayRank", "PrevRank", "RankChange",
        "TodayScore", "PrevScore", "ScoreChange",
        "Today_RS20", "Prev_RS20", "RS20_Change",
        "Today_Turnover5", "Prev_Turnover5", "Turnover5_Change",
        "StockCount", "TopStocks", "RotationSignal"
    ]
    if theme_flow_today is None or theme_flow_today.empty:
        return pd.DataFrame(columns=cols)

    today = ensure_theme_column(theme_flow_today)

    if theme_flow_hist is None or theme_flow_hist.empty:
        out = today.copy()
        out["PrevRank"] = np.nan
        out["RankChange"] = np.nan
        out["PrevScore"] = np.nan
        out["ScoreChange"] = np.nan
        out["Prev_RS20"] = np.nan
        out["RS20_Change"] = np.nan
        out["Prev_Turnover5"] = np.nan
        out["Turnover5_Change"] = np.nan
        out["RotationSignal"] = "NEW_BASELINE"

        out = out.rename(columns={
            "ThemeRank": "TodayRank",
            "ThemeScore": "TodayScore",
            "Avg_RS20": "Today_RS20",
            "Avg_TurnoverRatio5": "Today_Turnover5"
        })
        out = safe_sort(out, ["TodayScore"], ascending=False).reset_index(drop=True)
        out["RotationRank"] = out.index + 1
        return safe_subset(out, cols)

    hist = ensure_theme_column(theme_flow_hist)
    hist = coerce_numeric(hist, [
        "ThemeRank", "StockCount", "Avg_RS20", "Avg_RS60",
        "Avg_TurnoverRatio5", "Avg_TurnoverRatio20", "ThemeScore"
    ])

    if "Date" not in hist.columns or hist["Date"].dropna().empty:
        prev = pd.DataFrame()
    else:
        unique_dates = sorted(hist["Date"].dropna().unique())
        prev_date = unique_dates[-1]
        prev = hist[hist["Date"] == prev_date].copy()

    prev = ensure_theme_column(prev)

    today2 = today.rename(columns={
        "ThemeRank": "TodayRank",
        "ThemeScore": "TodayScore",
        "Avg_RS20": "Today_RS20",
        "Avg_TurnoverRatio5": "Today_Turnover5"
    })

    prev2 = prev.rename(columns={
        "ThemeRank": "PrevRank",
        "ThemeScore": "PrevScore",
        "Avg_RS20": "Prev_RS20",
        "Avg_TurnoverRatio5": "Prev_Turnover5"
    })

    prev2 = safe_subset(prev2, ["Theme", "PrevRank", "PrevScore", "Prev_RS20", "Prev_Turnover5"])

    merged = pd.merge(today2, prev2, on="Theme", how="left")

    merged["RankChange"] = merged["PrevRank"] - merged["TodayRank"]
    merged["ScoreChange"] = merged["TodayScore"] - merged["PrevScore"]
    merged["RS20_Change"] = merged["Today_RS20"] - merged["Prev_RS20"]
    merged["Turnover5_Change"] = merged["Today_Turnover5"] - merged["Prev_Turnover5"]

    def rotation_signal(row):
        if pd.isna(row.get("PrevRank", np.nan)):
            return "NEW_THEME"
        if row.get("RankChange", 0) >= 3 and row.get("ScoreChange", 0) > 0:
            return "STRONG_UP"
        if row.get("RankChange", 0) >= 1 and row.get("Turnover5_Change", 0) > 0:
            return "UP"
        if row.get("RankChange", 0) <= -3 and row.get("ScoreChange", 0) < 0:
            return "STRONG_DOWN"
        if row.get("RankChange", 0) <= -1:
            return "DOWN"
        return "STABLE"

    merged["RotationSignal"] = merged.apply(rotation_signal, axis=1)
    merged = safe_sort(merged, ["ScoreChange", "RankChange", "TodayScore"], ascending=[False, False, False]).reset_index(drop=True)
    merged["RotationRank"] = merged.index + 1
    return safe_subset(merged, cols)

# ---------------------------------------------------------
# 18) SIGNAL / RULES - 확장 최종버전
# ---------------------------------------------------------
def get_position_guide(mode, signal_count):
    """
    Mode + Signal_Count 기준 포지션 가이드
    """

    if mode == "NORMAL_MODE":
        if signal_count <= 1:
            return {
                "Position_Level": "최상위 공격",
                "Stock_Position": "70~90%",
                "Cash_Position": "10~30%",
                "Action": "RS 상위 + 거래대금 증가 종목 중심 적극 매수",
                "Risk": "과열 종목 추격만 주의"
            }
        elif signal_count <= 2:
            return {
                "Position_Level": "공격 유지",
                "Stock_Position": "60~75%",
                "Cash_Position": "25~40%",
                "Action": "주도 테마 유지, 신규매수는 눌림 위주",
                "Risk": "시장 과열 초기 가능성 점검"
            }
        else:
            return {
                "Position_Level": "중립 전환 준비",
                "Stock_Position": "45~60%",
                "Cash_Position": "40~55%",
                "Action": "신규매수 축소, 보유종목만 선별 유지",
                "Risk": "정상장 안의 위험 신호 증가"
            }

    elif mode == "RISK_MODE":
        if signal_count <= 3:
            return {
                "Position_Level": "중립",
                "Stock_Position": "40~55%",
                "Cash_Position": "45~60%",
                "Action": "강한 테마만 보유, 약한 종목 교체",
                "Risk": "변동성 확대"
            }
        elif signal_count <= 4:
            return {
                "Position_Level": "방어",
                "Stock_Position": "25~40%",
                "Cash_Position": "60~75%",
                "Action": "RS 약화 종목 축소, 현금 확대",
                "Risk": "지수 하락 가속 가능성"
            }
        else:
            return {
                "Position_Level": "강한 방어",
                "Stock_Position": "10~25%",
                "Cash_Position": "75~90%",
                "Action": "신규매수 금지, 초강세 종목만 단기 대응",
                "Risk": "급락장 전환 위험"
            }

    elif mode == "CRASH_MODE":
        if signal_count <= 5:
            return {
                "Position_Level": "최하위 방어",
                "Stock_Position": "0~15%",
                "Cash_Position": "85~100%",
                "Action": "관망 우선, 반등 시 현금화",
                "Risk": "패닉성 하락 가능성"
            }
        else:
            return {
                "Position_Level": "현금 최우선",
                "Stock_Position": "0~5%",
                "Cash_Position": "95~100%",
                "Action": "매매 중단에 가까운 방어 모드",
                "Risk": "시장 붕괴 구간"
            }

    return {
        "Position_Level": "판단불가",
        "Stock_Position": "-",
        "Cash_Position": "-",
        "Action": "-",
        "Risk": "-"
    }


def make_rank_change_text(rank_change):
    """
    RankChange: 양수면 순위 상승, 음수면 순위 하락
    """
    if pd.isna(rank_change):
        return "신규진입"
    if rank_change >= 3:
        return f"강한 상승 ▲{int(rank_change)}"
    elif rank_change >= 1:
        return f"상승 ▲{int(rank_change)}"
    elif rank_change <= -3:
        return f"강한 하락 ▼{abs(int(rank_change))}"
    elif rank_change <= -1:
        return f"하락 ▼{abs(int(rank_change))}"
    else:
        return "유지 ="


def build_signal_table(mode, signals, top20, buy_df, sell_df, theme_rotation_df=None):
    signal_count = len(signals)
    guide = get_position_guide(mode, signal_count)

    rows = [
        ["Timestamp", NOW_STR],
        ["Mode", mode],
        ["Signal_Count", signal_count],
        ["Signals", " | ".join(signals) if signals else "None"],

        ["Position_Level", guide["Position_Level"]],
        ["Recommended_Stock_Position", guide["Stock_Position"]],
        ["Recommended_Cash_Position", guide["Cash_Position"]],
        ["Action_Guide", guide["Action"]],
        ["Risk_Guide", guide["Risk"]],

        ["Top20_Count", len(top20) if top20 is not None else 0],
        ["Buy_Count", len(buy_df) if buy_df is not None else 0],
        ["Sell_Count", len(sell_df) if sell_df is not None else 0],
    ]

    if top20 is not None and not top20.empty:
        top20 = ensure_theme_column(top20)

        rows.append([
            "Top10_Names",
            ", ".join(top20["Name"].head(10).astype(str).tolist())
        ])

        top_themes = top20["Theme"].value_counts().head(5).to_dict()
        rows.append([
            "Top_Themes",
            " | ".join([f"{k}:{v}" for k, v in top_themes.items()])
        ])

    # 테마 순위 변동 설명 추가
    if theme_rotation_df is not None and not theme_rotation_df.empty:
        temp = theme_rotation_df.copy()

        if "RankChange" in temp.columns:
            temp["RankMove_Text"] = temp["RankChange"].apply(make_rank_change_text)

        top_rotation = temp.head(5)

        move_text = []
        for _, row in top_rotation.iterrows():
            theme = row.get("Theme", "")
            today_rank = row.get("TodayRank", "")
            prev_rank = row.get("PrevRank", "")
            move = row.get("RankMove_Text", "")
            signal = row.get("RotationSignal", "")

            move_text.append(
                f"{theme}: {prev_rank}위 → {today_rank}위 / {move} / {signal}"
            )

        rows.append([
            "Theme_Rank_Change_Top5",
            " | ".join(move_text)
        ])

    # 포지션 변동 예시
    rows.append([
        "Position_Change_Example",
        "예: NORMAL_MODE & Signal_Count 0~1 = 주식 70~90% / "
        "NORMAL_MODE & Signal_Count 2 = 주식 60~75% / "
        "RISK_MODE = 주식 25~55% / "
        "CRASH_MODE = 주식 0~15%"
    ])

    rows.append([
        "Position_Scale_Full",
        "최상위 공격 > 공격 유지 > 중립 전환 준비 > 중립 > 방어 > 강한 방어 > 최하위 방어 > 현금 최우선"
    ])

    rows.append([
        "Current_Position_Comment",
        f"현재 {mode}, Signal_Count {signal_count} 기준: {guide['Position_Level']} / 주식 {guide['Stock_Position']} / 현금 {guide['Cash_Position']}"
    ])

    return pd.DataFrame(rows, columns=["Item", "Value"])


# ---------------------------------------------------------
# 18-1) RULES TABLE - SIGNAL / 포지션 / 종가배팅 연결형
# ---------------------------------------------------------
def build_rules_table(mode, signal_count=None):
    """
    RULES 탭 생성
    - mode + signal_count 기준 포지션 설명
    - 매수/매도/종가배팅/ETF/테마순환 룰 설명
    - Google Sheets RULES 탭 저장용
    """
    if signal_count is None:
        signal_count = 0

    guide = get_position_guide(mode, signal_count)

    rows = [
        {"구분": "현재모드", "항목": "Mode", "내용": mode, "우선순위": 1},
        {"구분": "현재모드", "항목": "Signal_Count", "내용": signal_count, "우선순위": 1},
        {"구분": "포지션", "항목": "현재 포지션 단계", "내용": guide["Position_Level"], "우선순위": 1},
        {"구분": "포지션", "항목": "권장 주식비중", "내용": guide["Stock_Position"], "우선순위": 1},
        {"구분": "포지션", "항목": "권장 현금비중", "내용": guide["Cash_Position"], "우선순위": 1},
        {"구분": "포지션", "항목": "현재 대응", "내용": guide["Action"], "우선순위": 1},
        {"구분": "포지션", "항목": "위험 설명", "내용": guide["Risk"], "우선순위": 1},
        {"구분": "매수조건", "항목": "핵심 매수 조건", "내용": "RS20 > 0 + RS60 > 0 + 20일선 상회 + 거래대금 증가", "우선순위": 2},
        {"구분": "매수조건", "항목": "종가배팅 후보", "내용": "RS20 양수 + 거래대금 급증 + 당일 상승률 -2.5%~7% + 20MA 우상향", "우선순위": 2},
        {"구분": "매수조건", "항목": "ETF 우선 조건", "내용": "ETF 순위 상승 + 해당 ETF 구성 종목 RS 동반 상승 + 거래대금 증가", "우선순위": 2},
        {"구분": "매수조건", "항목": "눌림 매수 조건", "내용": "주도 테마 유지 + 20일선 위 조정 + 거래대금 감소 후 재증가", "우선순위": 2},
        {"구분": "매도조건", "항목": "기본 매도", "내용": "RS20 < 0 또는 20일선 이탈", "우선순위": 3},
        {"구분": "매도조건", "항목": "급등 매도", "내용": "당일 +8% 이상 상승했지만 거래대금 증가가 약하면 일부 차익", "우선순위": 3},
        {"구분": "매도조건", "항목": "약세 전환", "내용": "RS20 < 0 & RS60 < 0 동시 발생 시 비중 축소", "우선순위": 3},
        {"구분": "리스크", "항목": "NORMAL_MODE", "내용": "주도 테마 중심 공격 가능. 단, 과열 종목 추격매수 주의", "우선순위": 4},
        {"구분": "리스크", "항목": "RISK_MODE", "내용": "신규매수 축소, 강한 테마만 보유, 현금 45~75%", "우선순위": 4},
        {"구분": "리스크", "항목": "CRASH_MODE", "내용": "신규매수 금지, 현금 85~100%, 반등 시 현금화", "우선순위": 4},
        {"구분": "테마순환", "항목": "강한 순위 상승", "내용": "RankChange +3 이상이면 STRONG_UP, 주도테마 후보", "우선순위": 5},
        {"구분": "테마순환", "항목": "약한 순위 하락", "내용": "RankChange -3 이하이면 STRONG_DOWN, 비중 축소 후보", "우선순위": 5},
        {"구분": "운영법", "항목": "우선 확인 순서", "내용": "SIGNAL → RULES → THEME_ROTATION → TURNOVER_SURGE → BUY_CANDIDATE → TOP20", "우선순위": 6},
        {"구분": "운영법", "항목": "실전 해석", "내용": "RULES는 시장모드별 행동지침, BUY_CANDIDATE는 실제 후보, THEME_ROTATION은 주도테마 변화 확인용", "우선순위": 6},
    ]

    return pd.DataFrame(rows)

# ---------------------------------------------------------
# 19) CSV 저장
# ---------------------------------------------------------
def save_csv(df, filename):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULTS_DIR / filename
    if df is None:
        pd.DataFrame().to_csv(path, index=False, encoding="utf-8-sig")
    else:
        df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"[OK] CSV 저장: {path}")

def format_signal_message(signal_df):
    if signal_df is None or signal_df.empty:
        return f"[Korea RS SIGNAL]\n{NOW_STR}\nSIGNAL 데이터가 없습니다."

    values = dict(zip(signal_df["Item"].astype(str), signal_df["Value"].astype(str)))
    ordered_items = [
        "Timestamp",
        "Mode",
        "Signal_Count",
        "Signals",
        "Position_Level",
        "Recommended_Stock_Position",
        "Recommended_Cash_Position",
        "Action_Guide",
        "Risk_Guide",
        "Top20_Count",
        "Buy_Count",
        "Sell_Count",
        "Top10_Names",
        "Top_Themes",
        "Theme_Rank_Change_Top5",
        "Current_Position_Comment",
    ]

    labels = {
        "Timestamp": "시간",
        "Mode": "시장모드",
        "Signal_Count": "위험신호 수",
        "Signals": "위험신호",
        "Position_Level": "포지션 단계",
        "Recommended_Stock_Position": "권장 주식비중",
        "Recommended_Cash_Position": "권장 현금비중",
        "Action_Guide": "대응",
        "Risk_Guide": "리스크",
        "Top20_Count": "TOP20 수",
        "Buy_Count": "매수후보 수",
        "Sell_Count": "매도후보 수",
        "Top10_Names": "상위 종목",
        "Top_Themes": "상위 테마",
        "Theme_Rank_Change_Top5": "테마 변화",
        "Current_Position_Comment": "현재 해석",
    }

    lines = ["[Korea RS SIGNAL]"]
    for item in ordered_items:
        if item in values:
            lines.append(f"{labels.get(item, item)}: {values[item]}")
    return "\n".join(lines)

def get_signal_values(signal_df):
    if signal_df is None or signal_df.empty:
        return {}
    return dict(zip(signal_df["Item"].astype(str), signal_df["Value"].astype(str)))

def clean_signal_value(value):
    text = str(value)
    return text.replace("nan위 →", "신규 →").replace("nan", "-")

def load_font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf" if bold else "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumBarunGothicBold.ttf" if bold else "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/Library/Fonts/AppleGothic.ttf",
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    ]
    for path in candidates:
        if path and Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()

def wrap_text(draw, text, font, max_width):
    words = str(text).replace(" | ", "  |  ").split()
    lines = []
    line = ""
    for word in words:
        candidate = word if not line else f"{line} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            line = candidate
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines or [""]

def draw_wrapped_text(draw, xy, text, font, fill, max_width, line_gap=8):
    x, y = xy
    for line in wrap_text(draw, text, font, max_width):
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + line_gap
    return y

def make_signal_image(signal_df):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    values = {k: clean_signal_value(v) for k, v in get_signal_values(signal_df).items()}

    width = 1200
    margin = 52
    card_gap = 24
    bg = "#f3f6fb"
    navy = "#172554"
    blue = "#2563eb"
    red = "#dc2626"
    green = "#16a34a"
    text = "#111827"
    muted = "#4b5563"
    line = "#dbe3ef"

    title_font = load_font(48, bold=True)
    subtitle_font = load_font(24)
    label_font = load_font(24, bold=True)
    body_font = load_font(25)
    small_font = load_font(21)
    badge_font = load_font(30, bold=True)

    sections = [
        ("시장 상태", [
            ("시장모드", values.get("Mode", "-")),
            ("위험신호 수", values.get("Signal_Count", "-")),
            ("위험신호", values.get("Signals", "-")),
        ]),
        ("포지션 가이드", [
            ("단계", values.get("Position_Level", "-")),
            ("주식비중", values.get("Recommended_Stock_Position", "-")),
            ("현금비중", values.get("Recommended_Cash_Position", "-")),
            ("대응", values.get("Action_Guide", "-")),
            ("리스크", values.get("Risk_Guide", "-")),
        ]),
        ("시장 후보", [
            ("TOP20", values.get("Top20_Count", "-")),
            ("매수후보", values.get("Buy_Count", "-")),
            ("매도후보", values.get("Sell_Count", "-")),
            ("상위 종목", values.get("Top10_Names", "-")),
            ("상위 테마", values.get("Top_Themes", "-")),
            ("테마 변화", values.get("Theme_Rank_Change_Top5", "-")),
        ]),
        ("현재 해석", [
            ("요약", values.get("Current_Position_Comment", "-")),
        ]),
    ]

    probe = Image.new("RGB", (width, 10), bg)
    draw = ImageDraw.Draw(probe)
    content_width = width - margin * 2
    heights = [150]
    for _, rows in sections:
        h = 76
        for label, value in rows:
            label_w = 150
            wrapped = wrap_text(draw, value, body_font, content_width - label_w - 44)
            h += max(42, len(wrapped) * (body_font.size + 8)) + 8
        heights.append(h)
    height = sum(heights) + card_gap * len(sections) + margin

    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)

    y = 42
    draw.text((margin, y), "Korea RS SIGNAL", font=title_font, fill=navy)
    y += 58
    draw.text((margin, y), values.get("Timestamp", NOW_STR), font=subtitle_font, fill=muted)

    mode = values.get("Mode", "-")
    badge_fill = red if "CRASH" in mode else green if "NORMAL" in mode else "#f59e0b"
    badge_text = mode
    badge_w = int(draw.textlength(badge_text, font=badge_font)) + 38
    draw.rounded_rectangle((width - margin - badge_w, 48, width - margin, 98), radius=24, fill=badge_fill)
    draw.text((width - margin - badge_w + 19, 56), badge_text, font=badge_font, fill="white")
    y += 70

    for title, rows in sections:
        card_top = y
        x0, x1 = margin, width - margin
        draw.rounded_rectangle((x0, card_top, x1, card_top + 10), radius=18, fill="white")
        section_y = card_top + 24
        draw.text((x0 + 28, section_y), title, font=label_font, fill=blue)
        section_y += 48
        draw.line((x0 + 28, section_y, x1 - 28, section_y), fill=line, width=2)
        section_y += 22

        for label, value in rows:
            draw.text((x0 + 28, section_y), label, font=label_font, fill=text)
            value_x = x0 + 178
            section_y = draw_wrapped_text(
                draw,
                (value_x, section_y),
                value,
                body_font if label not in {"상위 종목", "상위 테마", "테마 변화", "위험신호"} else small_font,
                muted,
                x1 - value_x - 30,
                line_gap=8,
            )
            section_y += 14

        card_bottom = section_y + 18
        draw.rounded_rectangle((x0, card_top, x1, card_bottom), radius=22, outline=line, width=2)
        y = card_bottom + card_gap

    path = RESULTS_DIR / f"signal_{TODAY}.png"
    img.save(path)
    print(f"[OK] SIGNAL 이미지 저장: {path}")
    return path

def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        note = "[INFO] Telegram secret 없음: 발송 생략"
        if TELEGRAM_REQUIRED:
            raise RuntimeError(note)
        print(note)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    chunks = [message[i:i + 3900] for i in range(0, len(message), 3900)]
    masked_chat_id = TELEGRAM_CHAT_ID[:4] + "..." + TELEGRAM_CHAT_ID[-4:] if len(TELEGRAM_CHAT_ID) > 8 else "***"
    print(f"[INFO] Telegram 발송 대상 chat_id: {masked_chat_id}")

    for chunk in chunks:
        data = urlencode({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "disable_web_page_preview": "true",
        }).encode("utf-8")
        req = Request(url, data=data, method="POST")
        with urlopen(req, timeout=30) as response:
            response.read()
    print("[OK] Telegram SIGNAL 발송 완료")

def send_telegram_photo(image_path, caption):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        note = "[INFO] Telegram secret 없음: 이미지 발송 생략"
        if TELEGRAM_REQUIRED:
            raise RuntimeError(note)
        print(note)
        return

    masked_chat_id = TELEGRAM_CHAT_ID[:4] + "..." + TELEGRAM_CHAT_ID[-4:] if len(TELEGRAM_CHAT_ID) > 8 else "***"
    print(f"[INFO] Telegram 이미지 발송 대상 chat_id: {masked_chat_id}")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    with open(image_path, "rb") as image_file:
        response = requests.post(
            url,
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "caption": caption[:1024],
            },
            files={"photo": image_file},
            timeout=60,
        )
    if not response.ok:
        raise RuntimeError(f"Telegram 이미지 발송 실패: {response.status_code} {response.text}")
    print("[OK] Telegram SIGNAL 이미지 발송 완료")

# ---------------------------------------------------------
# 20) 메인
# ---------------------------------------------------------
def main():
    print("=" * 70)
    print("KOREA RS LIVE SYSTEM - FINAL STABLE VERSION")
    print("=" * 70)
    print(f"[TIME] {NOW_STR}")
    print(f"[UNIVERSE COUNT] {len(UNIVERSE)}")

    stock_tickers = [x[0] for x in UNIVERSE]
    bench_tickers = list(dict.fromkeys(BENCHMARKS.values()))

    print("\n[1] 종목 데이터 다운로드")
    stock_map = download_ohlcv(stock_tickers)

    print("\n[2] 벤치마크 데이터 다운로드")
    bench_map = download_ohlcv(bench_tickers)

    print("\n[3] ALL_RANK 계산")
    all_rank = build_rank_table(UNIVERSE, stock_map, bench_map)
    if all_rank.empty:
        print("[WARN] 랭킹 결과 없음")
        return

    print("[DEBUG] all_rank columns:", list(all_rank.columns))
    print("[DEBUG] Theme exists in all_rank:", "Theme" in all_rank.columns)

    print("\n[4] 시장 모드 계산")
    mode, signals = evaluate_market_signal(bench_map)

    print("\n[5] TOP20 계산")
    top20 = build_top20(all_rank, mode)

    print("\n[6] BUY / SELL 후보 계산")
    buy_df = build_buy_candidates(all_rank, mode)
    sell_df = build_sell_candidates(all_rank, mode)

    print("\n[7] THEME_RANK 계산")
    theme_df = build_theme_rank(all_rank, top_n_per_theme=5)

    print("\n[8] TURNOVER_SURGE 계산")
    turnover_surge_df = build_turnover_surge(all_rank, mode)

    print("\n[9] THEME_FLOW 계산")
    theme_flow_df = build_theme_flow(all_rank, turnover_surge_df)
    print("[DEBUG] theme_flow_df columns:", list(theme_flow_df.columns))

    print("\n[10] SIGNAL 보조 데이터 생성")

    print("\n[11] Google Sheets 연결")
    gc = init_gspread()

    print("\n[12] THEME_FLOW_HISTORY 읽기")
    theme_flow_hist_df = read_gsheet_as_df(gc, GSHEET_NAME, "THEME_FLOW_HISTORY")

    print("\n[13] THEME_ROTATION 계산")
    theme_rotation_df = build_theme_rotation(theme_flow_df, theme_flow_hist_df)

    print("\n[13-1] 확장 SIGNAL 생성")
    signal_df = build_signal_table(
        mode,
        signals,
        top20,
        buy_df,
        sell_df,
        theme_rotation_df
    )

    print("\n================ SIGNAL ================")
    print(signal_df.to_string(index=False))

    print("\n[14] SIGNAL CSV 저장")
    save_csv(signal_df, f"signal_{TODAY}.csv")
    image_path = make_signal_image(signal_df)

    print("\n[15] Google Sheets SIGNAL 저장")
    write_df_to_gsheet(gc, GSHEET_NAME, "SIGNAL", signal_df)

    print("\n[16] Telegram SIGNAL 발송")
    send_telegram_photo(image_path, "Korea RS SIGNAL")

    print("\n" + "=" * 70)
    print("DONE")
    print("=" * 70)

if __name__ == "__main__":
    main()
