# v5.229 TerminalVisibilityRefitFix

- SQL Workspace에서 `.sql` 파일을 열면 terminal pane이 숨겨집니다.
- SQL 파일에서 일반 코드 파일로 전환할 때 유지 중인 xterm 인스턴스가 숨김 상태의 geometry를 계속 사용해 prompt/cursor가 깨져 보일 수 있었습니다.
- `isSqlFile`/선택 파일 전환을 terminal layout restore effect dependency에 포함했습니다.
- terminal이 다시 visible이 된 뒤 2회의 requestAnimationFrame 및 후속 timer에서 fit/refresh/scrollToBottom을 수행합니다.
- terminal process/session/buffer는 재생성하지 않고 화면 geometry만 복구합니다.
