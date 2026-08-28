# v5.409 Responsive Notebook Toolbar Wrap

Notebook 상단의 북마크/코드/Markdown/출력 버튼이 좌우 분할 화면에서 좁아질 때 한 줄에 강제로 압축되던 문제를 수정합니다.

- `.notebook-editor-shell`을 CSS inline-size container로 지정
- Notebook toolbar와 action 영역에 flex-wrap 적용
- 액션 버튼은 `white-space: nowrap` / `flex: 0 0 auto`로 글자 찌그러짐 방지
- pane 폭 760px 이하: Notebook 정보와 action을 자동 2행 배치
- pane 폭 520px 이하: bookmark navigation도 한 행을 점유하면서 내부 wrap 허용
- viewport가 넓어도 split pane이 좁으면 container query가 즉시 반응
