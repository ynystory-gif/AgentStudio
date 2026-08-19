# v5.133 Workflow Requirement Coverage

## 목적

인터뷰에서 확정된 요구사항이 Target Agent Workflow에서 사라지거나
`파일 읽기`, `AI 요약` 같은 몇 개의 추상 노드로 과도하게 축약되는 문제를 개선합니다.

## 강화된 Workflow Designer 규칙

- Root 경로 제한 → 별도 validation + 거부 branch
- 확장자 allow-list → 별도 validation + 거부 branch
- MCP 사용 → Client / Transport / Server / Tool 책임 표시
- LLM 전환 가능 → Provider / Model 확인 단계
- React 결과 표시 → UI 단계
- 선택적 저장 → 저장 여부 decision
- txt/md 저장 → 저장 형식 단계
- Output 제한 → Output 경로 validation
- 외부 실패 → retry / failure policy

## Requirement Traceability

`target_agent_workflow.requirement_coverage`를 추가했습니다.

각 확정 요구사항이 어느 Workflow step에서 구현되는지 기록하고
Workflow 화면 하단의 `요구사항 반영 확인` 패널에서 확인할 수 있습니다.

LLM이 중요한 단계를 누락해도 Backend의 coverage 보강 로직이
요구 텍스트를 기준으로 핵심 실행 단계를 추가합니다.
