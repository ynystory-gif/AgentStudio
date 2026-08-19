# v5.230 PythonEditorPersistentRunFix

Python `.py` editor execution workflow.

- F5 / `전체 실행`: execute the full current Monaco editor buffer using the current project's Python environment.
- F8 / `선택 실행`: execute only the selected Monaco code.
- Interpreter priority: `.venv` -> `venv` -> system Python.
- F8 uses a persistent Python worker per project + terminal session so variables, functions and imports survive across selection executions.
- F5 starts from a fresh Python globals namespace, executes the whole buffer, then keeps the resulting namespace so later F8 selections can continue from that state.
- Execution stdout/stderr/traceback is displayed in the existing lower terminal pane.
- Unsaved editor buffer contents are executable; a disk save is not required before F5/F8.
- Nested Python files add both the project root and source file directory to `sys.path` for project-local imports.
