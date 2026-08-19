# v5.182 Terminal Horizontal Overflow Visibility Fix

- CODE 탭 터미널 영역에서 prompt/command/output 한 줄이 길어지면 터미널 우측 내용이 잘리지 않도록 가로 스크롤이 항상 보이도록 수정했습니다.
- xterm 내부 viewport 뿐 아니라 외부 terminal wrap에도 `overflow-x: auto`를 적용하여 긴 줄을 끝까지 확인할 수 있습니다.
- 터미널이 필요한 최소 폭을 계산해 `--terminal-min-width` CSS 변수로 반영하고, 긴 프롬프트/명령/출력 시 xterm 실제 렌더 폭이 넓어지도록 보강했습니다.
- 자동 우측 이동 시 내부 viewport와 외부 wrap 스크롤을 함께 끝으로 이동하도록 보강했습니다.
