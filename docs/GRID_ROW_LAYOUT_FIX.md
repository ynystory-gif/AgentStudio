# v5.131 Grid Row Layout Fix

실제 원인:
`workspace-main`은 CSS Grid이며 기존에는 3행만 정의했습니다.

```css
grid-template-rows: 42px minmax(0,1fr) 305px;
```

하지만 공통 Agent 진행 바가 추가된 뒤 실제 자식은 4개가 되었습니다.

```text
1. workspace-tabs
2. workspace-build-actions-wrap
3. workspace-top-pane
4. workspace-bottom-grid
```

Grid가 암시적 4번째 행을 만들면서 큰 세로 빈 공간이 발생했습니다.

수정:
일반 탭:
`42px auto minmax(0,1fr) 305px`

RUN / REPORT:
`42px auto auto minmax(260px,1fr)`

따라서 실행 결과/분석 리포트는 내용 높이만 사용하고
하단 코드 편집/터미널이 남은 화면을 사용합니다.
