# v5.301 Frontend TypeScript NotebookEditor Migration

## 목적

v5.300에서 Viewer/Notebook renderer/pure helper를 TypeScript로 분리한 다음 단계로, `App.jsx` 내부의 Jupyter Notebook 핵심 편집기인 `NotebookEditor`를 독립 `NotebookEditor.tsx` 컴포넌트로 이동합니다.

이번 단계는 기능 변경이 아니라 **타입 경계 확립과 모놀리식 App 축소**가 목적입니다. Terminal, DB Browser, Redis, Firestore, Supabase, LLM, MCP 본체는 구조 변경하지 않습니다.

## 이동된 코드

- `src/components/notebook/NotebookEditor.tsx`
  - Notebook JSON 유효성 화면
  - Code/Markdown/Raw cell 렌더링
  - Monaco cell editor instance 관리
  - cell selection 기억/선택 실행
  - 단일 셀/전체 셀 실행
  - Python 실행 중지
  - execution count/output 적용
  - cell 추가/삭제/출력 지우기
  - Notebook 내부 스크롤 boundary handoff
  - Notebook controller ref 제공

## 추가/강화된 타입

`src/types/notebook.ts`에 다음 contract를 추가했습니다.

- `NotebookExecutionRequest`
- `NotebookExecutionResult`
- `NotebookDependencyDiagnostic`
- `NotebookEditorController`
- Notebook cell `id`

`NotebookEditor.tsx` 내부에는 Monaco 전체 API를 임의 `any`로 노출하지 않고, 현재 Notebook이 실제 사용하는 editor/model/selection/layout 최소 contract를 별도로 정의했습니다.

## 회귀 방지 원칙

- v5.300의 Notebook UI className/DOM 구조를 유지합니다.
- Notebook Cell 실행/선택 실행/전체 실행/실행 중지 흐름을 유지합니다.
- Python kernel 검증 및 dependency diagnostic 출력 흐름을 유지합니다.
- Markdown preview/edit, Raw cell, output rendering을 유지합니다.
- Notebook 실행 Backend API 구현은 `App.jsx`에 그대로 남겨 이번 단계에서 Terminal/SQL/Python execution orchestration을 변경하지 않습니다.
- `NotebookEditor` 이후 `App.jsx` 본문은 v5.300과 동일하게 유지합니다.

## 검증

- `NotebookEditor.tsx` + Notebook TS 모듈 strict/noUncheckedIndexedAccess TypeScript check 통과
- 전체 현재 Frontend TS/TSX + `App.jsx(checkJs=false)` compiler parse/type check 통과
- `App.jsx`의 `StatusDot` 이후 EOF가 v5.300과 동일함을 비교 검증
- Backend Python `compileall` 통과
- Frontend/Backend/SYSTEM_ADMIN version gate `5.301` 동기화
- `styles.css`, runtime config 변경 없음 검증
- ZIP 비밀정보/캐시 제외 및 무결성 검사

현재 실행 환경은 npm registry 접근이 제한되어 실제 dependency install 기반 `npm run build`는 수행하지 못할 수 있습니다. Windows 기준 실행 환경에서는 `SYSTEM_ADMIN.cmd`가 `tsc -b && vite build`를 수행하므로 최종 production build를 다시 확인합니다.

## 다음 단계

Phase 4에서는 TypeScript 전환 난이도가 낮은 공통 UI/Report/Architecture/LLM panel 영역을 먼저 분리하는 것이 안전합니다. DB Browser/Terminal처럼 상태 결합도가 높은 IDE domain은 공통 panel 분리 이후 domain type을 먼저 정의한 다음 단계적으로 이동합니다.
