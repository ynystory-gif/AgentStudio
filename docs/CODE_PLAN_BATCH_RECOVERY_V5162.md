# v5.162 Code Plan Batch Recovery + Failure Message Fix

## 수정 배경

v5.161에서는 File Plan의 required 파일이 많을 때 최초 Code Plan이 일부 파일만 반환하면
누락 파일 전체를 한 번의 보강 LLM 호출로 다시 요청했습니다.

예: 계획 파일 28개 / 실제 또는 기존 파일 9개인 상태에서 남은 required 파일을 한 번에 생성하려고 하면,
LLM 응답 길이와 JSON 크기 때문에 일부 파일만 반환되어 `CODE_PLAN_INCOMPLETE`로 종료될 수 있었습니다.

또 `/workflow/start` 응답 연결이 중간에 끊겨 catch 경로로 들어간 경우,
`/workflow/diagnostics` 재조회로 실제 실패 상태를 정상 복구했는데도 팝업 첫 문구가
`Backend 연결 실패`로 표시되어 실제 원인과 전송 오류를 혼동하게 했습니다.

## v5.162 변경 내용

### 1. Code Plan required 파일 자동 배치 보강

- 누락 required 파일을 기본 3개 단위로 나누어 반복 생성
- 직전 보강에서 진전이 없으면 1개 파일 단위로 축소하여 재시도
- 최대 보강 횟수와 연속 무진전 횟수 제한
- 각 보강 응답은 이번 배치에서 요청한 정확한 파일 경로만 병합
- 이미 생성된 다른 파일을 LLM이 반복 반환해도 기존 Plan을 덮어쓰지 않음
- 보강 완료 후 required 전체가 포함된 경우에만 실제 파일 적용 단계로 진행

### 2. Code Plan 보강 이력 진단 저장

`code_plan_validation`에 다음 정보를 저장합니다.

- initial_missing_count
- supplement_rounds
- supplement_attempts
- supplement_completed
- supplement_no_progress_rounds
- missing_required_paths

실패 리포트와 generated_artifacts/debug_patch에도 Code Plan 상태를 함께 기록합니다.

### 3. 실패 화면에 Code Plan 누락 상세 표시

실패 진단 카드에서 다음 내용을 바로 확인할 수 있습니다.

- Required 파일 수
- 기존 존재 파일 수
- Code Plan 변경 파일 수
- 자동 보강 횟수
- 최종 누락 required 파일 목록

### 4. Backend 오류와 Agent 개발 실패 구분

`/workflow/start`의 응답 연결이 끊겼더라도 `/workflow/diagnostics` 재조회가 성공하면
더 이상 `Backend 연결 실패`를 주 원인처럼 표시하지 않습니다.

대신 다음 순서로 표시합니다.

1. 실제 Agent Workflow 상태
2. 실제 실패 원인
3. 필요 시 "시작 요청 응답 연결이 중간에 끊겼지만 진단 재조회는 성공" 참고 문구

## 기대 동작

File Plan이 20~30개 이상의 required 파일을 포함하더라도 한 번의 거대한 Code Plan JSON에 의존하지 않고,
작은 단위로 자동 보강한 뒤 파일 적용 → 테스트 → 디버그/복구 → 패키징 단계로 계속 진행합니다.
