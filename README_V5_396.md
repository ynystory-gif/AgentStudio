# THEANOVA AgentStudio v5.396 — Notebook Cell Debugger

Jupyter Notebook Python Code 셀에 VS Code와 유사한 셀 단위 디버깅 기능을 추가했습니다.

- `🐞 디버그 셀`
- 줄 번호 왼쪽 glyph 여백 클릭: 빨간 중단점
- 줄 번호 클릭: 기존 파란 북마크
- 현재 실행 줄 노란색 강조
- 계속(F5), 다음 줄/Step Over(F10), 함수 안/Step Into(F11), 함수 밖/Step Out(Shift+F11), 종료(Shift+F5)
- 변수 / 호출 스택 / 디버그 콘솔 표현식 평가
- 기존 Notebook persistent Python namespace 유지
- 중단점 프로젝트+Notebook별 localStorage 저장

검증:
- Backend Python compileall PASS
- v5.396 contract PASS 13/13
- Frontend critical contracts PASS
- NotebookEditor.tsx / notebook.ts / App.jsx parse diagnostics 0
- 실제 backend debugger: pause / step over / breakpoint / evaluate / continue / function step into/out 테스트 PASS
