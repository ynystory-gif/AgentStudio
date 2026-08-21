# THEANOVA AgentStudio Frontend TypeScript Migration Plan — v5.293 기준

## 1. v5.292 Frontend 실제 구조 분석

현재 Frontend source는 다음 4개 파일에 대부분 집중되어 있습니다.

| 파일 | 규모 | 역할 |
|---|---:|---|
| `src/App.jsx` | 약 652 KB / 16,988 lines | 거의 모든 UI, 상태, 이벤트, API 연결, Viewer, IDE 기능 |
| `src/styles.css` | 약 272 KB | 전체 IDE/System/Viewer 스타일 |
| `src/api.js` | 약 1.8 KB | FastAPI HTTP/WebSocket 공통 client |
| `src/main.jsx` | 약 0.2 KB | React bootstrap |

`App.jsx` 내부에는 약 30개의 React component function이 있고, 전체 파일 기준으로 약 233개의 `useState`, 45개의 `useEffect`, 50개의 `useRef`, 122개의 `api(...)` 호출이 존재합니다. 따라서 파일 전체를 한 번에 `.tsx`로 변경하면 props/state/ref/event/response 타입 오류가 동시에 폭발하면서 Notebook/Terminal/DB/LLM/MCP 회귀를 추적하기 어려워집니다.

### App.jsx 내부 주요 구간

- line 1~308: 공통 helper / Notebook parse-render helper
- line 309~983: Notebook / PDF / PPT-PPTX Viewer 계층
- line 984~2167: 공통 소형 UI + SystemPage
- line 2168~3140: Workflow / Report / Architecture / LLM panel
- line 3141~16988: IDE 본체

IDE 본체가 파일의 대부분을 차지하며 Terminal, Editor, Project, DB Browser, Redis, Firestore, Supabase, LLM, MCP, Workflow 상태가 서로 연결되어 있습니다.

## 2. 안전 전환 원칙

1. 기능 동작을 바꾸는 refactor와 TypeScript 전환을 같은 단계에서 섞지 않습니다.
2. 먼저 leaf component와 helper를 분리하고 타입을 고정합니다.
3. API response는 endpoint별 interface를 정의한 뒤 소비 component를 전환합니다.
4. Terminal/xterm, Monaco editor, Notebook controller ref는 DOM/ref/event 타입을 먼저 정의합니다.
5. `App.jsx`는 마지막에 전환합니다.
6. 각 단계마다 `npm run build` + 핵심 회귀 체크를 통과한 버전만 다음 기준 버전으로 사용합니다.

## 3. 단계별 전환 순서

### Phase 1 — v5.293 TypeScript Foundation

- Vite config TypeScript 전환
- tsconfig 도입
- `api.js` → `api.ts`
- 공통 runtime/API type 도입
- `main.jsx` → `main.tsx`
- `App.jsx` 유지
- SYSTEM_ADMIN TypeScript dependency 검사

### Phase 2 — Pure helper / Viewer 분리

- editor language/path helper
- notebook parse/format helper
- `NotebookMarkdown.tsx`
- `NotebookOutput.tsx`
- `PdfViewer.tsx`
- `PresentationViewer.tsx`

이 단계는 IDE global state 의존도가 가장 낮아 첫 `.tsx` component 전환 대상으로 적합합니다.

### Phase 3 — NotebookEditor 전환

- Notebook document/cell/output interface
- Python execution response type
- Notebook controller ref type
- keyboard/focus event type
- magic command 관련 type

v5.292의 Notebook magic + Terminal Backspace focus 수정사항을 회귀 기준으로 고정합니다.

### Phase 4 — Common UI / Report / Architecture / LLM panels

- StatusDot / StudioIcon / MiniBadge / SectionTitle
- Workflow diagram 계층
- Report/Metric/KeyValue 계층
- Architecture panels
- LLM catalog/history panels

### Phase 5 — SystemPage

- settings response/request type
- runtime status type
- database runtime/provider type
- Ollama/PostgreSQL/pgvector 관리 response type

### Phase 6 — IDE domain type 분리

다음 domain별 type을 먼저 생성한 뒤 IDE 내부를 단계적으로 이동합니다.

- Project / File tree / Editor tab
- Terminal session / completion / WebSocket event
- SQL profile / object explorer / query result
- Redis key/value/tree
- Firestore collection/document/field
- Supabase/PostgreSQL runtime
- LLM catalog/history/usage
- MCP server/tool registry
- Workflow state/progress/report
- Code edit/proposal/diff

### Phase 7 — IDE component 분리 및 `.tsx` 전환

대형 IDE를 기능 영역 단위 component/hook로 분리하고 props contract를 TypeScript로 고정합니다.

### Phase 8 — `App.jsx` → `App.tsx`

모든 하위 component가 `.tsx`가 된 뒤 routing shell만 남긴 상태에서 최종 전환합니다.

### Phase 9 — FastAPI OpenAPI 타입 연계

- `/openapi.json`을 기준으로 API contract generation 체계 도입
- Backend Pydantic schema와 Frontend TypeScript type drift 검증
- 수동 UI domain type과 generated API schema type의 경계 명확화

### Phase 10 — strict 완료

