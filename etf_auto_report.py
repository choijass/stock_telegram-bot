# ETF RS / moving-average report image sender.

import os
import time
import warnings
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import yfinance as yf
from PIL import Image, ImageDraw, ImageFont

warnings.filterwarnings("ignore")

KST = ZoneInfo("Asia/Seoul")
NOW = datetime.now(KST)
TODAY = NOW.strftime("%Y-%m-%d")
NOW_STR = NOW.strftime("%Y-%m-%d %H:%M:%S")
RESULTS_DIR = Path(os.getenv("RESULTS_DIR", "results"))
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_REQUIRED = os.getenv("TELEGRAM_REQUIRED", "false").lower() in {"1", "true", "yes", "y"}

korea_industry_etfs = {
    "091170.KS": "KODEX 은행",
    "140700.KS": "KODEX 보험",
    "102970.KS": "KODEX 증권",
    "117700.KS": "KODEX 건설",
    "300950.KS": "KODEX 게임산업",
    "395160.KS": "KODEX 시스템반도체",
    "445290.KS": "KODEX K-로봇액티브",
    "117460.KS": "KODEX 에너지화학",
    "091160.KS": "KODEX 반도체",
    "244580.KS": "KODEX 바이오",
    "228800.KS": "TIGER 여행레저",
    "364970.KS": "TIGER 바이오 TOP10",
    "091180.KS": "KODEX 자동차",
    "305540.KS": "TIGER 2차전지테마",
    "462010.KS": "TIGER 2차전지소재FN",
    "266360.KS": "KODEX 미디어&엔터테인먼트",
    "395150.KS": "KODEX 웹툰&드라마",
    "367760.KS": "RISE 5G테크",
    "228790.KS": "TIGER 화장품",
    "463250.KS": "TIGER 우주방산",
    "157490.KS": "TIGER 소프트웨어",
    "449450.KS": "PLUS K 방산",
    "139230.KS": "TIGER 200 중공업",
    "139280.KS": "TIGER 경기방어",
    "438900.KS": "HANARO FN K-푸드",
    "381570.KS": "HANARO FN친환경에너지",
    "466920.KS": "SOL 조선TOP3플러스",
    "475300.KS": "SOL 반도체전공정",
    "475310.KS": "SOL 반도체후공정",
    "307510.KS": "TIGER 의료기기",
    "433500.KS": "ACE 원자력테마딥서치",
    "483020.KS": "KIWOOM 의료AI",
    "495040.KS": "PLUS 코리아밸류업",
    "496770.KS": "PLUS 글로벌방산",
    "102960.KS": "KODEX 기계장비",
    "365000.KS": "TIGER 인터넷TOP10",
    "463050.KS": "TIMEFOLIO K바이오액티브",
    "421320.KS": "PLUS 우주항공&UAM",
    "457990.KS": "PLUS 태양광&ESS",
    "069500.KS": "KODEX 200",
}

etf_holdings_map = {
    "091160.KS": {"000660.KS": "SK하이닉스", "005930.KS": "삼성전자", "042700.KQ": "한미반도체", "000990.KS": "DB하이텍", "058470.KQ": "리노공업"},
    "395160.KS": {"000660.KS": "SK하이닉스", "005930.KS": "삼성전자", "042700.KQ": "한미반도체", "039030.KQ": "이오테크닉스", "036930.KQ": "주성엔지니어링"},
    "466920.KS": {"010140.KS": "삼성중공업", "329180.KS": "HD현대중공업", "042660.KS": "한화오션", "009540.KS": "HD한국조선해양"},
    "449450.KS": {"012450.KS": "한화에어로스페이스", "079550.KS": "LIG넥스원", "047810.KS": "한국항공우주", "272210.KS": "한화시스템", "064350.KS": "현대로템"},
    "463250.KS": {"012450.KS": "한화에어로스페이스", "079550.KS": "LIG넥스원", "047810.KS": "한국항공우주", "272210.KS": "한화시스템", "064350.KS": "현대로템"},
    "433500.KS": {"034020.KS": "두산에너빌리티", "052690.KS": "한전기술", "051600.KS": "한전KPS", "105840.KQ": "우진", "046940.KQ": "우원개발"},
    "305540.KS": {"373220.KS": "LG에너지솔루션", "006400.KS": "삼성SDI", "247540.KQ": "에코프로비엠", "086520.KQ": "에코프로", "003670.KS": "포스코퓨처엠"},
    "457990.KS": {"010120.KS": "LS ELECTRIC", "267260.KS": "HD현대일렉트릭", "298040.KS": "효성중공업", "112610.KS": "씨에스윈드", "336260.KS": "두산퓨얼셀"},
    "228790.KS": {"051900.KS": "LG생활건강", "090430.KS": "아모레퍼시픽", "161890.KQ": "한국콜마", "192820.KS": "코스맥스", "018290.KS": "브이티"},
}


