# v5.325 Browser Process Leak Guard

외부 CDP Browser가 startup 실패로 오인된 뒤 Chrome/Edge를 반복 생성하던 process leak을 차단한다.

핵심 변경:

1. ExitCode=0 + 동일 BrowserRuntime 자식 프로세스 존재 시 Chrome PID handoff로 인식하고 DevToolsActivePort를 계속 대기한다.
2. 실패 Runtime은 Windows에서 `taskkill /T /F` 및 command line scan으로 자식까지 정리하고 remaining=0을 확인한다.
3. passive endpoint(state/action/screenshot/stream)는 Chrome을 절대 시작하지 않는다.
4. startup 실패 circuit breaker는 사용자의 `다시 연결(force_restart)`에서만 해제한다.
5. Frontend WebSocket/state polling/resize는 ready 상태에서만 동작하고 startup 실패 후 자동 재시도하지 않는다.
6. Backend startup에서 이전 BrowserRuntime orphan 프로세스를 자동 회수한다.
