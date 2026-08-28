# THEANOVA AgentStudio v5.397 UnifiedSourceDebuggerAndNotebookDebugUXFix

- `python3` / `ipykernel` Notebook kernel도 Python debugger로 인식합니다.
- Debug 셀 버튼이 disabled일 때 hover cursor가 무한 로딩처럼 보이던 `cursor: wait`를 제거했습니다. 실제 요청 중일 때만 `시작 중…`/progress 상태를 표시합니다.
- Notebook에서 중단점만 찍어도 디버그 도구줄이 나타나고 `디버그 시작`, 계속, Step Over/Into/Out, 종료 버튼을 항상 확인할 수 있습니다.
- 일반 Source Editor에도 빨간 중단점, 현재 실행 줄, Debug toolbar, 변수, 호출 스택, Debug Console을 추가했습니다.
- 일반 `.py` 소스 파일은 Notebook과 동일한 Python bdb Step Debugger를 사용해 F5/F10/F11/Shift+F11/Shift+F5를 지원합니다.
- JavaScript/TypeScript/PowerShell/CMD/Shell/PHP/Ruby/Go/Java/C/C++/Rust 등은 현재 편집 버퍼를 Source Runner Adapter로 실행할 수 있습니다.
- 언어별 Step Debug Adapter가 없는 경우에도 동일 Debug UI를 보여주되 단계 버튼은 비활성화하고 실행 Adapter 상태를 명확히 표시합니다.