def download_data():
    holding_tickers = []
    for holdings in etf_holdings_map.values():
        holding_tickers.extend(holdings.keys())
    all_tickers = sorted(set(list(korea_industry_etfs.keys()) + holding_tickers))
    raw = yf.download(all_tickers, period="6mo", auto_adjust=True, progress=False, threads=True)
    data = raw["Close"].sort_index().dropna(how="all")
    valid_tickers = data.columns[data.notna().sum() > 20].tolist()
    data = data[valid_tickers]
    etf_data = data[[ticker for ticker in korea_industry_etfs if ticker in data.columns]]
    return data, etf_data, valid_tickers, [ticker for ticker in all_tickers if ticker not in valid_tickers]


def calculate_risk_adjusted_momentum(data, last_n_days=10):
    result = {}
    for day in data.index[-last_n_days:]:
        idx = data.index.get_loc(day)
        rows = []
        for ticker in data.columns:
            series = data[ticker].iloc[: idx + 1].dropna()
            if len(series) < 30:
                continue
            pct = series.pct_change().dropna()
            values = []
            for window in (21, 63, 126):
                ret = pct.tail(window).mean()
                vol = pct.tail(window).std()
                if pd.notna(vol) and vol != 0:
                    values.append(ret / vol)
            if values:
                rows.append({"티커": ticker, "점수": int(round(np.mean(values) * 100))})
        temp = pd.DataFrame(rows)
        if not temp.empty:
            temp = temp.sort_values("점수", ascending=False).head(20)
            result[day] = [f"{korea_industry_etfs.get(row['티커'], row['티커'])} ({int(row['점수'])})" for _, row in temp.iterrows()]
    return pd.DataFrame.from_dict(result, orient="index", columns=[f"Top{i + 1}" for i in range(20)])


def calculate_rs_rank(data, benchmark="069500.KS", lookback=20, top_n=5):
    benchmark_return = data[benchmark].pct_change(lookback).iloc[-1] if benchmark in data.columns else data.pct_change(lookback).iloc[-1].mean()
    etf_return = data.pct_change(lookback).iloc[-1]
    rs = etf_return - benchmark_return
    df = pd.DataFrame({
        "티커": rs.index,
        "ETF명": [korea_industry_etfs.get(ticker, ticker) for ticker in rs.index],
        "20일수익률": (etf_return * 100).round().astype("Int64"),
        "RS점수": (rs * 100).round().astype("Int64"),
    }).dropna()
    df = df.sort_values("RS점수", ascending=False).head(top_n)
    df.insert(0, "RS순위", range(1, len(df) + 1))
    return df


def count_consecutive_above(series, ma):
    count = 0
    for value in (series > ma).iloc[::-1]:
        if bool(value):
            count += 1
        else:
            break
    return int(count)


