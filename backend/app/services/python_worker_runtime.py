import ast
import asyncio
import base64
import bdb
import builtins
import contextlib
import io
import importlib
import inspect
import json
import linecache
import os
import shlex
import shutil
import subprocess
import sys
import traceback

RESPONSE_PREFIX = '__AGENTSTUDIO_PY_RESPONSE_V1__'
EVENT_PREFIX = '__AGENTSTUDIO_PY_EVENT_V1__'

namespace = {
    "__name__": "__main__",
    "__package__": None,
    "__builtins__": builtins,
}

# v5.411: Notebook rich-output streaming.
# AgentStudio does not embed a full ipykernel, so IPython.display would otherwise
# degrade to text such as "Figure(700x600)".  These hooks serialize display()
# payloads (especially Matplotlib figures) to the same MIME bundle shape used by
# Jupyter and emit them immediately over the worker stdout protocol.
def _agentstudio_emit_notebook_event(payload):
    try:
        sys.__stdout__.write(EVENT_PREFIX + json.dumps(payload, ensure_ascii=False) + "\n")
        sys.__stdout__.flush()
    except BaseException:
        pass

def _agentstudio_notebook_mime_bundle(value):
    data = {}
    metadata = {}
    if value is None:
        return data, metadata

    # Matplotlib Figure and compatible objects.
    if hasattr(value, "savefig") and callable(getattr(value, "savefig", None)):
        try:
            buffer = io.BytesIO()
            value.savefig(buffer, format="png", bbox_inches="tight")
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
            if encoded:
                data["image/png"] = encoded
        except BaseException:
            pass

    rich_methods = (
        ("_repr_png_", "image/png"),
        ("_repr_svg_", "image/svg+xml"),
        ("_repr_html_", "text/html"),
        ("_repr_markdown_", "text/markdown"),
    )
    for method_name, mime_type in rich_methods:
        if mime_type in data:
            continue
        method = getattr(value, method_name, None)
        if not callable(method):
            continue
        try:
            rendered = method()
            if rendered is None:
                continue
            if isinstance(rendered, tuple):
                rendered, rich_metadata = rendered
                if isinstance(rich_metadata, dict):
                    metadata[mime_type] = rich_metadata
            if mime_type == "image/png" and isinstance(rendered, (bytes, bytearray)):
                rendered = base64.b64encode(bytes(rendered)).decode("ascii")
            if rendered is not None:
                data[mime_type] = rendered
        except BaseException:
            pass

    if not data:
        try:
            data["text/plain"] = repr(value)
        except BaseException:
            data["text/plain"] = f"<{type(value).__name__}>"
    return data, metadata

def _agentstudio_notebook_display(*objects, display_id=None, raw=False, metadata=None, **kwargs):
    for value in objects:
        if raw and isinstance(value, dict):
            data = dict(value)
            rich_metadata = dict(metadata or {})
        else:
            data, rich_metadata = _agentstudio_notebook_mime_bundle(value)
            if isinstance(metadata, dict):
                rich_metadata.update(metadata)
        event = {
            "event": "display_data",
            "output": {
                "output_type": "display_data",
                "data": data,
                "metadata": rich_metadata,
            },
        }
        if display_id:
            event["display_id"] = str(display_id)
        _agentstudio_emit_notebook_event(event)
    return None

def _agentstudio_notebook_clear_output(wait=False):
    _agentstudio_emit_notebook_event({
        "event": "clear_output",
        "wait": bool(wait),
    })
    return None

def _agentstudio_install_notebook_display_hooks():
    try:
        import IPython.display as _agentstudio_ipython_display
        _agentstudio_ipython_display.display = _agentstudio_notebook_display
        _agentstudio_ipython_display.clear_output = _agentstudio_notebook_clear_output
    except BaseException:
        # IPython is optional. Notebook Python execution remains usable without it.
        pass

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

# v5.397: VS Code-like Notebook cell debugger.  The debugger runs inside the
# same persistent worker/namespace used by normal Notebook execution, so values
# created by earlier cells remain visible.  While Python is paused, this helper
# temporarily consumes debugger command packets directly from stdin; the outer
# worker loop resumes after the debugged cell finishes or is stopped.
def _agentstudio_send_response(payload):
    sys.__stdout__.write(RESPONSE_PREFIX + json.dumps(payload, ensure_ascii=False) + "\n")
    sys.__stdout__.flush()

def _agentstudio_safe_repr(value, limit=700):
    try:
        text = repr(value)
    except BaseException as exc:
        text = f"<repr failed: {type(exc).__name__}: {exc}>"
    text = str(text).replace("\r", "\\r").replace("\n", "\\n")
    if len(text) > limit:
        text = text[: max(0, limit - 1)] + "…"
    return text

