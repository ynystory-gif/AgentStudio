# v5.173 SYSTEM_ADMIN UTF-8 BOM Parser Fix

## 원인
Windows PowerShell 5.1은 UTF-8 BOM이 없는 `.ps1` 파일을 시스템 ANSI 코드페이지로 해석할 수 있습니다.
한글 UTF-8 바이트가 잘못 해석되면 문자열 따옴표와 Here-String 경계가 손상되어 `MissingTypename`, `UnexpectedToken`, `Try without Catch` 같은 연쇄 ParserError가 발생할 수 있습니다.

## 수정
- AgentStudio 자체 `SYSTEM_ADMIN.ps1`을 UTF-8 BOM + CRLF로 저장합니다.
- `SYSTEM_ADMIN.cmd`가 PowerShell 실행 전에 `chcp 65001`을 적용합니다.
- `SYSTEM_ADMIN.ps1`의 Here-String을 제거하여 PowerShell 5.1 파서 민감도를 낮췄습니다.
- 생성 Agent의 `SYSTEM_ADMIN.ps1`도 `utf-8-sig`로 기록합니다.
- 생성 Launcher 계약 검증에 `ps1_utf8_bom` 검사를 추가했습니다.

Health: `5.173 / SystemAdminUtf8BomParserFix`
