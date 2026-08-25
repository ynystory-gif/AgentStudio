# v5.323 Chrome CDP Diagnostics Log UI

외부 Chrome/Edge CDP 연결이 실패하면 AgentStudio 웹브라우저 오류 화면에 원인 진단 로그를 표시합니다.

표시 항목:
- 실패 stage/status/message/hint
- Chrome/Edge candidate 실행 파일
- 실제 launch command
- PID / ExitCode
- Runtime Profile 및 startup log 경로
- DevToolsActivePort 생성 여부와 내용
- CDP HTTP/WebSocket endpoint
- 마지막 오류와 Chrome startup log tail

진단 로그는 `%LOCALAPPDATA%\THEANOVA\AgentStudio\logs\browser_cdp_diagnostics.log`에도 누적 저장합니다.
