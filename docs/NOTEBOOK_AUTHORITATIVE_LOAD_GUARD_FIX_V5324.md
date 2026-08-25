# v5.324 Notebook Authoritative Load Guard Fix

Notebook/텍스트 파일을 비동기로 읽는 동안 `selected`가 먼저 바뀌면서 이전 또는 초기 Editor buffer가 새 파일 내용처럼 렌더링될 수 있던 회귀를 차단한다.

- 초기 Editor buffer는 빈 문자열이다.
- `fileLoadingPath`가 현재 파일이면 편집기 대신 로딩 상태를 표시한다.
- 열린 탭이라도 `editorFileContents`에 authoritative cache가 없으면 Backend `/files/read`를 다시 호출한다.
- 로딩 중 Ctrl+S와 Save As를 차단한다.
- `.ipynb` 저장은 Backend의 JSON validation/atomic replace 보호를 계속 사용한다.
