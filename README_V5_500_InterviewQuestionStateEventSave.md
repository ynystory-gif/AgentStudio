# THEANOVA AgentStudio v5.500

- 인터뷰 중 `UI / Layout 뭐가 있어?` 같은 정보 질문은 요구사항 답변으로 오인하지 않고 질문에 대한 답만 반환합니다. 질문 뒤에 다음 인터뷰 질문을 자동으로 붙이지 않습니다.
- 정보 질문은 대기 중 Requirement Slot을 완료 처리하지 않으며, 이미 분석한 첨부 파일을 재분석하지 않습니다.
- 첨부 파일은 Context 준비가 끝나면 Requirement Registry/요약을 한 번 자동 생성해 Memory에 저장하고 이후 인터뷰에서는 해당 Memory를 재사용합니다. 기본 첨부 요약은 LLM 재호출 없이 결정적으로 생성됩니다.
- 요구사항 수집 상태는 Assistant의 예시 문구가 아니라 실제 사용자 요구사항/확정 설정/첨부 분석 결과만 사용합니다. UI Framework와 Layout 상태를 분리했습니다.
- UI Framework(`React + TypeScript` 등)와 Layout Template을 별도 필드로 유지해 Layout 변경이 Frontend Framework 값을 덮어쓰지 않습니다.
- Tool / Prompt 설정 탭을 추가해 Tool 모드, 지정 Tool, System Prompt, 질문 응답 정책을 설계 Snapshot/Workflow 요구사항에 저장합니다.
- DB-backed 설계 자동 저장은 Background 상태 변경으로 실행하지 않고 실제 사용자 Pointer/Keyboard 액션 후에만 debounce 저장합니다. 사용자가 아무 동작도 하지 않으면 저장 시각이 갱신되지 않습니다.
- 첨부 분석 정리 패널의 높이 조절 Handle을 상단으로 이동하고 `▲ 접기 / ▼ 펼치기` 버튼을 추가했습니다.
- 일반 인터뷰 LLM 호출은 60초 hard timeout 후 deterministic interview fallback으로 전환해 2분 이상 무한 대기하지 않습니다.
- `지금 DB 설정`의 PostgreSQL/Firestore/Redis 사용 체크 컨트롤과 하위 옵션 체크박스의 클릭 영역을 복구했습니다.
