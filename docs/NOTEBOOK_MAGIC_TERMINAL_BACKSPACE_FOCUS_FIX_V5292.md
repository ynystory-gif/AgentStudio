# v5.292 NotebookMagicTerminalBackspaceFocusFix

## 문제

1. Notebook/LLM 편집 영역으로 돌아온 뒤에도 xterm의 hidden textarea가 키 입력을 잡아 Backspace가 터미널에 전달될 수 있었습니다.
2. 긴 PowerShell 명령이 여러 화면 줄로 soft-wrap 되었을 때 단순 `\b \b` 삭제가 줄 경계를 안정적으로 넘지 못했습니다.
3. `%%writefile`이 셀 2번째 줄에 위치하면 Python parser까지 전달되어 `SyntaxError`가 발생했습니다.

## 수정

- Notebook 영역의 mouse/focus capture 및 Monaco cell focus에서 `focusOwner=editor`를 즉시 설정합니다.
- xterm custom key/onData 입력은 `focusOwner=terminal`일 때만 처리합니다.
- soft-wrap Backspace는 xterm cursor 위치와 column 수를 기준으로 이전 row까지 명시적으로 이동해 erase 합니다.
- Notebook worker는 첫 번째 non-empty line의 `%%writefile`을 Cell Magic으로 처리합니다.
- Notebook LLM 적용 시 `%%writefile` 앞 선행 빈 줄을 제거해 물리적 첫 줄로 정규화합니다.

원본 Notebook/프로젝트 파일의 기존 실행 정책과 `SYSTEM_ADMIN.cmd` 단일 실행 정책은 유지합니다.
