# v5.192 New Terminal Project Session Fix

- 코드 편집기에서 `+ 터미널`을 누르면 UI 탭만 만들지 않고 현재 선택 프로젝트의 root를 상속합니다.
- 새 세션은 고유 session id로 Backend PowerShell WebSocket을 연결하며 `.venv` 감지/활성화와 프로젝트 working directory를 그대로 사용합니다.
- React가 새 terminal DOM을 mount하고 xterm instance를 먼저 생성한 뒤 WebSocket을 연결하여 history/ready/prompt 메시지가 초기화 전에 도착해 유실되는 race condition을 방지합니다.
- 프로젝트가 선택되지 않은 상태에서 새 터미널 생성은 막고 사용자에게 프로젝트 선택을 안내합니다.
- 새 터미널 연결 완료 후 xterm refresh/scroll/focus를 수행해 PowerShell prompt가 즉시 보이도록 합니다.
