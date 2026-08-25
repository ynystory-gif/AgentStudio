# v5.329 Startup Build / Failure Visibility Fix

## 문제

`SYSTEM_ADMIN.cmd`를 일반 권한으로 실행하면 `SYSTEM_ADMIN.ps1`이 UAC를 통해 별도 관리자 PowerShell을 시작합니다. 관리자 프로세스에서 Frontend build 등이 실패하면 해당 창이 닫힌 뒤 부모 창에는 `ExitCode=1`만 남아 실제 오류를 확인하기 어려웠습니다.

또한 VS Code-style Codex 패널의 기본 모델 선택 코드가 TypeScript의 `noUncheckedIndexedAccess` 설정에서 `CodexModel | undefined`를 `modelId(CodexModel)`에 전달할 수 있어 `npm run build`를 실패시킬 수 있었습니다.

## 수정

- 기본 모델 객체 존재 여부를 확인한 뒤 `modelId()`를 호출합니다.
- Codex input/textarea/select event 타입을 명시합니다.
- startup 예외를 `logs/system_manager_failure.log`에 저장합니다.
- UAC 자식 프로세스가 실패하면 부모 PowerShell이 실패 상세 로그 마지막 120줄을 출력합니다.
- `SYSTEM_ADMIN.cmd`도 실패 로그와 주요 로그 경로를 자동 표시합니다.

## 검증

- CodexPanel strict/noUncheckedIndexedAccess 격리 TypeScript typecheck PASS
- Frontend contract validation PASS
- Backend compileall PASS
- Codex protocol contract validation PASS
