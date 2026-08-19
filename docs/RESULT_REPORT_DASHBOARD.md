# v5.125 실행 결과 / 분석 리포트 Dashboard

## 실행 결과

Agent Factory의 실제 `workflow.state`를 화면에 연결합니다.

표시:
- 개발 상태
- 테스트 PASS/FAIL / Exit Code
- 생성 파일 수
- 수정 파일 수
- 디버그 반복 횟수
- 테스트 명령 및 출력
- 생성/수정 파일 목록
- 디버그/복구 기록
- 현재 터미널 출력

## 분석 리포트

표시:
- 요구사항 목표
- Acceptance Criteria / Constraints
- Agent Architecture
- 대상 Agent Workflow
- MCP / Tool 의사결정
- Capability
- 코드 생성 결과
- Coding Style Validation
- 최종 완료 상태

## Coding Style Validation

프로젝트 내 `.py/.js/.jsx/.ts/.tsx` 파일을 읽어
기존 `/coding-style/validate`를 호출합니다.

결과:
- PASS
- WARNING
- FAIL
- 검사 파일 수
- 파일별 Rule ID / Severity / Message

`코딩 스타일 재검증` 버튼으로 언제든 다시 검사할 수 있습니다.
