from __future__ import annotations

import importlib.util
import math
import os
import pathlib
import textwrap
from datetime import datetime

import numpy as np
import pandas as pd
import requests
from PIL import Image, ImageDraw, ImageFont


SOURCE_PATH = pathlib.Path(__file__).with_name("etf_ma_full.py")
RESULTS_DIR = pathlib.Path(os.getenv("RESULTS_DIR", "results"))


def find_font_path() -> str:
    candidates = [
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/Library/Fonts/AppleGothic.ttf",
    ]
    for path in candidates:
        if pathlib.Path(path).exists():
            return path
    return ""


FONT_PATH = find_font_path()


def load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    if FONT_PATH:
        try:
            index = 2 if bold and FONT_PATH.endswith(".ttc") else 0
            return ImageFont.truetype(FONT_PATH, size=size, index=index)
        except Exception:
            pass
    return ImageFont.load_default()


def load_source_module():
    spec = importlib.util.spec_from_file_location("etf_ma_full", SOURCE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"분석 파일을 불러올 수 없습니다: {SOURCE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def safe_num(value, digits: int = 1) -> str:
    if value is None or pd.isna(value):
        return "-"
    try:
        value = float(value)
    except Exception:
        return str(value)
    if math.isnan(value):
        return "-"
    return f"{value:.{digits}f}".rstrip("0").rstrip(".")


def shorten_name(name: object) -> str:
    text = str(name)
    for token in ["KODEX ", "TIGER ", "SOL ", "ACE ", "PLUS ", "HANARO ", "TIMEFOLIO ", "KIWOOM ", "RISE "]:
        text = text.replace(token, "")
    return text.strip()


def rank_change_text(current_rank, previous_rank) -> str:
    if pd.isna(current_rank) or pd.isna(previous_rank):
        return "NEW"
    diff = int(previous_rank) - int(current_rank)
    if diff > 0:
        return f"▲{diff}"
    if diff < 0:
        return f"▼{abs(diff)}"
    return "="


def build_ra_rank_change(score_history_df: pd.DataFrame) -> dict[str, str]:
    if score_history_df is None or score_history_df.empty:
        return {}
    dates = sorted(score_history_df["날짜"].dropna().unique())
    if len(dates) < 2:
        return {}
    latest, previous = dates[-1], dates[-2]

    def rank_for(day: str) -> pd.DataFrame:
        part = score_history_df[score_history_df["날짜"] == day].copy()
        part = part.sort_values("RA_AVG", ascending=False).reset_index(drop=True)
        part["rank"] = range(1, len(part) + 1)
        return part[["종목명", "rank"]]

    cur = rank_for(latest)
    prev = rank_for(previous).rename(columns={"rank": "prev_rank"})
    merged = cur.merge(prev, on="종목명", how="left")
    return {r["종목명"]: rank_change_text(r["rank"], r["prev_rank"]) for _, r in merged.iterrows()}


def prepare_display_df(df: pd.DataFrame, rank_changes: dict[str, str]) -> pd.DataFrame:
    df = df.copy()
    if df.empty:
        return df
    df["순위변화"] = df["종목명"].map(rank_changes).fillna("NEW")
    df["종목명_짧게"] = df["종목명"].map(shorten_name)
    df["이평5"] = df["현재_MA5_위아래"].fillna("-")
    df["이평10"] = df["현재_MA10_위아래"].fillna("-")
    df["이평20"] = df["현재_MA20_위아래"].fillna("-")
    df["최종점수"] = df["FINAL_SCORE"].map(lambda v: safe_num(v, 1))
    df["RA"] = df["RA순위"].map(lambda v: "-" if pd.isna(v) else str(int(v)))
    df["거래"] = df["거래대금증가율_5vs20"].map(lambda v: safe_num(v, 2) + "x" if pd.notna(v) else "-")
    return df


def build_turning_watch_df(buy_all: pd.DataFrame) -> pd.DataFrame:
    if buy_all is None or buy_all.empty:
        return pd.DataFrame()
    watch = buy_all[buy_all["순위"] > 10].copy()
    if watch.empty:
        return watch
    cond = (
        (watch["매매단계"] == "관심")
        & (
            (watch["오늘_상향돌파_MA10"] == "Y")
            | (watch["오늘_상향돌파_MA20"] == "Y")
            | (
                (watch["현재_MA20_위아래"] == "위")
                & (watch["현재_MA5_위아래"] == "위")
            )
        )
    )
    return watch[cond].head(5).reset_index(drop=True)


def build_report_data():
    src = load_source_module()
    results = src.run_all()
    if not results:
        raise RuntimeError("ETF 20일선 분석 결과가 없습니다.")
    close_df = src.build_close_panel(results, only_universe=True)
    _, ra_score_history_df = src.calculate_risk_adjusted_momentum_table(
        close_df,
        period_1m=src.RA_1M,
        period_3m=src.RA_3M,
        period_6m=src.RA_6M,
        last_n_days=src.RA_LAST_N_DAYS,
    )
    today_ra_rank_df = src.build_today_ra_rank(ra_score_history_df)
    buy_top10, buy_all, market_info = src.build_buy_candidates_top10(results, today_ra_rank_df)
    rank_changes = build_ra_rank_change(ra_score_history_df)

    top_df = prepare_display_df(buy_top10, rank_changes)
    watch_df = prepare_display_df(build_turning_watch_df(buy_all), rank_changes)
    return top_df, watch_df, market_info


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), str(text), font=font)
    return box[2] - box[0]


