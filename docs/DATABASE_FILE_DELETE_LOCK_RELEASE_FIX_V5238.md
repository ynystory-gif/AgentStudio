# Database File Delete Lock Release Fix v5.238

## 문제
Windows에서 프로젝트의 `.db` SQLite 파일을 삭제할 때 `WinError 32`가 발생할 수 있었다. AgentStudio SQL Workspace의 지속 SQLite 연결 또는 F5/F8/Notebook의 지속 Python Worker가 해당 DB 파일을 열고 있으면 Windows가 파일 삭제를 거부한다.

## 수정
- 일반 파일 삭제를 먼저 시도한다.
- `WinError 32/33` 공유 위반일 때만 AgentStudio가 소유한 잠금 복구를 수행한다.
- 삭제 대상과 동일한 SQLite DB를 SQL Workspace가 열고 있으면 해당 연결만 종료한다.
- 프로젝트의 지속 Python/Notebook Worker 세션을 모두 종료하고 프로세스 종료를 기다려 파일 핸들을 확실히 반환한다.
- 150ms 후 삭제를 한 번 재시도한다.
- 그래도 잠겨 있으면 외부 프로세스 잠금으로 판단하여 HTTP 409 `FILE_IN_USE`와 한국어 조치 안내를 반환한다. 임의의 외부 프로세스는 강제 종료하지 않는다.
- Frontend 삭제 확인 창은 raw Backend JSON 대신 사용자용 메시지를 표시한다.
- AgentStudio가 잠금을 해제해 삭제에 성공한 경우 어떤 내부 연결이 종료되었는지 알린다.

## 세션 영향
잠금 복구 과정에서 Python/Notebook 지속 세션이 종료될 수 있으므로 기존 변수/함수 상태는 초기화된다. 이는 실제 파일 잠금 오류가 발생했을 때만 수행된다.
