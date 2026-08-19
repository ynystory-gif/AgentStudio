# v5.201 Terminal Scrollbar Visibility Fix

- 코드 편집기 하단 xterm 터미널의 세로 스크롤바를 항상 표시합니다.
- 터미널 전용 세로 스크롤바 폭을 14px로 확대했습니다.
- 어두운 터미널 배경과 구분되는 트랙 및 밝은 thumb 색상을 적용했습니다.
- hover/active/focus 상태에서 thumb 대비를 더 높여 마우스로 쉽게 잡을 수 있습니다.
- 최소 thumb 높이를 두어 로그가 길어져도 손잡이가 지나치게 작아 보이지 않도록 했습니다.
- 터미널 출력/입력/scrollback 로직은 변경하지 않고 스크롤 UI만 개선합니다.