def _agentstudio_debug_variables(frame):
    variables = []
    hidden_prefixes = ("_agentstudio_", "__builtins__")
    for name, value in sorted(frame.f_locals.items(), key=lambda item: str(item[0]).casefold()):
        if str(name).startswith(hidden_prefixes):
            continue
        variables.append({
            "name": str(name),
            "type": type(value).__name__,
            "value": _agentstudio_safe_repr(value),
            "scope": "local",
        })
        if len(variables) >= 100:
            break
    return variables

def _agentstudio_debug_stack(frame, target_filename):
    stack = []
    current = frame
    canonical_target = os.path.normcase(os.path.abspath(target_filename))
    while current is not None and len(stack) < 30:
        current_filename = str(current.f_code.co_filename or "")
        canonical_current = os.path.normcase(os.path.abspath(current_filename)) if current_filename else ""
        if canonical_current == canonical_target:
            stack.append({
                "function": str(current.f_code.co_name or "<module>"),
                "file": current_filename,
                "line": int(current.f_lineno or 0),
            })
        current = current.f_back
    return stack

class _AgentStudioCellDebugger(bdb.Bdb):
    def __init__(self, *, filename, cell_index, stdout, stderr):
        super().__init__()
        self.filename = str(filename)
        self.canonical_filename = self.canonic(self.filename)
        self.cell_index = cell_index
        self.stdout = stdout
        self.stderr = stderr
        self.current_frame = None
        self.pause_reason = "step"
        self.exception_info = None

    def _is_target_frame(self, frame):
        return self.canonic(str(frame.f_code.co_filename or "")) == self.canonical_filename

    def _state_payload(self, frame, *, event="paused", reason=None, evaluate_result=None, evaluate_error=None):
        line = max(1, int(frame.f_lineno or 1))
        source_line = linecache.getline(self.filename, line).rstrip("\r\n")
        payload = {
            "ok": True,
            "event": event,
            "debug_active": True,
            "cell_index": self.cell_index,
            "line": line,
            "source_line": source_line,
            "reason": str(reason or self.pause_reason or "step"),
            "variables": _agentstudio_debug_variables(frame),
            "stack": _agentstudio_debug_stack(frame, self.filename),
            "stdout": self.stdout.getvalue(),
            "stderr": self.stderr.getvalue(),
        }
        if self.exception_info:
            exc_type, exc_value, _ = self.exception_info
            payload["exception"] = {
                "type": getattr(exc_type, "__name__", str(exc_type)),
                "message": str(exc_value),
            }
        if evaluate_result is not None:
            payload["evaluate_result"] = evaluate_result
        if evaluate_error is not None:
            payload["evaluate_error"] = evaluate_error
        return payload

    def _interaction(self, frame, *, reason="step", exception_info=None):
        self.current_frame = frame
        self.pause_reason = reason
        self.exception_info = exception_info
        _agentstudio_send_response(self._state_payload(frame, reason=reason))

        while True:
            raw_command = sys.stdin.readline()
            if not raw_command:
                self.set_quit()
                raise bdb.BdbQuit
            try:
                command_request = json.loads(raw_command)
            except BaseException as exc:
                _agentstudio_send_response(self._state_payload(
                    frame,
                    event="evaluate",
                    reason=reason,
                    evaluate_error=f"Debugger command JSON 오류: {exc}",
                ))
                continue

            if str(command_request.get("action") or "") != "debug_command":
                _agentstudio_send_response(self._state_payload(
                    frame,
                    event="evaluate",
                    reason=reason,
                    evaluate_error="디버깅이 일시정지된 동안에는 디버그 명령만 실행할 수 있습니다.",
                ))
                continue

            command = str(command_request.get("command") or "").strip().lower()
            if command == "evaluate":
                expression = str(command_request.get("expression") or "")
                if not expression.strip():
                    _agentstudio_send_response(self._state_payload(
                        frame, event="evaluate", reason=reason, evaluate_error="평가할 표현식을 입력하세요."
                    ))
                    continue
                try:
                    try:
                        value = eval(expression, frame.f_globals, frame.f_locals)
                        result_text = _agentstudio_safe_repr(value, limit=2000)
                    except SyntaxError:
                        exec(expression, frame.f_globals, frame.f_locals)
                        result_text = "<실행 완료>"
                    _agentstudio_send_response(self._state_payload(
                        frame, event="evaluate", reason=reason, evaluate_result=result_text
                    ))
                except BaseException as exc:
                    _agentstudio_send_response(self._state_payload(
                        frame,
                        event="evaluate",
                        reason=reason,
                        evaluate_error=f"{type(exc).__name__}: {exc}",
                    ))
                continue

            if command == "continue":
                self.set_continue()
                return
            if command == "step_over":
                self.set_next(frame)
                return
            if command == "step_into":
                self.set_step()
                return
            if command == "step_out":
                self.set_return(frame)
                return
            if command == "stop":
                self.set_quit()
                raise bdb.BdbQuit

            _agentstudio_send_response(self._state_payload(
                frame,
                event="evaluate",
                reason=reason,
                evaluate_error=f"지원하지 않는 디버그 명령입니다: {command}",
            ))

    def user_line(self, frame):
        if not self._is_target_frame(frame):
            return
        self._interaction(frame, reason="breakpoint" if self.break_here(frame) else "step")

    def user_exception(self, frame, exc_info):
        if not self._is_target_frame(frame):
            return
        self._interaction(frame, reason="exception", exception_info=exc_info)

