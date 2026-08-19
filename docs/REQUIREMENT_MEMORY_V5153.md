# v5.153 Requirement Collection Memory

## 목적
Agent 생성 실패 후 에이전트 설계 화면으로 돌아와도 이미 수집한 인터뷰 정보를 다시 묻지 않도록 합니다.

## 저장
브라우저 LocalStorage에 프로젝트 경로(또는 Agent 이름)를 Key로 Draft를 저장합니다.

저장 항목:
- Agent 이름
- Project Root
- Workflow Request
- 전체 인터뷰 Chat
- Confirmed Requirements
- Workflow Preview
- Workflow Quality
- Agent Build Stage
- 저장 시각

## 복원
같은 프로젝트 경로로 Agent 설계 화면에 진입하면 이전 Draft를 자동 복원합니다.
Workflow Preview까지 있으면 `WORKFLOW_READY` 상태까지 복구합니다.

## 요구사항 수집 현황
우측 프로젝트 구성 영역에 다음 Keyword 상태를 표시합니다.

- 목적
- 파일 형식
- 결과 형식
- LLM
- UI
- Backend
- MCP / Transport
- DB
- 권한 / 파일 접근
- 실행 환경
- 처리 제한

각 항목은 `수집 완료 / 미수집`으로 표시합니다.

## 바로 Workflow 설계
이전 대화나 Confirmed Requirement가 남아 있으면 인터뷰를 다시 시작하지 않고
`수집된 요구사항으로 바로 Workflow 설계` 버튼을 사용할 수 있습니다.

Workflow 설계 API에는 기존과 동일하게:
- interview_messages
- confirmed_requirements

가 전달됩니다.

## 주의
LocalStorage는 설계 Draft용입니다. 생성된 프로젝트의 최종 실패 분석 자료는
기존 reports/requirements_snapshot.json 및 failure_report.md가 별도로 유지됩니다.