def calculate_ma_position(data):
    close = data.iloc[-1]
    ma5 = data.rolling(5).mean().iloc[-1]
    ma10 = data.rolling(10).mean().iloc[-1]
    ma20 = data.rolling(20).mean().iloc[-1]
    df = pd.DataFrame({
        "티커": close.index,
        "ETF명": [korea_industry_etfs.get(ticker, ticker) for ticker in close.index],
        "현재가": close.round().astype("Int64"),
        "5일선": ma5.round().astype("Int64"),
        "10일선": ma10.round().astype("Int64"),
        "20일선": ma20.round().astype("Int64"),
        "5일선위치": np.where(close > ma5, "위", "아래"),
        "10일선위치": np.where(close > ma10, "위", "아래"),
        "20일선위치": np.where(close > ma20, "위", "아래"),
    })
    df["이평상태"] = np.select(
        [(close > ma5) & (close > ma10) & (close > ma20), (close > ma5) & (close > ma10), (close < ma5) & (close < ma10) & (close < ma20)],
        ["강세", "단기강세", "약세"],
        default="중립",
    )
    return df


def calculate_ma_hold_groups(data):
    rows = []
    ma5 = data.rolling(5).mean()
    ma10 = data.rolling(10).mean()
    ma20 = data.rolling(20).mean()
    for ticker in data.columns:
        series = data[ticker].dropna()
        if len(series) < 20:
            continue
        common_idx = series.index.intersection(ma5[ticker].dropna().index).intersection(ma10[ticker].dropna().index).intersection(ma20[ticker].dropna().index)
        series = series.loc[common_idx]
        s5 = ma5[ticker].loc[common_idx]
        s10 = ma10[ticker].loc[common_idx]
        s20 = ma20[ticker].loc[common_idx]
        rows.append({
            "티커": ticker,
            "ETF명": korea_industry_etfs.get(ticker, ticker),
            "5일선유지일": count_consecutive_above(series, s5),
            "10일선유지일": count_consecutive_above(series, s10),
            "20일선유지일": count_consecutive_above(series, s20),
            "현재가": int(round(series.iloc[-1])),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["유지그룹"] = np.select(
        [df["5일선유지일"] >= 5, df["10일선유지일"] >= 5, df["20일선유지일"] >= 5],
        ["5일선 유지그룹", "10일선 유지그룹", "20일선 유지그룹"],
        default="단기 확인",
    )
    return df.sort_values(["5일선유지일", "10일선유지일", "20일선유지일"], ascending=False)


def detect_ma_transition(data, lookback_days=5):
    rows = []
    ma5 = data.rolling(5).mean()
    ma10 = data.rolling(10).mean()
    ma20 = data.rolling(20).mean()
    for ticker in data.columns:
        series = data[ticker].dropna()
        if len(series) < 30:
            continue
        recent = series.tail(lookback_days)
        r5 = ma5[ticker].loc[recent.index]
        r10 = ma10[ticker].loc[recent.index]
        r20 = ma20[ticker].loc[recent.index]
        prev_close = recent.iloc[0]
        now_close = recent.iloc[-1]
        signal = None
        if prev_close > r20.iloc[0] and now_close > r10.iloc[-1] and now_close > r20.iloc[-1]:
            signal = "20일선 → 10일선 상승"
        if prev_close > r10.iloc[0] and now_close > r5.iloc[-1] and now_close > r10.iloc[-1]:
            signal = "10일선 → 5일선 상승"
        if signal:
            rows.append({
                "티커": ticker,
                "ETF명": korea_industry_etfs.get(ticker, ticker),
                "상승신호": signal,
                "최근등락률": int(round((now_close / prev_close - 1) * 100)),
                "현재가": int(round(now_close)),
            })
    return pd.DataFrame(rows)


def calculate_stock_rs_inside_etf(data, transition_df, benchmark="069500.KS", lookback=20, top_n=5):
    rows = []
    if transition_df is None or transition_df.empty:
        return pd.DataFrame()
    bench_ret = data[benchmark].pct_change(lookback).iloc[-1] if benchmark in data.columns else data.pct_change(lookback).iloc[-1].mean()
    for _, etf_row in transition_df.iterrows():
        for stock_ticker, stock_name in etf_holdings_map.get(etf_row["티커"], {}).items():
            if stock_ticker not in data.columns:
                continue
            stock_ret = data[stock_ticker].pct_change(lookback).iloc[-1]
            if pd.isna(stock_ret) or pd.isna(bench_ret):
                continue
            rows.append({
                "ETF명": etf_row["ETF명"],
                "ETF상승신호": etf_row["상승신호"],
                "종목명": stock_name,
                "20일수익률": int(round(stock_ret * 100)),
                "RS점수": int(round((stock_ret - bench_ret) * 100)),
            })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df["종목RS순위"] = df.groupby("ETF명")["RS점수"].rank(ascending=False, method="first").astype(int)
    return df[df["종목RS순위"] <= top_n].sort_values(["ETF명", "종목RS순위"])


def load_font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf" if bold else "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumBarunGothicBold.ttf" if bold else "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/Library/Fonts/AppleGothic.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def draw_card(draw, box, fill="white", outline="#dbe3ef", radius=22):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=2)


def draw_text(draw, xy, text, font, fill, max_width, line_gap=8):
    x, y = xy
    words = str(text).split()
    line = ""
    for word in words:
        candidate = word if not line else f"{line} {word}"
        if draw.textlength(candidate, font=font) <= max_width:
            line = candidate
        else:
            draw.text((x, y), line, font=font, fill=fill)
            y += font.size + line_gap
            line = word
    if line:
        draw.text((x, y), line, font=font, fill=fill)
        y += font.size + line_gap
    return y


def draw_table(draw, x, y, width, title, rows, columns, font, small_font, title_fill="#172554", limit=8):
    draw.text((x, y), title, font=load_font(30, bold=True), fill=title_fill)
    y += 52
    if rows is None or rows.empty:
        draw.text((x, y), "데이터 없음", font=font, fill="#64748b")
        return y + 42
    for idx, (_, row) in enumerate(rows.head(limit).iterrows(), start=1):
        parts = []
        for col in columns:
            if col in row:
                parts.append(f"{col} {row[col]}")
        y = draw_text(draw, (x, y), f"{idx}. " + " / ".join(parts), small_font, "#334155", width, line_gap=5)
    return y


def make_report_image(rs_top5_df, ma_hold_df, transition_df, inside_rs_df, momentum_df, valid_count, invalid_count):
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    width, height = 1200, 1760
    margin = 56
    bg = "#f4f7fb"
    navy = "#172554"
    red = "#dc2626"
    muted = "#4b5563"
    line = "#dbe3ef"
    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)
    title_font = load_font(58, bold=True)
    subtitle_font = load_font(27)
    label_font = load_font(26, bold=True)
    metric_font = load_font(42, bold=True)
    body_font = load_font(24)
    small_font = load_font(21)

    for gx in range(0, width, 48):
        draw.line((gx, 0, gx, height), fill="#edf2f7", width=1)
    for gy in range(0, height, 48):
        draw.line((0, gy, width, gy), fill="#edf2f7", width=1)

    y = 44
    draw.text((margin, y), "Korea ETF RS Report", font=title_font, fill=navy)
    draw.rectangle((margin, y + 76, margin + 610, y + 82), fill="#c8a24a")
    y += 96
    draw.text((margin, y), f"{NOW_STR} | ETF 상대강도 / 이평구조 / 내부 RS", font=subtitle_font, fill=muted)
    y += 82

    metrics = [
        ("RS TOP5", len(rs_top5_df), navy),
        ("이평 유지", len(ma_hold_df), navy),
        ("이평 상승", len(transition_df), red),
        ("내부 RS", len(inside_rs_df), red),
    ]
    metric_w = (width - margin * 2 - 24 * 3) // 4
    for i, (label, value, color) in enumerate(metrics):
        x0 = margin + i * (metric_w + 24)
        draw_card(draw, (x0, y, x0 + metric_w, y + 132), fill="white", outline=line)
        draw.text((x0 + 22, y + 22), label, font=label_font, fill=muted)
        draw.text((x0 + 22, y + 64), str(int(value)), font=metric_font, fill=color)
    y += 158

    draw_card(draw, (margin, y, width - margin, y + 270), fill="white", outline=line)
    left_x = margin + 28
    right_x = margin + 560
    draw_table(draw, left_x, y + 26, 500, "ETF RS TOP5", rs_top5_df, ["ETF명", "20일수익률", "RS점수"], body_font, small_font, limit=5)
    draw_table(draw, right_x, y + 26, 520, "이평 단계 상승 ETF", transition_df, ["ETF명", "상승신호", "최근등락률"], body_font, small_font, title_fill=red, limit=5)
    y += 296

    draw_card(draw, (margin, y, width - margin, y + 388), fill="white", outline=line)
    draw_table(draw, margin + 28, y + 26, width - margin * 2 - 56, "이평 유지그룹 TOP10", ma_hold_df, ["ETF명", "유지그룹", "5일선유지일", "10일선유지일", "20일선유지일"], body_font, small_font, limit=10)
    y += 414

    draw_card(draw, (margin, y, width - margin, y + 360), fill="#fff7f7", outline="#fecaca")
    draw_table(draw, margin + 28, y + 26, width - margin * 2 - 56, "상승 ETF 내부 RS 종목", inside_rs_df, ["ETF명", "종목명", "20일수익률", "RS점수"], body_font, small_font, title_fill=red, limit=8)
    y += 386

    latest_momentum = pd.DataFrame()
    if momentum_df is not None and not momentum_df.empty:
        latest = momentum_df.iloc[-1].dropna().head(10).tolist()
        latest_momentum = pd.DataFrame({"모멘텀TOP": latest})
    draw_card(draw, (margin, y, width - margin, y + 270), fill="white", outline=line)
    draw_table(draw, margin + 28, y + 26, width - margin * 2 - 56, "변동성 조정 모멘텀 TOP10", latest_momentum, ["모멘텀TOP"], body_font, small_font, limit=10)
    y += 296

    draw.text((margin, y), f"수집 성공 티커 {valid_count}개 / 제외 {invalid_count}개", font=body_font, fill=muted)
    path = RESULTS_DIR / f"etf_rs_report_{TODAY}.png"
    img.save(path)
    print(f"[OK] ETF 이미지 저장: {path}")
    return path


