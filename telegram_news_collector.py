# ============================================================
# Telegram 뉴스 조회수 + 현재 기준 최근 24시간 자동 취합
# TOP5 뉴스/리포트/외신 + ETF RS + 종목 RS + 종가베팅
# ΔRank / 뉴스등급 / 제외조건 / 장전체크 / 텔레그램 2차 전송
# ============================================================

import asyncio, base64, json, os, re, time, html, requests
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf
import gspread

from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from telethon import TelegramClient
from telethon.sessions import StringSession
from google.oauth2.service_account import Credentials

# ============================================================
# 1. 사용자 설정
# ============================================================

KST = ZoneInfo("Asia/Seoul")

def get_secret(name, default=""):
    return os.getenv(name, default).strip()


API_ID = int(get_secret("TELEGRAM_API_ID", "0"))
API_HASH = get_secret("TELEGRAM_API_HASH")
TELEGRAM_SESSION_STRING = get_secret("TELEGRAM_SESSION_STRING")
TELEGRAM_SESSION_B64 = get_secret("TELEGRAM_SESSION_B64")
SESSION_NAME = get_secret("TELEGRAM_SESSION_NAME", "telegram_news_session")
RESET_SESSION = get_secret("RESET_TELEGRAM_SESSION", "false").lower() in {"1", "true", "yes", "y"}

SPREADSHEET_NAME = get_secret("SPREADSHEET_NAME", "TELEGRAM_NEWS_ETF_RS_CLOSE_BET_SYSTEM")
USE_GOOGLE_SHEETS = get_secret("USE_GOOGLE_SHEETS", "true").lower() in {"1", "true", "yes", "y"}
GOOGLE_SERVICE_ACCOUNT_JSON = get_secret("GOOGLE_SERVICE_ACCOUNT_JSON")

SEND_BOT_TOKEN = get_secret("SEND_BOT_TOKEN") or get_secret("TELEGRAM_BOT_TOKEN")
SEND_CHAT_ID = get_secret("SEND_CHAT_ID") or get_secret("TELEGRAM_CHAT_ID")

# 현재 기준 수집
USE_NOW_BASED_COLLECTION = True
LOOKBACK_HOURS = 24
SPLIT_RATIO = 0.5

# 고정 시간 모드가 필요할 때만 사용
START_TIME = "09:00"
MID_TIME = "12:00"
CLOSE_TIME = "15:30"

MAX_CHANNELS = 100
MAX_MESSAGES_PER_CHANNEL = 400
INCLUDE_ALL_CHANNELS = False
BENCHMARK = "^KS11"

NEWS_CHANNEL_FILTER_KEYWORDS = [
    "news", "뉴스", "경제", "증권", "주식", "stock", "market",
    "투자", "리포트", "시황", "속보", "공시", "매크로", "finance"
]

EXCLUDE_CHANNEL_KEYWORDS = [
    "chat", "잡담", "일상", "방장", "공지방", "test", "테스트"
]

REPORT_KEYWORDS = [
    "리포트", "보고서", "목표가", "투자의견", "상향", "하향",
    "컨센서스", "실적 전망", "영업이익", "증권사", "애널리스트",
    "BUY", "SELL", "HOLD", "REPORT"
]

FOREIGN_NEWS_KEYWORDS = [
    "외신", "로이터", "REUTERS", "블룸버그", "BLOOMBERG", "CNBC",
    "WSJ", "월스트리트저널", "FT", "FINANCIAL TIMES",
    "NIKKEI", "닛케이", "AP", "AFP", "미국", "중국", "일본", "유럽",
    "FED", "연준", "FOMC", "나스닥", "S&P", "엔비디아", "테슬라",
    "NASDAQ", "DOW", "EU", "ECB", "BOJ"
]

# ============================================================
# 2. 섹터 / ETF / 종목 매핑
# ============================================================

SECTOR_KEYWORDS = {
    "AI반도체": ["AI", "인공지능", "HBM", "GPU", "엔비디아", "NVIDIA", "데이터센터", "반도체", "CXL", "ASIC"],
    "전력기기": ["전력", "변압기", "전선", "송전", "배전", "전력망", "초고압", "HVDC"],
    "원전": ["원전", "SMR", "원자력", "체코 원전", "웨스팅하우스"],
    "방산": ["방산", "미사일", "드론", "K방산", "무기", "전쟁", "국방", "천무", "K2", "K9"],
    "조선": ["조선", "LNG선", "선박", "수주", "한화오션", "삼성중공업"],
    "2차전지": ["2차전지", "배터리", "리튬", "양극재", "음극재", "전고체", "ESS", "전기차"],
    "바이오": ["바이오", "신약", "임상", "FDA", "ADC", "비만치료제"],
    "로봇": ["로봇", "휴머노이드", "감속기", "자동화", "협동로봇"],
    "보안": ["보안", "해킹", "사이버", "인증", "생체인식", "제로트러스트"],
    "정유/LNG": ["유가", "WTI", "브렌트", "LNG", "가스", "정유", "호르무즈", "중동"],
    "화장품": ["화장품", "K뷰티", "올리브영", "수출"],
    "엔터/게임": ["엔터", "게임", "하이브", "JYP", "와이지", "크래프톤", "넷마블"],
}

IMPORTANT_KEYWORDS = [
    "AI", "HBM", "반도체", "데이터센터", "전력", "원전", "SMR",
    "방산", "드론", "조선", "LNG", "2차전지", "ESS", "바이오",
    "FDA", "로봇", "보안", "유가", "중동", "수출", "실적", "수주",
    "상향", "목표가", "공급계약", "엔비디아", "트럼프", "금리"
]

ETF_MAP = {
    "AI반도체": [
        ("091160.KS", "KODEX 반도체"),
        ("091230.KS", "TIGER 반도체"),
        ("395160.KS", "KODEX Fn시스템반도체"),
        ("381180.KS", "TIGER 미국필라델피아반도체나스닥"),
    ],
    "전력기기": [("102960.KS", "KODEX 기계장비")],
    "원전": [
        ("434730.KS", "HANARO 원자력iSelect"),
        ("433500.KS", "ACE 원자력테마딥서치"),
    ],
    "방산": [
        ("449450.KS", "TIGER K방산&우주"),
        ("476070.KS", "PLUS K방산"),
    ],
    "조선": [("466920.KS", "SOL 조선TOP3플러스")],
    "2차전지": [
        ("305720.KS", "KODEX 2차전지산업"),
        ("305540.KS", "TIGER 2차전지테마"),
    ],
    "바이오": [
        ("244580.KS", "KODEX 바이오"),
        ("266420.KS", "KODEX 헬스케어"),
    ],
    "로봇": [("445290.KS", "KODEX K-로봇액티브")],
    "정유/LNG": [("117460.KS", "KODEX 에너지화학")],
    "엔터/게임": [("300950.KS", "KODEX 게임산업")],
}

