## v5.307 TypeScript System Runtime UI Migration

Frontend TypeScript Phase 7. v5.306 Terminal/WebSocket migration을 기반으로 System / Settings / Runtime 표시 계층을 단계적으로 TypeScript로 분리했습니다.

- 서비스 포트 설정 UI → `src/components/system/SystemRuntimePanels.tsx`
- AgentStudio Runtime DB / Supabase 설정 UI → `SystemRuntimePanels.tsx`
- Ollama Runtime 상태/실행/중지/설치 UI → `SystemRuntimePanels.tsx`
- 시스템 상태 요약 UI → `SystemRuntimePanels.tsx`
- System/Runtime 계약 타입 → `src/types/system.ts`
- 실제 Backend API orchestration, 비밀번호 ref, 설정 저장/테스트 로직은 `App.jsx`에 유지하여 회귀 범위를 제한
- v5.306의 Notebook/DB Browser/Terminal TypeScript 전환과 SystemAdmin UTF-8 BOM self-heal 유지

### 이전 버전 메모

## v5.306 TypeScript Terminal WebSocket Migration

v5.305를 기반으로 Frontend TypeScript Phase 6를 진행했습니다.

- 멀티 터미널 탭/이름변경/닫기/재시작/실행정지/Clear UI를 `src/components/terminal/TerminalPanel.tsx`로 분리했습니다.
- 터미널 오류 상세, 프로젝트 `.venv` 상태, xterm container, 자동완성 popup을 TypeScript 컴포넌트로 이동했습니다.
- Terminal session/process/error/completion/WebSocket 계약 타입을 `src/types/terminal.ts`에 추가했습니다.
- WebSocket 수신 JSON parse와 `input`/`command`/`interrupt`/`clear` 송신 serialization을 `src/utils/terminal.ts`의 typed boundary로 이동했습니다.
- 한글/CJK cell width 및 이전/다음 문자 helper를 `src/utils/terminal.ts`로 이동했습니다.
- xterm instance/FitAddon/WebSocket session lifecycle, Ctrl+C 종료 확인, command history/keyboard 처리와 Backend orchestration은 App.jsx에 그대로 유지했습니다.
- System/Runtime, MCP/Agent 본체 로직은 이번 단계에서 변경하지 않았습니다.
