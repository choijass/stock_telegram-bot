import html
import json
import os
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen



KST = timezone(timedelta(hours=9))
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"].strip()
CHAT_ID = os.getenv("SANGHANGA_TELEGRAM_CHAT_ID", os.getenv("TELEGRAM_CHAT_ID", "")).strip()
STATE_PATH = Path(os.getenv("SANGHANGA_STATE_PATH", "reports/sanghanga_seen.json"))
MAX_LEN = 3800

HEADERS = {"User-Agent": "Mozilla/5.0"}

NEWS_MAP = {
    "TS인베스트먼트": {
        "feature": "퓨리오사AI 투자 VC 관련주",
        "news": "퓨리오사AI 8000억 투자 수혜",
        "link": "https://www.mt.co.kr/amp/stock/2026/05/29/2026052909223359810",
        "related": "DSC인베스트먼트, LB인베스트먼트, 나우IB, 포바이포, 엑스페릭스",
        "importance": "🟥 ★★★★",
    },
    "LG전자": {
        "feature": "젠슨 황 방한·LG AI 협력 기대",
        "news": "젠슨 황 방한 기대에 LG그룹주 급등",
        "link": "https://stock.mk.co.kr/news/view/1096124",
        "related": "LG씨엔에스, LG이노텍, NAVER, 현대차, 현대모비스",
        "importance": "🟥 ★★★★",
    },
    "LG씨엔에스": {
        "feature": "LG그룹 AI·에이전틱 AI 수혜",
        "news": "LG AI 협력 기대감 부각",
        "link": "https://stock.mk.co.kr/news/view/1096124",
        "related": "LG전자, LG이노텍, 삼성SDS, 오브젠",
        "importance": "🟥 ★★★★",
    },
    "오브젠": {
        "feature": "AI 플랫폼 기술력 부각",
        "news": "AI 플랫폼주 동반 강세",
        "link": "https://www.newsprime.co.kr/news/article/?no=735093",
        "related": "플리토, 삼성SDS, NAVER, LG씨엔에스",
        "importance": "🟨 ★★",
    },
    "플리토": {
        "feature": "AI 통번역 솔루션 기대",
        "news": "AI 통번역 솔루션 기대",
        "link": "https://www.bodnara.co.kr/bbs/article.html?num=212831",
        "related": "오브젠, NAVER, 삼성SDS",
        "importance": "🟨 ★★",
    },
    "누리플랜": {
        "feature": "저시총 단기 수급",
        "news": "급등주 상위 종목 포함",
        "link": "https://alphasquare.co.kr/home/market-summary?code=006360",
        "related": "저시총 테마주, 단기 수급주",
        "importance": "⬜ ★",
    },
    "서울식품우": {
        "feature": "저유동성 우선주 수급",
        "news": "우선주 수급성 급등",
        "link": "https://finance.naver.com/item/main.naver?code=004415",
        "related": "서울식품, 우선주 테마",
        "importance": "⬜ ★",
    },
    "LG이노텍": {
        "feature": "AI 서버 기판 성장 기대",
        "news": "AI 서버 기판 성장 기대",
        "link": "https://www.edaily.co.kr/News/Read?mediaCodeNo=257&newsId=02709286645453840",
        "related": "삼성전기, LG전자, FC-BGA 관련주",
        "importance": "🟥 ★★★★",
    },
    "포바이포": {
        "feature": "퓨리오사AI 협력 관련주",
        "news": "퓨리오사AI 협력주 부각",
        "link": "https://www.newsway.co.kr/news/view?ud=2026052910005307757",
        "related": "TS인베스트먼트, DSC인베스트먼트, 엑스페릭스",
        "importance": "🟥 ★★★★",
    },
    "삼성전기": {
        "feature": "AI 반도체 부품·기판주",
        "news": "AI 반도체 부품주 확산",
        "link": "https://www.hani.co.kr/arti/economy/finance/1261074.html",
        "related": "LG이노텍, 삼성전자, 반도체 기판주",
        "importance": "🟧 ★★★",
    },
}

