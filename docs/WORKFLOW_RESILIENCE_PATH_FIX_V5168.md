# v5.168 Workflow Resilience / Settings Path Fix

- `reports/`, `debug/`, `logs/`, `history/`, cache/temp/output 등 AgentStudio 런타임 산출물을 다음 프로젝트 분석/Code Generation Context에서 제외합니다.
- 기존 design bundle에 runtime 진단 파일이 target/existing 파일로 남아 있어도 Workflow 시작 시 제거합니다.
- Settings Plan의 `app/...` 경로를 File Plan의 `backend/app/...` canonical 경로로 자동 정규화합니다.
- Code Generation이 Settings 파일을 이미 생성했다면 Settings Generator의 중복 LLM 호출을 생략합니다.
- Settings 존재 검증과 실패 진단의 planned/actual 비교는 경로 대소문자를 안전하게 처리합니다.
- Ollama 기반 로컬 로그 triage가 연결되지 않아도 deterministic fallback으로 GPT 디버깅 단계가 계속될 수 있게 합니다.
- Settings Generator/Debug 오류는 `WORKFLOW_EXCEPTION`으로 덮어쓰지 않고 명시적인 상태로 종료합니다.
- Health: `5.168 / WorkflowResiliencePathFix`.
