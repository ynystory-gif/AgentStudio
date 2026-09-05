from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


_WORKER_RESPONSE_PREFIX = '__AGENTSTUDIO_PY_RESPONSE_V1__'
_WORKER_EVENT_PREFIX = '__AGENTSTUDIO_PY_EVENT_V1__'

_WORKER_RUNTIME_PATH = Path(__file__).with_name("python_worker_runtime.py")


@dataclass
class PythonExecutionSession:
    key: str
    root: str
    session_id: str
    interpreter: str
    process: subprocess.Popen[str]
    lock: threading.Lock = field(default_factory=threading.Lock)
    debug_active: bool = False
    debug_cell_index: int | None = None
    last_debug_state: dict[str, Any] = field(default_factory=dict)


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


def _clean_cli_token(value: str) -> str:
    text = str(value or "")
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    return text


def _split_cli_arguments(value: str) -> list[str]:
    try:
        tokens = shlex.split(str(value or ""), posix=(os.name != "nt"))
    except ValueError as exc:
        raise ValueError(f"Notebook pip 명령을 해석하지 못했습니다: {exc}") from exc
    return [_clean_cli_token(token) for token in tokens]


def _notebook_pip_arguments(line: str) -> list[str] | None:
    """Return pip arguments for one Notebook package-management line."""
    raw = str(line or "").strip()
    if not raw or raw.startswith("#"):
        return None
    if re.match(r"^%pip(?:\s|$)", raw, flags=re.IGNORECASE):
        return _split_cli_arguments(raw[4:].strip())
    if not raw.startswith("!"):
        return None

    tokens = _split_cli_arguments(raw[1:].strip())
    if not tokens:
        return None
    command_name = os.path.basename(tokens[0]).casefold()
    if command_name in {"pip", "pip.exe", "pip3", "pip3.exe"}:
        return tokens[1:]
    if command_name in {"python", "python.exe", "python3", "python3.exe", "py", "py.exe"}:
        if len(tokens) >= 3 and tokens[1].casefold() == "-m" and tokens[2].casefold() == "pip":
            return tokens[3:]
    return None


