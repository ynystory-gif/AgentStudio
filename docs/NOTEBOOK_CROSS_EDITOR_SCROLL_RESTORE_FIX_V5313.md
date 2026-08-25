# v5.313 Notebook Cross-Editor Scroll Restore Fix

## 문제

Notebook A에서 아래쪽으로 스크롤한 뒤 다른 Notebook B로 전환했다가 A로 돌아오면 스크롤 위치가 유지되지만, SQL/일반 코드/다이어그램처럼 Notebook이 아닌 편집기를 열었다가 A로 돌아오면 NotebookEditor가 언마운트/재마운트되어 스크롤이 맨 위로 초기화되는 문제가 있었다.

## 수정

- Notebook 바깥 스크롤 위치를 `NotebookEditor` 컴포넌트 로컬 상태가 아니라 모듈 범위 Map에 저장한다.
- 저장 키는 `projectRoot + filePath`로 구성하여 프로젝트와 파일별로 독립 관리한다.
- `.ipynb → .sql/.py/.agentdiag.json → .ipynb`처럼 다른 편집기 종류를 거쳐도 원래 Notebook의 `scrollTop`을 복원한다.
- `onScroll`에서 위치를 즉시 기록하고, `useLayoutEffect`에서 초기 복원 후 Monaco/cell 레이아웃 안정화를 위해 animation frame과 짧은 settle restore를 수행한다.
- Notebook 간 전환과 Notebook이 아닌 편집기를 경유하는 전환 모두 같은 복원 경로를 사용한다.
- 브라우저 새로고침 후까지 영구 저장하지는 않으며 현재 AgentStudio 실행 세션 동안만 유지한다.

## 회귀 방지

`validate_frontend_contracts.cjs`에서 파일별 scroll cache, outer scroll capture, layout restore 계약을 검사한다.
