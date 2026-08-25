# v5.333 Idle Disk I/O Native File Watcher Fix

AgentStudio WORKSPACE가 열려 있기만 해도 1.5초마다 `/files/snapshot`이 프로젝트 전체를 순회하고 열린 파일을 SHA-256으로 다시 읽던 폴링을 제거했다.

Backend `/api/files/watch` WebSocket은 `watchfiles`를 사용해 Windows에서 native filesystem notification을 수신한다. 변경이 없으면 파일 트리를 순회하거나 파일 본문을 읽지 않는다.

Frontend는 실제 added/modified/deleted 이벤트가 들어온 경로만 처리한다. 추가/삭제 시 프로젝트 트리를 갱신하고, 열린 파일의 실제 변경 여부는 이벤트가 발생한 파일에 대해서만 SHA-256으로 확인한다. Dirty editor는 기존과 동일하게 충돌 보호를 유지한다.

Watcher 재연결 시에는 놓친 변경을 보정하기 위해 트리와 열린 파일을 한 번만 재검증한다.
