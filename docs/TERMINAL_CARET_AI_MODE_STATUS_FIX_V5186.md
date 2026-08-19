# v5.186 Terminal Caret + AI Mode Status Fix

- 터미널 상단의 큰 `입력 포커스` 배지를 제거했습니다.
- 터미널이 키보드 입력 대상일 때는 일반적인 1px focus outline과 xterm caret로 현재 입력 위치를 표시합니다.
- Enter 후 새 출력/PowerShell prompt가 도착하면 입력 caret가 보이는 마지막 줄로 이동하고 가로 위치는 새 prompt 시작점으로 복원합니다.
- 상단 `AI 모드` pill을 실제 동작하는 dropdown으로 변경했습니다.
- Backend `/llm/runtime-status`에서 현재 Provider routing, OpenAI 실제 설정 모델, Ollama 실제 연결 상태를 조회합니다.
- 상단 표시는 하드코딩된 `Ollama + GPT-5 mini`가 아니라 실제 코딩 Provider/Model을 표시합니다.
- AUTO / OpenAI 전용 / Ollama 전용 선택이 실제 Provider 설정을 변경합니다. Ollama가 연결되지 않았으면 Ollama 전용 선택은 비활성화됩니다.
- 메뉴에는 Coding/Debug, Requirements, Local routing과 Ollama 연결 여부를 함께 표시합니다.
