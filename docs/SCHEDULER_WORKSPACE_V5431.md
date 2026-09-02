# v5.431 Scheduler Workspace

- `DB ERD` 바로 오른쪽에 `스케줄러` Workspace 탭을 추가했습니다.
- Backend `JobManager` 작업과 UI / Layout Theme 동적 분석 Job을 하나의 목록으로 통합합니다.
- 기본 화면은 현재 `QUEUED / RUNNING / WAITING / CANCELLING` 작업만 표시합니다.
- `종료된 작업 포함`을 선택하면 최근 완료/실패/취소 작업도 확인할 수 있습니다.
- 각 활성 항목 오른쪽에 `실행취소` 버튼을 제공하며 Backend의 실제 Task cancel API를 호출합니다.
- Scheduler 화면은 2초 주기로 Backend 상태를 갱신해 Theme 분석처럼 별도 Job Registry를 사용하는 작업도 반영합니다.
- JobManager에 `created_at / updated_at`을 추가해 시작/갱신 시간을 표시합니다.
