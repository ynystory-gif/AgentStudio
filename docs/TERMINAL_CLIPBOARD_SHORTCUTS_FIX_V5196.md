# v5.196 Terminal Clipboard Shortcuts Fix

- Ctrl+C: 터미널 텍스트가 선택되어 있으면 클립보드로 복사합니다.
- 선택 영역이 없으면 기존 PowerShell 인터럽트(^C) 동작을 유지합니다.
- Ctrl+V: 시스템 클립보드 텍스트를 현재 command buffer의 caret 위치에 붙여넣고 xterm 화면을 즉시 갱신합니다.
- 붙여넣은 텍스트는 Enter 전까지 Backend로 실행 전송되지 않습니다.
- 멀티라인 클립보드는 안전을 위해 한 PowerShell 입력줄의 공백으로 정규화합니다.
- 자동완성 팝업이 열린 상태에서 붙여넣어도 현재 입력값 기준으로 후보를 다시 갱신합니다.
