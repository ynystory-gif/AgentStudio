# v5.151 Failure Diagnostics

실패/중단 시 반드시 진단 자료를 프로젝트 폴더에 남깁니다.

실제 Agent 파일 0개이면 `FAILED_NO_ARTIFACTS`로 판정합니다.
`venv`, `.venv`, `logs`, `reports`, `debug`, `node_modules`, `.git`는 산출물 수에서 제외합니다.

생성 파일:
- `reports/failure_report.md`
- `reports/workflow_state.json`
- `reports/requirements_snapshot.json`
- `reports/generated_artifacts.json`
- `debug/debug_patch.json`
- `debug/recovery_plan.md`
- `logs/agent_factory.log`
- `logs/workflow_execution.log`
- `logs/test.log` (테스트 결과가 있을 때)
- `logs/debug.log` (디버그 이력이 있을 때)

실행 결과/분석 리포트에도 실패 단계, 실제 파일 수, 계획 파일 수, 원인, 진단 파일 경로를 표시합니다.
