# v5.130 TRUE Compact Top Pane Fix

이전 v5.129는 Dashboard 내부 높이만 줄였기 때문에,
상위 `workspace-top-pane`의 flex/height 규칙이 남는 세로 공간을 계속 차지했습니다.

이번 수정:
- RUN/REPORT의 `workspace-top-pane`을 `flex: 0 0 auto`
- `height:auto`
- `min-height:0`
- `max-height:none`
- Dashboard wrapper도 `height:auto`
- 하단 `workspace-bottom-grid`가 남은 화면을 전부 사용하도록 변경

즉 상단은 실제 콘텐츠 높이만 사용하고,
남는 세로 공간은 LLM 코드 편집 + 터미널 영역이 사용합니다.
