# v5.161 실패 진단 표시 + dotfile + stdio Plan 검증

## 수정 사항

### `.env.example`
Code Plan이 `env.example`로 반환해도 File Plan에 `.env.example`이 required이면
동일 파일로 정규화합니다. `.gitignore`, `.dockerignore`도 같은 방식의 alias를 지원합니다.

### stdio Code Plan
확정 요구가 MCP stdio이면 다음 코드가 Code Plan에 포함되는지 File Apply 전에 검사합니다.

- Flask import
- requests.get/post
- localhost:5000
- 127.0.0.1:5000
- app.run()

위반 시 `CODE_PLAN_ARCHITECTURE_FAILED`로 중단하고 실제 파일에는 적용하지 않습니다.

### Failed to fetch
Frontend API 오류에 다음 정보를 포함합니다.

- Backend 연결 실패인지 HTTP 오류인지
- 호출 URL
- HTTP status

Workflow fetch가 실패하면 `/workflow/diagnostics`로 프로젝트 폴더의
기존 실패 진단 자료를 다시 조회합니다.

### 실행 결과 화면
실패 시 표시:

- 실패 단계와 원인
- 파일 적용 실행 여부/개수
- 테스트 실행 여부/ReturnCode
- 디버그/복구 실행 여부/횟수
- failure_report.md
- workflow_state.json
- requirements_snapshot.json
- generated_artifacts.json
- debug_patch.json
- recovery_plan.md
- agent_factory.log
- workflow_execution.log
- test.log
- debug.log

각 파일은 `있음 / 없음 / 확인 불가`로 표시합니다.
