# v5.143 Vite HMR Stability Fix

## 증상

Chrome DevTools:

- `WebSocket connection to ws://127.0.0.1:5173/?token=... failed`
- `net::ERR_CONNECTION_RESET`
- `Unexpected response code: 400`
- `[vite] failed to connect to websocket`
- `styles.css net::ERR_SOCKET_NOT_CONNECTED`

이 오류는 React 컴포넌트의 일반 런타임 오류가 아니라
Vite 개발 서버/HMR WebSocket 연결이 끊겼다는 의미입니다.

## 변경

### Vite 설정
`vite.config.js`에서 다음 값을 하나의 runtime port로 통일했습니다.

- server.host
- server.port
- server.hmr.host
- server.hmr.port
- server.hmr.clientPort

### package.json
기존 `vite --host 127.0.0.1 --port 5173` 하드코딩을 제거했습니다.

이제 `SYSTEM_ADMIN.ps1`이 선택한 실제 Frontend port를 사용합니다.

### Frontend runner
`frontend/frontend_console_runner.cjs`를 추가했습니다.

Vite가 예기치 않게 종료되면 2초 후 자동 재시작합니다.
로그는 기존 `logs/frontend_console.log`에 계속 기록됩니다.

### SYSTEM_ADMIN
Frontend 실행 시 runner를 사용하고
`AGENTSTUDIO_FRONTEND_HOST/PORT` 환경변수를 Vite에 전달합니다.

Frontend Health Check 실패 시
`frontend_console.log` 마지막 80줄을 관리자 콘솔에 표시합니다.
