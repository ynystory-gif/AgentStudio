# v5.190 Terminal Bottom + MCP Add Fix

- xterm 표시 행 수에서 1행의 안전 여백을 확보하여 마지막 출력/PowerShell prompt/caret가 하단에 가려지지 않도록 수정했습니다.
- `.xterm-screen`에 강제하던 `height:100%`를 제거하여 xterm 자체 row 높이 계산을 존중합니다.
- xterm `write()` 완료 callback 이후 `scrollToBottom()`과 refresh를 수행해 실제 buffer 반영 뒤 마지막 줄을 표시합니다.
- Workspace 우측 `MCP 도구 > + 추가` 버튼이 잘못된 `tab` 상태를 변경하던 문제를 수정하고 실제 MCP 연결 추가 Dialog를 엽니다.
- MCP 연결 추가 Dialog에서 서버 이름, Streamable HTTP Endpoint, 신뢰 수준, 읽기/쓰기 확인 정책을 입력해 `/mcp/servers`에 등록합니다.
- 등록 후 `/mcp/servers/{id}/sync`를 호출해 Tool Registry를 동기화하고 MCP 도구 목록을 갱신합니다.
- MCP 관리 화면에도 `+ MCP 연결 추가`와 서버별 `Tool 동기화` 버튼을 제공합니다.
