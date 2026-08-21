# v5.289 NotebookWritefileCellMagicFix

AgentStudio Notebook 실행기가 Jupyter의 `%%writefile` cell magic을 Python 문법으로 오인해 `SyntaxError`를 내던 문제를 수정합니다.

## 동작

```python
%%writefile apps/streamlit_01_hello.py
import streamlit as st
st.title("우리 도서관 대시보드")
```

위 셀은 Python으로 실행되지 않고 현재 `.ipynb`가 있는 폴더를 기준으로 `apps/streamlit_01_hello.py`를 UTF-8로 생성합니다. `apps` 폴더가 없으면 자동 생성합니다.

`-a` 및 `--append` 옵션도 지원하며, 프로젝트 루트 밖으로 나가는 경로는 안전을 위해 차단합니다.
