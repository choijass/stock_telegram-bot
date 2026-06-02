from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

from zoneinfo import ZoneInfo


REPORT_DIR = Path("reports")
US_REPORT_PATH = REPORT_DIR / "us_market_report_1.txt"
KR_REPORT_PATH = REPORT_DIR / "korea_impact_report_2.txt"
TIMEOUT = 20


@dataclass
class Quote:
    symbol: str
    label: str
    price: float | None = None
    previous_close: float | None = None
    regular_change_pct: float | None = None
    post_price: float | None = None
    post_change_pct: float | None = None
    source_state: str = ""


INDEXES = {
    "^GSPC": "S&P500",
    "^IXIC": "나스닥",
    "^DJI": "다우",
    "^RUT": "러셀2000",
}

MACRO = {
    "^TNX": "미 10년물 금리",
    "DX-Y.NYB": "달러인덱스 DXY",
    "CL=F": "WTI",
    "BZ=F": "Brent",
}

SECTOR_ETFS = {
    "XLK": "기술주 XLK",
    "SMH": "반도체 SMH",
    "XLP": "필수소비재 XLP",
    "IWM": "소형주 IWM",
    "XLE": "에너지 XLE",
    "XLF": "금융 XLF",
}

FEATURE_TICKERS = {
    "NVDA": "엔비디아",
    "AVGO": "브로드컴",
    "AMD": "AMD",
    "MU": "마이크론",
    "DELL": "Dell",
    "HPE": "HPE",
    "SMCI": "Super Micro",
    "NTAP": "NetApp",
    "MSFT": "마이크로소프트",
    "AAPL": "애플",
    "GOOGL": "알파벳",
    "CRWD": "CrowdStrike",
    "PANW": "Palo Alto",
    "COST": "Costco",
    "WMT": "Walmart",
    "GAP": "Gap",
    "AEO": "American Eagle",
}


def yahoo_chart(symbol: str) -> dict:
    encoded = quote(symbol, safe="")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}"
    params = {
        "interval": "1m",
        "range": "1d",
        "includePrePost": "true",
    }
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }
    query = "&".join(f"{key}={quote(value, safe='')}" for key, value in params.items())
    request = Request(f"{url}?{query}", headers=headers)
    with urlopen(request, timeout=TIMEOUT) as response:
        data = json.loads(response.read().decode("utf-8"))
    result = data.get("chart", {}).get("result") or []
    if not result:
        raise RuntimeError(data.get("chart", {}).get("error") or f"no data for {symbol}")
    return result[0]


def to_float(value) -> float | None:
    try:
        if value is None:
            return None
        value = float(value)
        if math.isnan(value):
            return None
        return value
    except (TypeError, ValueError):
        return None


def pct(price: float | None, base: float | None) -> float | None:
    if price is None or base in (None, 0):
        return None
    return (price / base - 1) * 100


def latest_close(result: dict) -> float | None:
    closes = result.get("indicators", {}).get("quote", [{}])[0].get("close") or []
    for value in reversed(closes):
        value = to_float(value)
        if value is not None:
            return value
    return None


def fetch_quote(symbol: str, label: str) -> Quote:
    try:
        result = yahoo_chart(symbol)
        meta = result.get("meta", {})
        previous_close = to_float(meta.get("chartPreviousClose") or meta.get("previousClose"))
        regular_price = to_float(meta.get("regularMarketPrice")) or latest_close(result)
        post_price = to_float(meta.get("postMarketPrice") or meta.get("preMarketPrice"))
        state = str(meta.get("marketState") or "")
        return Quote(
            symbol=symbol,
            label=label,
            price=regular_price,
            previous_close=previous_close,
            regular_change_pct=pct(regular_price, previous_close),
            post_price=post_price,
            post_change_pct=pct(post_price, regular_price),
            source_state=state,
        )
    except Exception as exc:
        print(f"fetch failed {symbol}: {exc}")
        return Quote(symbol=symbol, label=label)


def fmt_price(value: float | None, digits: int = 2, prefix: str = "") -> str:
    if value is None:
        return "확인불가"
    return f"{prefix}{value:,.{digits}f}"


