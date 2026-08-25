# v5.336 Interview Attachment Session & Project Create Flow Fix

## 문제 1 — 참고 파일이 매 대화마다 반복 첨부됨

이전 구현은 Agent 설계 인터뷰의 매 사용자 메시지에 `📎 참고 파일: ...` 문자열을 직접 붙이고, 같은 attachment id도 매 턴 Backend로 다시 보냈다.

### 수정

- 참고 파일 이름을 사용자 메시지 본문에 넣지 않는다.
- 처음 분석에 성공하면 원본 attachment id를 Backend registry에서 해제한다.
- Backend가 만든 제한된 요구사항 분석 Context만 `attachment_memory`로 세션에 유지한다.
- 새 파일을 추가하면 기존 메모리와 새 분석본을 합치고 다시 원본 attachment를 해제한다.
- Workflow 설계도 원본 파일 대신 동일한 세션 메모리를 재사용한다.

## 비밀정보 보호

첨부 파일에 `.env`, API key, token, password, DB URL credential이 들어 있어도 AI Context에 들어가기 전에 Backend에서 마스킹한다. 이전 브라우저 Draft에 이미 저장된 값도 Agent 설계 인터뷰 화면 복원 시 표시 마스킹한다.

## 문제 2 — 프로젝트 생성 버튼을 눌러도 진행되지 않음

기존 `AgentBuildActionBar`는 `WORKFLOW_READY` 상태에서만 프로젝트 생성 버튼을 활성화했다. 요구사항이 충분히 수집된 `REQUIREMENTS` 상태에서도 버튼이 막혀 사용자는 클릭해도 진행할 수 없었다.

### 수정

요구사항이 Workflow 설계를 시작할 만큼 수집되어 있으면 `프로젝트 생성` 버튼을 사용할 수 있다.

1. 아직 Workflow가 없으면 자동 Workflow 설계
2. Workflow 설계 성공 확인
3. 프로젝트 폴더와 DB Project row 생성
4. `PROJECT_CREATED` 단계로 전환

에이전트 이름 또는 프로젝트 경로가 없으면 버튼 클릭 즉시 사용자에게 필요한 입력을 명확히 알려준다.
