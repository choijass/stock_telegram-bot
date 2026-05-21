# Converted from Google Colab notebook
# Source notebook: 4.주식트랜드_국내_분석_FULL_v3(확정)

# %% [code] cell 1
# =========================================================
# KOREA STOCK AI THEME SYSTEM - UPGRADE PATCH
# 목적:
# 1) 기존 코드에 시장대비 RS20/RS60 추가
# 2) 종목 랭킹 안정화
# 3) Google Sheets 저장 안정화
# 4) one_page_summary 가독성 개선
# 5) 종가 매수 후보 점수 보강
#
# 사용법:
# - 이 파일의 함수들을 기존 코드 하단에 추가하거나,
# - 동일 이름 함수는 기존 함수와 교체해서 사용하세요.
# - main() 은 기존 파이프라인 함수명이 살아있다는 가정하에 동작합니다.
# =========================================================

import math
import time
import statistics
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests

try:
    import gspread
except Exception:
    gspread = None

KST = ZoneInfo("Asia/Seoul")

GSHEET_NAME = "Korea_Stock_AI_Theme_System_Full"
KOSPI_BENCHMARK = "^KS11"
KOSDAQ_BENCHMARK = "^KQ11"
REQUEST_TIMEOUT = 20
REQUEST_SLEEP = 0.12
MAX_RETRIES = 3
MAX_SHEET_ROWS_PER_TAB = 3000
MAX_SHEET_COLS = 60
HEADERS = {"User-Agent": "Mozilla/5.0"}
SYMBOL_FALLBACKS = {}

NEWS_FEEDS = [
    "https://news.google.com/rss/search?q=AI+semiconductor+OR+HBM+OR+datacenter+OR+GPU&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=robot+OR+factory+automation+OR+humanoid&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=cyber+attack+OR+ransomware+OR+security+breach&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=Iran+OR+oil+OR+Hormuz+OR+Middle+East+OR+LNG&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=defense+OR+missile+OR+drone+OR+war+OR+satellite&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=nuclear+OR+SMR+OR+reactor+OR+uranium&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=power+grid+OR+transformer+OR+HVDC+OR+substation&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=battery+OR+EV+OR+cathode+OR+anode+OR+lithium&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=shipbuilding+OR+LNG+carrier+OR+shipping+OR+container+freight&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=biotech+OR+ADC+OR+CDMO+OR+gene+therapy+OR+FDA&hl=en-US&gl=US&ceid=US:en",
]

NEWS_SECTOR_MAP = {
    "AI반도체": ["ai", "gpu", "hbm", "semiconductor", "datacenter", "server", "memory", "chip"],
    "반도체소부장": ["semiconductor equipment", "wafer", "etch", "deposition", "packaging", "osat"],
    "로봇": ["robot", "automation", "humanoid", "factory automation", "cobot"],
    "보안": ["cyber", "ransomware", "breach", "hack", "malware", "security"],
    "방산": ["defense", "missile", "drone", "war", "artillery", "military"],
    "우주항공/UAM": ["satellite", "space", "launch", "uam", "aerospace", "air mobility"],
    "정유/LNG": ["oil", "crude", "iran", "hormuz", "lng", "gas", "middle east"],
    "원전": ["nuclear", "smr", "reactor", "uranium"],
    "전력기기": ["power grid", "transformer", "hvdc", "substation", "power demand", "electricity"],
    "2차전지": ["battery", "ev", "cathode", "anode", "lithium", "recycling", "separator"],
    "조선": ["shipbuilding", "lng carrier", "vessel", "shipyard"],
    "해운": ["shipping", "container freight", "freight", "tanker", "bulk carrier"],
    "바이오": ["biotech", "adc", "cdmo", "gene therapy", "fda", "biosimilar", "clinical"],
    "자동차": ["ev", "autonomous", "vehicle", "mobility", "car maker"],
    "인터넷": ["platform", "e-commerce", "search", "cloud", "digital ads"],
    "게임/엔터": ["game", "gaming", "music", "streaming", "content", "entertainment"],
    "철강/소재": ["steel", "nickel", "copper", "aluminum", "rare earth"],
    "화학": ["petrochemical", "resin", "polymer", "chemical"],
    "건설/건자재": ["construction", "cement", "housing", "infra"],
    "금융": ["bank", "insurance", "brokerage", "asset management"],
    "유통/소비재": ["retail", "consumer", "beauty", "cosmetics", "duty free"],
    "통신": ["telecom", "5g", "network"],
    "여행/레저": ["travel", "airline", "hotel", "casino", "resort"],
    "음식료": ["food", "beverage", "ramen", "snack", "drink"],
}

