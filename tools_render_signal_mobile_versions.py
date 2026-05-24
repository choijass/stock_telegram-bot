from __future__ import annotations

import pathlib

from PIL import Image, ImageDraw, ImageFont


BASE = pathlib.Path(__file__).resolve().parent
OUT_DIR = BASE / "preview_weekly_actual_pages" / "mobile_versions"
FONT_PATH = "/System/Library/Fonts/AppleSDGothicNeo.ttc"
LINUX_FONT_PATH = "/usr/share/fonts/truetype/nanum/NanumGothic.ttf"


def font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    for path in (FONT_PATH, LINUX_FONT_PATH):
        try:
            return ImageFont.truetype(path, size=size, index=2 if path == FONT_PATH and bold else 0)
        except Exception:
            continue
    return ImageFont.load_default()


def tw(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont) -> int:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0]


def rr(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, radius: int = 28, outline: str | None = None, width: int = 1) -> None:
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont, max_width: int) -> list[str]:
    lines: list[str] = []
    for para in str(text or "-").split("\n"):
        current = ""
        for token in para.replace("/", " / ").replace("·", " · ").split():
            candidate = token if not current else f"{current} {token}"
            if tw(draw, candidate, fnt) <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = token
        if current:
            lines.append(current)
    return lines or ["-"]


def draw_wrapped(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, fnt: ImageFont.ImageFont, fill: str, max_width: int, line_h: int, max_lines: int | None = None) -> int:
    lines = wrap(draw, text, fnt, max_width)
    if max_lines is not None and len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".") + "..."
    for line in lines:
        draw.text((x, y), line, font=fnt, fill=fill)
        y += line_h
    return y


def pill(draw: ImageDraw.ImageDraw, x: int, y: int, label: str, fill: str, color: str = "#ffffff") -> None:
    f = font(19, True)
    w = tw(draw, label, f) + 34
    rr(draw, (x, y, x + w, y + 38), fill, 19)
    draw.text((x + 17, y + 8), label, font=f, fill=color)


def status(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, day: str, state: str, color: str, panel: str, border: str) -> None:
    rr(draw, (x, y, x + w, y + 116), panel, 22, border, 1)
    draw.text((x + 22, y + 21), day, font=font(21, True), fill="#9aa8bc")
    draw.text((x + 22, y + 64), state, font=font(31, True), fill=color)