- `allowJs` 제거
- JavaScript source 0개 확인
- TypeScript strict build
- production build
- 전체 회귀 검증

## 4. 핵심 회귀 검증 대상

- Notebook: cell 편집/실행/중지, magic, writefile, working directory, Backspace/focus
- Terminal: 새 세션, CWD, multiline, paste, Ctrl+Space, selection, Backspace, clear
- Monaco: 언어 감지, 저장, diff, external file sync, CRLF
- DB: SQLite/PostgreSQL/Supabase 연결 및 object explorer
- Redis: key tree/value inspector/script
- Firestore: collection/document/field CRUD 및 script
- PPT/PPTX/PDF: inline preview와 Windows COM fallback
- LLM: catalog/history/runtime/status/chat/edit
- MCP: server/tool registry/connection
- Workflow: requirement collection, plan, progress, diagnostics, recovery

## 5. 완료 조건

TypeScript 전환 완료는 단순히 확장자가 `.tsx`가 되는 것이 아니라 아래 조건을 모두 만족할 때로 정의합니다.

- `src` 아래 React/logic source가 `.ts/.tsx`로 전환됨
- `allowJs` 제거 가능
- `npm run build` 성공
- SYSTEM_ADMIN에서 Backend/Frontend version gate 성공
- 기존 기능 회귀 테스트 성공
- FastAPI OpenAPI contract와 주요 Frontend API type 불일치 없음
## 6. v5.300 진행 상태

Phase 2의 첫 실제 `.tsx` component/helper 이동을 완료했습니다.

- 완료: `NotebookMarkdown` / `NotebookOutput` → `components/notebook/NotebookRenderers.tsx`
- 완료: `PdfViewer` / `PresentationViewer` → `components/viewers/DocumentViewers.tsx`
- 완료: editor language/model path/file preview helper → `utils/editor.ts`
- 완료: Notebook parse/SQL/result/kernel helper → `utils/notebook.ts`
- 완료: Notebook document/cell/output 공통 타입 → `types/notebook.ts`
- 유지: `App.jsx` (Phase 3 이후까지 단계적으로 축소)
- 다음: `NotebookEditor.tsx` + execution/controller/Monaco ref 타입 고정

`App.jsx` 전체를 한 번에 TSX로 바꾸지 않고, 각 이동 단계에서 import contract와 타입 검증을 먼저 통과한 뒤 다음 영역으로 진행합니다.

## 7. v5.301 진행 상태

Phase 3 `NotebookEditor` TypeScript 이동을 완료했습니다.

- 완료: `NotebookEditor` → `components/notebook/NotebookEditor.tsx`
- 완료: Notebook execution request/result/dependency diagnostic 타입
- 완료: Notebook controller ref 타입
- 완료: Monaco cell editor/model/selection 최소 contract 타입
- 완료: cell 실행/선택 실행/전체 실행/중지 상태 타입
- 유지: Python/SQL 실행 orchestration은 `App.jsx`에 그대로 유지하여 Terminal/DB 회귀 범위를 차단
- 유지: `StatusDot` 이후 App 본문은 v5.300과 동일
- 다음: Phase 4 공통 UI / Report / Architecture / LLM panel TypeScript 분리

현재 `App.jsx`를 마지막까지 유지하는 원칙은 동일하며, leaf/panel component를 먼저 TypeScript로 이동해 App의 상태 결합도를 단계적으로 낮춥니다.



## 8. v5.302 SYSTEM_ADMIN UTF-8 BOM hotfix

- TypeScript Phase 3 (`NotebookEditor.tsx`) 결과는 그대로 유지한다.
- Windows PowerShell 5.1이 한글이 포함된 UTF-8 no-BOM `.ps1`을 ANSI로 오해하여 ParserError를 내는 문제를 수정했다.
- `SYSTEM_ADMIN.ps1`은 UTF-8 with BOM으로 배포한다.
- `SYSTEM_ADMIN.cmd`는 실행 전 PS1 BOM을 검사하고, BOM이 없지만 유효한 UTF-8이면 UTF-8 BOM을 자동 복원한다.
- 다음 TypeScript 컴포넌트 분리는 v5.303에서 재개한다.


## 9. v5.303 runtimeInfo import regression hotfix

The v5.300 import rewrite accidentally omitted `runtimeInfo` from the `./api` named import. SystemPage and IDE render paths still called `runtimeInfo()`, causing a browser-time ReferenceError. v5.303 restores the import and adds a pre-build contract check.

## 10. v5.304 common / report / architecture / LLM migration

- `CommonUi.tsx`: StatusDot, StudioIcon, MiniBadge, SectionTitle
- `ReportComponents.tsx`: MetricCard, StatusBadge, ReportSection, KeyValueGrid, FileChangeList, WorkflowMiniMap
- `ArchitecturePanels.tsx`: generated Agent architecture + AgentStudio platform architecture
- `LlmCatalogPanel.tsx`: recent LLM request/response history + routing catalog
- `types/report.ts`: report, architecture, LLM payload contracts
- Legacy `App.jsx` continues to own DB Browser, Terminal, System/Runtime, MCP, workspace orchestration.
- The next migration target is the DB Browser family.

