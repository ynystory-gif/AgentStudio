# v5.129 Compact RUN / REPORT Layout

문제:
`실행 결과` / `분석 리포트` 탭에서 workspace-top-pane이 기존 고정 높이를 유지하여
내용이 적어도 큰 세로 빈 공간이 발생했습니다.

개선:
- RUN / REPORT에서만 `compact-result-pane` 적용
- 상단 결과 영역을 콘텐츠 높이 기준으로 자동 축소
- 최대 높이는 viewport 기준으로 제한
- Dashboard의 `height:100%` 강제 제거
- 남는 공간은 하단 LLM 코드 편집 + 터미널 영역이 사용

일반 탭(DESIGN / WORKFLOW / CODE)의 기존 높이 동작은 변경하지 않습니다.
