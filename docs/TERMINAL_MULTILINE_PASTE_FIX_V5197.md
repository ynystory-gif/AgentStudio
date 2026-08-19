# v5.197 Terminal Multiline Paste Fix

- Ctrl+V로 붙여넣은 PowerShell 다중 행 텍스트의 줄바꿈과 탭을 보존합니다.
- `$body = @{ ... }`, backtick(`) line continuation, 여러 줄 Invoke-RestMethod 예제 등을 문서에서 복사한 형태 그대로 터미널 입력 버퍼에 넣습니다.
- 붙여넣기만으로 명령을 실행하지 않으며 사용자가 Enter를 눌렀을 때 전체 블록을 한 번에 PowerShell 세션으로 전송합니다.
- xterm 표시에서는 LF를 CRLF로 렌더링하여 각 줄이 좌측 열에서 시작하도록 합니다.
- 다중 행 붙여넣기 중에는 터미널 자동완성 팝업을 닫아 입력 블록을 가리지 않도록 합니다.
