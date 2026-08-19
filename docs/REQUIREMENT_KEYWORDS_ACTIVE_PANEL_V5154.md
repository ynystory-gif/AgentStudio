# v5.154 요구사항 수집 키워드 표시 위치 수정

## 원인
v5.153에서는 요구사항 수집 현황 UI가 legacy `renderBuilderScreen()`의
`builder-summary`에만 추가되어 있었습니다.

현재 실제 Agent 설계 화면은 `renderWorkspaceScreen()`의
`workspaceTab === 'DESIGN'`과 `unified-project-config`를 사용하므로
사용자 화면에는 수집 키워드가 나타나지 않았습니다.

## 수정
현재 실제 우측 `프로젝트 구성` 카드에 다음 정보를 직접 표시합니다.

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

각 항목은 `완료 / 미수집`으로 표시됩니다.

또한 현재 DESIGN 탭의 `Workflow 보기` 버튼도:
- workflowReq
- 저장된 사용자 답변
- confirmed requirements

를 이용해 다시 인터뷰하지 않고 Workflow를 설계할 수 있도록 수정했습니다.
