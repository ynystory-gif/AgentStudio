# v5.202 File System Sync + Persistence Fix

- 새 파일은 Editor tab을 열기 전에 Backend가 실제 디스크에 빈 파일을 생성하고 존재/mtime/size를 검증합니다.
- Backend가 반환한 canonical relative path를 사용하여 트리 선택과 Editor tab 경로가 실제 파일 경로와 일치합니다.
- Workspace가 열린 동안 1.5초 간격 lightweight filesystem snapshot으로 외부 파일 생성/수정/삭제를 감지합니다.
- 외부 신규 파일/삭제는 프로젝트 트리에 자동 반영합니다.
- 열린 파일이 외부에서 수정되었고 AgentStudio에 미저장 편집이 없으면 최신 디스크 내용을 자동 reload합니다.
- AgentStudio에 미저장 편집이 있는 파일이 외부에서 변경되면 자동 덮어쓰지 않고 conflict 표시를 남깁니다.
- 파일 저장 API는 editor가 마지막으로 읽은 mtime_ns를 보내 optimistic concurrency 검사를 수행하여 외부 변경을 실수로 덮어쓰는 것을 방지합니다.
- 외부에서 삭제된 열린 파일도 감지하여 탭에 표시하고 일반 저장으로 조용히 재생성하지 않습니다.
