# KRX 14:00 / 15:30 전달 구조 및 Mac mini 설치

## 확인된 문제
2026-10-08 14:00 예약 실행은 runner 로그상 20:51:31 KST에 시작했고 20:55:40경 보고서가 출력됐다. 15:30 예약 실행은 22:54:37에 runner가 시작했고 22:54:56에 보고서 프로그램이 시작됐다. 사용자가 제공한 run 생성시각과 합치면 지연은 프로그램 실행 이전 단계다. UTC cron은 올바르다. GitHub는 schedule 이벤트 지연/누락 가능성을 공식 문서에서 명시한다. 서비스 내부 원인이나 장애 여부는 이 로그로 확정할 수 없다.

기존 success는 프로세스 성공이다. sendMessage 응답의 ok/message_id를 저장하지 않아 텔레그램 수신 증거가 남지 않았다. 기존 watchdog은 schedule 트리거도 KRX 대상도 없었다.

## 적용 구조
- 기존 GitHub cron은 보조 경로로 유지한다.
- Mac cron은 1분마다 확인하고 13:55 / 15:25부터 명시적인 report_mode, report_date로 workflow_dispatch를 호출한다. runner가 먼저 준비되면 목표시각까지 기다린 다음 데이터를 수집한다. 목표시각 이전에는 발송하지 않는다.
- 준비 시간과 데이터 수집 시간 때문에 실제 도착은 목표시각 이후다. workflow_dispatch도 GitHub runner 대기열을 사용하므로 초 단위 정시 보장은 불가능하다. GitHub 장애까지 독립적으로 회피해야 한다면 Mac에서 수집/발송 프로그램 자체를 실행하는 별도 단계가 필요하다.
- Mac은 5분 간격으로 영수증을 재확인하며 활성 실행이 있으면 새 호출을 보류한다. GitHub watchdog도 5분마다 KRX 영수증을 확인한다. workflow success로 발송을 판정하지 않는다.
- 14시판은 14:00~14:15, 마감판은 15:30~16:00에서만 발송한다. 시간이 지나면 폐기하며 다음날 몰아서 보내지 않는다. 수집 중 창을 넘긴 경우에도 발송을 막는다. 14시판을 마감 데이터로 대체하지 않는다.
- 제목에 실제 수집 시작 시각과 예정시각을 표시한다. 현 데이터 제공자의 정규장/NXT 구분 및 정확한 15:30 스냅샷 보존은 별도 데이터 계약이 필요하다.
- 날짜/모드별 data/delivery/krx-YYYY-MM-DD-MODE.json에 분할 메시지 intent와 Telegram ok=true, message_id, chat_id, 응답시각을 저장한다. 모든 분할 메시지가 확인돼야 delivered가 된다. Telegram 서버 접수 증거이며 사용자의 열람 확인은 아니다.
- SHA를 사용하는 GitHub Contents 조건부 쓰기가 성공한 후에만 Telegram을 호출한다. 기록 저장 실패 시 발송하지 않는다. 확인된 분할 메시지는 재발송하지 않고 저장된 원문에서 이어간다.
- 응답 타임아웃/연결 끊김/수신 영수증 저장 실패는 sending 상태로 남겨 자동 재발송을 막는다. Bot API에는 멱등키가 없으므로 전달 누락과 중복을 동시에 완전히 제거할 수 없다. 불확실한 경우 중복 방지를 우선한다.

## Mac mini에서 실행
저장소를 이미 내려받았다면 해당 폴더에서 아래 명령을 실행한다.

```bash
brew install gh python
gh auth login
# 토큰/계정은 이 저장소에 Actions:write, Contents:read 권한 필요.
# 아래 설치기는 기존 다른 cron 항목을 보존한다.
git pull --ff-only origin main
bash scripts/install_mac_krx_cron.sh
crontab -l
```

저장소가 없다면 먼저:

```bash
git clone https://github.com/choijass/stock_telegram-bot.git
cd stock_telegram-bot
```

Mac은 로그인 상태에서 켜져 있고 인터넷 연결과 절전 해제가 필요하다. System Settings > Energy에서 자동 잠자기를 해제하거나, 항상 켜진 서버라면 아래 설정을 선택할 수 있다:

```bash
sudo pmset -a sleep 0
```

설치기는 한국시간을 코드에서 판단하므로 Mac 시간대가 달라도 동작한다. gh 인증은 macOS Keychain을 사용한다. cron에서 인증 접근 오류가 발생하면 로그를 확인한다. 토큰을 cron 명령줄에 직접 넣지 않는다.

```bash
tail -n 50 "$HOME/Library/Logs/krx-dispatch/cron.log"
```

설치 복사본 갱신: git pull 후 설치기를 다시 실행한다. 제거:

```bash
crontab -l | sed '/# krx-dispatch-managed$/d' | crontab -
```

## 운영 및 실패 확인
- 저장소 Actions에서 Run workflow 시 report_mode를 반드시 지정한다. report_date를 생략하면 KST 오늘이다. 과거 날짜나 창 밖 실행은 발송하지 않는다.
- 영수증은 저장소 data/delivery에 남고 실행 artifact results/delivery.json에도 저장된다. 영수증이 없다면 전달 완료로 취급하지 않는다.
- sending이 남으면 실제 Telegram 채널과 ledger의 분할 메시지를 대조한다. 접수가 확인되면 message_id를 넣고 sent로 수정한다. 미접수가 확실한 경우에만 rejected로 바꿔 발송창 내 재시도한다. 확인 없이 삭제하지 않는다.
- 주말은 건너뛴다. 기존처럼 KRX 공휴일 캘린더는 아직 연결돼 있지 않다.
- Mac 미설치/잠자기/토큰 오류는 이 원격 작업에서 해결하거나 확인할 수 없다. 설치 후 다음 거래일 실제 영수증과 도착 시각을 확인해야 한다.

## 검증
네트워크 발송 없이 단위 테스트로 늦은 창, UTF-16 메시지 길이, 중복 완료/불확실 상태, 명시적 API 거절, 타임아웃, intent 저장 실패, 정상 영수증을 확인한다. 실제 Telegram 발송과 Mac crontab 변경은 원격 작업에서 수행하지 않았다.

공식 예약 실행 설명: https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule
