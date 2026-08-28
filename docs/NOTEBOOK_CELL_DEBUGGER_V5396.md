# v5.396 Notebook Cell Debugger

- Python Notebook Code 셀에 `🐞 디버그 셀` 추가
- Monaco glyph 여백 클릭으로 빨간 중단점 추가/해제 (줄 번호 클릭은 기존 북마크 유지)
- 현재 실행 줄을 노란색으로 강조
- Continue(F5), Step Over(F10), Step Into(F11), Step Out(Shift+F11), Stop(Shift+F5)
- 같은 Notebook persistent Python namespace에서 디버깅
- 변수, 호출 스택, 디버그 콘솔 expression 평가 제공
- 중단점은 프로젝트+Notebook별 localStorage에 유지
- `!command`, `%magic`, `%%cell magic`은 일반 실행을 사용하도록 안전하게 안내
