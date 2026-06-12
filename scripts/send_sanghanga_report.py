import html
import json
import os
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET



KST = timezone(timedelta(hours=9))
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"].strip()
CHAT_ID = os.getenv("SANGHANGA_TELEGRAM_CHAT_ID", os.getenv("TELEGRAM_CHAT_ID", "")).strip()
STATE_PATH = Path(os.getenv("SANGHANGA_STATE_PATH", "reports/sanghanga_seen.json"))
MAX_LEN = 3800
ALLOW_FALLBACK_DATA = os.getenv("SANGHANGA_ALLOW_FALLBACK_DATA", "").lower() in {"1", "true", "yes", "y"}

HEADERS = {"User-Agent": "Mozilla/5.0"}

THEME_RULES = [
    {
        "keys": ("퓨리오사", "NPU", "AI반도체"),
        "line": "🟥 ★★★★ 퓨리오사AI / NPU / AI반도체 / VC투자",
        "query": "퓨리오사AI 투자 AI반도체 일정",
    },
    {
        "keys": ("젠슨", "엔비디아", "피지컬AI"),
        "line": "🟥 ★★★★ 엔비디아 / 젠슨 황 / 피지컬AI / 로봇",
        "query": "엔비디아 젠슨 황 피지컬AI 일정",
    },
    {
        "keys": ("AI", "인공지능", "에이전틱", "통번역", "AI플랫폼"),
        "line": "🟧 ★★★ AI / 에이전틱AI / AI플랫폼 / AI통번역",
        "query": "AI 에이전틱AI 인공지능 일정",
    },
    {
        "keys": ("반도체", "HBM", "기판", "FC-BGA"),
        "line": "🟧 ★★★ 반도체 / HBM / FC-BGA / AI서버기판",
        "query": "반도체 HBM AI서버기판 일정",
    },
    {
        "keys": ("로봇", "자율주행", "휴머노이드"),
        "line": "🟨 ★★ 로봇 / 자율주행 / 휴머노이드",
        "query": "로봇 휴머노이드 자율주행 일정",
    },
    {
        "keys": ("우선주", "품절주", "저시총", "단기 수급"),
        "line": "⬜ ★ 우선주 / 품절주 / 저시총 / 단기수급",
        "query": "우선주 품절주 급등 일정",
    },
    {
        "keys": ("2차전지", "배터리", "리튬"),
        "line": "🟨 ★★ 2차전지 / 배터리 / 리튬",
        "query": "2차전지 배터리 리튬 일정",
    },
    {
        "keys": ("바이오", "제약", "임상"),
        "line": "🟨 ★★ 바이오 / 제약 / 임상",
        "query": "바이오 제약 임상 일정",
    },
]

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


def shorten(value: str, limit: int = 64) -> str:
    value = clean_text(value)
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


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


def fetch_stock_news(name: str) -> dict:
    compact_name = re.sub(r"\s+", "", name)

    for query_text in (f"{name} 특징주", f"{name} 주가 급등"):
        query = quote(query_text)
        url = f"https://search.naver.com/search.naver?where=news&query={query}"

        try:
            text = http_get_text(url, encoding="utf-8")
        except Exception:
            continue

        matches = re.findall(
            r'<a[^>]+class="news_tit"[^>]+href="([^"]+)"[^>]+title="([^"]+)"',
            text,
            flags=re.S,
        )
        if not matches:
            matches = [
                (link, clean_text(title))
                for link, title in re.findall(
                    r'<a[^>]+href="([^"]+)"[^>]*>\s*<span[^>]+sds-comps-text-type-headline1[^>]*>(.*?)</span>',
                    text,
                    flags=re.S,
                )
            ]

        for link, title in matches:
            title = clean_text(title)
            compact_title = re.sub(r"\s+", "", title)
            if compact_name not in compact_title:
                continue
            news = normalize_news_title(title)
            feature = make_feature_from_title(name, news)
            return {
                "feature": feature,
                "news": shorten(news, 72),
                "link": html.unescape(link),
                "related": infer_related_from_title(news),
            }

    return {}


