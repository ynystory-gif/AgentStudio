# v5.380 Codex Usage Settings Popover

## 목적

오른쪽 Codex 패널의 `⚙` 버튼을 눌렀을 때 ChatGPT 계정 메뉴처럼 현재 Codex 구독 사용량을 빠르게 확인할 수 있도록 합니다.

## 동작

- 설정 팝오버를 열면 `/codex/rate-limits?force=true`를 호출해 Codex app-server의 공식 Rate Limit 정보를 즉시 갱신합니다.
- 300분 Window는 `5시간`, 10080분 Window는 `1주`로 표시합니다.
- `usedPercent`를 남은 비율로 변환하여 `100 - usedPercent` 값을 표시합니다.
- 짧은 Window의 초기화는 로컬 시각(예: `오후 6:13`), 하루 이상 Window의 초기화는 날짜(예: `9월 1일`)로 표시합니다.
- Rate Limit Reset Credit이 제공되면 `재설정 N회 가능` 항목을 표시합니다.
- 기존 CLI, PID, 프로젝트, 현재 파일 정보는 `Codex 상세 정보` 접기 영역으로 유지합니다.

## 데이터 출처

AgentStudio Backend가 이미 연결 중인 `codex app-server`의 `account/rateLimits/read` 응답만 사용하며 별도 추정 사용량을 만들지 않습니다.