def _agentstudio_debug_cell(*, code, filename, cell_index, breakpoints, global_namespace, stdout, stderr):
    # Debugging Jupyter shell/cell magics through bdb produces misleading source
    # locations.  Normal execution still supports those magics; the debugger
    # intentionally targets Python code cells only.
    raw_lines = str(code or "").splitlines()
    if any(line.lstrip().startswith(("!", "%")) for line in raw_lines):
        return {
            "ok": False,
            "event": "error",
            "debug_active": False,
            "error_type": "NotebookDebugUnsupportedMagic",
            "error_message": "!command, %magic, %%cell magic이 포함된 셀은 일반 셀 실행을 사용해 주세요.",
            "traceback": "",
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
            "cell_index": cell_index,
        }

    debugger = _AgentStudioCellDebugger(
        filename=filename,
        cell_index=cell_index,
        stdout=stdout,
        stderr=stderr,
    )
    valid_breakpoints = []
    max_line = max(1, len(raw_lines))
    for raw_line in breakpoints or []:
        try:
            line = int(raw_line)
        except (TypeError, ValueError):
            continue
        if 1 <= line <= max_line and line not in valid_breakpoints:
            valid_breakpoints.append(line)
            try:
                debugger.set_break(filename, line)
            except BaseException:
                pass

    try:
        # bdb stops at the first executable line.  Continue/step commands then
        # honor explicit red breakpoints and provide a predictable VS Code-like
        # entry point even when the user has not placed a breakpoint yet.
        compiled = compile(code, filename, "exec")
        debugger.runctx(compiled, global_namespace, global_namespace)
        return {
            "ok": True,
            "event": "finished",
            "debug_active": False,
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
            "traceback": "",
            "error_type": "",
            "error_message": "",
            "cell_index": cell_index,
            "breakpoints": valid_breakpoints,
        }
    except bdb.BdbQuit:
        return {
            "ok": False,
            "cancelled": True,
            "event": "stopped",
            "debug_active": False,
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
            "traceback": "",
            "error_type": "ExecutionCancelled",
            "error_message": "Notebook 셀 디버깅을 종료했습니다.",
            "cell_index": cell_index,
            "breakpoints": valid_breakpoints,
        }
    except BaseException as exc:
        return {
            "ok": False,
            "event": "error",
            "debug_active": False,
            "stdout": stdout.getvalue(),
            "stderr": stderr.getvalue(),
            "traceback": traceback.format_exc(),
            "error_type": type(exc).__name__,
            "error_message": str(exc),
            "cell_index": cell_index,
            "breakpoints": valid_breakpoints,
        }

for raw in sys.stdin:
    try:
        request = json.loads(raw)
        action = str(request.get("action") or "execute").strip().lower()
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
            _agentstudio_install_notebook_display_hooks()
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
            if action == "debug_start":
                # Keep stdout/stderr redirected for the whole debug session.
                # Pause/evaluate protocol messages bypass the redirect through
                # sys.__stdout__ so they remain visible to AgentStudio.
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    response = _agentstudio_debug_cell(
                        code=code,
                        filename=filename,
                        cell_index=request.get("cell_index"),
                        breakpoints=request.get("breakpoints") or [],
                        global_namespace=namespace,
                        stdout=stdout,
                        stderr=stderr,
                    )
                # The debug helper already owns execution and returns the final
                # terminal response.  Skip the normal compile/exec path below.
                ok = bool(response.get("ok"))
                error_type = str(response.get("error_type") or "")
                error_message = str(response.get("error_message") or "")
                trace = str(response.get("traceback") or "")
            else:
                response = None

            if action != "debug_start":
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
                              if notebook_mode:
                                  rich_data, rich_metadata = _agentstudio_notebook_mime_bundle(result)
                                  _agentstudio_emit_notebook_event({
                                      "event": "display_data",
                                      "output": {
                                          "output_type": "execute_result",
                                          "data": rich_data,
                                          "metadata": rich_metadata,
                                      },
                                  })
                              else:
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

        if action != "debug_start" or response is None:
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
