# v5.166 Context Budget / Version Guard Fix

## 발생 원인

Agent Factory `code_generation` 단계에서 Coding Style 전체 규칙, 설계 Context, 인터뷰 원문,
기존 파일 Context가 한 요청에 중복 포함되어 OpenAI 128K Context Window를 초과할 수 있었습니다.
또 Frontend만 최신 파일로 교체되고 이전 Backend 프로세스가 남아 있으면 최신 UI가 이전
`/workflow/start` 구현을 호출하는 혼합 버전 실행이 가능했습니다.

## 수정

- Patch/Code Generation 입력을 문자 기준 보수 예산으로 자동 축약합니다.
- 요청/기존 파일/Coding Style/Code Template마다 독립 예산을 둡니다.
- 시작과 끝 지시는 유지하고 긴 중간 Context만 축약합니다.
- Context Overflow가 발생하면 더 작은 Emergency Context로 1회 자동 재시도합니다.
- Agent Workflow 설계 Context에서 Coding Style 전체 본문 중복을 제거하고 tag/rule id만 유지합니다.
- 인터뷰 원문은 확정 요구사항을 보조하는 12,000자 범위로 제한합니다.
- Code Generation 자체 실패는 `WORKFLOW_EXCEPTION` 대신 `CODE_GENERATION_FAILED`로 반환하여
  실제 실패 단계를 진단 화면에서 구분합니다.
- Frontend가 Agent 개발 시작 전에 `/api/health`의 Backend 버전을 확인합니다.
- Frontend v5.166 / Backend 다른 버전이면 개발 시작을 차단하고 재시작 안내를 표시합니다.
- SYSTEM_ADMIN이 `backend_console_runner.py` 부모/자식 프로세스 트리를 함께 종료합니다.
- Health Build: `ContextBudgetVersionGuardFix`, Version: `5.166`.

## 입력 예산

- 일반 Patch Message 총 문자 상한: 82,000자
- Emergency Patch Message 총 문자 상한: 44,000자
- 일반 요청 Context: 34,000자
- 기존 파일 Context: 22,000자
- Coding Style: 14,000자
- Code Template: 7,000자

문자 수는 토큰 수와 동일하지 않으므로 실제 모델 한도보다 충분히 보수적으로 설정합니다.