SECTOR_STOCK_MAP = {
    "AI반도체": [
        ("005930.KS", "삼성전자"),
        ("000660.KS", "SK하이닉스"),
        ("042700.KS", "한미반도체"),
        ("007660.KS", "이수페타시스"),
    ],
    "전력기기": [
        ("267260.KS", "HD현대일렉트릭"),
        ("010120.KS", "LS ELECTRIC"),
        ("298040.KS", "효성중공업"),
    ],
    "원전": [
        ("034020.KS", "두산에너빌리티"),
        ("052690.KS", "한전기술"),
        ("010140.KS", "삼성중공업"),
    ],
    "방산": [
        ("012450.KS", "한화에어로스페이스"),
        ("064350.KS", "현대로템"),
        ("079550.KS", "LIG넥스원"),
    ],
    "조선": [
        ("329180.KS", "HD현대중공업"),
        ("042660.KS", "한화오션"),
        ("010140.KS", "삼성중공업"),
    ],
    "2차전지": [
        ("373220.KS", "LG에너지솔루션"),
        ("247540.KQ", "에코프로비엠"),
        ("086520.KQ", "에코프로"),
    ],
    "바이오": [
        ("196170.KQ", "알테오젠"),
        ("141080.KQ", "리가켐바이오"),
    ],
    "로봇": [("454910.KS", "두산로보틱스")],
    "보안": [("236200.KQ", "슈프리마")],
}

STOCK_KEYWORDS = {}
for sector, stocks in SECTOR_STOCK_MAP.items():
    for ticker, name in stocks:
        STOCK_KEYWORDS[name] = [name, ticker.replace(".KS", "").replace(".KQ", "")]

# ============================================================
# 3. Telethon 세션
# ============================================================

def create_telegram_client():
    if not API_ID or not API_HASH:
        raise RuntimeError("TELEGRAM_API_ID / TELEGRAM_API_HASH GitHub Secrets가 필요합니다.")

    if TELEGRAM_SESSION_STRING:
        return TelegramClient(StringSession(TELEGRAM_SESSION_STRING), API_ID, API_HASH)

    session_file = Path(f"{SESSION_NAME}.session")
    if TELEGRAM_SESSION_B64 and not session_file.exists():
        session_file.write_bytes(base64.b64decode(TELEGRAM_SESSION_B64))

    if RESET_SESSION:
        for f in [session_file, Path(f"{SESSION_NAME}.session-journal")]:
            if f.exists():
                f.unlink()
                print("삭제:", f)

    if not session_file.exists():
        raise RuntimeError(
            "GitHub Actions에서는 텔레그램 로그인 코드를 입력할 수 없습니다. "
            "TELEGRAM_SESSION_STRING 또는 TELEGRAM_SESSION_B64 Secret을 추가하세요."
        )

    print(f"[SESSION] GitHub Actions 텔레그램 세션 재사용: {session_file}")
    return TelegramClient(SESSION_NAME, API_ID, API_HASH)

# ============================================================
# 4. 기본 함수
# ============================================================

def clean_text(text):
    if not text:
        return ""
    text = re.sub(r"http\S+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def make_short_title(text, max_len=34):
    text = clean_text(text)
    text = re.sub(r"^\[.*?\]", "", text).strip()
    text = re.sub(r"^[▶■●📌🔥✅\-\*\s]+", "", text).strip()
    parts = re.split(r"[.\n]", text)
    title = parts[0].strip() if parts else text
    if len(title) > max_len:
        title = title[:max_len] + "…"
    return title

def safe_int(x):
    try:
        if pd.isna(x):
            return 0
        return int(round(float(x)))
    except:
        return 0

def time_to_dt(date_value, hhmm):
    h, m = map(int, hhmm.split(":"))
    return datetime.combine(date_value, datetime.min.time(), tzinfo=KST).replace(hour=h, minute=m)

def get_dynamic_time_window():
    now_dt = datetime.now(KST)

    if USE_NOW_BASED_COLLECTION:
        start_dt = now_dt - pd.Timedelta(hours=LOOKBACK_HOURS)
        end_dt = now_dt
        split_dt = start_dt + (end_dt - start_dt) * SPLIT_RATIO
    else:
        today = datetime.now(KST).date()
        start_dt = time_to_dt(today, START_TIME)
        split_dt = time_to_dt(today, MID_TIME)
        end_dt = time_to_dt(today, CLOSE_TIME)

    return start_dt, split_dt, end_dt

def parse_time(date_obj):
    if date_obj.tzinfo is None:
        date_obj = date_obj.replace(tzinfo=timezone.utc)
    return date_obj.astimezone(KST)

def contains_any(text, words):
    t = str(text).upper()
    return any(str(w).upper() in t for w in words)

def extract_keywords(text):
    return ", ".join(sorted(set([kw for kw in IMPORTANT_KEYWORDS if kw.upper() in str(text).upper()])))

def extract_sectors(text):
    return ", ".join(sorted(set([s for s, words in SECTOR_KEYWORDS.items() if contains_any(text, words)])))

def extract_stocks(text):
    return ", ".join(sorted(set([s for s, words in STOCK_KEYWORDS.items() if contains_any(text, words)])))

def classify_news_type(text):
    t = str(text).upper()
    if any(k.upper() in t for k in REPORT_KEYWORDS):
        return "리포트"
    if any(k.upper() in t for k in FOREIGN_NEWS_KEYWORDS):
        return "외신"
    return "일반뉴스"

def rank_score(series):
    if series is None:
        return pd.Series(dtype=float)

    if isinstance(series, (int, float, np.integer, np.floating)):
        series = pd.Series([series])

    if not isinstance(series, pd.Series):
        series = pd.Series(series)

    if len(series) == 0:
        return series

    return series.rank(pct=True) * 100

def to_int_columns(df):
    if df is None or df.empty:
        return df
    out = df.copy()
    for col in out.select_dtypes(include=[np.number]).columns:
        out[col] = out[col].replace([np.inf, -np.inf], 0).fillna(0).round(0).astype(int)
    return out

def top_list(df, col, n):
    if df is None or df.empty or col not in df.columns:
        return "없음"
    return ", ".join(df.head(n)[col].astype(str).tolist())

# ============================================================
# 5. Google Sheets
# ============================================================

def connect_gsheet():
    if not USE_GOOGLE_SHEETS:
        raise RuntimeError("USE_GOOGLE_SHEETS=false")
    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_JSON GitHub Secret이 필요합니다.")

    info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(info, scopes=scopes)
    gc = gspread.authorize(creds)

    try:
        sh = gc.open(SPREADSHEET_NAME)
    except Exception:
        sh = gc.create(SPREADSHEET_NAME)

    return sh

def load_prev_sheet(sheet_name):
    if not USE_GOOGLE_SHEETS:
        print("[PREV] Google Sheets 비활성화")
        return pd.DataFrame()
    try:
        sh = connect_gsheet()
        ws = sh.worksheet(sheet_name)
        values = ws.get_all_records()
        df = pd.DataFrame(values)
        print(f"[PREV] 전일 데이터 로드 성공: {sheet_name} / {len(df)}건")
        return df
    except Exception as e:
        print(f"[PREV] 전일 데이터 없음: {sheet_name} / {e}")
        return pd.DataFrame()

def write_df_to_sheet(sh, sheet_name, df):
    if df is None or df.empty:
        df = pd.DataFrame({"내용": ["데이터 없음"]})

    df = df.copy()

    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].astype(str)

    df = df.replace([np.inf, -np.inf], np.nan).fillna("")

    try:
        ws = sh.worksheet(sheet_name)
        ws.clear()
    except:
        ws = sh.add_worksheet(
            title=sheet_name,
            rows=max(len(df) + 20, 100),
            cols=max(len(df.columns) + 5, 20)
        )

    values = [df.columns.tolist()] + df.astype(str).values.tolist()
    ws.update(values)

    try:
        ws.freeze(rows=1)
        ws.format("1:1", {
            "textFormat": {"bold": True},
            "backgroundColor": {"red": 0.90, "green": 0.90, "blue": 0.90}
        })
    except:
        pass