FALLBACK_ROWS = [
    {"code": "246690", "name": "TS인베스트먼트", "rate": 29.96, "market": "KOSDAQ", "market_cap": "724억"},
    {"code": "066570", "name": "LG전자", "rate": 29.93, "market": "KOSPI", "market_cap": "47조 7,252억"},
    {"code": "064400", "name": "LG씨엔에스", "rate": 29.91, "market": "KOSPI", "market_cap": "11조 256억"},
    {"code": "011070", "name": "LG이노텍", "rate": 28.57, "market": "KOSPI", "market_cap": "34조 5,066억"},
    {"code": "389140", "name": "포바이포", "rate": 20.43, "market": "KOSDAQ", "market_cap": "1,194억"},
    {"code": "009150", "name": "삼성전기", "rate": 15.04, "market": "KOSPI", "market_cap": "158조 8,735억"},
    {"code": "417860", "name": "오브젠", "rate": 29.93, "market": "KOSDAQ", "market_cap": "424억"},
    {"code": "300080", "name": "플리토", "rate": 29.89, "market": "KOSDAQ", "market_cap": "1,807억"},
    {"code": "069140", "name": "누리플랜", "rate": 29.90, "market": "KOSDAQ", "market_cap": "325억"},
    {"code": "004415", "name": "서울식품우", "rate": 29.94, "market": "KOSPI", "market_cap": "22억"},
]


def clean_text(value: str) -> str:
    value = html.unescape(str(value))
    value = re.sub(r"<[^>]*>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def fetch_rise_page(sosok: int) -> list[dict]:
    url = f"https://finance.naver.com/sise/sise_rise.naver?sosok={sosok}"
    response_text = http_get_text(url, encoding="euc-kr")
    market = "KOSPI" if sosok == 0 else "KOSDAQ"
    rows = []

    for block in re.findall(r"<tr>(.*?)</tr>", response_text, flags=re.S):
        m = re.search(r'code=(\d{6})" class="tltle">([^<]+)</a>', block)
        if not m:
            continue
        code, name = m.group(1), clean_text(m.group(2))
        rate_m = re.search(r'([+-]\d+(?:\.\d+)?)%', clean_text(block))
        if not rate_m:
            continue
        rate = float(rate_m.group(1).replace("+", ""))
        if rate < 15:
            continue
        rows.append(
            {
                "code": code,
                "name": name,
                "rate": rate,
                "market": market,
                "market_cap": get_market_cap(code),
            }
        )
    return rows


def get_market_cap(code: str) -> str:
    try:
        url = f"https://finance.naver.com/item/main.naver?code={code}"
        text = http_get_text(url, encoding="utf-8")
        m = re.search(r'<em id="_market_sum">\s*(.*?)\s*</em>', text, flags=re.S)
        if not m:
            return "-"
        value = clean_text(m.group(1)).replace(" ", "")
        return value or "-"
    except Exception:
        return "-"


def http_get_text(url: str, encoding: str) -> str:
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=20) as response:
        return response.read().decode(encoding, errors="replace")


def load_seen() -> set[str]:
    if not STATE_PATH.exists():
        return set()
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return set(data.get("seen_codes", []))
    except Exception:
        return set()


def save_seen(rows: list[dict]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "updated_at_kst": datetime.now(KST).isoformat(timespec="seconds"),
        "seen_codes": sorted({row["code"] for row in rows}),
    }
    STATE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def get_rows() -> list[dict]:
    rows: list[dict] = []
    try:
        rows.extend(fetch_rise_page(0))
        rows.extend(fetch_rise_page(1))
    except Exception as exc:
        print(f"[WARN] Naver rise fetch failed, fallback used: {exc}")
        rows = FALLBACK_ROWS[:]

    rows.sort(key=lambda row: row["rate"], reverse=True)
    return rows[:20]


def enrich(row: dict, seen: set[str]) -> dict:
    meta = NEWS_MAP.get(row["name"], {})
    title = row["name"] + (" [신규진입]" if row["code"] not in seen else "")
    return {
        **row,
        "title": title,
        "status": "상한가" if row["rate"] >= 29.5 else "장중 15% 이상",
        "news": meta.get("news", "장중 15% 이상 급등"),
        "feature": meta.get("feature", "장중 15% 이상 수급 유입"),
        "link": meta.get("link", f"https://finance.naver.com/item/main.naver?code={row['code']}"),
        "related": meta.get("related", "동일 테마/업종 확인 필요"),
        "importance": meta.get("importance", "🟨 ★★"),
    }