def fmt_pct(value: float | None) -> str:
    if value is None:
        return "확인불가"
    return f"{value:+.2f}%"


def stars(change_pct: float | None, important: bool = False) -> str:
    if important:
        return "★★★★★"
    if change_pct is None:
        return "★★☆☆☆"
    absolute = abs(change_pct)
    if absolute >= 8:
        return "★★★★★"
    if absolute >= 4:
        return "★★★★☆"
    if absolute >= 2:
        return "★★★☆☆"
    return "★★☆☆☆"


def trend_word(change_pct: float | None) -> str:
    if change_pct is None:
        return "확인 필요"
    if change_pct >= 2:
        return "강세"
    if change_pct > 0:
        return "상승"
    if change_pct <= -2:
        return "약세"
    return "보합권"


def market_summary(indexes: dict[str, Quote], sectors: dict[str, Quote]) -> list[str]:
    spx = indexes["^GSPC"].regular_change_pct
    nasdaq = indexes["^IXIC"].regular_change_pct
    smh = sectors["SMH"].regular_change_pct
    xlk = sectors["XLK"].regular_change_pct
    iwm = sectors["IWM"].regular_change_pct

    lines = []
    if (spx or 0) > 0 and (nasdaq or 0) > 0:
        lines.append("미국 증시 상승 마감")
    elif (spx or 0) < 0 and (nasdaq or 0) < 0:
        lines.append("미국 증시 하락 마감")
    else:
        lines.append("미국 증시 혼조 마감")

    if (smh or 0) > 0.5 or (xlk or 0) > 0.5:
        lines.append("AI·반도체·기술주 수급 우위")
    elif (smh or 0) < -0.5 or (xlk or 0) < -0.5:
        lines.append("AI·반도체·기술주 차익실현")
    else:
        lines.append("기술주는 방향성 제한")

    if iwm is not None and spx is not None and iwm < spx - 0.5:
        lines.append("소형주는 상대적 약세")
    elif iwm is not None and spx is not None and iwm > spx + 0.5:
        lines.append("소형주로 매수 확산")

    return lines[:4]


def pick_features(quotes: dict[str, Quote]) -> list[Quote]:
    available = [q for q in quotes.values() if q.regular_change_pct is not None]
    winners = sorted(available, key=lambda q: q.regular_change_pct or 0, reverse=True)[:4]
    losers = sorted(available, key=lambda q: q.regular_change_pct or 0)[:3]
    seen = set()
    picked = []
    for quote in winners + losers:
        if quote.symbol not in seen:
            picked.append(quote)
            seen.add(quote.symbol)
    return picked


def feature_reason(q: Quote) -> str:
    symbol = q.symbol
    change = q.regular_change_pct or 0
    if symbol in {"NVDA", "AVGO", "AMD", "MU", "SMCI", "DELL", "HPE"}:
        base = "AI 서버·반도체 인프라 수급과 직접 연결"
    elif symbol in {"NTAP", "MSFT", "CRWD", "PANW"}:
        base = "데이터 인프라·클라우드·보안 소프트웨어 흐름 확인"
    elif symbol in {"AAPL", "GOOGL"}:
        base = "대형 기술주 수급과 AI 기대감 반영"
    elif symbol in {"COST", "WMT", "GAP", "AEO"}:
        base = "미국 소비·리테일 심리와 연결"
    else:
        base = "업종 대표주 흐름 확인"

    if change >= 2:
        return f"{base}. 강한 매수세로 다음 거래일 지속성은 중상, 단기 과열은 확인 필요."
    if change <= -2:
        return f"{base}. 약세가 뚜렷해 반등은 가능하지만 추세 회복 확인 필요."
    return f"{base}. 방향성은 제한적이며 후속 재료 확인 필요."


