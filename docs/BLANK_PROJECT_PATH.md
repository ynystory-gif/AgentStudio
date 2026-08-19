# v5.122 프로젝트 경로 초기값

신규 Agent 설계 화면에서 프로젝트 경로의 실제 초기값을 제거했습니다.

기존:
- 특정 로컬 경로가 실제 값으로 미리 입력됨

변경:
- `newAgentProjectRoot` 초기값은 빈 문자열
- 입력칸에는 placeholder 예시만 표시
- 예시: `F:\Source\repos\Theanova\AI\MyAgent`
- 실제 경로는 사용자가 직접 입력하거나 `경로 찾기`로 선택
- 경로가 비어 있으면 생성 경로 안내 문구 표시
