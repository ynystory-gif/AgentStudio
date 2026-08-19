# v5.207 External Save Conflict Choice Fix

- AgentStudio에 저장하지 않은 수정 내용이 있는 열린 파일을 외부 프로그램이 수정했을 때 기존 외부 변경 알림/로드 확인 흐름은 유지합니다.
- 사용자가 외부 파일 로드를 취소하고 AgentStudio의 로컬 편집 내용을 계속 유지한 상태에서 저장을 시도해 실제 디스크 내용과 충돌하면 저장 충돌 전용 Dialog를 표시합니다.
- 저장 충돌 Dialog는 `외부 파일 로드`, `외부 파일 무시하고 저장`, `취소` 3개 선택지를 제공합니다.
- `외부 파일 로드`는 디스크의 최신 파일을 다시 읽어 AgentStudio의 미저장 내용을 교체합니다.
- `외부 파일 무시하고 저장`은 사용자가 명시적으로 선택한 경우에만 `/file/write`에 `force=true`를 보내 현재 AgentStudio 내용을 디스크에 덮어씁니다.
- 강제 저장 성공 후 SHA-256/mtime baseline, dirty state, external conflict state, 외부 변경 알림을 새 저장 결과 기준으로 정리합니다.
- `취소`는 현재 AgentStudio 편집 내용과 디스크 파일을 모두 변경하지 않습니다.