SECTORS = {
    "AI반도체": [("삼성전자", "005930.KS"), ("SK하이닉스", "000660.KS"), ("한미반도체", "042700.KQ"), ("이수페타시스", "007660.KS"), ("리노공업", "058470.KQ"), ("DB하이텍", "000990.KS")],
    "반도체소부장": [("원익IPS", "240810.KQ"), ("주성엔지니어링", "036930.KQ"), ("피에스케이홀딩스", "031980.KQ"), ("동진쎄미켐", "005290.KQ"), ("솔브레인", "357780.KQ"), ("ISC", "095340.KQ")],
    "2차전지": [("LG에너지솔루션", "373220.KS"), ("삼성SDI", "006400.KS"), ("에코프로비엠", "247540.KQ"), ("에코프로", "086520.KQ"), ("포스코퓨처엠", "003670.KS"), ("엘앤에프", "066970.KQ")],
    "바이오": [("삼성바이오로직스", "207940.KS"), ("셀트리온", "068270.KS"), ("SK바이오팜", "326030.KS"), ("알테오젠", "196170.KQ"), ("리가켐바이오", "141080.KQ"), ("펩트론", "087010.KQ")],
    "보안": [("안랩", "053800.KQ"), ("지니언스", "263860.KQ"), ("모니터랩", "434480.KQ"), ("한국정보인증", "053300.KQ"), ("슈프리마", "236200.KQ"), ("아톤", "158430.KQ")],
    "로봇": [("레인보우로보틱스", "277810.KQ"), ("두산로보틱스", "454910.KS"), ("로보스타", "090360.KQ"), ("유일로보틱스", "388720.KQ"), ("뉴로메카", "348340.KQ"), ("티로보틱스", "117730.KQ")],
    "방산": [("한화에어로스페이스", "012450.KS"), ("LIG넥스원", "079550.KS"), ("현대로템", "064350.KS"), ("한국항공우주", "047810.KS"), ("풍산", "103140.KS"), ("한화시스템", "272210.KS")],
    "우주항공/UAM": [("한국항공우주", "047810.KS"), ("한화에어로스페이스", "012450.KS"), ("켄코아에어로스페이스", "274090.KQ"), ("인텔리안테크", "189300.KQ"), ("쎄트렉아이", "099320.KQ"), ("제노코", "361390.KQ")],
    "원전": [("두산에너빌리티", "034020.KS"), ("한전기술", "052690.KS"), ("한전산업", "130660.KS"), ("비에이치아이", "083650.KQ"), ("우리기술", "032820.KQ"), ("오르비텍", "046120.KQ")],
    "전력기기": [("HD현대일렉트릭", "267260.KS"), ("LS ELECTRIC", "010120.KS"), ("효성중공업", "298040.KS"), ("대한전선", "001440.KS"), ("가온전선", "000500.KS"), ("제룡전기", "033100.KQ")],
    "조선": [("HD한국조선해양", "009540.KS"), ("한화오션", "042660.KS"), ("삼성중공업", "010140.KS"), ("HD현대미포", "010620.KS"), ("HJ중공업", "097230.KS"), ("세진중공업", "075580.KQ")],
    "해운": [("HMM", "011200.KS"), ("팬오션", "028670.KS"), ("대한해운", "005880.KS"), ("흥아해운", "003280.KS"), ("KSS해운", "044450.KS"), ("STX그린로지스", "465770.KS")],
    "정유/LNG": [("S-Oil", "010950.KS"), ("SK이노베이션", "096770.KS"), ("포스코인터내셔널", "047050.KS"), ("한국가스공사", "036460.KS"), ("흥구석유", "024060.KQ"), ("중앙에너비스", "000440.KQ")],
    "철강/소재": [("POSCO홀딩스", "005490.KS"), ("현대제철", "004020.KS"), ("고려아연", "010130.KS"), ("풍산", "103140.KS"), ("TCC스틸", "002710.KS"), ("세아제강", "306200.KS")],
    "화학": [("LG화학", "051910.KS"), ("금호석유", "011780.KS"), ("롯데케미칼", "011170.KS"), ("한화솔루션", "009830.KS"), ("대한유화", "006650.KS"), ("코오롱인더", "120110.KS")],
    "자동차": [("현대차", "005380.KS"), ("기아", "000270.KS"), ("현대모비스", "012330.KS"), ("HL만도", "204320.KS"), ("에스엘", "005850.KS"), ("화신", "010690.KS")],
    "인터넷": [("NAVER", "035420.KS"), ("카카오", "035720.KS"), ("더존비즈온", "012510.KS"), ("아프리카TV", "067160.KQ"), ("카페24", "042000.KQ"), ("플래티어", "367000.KQ")],
    "게임/엔터": [("크래프톤", "259960.KS"), ("엔씨소프트", "036570.KS"), ("넷마블", "251270.KS"), ("하이브", "352820.KS"), ("JYP Ent.", "035900.KQ"), ("에스엠", "041510.KQ")],
    "건설/건자재": [("현대건설", "000720.KS"), ("DL이앤씨", "375500.KS"), ("GS건설", "006360.KS"), ("삼성물산", "028260.KS"), ("KCC", "002380.KS"), ("한일시멘트", "300720.KS")],
    "금융": [("KB금융", "105560.KS"), ("신한지주", "055550.KS"), ("하나금융지주", "086790.KS"), ("우리금융지주", "316140.KS"), ("메리츠금융지주", "138040.KS"), ("한국금융지주", "071050.KS")],
    "통신": [("SK텔레콤", "017670.KS"), ("KT", "030200.KS"), ("LG유플러스", "032640.KS"), ("쏠리드", "050890.KQ"), ("RFHIC", "218410.KQ"), ("케이엠더블유", "032500.KQ")],
    "유통/소비재": [("호텔신라", "008770.KS"), ("신세계", "004170.KS"), ("이마트", "139480.KS"), ("현대백화점", "069960.KS"), ("아모레퍼시픽", "090430.KS"), ("한국콜마", "161890.KS")],
    "여행/레저": [("대한항공", "003490.KS"), ("아시아나항공", "020560.KS"), ("하나투어", "039130.KS"), ("모두투어", "080160.KQ"), ("파라다이스", "034230.KQ"), ("롯데관광개발", "032350.KS")],
    "음식료": [("삼양식품", "003230.KS"), ("농심", "004370.KS"), ("오리온", "271560.KS"), ("CJ제일제당", "097950.KS"), ("롯데웰푸드", "280360.KS"), ("하이트진로", "000080.KS")],
}

ETF_SECTORS = {
    "반도체": [("KODEX 반도체", "091160.KS"), ("TIGER 반도체", "091230.KS"), ("KODEX Fn시스템반도체", "395160.KS")],
    "2차전지": [("KODEX 2차전지산업", "305720.KS"), ("TIGER 2차전지테마", "305540.KS")],
    "AI/테크": [("KODEX AI전력핵심설비", "487230.KS"), ("KODEX AI반도체핵심장비", "483240.KS")],
    "방산": [("PLUS K방산", "449450.KS"), ("SOL K방산", "494340.KS")],
    "원전": [("HANARO 원자력iSelect", "434730.KS"), ("ACE 원자력테마딥서치", "433500.KS")],
    "조선": [("SOL 조선TOP3플러스", "466920.KS")],
    "전력기기": [("PLUS 글로벌원자력밸류체인", "495220.KS")],
    "바이오": [("TIGER 바이오TOP10", "364970.KS"), ("KODEX 바이오", "244580.KS")],
    "인터넷": [("KODEX K-메타버스액티브", "401470.KS")],
    "금융": [("KODEX 은행", "091170.KS"), ("TIGER 은행고배당플러스TOP10", "466940.KS")],
}

SESSION = None
FETCH_LOGS = []
LATEST_CACHE = {}
HISTORY_CACHE = {}


def build_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def init_runtime():
    global SESSION
    if SESSION is None:
        SESSION = build_session()


def clean_text(x):
    return " ".join(str(x or "").split())


def safe_num(x, default=None):
    try:
        if x is None:
            return default
        if isinstance(x, float) and math.isnan(x):
            return default
        return float(x)
    except Exception:
        return default


def pct_change(curr, prev):
    if curr is None or prev in (None, 0):
        return None
    return (curr / prev - 1.0) * 100.0


def rolling_mean(values, window):
    out = []
    for i in range(len(values)):
        if i + 1 < window:
            out.append(None)
        else:
            chunk = [v for v in values[i - window + 1:i + 1] if v is not None]
            out.append(sum(chunk) / len(chunk) if chunk else None)
    return out


def rank_desc(values):
    uniq = sorted({v for v in values if v is not None}, reverse=True)
    mapping = {v: i + 1 for i, v in enumerate(uniq)}
    return [mapping.get(v) if v is not None else None for v in values]


def clip(x, lo=0, hi=100):
    if x is None:
        return 0
    return max(lo, min(hi, x))


def records_to_sheet_rows(records):
    if not records:
        return [["데이터 없음"]]
    headers = list(records[0].keys())
    rows = [headers]
    for r in records:
        rows.append([r.get(h, "") for h in headers])
    return rows


def safe_sheet_title(title, max_len=90):
    title = clean_text(title)
    for bad in ['[', ']', '*', '?', '/', '\\']:
        title = title.replace(bad, "_")
    return title[:max_len]


def add_fetch_log(kind, name, symbol, status, message=""):
    FETCH_LOGS.append({
        "kind": kind,
        "name": name,
        "symbol": symbol,
        "status": status,
        "message": clean_text(message),
        "timestamp_kst": datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"),
    })


