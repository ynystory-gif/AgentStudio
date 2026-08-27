from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


_WORKER_RESPONSE_PREFIX = '__AGENTSTUDIO_PY_RESPONSE_V1__'

_WORKER_CODE = r'''
import ast
import asyncio
import builtins
import contextlib
import io
import importlib
import inspect
import json
import linecache
import os
import shlex
import subprocess
import sys
import traceback

RESPONSE_PREFIX = '__AGENTSTUDIO_PY_RESPONSE_V1__'

namespace = {
    "__name__": "__main__",
    "__package__": None,
    "__builtins__": builtins,
}

# v5.349: AgentStudio Notebook cells now support the same top-level await
# syntax users expect from Jupyter/IPython.  The worker itself is synchronous,
# so keep a private event loop alive across persistent Notebook cell runs.
# If user code closes/replaces the current loop, create a fresh one lazily.
_agentstudio_asyncio_loop = None

def _agentstudio_run_awaitable(value):
    global _agentstudio_asyncio_loop
    if not inspect.isawaitable(value):
        return value

    loop = _agentstudio_asyncio_loop
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        _agentstudio_asyncio_loop = loop
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(value)
    finally:
        # Preserve this loop for the next Notebook cell.  This mirrors the
        # persistent-kernel behavior better than asyncio.run(), which closes
        # its loop after every call and can break loop-bound async objects.
        if not loop.is_closed():
            asyncio.set_event_loop(loop)

def _agentstudio_execute_compiled(compiled, global_namespace):
    # eval() works for code compiled in both exec/eval modes.  When
    # PyCF_ALLOW_TOP_LEVEL_AWAIT is present, executing a coroutine code object
    # returns an awaitable which must be driven to completion explicitly.
    value = eval(compiled, global_namespace, global_namespace)
    return _agentstudio_run_awaitable(value)

def _agentstudio_notebook_pip(arguments):
    """Run %pip with the exact interpreter backing the Notebook session."""
    args = shlex.split(str(arguments or ""), posix=True)
    completed = subprocess.run([sys.executable, "-m", "pip", *args], check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"%pip 명령이 실패했습니다. 종료 코드: {completed.returncode}")
    importlib.invalidate_caches()
    return None

def _agentstudio_notebook_shell(command):
    """Execute a Jupyter-style ``!command`` from the Notebook CWD.

    ``!pip``/``!pip3`` and ``!python``/``!python3`` are pinned to the exact
    interpreter backing the current AgentStudio Notebook session so package
    installation and Python subprocesses cannot silently escape the project's
    ``.venv``.  Other commands (for example ``!uv add ...``) run through the
    platform shell while preserving the Notebook file directory as CWD.
    """
    raw = str(command or "").strip()
    if not raw:
        return None

    try:
        tokens = shlex.split(raw, posix=(os.name != "nt"))
    except ValueError as exc:
        raise ValueError(f"Notebook ! 명령을 해석하지 못했습니다: {exc}") from exc
    if not tokens:
        return None

    def _clean_token(value):
        text = str(value or "")
        if len(text) >= 2 and text[0] == text[-1] and text[0] in {"\"", "'"}:
            return text[1:-1]
        return text

    tokens = [_clean_token(token) for token in tokens]
    command_name = os.path.basename(tokens[0]).casefold()

    if command_name in {"pip", "pip.exe", "pip3", "pip3.exe"}:
        argv = [sys.executable, "-m", "pip", *tokens[1:]]
        completed = subprocess.run(argv, check=False)
    elif command_name in {"python", "python.exe", "python3", "python3.exe", "py", "py.exe"}:
        argv = [sys.executable, *tokens[1:]]
        completed = subprocess.run(argv, check=False)
    elif os.name == "nt":
        powershell = shutil.which("powershell.exe") or shutil.which("powershell")
        if powershell:
            completed = subprocess.run(
                [powershell, "-NoLogo", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", raw],
                check=False,
            )
        else:
            completed = subprocess.run(raw, shell=True, check=False)
    else:
        shell_path = os.environ.get("SHELL") or "/bin/sh"
        completed = subprocess.run(raw, shell=True, executable=shell_path, check=False)

    if completed.returncode != 0:
        raise RuntimeError(f"Notebook ! 명령이 실패했습니다. 종료 코드: {completed.returncode}")

    # A successful package-management command can make a newly installed
    # module importable in the same persistent Notebook worker immediately.
    importlib.invalidate_caches()
    return None

def _agentstudio_notebook_writefile(arguments, body, project_root):
    """Implement the safe Notebook subset of Jupyter ``%%writefile``.

    Relative paths are resolved from the Notebook working directory (CWD).
    The destination must remain inside the current AgentStudio project so a
    Notebook cell cannot accidentally overwrite arbitrary files elsewhere.
    Parent directories are created automatically, which is convenient for
    exercises such as ``%%writefile apps/streamlit_01_hello.py``.
    """
    tokens = shlex.split(str(arguments or "").strip(), posix=False)
    append = False
    filenames = []
    for token in tokens:
        normalized = str(token).strip()
        if normalized in {"-a", "--append"}:
            append = True
            continue
        if len(normalized) >= 2 and normalized[0] == normalized[-1] and normalized[0] in {"\"", "'"}:
            normalized = normalized[1:-1]
        filenames.append(normalized)

    if len(filenames) != 1 or not filenames[0]:
        raise ValueError("%%writefile 사용법: %%writefile [-a] <파일경로>")

    root_path = os.path.realpath(os.path.abspath(str(project_root or os.getcwd())))
    requested = filenames[0]
    target_path = requested if os.path.isabs(requested) else os.path.join(os.getcwd(), requested)
    target_path = os.path.realpath(os.path.abspath(target_path))
    try:
        inside_project = os.path.commonpath([root_path, target_path]) == root_path
    except ValueError:
        inside_project = False
    if not inside_project:
        raise ValueError("%%writefile 대상은 현재 AgentStudio 프로젝트 폴더 안에 있어야 합니다.")

    parent = os.path.dirname(target_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    mode = "a" if append else "w"
    with open(target_path, mode, encoding="utf-8", newline="") as handle:
        handle.write(str(body or ""))

    action = "Appending" if append else "Writing"
    display_path = os.path.relpath(target_path, os.getcwd())
    print(f"{action} {display_path}")
    return None

def _preprocess_notebook_code(source, project_root):
    """Translate supported Jupyter magics to executable Python.

    ``%pip`` and Jupyter-style ``!command`` stay line-oriented so traceback
    line numbers remain aligned. ``%%writefile`` is a cell magic: the first
    line is the directive and every
    following character is written to disk as UTF-8 instead of being executed.
    """
    text = str(source or "")
    lines = text.splitlines(True)

    # Jupyter treats a cell magic as the first meaningful line of the cell.
    # LLM-generated Notebook edits can legitimately leave one or more blank
    # lines before ``%%writefile``.  v5.291 only inspected physical line 1, so
    # a cell whose traceback showed the magic on line 2 fell through to the
    # Python parser and raised SyntaxError.  Find the first non-empty line and
    # keep all leading blank lines so traceback/cell line mapping stays stable.
    magic_index = None
    for index, raw_line in enumerate(lines):
        candidate = raw_line.rstrip("\r\n").lstrip("\ufeff \t")
        if candidate:
            magic_index = index
            break

    if magic_index is not None:
        magic_body = lines[magic_index].rstrip("\r\n")
        magic_stripped = magic_body.lstrip("\ufeff \t")
        lower_magic = magic_stripped.casefold()
        magic = "%%writefile"
        if lower_magic.startswith(magic) and (len(magic_stripped) == len(magic) or magic_stripped[len(magic)].isspace()):
            arguments = magic_stripped[len(magic):].strip()
            body = "".join(lines[magic_index + 1:])
            translated = ["\n" for _ in lines[:magic_index]]
            translated.append(
                f"_agentstudio_notebook_writefile({arguments!r}, {body!r}, {str(project_root or '')!r})\n"
            )
            # Preserve the source line count for predictable traceback/cell mapping.
            translated.extend("\n" for _ in lines[magic_index + 1:])
            return "".join(translated)

    translated = []
    for raw_line in lines:
        newline = "\n" if raw_line.endswith("\n") else ""
        body = raw_line[:-1] if newline else raw_line
        stripped = body.lstrip()
        indent = body[: len(body) - len(stripped)]
        lower = stripped.casefold()
        if lower.startswith("%pip") and (len(stripped) == 4 or stripped[4].isspace()):
            arguments = stripped[4:].strip()
            translated.append(f"{indent}_agentstudio_notebook_pip({arguments!r}){newline}")
            continue
        if stripped.startswith("!"):
            command = stripped[1:].strip()
            translated.append(f"{indent}_agentstudio_notebook_shell({command!r}){newline}")
            continue
        translated.append(raw_line)
    return "".join(translated)

namespace["_agentstudio_notebook_pip"] = _agentstudio_notebook_pip
namespace["_agentstudio_notebook_shell"] = _agentstudio_notebook_shell
namespace["_agentstudio_notebook_writefile"] = _agentstudio_notebook_writefile

for raw in sys.stdin:
    try:
        request = json.loads(raw)
        code = str(request.get("code") or "")
        filename = str(request.get("filename") or "<agentstudio>")
        root = str(request.get("root") or os.getcwd())
        # v5.276: Notebook 셀은 일반 Jupyter와 동일하게 현재 .ipynb 파일이
        # 들어 있는 폴더를 작업 디렉터리(CWD)로 사용한다. 프로젝트 root는
        # 인터프리터/세션/sys.path 기준으로 계속 유지한다.
        working_directory = str(request.get("working_directory") or root)
        reset = bool(request.get("reset"))
        capture_last_expression = bool(request.get("capture_last_expression"))
        notebook_mode = bool(request.get("notebook_mode"))
        raw_env_overrides = request.get("env_overrides") or {}
        env_overrides = {
            str(key): str(value)
            for key, value in raw_env_overrides.items()
            if isinstance(key, str) and value is not None
        } if isinstance(raw_env_overrides, dict) else {}
        if notebook_mode:
            code = _preprocess_notebook_code(code, root)

        if reset:
            namespace = {
                "__name__": "__main__",
                "__package__": None,
                "__builtins__": builtins,
                "_agentstudio_notebook_pip": _agentstudio_notebook_pip,
                "_agentstudio_notebook_shell": _agentstudio_notebook_shell,
                "_agentstudio_notebook_writefile": _agentstudio_notebook_writefile,
            }

        namespace["__file__"] = filename
        namespace["__name__"] = "__main__"
        namespace["__package__"] = None

        if working_directory:
            os.chdir(working_directory)

        if root and root not in sys.path:
            sys.path.insert(0, root)

        file_parent = os.path.dirname(filename) if filename and not filename.startswith("<") else ""
        if file_parent and os.path.isdir(file_parent) and file_parent not in sys.path:
            sys.path.insert(0, file_parent)

        stdout = io.StringIO()
        stderr = io.StringIO()
        ok = True
        error_type = ""
        error_message = ""
        trace = ""

        previous_env = {}
        missing_env = set()
        try:
            # 요청 단위 secret/env는 persistent worker 전체에 남기지 않는다.
            # Redis scratch 실행 시 DPAPI에서 복호화한 비밀번호도 이 블록 안에서만 노출된다.
            for env_key, env_value in env_overrides.items():
                if env_key in os.environ:
                    previous_env[env_key] = os.environ[env_key]
                else:
                    missing_env.add(env_key)
                os.environ[env_key] = env_value

            # 실행 코드가 에디터의 미저장 내용이거나 F8 선택 영역이어도
            # traceback이 디스크의 오래된 파일 내용을 다시 읽지 않도록
            # 현재 실행 코드를 linecache에 등록한다.
            linecache.cache[filename] = (
                len(code.encode("utf-8")),
                None,
                code.splitlines(True),
                filename,
            )
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                # Jupyter/IPython accepts ``await`` directly in a Code cell.
                # Python's compile() can provide the same semantics via
                # PyCF_ALLOW_TOP_LEVEL_AWAIT, but only in Notebook mode so
                # normal .py editor execution continues to enforce standard
                # Python script syntax.
                compile_flags = ast.PyCF_ALLOW_TOP_LEVEL_AWAIT if notebook_mode else 0
                if capture_last_expression:
                    tree = ast.parse(code, filename=filename, mode="exec")
                    if tree.body and isinstance(tree.body[-1], ast.Expr):
                        body_module = ast.Module(body=tree.body[:-1], type_ignores=getattr(tree, "type_ignores", []))
                        ast.fix_missing_locations(body_module)
                        if body_module.body:
                            body_compiled = compile(body_module, filename, "exec", flags=compile_flags)
                            _agentstudio_execute_compiled(body_compiled, namespace)
                        expression = ast.Expression(body=tree.body[-1].value)
                        ast.fix_missing_locations(expression)
                        expression_compiled = compile(expression, filename, "eval", flags=compile_flags)
                        result = _agentstudio_execute_compiled(expression_compiled, namespace)
                        if result is not None:
                            print(repr(result))
                    else:
                        compiled = compile(tree, filename, "exec", flags=compile_flags)
                        _agentstudio_execute_compiled(compiled, namespace)
                else:
                    compiled = compile(code, filename, "exec", flags=compile_flags)
                    _agentstudio_execute_compiled(compiled, namespace)
        except SystemExit as exc:
            ok = exc.code in (None, 0)
            if not ok:
                error_type = "SystemExit"
                error_message = str(exc.code)
                trace = traceback.format_exc()
        except BaseException as exc:
            ok = False
            error_type = type(exc).__name__
            error_message = str(exc)
            trace = traceback.format_exc()
        finally:
            for env_key in env_overrides:
                if env_key in previous_env:
                    os.environ[env_key] = previous_env[env_key]
                elif env_key in missing_env:
                    os.environ.pop(env_key, None)

        response = {
            "ok": ok,
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
            "error_type": error_type,
            "error_message": error_message,
            "traceback": trace,
        }
    except BaseException as exc:
        response = {
            "ok": False,
            "stdout": "",
            "stderr": "",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "traceback": traceback.format_exc(),
        }

    sys.__stdout__.write(RESPONSE_PREFIX + json.dumps(response, ensure_ascii=False) + "\n")
    sys.__stdout__.flush()
'''


