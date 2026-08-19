# v5.217 PowerShell Editor Run Selection Fix

- `.ps1` 파일이 활성화된 경우 코드 탭 우측에 `전체 실행`, `선택 실행` 버튼을 표시합니다.
- `전체 실행`은 현재 Monaco Editor buffer 전체를 활성 PowerShell 터미널에 그대로 표시한 뒤 실행합니다. 저장되지 않은 편집 내용도 현재 buffer 기준으로 실행됩니다.
- `선택 실행`은 Monaco Editor에서 선택된 범위만 활성 PowerShell 터미널에 표시하고 실행합니다.
- 선택 영역이 없으면 실행하지 않고 안내합니다.
- 활성 터미널이 종료된 경우 현재 프로젝트 기준 새 PowerShell 터미널을 생성한 뒤 실행합니다.
- 여러 줄 PowerShell은 기존 terminal manager의 UTF-8 ScriptBlock 실행 경로를 그대로 사용하여 backtick, 한글, 변수, Set-Location 상태를 보존합니다.
