# v5.222 Terminal Shift Arrow Selection Fix

- Terminal에서 `Shift+↑` / `Shift+↓`로 출력 텍스트 선택 영역을 한 줄씩 확장할 수 있습니다.
- Shift 조합은 PowerShell command history 이동으로 전달하지 않고 xterm selection으로 처리합니다.
- 선택한 텍스트는 기존 `Ctrl+C`로 시스템 클립보드에 복사할 수 있습니다.
- 일반 `↑` / `↓`는 기존 command history 탐색을 그대로 유지합니다.
- Shift 선택 중 새 입력을 시작하면 keyboard selection state를 종료합니다.
