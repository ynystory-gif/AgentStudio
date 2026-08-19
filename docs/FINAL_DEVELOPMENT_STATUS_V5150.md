# v5.150 Final Development Status Feedback

## 문제

실행 결과에서 `DEBUG_PATCH_READY` 같은 상태가 표시돼도
사용자가 이것이 완료인지, 실패인지, 다음 조치가 필요한 상태인지 알기 어려웠습니다.

## 변경

Workflow 최종 State를 다음 다섯 종류로 분류합니다.

### 성공
예:
- COMPLETED
- PACKAGE_COMPLETED
- REVIEW_COMPLETED
- SUCCESS

표시:
`Agent 개발이 완료되었습니다.`

### 실패
예:
- FAILED
- ERROR
- BUILD_FAILED
- TEST_FAILED
- PACKAGE_FAILED
- ABORTED
- test_returncode > 0

표시:
`Agent 개발에 실패했습니다.`

### 디버그 조치 필요
예:
- DEBUG_PATCH_READY

표시:
`디버그 패치가 준비되었습니다.`
`개발이 완료된 상태가 아닙니다.`

### 사용자 조치 대기
예:
- WAITING_APPROVAL
- APPROVAL_REQUIRED
- CHECKPOINT
- PAUSED
- REVIEW_REQUIRED

표시:
`사용자 조치를 기다리고 있습니다.`

### 기타 종료
정의되지 않은 최종 State는 완료로 오인하지 않고
`Agent Factory 실행이 종료되었습니다.`로 표시합니다.

## 알림

성공, 실패, DEBUG_PATCH_READY 상태에서는 browser alert도 함께 표시합니다.
또 실행 결과 화면 상단에 상태 Banner를 유지해 사용자가 나중에도 확인할 수 있습니다.