def build_us_report(
    indexes: dict[str, Quote],
    macro: dict[str, Quote],
    sectors: dict[str, Quote],
    features: list[Quote],
    now_kst: datetime,
) -> str:
    summary = market_summary(indexes, sectors)
    report_date = now_kst.strftime("%Y.%m.%d %H:%M KST")

    lines = [
        "📌 [미국장 데일리 리뷰]",
        f"기준: {report_date} 실시간/최근 거래 데이터",
        "",
        "🚨 핵심 요약",
        *[f"- {line}" for line in summary],
        "- 특징주는 주요 감시종목 내 등락률 상하위 중심",
        "",
        "📊 1. 주요 지수",
    ]

    for symbol, label in INDEXES.items():
        q = indexes[symbol]
        lines.append(f"{label}: {fmt_price(q.price)} / {fmt_pct(q.regular_change_pct)}")

    lines.extend(
        [
            "",
            "해석:",
            "지수 방향과 나스닥·러셀2000 괴리를 함께 확인. 대형 기술주 주도인지, 시장 폭이 넓어지는지가 핵심.",
            "",
            "💵 2. 금리 / 국채",
            f"미 10년물 금리: {fmt_price(macro['^TNX'].price, 2)}% / {fmt_pct(macro['^TNX'].regular_change_pct)}",
            "",
            "해석:",
            "금리 상승은 성장주 부담, 금리 하락은 기술주 밸류에이션 부담 완화 요인.",
            "",
            "💱 3. 환율",
            f"달러인덱스 DXY: {fmt_price(macro['DX-Y.NYB'].price)} / {fmt_pct(macro['DX-Y.NYB'].regular_change_pct)}",
            "",
            "🛢 4. 유가",
            f"WTI: {fmt_price(macro['CL=F'].price, prefix='$')} / {fmt_pct(macro['CL=F'].regular_change_pct)}",
            f"Brent: {fmt_price(macro['BZ=F'].price, prefix='$')} / {fmt_pct(macro['BZ=F'].regular_change_pct)}",
            "",
            "🏭 5. 섹터 / ETF",
        ]
    )

    for symbol, label in SECTOR_ETFS.items():
        q = sectors[symbol]
        lines.append(f"{label}: {trend_word(q.regular_change_pct)} / {fmt_price(q.price, prefix='$')} / {fmt_pct(q.regular_change_pct)}")

    lines.extend(["", "⭐ 6. 특징주"])
    for q in features:
        lines.extend(
            [
                "",
                f"{q.symbol} ({q.label})",
                f"정규장/현재: {fmt_price(q.price, prefix='$')} / {fmt_pct(q.regular_change_pct)}",
                f"시간외: {fmt_price(q.post_price, prefix='$')} / {fmt_pct(q.post_change_pct)}",
                f"중요도: {stars(q.regular_change_pct, q.symbol in {'NVDA', 'AVGO', 'DELL', 'HPE', 'SMCI'})}",
                f"내용: {feature_reason(q)}",
            ]
        )

    lines.extend(
        [
            "",
            "🗓 7. 예정 일정",
            "이번 주 확인: ISM, ADP 고용, 고용보고서, 주요 기술주 실적, 대형 테크 이벤트",
            "다음 핵심: 고용·물가 지표가 금리를 자극하는지, AI 인프라 실적 모멘텀이 이어지는지 확인.",
            "",
            "🧭 8. 종합의견",
            "단기 판단은 금리와 반도체 ETF가 같이 봐야 합니다.",
            "SMH·XLK가 강하고 10년물 금리가 안정되면 AI/기술주 지속성이 높아집니다.",
            "반대로 금리 상승과 SMH 약세가 동시에 나오면 급등주 추격보다 현금 비중과 눌림 확인이 유리합니다.",
        ]
    )
    return "\n".join(lines)


