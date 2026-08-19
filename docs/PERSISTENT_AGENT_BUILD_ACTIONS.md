# v5.128 Persistent Agent Build Actions

문제:
신규 Agent 설계 인터뷰에서는 Workflow 설계 / 프로젝트 생성 / 개발 시작 버튼이 보이지만,
Workspace의 에이전트 설계 또는 Workflow 탭으로 이동하면 진행 버튼이 사라졌습니다.

개선:
- AgentBuildActionBar 공통 컴포넌트 추가
- 신규 Agent 설계 인터뷰 화면에서도 동일 컴포넌트 사용
- 프로젝트 Workspace의 모든 탭 상단에 공통 진행 바 표시

적용 탭:
- 에이전트 설계
- 워크플로우
- 코드 편집
- 실행 결과
- 분석 리포트

버튼:
1. Workflow 설계
2. 프로젝트 생성
3. 개발 시작

동일한 `agentBuildStage`를 공유하므로 화면을 이동해도 진행 상태와 버튼 활성/비활성 상태가 유지됩니다.