def save_all_to_sheets(result):
    if not USE_GOOGLE_SHEETS:
        print("[SKIP] Google Sheets 저장 비활성화")
        return

    sh = connect_gsheet()

    for sheet_name, df in result.items():
        print(f"[SAVE] {sheet_name}")
        write_df_to_sheet(sh, sheet_name, df)
        time.sleep(1)

    print(f"[완료] Google Sheets 저장 완료: {SPREADSHEET_NAME}")

# ============================================================
# 6. Telethon 로그인 / 자동 채널 수집
# ============================================================

async def validate_telethon_login():
    if not isinstance(API_ID, int):
        raise ValueError("API_ID는 숫자여야 합니다.")
    if not API_HASH or "여기에" in API_HASH:
        raise ValueError("API_HASH를 입력하세요.")

    client = create_telegram_client()
    await client.start()

    me = await client.get_me()

    if getattr(me, "bot", False):
        await client.disconnect()
        raise RuntimeError(
            "현재 Telethon 세션이 봇 계정입니다. "
            "RESET_SESSION=True로 세션 삭제 후, 로그인 입력창에는 봇 토큰이 아니라 휴대폰 번호(+8210...)를 입력하세요."
        )

    print(f"[OK] 사용자 계정 로그인 성공: {me.first_name} / id={me.id}")

    await client.disconnect()

def channel_match_score(title, username):
    text = f"{title or ''} {username or ''}".lower()
    if any(x.lower() in text for x in EXCLUDE_CHANNEL_KEYWORDS):
        return -999

    score = 0
    for kw in NEWS_CHANNEL_FILTER_KEYWORDS:
        if kw.lower() in text:
            score += 10
    return score

async def get_auto_channels(client):
    dialogs = await client.get_dialogs(limit=None)
    rows = []

    for d in dialogs:
        try:
            if not d.is_channel:
                continue
            entity = d.entity
            title = getattr(entity, "title", "") or ""
            username = getattr(entity, "username", "") or ""
            score = channel_match_score(title, username)
            include = score > -999 if INCLUDE_ALL_CHANNELS else score > 0

            if include:
                rows.append({
                    "title": title,
                    "username": username,
                    "entity": entity,
                    "score": score,
                })
        except:
            continue

    ch_df = pd.DataFrame(rows)

    if ch_df.empty:
        return [], ch_df

    ch_df = ch_df.sort_values("score", ascending=False).head(MAX_CHANNELS).reset_index(drop=True)
    channels = ch_df["entity"].tolist()

    return channels, ch_df.drop(columns=["entity"])

async def fetch_telegram_news():
    await validate_telethon_login()

    client = create_telegram_client()
    await client.start()

    me = await client.get_me()
    if getattr(me, "bot", False):
        await client.disconnect()
        raise RuntimeError("봇 계정으로 로그인되어 get_dialogs를 실행할 수 없습니다. 휴대폰 번호로 다시 로그인하세요.")

    channels, channel_df = await get_auto_channels(client)
    print(f"[INFO] 자동 선택 채널 수: {len(channels)}")

    start_dt, split_dt, close_dt = get_dynamic_time_window()

    print(
        f"[TIME] 수집구간: {start_dt.strftime('%Y-%m-%d %H:%M')} "
        f"~ {close_dt.strftime('%Y-%m-%d %H:%M')}"
    )
    print(
        f"[TIME] 비교구간: 이전구간 <= {split_dt.strftime('%Y-%m-%d %H:%M')} / "
        f"최근구간 > {split_dt.strftime('%Y-%m-%d %H:%M')}"
    )

    rows = []
    error_rows = []

    for idx, entity in enumerate(channels, 1):
        title = getattr(entity, "title", "") or ""
        username = getattr(entity, "username", "") or ""
        channel_name = username if username else title

        try:
            count = 0

            async for msg in client.iter_messages(entity, limit=MAX_MESSAGES_PER_CHANNEL):
                msg_time = parse_time(msg.date)

                if msg_time < start_dt:
                    break
                if msg_time > close_dt:
                    continue

                text = clean_text(msg.message or "")
                if not text:
                    continue

                link = f"https://t.me/{channel_name}/{msg.id}" if username else ""

                rows.append({
                    "date": msg_time.strftime("%Y-%m-%d"),
                    "time": msg_time.strftime("%H:%M:%S"),
                    "datetime": msg_time.replace(tzinfo=None),
                    "channel": channel_name,
                    "channel_title": title,
                    "message_id": msg.id,
                    "link": link,
                    "short_title": make_short_title(text),
                    "views": safe_int(getattr(msg, "views", 0) or 0),
                    "forwards": safe_int(getattr(msg, "forwards", 0) or 0),
                    "replies": safe_int(getattr(msg.replies, "replies", 0) if msg.replies else 0),
                    "text": text,
                    "news_type": classify_news_type(text),
                    "keywords": extract_keywords(text),
                    "sectors": extract_sectors(text),
                    "stocks": extract_stocks(text),
                })

                count += 1

            print(f"[OK] {idx}/{len(channels)} 수집: {channel_name} / {count}건")
            time.sleep(0.2)

        except Exception as e:
            print(f"[WARN] 채널 수집 실패: {channel_name} / {e}")
            error_rows.append({
                "channel": channel_name,
                "title": title,
                "error": str(e)
            })

    await client.disconnect()

    df = pd.DataFrame(rows)
    err_df = pd.DataFrame(error_rows)

    if not df.empty:
        df = df.sort_values(["datetime", "views"], ascending=[True, False]).reset_index(drop=True)

    return df, err_df, channel_df