def normalize_news_title(title: str) -> str:
    title = clean_text(title)
    title = re.sub(r"\[\s*[^]]*특징주[^]]*\]\s*", "", title)
    title = re.sub(r"\s+([,，])", r"\1", title)
    title = re.sub(r"\s+", " ", title)
    return title.strip(" -·|")


def make_feature_from_title(name: str, title: str) -> str:
    feature = normalize_news_title(title)
    feature = re.sub(rf"^{re.escape(name)}\s*[,，]?\s*", "", feature)
    feature = feature.strip(" ,，-·|")
    return shorten(feature or title)


def infer_related_from_title(title: str) -> str:
    title = clean_text(title)
    theme_map = [
        (("퓨리오사", "NPU", "AI반도체"), "TS인베스트먼트, DSC인베스트먼트, LB인베스트먼트, 나우IB, 포바이포, 엑스페릭스"),
        (("젠슨", "엔비디아", "피지컬AI"), "LG전자, LG씨엔에스, LG이노텍, NAVER, 현대차, 현대모비스"),
        (("AI", "인공지능", "에이전틱"), "오브젠, 플리토, 삼성SDS, NAVER, LG씨엔에스"),
        (("반도체", "HBM", "기판", "FC-BGA"), "삼성전자, SK하이닉스, 삼성전기, LG이노텍, 한미반도체"),
        (("로봇", "자율주행"), "현대차, 현대모비스, 로보티즈, 로보스타, LG전자"),
        (("우선주", "품절주"), "우선주 테마, 저유동성 종목"),
        (("2차전지", "배터리", "리튬"), "LG에너지솔루션, 에코프로, 포스코퓨처엠, 금양"),
        (("바이오", "제약", "임상"), "바이오·제약주"),
    ]
    for keys, related in theme_map:
        if any(key in title for key in keys):
            return related
    return "동일 테마/업종 확인 필요"


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
        if ALLOW_FALLBACK_DATA:
            print(f"[WARN] Naver rise fetch failed, fallback used: {exc}")
            rows = FALLBACK_ROWS[:]
        else:
            print(f"[WARN] Naver rise fetch failed, no stale fallback sent: {exc}")
            rows = []

    rows.sort(key=lambda row: row["rate"], reverse=True)
    return rows[:20]


def enrich(row: dict, seen: set[str]) -> dict:
    meta = fetch_stock_news(row["name"])
    if not meta and ALLOW_FALLBACK_DATA:
        meta = NEWS_MAP.get(row["name"], {})
    if not meta:
        meta = {}
    title = row["name"] + (" [신규진입]" if row["code"] not in seen else "")
    return {
        **row,
        "title": title,
        "status": "상한가" if row["rate"] >= 29.5 else "장중 15% 이상",
        "news": meta.get("news", f"{row['name']} 장중 15% 이상 급등"),
        "feature": meta.get("feature", f"{row['name']} 장중 15% 이상 급등"),
        "link": meta.get("link", f"https://finance.naver.com/item/main.naver?code={row['code']}"),
        "related": meta.get("related", "동일 테마/업종 확인 필요"),
        "importance": meta.get("importance", infer_importance(row, meta)),
    }


def infer_importance(row: dict, meta: dict) -> str:
    text = " ".join([row.get("name", ""), meta.get("news", ""), meta.get("feature", ""), meta.get("related", "")])
    if row.get("rate", 0) >= 29.5 and any(key in text for key in ("AI", "반도체", "엔비디아", "퓨리오사", "로봇", "바이오")):
        return "🟥 ★★★★"
    if row.get("rate", 0) >= 29.5:
        return "🟧 ★★★"
    if any(key in text for key in ("AI", "반도체", "엔비디아", "퓨리오사", "2차전지", "바이오")):
        return "🟧 ★★★"
    if row.get("rate", 0) >= 20:
        return "🟨 ★★"
    return "⬜ ★"


def row_theme_text(row: dict) -> str:
    return " ".join(
        clean_text(row.get(key, ""))
        for key in ("title", "name", "news", "feature", "related")
    )


def active_theme_rules(rows: list[dict]) -> list[dict]:
    scored = []
    for rule in THEME_RULES:
        score = 0
        for row in rows:
            text = row_theme_text(row)
            if any(key in text for key in rule["keys"]):
                score += 1
        if score:
            scored.append((score, rule))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [rule for _, rule in scored]