def timeline(draw: ImageDraw.ImageDraw, x: int, y: int, width: int, line: str) -> None:
    items = [
        ("월", "없음", "#7d8898"),
        ("화", "방어", "#38bdf8"),
        ("수", "현금", "#60a5fa"),
        ("목", "공격", "#ef4444"),
        ("금", "유지", "#fb7185"),
    ]
    step = width // 5
    cy = y + 82
    for i, (day, label, color) in enumerate(items):
        cx = x + step * i + step // 2
        if i < len(items) - 1:
            nx = x + step * (i + 1) + step // 2
            draw.line((cx + 30, cy, nx - 32, cy), fill=line, width=5)
            draw.polygon([(nx - 32, cy), (nx - 48, cy - 10), (nx - 48, cy + 10)], fill=line)
        draw.ellipse((cx - 30, cy - 30, cx + 30, cy + 30), fill=color)
        draw.text((cx - tw(draw, day, font(21, True)) // 2, cy - 14), day, font=font(21, True), fill="#ffffff")
        draw.text((cx - tw(draw, label, font(17, True)) // 2, cy + 46), label, font=font(17, True), fill="#ffffff")


def bullet(draw: ImageDraw.ImageDraw, x: int, y: int, text: str, dot: str, max_width: int, text_color: str) -> int:
    draw.ellipse((x, y + 10, x + 17, y + 27), fill=dot)
    return draw_wrapped(draw, x + 34, y, text, font(24, True), text_color, max_width - 34, 35, 3) + 18


def section(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, title: str, lines: list[str], dot: str, panel: str, border: str, text_color: str) -> int:
    temp = Image.new("RGB", (1, 1))
    td = ImageDraw.Draw(temp)
    content_h = sum(len(wrap(td, line, font(24, True), w - 102)) * 35 + 18 for line in lines)
    h = max(210, 98 + content_h + 36)
    rr(draw, (x, y, x + w, y + h), panel, 28, border, 1)
    draw.text((x + 34, y + 34), title, font=font(32, True), fill=text_color)
    yy = y + 98
    for line in lines:
        yy = bullet(draw, x + 34, yy, line, dot, w - 68, text_color)
    return y + h + 28


CORE = [
    "화~수: 방어 심화, 현금 최우선까지 하락",
    "목: 최상위 공격으로 급반전, 반도체 중심 포트 강화",
    "금: 공격 유지로 완화, 교체 후보는 바이오·조선·AI 약세 중심",
]
PORT = [
    "화: 반도체:2 / 지수:2 / 전력:1 / 2차전지:1 / 헤지:1",
    "목: 반도체 4개로 확대, 지수·2차전지 일부 축소",
    "금: 코스닥150레버리지 · 에코프로 · 리가켐바이오 교체 후보",
]
SUMMARY = (
    "이번 주는 초반 방어 심화로 현금 최우선 단계까지 내려갔지만, 목요일 최상위 공격으로 빠르게 반전되었습니다. "
    "금요일에는 공격 유지로 마감하며 주식 비중은 열어두되 속도 조절이 필요한 흐름입니다. "
    "포트폴리오는 반도체 중심으로 강화되었고, 지수·2차전지 일부 축소와 바이오·조선·AI 약세 후보 점검이 필요합니다."
)


THEMES = [
    {
        "num": "01",
        "name": "다크 대시보드",
        "file": "01_dark_dashboard.png",
        "bg": "#070b13",
        "outer": "#0f172a",
        "panel": "#101827",
        "border": "#334155",
        "title": "#ffffff",
        "text": "#f1f5f9",
        "muted": "#8da0b8",
        "line": "#4b5568",
    },
    {
        "num": "02",
        "name": "블루 리포트",
        "file": "02_blue_report.png",
        "bg": "#071426",
        "outer": "#10243d",
        "panel": "#0b1b31",
        "border": "#2563eb",
        "title": "#f8fbff",
        "text": "#e5efff",
        "muted": "#93c5fd",
        "line": "#3b82f6",
    },
    {
        "num": "03",
        "name": "프리미엄 블랙",
        "file": "03_premium_black.png",
        "bg": "#030712",
        "outer": "#080d18",
        "panel": "#0b0f19",
        "border": "#52525b",
        "title": "#fafafa",
        "text": "#f4f4f5",
        "muted": "#a1a1aa",
        "line": "#71717a",
    },
    {
        "num": "04",
        "name": "레드 포커스",
        "file": "04_red_focus.png",
        "bg": "#12070a",
        "outer": "#1a1117",
        "panel": "#18111b",
        "border": "#be123c",
        "title": "#fff7f7",
        "text": "#ffe4e6",
        "muted": "#fda4af",
        "line": "#9f1239",
    },
    {
        "num": "05",
        "name": "라이트 카드",
        "file": "05_light_card.png",
        "bg": "#dbe7f4",
        "outer": "#f8fafc",
        "panel": "#ffffff",
        "border": "#cbd5e1",
        "title": "#0f172a",
        "text": "#1e293b",
        "muted": "#475569",
        "line": "#94a3b8",
    },
]


def render(theme: dict[str, str]) -> pathlib.Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    width, height = 760, 2300
    image = Image.new("RGB", (width, height), theme["bg"])
    draw = ImageDraw.Draw(image)
    rr(draw, (30, 30, width - 30, height - 30), theme["outer"], 34, theme["border"], 1)

    x = 62
    content_w = width - 124
    y = 70
    pill(draw, x, y, f"{theme['num']} · {theme['name']}", "#1d4ed8" if theme["num"] != "05" else "#0f172a")
    y += 58
    draw.text((x, y), "SIGNAL DASHBOARD", font=font(24, True), fill=theme["muted"])
    y += 46
    draw.text((x, y), "주간 리스크 / 포지션", font=font(40, True), fill=theme["title"])
    y += 58
    draw.text((x, y), "2026.05.18 - 05.22 · 모바일 세로형", font=font(19, True), fill=theme["muted"])
    y += 54

    gap = 20
    card_w = (content_w - gap) // 2
    status(draw, x, y, card_w, "화", "방어", "#38bdf8", theme["panel"], theme["border"])
    status(draw, x + card_w + gap, y, card_w, "수", "현금", "#60a5fa", theme["panel"], theme["border"])
    y += 136
    status(draw, x, y, card_w, "목", "공격", "#ef4444", theme["panel"], theme["border"])
    status(draw, x + card_w + gap, y, card_w, "금", "유지", "#fb7185", theme["panel"], theme["border"])
    y += 154

    rr(draw, (x, y, x + content_w, y + 218), theme["panel"], 28, theme["border"], 1)
    draw.text((x + 34, y + 36), "Position Flow", font=font(31, True), fill=theme["title"])
    timeline(draw, x + 26, y + 64, content_w - 52, theme["line"])
    y += 246

    y = section(draw, x, y, content_w, "핵심 변화", CORE, "#ef4444", theme["panel"], theme["border"], theme["text"])
    y = section(draw, x, y, content_w, "포트 변화", PORT, "#f97316", theme["panel"], theme["border"], theme["text"])

    lines = wrap(draw, SUMMARY, font(24, True), content_w - 68)
    h = 124 + len(lines) * 38 + 86
    rr(draw, (x, y, x + content_w, y + h), theme["panel"], 28, theme["border"], 1)
    draw.text((x + 34, y + 34), "전체 주간 요약", font=font(32, True), fill=theme["title"])
    draw_wrapped(draw, x + 34, y + 98, SUMMARY, font(24, True), theme["text"], content_w - 68, 38, None)
    y += h + 44

    final_h = height
    image = image.crop((0, 0, width, final_h))
    path = OUT_DIR / theme["file"]
    image.save(path)
    return path


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        print(render(theme))


if __name__ == "__main__":
    main()
