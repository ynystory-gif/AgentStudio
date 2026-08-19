# v5.159 성공/실패 판정 + Code Plan 경로 정규화

## 성공으로 잘못 표시된 원인
Frontend가 성공 상태를 다음처럼 검사했습니다.

`completedStatuses.some(value => status.includes(value))`

따라서:
`CODE_PLAN_INCOMPLETE`

안에 문자열 `COMPLETE`가 포함되어 있어 성공으로 잘못 분류되었습니다.

## 성공 판정
이제 성공은 정확히 다음 조건을 모두 만족해야 합니다.

- 최종 상태: `COMPLETED` 또는 `SUCCESS`
- test_result.returncode == 0
- build_artifact_validation.ok == true
- patch_result가 1개 이상

하나라도 빠지면 성공으로 표시하지 않습니다.

## 실패 판정
다음 상태는 명시적인 실패입니다.

- CODE_PLAN_INCOMPLETE
- REPAIR_PLAN_INCOMPLETE
- FILE_APPLY_FAILED
- REQUIREMENT_COVERAGE_FAILED
- BUILD_ARTIFACT_STALLED
- TEST_FAILED
- DEBUG_STOPPED
- INCOMPLETE
- FAILED / ERROR / ABORTED

## Code Plan 경로 문제
LLM 결과에 같은 파일이 다음 두 형태로 동시에 존재할 수 있었습니다.

- F:\project\backend\app\main.py
- backend/app/main.py

이제 모든 Code Plan 경로를 프로젝트 Root 기준 상대경로로 정규화합니다.

예:
둘 다 `backend/app/main.py`

초기 Plan, 보강 Plan, Repair Plan 모두 정규화하며 동일 파일은 한 항목으로 병합됩니다.

## 실패 진단
CODE_PLAN_INCOMPLETE이면 누락 required 파일명을 failure report에 기록합니다.
