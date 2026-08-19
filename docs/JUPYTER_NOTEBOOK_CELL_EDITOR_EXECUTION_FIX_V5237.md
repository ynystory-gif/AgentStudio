# Jupyter Notebook Cell Editor / Execution Fix v5.237

## 문제

`.ipynb` 파일이 일반 JSON 텍스트로 열려 VS Code/Jupyter처럼 Markdown과 Code 셀을 읽고 실행하기 어려웠습니다.

## 수정

- `.ipynb`를 Notebook 전용 화면으로 렌더링합니다.
- Markdown 셀은 제목, 목록, 인용, 표, 코드 블록을 문서 형태로 표시합니다.
- Markdown 셀은 `편집` 또는 더블 클릭으로 Monaco Markdown 편집기로 전환됩니다.
- Code 셀은 Monaco Python 편집기로 표시됩니다.
- 각 Code 셀에 `셀 실행`, `선택 실행`을 제공합니다.
- F5는 위에서부터 모든 Python Code 셀을 순차 실행합니다. 첫 Code 셀에서 Python 세션을 초기화하고 이후 셀은 같은 세션을 유지합니다.
- F8은 현재 Code 셀에서 선택한 Python 코드만 실행합니다.
- 실행 stdout/stderr/error를 Notebook 셀 바로 아래 output으로 기록하며 `.ipynb` 저장 시 함께 보존합니다.
- Notebook 셀의 마지막 줄이 표현식이면 Jupyter처럼 `repr()` 결과를 자동 출력합니다.
- `+ 코드`, `+ Markdown`, 셀 삭제, 전체 출력 지우기를 제공합니다.
- 기존 프로젝트 `.venv` Python 선택 규칙과 v5.235의 누락 패키지 진단을 Notebook 실행에도 그대로 사용합니다.
- Backend `/python/execute`가 `.ipynb` 상대 경로를 허용합니다.

## 제한

현재 셀 실행 엔진은 Python Notebook 커널을 대상으로 합니다. 다른 언어 전용 Jupyter 커널은 편집/표시는 가능하지만 실행은 차단하고 커널명을 안내합니다.