# ============================================================
# 7. 뉴스 분석
# ============================================================

def add_interest_score(df):
    if df.empty:
        return df

    out = df.copy()
    out["view_score"] = rank_score(out["views"])
    out["forward_score"] = rank_score(out["forwards"])
    out["reply_score"] = rank_score(out["replies"])

    out["interest_score"] = (
        out["view_score"] * 0.75 +
        out["forward_score"] * 0.15 +
        out["reply_score"] * 0.10
    )

    return to_int_columns(out)

def explode_items(df, col, item_name):
    if df.empty:
        return pd.DataFrame()

    rows = []

    for _, r in df.iterrows():
        for item in str(r.get(col, "")).split(","):
            item = item.strip()
            if item:
                rows.append({
                    item_name: item,
                    "channel": r.get("channel", ""),
                    "views": r.get("views", 0),
                    "forwards": r.get("forwards", 0),
                    "replies": r.get("replies", 0),
                    "interest_score": r.get("interest_score", 0),
                    "time": r.get("time", ""),
                    "text": r.get("text", ""),
                })

    return pd.DataFrame(rows)

def build_persistence_rank(df_prev, df_recent, col, item_name, score_name):
    e_prev = explode_items(df_prev, col, item_name)
    e_recent = explode_items(df_recent, col, item_name)

    def agg(e, prefix):
        if e.empty:
            return pd.DataFrame(columns=[item_name])
        return e.groupby(item_name).agg(
            **{
                f"{prefix}_뉴스수": (item_name, "count"),
                f"{prefix}_채널수": ("channel", "nunique"),
                f"{prefix}_조회수합": ("views", "sum"),
                f"{prefix}_전달수합": ("forwards", "sum"),
                f"{prefix}_평균관심점수": ("interest_score", "mean"),
            }
        ).reset_index()

    a_prev = agg(e_prev, "이전구간")
    a_recent = agg(e_recent, "최근구간")

    if a_prev.empty and a_recent.empty:
        return pd.DataFrame()

    out = pd.merge(a_prev, a_recent, on=item_name, how="outer").fillna(0)

    out["전체뉴스수"] = out.get("이전구간_뉴스수", 0) + out.get("최근구간_뉴스수", 0)
    out["전체채널수"] = out.get("이전구간_채널수", 0) + out.get("최근구간_채널수", 0)
    out["전체조회수"] = out.get("이전구간_조회수합", 0) + out.get("최근구간_조회수합", 0)
    out["최근재등장"] = np.where(out.get("최근구간_뉴스수", 0) > 0, 1, 0)
    out["조회수증가"] = out.get("최근구간_조회수합", 0) - out.get("이전구간_조회수합", 0)

    s_recent_views = out["최근구간_조회수합"] if "최근구간_조회수합" in out.columns else pd.Series([0] * len(out))
    s_news = out["전체뉴스수"] if "전체뉴스수" in out.columns else pd.Series([0] * len(out))
    s_channel = out["전체채널수"] if "전체채널수" in out.columns else pd.Series([0] * len(out))
    s_delta = out["조회수증가"] if "조회수증가" in out.columns else pd.Series([0] * len(out))

    out[score_name] = (
        rank_score(out["전체조회수"]) * 0.35 +
        rank_score(s_recent_views) * 0.25 +
        rank_score(s_news) * 0.15 +
        rank_score(s_channel) * 0.10 +
        rank_score(s_delta) * 0.05 +
        out["최근재등장"] * 10
    )

    out["다음날판단"] = np.where(
        out[score_name] >= 80, "강한 주목",
        np.where(out[score_name] >= 60, "관심 지속", "단기 이슈")
    )

    out = to_int_columns(out)
    out = out.sort_values(score_name, ascending=False).reset_index(drop=True)
    out.insert(0, "순위", range(1, len(out) + 1))

    return out

def build_news_rank(df, name):
    if df.empty:
        return pd.DataFrame({"내용": [f"{name} 데이터 없음"]})
    out = df.sort_values("interest_score", ascending=False).head(100).copy()
    out.insert(0, "순위", range(1, len(out) + 1))
    return out

def build_view_top5(df, news_type=None, title="조회수_TOP5"):
    if df is None or df.empty:
        return pd.DataFrame({"내용": [f"{title} 데이터 없음"]})

    out = df.copy()

    if news_type:
        out = out[out["news_type"] == news_type].copy()

    if out.empty:
        return pd.DataFrame({"내용": [f"{title} 데이터 없음"]})

    out = out.sort_values("views", ascending=False).head(5).copy()
    out.insert(0, "순위", range(1, len(out) + 1))

    keep_cols = [
        "순위", "date", "time", "channel", "news_type",
        "views", "forwards", "replies",
        "short_title", "link",
        "keywords", "sectors", "stocks", "text"
    ]

    keep_cols = [c for c in keep_cols if c in out.columns]
    return out[keep_cols]

# ============================================================
# 8. 가격 / RS 계산
# ============================================================

def get_all_tickers():
    tickers = set([BENCHMARK])

    for sector, etfs in ETF_MAP.items():
        for ticker, name in etfs:
            tickers.add(ticker)

    for sector, stocks in SECTOR_STOCK_MAP.items():
        for ticker, name in stocks:
            tickers.add(ticker)

    return sorted(tickers)

def fetch_price_data(tickers, period="6mo"):
    data = {}

    for ticker in tickers:
        try:
            df = yf.download(
                ticker,
                period=period,
                interval="1d",
                auto_adjust=True,
                progress=False,
                threads=False
            )

            if df is None or df.empty:
                print(f"[WARN] 가격 데이터 없음: {ticker}")
                continue

            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]

            data[ticker] = df
            time.sleep(0.1)

        except Exception as e:
            print(f"[WARN] 가격 수집 실패: {ticker} / {e}")

    return data

def calc_return(close, days):
    if close is None or len(close) <= days:
        return np.nan
    return (close.iloc[-1] / close.iloc[-days-1] - 1) * 100