def build_kr_report(
    indexes: dict[str, Quote],
    sectors: dict[str, Quote],
    us_quotes: dict[str, Quote],
    now_kst: datetime,
) -> str:
    smh = sectors["SMH"].regular_change_pct
    xlk = sectors["XLK"].regular_change_pct
    iwm = sectors["IWM"].regular_change_pct
    ai_names = ["NVDA", "AVGO", "AMD", "MU", "DELL", "HPE", "SMCI"]
    ai_avg_values = [us_quotes[s].regular_change_pct for s in ai_names if us_quotes[s].regular_change_pct is not None]
    ai_avg = sum(ai_avg_values) / len(ai_avg_values) if ai_avg_values else None

    if (smh or 0) > 0.7 or (ai_avg or 0) > 1:
        semi_impact = "강한 긍정"
        semi_priority = "★★★★★"
        semi_comment = "미국 AI·반도체 수급이 우호적이라 한국 HBM·메모리 밸류체인으로 연결 가능성이 큼."
    elif (smh or 0) < -0.7 or (ai_avg or 0) < -1:
        semi_impact = "부정 / 관망"
        semi_priority = "★★★★☆"
        semi_comment = "미국 반도체 수급이 약해 한국 반도체도 시초가 변동성 또는 차익실현 가능성."
    else:
        semi_impact = "중립~긍정"
        semi_priority = "★★★★☆"
        semi_comment = "AI 모멘텀은 유지되지만 강한 추격보다 대형주 지지 확인이 필요."

    power_impact = "중상" if (xlk or 0) > 0 or (ai_avg or 0) > 0 else "중립"
    apple_impact = "중" if (us_quotes["AAPL"].regular_change_pct or 0) >= 0 else "중립"
    retail_impact = "중립~부정" if min(us_quotes["GAP"].regular_change_pct or 0, us_quotes["AEO"].regular_change_pct or 0) < -1 else "중립"

    report_date = now_kst.strftime("%Y.%m.%d %H:%M KST")
    lines = [
        "📌 [미국장 연계 한국주식 영향 리포트]",
        f"기준: {report_date} 실시간/최근 미국 데이터 연계",
        "",
        "🚨 핵심 요약",
        f"- 반도체 ETF SMH: {fmt_pct(smh)}",
        f"- 기술주 ETF XLK: {fmt_pct(xlk)}",
        f"- AI 인프라 감시종목 평균: {fmt_pct(ai_avg)}",
        f"- 러셀2000 IWM: {fmt_pct(iwm)}",
        "",
        "🔗 1. 미국장 핵심 연결고리",
        "미국장 데이터는 한국장 개장 전 HBM, 메모리, 반도체 장비, 전력기기, 애플 밸류체인의 1차 방향성 힌트입니다.",
        "특히 SMH·XLK·AI 서버주가 동시에 강하면 한국 반도체 대형주와 장비주 수급 확산 가능성이 커집니다.",
        "",
        "🔥 2. 직접 수혜 섹터: 반도체 / HBM / AI 서버",
        f"영향: {semi_impact}",
        f"중요도: {semi_priority}",
        "",
        "관심 종목:",
        "SK하이닉스, 삼성전자, 한미반도체, 이오테크닉스, 주성엔지니어링, 원익IPS, 리노공업, ISC",
        "",
        "관련 ETF:",
        "KODEX 반도체, TIGER 반도체, KODEX AI반도체핵심장비, TIGER AI반도체핵심공정",
        "",
        "해석:",
        semi_comment,
        "",
        "⭐ 3. 종목별 연결 분석",
        "",
        "SK하이닉스",
        f"영향: {semi_impact}",
        "중요도: ★★★★★",
        "내용: HBM 대표 수혜주. SMH와 AI 서버주가 강하면 한국장 1순위 확인 대상.",
        "",
        "삼성전자",
        f"영향: {semi_impact if semi_impact != '부정 / 관망' else '중립~부정'}",
        "중요도: ★★★★★",
        "내용: 메모리 업황과 HBM 기대가 같이 반영. 코스피 지수 방향에도 영향 큼.",
        "",
        "한미반도체",
        "영향: 긍정 / 변동성 주의" if semi_impact != "부정 / 관망" else "영향: 관망 / 차익실현 주의",
        "중요도: ★★★★☆",
        "내용: HBM 후공정 장비 대표주. 미국 AI 서버 수급이 강할 때 탄력적이나 단기 과열 확인 필요.",
        "",
        "리노공업 / ISC",
        "영향: 긍정" if semi_impact != "부정 / 관망" else "영향: 중립",
        "중요도: ★★★★☆",
        "내용: AI칩·고성능 반도체 테스트 부품 수혜.",
        "",
        "⚡ 4. 확산 수혜: 전력기기 / 데이터센터 인프라",
        f"영향: {power_impact}",
        "중요도: ★★★★☆",
        "",
        "관심 종목:",
        "HD현대일렉트릭, LS ELECTRIC, 효성중공업, 일진전기, 대한전선",
        "",
        "해석:",
        "AI 서버 수요가 유지되면 데이터센터 전력 수요 기대가 이어집니다. 반도체 이후 순환매 후보입니다.",
        "",
        "🍎 5. 이벤트 연계: Apple / 온디바이스 AI",
        f"영향: {apple_impact}",
        "중요도: ★★★☆☆",
        "",
        "관심 종목:",
        "LG이노텍, 비에이치, 삼성전기, LG디스플레이",
        "",
        f"해석: AAPL 등락률 {fmt_pct(us_quotes['AAPL'].regular_change_pct)}. 애플이 강하면 온디바이스 AI와 부품주 관심이 살아날 수 있음.",
        "",
        "⚠️ 6. 부정적 연결: 의류 / 소비재 / 유통",
        f"영향: {retail_impact}",
        "중요도: ★★★☆☆",
        "",
        "미국 관련주:",
        f"GAP {fmt_pct(us_quotes['GAP'].regular_change_pct)}, AEO {fmt_pct(us_quotes['AEO'].regular_change_pct)}",
        "",
        "보수적 관찰:",
        "영원무역, 한세실업, F&F, 신세계, 현대백화점",
        "",
        "📍 7. 한국장 관찰 우선순위",
        "1순위: SK하이닉스, 삼성전자",
        "2순위: 한미반도체, 리노공업, ISC",
        "3순위: HD현대일렉트릭, LS ELECTRIC, 효성중공업",
        "4순위: LG이노텍, 삼성전기",
        "주의: 의류 OEM, 백화점, 내수 소비재",
        "",
        "🧭 8. 종합의견",
        "한국장은 미국 반도체·기술주 강도와 금리 안정 여부를 같이 봐야 합니다.",
        "시초가 급등 추격보다 SK하이닉스·삼성전자가 지수를 받치는지, 이후 장비주·전력기기로 수급이 확산되는지 확인하는 전략이 유리합니다.",
    ]
    return "\n".join(lines)


