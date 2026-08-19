# v5.216 Code Chat Shift+Enter Fix

- `LLM 대화형 코드 편집` 입력창에서 Enter는 기존처럼 코드 작업을 실행합니다.
- Shift+Enter는 실행하지 않고 textarea 안에서 새 줄을 삽입합니다.
- Shift+Enter 이벤트는 상위/global shortcut으로 전파하지 않아 잘못된 실행을 방지합니다.
- 한글 IME 조합 중 Enter는 실행 이벤트로 처리하지 않습니다.
- 입력창 title에 `Enter: 실행 · Shift+Enter: 줄바꿈` 안내를 추가했습니다.
