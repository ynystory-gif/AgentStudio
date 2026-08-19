# Python Missing Module Diagnostic Fix v5.235

## Problem
Python F5/F8 execution correctly selected the project `.venv`, but a missing dependency only produced a raw `ModuleNotFoundError`. Users could not immediately tell whether AgentStudio chose the wrong interpreter or the selected virtual environment simply lacked the package. In selection/unsaved execution, traceback source text could also be loaded from the on-disk file and point at a stale or wrong line.

## Fix
- Detect `ModuleNotFoundError` from the persistent Python worker response.
- Return the exact interpreter path used by the project execution session.
- Map common import names to their pip package names, including `psycopg -> psycopg[binary]` and `dotenv -> python-dotenv`.
- Show a copyable interpreter-specific pip install command in the AgentStudio terminal.
- If `requirements.txt` exists, also show the command to install the full project requirements.
- Do not automatically modify the user's virtual environment.
- Register the actual executed editor code in Python `linecache` so tracebacks for F8 selections and unsaved editor content show the correct source line rather than stale disk content.

## Expected behavior
For:

```python
import psycopg
```

when the selected project `.venv` does not contain psycopg, the terminal still shows the Python traceback and then adds a clear diagnostic such as:

```text
[패키지 설치 필요] 현재 선택된 Python 환경에 'psycopg' 모듈이 설치되어 있지 않습니다.
설치 명령: & "C:\...\.venv\Scripts\python.exe" -m pip install "psycopg[binary]"
```

This makes the distinction explicit: interpreter selection is correct; the dependency is missing from that interpreter.