def http_get(url, params=None, timeout=REQUEST_TIMEOUT):
    init_runtime()
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = SESSION.get(url, params=params, timeout=timeout)
            if r.status_code == 404:
                return r
            r.raise_for_status()
            return r
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES:
                time.sleep(0.7 * attempt)
    raise last_err


def flatten_sector_members():
    rows = []
    for sector, members in SECTORS.items():
        for name, symbol in members:
            rows.append({"sector": sector, "name": name, "ticker": symbol, "group": "stock"})
    for sector, members in ETF_SECTORS.items():
        for name, symbol in members:
            rows.append({"sector": sector, "name": name, "ticker": symbol, "group": "etf"})
    return rows


def get_news():
    rows = []
    for url in NEWS_FEEDS:
        try:
            r = http_get(url, timeout=15)
            root = ET.fromstring(r.content)
            for item in root.findall(".//item")[:30]:
                rows.append({
                    "title": clean_text(item.findtext("title", "")),
                    "description": clean_text(item.findtext("description", "")),
                    "link": clean_text(item.findtext("link", "")),
                    "feed_url": url,
                })
            time.sleep(REQUEST_SLEEP)
        except Exception as e:
            add_fetch_log("news", "feed", url, "error", str(e))

    uniq = []
    seen = set()
    for r in rows:
        key = (r["title"], r["link"])
        if key not in seen:
            seen.add(key)
            uniq.append(r)
    return uniq


def map_news_to_sector(news_rows):
    tagged = []
    for row in news_rows:
        text = f'{row["title"]} {row["description"]}'.lower()
        for sector, keywords in NEWS_SECTOR_MAP.items():
            hits = [kw for kw in keywords if kw.lower() in text]
            if hits:
                tagged.append({
                    "title": row["title"],
                    "description": row["description"],
                    "link": row["link"],
                    "sector": sector,
                    "matched_keywords": ", ".join(sorted(set(hits))),
                })
    out = []
    seen = set()
    for r in tagged:
        key = (r["title"], r["sector"])
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def resolve_symbol(symbol):
    if symbol in SYMBOL_FALLBACKS:
        return SYMBOL_FALLBACKS[symbol]
    return symbol


def fetch_yahoo_chart(symbol, name="", kind="stock", range_str="6mo", interval="1d"):
    resolved = resolve_symbol(symbol)
    if resolved is None:
        add_fetch_log(kind, name, symbol, "skip", "fallback 없음")
        return []

    cache_key = (resolved, range_str, interval)
    if cache_key in HISTORY_CACHE:
        return HISTORY_CACHE[cache_key]

    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{resolved}"
    params = {
        "range": range_str,
        "interval": interval,
        "includePrePost": "false",
        "events": "div,splits",
    }

    try:
        r = http_get(url, params=params, timeout=20)
        if r.status_code == 404:
            add_fetch_log(kind, name, resolved, "404", "Yahoo 미지원 심볼")
            return []

        data = r.json()
        result = data.get("chart", {}).get("result")
        error = data.get("chart", {}).get("error")
        if error:
            add_fetch_log(kind, name, resolved, "chart_error", str(error))
            return []
        if not result:
            add_fetch_log(kind, name, resolved, "empty", "데이터 없음")
            return []

        res = result[0]
        timestamps = res.get("timestamp", [])
        quote = res.get("indicators", {}).get("quote", [{}])[0]
        opens = quote.get("open", [])
        highs = quote.get("high", [])
        lows = quote.get("low", [])
        closes = quote.get("close", [])
        volumes = quote.get("volume", [])

        rows = []
        for i, ts in enumerate(timestamps):
            close = safe_num(closes[i] if i < len(closes) else None)
            open_ = safe_num(opens[i] if i < len(opens) else None)
            high = safe_num(highs[i] if i < len(highs) else None)
            low = safe_num(lows[i] if i < len(lows) else None)
            volume = safe_num(volumes[i] if i < len(volumes) else None, 0)
            if close is None:
                continue
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(KST)
            rows.append({
                "date": dt.strftime("%Y-%m-%d"),
                "open": open_,
                "high": high,
                "low": low,
                "close": close,
                "volume": volume or 0,
                "value": close * (volume or 0),
            })
        HISTORY_CACHE[cache_key] = rows
        add_fetch_log(kind, name, resolved, "ok", f"rows={len(rows)}")
        time.sleep(REQUEST_SLEEP)
        return rows
    except Exception as e:
        add_fetch_log(kind, name, resolved, "error", str(e))
        return []


def enrich_price_rows(rows):
    if not rows:
        return rows

    closes = [r["close"] for r in rows]
    values = [r["value"] / 100_000_000 for r in rows]

    ma5 = rolling_mean(closes, 5)
    ma10 = rolling_mean(closes, 10)
    ma20 = rolling_mean(closes, 20)
    ma60 = rolling_mean(closes, 60)
    value_ma20 = rolling_mean(values, 20)

    for i, r in enumerate(rows):
        prev_close = closes[i - 1] if i >= 1 else None
        prev5 = closes[i - 5] if i >= 5 else None
        prev10 = closes[i - 10] if i >= 10 else None
        prev20 = closes[i - 20] if i >= 20 else None
        prev60 = closes[i - 60] if i >= 60 else None

        r["ret1"] = pct_change(r["close"], prev_close)
        r["ret5"] = pct_change(r["close"], prev5)
        r["ret10"] = pct_change(r["close"], prev10)
        r["ret20"] = pct_change(r["close"], prev20)
        r["ret60"] = pct_change(r["close"], prev60)

        r["value_eok"] = values[i]
        r["value_ma20"] = value_ma20[i]
        r["value_ratio20"] = (values[i] / value_ma20[i]) if value_ma20[i] not in (None, 0) else None

        r["ma5"] = ma5[i]
        r["ma10"] = ma10[i]
        r["ma20"] = ma20[i]
        r["ma60"] = ma60[i]

        r["ma5_chg"] = pct_change(ma5[i], ma5[i - 1] if i >= 1 else None)
        r["ma10_chg"] = pct_change(ma10[i], ma10[i - 1] if i >= 1 else None)
        r["ma20_chg"] = pct_change(ma20[i], ma20[i - 1] if i >= 1 else None)
        r["ma60_chg"] = pct_change(ma60[i], ma60[i - 1] if i >= 1 else None)

        high_20 = [x for x in closes[max(0, i - 19):i + 1] if x is not None]
        high_60 = [x for x in closes[max(0, i - 59):i + 1] if x is not None]
        r["is_new_high_20"] = 1 if high_20 and r["close"] >= max(high_20) else 0
        r["is_new_high_60"] = 1 if high_60 and r["close"] >= max(high_60) else 0
        r["is_new_high"] = r["is_new_high_20"]
    return rows


def get_symbol_latest(symbol, name="", kind="stock"):
    cache_key = (symbol, name, kind)
    if cache_key in LATEST_CACHE:
        return LATEST_CACHE[cache_key]
    rows = enrich_price_rows(fetch_yahoo_chart(symbol, name=name, kind=kind))
    latest = rows[-1] if rows else None
    LATEST_CACHE[cache_key] = latest
    return latest


