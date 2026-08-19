# v5.179 Terminal Horizontal Scroll + Backspace Fix

- 긴 PowerShell prompt/command가 터미널 폭을 넘으면 xterm 열 수를 자동 확장하여 줄바꿈 대신 가로 스크롤을 사용합니다.
- 한 글자 입력 시 prompt 전체를 다시 그리지 않는 v5.178 동작을 유지합니다.
- Backspace는 로컬 command buffer를 기준으로 끝까지 삭제하며 wrap 경계에서 멈추지 않습니다.
- 한글/동아시아 문자의 display cell 폭을 2칸으로 계산하여 command line 폭을 확보합니다.
- 터미널 출력의 긴 라인도 필요한 열 수를 확장하여 가로 스크롤로 확인할 수 있습니다.
- Enter를 누르기 전에는 입력 문자를 Backend로 보내지 않으며, 완성 명령만 WebSocket으로 전송합니다.
