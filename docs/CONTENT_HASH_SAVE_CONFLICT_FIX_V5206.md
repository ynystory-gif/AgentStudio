# v5.206 Content Hash Save Conflict Fix

- AgentStudio 내부에서 코드를 수정한 뒤 저장할 때 `expected_mtime_ns`만 비교하여 정상 저장도 HTTP 409 Conflict로 오인할 수 있던 문제를 수정했습니다.
- 파일을 읽을 때 SHA-256을 함께 반환하고 Editor가 마지막으로 읽은 콘텐츠 해시를 optimistic concurrency token으로 보관합니다.
- 저장 시 현재 디스크 파일의 SHA-256이 마지막 읽기 해시와 같으면 mtime이 달라도 정상 저장합니다.
- 실제 디스크 콘텐츠가 달라졌을 때만 `EXTERNAL_FILE_CHANGED` 409를 반환합니다.
- 외부 파일 watcher도 dirty 파일의 mtime/size가 달라졌을 때 SHA-256을 재확인하여 metadata-only 변경은 충돌로 표시하지 않습니다.
- 진짜 외부 수정 충돌이 저장 시 발견되면 기존 외부 변경 확인 Dialog/알림 흐름으로 연결합니다.