def get_benchmark_map():
    kospi = get_symbol_latest(KOSPI_BENCHMARK, name="KOSPI", kind="benchmark") or {}
    kosdaq = get_symbol_latest(KOSDAQ_BENCHMARK, name="KOSDAQ", kind="benchmark") or {}
    return {
        "KOSPI": {"ret20": safe_num(kospi.get("ret20"), 0) or 0, "ret60": safe_num(kospi.get("ret60"), 0) or 0},
        "KOSDAQ": {"ret20": safe_num(kosdaq.get("ret20"), 0) or 0, "ret60": safe_num(kosdaq.get("ret60"), 0) or 0},
    }


def market_key_from_symbol(symbol):
    return "KOSDAQ" if str(symbol).endswith(".KQ") else "KOSPI"


def build_sector_raw():
    rows = []
    benchmark_map = get_benchmark_map()
    for sector, stocks in SECTORS.items():
        for name, symbol in stocks:
            last = get_symbol_latest(symbol, name=name, kind="stock")
            if not last:
                continue
            mkt = market_key_from_symbol(symbol)
            bm20 = benchmark_map[mkt]["ret20"]
            bm60 = benchmark_map[mkt]["ret60"]
            ret20 = last.get("ret20") or 0
            ret60 = last.get("ret60") or 0
            rows.append({
                "date": last["date"],
                "sector": sector,
                "name": name,
                "ticker": symbol,
                "market": mkt,
                "ret1": last.get("ret1") or 0,
                "ret5": last.get("ret5") or 0,
                "ret20": ret20,
                "ret60": ret60,
                "rs20": round(ret20 - bm20, 2),
                "rs60": round(ret60 - bm60, 2),
                "value_eok": last.get("value_eok") or 0,
                "value_ratio20": last.get("value_ratio20") or 0,
                "is_new_high": last.get("is_new_high") or 0,
                "is_new_high_60": last.get("is_new_high_60") or 0,
            })
    return rows


def summarize_sector(sector_raw, news_tagged):
    if not sector_raw:
        return []
    news_count = {}
    for r in news_tagged:
        news_count[r["sector"]] = news_count.get(r["sector"], 0) + 1
    grouped = {}
    for r in sector_raw:
        grouped.setdefault(r["sector"], []).append(r)
    out = []
    date_str = sector_raw[0]["date"] if sector_raw else ""
    for sector, items in grouped.items():
        mean_ret1 = statistics.mean([x["ret1"] for x in items]) if items else 0
        mean_ret5 = statistics.mean([x["ret5"] for x in items]) if items else 0
        mean_ret20 = statistics.mean([x["ret20"] for x in items]) if items else 0
        mean_rs20 = statistics.mean([x["rs20"] for x in items]) if items else 0
        mean_rs60 = statistics.mean([x["rs60"] for x in items]) if items else 0
        total_value = sum(x["value_eok"] for x in items)
        ratio_vals = [x["value_ratio20"] for x in items if x["value_ratio20"] is not None]
        value_ratio_avg = statistics.mean(ratio_vals) if ratio_vals else 0
        up_count = sum(1 for x in items if x["ret1"] > 0)
        stock_count = len(items)
        new_high_count = sum(x["is_new_high"] for x in items)
        new_high_60_count = sum(x["is_new_high_60"] for x in items)
        leader = sorted(items, key=lambda x: (x["rs20"], x["value_eok"], x["ret1"]), reverse=True)[0]
        out.append({
            "date": date_str,
            "sector": sector,
            "mean_ret1": round(mean_ret1, 2),
            "mean_ret5": round(mean_ret5, 2),
            "mean_ret20": round(mean_ret20, 2),
            "mean_rs20": round(mean_rs20, 2),
            "mean_rs60": round(mean_rs60, 2),
            "total_value_eok": round(total_value, 2),
            "value_ratio_avg": round(value_ratio_avg, 2),
            "up_count": up_count,
            "stock_count": stock_count,
            "up_ratio": round(up_count / stock_count, 4) if stock_count else 0,
            "new_high_count": new_high_count,
            "new_high_60_count": new_high_60_count,
            "leader": leader["name"],
            "leader_rs20": leader["rs20"],
            "leader_value_eok": round(leader["value_eok"], 2),
            "news_count": news_count.get(sector, 0),
        })
    return out


def add_boom_score(summary_rows):
    out = []
    for r in summary_rows:
        news_score = clip(r["news_count"] * 12)
        ret1_score = clip((r["mean_ret1"] + 5) * 10)
        ret20_score = clip((r["mean_ret20"] + 10) * 4)
        rs20_score = clip((r["mean_rs20"] + 10) * 4)
        value_score = clip(r["total_value_eok"] / 60)
        ratio_score = clip(r["value_ratio_avg"] * 28)
        breadth_score = clip(r["up_ratio"] * 100)
        high_score = clip((r["new_high_count"] / r["stock_count"]) * 100 if r["stock_count"] else 0)

        boom_score = round(
            news_score * 0.11 +
            ret1_score * 0.15 +
            ret20_score * 0.12 +
            rs20_score * 0.17 +
            value_score * 0.18 +
            ratio_score * 0.12 +
            breadth_score * 0.08 +
            high_score * 0.07,
            2
        )
        if boom_score >= 80:
            stage = "3차 폭발"
        elif boom_score >= 65:
            stage = "2차 확정"
        elif boom_score >= 50:
            stage = "1차 탐지"
        else:
            stage = "관찰"
        x = dict(r)
        x.update({
            "news_score": news_score,
            "ret1_score": ret1_score,
            "ret20_score": ret20_score,
            "rs20_score": rs20_score,
            "value_score": value_score,
            "ratio_score": ratio_score,
            "breadth_score": breadth_score,
            "high_score": high_score,
            "boom_score": boom_score,
            "stage": stage,
        })
        out.append(x)
    return sorted(out, key=lambda x: (x["boom_score"], x["mean_rs20"], x["total_value_eok"]), reverse=True)


def build_etf_raw():
    rows = []
    kospi_bm = get_benchmark_map()["KOSPI"]
    for sector, etfs in ETF_SECTORS.items():
        for name, symbol in etfs:
            last = get_symbol_latest(symbol, name=name, kind="etf")
            if not last:
                continue
            ret20 = last.get("ret20") or 0
            ret60 = last.get("ret60") or 0
            rows.append({
                "date": last["date"],
                "sector": sector,
                "etf_name": name,
                "ticker": symbol,
                "close": last["close"],
                "ret1": last.get("ret1") or 0,
                "ret5": last.get("ret5") or 0,
                "ret20": ret20,
                "ret60": ret60,
                "rs20": round(ret20 - kospi_bm["ret20"], 2),
                "rs60": round(ret60 - kospi_bm["ret60"], 2),
                "value_eok": last.get("value_eok") or 0,
                "value_ratio20": last.get("value_ratio20") or 0,
                "is_new_high": last.get("is_new_high") or 0,
            })
    return rows


def calculate_etf_rs_ranking(etf_raw):
    ranked = []
    sorted_rows = sorted(
        etf_raw,
        key=lambda x: (x.get("rs20", -999), x.get("ret20", -999), x.get("value_ratio20", -999)),
        reverse=True,
    )
    for i, r in enumerate(sorted_rows, 1):
        x = dict(r)
        x["rank"] = i
        ranked.append(x)
    return ranked


