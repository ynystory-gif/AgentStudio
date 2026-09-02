# THEANOVA AgentStudio v5.492 - LiveTranscriptTextFileSave

- 메모 > 실시간 기록에 `파일 저장` 버튼 추가
- 현재 실시간 Transcript 전체를 프로젝트 `recordings/` 폴더의 UTF-8 `.txt` 파일로 저장
- `요약 파일 저장` 버튼은 현재 Transcript를 최신 내용으로 요약한 뒤 `.txt`로 저장
- 저장 성공 후 실제 절대 경로를 실시간 기록 화면에 표시
- 동일 초에 여러 번 저장하면 `_2`, `_3` 방식으로 충돌 없이 저장
- Backend 저장 경로는 기존 프로젝트 허용 경로 검사(`write_file`)를 그대로 사용