def calc_rs_table(price_data):
    benchmark_df = price_data.get(BENCHMARK)

    if benchmark_df is None or benchmark_df.empty:
        bench_ret5 = bench_ret20 = bench_ret60 = 0
    else:
        bclose = benchmark_df["Close"]
        bench_ret5 = calc_return(bclose, 5)
        bench_ret20 = calc_return(bclose, 20)
        bench_ret60 = calc_return(bclose, 60)

    rows = []

    for ticker, df in price_data.items():
        if ticker == BENCHMARK or df is None or df.empty:
            continue

        close = df["Close"]
        volume = df["Volume"] if "Volume" in df.columns else pd.Series(dtype=float)

        ret1 = calc_return(close, 1)
        ret5 = calc_return(close, 5)
        ret20 = calc_return(close, 20)
        ret60 = calc_return(close, 60)

        rs5 = ret5 - bench_ret5 if pd.notna(ret5) else np.nan
        rs20 = ret20 - bench_ret20 if pd.notna(ret20) else np.nan
        rs60 = ret60 - bench_ret60 if pd.notna(ret60) else np.nan

        ma5 = close.rolling(5).mean().iloc[-1] if len(close) >= 5 else np.nan
        ma20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else np.nan

        value_ratio20 = np.nan
        if len(close) >= 21 and len(volume) >= 21:
            value = close * volume
            value_ratio20 = value.iloc[-1] / value.rolling(20).mean().iloc[-1]

        rows.append({
            "ticker": ticker,
            "ret1": ret1,
            "ret5": ret5,
            "ret20": ret20,
            "ret60": ret60,
            "RS5": rs5,
            "RS20": rs20,
            "RS60": rs60,
            "MA5위": 1 if close.iloc[-1] > ma5 else 0,
            "MA20위": 1 if close.iloc[-1] > ma20 else 0,
            "거래대금배율20": value_ratio20,
        })

    rs = pd.DataFrame(rows)

    if rs.empty:
        return rs

    rs["RS점수"] = (
        rank_score(rs["RS5"].fillna(-999)) * 0.25 +
        rank_score(rs["RS20"].fillna(-999)) * 0.45 +
        rank_score(rs["RS60"].fillna(-999)) * 0.20 +
        rank_score(rs["거래대금배율20"].fillna(0)) * 0.10
    )

    rs = to_int_columns(rs)
    rs = rs.sort_values("RS점수", ascending=False).reset_index(drop=True)
    rs.insert(0, "RS순위", range(1, len(rs) + 1))

    return rs

def build_next_day_etf(sector_rank, rs_table):
    if sector_rank is None or sector_rank.empty:
        return pd.DataFrame()

    rows = []

    for _, r in sector_rank.iterrows():
        sector = r.get("sector", "")
        sector_score = r.get("섹터지속력점수", 0)

        for ticker, name in ETF_MAP.get(sector, []):
            rs_row = rs_table[rs_table["ticker"] == ticker] if not rs_table.empty else pd.DataFrame()

            rs_score = int(rs_row["RS점수"].iloc[0]) if not rs_row.empty else 0
            ret5 = int(rs_row["ret5"].iloc[0]) if not rs_row.empty else 0
            ret20 = int(rs_row["ret20"].iloc[0]) if not rs_row.empty else 0
            value_ratio20 = int(rs_row["거래대금배율20"].iloc[0]) if not rs_row.empty else 0

            final_score = int(sector_score * 0.55 + rs_score * 0.45)

            rows.append({
                "섹터": sector,
                "ETF코드": ticker,
                "ETF명": name,
                "섹터지속력점수": sector_score,
                "ETF_RS점수": rs_score,
                "ret5": ret5,
                "ret20": ret20,
                "거래대금배율20": value_ratio20,
                "ETF종합점수": final_score,
                "판단": "강한 주목" if final_score >= 80 else "관심" if final_score >= 60 else "대기"
            })

    out = pd.DataFrame(rows)

    if out.empty:
        return out

    out = out.sort_values("ETF종합점수", ascending=False).reset_index(drop=True)
    out.insert(0, "순위", range(1, len(out) + 1))

    return out

def build_related_stock_rs(sector_rank, rs_table):
    if sector_rank is None or sector_rank.empty:
        return pd.DataFrame()

    rows = []

    for _, r in sector_rank.iterrows():
        sector = r.get("sector", "")
        sector_score = r.get("섹터지속력점수", 0)

        for ticker, name in SECTOR_STOCK_MAP.get(sector, []):
            rs_row = rs_table[rs_table["ticker"] == ticker] if not rs_table.empty else pd.DataFrame()

            rs_score = int(rs_row["RS점수"].iloc[0]) if not rs_row.empty else 0
            ret1 = int(rs_row["ret1"].iloc[0]) if not rs_row.empty else 0
            ret5 = int(rs_row["ret5"].iloc[0]) if not rs_row.empty else 0
            ret20 = int(rs_row["ret20"].iloc[0]) if not rs_row.empty else 0
            value_ratio20 = int(rs_row["거래대금배율20"].iloc[0]) if not rs_row.empty else 0
            ma5 = int(rs_row["MA5위"].iloc[0]) if not rs_row.empty else 0
            ma20 = int(rs_row["MA20위"].iloc[0]) if not rs_row.empty else 0

            final_score = int(sector_score * 0.45 + rs_score * 0.45 + value_ratio20 * 3 + ma5 * 3 + ma20 * 4)

            rows.append({
                "섹터": sector,
                "종목코드": ticker,
                "종목명": name,
                "섹터지속력점수": sector_score,
                "종목_RS점수": rs_score,
                "ret1": ret1,
                "ret5": ret5,
                "ret20": ret20,
                "거래대금배율20": value_ratio20,
                "MA5위": ma5,
                "MA20위": ma20,
                "종목종합점수": final_score,
                "판단": "강한 주목" if final_score >= 85 else "관심" if final_score >= 65 else "대기"
            })

    out = pd.DataFrame(rows)

    if out.empty:
        return out

    out = out.sort_values("종목종합점수", ascending=False).reset_index(drop=True)
    out.insert(0, "순위", range(1, len(out) + 1))

    return out

