# v5.171 Test Focused Repair Fix

## 문제
- Build Artifact Placeholder 복구가 debug_iteration을 소비한 뒤 TEST_FAILED가 발생하면 테스트 복구 기회가 사실상 1회만 남았습니다.
- TEST_FAILED 후 code_generation이 이전 build_artifact_validation 상태를 보고 다시 Build Repair 모드로 들어가 실제 테스트 오류 파일을 수정하지 못했습니다.
- 화면의 실패 원인이 ReturnCode=1만 보여 실제 IndentationError 위치를 즉시 알기 어려웠습니다.

## 수정
- Build Repair 횟수와 Test Debug 횟수를 분리합니다.
- Debug History에 `type=test_failure`, `source_status`, `repair_attempt`를 기록합니다.
- TEST_FAILED 후에는 테스트 로그와 Debug 지시에서 실패 파일을 추출해 해당 파일만 읽습니다.
- 각 테스트 실패 파일은 현재 내용 기준 `replace_entire_file=true` Focused Repair로 재작성하여 들여쓰기/문법/Import 오류를 파일 단위로 복구합니다.
- 다른 파일은 수정하지 않으며 최대 3개의 명확히 식별된 실패 파일만 대상으로 합니다.
- 테스트 실패 진단 메시지에 ReturnCode뿐 아니라 실제 핵심 오류(예: IndentationError와 line)를 함께 표시합니다.

Health: `5.171 / TestFocusedRepairFix`