def build_common_keyword_lines(rows: list[dict]) -> list[str]:
    rules = active_theme_rules(rows)
    if rules:
        return [rule["line"] for rule in rules[:4]]

    keywords = []
    for row in rows[:8]:
        words = re.findall(r"[가-힣A-Za-z0-9+-]{2,}", row_theme_text(row))
        for word in words:
            if word in {"상한가", "급등", "특징주", "관련주", "기대", "종목", "진입"}:
                continue
            if word not in keywords:
                keywords.append(word)
            if len(keywords) >= 8:
                break
        if len(keywords) >= 8:
            break
    return ["🟨 ★★ " + " / ".join(keywords[:8])] if keywords else ["- 최신 급등 테마 확인 필요"]


def fetch_google_news(query: str, limit: int = 3) -> list[dict]:
    url = f"https://news.google.com/rss/search?q={quote(query)}&hl=ko&gl=KR&ceid=KR:ko"
    try:
        text = http_get_text(url, encoding="utf-8")
        root = ET.fromstring(text)
    except Exception:
        return []

    items = []
    for item in root.findall(".//item"):
        title = clean_text(item.findtext("title", ""))
        link = clean_text(item.findtext("link", ""))
        pub_date = clean_text(item.findtext("pubDate", ""))
        if not title:
            continue
        date_text = format_rss_date(pub_date)
        items.append({"date": date_text, "title": shorten(title, 74), "link": link})
        if len(items) >= limit:
            break
    return items


def format_rss_date(pub_date: str) -> str:
    if not pub_date:
        return datetime.now(KST).strftime("%Y-%m-%d")
    try:
        dt = datetime.strptime(pub_date, "%a, %d %b %Y %H:%M:%S %Z")
        return dt.replace(tzinfo=timezone.utc).astimezone(KST).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now(KST).strftime("%Y-%m-%d")


def build_news_schedule_lines(rows: list[dict]) -> list[str]:
    rules = active_theme_rules(rows)[:3]
    queries = [rule["query"] for rule in rules]
    if not queries:
        queries = [f"{row['name']} 일정 뉴스" for row in rows[:3]]

    result = []
    seen = set()
    for query in queries:
        for item in fetch_google_news(query, limit=2):
            if item["title"] in seen:
                continue
            seen.add(item["title"])
            suffix = f" / {item['link']}" if item.get("link") else ""
            result.append(f"- {item['date']}: {item['title']}{suffix}")
            if len(result) >= 4:
                return result
        time.sleep(0.1)

    return result or ["- 최신 일정성 뉴스 자동 수집 실패: 장중 주요 뉴스 수동 확인 필요"]


def split_related_names(value: str) -> list[str]:
    names = []
    for part in re.split(r"[,/·]", clean_text(value)):
        name = part.strip()
        if not name or name in {"관련주", "테마", "동일 테마", "업종 확인 필요", "확인 필요"}:
            continue
        if len(name) > 18:
            continue
        if name not in names:
            names.append(name)
    return names


def build_watchlist_lines(rows: list[dict], limit: int = 7) -> list[str]:
    current_names = {row["name"] for row in rows}
    candidates: list[dict] = []
    seen = set()

    for row in rows:
        for name in split_related_names(row.get("related", "")):
            if name in current_names or name in seen:
                continue
            seen.add(name)
            candidates.append(
                {
                    "name": name,
                    "importance": row.get("importance", "🟨 ★★"),
                    "reason": shorten(f"{row['name']} 급등 테마 연동: {row.get('feature', row.get('news', ''))}", 54),
                }
            )
            if len(candidates) >= limit:
                break
        if len(candidates) >= limit:
            break

    if not candidates:
        return ["- 당일 급등 종목의 관련주 자동 추출 실패: 관련 테마 수동 확인 필요"]

    return [
        f"{idx}. {item['name']}: {item['importance']} {item['reason']}"
        for idx, item in enumerate(candidates, 1)
    ]


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
            *build_common_keyword_lines(rows),
            "",
            "뉴스 일정",
            *build_news_schedule_lines(rows),
            "",
            "추가 급등 가능 관찰 기업",
            *build_watchlist_lines(rows),
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
            *build_common_keyword_lines(rows),
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