def build_close_bet_candidates(sector_rank, next_day_etf, stock_rs):
    if stock_rs is None or stock_rs.empty:
        return pd.DataFrame()

    rows = []

    for _, r in stock_rs.iterrows():
        sector = r.get("섹터", "")

        etf_rows = next_day_etf[next_day_etf["섹터"] == sector] if next_day_etf is not None and not next_day_etf.empty else pd.DataFrame()
        etf_score = int(etf_rows["ETF종합점수"].max()) if not etf_rows.empty else 0
        etf_name = etf_rows.sort_values("ETF종합점수", ascending=False)["ETF명"].iloc[0] if not etf_rows.empty else ""

        sector_score = int(r.get("섹터지속력점수", 0))
        stock_score = int(r.get("종목_RS점수", 0))
        value_ratio = int(r.get("거래대금배율20", 0))
        ma5 = int(r.get("MA5위", 0))
        ma20 = int(r.get("MA20위", 0))

        close_score = int(
            sector_score * 0.35 +
            etf_score * 0.25 +
            stock_score * 0.30 +
            min(value_ratio, 5) * 2 +
            ma5 * 3 +
            ma20 * 4
        )

        if close_score >= 70:
            rows.append({
                "섹터": sector,
                "ETF": etf_name,
                "종목코드": r.get("종목코드", ""),
                "종목명": r.get("종목명", ""),
                "섹터지속력점수": sector_score,
                "ETF종합점수": etf_score,
                "종목_RS점수": stock_score,
                "거래대금배율20": value_ratio,
                "MA5위": ma5,
                "MA20위": ma20,
                "종가베팅점수": close_score,
                "매매판단": "종가베팅 1순위" if close_score >= 85 else "관심 후보",
                "체크조건": "VWAP 위 유지 / 장막판 거래대금 유지 / 전일고점 돌파 확인"
            })

    out = pd.DataFrame(rows)

    if out.empty:
        return out

    out = out.sort_values("종가베팅점수", ascending=False).reset_index(drop=True)
    out.insert(0, "순위", range(1, len(out) + 1))

    return out

# ============================================================
# 9. ΔRank / 뉴스등급 / 제외조건 / 장전체크
# ============================================================

def build_delta_rank(today_sector_rank, prev_sector_rank=None):
    if today_sector_rank is None or today_sector_rank.empty:
        return pd.DataFrame()

    today = today_sector_rank.copy()
    today = today.rename(columns={"순위": "오늘순위"})

    if prev_sector_rank is None or prev_sector_rank.empty or "sector" not in prev_sector_rank.columns:
        today["전일순위"] = ""
        today["ΔRank"] = ""
        today["변화판단"] = "전일 데이터 없음"
        return today

    if "순위" not in prev_sector_rank.columns:
        today["전일순위"] = ""
        today["ΔRank"] = ""
        today["변화판단"] = "전일 순위 없음"
        return today

    prev = prev_sector_rank[["sector", "순위"]].copy()
    prev = prev.rename(columns={"순위": "전일순위"})

    out = today.merge(prev, on="sector", how="left")
    out["전일순위"] = out["전일순위"].fillna(999).astype(int)
    out["ΔRank"] = out["전일순위"] - out["오늘순위"]

    out["변화판단"] = np.where(
        out["ΔRank"] >= 5, "급상승",
        np.where(out["ΔRank"] >= 2, "상승", np.where(out["ΔRank"] <= -2, "하락", "유지"))
    )

    return out.sort_values("ΔRank", ascending=False).reset_index(drop=True)

def build_news_grade(sector_rank):
    if sector_rank is None or sector_rank.empty:
        return pd.DataFrame()

    out = sector_rank.copy()

    def grade(row):
        score = row.get("섹터지속력점수", 0)
        reappear = row.get("최근재등장", 0)
        view_sum = row.get("전체조회수", 0)

        if score >= 85 and reappear == 1 and view_sum > 0:
            return "A"
        elif reappear == 1 and score >= 65:
            return "B"
        elif row.get("이전구간_뉴스수", 0) > 0 and row.get("최근구간_뉴스수", 0) == 0:
            return "C"
        else:
            return "D"

    out["뉴스지속력등급"] = out.apply(grade, axis=1)
    return out

def build_close_bet_exclude(stock_rs, next_day_etf):
    if stock_rs is None or stock_rs.empty:
        return pd.DataFrame()

    rows = []

    for _, r in stock_rs.iterrows():
        reasons = []
        sector = r.get("섹터", "")
        stock_name = r.get("종목명", "")

        etf_rows = next_day_etf[next_day_etf["섹터"] == sector] if next_day_etf is not None and not next_day_etf.empty else pd.DataFrame()
        etf_score = int(etf_rows["ETF종합점수"].max()) if not etf_rows.empty else 0

        rs_score = int(r.get("종목_RS점수", 0))
        ma20 = int(r.get("MA20위", 0))
        value_ratio = int(r.get("거래대금배율20", 0))
        ret1 = int(r.get("ret1", 0))

        if etf_score < 60:
            reasons.append("ETF RS 약함")
        if ma20 == 0:
            reasons.append("종목 20일선 아래")
        if value_ratio < 1:
            reasons.append("거래대금 부족")
        if rs_score < 60 or ret1 <= 0:
            reasons.append("뉴스 강하지만 주가 반응 약함")

        if reasons:
            rows.append({
                "섹터": sector,
                "종목명": stock_name,
                "ETF_RS점수": etf_score,
                "종목_RS점수": rs_score,
                "거래대금배율20": value_ratio,
                "MA20위": ma20,
                "ret1": ret1,
                "제외사유": ", ".join(reasons)
            })

    return pd.DataFrame(rows)

def build_pre_market_checklist(keyword_rank, sector_rank, next_day_etf, close_bet):
    return pd.DataFrame([
        {
            "체크항목": "현재 강한 키워드가 장전 뉴스에 다시 나오는지",
            "확인대상": top_list(keyword_rank, "keyword", 10),
            "판단기준": "장전 08:00~09:00 재등장 시 지속 가능성 상승"
        },
        {
            "체크항목": "관련 ETF 시초가 강한지",
            "확인대상": top_list(next_day_etf, "ETF명", 7),
            "판단기준": "시초가 + 거래대금 동반 상승 확인"
        },
        {
            "체크항목": "대장주 거래대금 붙는지",
            "확인대상": top_list(close_bet, "종목명", 10),
            "판단기준": "장초반 5~15분 거래대금 증가 확인"
        },
        {
            "체크항목": "섹터 순환매인지 단일 뉴스인지",
            "확인대상": top_list(sector_rank, "sector", 7),
            "판단기준": "동일 섹터 내 3종목 이상 동반 상승 시 확산"
        },
    ])

# ============================================================
# 10. 분석 통합
# ============================================================

