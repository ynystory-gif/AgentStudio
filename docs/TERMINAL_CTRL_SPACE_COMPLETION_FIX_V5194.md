# v5.194 Terminal Ctrl+Space Completion Fix

- 코드 편집기 하단 PowerShell 터미널에서 `Ctrl+Space`를 누르면 현재 입력 커서 앞의 토큰을 기준으로 자동완성 후보를 표시합니다.
- 현재 작업 폴더의 파일/폴더와 PowerShell/PATH 실행 명령을 후보로 제공합니다.
- `↑/↓`로 선택하고 `Tab` 또는 `Enter`로 적용하며 `Esc`로 닫을 수 있습니다.
- 마우스로 후보를 선택할 수도 있습니다.
- 현재 PowerShell 작업 경로(CWD)를 반영하여 `./`, `.\\`, 절대 경로 등 경로 자동완성을 지원합니다.
- 자동완성 요청은 명령 실행이 아니며, 선택한 후보를 로컬 command buffer에 삽입한 뒤 실제 실행은 기존처럼 Enter 입력 시 수행합니다.
