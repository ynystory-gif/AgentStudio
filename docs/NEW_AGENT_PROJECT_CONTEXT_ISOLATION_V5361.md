# v5.362 NewAgentProjectContextIsolation

## 문제

기존 프로젝트(MINI_PRO 등)를 로드한 상태에서 `+ 신규 Agent 만들기`로 새 설계를 시작하면 `loadedProjectAnalysis`와 `workflowReq`가 남아 있어 Workflow 탭이 이전 프로젝트의 이름과 RAG Workflow를 표시할 수 있었다. 비동기 Project Adaptive 분석이 신규 Agent 전환 이후 늦게 완료되면 지워진 상태를 다시 오염시킬 가능성도 있었다.

## 수정

1. 신규 Agent 시작을 project-context epoch 경계로 정의한다.
2. 이전 Project Adaptive Analysis / Workflow / DB ERD / DB Preview / Analysis / Coding Style / Execution 상태를 모두 초기화한다.
3. `workflowReq`, `confirmedInterviewRequirements`, 이전 프로젝트 이름/경로를 초기화한다.
4. `refreshAdaptiveProjectAnalysis()`는 시작 epoch와 현재 epoch가 다르면 결과를 버린다.
5. `loadProject()`도 epoch를 캡처하여 프로젝트 전환 중 발생한 stale response를 반영하지 않는다.
6. 신규 Agent 모드(`selectedProjectId == null`)에서는 Workflow/Report가 loaded project adaptive report로 fallback하지 않는다.

## 기대 결과

신규 `AI 상품 검색·추천·주문 상담 Agent`를 시작하면 이전 `MINI_PRO · RAG 기반 AI Agent Workflow`가 보이지 않고, 새 요구사항을 수집/설계하기 전에는 빈 Target Workflow 상태가 표시된다.