def summarize_etf_sector_ranking(etf_rs_rank):
    grouped = {}
    for r in etf_rs_rank:
        grouped.setdefault(r["sector"], []).append(r)
    rows = []
    for sector, items in grouped.items():
        top = sorted(items, key=lambda x: (x["rs20"], x["ret20"]), reverse=True)[0]
        rows.append({
            "sector": sector,
            "sector_rank": None,
            "top_etf": top["etf_name"],
            "top_etf_ticker": top["ticker"],
            "top_etf_rs20": top["rs20"],
            "top_etf_ret20": top["ret20"],
            "etf_count": len(items),
            "sector_rs20_avg": round(statistics.mean([x["rs20"] for x in items]), 2),
        })
    rows = sorted(rows, key=lambda x: (x["sector_rs20_avg"], x["top_etf_rs20"]), reverse=True)
    for i, r in enumerate(rows, 1):
        r["sector_rank"] = i
    return rows


def build_stock_rs_table():
    benchmark_map = get_benchmark_map()
    rows = []
    for sector, members in SECTORS.items():
        for name, symbol in members:
            last = get_symbol_latest(symbol, name=name, kind="stock")
            if not last:
                continue
            mkt = market_key_from_symbol(symbol)
            bm20 = benchmark_map[mkt]["ret20"]
            bm60 = benchmark_map[mkt]["ret60"]
            ret20 = last.get("ret20") or 0
            ret60 = last.get("ret60") or 0
            score = (
                (ret20 - bm20) * 0.55 +
                (ret60 - bm60) * 0.25 +
                (last.get("ret5") or 0) * 0.10 +
                min(last.get("value_ratio20") or 0, 5) * 3.0 +
                (last.get("is_new_high") or 0) * 4
            )
            rows.append({
                "sector": sector,
                "name": name,
                "ticker": symbol,
                "market": mkt,
                "ret1": round(last.get("ret1") or 0, 2),
                "ret5": round(last.get("ret5") or 0, 2),
                "ret20": round(ret20, 2),
                "ret60": round(ret60, 2),
                "rs20": round(ret20 - bm20, 2),
                "rs60": round(ret60 - bm60, 2),
                "value_eok": round(last.get("value_eok") or 0, 2),
                "value_ratio20": round(last.get("value_ratio20") or 0, 2),
                "is_new_high": last.get("is_new_high") or 0,
                "score": round(score, 2),
            })
    rows = sorted(rows, key=lambda x: (x["score"], x["rs20"], x["value_eok"]), reverse=True)
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def build_stock_recommendation(etf_sector_rank, stock_rs_rank, top_sector_n=7, top_per_sector=3):
    top_sectors = {r["sector"] for r in etf_sector_rank[:top_sector_n]}
    rows = []
    for sector in top_sectors:
        candidates = [x for x in stock_rs_rank if x["sector"] == sector]
        candidates = sorted(candidates, key=lambda x: (x["score"], x["rs20"], x["value_eok"]), reverse=True)[:top_per_sector]
        for rank_in_sector, r in enumerate(candidates, 1):
            x = dict(r)
            x["sector_pick_rank"] = rank_in_sector
            x["reason"] = "ETF상위섹터+RS상위"
            rows.append(x)
    return rows


def build_stock_snapshot():
    rows = []
    for sector, members in SECTORS.items():
        for name, symbol in members:
            last = get_symbol_latest(symbol, name=name, kind="stock")
            if not last:
                continue
            rows.append({
                "sector": sector,
                "name": name,
                "ticker": symbol,
                "ret1": round(last.get("ret1") or 0, 2),
                "ret5": round(last.get("ret5") or 0, 2),
                "ret20": round(last.get("ret20") or 0, 2),
                "value_eok": round(last.get("value_eok") or 0, 2),
                "value_ratio20": round(last.get("value_ratio20") or 0, 2),
                "is_new_high": last.get("is_new_high") or 0,
                "is_new_high_60": last.get("is_new_high_60") or 0,
            })
    return rows


def build_value_explosion_theme(stock_snapshot, news_tagged):
    news_count = {}
    for r in news_tagged:
        news_count[r["sector"]] = news_count.get(r["sector"], 0) + 1

    grouped = {}
    for r in stock_snapshot:
        grouped.setdefault(r["sector"], []).append(r)

    rows = []
    for sector, items in grouped.items():
        leader = sorted(items, key=lambda x: (x["value_ratio20"], x["ret1"], x["value_eok"]), reverse=True)[0]
        value_ratio_avg = statistics.mean([x["value_ratio20"] for x in items]) if items else 0
        mean_ret1 = statistics.mean([x["ret1"] for x in items]) if items else 0
        new_high_count = sum(x["is_new_high"] for x in items)
        score = round(
            clip(value_ratio_avg * 25) * 0.45 +
            clip((mean_ret1 + 5) * 10) * 0.20 +
            clip(news_count.get(sector, 0) * 12) * 0.15 +
            clip((new_high_count / len(items)) * 100 if items else 0) * 0.20,
            2
        )
        stage = "폭발" if score >= 70 else ("확산" if score >= 50 else "관찰")
        rows.append({
            "sector": sector,
            "leader": leader["name"],
            "leader_ret1": leader["ret1"],
            "leader_value_ratio20": leader["value_ratio20"],
            "value_ratio_avg": round(value_ratio_avg, 2),
            "mean_ret1": round(mean_ret1, 2),
            "news_count": news_count.get(sector, 0),
            "new_high_count": new_high_count,
            "value_theme_score": score,
            "theme_stage": stage,
        })
    return sorted(rows, key=lambda x: (x["value_theme_score"], x["leader_value_ratio20"]), reverse=True)


def build_day1_theme_stock_pick(stock_snapshot, value_theme, top_theme_n=6, top_stock_n=2):
    top_sectors = {r["sector"] for r in value_theme[:top_theme_n]}
    rows = []
    for sector in top_sectors:
        items = [x for x in stock_snapshot if x["sector"] == sector]
        items = sorted(items, key=lambda x: (x["value_ratio20"], x["ret1"], x["is_new_high"], x["value_eok"]), reverse=True)[:top_stock_n]
        for i, r in enumerate(items, 1):
            x = dict(r)
            x["pick_rank"] = i
            x["reason"] = "거래대금폭발 Day1"
            rows.append(x)
    return rows


def build_close_buy_etf_sector(etf_rs_rank, etf_sector_rank, value_theme):
    theme_score_map = {r["sector"]: r["value_theme_score"] for r in value_theme}
    rank_map = {r["sector"]: r["sector_rank"] for r in etf_sector_rank}
    rows = []
    for r in etf_rs_rank:
        sector_bonus = max(0, 15 - (rank_map.get(r["sector"], 99) or 99))
        value_bonus = min(theme_score_map.get(r["sector"], 0), 100) * 0.15
        score = round(
            clip((r["rs20"] + 10) * 4) * 0.38 +
            clip((r["ret5"] + 10) * 5) * 0.12 +
            clip(r["value_ratio20"] * 25) * 0.20 +
            sector_bonus * 2.0 +
            value_bonus +
            (6 if r["is_new_high"] else 0),
            2
        )
        action = "강관심" if score >= 75 else ("관심" if score >= 60 else "관찰")
        x = dict(r)
        x["close_buy_score"] = score
        x["action"] = action
        rows.append(x)
    return sorted(rows, key=lambda x: x["close_buy_score"], reverse=True)


