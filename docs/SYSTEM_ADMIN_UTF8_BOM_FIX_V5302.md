# v5.302 SYSTEM_ADMIN UTF-8 BOM Self-Heal Fix

## 증상
Windows PowerShell 5.1에서 `SYSTEM_ADMIN.ps1`의 한글 문자열이 깨지고 `MissingArrayIndexExpression`, `The string is missing the terminator`, `Missing closing }` 같은 연쇄 ParserError가 발생했다.

## 원인
`SYSTEM_ADMIN.ps1`이 UTF-8이지만 BOM 없이 패키징되면 Windows PowerShell 5.1이 시스템 ANSI 코드페이지로 해석할 수 있다. 한글 UTF-8 바이트가 잘못 해석되면서 문자열 리터럴 자체가 손상되어 파서 오류가 발생한다.

## 수정
- `SYSTEM_ADMIN.ps1`: UTF-8 with BOM으로 복원.
- `SYSTEM_ADMIN.cmd`: 실행 전에 PS1 BOM을 검사한다. BOM이 없고 유효한 UTF-8이면 UTF-8 BOM으로 자동 재저장한 뒤 실행한다.
- UTF-8 자체가 손상된 파일이면 자동 실행하지 않고 명확한 오류로 중단한다.
- v5.301의 NotebookEditor TypeScript 전환 내용은 그대로 유지한다.