def build_one_page_summary(keyword_rank, sector_rank, stock_rank, next_day_etf, stock_rs, close_bet, delta_rank):
    rising = delta_rank[delta_rank["변화판단"].isin(["급상승", "상승"])] if not delta_rank.empty and "변화판단" in delta_rank.columns else pd.DataFrame()

    return pd.DataFrame([
        {"항목": "현재 핵심 키워드", "내용": top_list(keyword_rank, "keyword", 10)},
        {"항목": "주목 섹터", "내용": top_list(sector_rank, "sector", 7)},
        {"항목": "급상승 섹터", "내용": top_list(rising, "sector", 5)},
        {"항목": "주목 ETF", "내용": top_list(next_day_etf, "ETF명", 7)},
        {"항목": "관련 RS 종목", "내용": top_list(stock_rs, "종목명", 10)},
        {"항목": "종가베팅 후보", "내용": top_list(close_bet, "종목명", 10)},
        {"항목": "핵심 해석", "내용": "현재 기준 뉴스 지속력 + ΔRank + ETF RS + 종목 RS가 동시에 강한 후보를 우선 추적합니다."},
    ])

def build_scenario(keyword_rank, sector_rank, next_day_etf, stock_rs, close_bet):
    return pd.DataFrame([
        {
            "구분": "강한 지속 시나리오",
            "조건": "이전구간 상위 키워드가 최근구간에도 재등장 + ETF RS 상위",
            "해석": f"핵심 키워드: {top_list(keyword_rank, 'keyword', 7)}",
            "대응": "다음 장초반 같은 키워드 재등장과 ETF 갭상승 확인"
        },
        {
            "구분": "섹터 ETF 확산 시나리오",
            "조건": "뉴스 지속력 높은 섹터의 ETF RS 동반 상승",
            "해석": f"관심 ETF: {top_list(next_day_etf, 'ETF명', 7)}",
            "대응": "ETF → 대장주 → 후발주 순서로 거래대금 확인"
        },
        {
            "구분": "종가베팅 시나리오",
            "조건": "뉴스 지속력 + ETF RS + 종목 RS + 거래대금",
            "해석": f"후보 종목: {top_list(close_bet, '종목명', 10)}",
            "대응": "VWAP 위 유지, 전일 고점 돌파, 최근 거래대금 유지 확인"
        },
    ])

def analyze_news(df, err_df, channel_df, prev_sector_rank=None):
    if df.empty:
        return {
            "자동선택채널": channel_df if channel_df is not None and not channel_df.empty else pd.DataFrame({"내용": ["자동 선택 채널 없음"]}),
            "수집오류": err_df if not err_df.empty else pd.DataFrame({"내용": ["수집된 뉴스 없음"]})
        }

    start_dt, split_dt, end_dt = get_dynamic_time_window()
    split_naive = split_dt.replace(tzinfo=None)
    end_naive = end_dt.replace(tzinfo=None)

    df = add_interest_score(df)

    df_prev = df[df["datetime"] <= split_naive].copy()
    df_recent = df[(df["datetime"] > split_naive) & (df["datetime"] <= end_naive)].copy()
    df_all = df[df["datetime"] <= end_naive].copy()

    keyword_rank = build_persistence_rank(df_prev, df_recent, "keywords", "keyword", "키워드지속력점수")
    sector_rank = build_persistence_rank(df_prev, df_recent, "sectors", "sector", "섹터지속력점수")
    stock_news_rank = build_persistence_rank(df_prev, df_recent, "stocks", "stock", "뉴스종목관심점수")

    print("[RS] 가격 데이터 수집 시작")
    price_data = fetch_price_data(get_all_tickers())
    rs_table = calc_rs_table(price_data)

    next_day_etf = build_next_day_etf(sector_rank, rs_table)
    related_stock_rs = build_related_stock_rs(sector_rank, rs_table)
    close_bet = build_close_bet_candidates(sector_rank, next_day_etf, related_stock_rs)

    delta_rank = build_delta_rank(sector_rank, prev_sector_rank)
    news_grade = build_news_grade(sector_rank)
    close_exclude = build_close_bet_exclude(related_stock_rs, next_day_etf)
    pre_market = build_pre_market_checklist(keyword_rank, sector_rank, next_day_etf, close_bet)

    return {
        "one_page_summary": build_one_page_summary(keyword_rank, sector_rank, stock_news_rank, next_day_etf, related_stock_rs, close_bet, delta_rank),
        "자동선택채널": channel_df,
        "TELEGRAM_NEWS_RAW": df,

        "조회수_TOP5_뉴스": build_view_top5(df_all, "일반뉴스", "조회수_TOP5_뉴스"),
        "조회수_TOP5_리포트": build_view_top5(df_all, "리포트", "조회수_TOP5_리포트"),
        "조회수_TOP5_외신": build_view_top5(df_all, "외신", "조회수_TOP5_외신"),

        "이전구간_뉴스순위": build_news_rank(df_prev, "이전구간"),
        "최근구간_뉴스순위": build_news_rank(df_recent, "최근구간"),
        "전체구간_뉴스순위": build_news_rank(df_all, "전체구간"),

        "키워드_지속력": keyword_rank,
        "섹터_지속력": sector_rank,
        "뉴스_종목관심도": stock_news_rank,

        "ΔRANK_CHANGE": delta_rank,
        "NEWS_GRADE": news_grade,
        "CLOSE_BET_EXCLUDE": close_exclude,
        "PRE_MARKET_CHECKLIST": pre_market,

        "ETF_RS_RANK": rs_table,
        "NEXT_DAY_ETF": next_day_etf,
        "RELATED_STOCK_RS": related_stock_rs,
        "CLOSE_BET_CANDIDATE": close_bet,

        "다음날_시나리오": build_scenario(keyword_rank, sector_rank, next_day_etf, related_stock_rs, close_bet),
        "수집오류": err_df if not err_df.empty else pd.DataFrame({"내용": ["오류 없음"]}),
    }

# ============================================================
# 11. 텔레그램 전송
# ============================================================

def make_top5_lines(df):
    if df is None or df.empty or "short_title" not in df.columns:
        return "- 없음"

    lines = []

    for _, r in df.head(5).iterrows():
        rank = r.get("순위", "")
        views = r.get("views", 0)
        title = html.escape(str(r.get("short_title", "")))
        link = str(r.get("link", ""))

        if link:
            lines.append(f'{rank}. [{views}뷰] <a href="{link}">{title}</a>')
        else:
            lines.append(f"{rank}. [{views}뷰] {title}")

    return "\n".join(lines)