def _split_notebook_package_cell(code: str) -> tuple[list[list[str]], str]:
    commands: list[list[str]] = []
    remaining_lines: list[str] = []
    for line in str(code or "").splitlines():
        pip_args = _notebook_pip_arguments(line)
        if pip_args is None:
            remaining_lines.append(line)
        else:
            commands.append(pip_args)
            # Preserve source line numbers for traceback/debug parity.
            remaining_lines.append("")
    return commands, "\n".join(remaining_lines)


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

        worker_runtime = _WORKER_RUNTIME_PATH.resolve()
        if not worker_runtime.exists() or not worker_runtime.is_file():
            raise FileNotFoundError(f"Python Worker Runtime 파일을 찾을 수 없습니다: {worker_runtime}")

        process = subprocess.Popen(
            [interpreter, "-u", str(worker_runtime)],
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

    @staticmethod
    def _read_worker_response(session: PythonExecutionSession) -> tuple[dict[str, Any], str]:
        if session.process.stdout is None:
            raise RuntimeError("Python 실행 세션의 stdout을 사용할 수 없습니다.")
        native_output_parts: list[str] = []
        while True:
            response_line = session.process.stdout.readline()
            if not response_line:
                raise RuntimeError(
                    "Python 실행 세션이 프로토콜 응답 전에 종료되었습니다."
                    + (f"\n자식 프로세스 출력:\n{''.join(native_output_parts)[-4000:]}" if native_output_parts else "")
                )
            marker_index = response_line.find(_WORKER_RESPONSE_PREFIX)
            if marker_index < 0:
                native_output_parts.append(response_line)
                continue
            if marker_index > 0:
                native_output_parts.append(response_line[:marker_index])
            response_json = response_line[marker_index + len(_WORKER_RESPONSE_PREFIX):].strip()
            if not response_json:
                continue
            try:
                response = json.loads(response_json)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    "Python 실행 세션의 내부 응답 JSON을 해석하지 못했습니다: "
                    f"{exc}. 응답={response_json[:500]!r}"
                ) from exc
            return response, "".join(native_output_parts)

    @staticmethod
    def _execution_context(
        *,
        root: str,
        relative_path: str = "",
        notebook_mode: bool = False,
        cell_index: int | None = None,
    ) -> tuple[Path, str, str, Path]:
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
        execution_filename = str(filename_path)
        execution_working_directory = project_root
        if notebook_mode and relative.lower().endswith(".ipynb"):
            display_cell = (int(cell_index) + 1) if cell_index is not None else 1
            execution_filename = f"{filename_path}.cell-{display_cell}.py"
            execution_working_directory = filename_path.parent
        return project_root, relative, execution_filename, execution_working_directory

    def debug_start(
        self,
        *,
        root: str,
        code: str,
        relative_path: str,
        session_id: str | None,
        cell_index: int,
        breakpoints: list[int] | None = None,
        reset: bool = False,
        env_overrides: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        project_root, relative, execution_filename, working_directory = self._execution_context(
            root=root, relative_path=relative_path, notebook_mode=True, cell_index=cell_index
        )
        session = self._get_or_create(str(project_root), session_id)
        with session.lock:
            if session.debug_active:
                return {**session.last_debug_state, "debug_active": True, "event": "paused"}
            if session.process.stdin is None:
                raise RuntimeError("Python 디버그 세션의 stdin을 사용할 수 없습니다.")
            request = {
                "action": "debug_start",
                "root": str(project_root),
                "working_directory": str(working_directory),
                "code": str(code or ""),
                "filename": execution_filename,
                "reset": bool(reset),
                "capture_last_expression": False,
                "notebook_mode": True,
                "cell_index": int(cell_index),
                "breakpoints": [int(line) for line in (breakpoints or []) if int(line) > 0],
                "env_overrides": {str(k): str(v) for k, v in (env_overrides or {}).items() if v is not None},
            }
            session.process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
            session.process.stdin.flush()
            response, native_output = self._read_worker_response(session)
            if native_output:
                response["stdout"] = native_output + str(response.get("stdout") or "")
            session.debug_active = bool(response.get("debug_active")) and str(response.get("event") or "") in {"paused", "evaluate"}
            session.debug_cell_index = int(cell_index) if session.debug_active else None
            session.last_debug_state = dict(response)
        response.update({
            "interpreter": session.interpreter,
            "session_id": session.session_id,
            "root": str(project_root),
            "relative_path": relative,
            "notebook_mode": True,
            "cell_index": int(cell_index),
        })
        return response

    def debug_command(
        self,
        *,
        root: str,
        session_id: str | None,
        command: str,
        expression: str = "",
    ) -> dict[str, Any]:
        key = self._session_key(root, session_id)
        with self._sessions_lock:
            session = self._sessions.get(key)
        if not session or session.process.poll() is not None:
            raise RuntimeError("활성 Notebook 디버그 세션이 없습니다.")
        with session.lock:
            if not session.debug_active:
                raise RuntimeError("Notebook 디버거가 현재 일시정지 상태가 아닙니다.")
            if session.process.stdin is None:
                raise RuntimeError("Python 디버그 세션의 stdin을 사용할 수 없습니다.")
            packet = {"action": "debug_command", "command": str(command or "").strip().lower()}
            if expression:
                packet["expression"] = str(expression)
            session.process.stdin.write(json.dumps(packet, ensure_ascii=False) + "\n")
            session.process.stdin.flush()
            response, native_output = self._read_worker_response(session)
            if native_output:
                response["stdout"] = native_output + str(response.get("stdout") or "")
            event = str(response.get("event") or "")
            session.debug_active = bool(response.get("debug_active")) and event in {"paused", "evaluate"}
            if not session.debug_active:
                session.debug_cell_index = None
            session.last_debug_state = dict(response)
        response.update({
            "interpreter": session.interpreter,
            "session_id": session.session_id,
            "root": str(Path(root).expanduser().resolve()),
        })
        return response

    def debug_status(self, root: str, session_id: str | None = None) -> dict[str, Any]:
        key = self._session_key(root, session_id)
        with self._sessions_lock:
            session = self._sessions.get(key)
        if not session or session.process.poll() is not None:
            return {"ok": True, "debug_active": False, "event": "idle"}
        return {
            "ok": True,
            "debug_active": bool(session.debug_active),
            "event": str(session.last_debug_state.get("event") or ("paused" if session.debug_active else "idle")),
            "cell_index": session.debug_cell_index,
            "line": session.last_debug_state.get("line"),
            "variables": session.last_debug_state.get("variables") or [],
            "stack": session.last_debug_state.get("stack") or [],
            "source_line": session.last_debug_state.get("source_line") or "",
        }

    def execute_package_cell(
        self,
        *,
        root: str,
        code: str,
        relative_path: str = "",
        session_id: str | None = None,
        capture_last_expression: bool = False,
        notebook_mode: bool = True,
        cell_index: int | None = None,
        env_overrides: dict[str, str] | None = None,
        timeout: int = 900,
    ) -> dict[str, Any]:
        """Execute Notebook pip commands outside the persistent Python worker."""
        project_root, relative, _execution_filename, working_directory = self._execution_context(
            root=root,
            relative_path=relative_path,
            notebook_mode=notebook_mode,
            cell_index=cell_index,
        )
        package_commands, remaining_code = _split_notebook_package_cell(code)
        if not package_commands:
            raise ValueError("실행할 Notebook pip 패키지 명령을 찾지 못했습니다.")

        interpreter = self.resolve_interpreter(str(project_root))
        # Release imported extension modules/DLL file handles before pip mutates
        # the environment. The next Python execution creates a clean worker.
        worker_was_reset = self.reset(str(project_root), session_id)

        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        for key, value in (env_overrides or {}).items():
            if value is not None:
                env[str(key)] = str(value)

        stdout_parts: list[str] = []
        stderr_parts: list[str] = []
        command_summaries: list[str] = []
        for pip_args in package_commands:
            argv = [interpreter, "-m", "pip", *pip_args]
            command_summaries.append(" ".join(["python", "-m", "pip", *pip_args]))
            try:
                completed = subprocess.run(
                    argv,
                    cwd=str(working_directory),
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=max(30, int(timeout or 900)),
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                return {
                    "ok": False,
                    "stdout": "".join(stdout_parts) + str(exc.stdout or ""),
                    "stderr": "".join(stderr_parts) + str(exc.stderr or ""),
                    "error_type": "PackageInstallTimeout",
                    "error_message": f"pip 실행이 {max(30, int(timeout or 900))}초를 초과했습니다.",
                    "traceback": "",
                    "interpreter": interpreter,
                    "session_id": session_id or "default",
                    "root": str(project_root),
                    "relative_path": relative,
                    "working_directory": str(working_directory),
                    "package_management": True,
                    "package_commands": command_summaries,
                    "worker_reset": worker_was_reset,
                }

            if completed.stdout:
                stdout_parts.append(completed.stdout)
            if completed.stderr:
                stderr_parts.append(completed.stderr)
            if completed.returncode != 0:
                return {
                    "ok": False,
                    "stdout": "".join(stdout_parts),
                    "stderr": "".join(stderr_parts),
                    "error_type": "PackageInstallError",
                    "error_message": f"pip 명령이 실패했습니다. 종료 코드: {completed.returncode}",
                    "traceback": "",
                    "returncode": completed.returncode,
                    "interpreter": interpreter,
                    "session_id": session_id or "default",
                    "root": str(project_root),
                    "relative_path": relative,
                    "working_directory": str(working_directory),
                    "package_management": True,
                    "package_commands": command_summaries,
                    "worker_reset": worker_was_reset,
                }

        package_stdout = "".join(stdout_parts)
        package_stderr = "".join(stderr_parts)
        if remaining_code.strip():
            result = self.execute(
                root=str(project_root),
                code=remaining_code,
                relative_path=relative,
                session_id=session_id,
                reset=False,
                capture_last_expression=capture_last_expression,
                notebook_mode=notebook_mode,
                cell_index=cell_index,
                env_overrides=env_overrides,
            )
            result["stdout"] = package_stdout + str(result.get("stdout") or "")
            result["stderr"] = package_stderr + str(result.get("stderr") or "")
        else:
            result = {
                "ok": True,
                "stdout": package_stdout,
                "stderr": package_stderr,
                "error_type": "",
                "error_message": "",
                "traceback": "",
                "interpreter": interpreter,
                "session_id": session_id or "default",
                "root": str(project_root),
                "relative_path": relative,
                "working_directory": str(working_directory),
                "persistent": True,
                "notebook_mode": notebook_mode,
                "cell_index": cell_index,
            }

        result.update({
            "package_management": True,
            "package_commands": command_summaries,
            "worker_reset": worker_was_reset,
            "package_environment_refreshed": bool(result.get("ok")),
        })
        return result

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
        if session.debug_active:
            raise RuntimeError("Notebook 디버거가 일시정지되어 있습니다. 디버그를 계속하거나 종료한 뒤 일반 실행을 사용하세요.")
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
                    # v5.488: preserve native output and discard a dead worker.
                    with self._sessions_lock:
                        self._sessions.pop(session.key, None)
                    response = {
                        "ok": False,
                        "stdout": "".join(native_output_parts),
                        "stderr": "",
                        "error_type": "PythonWorkerExited",
                        "error_message": "Python 실행 세션이 최종 응답 전에 종료되었습니다. 다음 실행은 새 세션에서 자동 시작됩니다.",
                        "traceback": "",
                        "session_recovered": True,
                    }
                    response_json = ""
                    break

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
        if native_output and not bool(response.get("session_recovered")):
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

    def execute_stream(
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
    ):
        """Yield Notebook display/clear events while the persistent worker runs.

        The final packet is ``{"type": "result", "result": ...}``.  Rich
        display events are also folded into ``result.rich_outputs`` so the last
        visible frame can be saved back into the .ipynb document.
        """
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

        execution_filename = str(filename_path)
        execution_working_directory = project_root
        if notebook_mode and relative.lower().endswith(".ipynb"):
            display_cell = (int(cell_index) + 1) if cell_index is not None else 1
            execution_filename = f"{filename_path}.cell-{display_cell}.py"
            execution_working_directory = filename_path.parent

        session = self._get_or_create(str(project_root), session_id)
        if session.debug_active:
            raise RuntimeError("Notebook 디버거가 일시정지되어 있습니다. 디버그를 계속하거나 종료한 뒤 일반 실행을 사용하세요.")

        request = {
            "root": str(project_root),
            "working_directory": str(execution_working_directory),
            "code": str(code or ""),
            "filename": execution_filename,
            "reset": bool(reset),
            "capture_last_expression": bool(capture_last_expression),
            "notebook_mode": bool(notebook_mode),
            "cell_index": cell_index,
            "env_overrides": {str(k): str(v) for k, v in (env_overrides or {}).items() if v is not None},
        }

        yield {
            "type": "start",
            "cell_index": cell_index,
            "session_id": session.session_id,
            "interpreter": session.interpreter,
        }

        native_output_parts: list[str] = []
        rich_outputs: list[dict[str, Any]] = []
        pending_clear_wait = False
        response: dict[str, Any] | None = None

        with session.lock:
            if session.process.poll() is not None:
                with self._sessions_lock:
                    self._sessions.pop(session.key, None)
                session = self._get_or_create(str(project_root), session_id)

            if session.process.stdin is None or session.process.stdout is None:
                raise RuntimeError("Python 실행 세션의 stdin/stdout을 사용할 수 없습니다.")

            session.process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
            session.process.stdin.flush()

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
                        break
                    # v5.488: keep NDJSON final-result semantics when the worker exits.
                    with self._sessions_lock:
                        self._sessions.pop(session.key, None)
                    response = {
                        "ok": False,
                        "stdout": "".join(native_output_parts),
                        "stderr": "",
                        "error_type": "PythonWorkerExited",
                        "error_message": "Python 실행 세션이 최종 응답 전에 종료되어 세션을 자동 복구했습니다. 다음 실행은 새 Python 세션에서 시작됩니다.",
                        "traceback": "",
                        "session_recovered": True,
                    }
                    break

                event_index = response_line.find(_WORKER_EVENT_PREFIX)
                response_index = response_line.find(_WORKER_RESPONSE_PREFIX)

                if event_index >= 0 and (response_index < 0 or event_index < response_index):
                    if event_index > 0:
                        native_output_parts.append(response_line[:event_index])
                    event_json = response_line[event_index + len(_WORKER_EVENT_PREFIX):].strip()
                    if not event_json:
                        continue
                    try:
                        event = json.loads(event_json)
                    except json.JSONDecodeError:
                        native_output_parts.append(response_line)
                        continue

                    event_name = str(event.get("event") or "")
                    if event_name == "clear_output":
                        if bool(event.get("wait")):
                            # Jupyter semantics: defer the clear until replacement
                            # output is actually available. This keeps the previous
                            # animation frame visible and prevents a blank flash.
                            pending_clear_wait = True
                        else:
                            rich_outputs.clear()
                            pending_clear_wait = False
                    else:
                        output = event.get("output")
                        if isinstance(output, dict):
                            if pending_clear_wait:
                                rich_outputs.clear()
                                pending_clear_wait = False
                            rich_outputs.append(output)
                    yield {"type": "event", "event": event}
                    continue

                if response_index >= 0:
                    if response_index > 0:
                        native_output_parts.append(response_line[:response_index])
                    response_json = response_line[response_index + len(_WORKER_RESPONSE_PREFIX):].strip()
                    if not response_json:
                        continue
                    try:
                        response = json.loads(response_json)
                    except json.JSONDecodeError as exc:
                        raise RuntimeError(
                            "Python 실행 세션의 내부 응답 JSON을 해석하지 못했습니다: "
                            f"{exc}. 응답={response_json[:500]!r}"
                        ) from exc
                    break

                native_output_parts.append(response_line)

        if response is None:
            response = {
                "ok": False,
                "stdout": "",
                "stderr": "",
                "error_type": "NotebookStreamingError",
                "error_message": "Notebook 스트리밍 실행 결과를 받지 못했습니다.",
                "traceback": "",
            }

        native_output = "".join(native_output_parts)
        if native_output and not bool(response.get("session_recovered")):
            response["stdout"] = native_output + str(response.get("stdout") or "")

        dependency = _dependency_diagnostic(
            response=response,
            interpreter=session.interpreter,
            project_root=project_root,
        )
        if dependency:
            response["dependency_diagnostic"] = dependency

        if rich_outputs:
            response["rich_outputs"] = rich_outputs

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
            "streaming": True,
        })
        yield {"type": "result", "result": response}

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
