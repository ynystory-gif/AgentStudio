# v5.188 Ollama Server Manager

THEANOVA AgentStudio는 Ollama를 별도 Agent로 만들지 않고 로컬 LLM Provider/Server로 관리합니다.

## 관리 흐름

1. Ollama 설치 여부/실행 파일 확인
2. `/api/version`, `/api/tags`로 실제 Server 연결 상태 확인
3. 설치되어 있으나 Server가 중지된 경우 `Ollama 실행` 제공
4. AgentStudio가 시작한 Server만 PID를 기록하여 안전하게 `Ollama 중지` 허용
5. 설치되지 않은 경우에만 `Ollama 설치` 표시
6. SYSTEM_ADMIN 시작 시 `OLLAMA_AUTO_START=true`이면 127.0.0.1:11434를 확인하고 필요 시 `ollama serve` 자동 실행
7. 이미 다른 프로세스가 Ollama Server를 실행 중이면 재실행/강제 종료하지 않음

## Runtime API

- `GET /api/settings/ollama/runtime/status`
- `POST /api/settings/ollama/runtime/start`
- `POST /api/settings/ollama/runtime/stop`

## 로그

- `backend/logs/ollama_server/ollama_server.log`
- `backend/logs/ollama_server/ollama_server.err.log`
- `backend/logs/ollama_server/managed_ollama.pid`
- 연결 테스트 실패 상세: `backend/logs/connection_tests/*_ollama_connection.log`