def wrap_text(draw: ImageDraw.ImageDraw, text: object, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    raw = "" if text is None else str(text)
    if not raw:
        return [""]
    lines: list[str] = []
    current = ""
    for token in raw.replace("+", " + ").split(" "):
        if not token:
            continue
        candidate = token if not current else f"{current} {token}"
        if text_width(draw, candidate, font) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        if text_width(draw, token, font) <= max_width:
            current = token
        else:
            unit = max(text_width(draw, "가", font), 1)
            parts = textwrap.wrap(token, width=max(4, int(max_width / unit)), break_long_words=True)
            lines.extend(parts[:-1])
            current = parts[-1] if parts else ""
    lines.append(current)
    return lines or [""]


def color_for_value(value: str) -> str:
    if value == "위" or value == "정배열" or value.startswith("▲") or value == "매수":
        return "#dc2626"
    if value == "아래" or value == "역배열" or value.startswith("▼"):
        return "#2563eb"
    if value == "관심" or value == "혼조":
        return "#e26a2c"
    return "#111827"


def render_table_rows(
    draw: ImageDraw.ImageDraw,
    df: pd.DataFrame,
    columns: list[tuple[str, str, int]],
    x0: int,
    y: int,
    width: int,
    margin: int,
    row_h: int,
    fonts: dict[str, ImageFont.ImageFont],
) -> int:
    gap = 14
    if df.empty:
        draw.text((x0 + 20, y + 36), "조건에 맞는 후보가 없습니다.", font=fonts["body_bold"], fill="#64748b")
        return y + row_h
    for idx, row in df.iterrows():
        fill = "#ffffff" if idx % 2 == 0 else "#f8fafc"
        draw.rounded_rectangle((x0, y, width - margin, y + row_h), radius=8, fill=fill)
        x = x0
        for key, _, col_w in columns:
            value = str(row.get(key, ""))
            font = fonts["body_bold"] if key in {"순위", "종목명_짧게", "매매단계", "배열상태"} else fonts["body"]
            color = color_for_value(value)
            if key == "한줄코멘트":
                yy = y + 18
                for line in wrap_text(draw, value, fonts["small"], col_w - 12)[:3]:
                    draw.text((x + 8, yy), line, font=fonts["small"], fill="#334155")
                    yy += 26
            else:
                yy = y + 43
                if key == "종목명_짧게":
                    yy = y + 31
                    for line in wrap_text(draw, value, fonts["body_bold"], col_w - 12)[:2]:
                        draw.text((x + 8, yy), line, font=fonts["body_bold"], fill=color)
                        yy += 30
                else:
                    draw.text((x + 8, yy), value, font=font, fill=color)
            x += col_w + gap
        draw.line((x0 + 8, y + row_h - 1, width - margin - 8, y + row_h - 1), fill="#e5e7eb", width=1)
        y += row_h
    return y


def render_image(df: pd.DataFrame, watch_df: pd.DataFrame, market_info: dict) -> pathlib.Path:
    width = 1800
    margin = 64
    title_h = 168
    header_h = 54
    row_h = 118
    section_h = 58
    footer_h = 54
    height = (
        margin + title_h
        + section_h + header_h + max(len(df), 1) * row_h
        + section_h + header_h + max(len(watch_df), 1) * row_h
        + footer_h + margin
    )

    img = Image.new("RGB", (width, height), "#f3f6fb")
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((32, 32, width - 32, height - 32), radius=28, fill="#ffffff")

    title_font = load_font(44, True)
    sub_font = load_font(23)
    header_font = load_font(22, True)
    body_font = load_font(24)
    body_bold = load_font(25, True)
    small_font = load_font(19)
    fonts = {"body": body_font, "body_bold": body_bold, "small": small_font}

    draw.text((margin, 58), "ETF 20일선 종합 리포트 | 매수후보 최종요약", font=title_font, fill="#14213d")
    subtitle = (
        f"시장: {market_info.get('market_view', '-')} / "
        f"20일선 위 {market_info.get('ma20_above_count', '-')}/{market_info.get('universe_count', '-')} "
        f"({market_info.get('ma20_above_ratio', '-')}%) / "
        f"정배열 {market_info.get('stack_bull_count', '-')}개"
    )
    draw.text((margin, 116), subtitle, font=sub_font, fill="#475569")

    columns = [
        ("순위", "순위", 70),
        ("순위변화", "변화", 88),
        ("종목명_짧게", "ETF명", 282),
        ("매매단계", "단계", 86),
        ("최종점수", "점수", 88),
        ("이평5", "5일", 72),
        ("이평10", "10일", 78),
        ("이평20", "20일", 78),
        ("배열상태", "배열", 108),
        ("RA", "RA", 64),
        ("거래", "거래", 86),
        ("한줄코멘트", "요약 코멘트", 594),
    ]
    gap = 14
    x0 = margin
    y = margin + title_h

    draw.rounded_rectangle((x0, y + 8, width - margin, y + section_h - 8), radius=16, fill="#172554")
    draw.text((x0 + 22, y + 20), "매수후보 TOP10", font=load_font(27, True), fill="#ffffff")
    y += section_h

    draw.rounded_rectangle((x0, y, width - margin, y + header_h), radius=10, fill="#e8eef8")
    x = x0
    for _, label, col_w in columns:
        draw.text((x + 8, y + 15), label, font=header_font, fill="#23324d")
        x += col_w + gap

    y += header_h
    y = render_table_rows(draw, df, columns, x0, y, width, margin, row_h, fonts)

    y += 18
    draw.rounded_rectangle((x0, y + 8, width - margin, y + section_h - 8), radius=16, fill="#7c2d12")
    draw.text((x0 + 22, y + 20), "순위 아래 이평 돌리는 관심", font=load_font(27, True), fill="#ffffff")
    y += section_h

    draw.rounded_rectangle((x0, y, width - margin, y + header_h), radius=10, fill="#fff1e8")
    x = x0
    for _, label, col_w in columns:
        draw.text((x + 8, y + 15), label, font=header_font, fill="#7c2d12")
        x += col_w + gap
    y += header_h
    y = render_table_rows(draw, watch_df, columns, x0, y, width, margin, row_h, fonts)

    draw.text(
        (margin, height - margin - 28),
        f"생성시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · 순위변화는 전 거래일 RA 순위 대비",
        font=small_font,
        fill="#64748b",
    )
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"etf_ma_buy_summary_{datetime.now().strftime('%Y-%m-%d')}.png"
    img.save(out)
    return out


def send_telegram_photo(image_path: pathlib.Path) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    required = os.getenv("TELEGRAM_REQUIRED", "").lower() == "true"
    if not token or not chat_id:
        message = "TELEGRAM_BOT_TOKEN 또는 TELEGRAM_CHAT_ID가 없어 텔레그램 발송을 건너뜁니다."
        if required:
            raise RuntimeError(message)
        print(message)
        return
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    caption = f"[ETF 20일선 종합 리포트]\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    with image_path.open("rb") as fp:
        response = requests.post(
            url,
            data={"chat_id": chat_id, "caption": caption},
            files={"photo": fp},
            timeout=60,
        )
    if not response.ok:
        raise RuntimeError(f"텔레그램 발송 실패: {response.status_code} {response.text}")
    print("텔레그램 발송 완료:", image_path)


def main() -> None:
    df, watch_df, market_info = build_report_data()
    image_path = render_image(df, watch_df, market_info)
    print("이미지 생성 완료:", image_path)
    send_telegram_photo(image_path)


if __name__ == "__main__":
    main()
