# v5.167 SYSTEM_ADMIN Parser Fix

## 문제
Windows PowerShell 5.1에서 `SYSTEM_ADMIN.ps1`의 Backend/Frontend 실행용 중첩 `powershell.exe -Command` 문자열을 구문 분석하는 과정에서 `&`, backtick, 괄호가 외부 스크립트 파서와 충돌하여 `AmpersandNotAllowed` 및 연쇄적인 닫는 괄호/중괄호 오류가 발생했습니다.

## 수정
- Backend는 `.venv\Scripts\python.exe`를 `Start-Process`로 직접 실행합니다.
- Frontend는 `node.exe`를 `Start-Process`로 직접 실행합니다.
- Backend UTF-8 환경변수와 Frontend host/port 환경변수는 자식 프로세스 생성 직전에 설정하고 즉시 원래 값으로 복구합니다.
- 중첩 `-Command` 문자열과 그 안의 `& { ... }` 블록을 완전히 제거했습니다.
- Health version을 `5.167 / SystemAdminParserFix`로 갱신했습니다.
