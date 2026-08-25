## v5.345 Generated Agent Setup + Incremental Build Trace + Modular React TypeScript

### v5.345 변경 사항

- 생성된 Agent `SYSTEM_ADMIN.cmd`에 **초기 설정 Gate** 추가
  - DB / Redis / LLM / 외부 API 필수 설정이 없으면 `SETUP_REQUIRED (ExitCode=2)`
  - 설정 완료 전 pip/npm 설치, `app.main:app` import, FastAPI/Frontend 실행을 하지 않음
  - `.env`가 없으면 `.env.example` 기반으로 만들고 필수 Key를 준비한 뒤 편집기로 열어줌
- Agent 개발에 **실제 LangGraph Node 기반 생성 진행 로그** 추가
  - 추가 LLM 호출 없음
  - Token 단위 로그가 아니라 Node 완료 이벤트만 메모리/WebSocket으로 전달
- 재작업에 **Incremental Regeneration** 추가
  - `FULL_REUSE`: 변경 없음 → 이전 설계 재사용, 설계 LLM 0회
  - `PARTIAL_REVISE`: 변경된 요구사항 영향 섹션/파일만 재설계·수정
  - `FULL_REDESIGN`: 목적/Workflow/Architecture가 크게 변하면 전체 재설계
- DB 변경은 증분 모드에서도 고성능 `Codex → OpenAI → Ollama` 설계 + 기존 DB Validator 유지
- As-Built Architecture는 Source Fingerprint로 변경 여부를 확인해 의미 분석 LLM 재호출을 줄임
- 생성 대상 Agent가 **React + TypeScript**를 요구하면 `.tsx/.ts` Frontend 계약을 강제
  - `App.tsx`, `main.tsx`, `services/api.ts` 사용
  - `App.jsx`, `main.jsx`, `services/api.js` 생성 시 완료 검증 실패
  - `App.tsx`는 Route/Layout/Page 조립만 담당하고 대형 단일 파일 UI 금지
- 생성 Agent React UI를 기본 분리 구조로 계획
  - `layouts/AppLayout.tsx`
  - `components/layout/TopHeader.tsx`
  - `components/layout/Sidebar.tsx`
  - `components/layout/Footer.tsx`
  - `pages/HomePage.tsx` 및 업무별 Page
  - `services/api.ts`, `types/index.ts`, `styles/global.css`
- 기존 v5.344 우측 패널 / 실시간 DB Preview / Architecture State Fix 및 이전 기능 유지

자세한 내용: `docs/GENERATED_AGENT_SETUP_INCREMENTAL_BUILD_TRACE_V5345.md`

## v5.344 Right Panel Live DB + Architecture State Fix

### v5.344 변경 사항

- 우측 `Agent 제작 진행` 버튼을 `설계 검토 / 프로젝트 생성 / 개발 시작`으로 정리
- 요구사항 카드의 중복 Workflow 설계 버튼 제거
- 대화가 변경될 때만 갱신되는 `DB 실시간 설계 · 초안` 추가
  - Module / Entity / 관계 / DDL 탭
  - PostgreSQL / pgvector 기술 표시
  - Redis Session / Search Cache / Cart / Order Draft Key 초안 표시
  - 실시간 Preview는 LLM 없이 검증된 Module Registry로 생성
  - 최종 DB Entity/PK/FK는 설계 검토 단계에서 고성능 Provider + Validator로 확정
- Workflow 인터뷰 Context의 `\\n` 문자열 조합 오류를 실제 줄바꿈으로 수정
- Architecture fallback이 전체 Requirement State/대화 JSON을 `goal`로 출력하지 않도록 Backend Sanitizer 추가
- Architecture 화면을 Design / As-Built / Conformance lifecycle로 분리
- `NOT_STARTED`에서는 Raw JSON 대신 Empty State 표시
- Architecture component/description의 Raw State 문자열을 Frontend에서도 차단
- v5.343 Live Requirement Summary 및 기존 Codex/DB/Attachment/Native Watcher 기능 유지

자세한 내용: `docs/RIGHT_PANEL_LIVE_DB_ARCHITECTURE_STATE_FIX_V5344.md`