def write_debug_snapshot(all_quotes: dict[str, Quote], now_kst: datetime) -> None:
    data = {
        "generated_at_kst": now_kst.isoformat(),
        "quotes": {
            symbol: {
                "label": quote.label,
                "price": quote.price,
                "previous_close": quote.previous_close,
                "regular_change_pct": quote.regular_change_pct,
                "post_price": quote.post_price,
                "post_change_pct": quote.post_change_pct,
                "source_state": quote.source_state,
            }
            for symbol, quote in all_quotes.items()
        },
    }
    (REPORT_DIR / "us_market_realtime_snapshot.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    now_kst = datetime.now(timezone.utc).astimezone(ZoneInfo("Asia/Seoul"))

    indexes = {symbol: fetch_quote(symbol, label) for symbol, label in INDEXES.items()}
    macro = {symbol: fetch_quote(symbol, label) for symbol, label in MACRO.items()}
    sectors = {symbol: fetch_quote(symbol, label) for symbol, label in SECTOR_ETFS.items()}
    us_quotes = {symbol: fetch_quote(symbol, label) for symbol, label in FEATURE_TICKERS.items()}
    all_quotes = {**indexes, **macro, **sectors, **us_quotes}
    valid_count = sum(1 for quote in all_quotes.values() if quote.price is not None)
    if valid_count < 10:
        raise SystemExit(f"not enough live US data fetched: {valid_count}/{len(all_quotes)}")

    features = pick_features(us_quotes)
    US_REPORT_PATH.write_text(
        build_us_report(indexes, macro, sectors, features, now_kst),
        encoding="utf-8",
    )
    KR_REPORT_PATH.write_text(
        build_kr_report(indexes, sectors, us_quotes, now_kst),
        encoding="utf-8",
    )
    write_debug_snapshot(all_quotes, now_kst)
    print(f"wrote {US_REPORT_PATH} and {KR_REPORT_PATH}")


if __name__ == "__main__":
    main()
