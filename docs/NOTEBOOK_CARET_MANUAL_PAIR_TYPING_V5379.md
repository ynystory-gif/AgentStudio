# v5.379 Notebook Caret Persistence + Manual Pair Typing

## 문제

Notebook Code Cell 중간에 커서를 둔 상태에서 문자 입력/삭제/붙여넣기를 수행하면 전체 `.ipynb` JSON 직렬화 결과가 controlled Monaco `value`로 다시 주입되면서 caret가 셀 끝/마지막 줄로 이동할 수 있었습니다. 또한 Monaco 기본 auto-closing으로 `print(` 입력 시 `print()`가 생성되어 사용자가 입력한 문자열과 caret 위치가 달라질 수 있었습니다.

## 수정

- Notebook Cell Monaco model은 mount 이후 자체 model을 유지하고 `defaultValue`는 최초 로드에만 사용합니다.
- Cell 변경값은 즉시 Notebook JSON/dirty-state에 mirror하지만 같은 값을 다시 Monaco model에 강제 적용하지 않습니다.
- 외부 reload/Agent edit은 focused Cell을 방해하지 않고 blur 이후 동기화합니다.
- Notebook 변경 시 App의 global Monaco ref 강제 focus를 수행하지 않습니다.
- `autoClosingBrackets`, `autoClosingQuotes`, `autoClosingDelete`, `autoClosingOvertype`, `autoSurround`를 `never`로 설정합니다.

## 완료 기준

1. Code Cell 2번째 줄 중간에 커서를 두고 `ABC` 입력 후 caret가 `ABC` 직후에 남아 있습니다.
2. 중간 문자열 Backspace/Delete 후 caret가 마지막 줄로 이동하지 않습니다.
3. 중간 위치에 여러 줄 붙여넣기 후 caret가 붙여넣은 텍스트 끝에 남아 있습니다.
4. `print(` 입력 결과는 `print(`입니다.
5. `print("` 입력 결과는 `print("`입니다.