def build_close_buy_candidates(stock_rs_rank, stock_snapshot, value_theme):
    snap_map = {x["ticker"]: x for x in stock_snapshot}
    theme_score_map = {r["sector"]: r["value_theme_score"] for r in value_theme}
    rows = []
    for r in stock_rs_rank:
        snap = snap_map.get(r["ticker"], {})
        value_ratio20 = snap.get("value_ratio20", r.get("value_ratio20", 0)) or 0
        score = round(
            clip((r["rs20"] + 10) * 4) * 0.34 +
            clip((r["rs60"] + 10) * 3) * 0.12 +
            clip((r["ret5"] + 10) * 5) * 0.12 +
            clip(value_ratio20 * 20) * 0.20 +
            min(theme_score_map.get(r["sector"], 0), 100) * 0.14 +
            (8 if r["is_new_high"] else 0),
            2
        )
        action = "강관심" if score >= 78 else ("관심" if score >= 63 else "관찰")
        x = dict(r)
        x["close_buy_score"] = score
        x["action"] = action
        rows.append(x)
    return sorted(rows, key=lambda x: (x["close_buy_score"], x["rs20"], x["value_eok"]), reverse=True)


def build_one_page_close_buy_summary(boom_score, etf_sector_rank, value_theme, close_stock_candidates, close_etf_candidates):
    rows = []
    for i, r in enumerate(boom_score[:8], 1):
        rows.append({
            "section": "BOOM_SCORE",
            "rank": i,
            "name": r["sector"],
            "score": r["boom_score"],
            "detail1": f'평균RS20:{r.get("mean_rs20", "")}',
            "detail2": f'리더:{r["leader"]}',
            "detail3": f'단계:{r["stage"]}',
        })
    for i, r in enumerate(etf_sector_rank[:8], 1):
        rows.append({
            "section": "ETF_SECTOR_RANK",
            "rank": i,
            "name": r["sector"],
            "score": r["sector_rs20_avg"],
            "detail1": f'대표ETF:{r["top_etf"]}',
            "detail2": f'RS20:{r["top_etf_rs20"]}',
            "detail3": f'섹터순위:{r["sector_rank"]}',
        })
    for i, r in enumerate(value_theme[:8], 1):
        rows.append({
            "section": "VALUE_THEME",
            "rank": i,
            "name": r["sector"],
            "score": r["value_theme_score"],
            "detail1": f'리더:{r["leader"]}',
            "detail2": f'리더등락:{r["leader_ret1"]}',
            "detail3": f'단계:{r["theme_stage"]}',
        })
    for i, r in enumerate(close_etf_candidates[:8], 1):
        rows.append({
            "section": "ETF_CLOSE_BUY",
            "rank": i,
            "name": r["etf_name"],
            "score": r["close_buy_score"],
            "detail1": f'섹터:{r["sector"]}',
            "detail2": f'RS20:{r["rs20"]}',
            "detail3": f'판정:{r["action"]}',
        })
    for i, r in enumerate(close_stock_candidates[:15], 1):
        rows.append({
            "section": "STOCK_CLOSE_BUY",
            "rank": i,
            "name": r["name"],
            "score": r["close_buy_score"],
            "detail1": f'섹터:{r["sector"]}',
            "detail2": f'RS20:{r["rs20"]}',
            "detail3": f'판정:{r["action"]}',
        })
    return rows


def trim_rows_for_sheet(records, max_rows=MAX_SHEET_ROWS_PER_TAB):
    if not records:
        return records
    return records[:max_rows]


def get_gspread_client_login():
    if gspread is None:
        print("[Google Sheets 스킵] gspread 미설치")
        return None
    try:
        import google.colab  # noqa
        from google.colab import auth
        from google.auth import default
        auth.authenticate_user()
        creds, _ = default()
        gc = gspread.authorize(creds)
        return gc
    except Exception as e:
        print(f"[Google Sheets 스킵] Colab 인증 불가 / {e}")
        return None


def ensure_worksheet(sh, title, rows=2000, cols=50):
    title = safe_sheet_title(title)
    existing = {ws.title: ws for ws in sh.worksheets()}
    ws = existing.get(title)
    if ws is None:
        ws = sh.add_worksheet(title=title, rows=max(rows, 100), cols=max(cols, 10))
    return ws


def upload_rows_to_worksheet(ws, records):
    rows = records_to_sheet_rows(trim_rows_for_sheet(records))
    need_rows = max(len(rows), 10)
    need_cols = max(len(rows[0]) if rows else 1, 10)
    try:
        if ws.row_count < need_rows or ws.col_count < need_cols:
            ws.resize(rows=max(need_rows, ws.row_count), cols=max(need_cols, ws.col_count))
    except Exception:
        pass
    ws.clear()
    ws.update("A1", rows)
    try:
        ws.freeze(rows=1)
    except Exception:
        pass


def save_to_gsheet(sheet_name, data_map):
    gc = get_gspread_client_login()
    if gc is None:
        return None
    try:
        sh = gc.open(sheet_name)
        print(f"[기존 스프레드시트 열기] {sheet_name}")
    except Exception:
        sh = gc.create(sheet_name)
        print(f"[새 스프레드시트 생성] {sheet_name}")
        print("URL:", sh.url)

    for raw_title, records in data_map.items():
        title = safe_sheet_title(raw_title)
        ws = ensure_worksheet(sh, title=title, rows=min(MAX_SHEET_ROWS_PER_TAB + 10, 5000), cols=MAX_SHEET_COLS)
        upload_rows_to_worksheet(ws, records)
        print(f"[업로드] {title} / rows={min(len(records), MAX_SHEET_ROWS_PER_TAB)}")
    return sh.url


