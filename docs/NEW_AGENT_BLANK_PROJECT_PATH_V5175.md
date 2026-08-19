# v5.175 신규 Agent 프로젝트 경로 초기화

## 변경 목적
`신규 Agent 만들기`를 클릭했을 때 이전 프로젝트 경로나 시스템 기본 프로젝트 경로가 `프로젝트 경로` 입력칸의 실제 value로 남지 않도록 합니다.

## 동작
- 신규 Agent 진입 시 `newAgentProjectRoot`를 빈 문자열로 초기화합니다.
- 기존 workspace `root`도 함께 비워 이전 프로젝트 경로가 fallback으로 재사용되지 않게 합니다.
- `/settings/default-paths`의 `project_root`는 입력 value로 자동 주입하지 않습니다.
- 입력칸에는 예시 placeholder만 표시됩니다.
- 사용자는 직접 경로를 입력하거나 `경로 찾기`로 선택합니다.
- 새 경로를 선택한 뒤 해당 경로에 저장된 Requirement Draft가 있으면 기존 Draft 복원 로직은 그대로 동작합니다.

## 버전
- 5.175
- Build: `NewAgentBlankProjectPathFix`
