# v5.220 Code Chat Focus & Terminal Interrupt Fix

## LLM 코드 대화 입력 포커스
- 코드 대화 textarea가 focus/pointer를 받으면 focus owner를 `code-chat`으로 전환합니다.
- input/textarea/select/contenteditable에 실제 DOM focus가 있는 동안 xterm 자동 focus를 금지합니다.
- terminal output/ready/prompt/ref mount/layout restore가 발생해도 사용자가 입력 중인 텍스트 필드의 focus를 빼앗지 않습니다.
- 사용자가 터미널 탭/터미널 본문을 직접 클릭한 경우에만 terminal focus를 강제로 활성화합니다.

## Ctrl+C / PowerShell interrupt
- idle terminal에서 Ctrl+C는 현재 local input line만 취소하고 Backend PowerShell에 signal을 보내지 않습니다.
- 실행 중 명령은 busy 상태로 추적하고 Ctrl+C에서만 Backend interrupt를 요청합니다.
- Windows Backend는 더 이상 `CTRL_BREAK_EVENT`를 사용하지 않습니다. 해당 signal은 persistent PowerShell에서 `Entering debug mode`를 유발할 수 있습니다.
- npm/node/python 등 PowerShell의 직접 child process tree만 종료하여 persistent PowerShell session을 보존합니다.
- child process가 없는 built-in PowerShell command에는 `CTRL_C_EVENT`를 fallback으로 사용합니다.
