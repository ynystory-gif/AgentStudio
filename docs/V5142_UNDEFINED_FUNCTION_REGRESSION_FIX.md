# v5.142 Undefined Function Regression Fix

## 장애

v5.141에서 페이지가 렌더링되지 않았습니다.

브라우저 콘솔:

`ReferenceError: askCodeEditorLLM is not defined`

## 원인

독립 Builder UI를 제거하면서 `renderBuilderScreen`부터 다음 renderer까지 큰 문자열 범위를 삭제했고,
그 범위 안에 `askCodeEditorLLM` 등 Workspace에서 사용하는 함수가 포함되어 있었습니다.

## 수정 원칙

v5.142는 v5.140에서 다시 만들었습니다.

- 함수/service 로직 삭제 금지
- 독립 Builder는 route에서만 사용하지 않음
- DESIGN UI만 Workspace에 통합
- askCodeEditorLLM / applyCodeEditProposal / discardCodeEditProposal 보존
- Terminal DOM 상시 mount
- Workspace DOM도 페이지 전환 시 mount 유지

## Regression Guard

패키징 전 다음 함수 존재를 검사합니다.

- askCodeEditorLLM
- applyCodeEditProposal
- discardCodeEditProposal
- previewTargetWorkflow
- createAgentProjectFromInterview
- startAgentDevelopment
