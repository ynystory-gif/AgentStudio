# v5.392 ValidationInfrastructureFallback

Agent 생성 파일과 검증 인프라 장애를 분리합니다.

## 주요 변경

- Codex Windows sandbox helper 오류를 provider 인프라 실패로 감지합니다.
- Code Generation / Patch / Multi-file / Debug Repair에서 Codex가 인프라 문제로 실패하면 OpenAI/Ollama fallback을 시도합니다.
- 생성 프로젝트는 수정하지 않고 파일 목록, Git 상태, Python compileall, Frontend build(--if-present) 결과를 로컬 fallback 근거로 수집합니다.
- Codex 실행 파일 경로, app-server 실행 명령, stderr tail, 마지막 runtime error를 진단 데이터에 보존합니다.
- 실제 테스트 실패가 확인되지 않은 상태에서 검증 인프라가 막히면 `DEBUG_STOPPED/FAILED` 대신 `VALIDATION_BLOCKED`로 종료합니다.
- `reports/failure_report.md`, `debug/debug_patch.json`, `logs/validation_fallback.json`에 fallback 근거를 저장합니다.
- 실행 결과 UI는 `Agent 생성 후 검증이 중단되었습니다.`로 표시하고 `검증 다시 실행`을 제공합니다.
