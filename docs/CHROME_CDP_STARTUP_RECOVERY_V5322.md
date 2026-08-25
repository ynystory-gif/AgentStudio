# v5.322 Chrome CDP Startup Recovery Fix

외부 웹브라우저 CDP startup 안정화 버전입니다.

- loopback DevTools 요청 proxy 우회
- remote-debugging-port=0 + DevToolsActivePort 사용
- 고유 BrowserRuntime user-data-dir 사용
- Chrome/Edge 후보 자동 재시도
- startup log/ExitCode 진단
- BrowserProfile storage_state로 Cookie/LocalStorage 복원
- Frontend 다시 연결 버튼
