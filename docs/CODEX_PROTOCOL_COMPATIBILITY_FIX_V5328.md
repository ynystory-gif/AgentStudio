# THEANOVA AgentStudio v5.328 - Codex Protocol Compatibility Fix

## 목적

`v5.327_VsCodeStyleCodexPanel`의 Codex app-server 직접 통합을 최신 v2 프로토콜 형태에 맞추고, 실제 turn 스트리밍 중 연결 안정성을 강화한다.

## Backend 변경

- `thread/start`, `thread/resume`: `approvalPolicy=untrusted`, `sandbox=workspace-write` 사용
- `thread/start`: reasoning effort를 `config.model_reasoning_effort`로 전달
- `turn/start`: `sandboxPolicy.type=workspaceWrite`와 `writableRoots`, `networkAccess`, `excludeTmpdirEnvVar`, `excludeSlashTmp` 명시
- model/list가 광고한 reasoning effort와 요청 effort 조합을 사전 검증
- app-server 종료 시 pending RPC 즉시 해제
- Windows 종료 시 app-server process tree 강제 정리
- 이전 app-server reader가 새 프로세스 상태를 덮어쓰지 못하도록 process instance race guard 적용

## Frontend 변경

- `supportedReasoningEfforts[].reasoningEffort`, `defaultReasoningEffort` 지원
- 지원하지 않는 effort를 자동 교정
- `item/tool/requestUserInput` 질문/선택지/직접 입력/비밀 입력 UI 지원
- `item/completed` final agentMessage fallback 반영
- 상태 변경에 따른 WebSocket 불필요 재연결 제거

## 회귀 검증

`backend/validate_codex_protocol_contract.py`로 Codex 실행 파일 없이 JSON-RPC 요청 shape를 검증한다.

```powershell
python backend/validate_codex_protocol_contract.py
node frontend/validate_frontend_contracts.cjs
python -m compileall -q backend/app
```

실제 Codex 설치 환경에서는 AgentStudio 실행 후 오른쪽 `Codex` 탭에서 ChatGPT 로그인 → 새 대화 → 메시지 전송 → 명령/파일 승인 → 추가 입력 요청 순서로 확인한다.
