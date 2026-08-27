# v5.383 AgentUILayoutRuntimePersistenceControls

## 목적

Agent 서비스가 실행 중일 때 사용자가 다른 메뉴/탭으로 이동해도 Backend Agent Runtime은 계속 실행되고, 원래 화면으로 돌아오면 진행 상태와 UI Context를 복원할 수 있도록 Layout 설정과 생성 규칙을 연결합니다.

## 플랫폼 고정 정책

- `agent_runtime_persistent = true`
- 메뉴/탭 이동 또는 React component unmount는 Agent run의 cancel/stop 신호가 아닙니다.
- Agent Runtime은 `session_id` / `run_id` 기반 Backend lifecycle로 관리합니다.
- WebSocket/SSE 재연결 시 현재 run 상태를 다시 조회하고 누락된 진행 이벤트를 재동기화합니다.

## Layout 설정

- `restore_screen_state`
- `restore_scroll_position`
- `restore_draft_input`
- `restore_selection_state`
- `screen_restore_mode`: `auto`, `keep_alive`, `state_rehydrate`
- `show_running_tasks`
- `runtime_status_position`: `top_statusbar`, `sidebar`, `right_panel`, `bottom_statusbar`, `floating_button`
- `notify_agent_complete`
- `notify_agent_failure`
- `run_item_navigate`

## 템플릿 기본값

- AI Chat Workspace / RAG Knowledge Workspace: 대화·입력·스크롤·선택 상태 복원을 기본 활성화합니다.
- Dashboard / Monitoring / MCP Console: 대시보드 필터·선택·스크롤 복원을 기본 활성화하고 입력 Draft 복원은 기본 비활성화합니다.
- Headless Agent: 화면 상태 복원은 비활성화하고 Backend Runtime 유지, 실행 상태 표시, 완료/실패 알림을 유지합니다.

## 생성 Agent 구현 규칙

Frontend는 실행 상태 store와 페이지 상태를 관리하고 Backend는 화면 lifecycle과 독립된 Agent Runtime을 유지합니다. 화면 복귀 시 REST 상태 재조회와 WebSocket/SSE 재연결을 통해 현재 진행률과 결과를 복원합니다.
