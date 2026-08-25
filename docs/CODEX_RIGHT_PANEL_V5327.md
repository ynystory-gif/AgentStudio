# v5.327 VS Code-style Codex Right Panel

AgentStudio Code workspace의 오른쪽 패널에서 OpenAI Codex를 IDE client로 직접 사용합니다.

## 연결 계층

`React CodexPanel → FastAPI /api/codex/* → CodexAppServerManager → codex app-server(stdio JSONL) → ChatGPT Codex`

## 보안 / 자원 원칙

- AgentStudio는 ChatGPT 비밀번호를 입력받거나 저장하지 않습니다.
- ChatGPT 로그인은 Codex 관리 OAuth로 처리합니다.
- Codex CLI가 없으면 자동 설치하지 않고 설치 명령만 제공합니다.
- app-server는 Codex 탭을 열 때 필요 시 1개만 시작하고 Backend 종료 시 정리합니다.
- command/file edit는 `unlessTrusted + workspaceWrite`를 사용하고 app-server가 보낸 승인 요청을 사용자에게 표시합니다.

## Backend API

- `GET /api/codex/status`
- `POST /api/codex/start`
- `POST /api/codex/login/chatgpt`
- `GET /api/codex/models`
- `GET /api/codex/threads`
- `POST /api/codex/thread/start`
- `POST /api/codex/thread/resume`
- `POST /api/codex/turn/start`
- `POST /api/codex/turn/interrupt`
- `POST /api/codex/approval`
- `WS /api/codex/events`