@dataclass
class PythonExecutionSession:
    key: str
    root: str
    session_id: str
    interpreter: str
    process: subprocess.Popen[str]
    lock: threading.Lock = field(default_factory=threading.Lock)


_PIP_PACKAGE_BY_IMPORT = {
    "psycopg": "psycopg[binary]",
    "dotenv": "python-dotenv",
    "PIL": "Pillow",
    "cv2": "opencv-python",
    "yaml": "PyYAML",
    "sklearn": "scikit-learn",
    "bs4": "beautifulsoup4",
    "Crypto": "pycryptodome",
    "serial": "pyserial",
    "dateutil": "python-dateutil",
}


def _powershell_quote(value: str) -> str:
    return '"' + str(value).replace('"', '`"') + '"'


def _missing_module_name(response: dict[str, Any]) -> str:
    if str(response.get("error_type") or "") != "ModuleNotFoundError":
        return ""
    message = str(response.get("error_message") or "")
    match = re.search(r"No module named ['\"]([^'\"]+)['\"]", message)
    return match.group(1).split(".", 1)[0] if match else ""


def _dependency_diagnostic(
    *,
    response: dict[str, Any],
    interpreter: str,
    project_root: Path,
) -> dict[str, Any] | None:
    module_name = _missing_module_name(response)
    if not module_name:
        return None

    package_name = _PIP_PACKAGE_BY_IMPORT.get(module_name, module_name)
    interpreter_text = str(interpreter)
    if sys.platform == "win32" or interpreter_text.lower().endswith(".exe"):
        install_command = (
            f"& {_powershell_quote(interpreter_text)} -m pip install "
            f"{_powershell_quote(package_name)}"
        )
    else:
        import shlex
        install_command = (
            f"{shlex.quote(interpreter_text)} -m pip install "
            f"{shlex.quote(package_name)}"
        )

    requirements_path = project_root / "requirements.txt"
    requirements_command = ""
    if requirements_path.exists() and requirements_path.is_file():
        if sys.platform == "win32" or interpreter_text.lower().endswith(".exe"):
            requirements_command = (
                f"& {_powershell_quote(interpreter_text)} -m pip install -r "
                f"{_powershell_quote(str(requirements_path))}"
            )
        else:
            import shlex
            requirements_command = (
                f"{shlex.quote(interpreter_text)} -m pip install -r "
                f"{shlex.quote(str(requirements_path))}"
            )

    return {
        "code": "PYTHON_MODULE_NOT_FOUND",
        "missing_module": module_name,
        "pip_package": package_name,
        "interpreter": interpreter_text,
        "install_command": install_command,
        "requirements_path": str(requirements_path) if requirements_command else "",
        "requirements_command": requirements_command,
        "message": (
            f"현재 선택된 Python 환경에 '{module_name}' 모듈이 설치되어 있지 않습니다. "
            f"이 실행은 {interpreter_text} 환경을 사용합니다."
        ),
    }