def main():
    print("[0] 유니버스 정보")
    sector_count = len(SECTORS)
    stock_count = sum(len(v) for v in SECTORS.values())
    etf_count = sum(len(v) for v in ETF_SECTORS.values())
    print("주식 섹터 수:", sector_count)
    print("주식 종목 수:", stock_count)
    print("ETF 수:", etf_count)

    print("[1] 글로벌 뉴스 수집")
    news_raw = get_news()
    print("뉴스 건수:", len(news_raw))

    print("[2] 뉴스 → 한국 섹터 매핑")
    news_tagged = map_news_to_sector(news_raw)
    print("섹터 매핑 뉴스 건수:", len(news_tagged))

    print("[3] 한국 섹터 원본 데이터 생성")
    sector_raw = build_sector_raw()
    print("섹터 원본 행 수:", len(sector_raw))

    print("[4] 섹터 요약")
    sector_summary = summarize_sector(sector_raw, news_tagged)
    print("섹터 요약 행 수:", len(sector_summary))

    print("[5] Boom Score 계산")
    boom_score = add_boom_score(sector_summary)
    print("Boom Score 행 수:", len(boom_score))

    print("[6] ETF 원본 데이터 생성")
    etf_raw = build_etf_raw()
    print("ETF 원본 행 수:", len(etf_raw))

    print("[7] ETF RS 랭킹 계산")
    etf_rs_rank = calculate_etf_rs_ranking(etf_raw)
    print("ETF RS 랭킹 행 수:", len(etf_rs_rank))

    print("[8] ETF 섹터 순위 계산")
    etf_sector_rank = summarize_etf_sector_ranking(etf_rs_rank)
    print("ETF 섹터 순위 행 수:", len(etf_sector_rank))

    print("[9] 종목 RS 랭킹 계산")
    stock_rs_rank = build_stock_rs_table()
    print("종목 RS 행 수:", len(stock_rs_rank))

    print("[10] ETF 상위 섹터 기반 종목 추천")
    stock_recommend = build_stock_recommendation(etf_sector_rank, stock_rs_rank)
    print("추천 종목 수:", len(stock_recommend))

    print("[11] 거래대금 폭발 감지용 종목 스냅샷")
    stock_snapshot = build_stock_snapshot()
    print("종목 스냅샷 행 수:", len(stock_snapshot))

    print("[12] 거래대금 폭발 테마 탐지")
    value_theme = build_value_explosion_theme(stock_snapshot, news_tagged)
    print("거래대금 테마 행 수:", len(value_theme))

    print("[13] Day1 테마 종목 추천")
    day1_stock_pick = build_day1_theme_stock_pick(stock_snapshot, value_theme)
    print("Day1 추천 종목 수:", len(day1_stock_pick))

    print("[14] 종가 매수 ETF 후보 생성")
    close_buy_etf = build_close_buy_etf_sector(etf_rs_rank, etf_sector_rank, value_theme)
    print("종가 매수 ETF 후보 수:", len(close_buy_etf))

    print("[15] 종가 매수 종목 후보 생성")
    close_buy_stock = build_close_buy_candidates(stock_rs_rank, stock_snapshot, value_theme)
    print("종가 매수 종목 후보 수:", len(close_buy_stock))

    print("[16] 한 페이지 요약 생성")
    one_page_summary = build_one_page_close_buy_summary(
        boom_score,
        etf_sector_rank,
        value_theme,
        close_buy_stock,
        close_buy_etf,
    )

    print("[16-1] 등락률 출현 횟수 요약 생성")
    ret_appearance_summary = build_ret_appearance_summary(stock_snapshot)

    print("[16-2] 섹터 종목 확산 페이지 생성")
    sector_stock_expansion = build_sector_stock_expansion(stock_snapshot)

    print("[16-3] one_page_summary 하단에 등락률/확산 섹션 추가")
    one_page_summary = append_ret_appearance_to_one_page(
        one_page_summary,
        ret_appearance_summary,
        sector_stock_expansion,
    )

    print("한 페이지 요약 행 수:", len(one_page_summary))
    print("등락률 출현 요약 행 수:", len(ret_appearance_summary))
    print("섹터 확산 페이지 행 수:", len(sector_stock_expansion))

    fetch_logs = FETCH_LOGS[:]
    universe_table = flatten_sector_members()

    print("[17] Google Sheets 저장")
    gsheet_url = save_to_gsheet(GSHEET_NAME, {
        "universe_all": universe_table,
        "news_raw": news_raw,
        "news_tagged": news_tagged,
        "sector_raw": sector_raw,
        "sector_summary": sector_summary,
        "boom_score": boom_score,
        "etf_raw": etf_raw,
        "etf_rs_rank": etf_rs_rank,
        "etf_sector_rank": etf_sector_rank,
        "stock_rs_rank": stock_rs_rank,
        "stock_recommend": stock_recommend,
        "stock_snapshot": stock_snapshot,
        "value_theme": value_theme,
        "day1_stock_pick": day1_stock_pick,
        "close_buy_etf": close_buy_etf,
        "close_buy_stock": close_buy_stock,
        "one_page_summary": one_page_summary,
        "ret_appearance_summary": ret_appearance_summary,
        "sector_stock_expansion": sector_stock_expansion,
        "fetch_logs": fetch_logs,
    })
    print("Google Sheets URL:", gsheet_url)

    return {
        "universe_all": universe_table,
        "news_raw": news_raw,
        "news_tagged": news_tagged,
        "sector_raw": sector_raw,
        "sector_summary": sector_summary,
        "boom_score": boom_score,
        "etf_raw": etf_raw,
        "etf_rs_rank": etf_rs_rank,
        "etf_sector_rank": etf_sector_rank,
        "stock_rs_rank": stock_rs_rank,
        "stock_recommend": stock_recommend,
        "stock_snapshot": stock_snapshot,
        "value_theme": value_theme,
        "day1_stock_pick": day1_stock_pick,
        "close_buy_etf": close_buy_etf,
        "close_buy_stock": close_buy_stock,
        "one_page_summary": one_page_summary,
        "ret_appearance_summary": ret_appearance_summary,
        "sector_stock_expansion": sector_stock_expansion,
        "fetch_logs": fetch_logs,
        "gsheet_url": gsheet_url,
    }



# =========================================================
# 🔥 추가 기능: one_page_summary 등락률 출현 횟수 + 섹터 종목 확산
# =========================================================

def build_ret_appearance_summary(stock_snapshot):
    """
    섹터별 상승/하락 출현 횟수 요약
    - one_page_summary 안에 RET_APPEARANCE 섹션으로 추가
    - 별도 탭 ret_appearance_summary 로도 저장
    """
    rows = []
    grouped = {}
    for r in stock_snapshot:
        grouped.setdefault(r.get("sector", "미분류"), []).append(r)

    for sector, items in grouped.items():
        stock_count = len(items)

        up_1d = sum(1 for x in items if safe_num(x.get("ret1"), 0) > 0)
        down_1d = sum(1 for x in items if safe_num(x.get("ret1"), 0) < 0)
        flat_1d = stock_count - up_1d - down_1d

        up_5d = sum(1 for x in items if safe_num(x.get("ret5"), 0) > 0)
        down_5d = sum(1 for x in items if safe_num(x.get("ret5"), 0) < 0)
        flat_5d = stock_count - up_5d - down_5d

        up_20d = sum(1 for x in items if safe_num(x.get("ret20"), 0) > 0)
        down_20d = sum(1 for x in items if safe_num(x.get("ret20"), 0) < 0)
        flat_20d = stock_count - up_20d - down_20d

        value_expand_count = sum(1 for x in items if safe_num(x.get("value_ratio20"), 0) >= 1.3)
        strong_count = sum(
            1 for x in items
            if safe_num(x.get("ret1"), 0) > 0
            and safe_num(x.get("ret5"), 0) > 0
            and safe_num(x.get("value_ratio20"), 0) >= 1.3
        )
        new_high_count = sum(1 for x in items if safe_num(x.get("is_new_high"), 0) == 1)

        rows.append({
            "sector": sector,
            "stock_count": stock_count,
            "상승_1일_출현수": up_1d,
            "하락_1일_출현수": down_1d,
            "보합_1일_출현수": flat_1d,
            "상승_5일_출현수": up_5d,
            "하락_5일_출현수": down_5d,
            "보합_5일_출현수": flat_5d,
            "상승_20일_출현수": up_20d,
            "하락_20일_출현수": down_20d,
            "보합_20일_출현수": flat_20d,
            "거래대금증가종목수": value_expand_count,
            "강한종목수": strong_count,
            "신고가종목수": new_high_count,
            "상승_1일_비율": round(up_1d / stock_count, 4) if stock_count else 0,
            "상승_5일_비율": round(up_5d / stock_count, 4) if stock_count else 0,
            "상승_20일_비율": round(up_20d / stock_count, 4) if stock_count else 0,
            "강한종목비율": round(strong_count / stock_count, 4) if stock_count else 0,
        })

    return sorted(
        rows,
        key=lambda x: (
            x["강한종목수"],
            x["거래대금증가종목수"],
            x["상승_1일_출현수"],
            x["상승_5일_출현수"],
        ),
        reverse=True,
    )


