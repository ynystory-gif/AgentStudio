# v5.219 Editor Run Shortcut & CMD Execute Fix

- `.ps1` 활성 파일에서 F5는 전체 실행, F8은 Monaco 선택 영역 실행으로 동작합니다.
- `.ps1` 상단 실행 버튼에 F5/F8 단축키 안내를 표시합니다.
- `.cmd` 활성 파일에서는 `실행 (F5)` 버튼을 표시합니다.
- CMD 실행은 내용을 PowerShell terminal에 붙여넣지 않고 Windows Shell `open`을 사용하여 Explorer에서 더블 클릭한 것과 같은 방식으로 저장된 `.cmd` 파일을 실행합니다.
- F5 브라우저 새로고침은 `.ps1/.cmd` 코드 편집 화면에서 차단됩니다.
