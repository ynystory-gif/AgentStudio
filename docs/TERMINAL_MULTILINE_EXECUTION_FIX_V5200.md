# v5.200 Terminal Multiline Execution Fix

- AgentStudio 터미널에서 여러 줄 PowerShell block을 붙여넣은 뒤 Enter를 눌러도 실제 PowerShell 세션에 안정적으로 전달되지 않던 문제를 수정했습니다.
- 여러 줄 command는 UTF-8 Base64로 인코딩한 뒤 동일 PowerShell 세션에서 `[ScriptBlock]::Create(...)`로 복원하고 dot-source 실행합니다.
- `$body = @{ ... }`, 빈 줄, 한글, PowerShell backtick(`) continuation 등 multi-line 문법을 AgentStudio 내부 CWD/prompt marker 명령과 분리합니다.
- dot-source 실행을 사용하므로 multi-line block에서 만든 변수와 `Set-Location` 변경은 현재 persistent PowerShell 세션에 유지됩니다.
- 단일 행 명령은 기존 interactive 방식으로 그대로 전달합니다.
