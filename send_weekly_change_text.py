from __future__ import annotations

import os
import textwrap

import requests


MESSAGE = """\
주말 종합 리포트 - 주간 변화

기간: 2026.05.25 ~ 2026.05.29
단, 2~4번 리포트에서 월요일 데이터는 시장 데이터상 05.25가 아니라 직전 거래일 05.22 기준으로 잡혔습니다.

[1번 SIGNAL]
포지션은 주간 내내 최상위 공격 유지입니다.

월: NORMAL / 위험신호 1 / 최상위 공격 / 주식 70~90, 현금 10~30 / 매수후보 0
- BRENT 위험신호, 반도체 4개 유지

화: NORMAL / 위험신호 1 / 최상위 공격 / 주식 70~90, 현금 10~30 / 매수후보 6
- 반도체, 지수, 반도체장비 확대

수: NORMAL / 위험신호 0 / 최상위 공격 / 주식 70~90, 현금 10~30 / 매수후보 5
- 위험신호 해소, IT서비스와 바이오 편입

목: NORMAL / 위험신호 0 / 최상위 공격 / 주식 70~90, 현금 10~30 / 매수후보 3
- 반도체 4개 확대, 2차전지 축소

금: NORMAL / 위험신호 1 / 최상위 공격 / 주식 70~90, 현금 10~30 / 매수후보 1
- KOSDAQ 20D DD 위험신호 재등장

금요일 포트 후보:
- SK하이닉스

금요일 교체 예상:
- NAVER, LG화학, 카카오, 현대건설, LG에너지솔루션, 포스코퓨처엠, KODEX 골드선물(H), PLUS K방산

[2번 ETF RS]
ETF 상대강도는 5G테크가 월~금 내내 1위입니다.

월 TOP3: 5G테크, 시스템반도체, 반도체
화 TOP3: 5G테크, 시스템반도체, 반도체
수 TOP3: 5G테크, 시스템반도체, 반도체
목 TOP3: 5G테크, 시스템반도체, 200
금 TOP3: 5G테크, 시스템반도체, 200

금요일 TOP5:
1. 5G테크 / 20D 79.7% / RS 45.2
2. 시스템반도체 / 20D 59.9% / RS 25.4
3. 200 / 20D 34.5% / RS 0.0
4. 코리아밸류업 / 20D 31.5% / RS -3.0
5. 반도체 / 20D 28.3% / RS -6.2

해석:
- 5G테크가 압도적 주도 ETF입니다.
- 시스템반도체도 2위 고정으로 강합니다.
- 일반 반도체 ETF는 초반 3위였지만 목~금 5위로 밀렸습니다.
- 지수형 200은 수요일부터 3위권으로 올라왔습니다.

[3번 주식트렌드]
섹터 트렌드는 주간 내내 반도체가 1위입니다.

월 TOP3: 반도체, 방산, 인터넷
화 TOP3: 반도체, 방산, 인터넷
수 TOP3: 반도체, 방산, 인터넷
목 TOP3: 반도체, 인터넷, 방산
금 TOP3: 반도체, 인터넷, 방산

금요일 TOP5:
1. 반도체 / 강관심 / Score 72.0 / 5D 12.8% / 20D 39.0%
2. 인터넷 / 강관심 / Score 57.9 / 5D 14.8% / 20D 18.7%
3. 방산 / 강관심 / Score 27.4 / 5D 5.7% / 20D 9.0%
4. AI/테크 / 관심 / Score 15.5 / 5D 1.7% / 20D 8.2%
5. 2차전지 / 관심 / Score 10.9 / 5D 6.6% / 20D -6.2%

해석:
- 반도체는 월~금 1위 고정입니다.
- 인터넷은 목요일부터 2위로 올라오며 후반 강세가 뚜렷합니다.
- 방산은 강관심 유지지만 주 후반 상대 순위는 3위로 밀렸습니다.
- 2차전지는 목요일 4위 진입 후 금요일 5위로 약화됐습니다.

[4번 ETF 20일선]
MA 리포트는 SK하이닉스와 5G테크가 1위 경쟁입니다.

월 TOP3: SK하이닉스, 5G테크, 시스템반도체
화 TOP3: 5G테크, SK하이닉스, 시스템반도체
수 TOP3: SK하이닉스, 5G테크, 자동차TOP3플러스
목 TOP3: SK하이닉스, 5G테크, 자동차TOP3플러스
금 TOP3: 5G테크, SK하이닉스, 자동차TOP3플러스

금요일 TOP5:
1. 5G테크 / 점수 97.7 / 20D 79.7% / 이평 위·위·위 / 정배열
2. SK하이닉스 / 점수 97.5 / 20D 79.5% / 이평 위·위·위 / 정배열
3. 자동차TOP3플러스 / 점수 84.2 / 20D 66.2% / 이평 위·위·위 / 정배열
4. 시스템반도체 / 점수 77.9 / 20D 59.9% / 이평 위·위·위 / 정배열
5. 코리아밸류업 / 점수 49.5 / 20D 31.5% / 이평 위·위·위 / 정배열

해석:
- 금요일 기준 TOP5 전부 위/위/위 + 정배열입니다.
- 5G테크와 SK하이닉스가 거의 같은 점수로 최상위권입니다.
- 자동차TOP3플러스가 수~금 3위 고정으로 강합니다.
- 시스템반도체도 주간 내내 3~4위권을 유지했습니다.

[전체 종합]
1. SIGNAL은 최상위 공격 유지
2. ETF RS는 5G테크 압도
3. 주식트렌드는 반도체 주도
4. ETF 20일선은 5G테크와 SK하이닉스 양강
5. 후반부에는 인터넷 섹터가 빠르게 올라옴
6. 2차전지는 일부 반등은 있었지만 SIGNAL 기준으로는 축소/교체 신호가 같이 나옴

다음 주 우선 관찰:
1. 5G테크
2. SK하이닉스
3. 시스템반도체
4. 반도체
5. 인터넷 섹터 관련 후보
보조 관찰: 자동차TOP3플러스, 코리아밸류업
"""


def chunks(text: str, limit: int = 3500) -> list[str]:
    parts: list[str] = []
    current = ""
    for block in textwrap.dedent(text).strip().split("\n\n"):
        candidate = block if not current else f"{current}\n\n{block}"
        if len(candidate) <= limit:
            current = candidate
        else:
            if current:
                parts.append(current)
            current = block
    if current:
        parts.append(current)
    return parts


def main() -> None:
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_CHAT_ID"]
    for idx, message in enumerate(chunks(MESSAGE), 1):
        prefix = f"[주말 종합 리포트 {idx}]\n\n" if len(chunks(MESSAGE)) > 1 else ""
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={
                "chat_id": chat_id,
                "text": prefix + message,
                "disable_web_page_preview": "true",
            },
            timeout=30,
        )
        response.raise_for_status()
        print(f"sent message part {idx}")


if __name__ == "__main__":
    main()