def version1(rows: list[dict]) -> str:
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    upper = [r for r in rows if r["status"] == "상한가"]
    fifteen = [r for r in rows if r["status"] != "상한가"]
    lines = [
        "1번. 상한가/급등주 리포트",
        f"기준: {now} KST",
        "중요도: 🟥 ★★★★ / 🟧 ★★★ / 🟨 ★★ / ⬜ ★",
        "",
        "장중 15% 진입 / 상한가 종목 요약",
        "",
        "상한가 진입 종목",
    ]
    lines.extend(format_detail_list(upper))
    lines.extend(["", "장중 15% 이상 진입 종목"])
    lines.extend(format_detail_list(fifteen))
    lines.extend(
        [
            "",
            "급등 종목 순위",
            *[
                f"{idx}. {r['title']}: {r['importance']} {r['news']}"
                for idx, r in enumerate(rows[:10], 1)
            ],
            "",
            "공통 키워드",
            "🟥 ★★★★ AI / 젠슨 황 / 엔비디아 / 퓨리오사AI / 국민성장펀드 / AI반도체",
            "🟧 ★★★ 피지컬AI / FC-BGA / AI 서버기판 / 에이전틱AI",
            "🟨 ★★ AI통번역 / AI플랫폼",
            "⬜ ★ 우선주 / 저시총 / 단기수급",
            "",
            "뉴스 일정",
            "- 2026-05-28: 국민성장펀드, 퓨리오사AI 약 8,000억 투자 승인",
            "- 2026-06-02~06-05: 젠슨 황, 컴퓨텍스 2026 참석 예정",
            "- 2026-06월 초: 젠슨 황 방한 가능성, LG·네이버·현대차 등 회동 기대",
            "",
            "추가 급등 가능 관찰 기업",
            "1. DSC인베스트먼트: 🟥 ★★★★ 퓨리오사AI 초기 투자",
            "2. 엑스페릭스: 🟧 ★★★ 퓨리오사AI 총판계약",
            "3. LB인베스트먼트: 🟧 ★★★ 퓨리오사AI 투자 VC",
            "4. 나우IB: 🟨 ★★ 퓨리오사AI 투자 관련주",
            "5. NAVER: 🟧 ★★★ 젠슨 황 회동·하이퍼클로바X",
            "6. 현대차: 🟧 ★★★ 피지컬AI·로봇 협력 기대",
            "7. 삼성SDS: 🟨 ★★ AI·클라우드",
        ]
    )
    return "\n".join(lines).strip()


def format_detail_list(rows: list[dict]) -> list[str]:
    if not rows:
        return ["없음"]
    lines = []
    for idx, row in enumerate(rows, 1):
        lines.extend(
            [
                f"{idx}. {row['title']}",
                f"구분: {row['status']} / 등락률: +{row['rate']:.2f}% / 시총: {row['market_cap']}",
                f"특징주: {row['feature']}",
                f"뉴스: {row['news']}",
                f"링크: {row['link']}",
                f"관련주: {row['related']}",
                "",
            ]
        )
    return lines


def version2(rows: list[dict]) -> str:
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    lines = [
        "2번. 상한가/급등주 요약 축약 버전",
        f"기준: {now} KST",
        "",
        "상한가/15% 이상 종목",
    ]
    for idx, row in enumerate(rows[:12], 1):
        lines.extend(
            [
                f"{idx}. {row['title']}: {row['status']} / +{row['rate']:.2f}%",
                f"특징주: {row['feature']}",
                f"뉴스: {row['news']}",
                f"링크: {row['link']}",
                f"관련주: {row['related']}",
                "",
            ]
        )
    lines.extend(
        [
            "핵심 키워드",
            "🟥 ★★★★ AI / 젠슨 황 / 엔비디아 / 퓨리오사AI / 국민성장펀드",
            "🟧 ★★★ 피지컬AI / AI 서버기판 / 에이전틱AI",
            "🟨 ★★ AI통번역 / AI플랫폼",
            "⬜ ★ 우선주 / 저시총 / 단기수급",
        ]
    )
    return "\n".join(lines).strip()


def split_message(text: str) -> list[str]:
    chunks = []
    remaining = text.strip()
    while remaining:
        if len(remaining) <= MAX_LEN:
            chunks.append(remaining)
            break
        cut = remaining.rfind("\n\n", 0, MAX_LEN)
        if cut < MAX_LEN // 2:
            cut = remaining.rfind("\n", 0, MAX_LEN)
        if cut < MAX_LEN // 2:
            cut = MAX_LEN
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    return chunks


def send(text: str) -> None:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    chunks = split_message(text)
    for idx, chunk in enumerate(chunks, 1):
        prefix = f"[{idx}/{len(chunks)}]\n" if len(chunks) > 1 else ""
        payload = json.dumps(
            {"chat_id": CHAT_ID, "text": prefix + chunk, "disable_web_page_preview": False}
        ).encode("utf-8")
        req = Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
        if not data.get("ok"):
            raise RuntimeError(data)
        time.sleep(0.8)


def main() -> None:
    if not CHAT_ID:
        raise RuntimeError("TELEGRAM_CHAT_ID or SANGHANGA_TELEGRAM_CHAT_ID is required.")

    rows = get_rows()
    seen = load_seen()
    enriched = [enrich(row, seen) for row in rows]

    if not enriched:
        send("상한가/급등주 리포트\n현재 장중 15% 이상 진입 종목이 없습니다.")
        save_seen([])
        return

    send(version1(enriched))
    send(version2(enriched))
    save_seen(enriched)


if __name__ == "__main__":
    main()
