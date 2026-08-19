# v5.195 Terminal Live Completion Filter Fix

- Ctrl+Space 자동완성 팝업을 현재 터미널 입력줄 위에 표시하여 사용자가 입력 중인 command/prompt를 계속 볼 수 있습니다.
- 자동완성 목록이 열린 상태에서도 문자 입력, Backspace, Delete, 좌/우/Home/End 편집을 계속할 수 있습니다.
- 입력 buffer/cursor가 바뀌면 85ms debounce 후 `/terminal/completions`를 다시 호출하여 현재 토큰에 맞는 후보만 실시간으로 갱신합니다.
- 사용자가 글자를 더 입력할수록 파일/폴더/PowerShell/PATH 후보가 즉시 줄어듭니다.
- ↑/↓ 선택, Tab/Enter 적용, Esc 닫기, 마우스 선택 동작은 유지합니다.
- 자동완성 팝업 header에 현재 token과 후보 수를 표시합니다.