def build_telegram_summary_message(result):
    keyword = result.get("키워드_지속력", pd.DataFrame())
    sector = result.get("섹터_지속력", pd.DataFrame())
    delta = result.get("ΔRANK_CHANGE", pd.DataFrame())
    grade = result.get("NEWS_GRADE", pd.DataFrame())
    etf = result.get("NEXT_DAY_ETF", pd.DataFrame())
    stock_rs = result.get("RELATED_STOCK_RS", pd.DataFrame())
    close_bet = result.get("CLOSE_BET_CANDIDATE", pd.DataFrame())

    top_news = result.get("조회수_TOP5_뉴스", pd.DataFrame())
    top_report = result.get("조회수_TOP5_리포트", pd.DataFrame())
    top_foreign = result.get("조회수_TOP5_외신", pd.DataFrame())

    now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M")

    rising_sector = delta[delta["변화판단"].isin(["급상승", "상승"])] if delta is not None and not delta.empty and "변화판단" in delta.columns else pd.DataFrame()
    grade_a = grade[grade["뉴스지속력등급"] == "A"] if grade is not None and not grade.empty and "뉴스지속력등급" in grade.columns else pd.DataFrame()

    close_lines = []
    if close_bet is not None and not close_bet.empty:
        for _, r in close_bet.head(7).iterrows():
            close_lines.append(
                f"- {html.escape(str(r.get('종목명')))} / {html.escape(str(r.get('섹터')))} / {r.get('종가베팅점수')}점"
            )
    else:
        close_lines = ["- 없음"]

    msg = f"""
📌 <b>현재 기준 뉴스 + ETF RS 종가베팅 요약</b>
기준: {now_str}
수집: 최근 {LOOKBACK_HOURS}시간

🔥 <b>핵심 키워드</b>
{html.escape(top_list(keyword, "keyword", 10))}

📊 <b>주목 섹터</b>
{html.escape(top_list(sector, "sector", 7))}

🚀 <b>전일 대비 급상승 섹터</b>
{html.escape(top_list(rising_sector, "sector", 5))}

🅰️ <b>뉴스 지속력 A등급</b>
{html.escape(top_list(grade_a, "sector", 5))}

📈 <b>섹터 ETF RS</b>
{html.escape(top_list(etf, "ETF명", 7))}

🏢 <b>관련 RS 종목</b>
{html.escape(top_list(stock_rs, "종목명", 10))}

🎯 <b>종가베팅 후보</b>
{chr(10).join(close_lines)}

📰 <b>조회수 상위 뉴스 TOP5</b>
{make_top5_lines(top_news)}

📑 <b>조회수 상위 리포트 TOP5</b>
{make_top5_lines(top_report)}

🌍 <b>조회수 상위 외신 뉴스 TOP5</b>
{make_top5_lines(top_foreign)}

✅ <b>체크포인트</b>
- 최근구간 재등장 여부
- 전일 대비 ΔRank 급상승
- ETF RS 상위
- 종목 RS 상위
- 거래대금 유지
- VWAP 위 유지
"""
    return msg.strip()

def build_close_bet_short_message(result):
    close_bet = result.get("CLOSE_BET_CANDIDATE", pd.DataFrame())
    exclude = result.get("CLOSE_BET_EXCLUDE", pd.DataFrame())
    pre_market = result.get("PRE_MARKET_CHECKLIST", pd.DataFrame())

    now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M")

    lines = []
    if close_bet is not None and not close_bet.empty:
        for _, r in close_bet.head(10).iterrows():
            lines.append(
                f"{r.get('순위')}. {html.escape(str(r.get('종목명')))} / {html.escape(str(r.get('섹터')))} / {r.get('종가베팅점수')}점"
            )
    else:
        lines.append("후보 없음")

    exclude_lines = []
    if exclude is not None and not exclude.empty:
        for _, r in exclude.head(5).iterrows():
            exclude_lines.append(
                f"- {html.escape(str(r.get('종목명')))}: {html.escape(str(r.get('제외사유')))}"
            )
    else:
        exclude_lines.append("- 제외 후보 없음")

    checklist_lines = []
    if pre_market is not None and not pre_market.empty:
        for _, r in pre_market.head(4).iterrows():
            checklist_lines.append(
                f"- {html.escape(str(r.get('체크항목')))}"
            )
    else:
        checklist_lines.append("- 장전 체크리스트 없음")

    msg = f"""
🎯 <b>종가베팅 후보 압축</b>
기준: {now_str}

<b>후보 TOP10</b>
{chr(10).join(lines)}

⚠️ <b>제외 체크</b>
{chr(10).join(exclude_lines)}

🌅 <b>다음 장전 체크</b>
{chr(10).join(checklist_lines)}

✅ <b>최종 확인</b>
- VWAP 위 유지
- 거래대금 유지
- ETF RS 약하지 않을 것
- 종목 20일선 위
"""
    return msg.strip()

def send_telegram_message(text):
    if not SEND_BOT_TOKEN or "여기에" in SEND_BOT_TOKEN:
        print("[SKIP] SEND_BOT_TOKEN 미입력")
        return

    if not SEND_CHAT_ID or "여기에" in SEND_CHAT_ID:
        print("[SKIP] SEND_CHAT_ID 미입력")
        return

    url = f"https://api.telegram.org/bot{SEND_BOT_TOKEN}/sendMessage"

    payload = {
        "chat_id": SEND_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }

    r = requests.post(url, json=payload, timeout=30)

    try:
        data = r.json()
    except:
        print("[ERROR] 텔레그램 응답 파싱 실패:", r.text)
        return

    if not data.get("ok"):
        print("[ERROR] 텔레그램 전송 실패:", data)
    else:
        print("[OK] 텔레그램 채널 전송 완료")

# ============================================================
# 12. 실행
# ============================================================

async def main():
    print("[0] 전일 섹터 순위 로드")
    prev_sector_rank = load_prev_sheet("섹터_지속력")

    print("[1] 텔레그램 뉴스 수집 시작")
    df, err_df, channel_df = await fetch_telegram_news()

    print(f"[2] 자동 선택 채널 수: {0 if channel_df is None else len(channel_df)}건")
    print(f"[3] 수집 뉴스 수: {len(df)}건")
    print(f"[4] 수집 오류 채널 수: {len(err_df)}건")

    print("[5] 뉴스 + ETF RS + 종가베팅 분석")
    result = analyze_news(df, err_df, channel_df, prev_sector_rank)

    print("[6] Google Sheets 저장")
    save_all_to_sheets(result)

    print("[7] 텔레그램 1차 전체 요약 전송")
    msg = build_telegram_summary_message(result)
    send_telegram_message(msg)

    time.sleep(1)

    print("[8] 텔레그램 2차 종가베팅 압축 전송")
    short_msg = build_close_bet_short_message(result)
    send_telegram_message(short_msg)

    print("[완료] 현재 기준 뉴스 / ΔRank / 등급 / 제외조건 / 장전체크 / 종가베팅 전송 완료")

if __name__ == "__main__":
    asyncio.run(main())