def send_telegram_photo(image_path):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        note = "[INFO] Telegram secret 없음: 이미지 발송 생략"
        if TELEGRAM_REQUIRED:
            raise RuntimeError(note)
        print(note)
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    with open(image_path, "rb") as image_file:
        response = requests.post(
            url,
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": "Korea ETF RS Report"},
            files={"photo": image_file},
            timeout=60,
        )
    if not response.ok:
        raise RuntimeError(f"Telegram 이미지 발송 실패: {response.status_code} {response.text}")
    print("[OK] Telegram ETF 이미지 발송 완료")


def main():
    print("[1] ETF 데이터 다운로드")
    data, etf_data, valid_tickers, invalid_tickers = download_data()
    print(f"[OK] 정상 수집 티커 {len(valid_tickers)}개 / 제외 {len(invalid_tickers)}개")
    time.sleep(0.5)

    print("[2] 지표 계산")
    momentum_df = calculate_risk_adjusted_momentum(etf_data, last_n_days=10)
    rs_top5_df = calculate_rs_rank(etf_data, top_n=5)
    ma_hold_df = calculate_ma_hold_groups(etf_data)
    transition_df = detect_ma_transition(etf_data, lookback_days=5)
    inside_rs_df = calculate_stock_rs_inside_etf(data, transition_df, top_n=5)

    print("[3] 이미지 생성")
    image_path = make_report_image(rs_top5_df, ma_hold_df, transition_df, inside_rs_df, momentum_df, len(valid_tickers), len(invalid_tickers))

    print("[4] Telegram 발송")
    send_telegram_photo(image_path)
    print("[DONE] ETF RS Report")


if __name__ == "__main__":
    main()
