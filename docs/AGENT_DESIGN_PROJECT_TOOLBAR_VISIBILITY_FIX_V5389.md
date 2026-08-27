# v5.389 AgentDesignProjectToolbarVisibilityFix

## 문제

Agent 설계 인터뷰에 `AgentDesignProjectToolbar`가 렌더링되도록 구현되어 있었지만,
기존 `.builder-chat` Grid가 Toolbar 추가 이전의 4행 구조를 계속 사용하고 있어
`프로젝트 저장` / `프로젝트 로드`가 화면에서 보이지 않거나 레이아웃에 의해 밀릴 수 있었습니다.

## 수정

- Agent 설계 인터뷰 Grid를 5행으로 고정
  1. 설계 프로젝트 Toolbar
  2. Agent 설계 인터뷰 Header
  3. 대화 영역
  4. Workflow/생성 Action Bar
  5. 답변 입력창
- Toolbar에 명시적인 표시/높이/z-index 보강
- 버튼을 `프로젝트 저장`, `프로젝트 로드`로 명확히 분리
- `프로젝트 로드` 클릭 시 `Agent 설계 프로젝트 목록` Modal 표시
- 목록에서 저장된 프로젝트를 선택하면 기존 인터뷰/요구사항/Workflow/기능 상태를 복원

## 위치

`에이전트 설계` → `Agent 설계 인터뷰` 바로 위에 항상 표시됩니다.
