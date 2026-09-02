# THEANOVA AgentStudio v5.501

- `지금 DB 설정`에서 PostgreSQL/Firestore/Redis 사용 체크 상태를 `enabled`와 `use_in_agent`에 함께 반영해 클릭 후 즉시 원상복귀되는 상태 충돌을 수정했습니다.
- 과거 저장 Snapshot을 정규화할 때 `enabled` 값을 우선하고 두 상태를 동기화합니다.
- DB 미사용/건너뛰기/나중에 설정 시 `enabled=false`, `use_in_agent=false`를 함께 저장합니다.
- 요구사항 수집 현황은 키워드가 문서나 대화에 단순 등장했다는 이유만으로 완료 처리하지 않고 실제 값/확정 상태가 있을 때만 완료합니다.
- v5.500의 사용자 질문 즉답, 첨부파일 1회 분석/Memory 재사용, 사용자 액션 기반 저장, Tool/Prompt 단계, UI Framework/Layout 분리, 첨부 정리 패널 상단 조절/접기 기능을 유지합니다.