def build_sector_stock_expansion(stock_snapshot):
    """
    아래 페이지/별도 탭: sector_stock_expansion
    섹터별로 강한 종목이 몇 개로 늘어나는지 확인하는 확산 페이지
    """
    rows = []
    grouped = {}
    for r in stock_snapshot:
        grouped.setdefault(r.get("sector", "미분류"), []).append(r)

    for sector, items in grouped.items():
        total = len(items)
        ret1_positive = sum(1 for x in items if safe_num(x.get("ret1"), 0) > 0)
        ret5_positive = sum(1 for x in items if safe_num(x.get("ret5"), 0) > 0)
        ret20_positive = sum(1 for x in items if safe_num(x.get("ret20"), 0) > 0)
        value_expand = sum(1 for x in items if safe_num(x.get("value_ratio20"), 0) >= 1.3)
        value_explosion = sum(1 for x in items if safe_num(x.get("value_ratio20"), 0) >= 2.0)
        new_high = sum(1 for x in items if safe_num(x.get("is_new_high"), 0) == 1)

        expansion_count = sum(
            1 for x in items
            if safe_num(x.get("ret1"), 0) > 0
            and safe_num(x.get("ret5"), 0) > 0
            and safe_num(x.get("value_ratio20"), 0) >= 1.3
        )

        early_count = sum(
            1 for x in items
            if safe_num(x.get("ret1"), 0) > 0
            and safe_num(x.get("value_ratio20"), 0) >= 1.3
        )

        if expansion_count >= 4:
            stage = "섹터 확산 강함"
        elif expansion_count >= 2:
            stage = "섹터 확산 진행"
        elif early_count >= 2:
            stage = "초기 확산 관찰"
        else:
            stage = "확산 약함"

        rows.append({
            "sector": sector,
            "전체종목수": total,
            "1일상승종목수": ret1_positive,
            "5일상승종목수": ret5_positive,
            "20일상승종목수": ret20_positive,
            "거래대금증가종목수_1_3배이상": value_expand,
            "거래대금폭발종목수_2배이상": value_explosion,
            "신고가종목수": new_high,
            "초기확산종목수": early_count,
            "섹터확산종목수": expansion_count,
            "섹터확산비율": round(expansion_count / total, 4) if total else 0,
            "상승확산비율_1일": round(ret1_positive / total, 4) if total else 0,
            "상승확산비율_5일": round(ret5_positive / total, 4) if total else 0,
            "해석": stage,
        })

    return sorted(
        rows,
        key=lambda x: (
            x["섹터확산종목수"],
            x["거래대금증가종목수_1_3배이상"],
            x["1일상승종목수"],
        ),
        reverse=True,
    )


def append_ret_appearance_to_one_page(one_page_summary, ret_appearance_summary, sector_stock_expansion=None):
    """
    기존 one_page_summary 아래에 RET_APPEARANCE / SECTOR_EXPANSION 섹션을 추가
    """
    rows = list(one_page_summary)

    for i, r in enumerate(ret_appearance_summary[:10], 1):
        rows.append({
            "section": "RET_APPEARANCE",
            "rank": i,
            "name": r["sector"],
            "score": r["강한종목수"],
            "detail1": f'1일 상승:{r["상승_1일_출현수"]} / 하락:{r["하락_1일_출현수"]}',
            "detail2": f'5일 상승:{r["상승_5일_출현수"]} / 20일 상승:{r["상승_20일_출현수"]}',
            "detail3": f'강한종목:{r["강한종목수"]} / 비율:{round(r["강한종목비율"] * 100, 1)}%',
        })

    if sector_stock_expansion:
        for i, r in enumerate(sector_stock_expansion[:10], 1):
            rows.append({
                "section": "SECTOR_EXPANSION",
                "rank": i,
                "name": r["sector"],
                "score": r["섹터확산종목수"],
                "detail1": f'확산종목:{r["섹터확산종목수"]}/{r["전체종목수"]}',
                "detail2": f'거래대금증가:{r["거래대금증가종목수_1_3배이상"]} / 신고가:{r["신고가종목수"]}',
                "detail3": r["해석"],
            })

    return rows



# =========================================================
# 🔥 추가 기능: 전일 대비 순위 변화 (Δrank) + 신규 진입
# =========================================================

def calculate_rank_delta(current, prev, key="ticker"):
    prev_map = {r[key]: r for r in prev}
    out = []
    for r in current:
        prev_rank = prev_map.get(r[key], {}).get("rank")
        curr_rank = r.get("rank")
        delta = None
        if prev_rank and curr_rank:
            delta = prev_rank - curr_rank
        x = dict(r)
        x["prev_rank"] = prev_rank
        x["delta_rank"] = delta
        x["new_entry"] = 1 if prev_rank is None else 0
        out.append(x)
    return out


def extract_top_new_entries(rank_table, top_n=200):
    return [r for r in rank_table if r.get("new_entry") == 1 and r.get("rank") <= top_n]


# =========================================================
# main() 내부에 추가 (예시 위치)
# =========================================================

# [추가] 전일 데이터 불러오기 (Google Sheets or 캐시 활용)
# prev_stock_rs_rank = load_previous_data("stock_rs_rank")
# prev_etf_rs_rank = load_previous_data("etf_rs_rank")

# [추가] 순위 변화 계산
# stock_rs_delta = calculate_rank_delta(stock_rs_rank, prev_stock_rs_rank)
# etf_rs_delta = calculate_rank_delta(etf_rs_rank, prev_etf_rs_rank)

# [추가] 신규 진입
# new_stock_entries = extract_top_new_entries(stock_rs_delta, 200)
# new_etf_entries = extract_top_new_entries(etf_rs_delta, 50)

# Google Sheets 저장 시 추가
# "stock_rs_delta": stock_rs_delta,
# "etf_rs_delta": etf_rs_delta,
# "new_stock_entries": new_stock_entries,
# "new_etf_entries": new_etf_entries,


if __name__ == "__main__":
    results = main()
    print("완료")
# 주식트랜드_국내_분석_FULL
