# 기관 수급·NXT 통합 보고서 — 추세 추종 텔레그램 채널

매주 월~금 18:10 KST 예약 발송을 위한 독립 GitHub Actions 워크플로입니다.

- 기존 `TELEGRAM_BOT_TOKEN` 재사용
- 새 저장소 Secret `TELEGRAM_TREND_CHAT_ID`에 **추세 추종 채널의 숫자 채팅 ID 또는 공개 채널 @username** 지정
- 해당 채널에 기존 봇을 관리자(메시지 게시 권한)로 초대
- 발송할 **실제 검증된 내용**은 `reports/institution_nxt/YYYY-MM-DD.txt`에 UTF-8 텍스트로 준비
- 입력 파일이 없거나 빈 경우 조용히 발송 건너뜀. 가짜 시장 데이터는 생성하지 않음
- `workflow_dispatch`를 통해 특정 날짜 보고서로 테스트 가능
- GitHub Actions의 cron은 실행이 늦을 수 있어 실시간 NXT 매매 시점 보장 불가. 정시 발송은 맥미니 스케줄러 권장
- ChatGPT 예약 보고서는 이 GitHub 파일에 자동으로 저장되지 않음. 별도 생성 파이프라인 필요
- 실제 Telegram 발송 검증 전에 PR을 합치거나 프로덕션으로 적용하지 말 것.