class PythonExecutionManager:
    """Persistent project Python execution sessions for editor F5/F8.

    A lightweight worker is launched with the project's own Python interpreter.
    The worker keeps one globals namespace alive so F8 selections can share
    variables/functions across executions. F5 resets the namespace first, which
    mirrors a fresh script run while still leaving the resulting namespace
    available to later F8 selections.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, PythonExecutionSession] = {}
        self._sessions_lock = threading.Lock()
        self._cancelled_sessions: set[str] = set()

    @staticmethod
    def _session_key(root: str, session_id: str | None) -> str:
        normalized = str(Path(root).expanduser().resolve())
        if sys.platform == "win32":
            normalized = normalized.casefold()
        return f"{normalized}::{session_id or 'default'}"

    @staticmethod
    def _project_python(project_root: Path) -> Path | None:
        candidates = [
            project_root / ".venv" / "Scripts" / "python.exe",
            project_root / "venv" / "Scripts" / "python.exe",
            project_root / ".venv" / "bin" / "python",
            project_root / "venv" / "bin" / "python",
        ]
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                return candidate.resolve()
        return None

    def resolve_interpreter(self, root: str) -> str:
        project_root = Path(root).expanduser().resolve()
        if not project_root.exists() or not project_root.is_dir():
            raise FileNotFoundError(str(project_root))

        project_python = self._project_python(project_root)
        if project_python:
            return str(project_python)

        system_python = shutil.which("python") or shutil.which("python3")
        if system_python:
            return str(Path(system_python).resolve())

        return str(Path(sys.executable).resolve())

    def _start(self, root: str, session_id: str | None) -> PythonExecutionSession:
        project_root = Path(root).expanduser().resolve()
        interpreter = self.resolve_interpreter(str(project_root))
        key = self._session_key(str(project_root), session_id)

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"

        process = subprocess.Popen(
            [interpreter, "-u", "-c", _WORKER_CODE],
            cwd=str(project_root),
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            # v5.234: 사용자 코드가 실행한 docker/git/npm 같은 자식 프로세스의
            # native stderr도 Worker stdout 통신선으로 합쳐 한 곳에서 안전하게 drain한다.
            # 응답 자체는 RESPONSE_PREFIX로 framing하므로 일반 출력과 충돌하지 않는다.
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=(
                subprocess.CREATE_NO_WINDOW
                if sys.platform == "win32"
                else 0
            ),
        )

        return PythonExecutionSession(
            key=key,
            root=str(project_root),
            session_id=session_id or "default",
            interpreter=interpreter,
            process=process,
        )

    @staticmethod
    def _same_interpreter(left: str, right: str) -> bool:
        try:
            left_path = str(Path(left).expanduser().resolve())
            right_path = str(Path(right).expanduser().resolve())
        except Exception:
            left_path = str(left or '')
            right_path = str(right or '')
        if sys.platform == 'win32':
            return left_path.casefold() == right_path.casefold()
        return left_path == right_path

    def _get_or_create(self, root: str, session_id: str | None) -> PythonExecutionSession:
        key = self._session_key(root, session_id)
        expected_interpreter = self.resolve_interpreter(root)
        stale_session: PythonExecutionSession | None = None
        with self._sessions_lock:
            session = self._sessions.get(key)
            if session and session.process.poll() is None and self._same_interpreter(session.interpreter, expected_interpreter):
                return session
            if session:
                stale_session = self._sessions.pop(key, None)

        # A project venv can be created/replaced while AgentStudio stays open.
        # Do not keep executing the Notebook in the worker that was bound to the
        # old interpreter; this was the main cause of search/tab-switch followed
        # by intermittent ModuleNotFoundError until the file was closed/reopened.
        if stale_session:
            self._stop_session_process(stale_session, timeout=1.0)

        with self._sessions_lock:
            session = self._sessions.get(key)
            if session and session.process.poll() is None and self._same_interpreter(session.interpreter, expected_interpreter):
                return session
            session = self._start(root, session_id)
            self._sessions[key] = session
            return session

    def execute(
        self,
        *,
        root: str,
        code: str,
        relative_path: str = "",
        session_id: str | None = None,
        reset: bool = False,
        capture_last_expression: bool = False,
        notebook_mode: bool = False,
        cell_index: int | None = None,
        env_overrides: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        project_root = Path(root).expanduser().resolve()
        if not project_root.exists() or not project_root.is_dir():
            raise FileNotFoundError(str(project_root))

        relative = str(relative_path or "").replace("\\", "/").lstrip("/")
        filename_path = (project_root / relative).resolve() if relative else project_root / "<selection>"
        if relative:
            try:
                filename_path.relative_to(project_root)
            except ValueError as exc:
                raise ValueError("프로젝트 root 밖의 Python 파일은 실행할 수 없습니다.") from exc

        # A real .ipynb path points at JSON, not at the Python cell being executed.
        # Use a non-existent cell-specific pseudo filename for compile()/traceback so
        # SyntaxError never renders notebook JSON such as `"cells": [` as source.
        execution_filename = str(filename_path)
        execution_working_directory = project_root
        if notebook_mode and relative.lower().endswith(".ipynb"):
            display_cell = (int(cell_index) + 1) if cell_index is not None else 1
            execution_filename = f"{filename_path}.cell-{display_cell}.py"
            # 상대 경로(Path/open/CSV/JSON/Firebase key 등)는 Notebook 파일
            # 위치를 기준으로 해석한다. Worker 프로세스 자체는 프로젝트별로
            # 재사용하므로 매 셀 실행 요청마다 CWD를 이 경로로 다시 맞춘다.
            execution_working_directory = filename_path.parent

        session = self._get_or_create(str(project_root), session_id)
        request = {
            "root": str(project_root),
            "working_directory": str(execution_working_directory),
            "code": str(code or ""),
            "filename": execution_filename,
            "reset": bool(reset),
            "capture_last_expression": bool(capture_last_expression),
            "notebook_mode": bool(notebook_mode),
            "env_overrides": {str(k): str(v) for k, v in (env_overrides or {}).items() if v is not None},
        }

        with session.lock:
            if session.process.poll() is not None:
                with self._sessions_lock:
                    self._sessions.pop(session.key, None)
                session = self._get_or_create(str(project_root), session_id)

            if session.process.stdin is None or session.process.stdout is None:
                raise RuntimeError("Python 실행 세션의 stdin/stdout을 사용할 수 없습니다.")

            session.process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
            session.process.stdin.flush()

            # v5.234: Worker stdout에는 Python 코드가 실행한 native 자식 프로세스
            # (docker/git/npm 등)의 출력이 직접 섞일 수 있다. 예전에는 첫 줄을 곧바로
            # json.loads()해 `Expecting value: line 1 column 1` 오류가 발생했다.
            # 이제 고유 framing prefix가 붙은 응답 줄이 나올 때까지 일반 출력을
            # 수집하고, prefix 뒤의 JSON만 내부 프로토콜로 파싱한다.
            native_output_parts: list[str] = []
            response_json = ""
            while True:
                response_line = session.process.stdout.readline()
                if not response_line:
                    with self._sessions_lock:
                        cancelled = session.key in self._cancelled_sessions
                        if cancelled:
                            self._cancelled_sessions.discard(session.key)
                    if cancelled:
                        response = {
                            "ok": False,
                            "cancelled": True,
                            "stdout": "".join(native_output_parts),
                            "stderr": "",
                            "error_type": "ExecutionCancelled",
                            "error_message": "사용자가 Python 실행을 중지했습니다.",
                            "traceback": "",
                        }
                        response_json = ""
                        break
                    raise RuntimeError(
                        "Python 실행 세션이 프로토콜 응답 전에 종료되었습니다."
                        + (
                            f"\n자식 프로세스 출력:\n{''.join(native_output_parts)[-4000:]}"
                            if native_output_parts
                            else ""
                        )
                    )

                marker_index = response_line.find(_WORKER_RESPONSE_PREFIX)
                if marker_index < 0:
                    native_output_parts.append(response_line)
                    continue

                if marker_index > 0:
                    native_output_parts.append(response_line[:marker_index])
                response_json = response_line[marker_index + len(_WORKER_RESPONSE_PREFIX):].strip()
                if response_json:
                    break

            if response_json:
                try:
                    response = json.loads(response_json)
                except json.JSONDecodeError as exc:
                    raise RuntimeError(
                        "Python 실행 세션의 내부 응답 JSON을 해석하지 못했습니다: "
                        f"{exc}. 응답={response_json[:500]!r}"
                    ) from exc

        native_output = "".join(native_output_parts)
        if native_output:
            # subprocess.run(..., capture_output=False) 같은 native 출력도 실행 결과에
            # 포함해 사용자가 터미널에서 볼 수 있게 한다.
            response["stdout"] = native_output + str(response.get("stdout") or "")

        # v5.235: ModuleNotFoundError를 단순 traceback으로 끝내지 않고, 실제로
        # 선택된 프로젝트 Python과 그 환경에 설치할 정확한 pip 명령을 반환한다.
        # 환경 변경은 자동 수행하지 않는다.
        dependency = _dependency_diagnostic(
            response=response,
            interpreter=session.interpreter,
            project_root=project_root,
        )
        if dependency:
            response["dependency_diagnostic"] = dependency

        response.update({
            "interpreter": session.interpreter,
            "session_id": session.session_id,
            "root": str(project_root),
            "relative_path": relative,
            "working_directory": str(execution_working_directory),
            "persistent": True,
            "reset": bool(reset),
            "capture_last_expression": bool(capture_last_expression),
            "notebook_mode": bool(notebook_mode),
            "cell_index": cell_index,
        })
        return response

    @staticmethod
    def _stop_session_process(session: PythonExecutionSession, timeout: float = 2.0) -> None:
        """Stop a persistent worker and wait for Windows file handles to close."""
        process = session.process
        if process.poll() is not None:
            return
        try:
            process.terminate()
            process.wait(timeout=timeout)
            return
        except subprocess.TimeoutExpired:
            pass
        except Exception:
            return
        try:
            process.kill()
            process.wait(timeout=1.0)
        except Exception:
            pass

    def stop(self, root: str, session_id: str | None = None) -> bool:
        """Immediately stop one running editor/notebook Python worker.

        The worker is intentionally discarded because Python cannot safely
        interrupt arbitrary user code in the same persistent interpreter.
        The next run automatically starts a fresh session.
        """
        key = self._session_key(root, session_id)
        with self._sessions_lock:
            session = self._sessions.pop(key, None)
            if session:
                self._cancelled_sessions.add(key)
        if not session:
            return False
        self._stop_session_process(session, timeout=0.8)
        return True

    def reset(self, root: str, session_id: str | None = None) -> bool:
        key = self._session_key(root, session_id)
        with self._sessions_lock:
            session = self._sessions.pop(key, None)
        if not session:
            return False
        self._stop_session_process(session)
        return True

    def reset_all_for_root(self, root: str) -> list[str]:
        """Stop every editor/notebook Python worker for one project root.

        Multiple terminal tabs create multiple Python session ids. A SQLite
        connection may have been created in any one of them, so lock recovery
        must release all AgentStudio-owned workers for the project.
        """
        project_root = str(Path(root).expanduser().resolve())
        compare_root = project_root.casefold() if sys.platform == "win32" else project_root
        with self._sessions_lock:
            matched: list[PythonExecutionSession] = []
            for key, session in list(self._sessions.items()):
                session_root = str(Path(session.root).expanduser().resolve())
                compare_session_root = session_root.casefold() if sys.platform == "win32" else session_root
                if compare_session_root == compare_root:
                    matched.append(session)
                    self._sessions.pop(key, None)

        for session in matched:
            self._stop_session_process(session)
        return [session.session_id for session in matched]

    def status(self, root: str, session_id: str | None = None) -> dict[str, Any]:
        key = self._session_key(root, session_id)
        session = self._sessions.get(key)
        resolved_interpreter = self.resolve_interpreter(root)
        active = bool(session and session.process.poll() is None)
        bound_interpreter = session.interpreter if active and session else ''
        stale_interpreter = bool(
            active
            and bound_interpreter
            and not self._same_interpreter(bound_interpreter, resolved_interpreter)
        )
        return {
            "ok": True,
            "active": active,
            "persistent": True,
            "interpreter": bound_interpreter or resolved_interpreter,
            "bound_interpreter": bound_interpreter,
            "resolved_interpreter": resolved_interpreter,
            "stale_interpreter": stale_interpreter,
            "session_id": session_id or "default",
        }


python_execution_manager = PythonExecutionManager()
