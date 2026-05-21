from __future__ import annotations

import importlib.util
import math
import os
import pathlib
import textwrap
from datetime import datetime

import requests
from PIL import Image, ImageDraw, ImageFont


SOURCE_PATH = pathlib.Path(__file__).with_name("stocktrend_full_v3.py")
RESULTS_DIR = pathlib.Path(os.getenv("RESULTS_DIR", "results"))
SECTION_LABELS = {
    "BOOM_SCORE": "Boom Score 상위 섹터",
    "ETF_SECTOR_RANK": "ETF 섹터 순위",
    "VALUE_THEME": "거래대금 폭발 테마",
    "STOCK_CLOSE_BUY": "종가 매수 종목 후보",
    "ETF_CLOSE_BUY": "종가 매수 ETF 후보",
    "RET_APPEARANCE": "등락률 출현 횟수",
    "SECTOR_EXPANSION": "섹터 종목 확산",
}
FIRST_PAGE_SECTIONS = {
    "BOOM_SCORE",
    "ETF_SECTOR_RANK",
    "VALUE_THEME",
    "STOCK_CLOSE_BUY",
    "ETF_CLOSE_BUY",
}


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


def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), str(text), font=font)
    return box[2] - box[0]


def wrap_text(draw: ImageDraw.ImageDraw, text: object, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    raw = "" if text is None else str(text)
    if not raw:
        return [""]
    lines: list[str] = []
    for paragraph in raw.split("\n"):
        current = ""
        for token in paragraph.replace("|", " | ").split(" "):
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
                approx = max(4, int(max_width / unit))
                parts = textwrap.wrap(token, width=approx, break_long_words=True)
                lines.extend(parts[:-1])
                current = parts[-1] if parts else ""
        lines.append(current)
    return lines or [""]


def fmt_value(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def run_analysis() -> list[dict]:
    spec = importlib.util.spec_from_file_location("stocktrend_full_v3", SOURCE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"분석 파일을 불러올 수 없습니다: {SOURCE_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    results = module.main()
    return results["one_page_summary"]


def split_summary_rows(rows: list[dict]) -> list[list[dict]]:
    first: list[dict] = []
    second: list[dict] = []
    for row in rows:
        section = str(row.get("section", "SUMMARY"))
        if section in FIRST_PAGE_SECTIONS:
            first.append(row)
        else:
            second.append(row)
    return [part for part in (first, second) if part]


def render_summary(rows: list[dict], page_no: int, page_total: int) -> pathlib.Path:
    width = 1700
    margin_x = 70
    top = 64
    bottom = 70
    table_x = margin_x
    table_w = width - margin_x * 2

    title_font = load_font(42, True)
    sub_font = load_font(22)
    section_font = load_font(27, True)
    header_font = load_font(21, True)
    body_font = load_font(22)
    small_font = load_font(20)

    probe = Image.new("RGB", (width, 200), "white")
    probe_draw = ImageDraw.Draw(probe)
    columns = [
        ("rank", "순위", 90),
        ("name", "이름", 260),
        ("score", "점수", 130),
        ("detail1", "상세 1", 330),
        ("detail2", "상세 2", 360),
        ("detail3", "상세 3", 390),
    ]
    gap = 18

    section_order: list[str] = []
    for row in rows:
        section = str(row.get("section", "SUMMARY"))
        if section not in section_order:
            section_order.append(section)

    layout: list[tuple[str, dict | None, int]] = []
    y = top + 92
    for section in section_order:
        section_rows = [r for r in rows if str(r.get("section", "SUMMARY")) == section]
        layout.append((section, None, 58))
        y += 58
        layout.append((section, {"__header__": True}, 46))
        y += 46
        for row in section_rows:
            line_counts = []
            for key, _, col_w in columns:
                line_counts.append(len(wrap_text(probe_draw, fmt_value(row.get(key)), body_font, col_w - 24)))
            row_h = max(48, max(line_counts) * 29 + 22)
            layout.append((section, row, row_h))
            y += row_h
        y += 16

    height = y + bottom
    img = Image.new("RGB", (width, height), "#f3f6fb")
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((34, 34, width - 34, height - 34), radius=28, fill="#ffffff")
    draw.text((margin_x, 58), f"국내 주식 트렌드 분석 | 요약 {page_no}/{page_total}", font=title_font, fill="#14213d")
    draw.text(
        (margin_x, 112),
        f"생성시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ·  {page_no}/{page_total} 페이지 · {len(rows)}행",
        font=sub_font,
        fill="#6b7280",
    )

    y = top + 92
    for section, row, row_h in layout:
        if row is None:
            label = SECTION_LABELS.get(section, section)
            draw.rounded_rectangle((table_x, y + 8, table_x + table_w, y + row_h - 8), radius=16, fill="#172554")
            draw.text((table_x + 22, y + 20), label, font=section_font, fill="#ffffff")
            y += row_h
            continue
        if row.get("__header__"):
            x = table_x
            draw.rounded_rectangle((x, y, x + table_w, y + row_h), radius=10, fill="#e8eef8")
            for _, label, col_w in columns:
                draw.text((x + 12, y + 12), label, font=header_font, fill="#23324d")
                x += col_w + gap
            y += row_h
            continue

        fill = "#ffffff" if (y // 10) % 2 == 0 else "#f8fafc"
        draw.rounded_rectangle((table_x, y, table_x + table_w, y + row_h), radius=8, fill=fill)
        x = table_x
        for key, _, col_w in columns:
            value = fmt_value(row.get(key))
            font = body_font
            color = "#111827"
            if key == "rank":
                font = load_font(23, True)
                color = "#dc2626" if value in {"1", "2", "3"} else "#334155"
            elif key == "score":
                color = "#dc2626" if value and not value.startswith("-") else "#2563eb"
            elif key == "name":
                font = load_font(23, True)
            yy = y + 13
            for line in wrap_text(draw, value, font, col_w - 24):
                draw.text((x + 12, yy), line, font=font if yy == y + 13 else small_font, fill=color)
                yy += 29
            x += col_w + gap
        draw.line((table_x + 8, y + row_h - 1, table_x + table_w - 8, y + row_h - 1), fill="#e5e7eb", width=1)
        y += row_h

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / f"stocktrend_one_page_summary_{datetime.now().strftime('%Y-%m-%d')}_{page_no}of{page_total}.png"
    img.save(out_path)
    return out_path


def send_telegram_photo(image_path: pathlib.Path, page_no: int, page_total: int) -> None:
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
    caption = f"[국내 주식 트렌드 분석 {page_no}/{page_total}]\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
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
    rows = run_analysis()
    parts = split_summary_rows(rows)
    page_total = len(parts)
    image_paths = [render_summary(part, idx, page_total) for idx, part in enumerate(parts, start=1)]
    for image_path in image_paths:
        print("이미지 생성 완료:", image_path)
    for idx, image_path in enumerate(image_paths, start=1):
        send_telegram_photo(image_path, idx, page_total)


if __name__ == "__main__":
    main()
