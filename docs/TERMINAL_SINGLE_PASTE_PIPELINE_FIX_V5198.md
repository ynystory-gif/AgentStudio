# v5.198 Terminal Single Paste Pipeline Fix

- Ctrl+V 중복 붙여넣기의 원인이었던 custom clipboard read와 xterm native paste의 이중 처리 구조를 제거했습니다.
- Ctrl+V는 xterm native paste pipeline 하나만 사용하고 onData를 단일 command buffer 입력 경로로 사용합니다.
- 여러 줄 PowerShell 붙여넣기는 줄바꿈 구조를 유지하되 command buffer에 정확히 한 번만 반영됩니다.
- 붙여넣기 자체는 실행하지 않으며 사용자가 Enter를 눌렀을 때만 전체 command buffer를 Backend PowerShell 세션으로 전송합니다.
