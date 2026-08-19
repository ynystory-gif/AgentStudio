from __future__ import annotations

import asyncio
import base64
import os
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TerminalSession:
    id: str
    root: str
    project_name: str
    process: subprocess.Popen
    queue: asyncio.Queue[str]
    loop: asyncio.AbstractEventLoop
    has_venv: bool = False
    elevated: bool = False
    writer_lock: threading.Lock = field(default_factory=threading.Lock)
    reader_thread: threading.Thread | None = None
    closed: bool = False
    history: list[str] = field(default_factory=list)
    history_chars: int = 0


TERMINAL_HISTORY_MAX_CHARS = 600_000


def _is_windows_administrator() -> bool:
    if sys.platform != "win32":
        return True
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


class TerminalManager:
    """
    Windows SelectorEventLoop-safe persistent terminal manager.

    Important:
    - FastAPI stays on SelectorEventLoop for Psycopg async compatibility.
    - PowerShell is NOT started by asyncio subprocess API.
    - subprocess.Popen runs independently of asyncio.
    - stdout is read by a normal Python thread.
    - reader thread forwards output into asyncio.Queue via
      loop.call_soon_threadsafe().
    """

    def __init__(self) -> None:
        self.sessions: dict[str, TerminalSession] = {}

    def _build_env(self, root: str) -> dict[str, str]:
        env = os.environ.copy()
        project_root = Path(root)
        venv_dir = project_root / ".venv"
        scripts_dir = venv_dir / "Scripts"

        if scripts_dir.exists():
            env["VIRTUAL_ENV"] = str(venv_dir)
            env["PATH"] = str(scripts_dir) + os.pathsep + env.get("PATH", "")
            env.pop("PYTHONHOME", None)

        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        return env

    def _powershell_command(self) -> list[str]:
        return [
            "powershell.exe",
            "-NoLogo",
            "-NoExit",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            "-",
        ]

    async def create(
        self,
        root: str,
        project_name: str = "",
        session_id: str | None = None,
    ) -> TerminalSession:
        project_root = Path(root).expanduser().resolve()

        if not project_root.exists() or not project_root.is_dir():
            raise FileNotFoundError(str(project_root))

        if sys.platform == "win32" and not _is_windows_administrator():
            raise PermissionError(
                "AgentStudio 터미널은 관리자 권한으로만 실행됩니다. "
                "현재 Backend가 관리자 권한이 아닙니다. SYSTEM_ADMIN.cmd로 AgentStudio를 다시 실행하세요."
            )

        sid = session_id or f"terminal-{uuid.uuid4().hex[:12]}"

        existing = self.sessions.get(sid)
        if (
            existing
            and existing.process.poll() is None
            and not existing.closed
        ):
            return existing

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[str] = asyncio.Queue()

        # NOTE:
        # Do not use asyncio subprocess API on Windows here.
        # AgentStudio FastAPI uses SelectorEventLoop for Psycopg,
        # and Windows SelectorEventLoop doesn't support asyncio subprocesses.
        process = subprocess.Popen(
            self._powershell_command(),
            cwd=str(project_root),
            env=self._build_env(str(project_root)),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=False,
            bufsize=0,
            creationflags=(
                subprocess.CREATE_NEW_PROCESS_GROUP
                if sys.platform == "win32"
                else 0
            ),
        )

        has_venv = (project_root / ".venv" / "Scripts").exists()

        session = TerminalSession(
            id=sid,
            root=str(project_root),
            project_name=project_name or project_root.name,
            process=process,
            has_venv=has_venv,
            elevated=_is_windows_administrator(),
            queue=queue,
            loop=loop,
        )

        reader = threading.Thread(
            target=self._reader_thread,
            args=(session,),
            name=f"AgentStudioTerminal-{sid}",
            daemon=True,
        )
        session.reader_thread = reader

        self.sessions[sid] = session
        reader.start()

        await self._bootstrap(session)
        return session

    def _queue_text(self, session: TerminalSession, text: str) -> None:
        if session.closed:
            return

        # Internal process-exit marker is control metadata, not terminal history.
        if text and not text.startswith("__THEANOVA_PROCESS_EXIT__="):
            session.history.append(text)
            session.history_chars += len(text)

            while (
                session.history
                and session.history_chars > TERMINAL_HISTORY_MAX_CHARS
            ):
                removed = session.history.pop(0)
                session.history_chars -= len(removed)

        try:
            session.loop.call_soon_threadsafe(
                session.queue.put_nowait,
                text,
            )
        except RuntimeError:
            # Event loop already closed.
            pass

    def get_history(self, session_id: str) -> str:
        session = self.sessions.get(session_id)
        if not session:
            return ""
        return "".join(session.history)

    def clear_history(self, session_id: str) -> bool:
        """Clear only the retained terminal output for reconnect/history replay.

        The PowerShell process and its working directory/environment stay alive.
        This is intentionally different from restart/close.
        """
        session = self.sessions.get(session_id)
        if not session:
            return False
        session.history.clear()
        session.history_chars = 0
        return True

    def _reader_thread(self, session: TerminalSession) -> None:
        stream = session.process.stdout

        if stream is None:
            self._queue_text(
                session,
                "\n[ERROR] PowerShell stdout을 사용할 수 없습니다.\n",
            )
            return

        try:
            while not session.closed:
                chunk = stream.read(4096)

                if not chunk:
                    break

                text = chunk.decode(
                    "utf-8",
                    errors="replace",
                )
                self._queue_text(session, text)

        except Exception as e:
            self._queue_text(
                session,
                f"\n[ERROR] 터미널 출력 읽기 실패: {e}\n",
            )

        finally:
            exit_code = session.process.poll()
            self._queue_text(
                session,
                f"__THEANOVA_PROCESS_EXIT__={exit_code}\n",
            )

    async def _bootstrap(self, session: TerminalSession) -> None:
        project_root = Path(session.root)
        activate = (
            project_root
            / ".venv"
            / "Scripts"
            / "Activate.ps1"
        )

        safe_root = str(project_root).replace("'", "''")

        commands = [
            "[Console]::InputEncoding=[System.Text.Encoding]::UTF8",
            "[Console]::OutputEncoding=[System.Text.Encoding]::UTF8",
            "$OutputEncoding=[System.Text.Encoding]::UTF8",
            "$env:PYTHONUTF8='1'",
            "$env:PYTHONIOENCODING='utf-8'",
            "$env:PYTHONUNBUFFERED='1'",
            f"Set-Location -LiteralPath '{safe_root}'",
        ]

        if activate.exists():
            safe_activate = str(activate).replace("'", "''")
            commands.extend([
                (
                    "Set-ExecutionPolicy "
                    "-Scope Process "
                    "-ExecutionPolicy RemoteSigned"
                ),
                f"& '{safe_activate}'",
            ])

        # Force a visible prompt-like line after bootstrap.
        commands.extend([
            "$__theanova_prefix = if ($env:VIRTUAL_ENV) { '(.venv) ' } else { '' }",
            "Write-Output ('__THEANOVA_PROMPT__=' + $__theanova_prefix + 'PS ' + (Get-Location).Path + '> ')",
        ])

        await self.send_raw(
            session.id,
            "\r\n".join(commands) + "\r\n",
        )

    async def send_raw(
        self,
        session_id: str,
        text: str,
    ) -> None:
        session = self.sessions.get(session_id)

        if not session:
            raise KeyError(
                f"터미널 세션을 찾을 수 없습니다: {session_id}"
            )

        if session.closed:
            raise RuntimeError(
                "터미널 세션이 이미 닫혔습니다."
            )

        if session.process.poll() is not None:
            raise RuntimeError(
                "PowerShell 프로세스가 이미 종료되었습니다."
            )

        if session.process.stdin is None:
            raise RuntimeError(
                "PowerShell stdin을 사용할 수 없습니다."
            )

        def _write() -> None:
            with session.writer_lock:
                session.process.stdin.write(
                    text.encode("utf-8")
                )
                session.process.stdin.flush()

        await asyncio.to_thread(_write)

    def _wrap_multiline_command(self, command: str) -> str:
        """
        Execute a multi-line PowerShell block as one logical command.

        Feeding a pasted block line-by-line into an interactive
        ``powershell.exe -Command -`` process is fragile when the block
        contains backtick continuations, hashtables, blank lines or Korean
        text.  Encode the complete UTF-8 script and reconstruct it inside the
        *same* PowerShell process, then dot-source the ScriptBlock so current
        session state (variables / Set-Location) is preserved.
        """
        encoded = base64.b64encode(command.encode("utf-8")).decode("ascii")
        return (
            "$__theanova_command_text = "
            "[System.Text.Encoding]::UTF8.GetString("
            "[System.Convert]::FromBase64String('"
            + encoded
            + "'))"
            + "\r\n"
            + ". ([ScriptBlock]::Create($__theanova_command_text))"
            + "\r\n"
            + "Remove-Variable __theanova_command_text "
              "-ErrorAction SilentlyContinue"
        )

    async def send_command(
        self,
        session_id: str,
        command: str,
    ) -> None:
        # Keep internal line endings deterministic.  The frontend stores
        # pasted PowerShell blocks as LF; normalize any other source here.
        command = command.replace("\r\n", "\n").replace("\r", "\n")
        command = command.rstrip("\n")

        # Single-line commands can stay direct for an interactive-shell feel.
        # Multi-line blocks are transferred as a single encoded ScriptBlock
        # so PowerShell continuation syntax cannot merge with AgentStudio's
        # internal CWD/prompt marker commands.
        executable = (
            self._wrap_multiline_command(command)
            if "\n" in command
            else command
        )

        payload = (
            executable
            + "\r\n"
            + "Write-Output ('__THEANOVA_CWD__=' + (Get-Location).Path)"
            + "\r\n"
            + "$__theanova_prefix = if ($env:VIRTUAL_ENV) { '(.venv) ' } else { '' }"
            + "\r\n"
            + "Write-Output ('__THEANOVA_PROMPT__=' + $__theanova_prefix + 'PS ' + (Get-Location).Path + '> ')"
            + "\r\n"
        )

        await self.send_raw(
            session_id,
            payload,
        )

    async def send(
        self,
        session_id: str,
        text: str,
    ) -> None:
        # 하위 호환용. 기존 input 메시지는 완성 명령으로 간주합니다.
        await self.send_command(
            session_id,
            text,
        )

    def _windows_direct_child_pids(self, parent_pid: int) -> list[int]:
        """Return direct child process IDs for a Windows process.

        We intentionally query child processes instead of sending CTRL_BREAK
        to the persistent PowerShell host. CTRL_BREAK can place PowerShell
        into debugger mode ("Entering debug mode") rather than behaving
        like the interactive Ctrl+C users expect.
        """
        if sys.platform != "win32":
            return []

        ps = (
            "Get-CimInstance Win32_Process -Filter \"ParentProcessId = "
            + str(int(parent_pid))
            + "\" | Select-Object -ExpandProperty ProcessId"
        )
        try:
            result = subprocess.run(
                [
                    "powershell.exe",
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    ps,
                ],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception:
            return []

        pids: list[int] = []
        for line in (result.stdout or "").splitlines():
            value = line.strip()
            if value.isdigit():
                pid = int(value)
                if pid > 0 and pid != int(parent_pid):
                    pids.append(pid)
        return pids

    def _terminate_windows_child_trees(self, parent_pid: int) -> int:
        """Terminate foreground child process trees, preserving PowerShell."""
        child_pids = self._windows_direct_child_pids(parent_pid)
        killed = 0
        for pid in child_pids:
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    text=True,
                    timeout=8,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                killed += 1
            except Exception:
                continue
        return killed

    async def interrupt(
        self,
        session_id: str,
    ) -> None:
        session = self.sessions.get(session_id)

        if not session:
            raise KeyError(
                f"터미널 세션을 찾을 수 없습니다: {session_id}"
            )

        if session.process.poll() is not None:
            return

        if sys.platform == "win32":
            # Do NOT use CTRL_BREAK_EVENT here. In a persistent PowerShell
            # host it can enter the PowerShell debugger instead of stopping
            # the foreground npm/node/python command. Prefer terminating only
            # direct child process trees so the shell/session survives.
            killed = await asyncio.to_thread(
                self._terminate_windows_child_trees,
                session.process.pid,
            )
            if killed:
                return

            # Built-in PowerShell commands (for example Start-Sleep) may have
            # no child process. Fall back to CTRL_C_EVENT for the process group,
            # which is the closest Windows equivalent to interactive Ctrl+C.
            try:
                session.process.send_signal(
                    signal.CTRL_C_EVENT  # type: ignore[name-defined]
                )
                return
            except Exception:
                # Preserve the persistent shell even if Ctrl+C delivery is not
                # available; never taskkill the root PowerShell process here.
                return
        else:
            session.process.send_signal(signal.SIGINT)

    async def close(
        self,
        session_id: str,
    ) -> None:
        session = self.sessions.pop(
            session_id,
            None,
        )

        if not session:
            return

        if session.process.poll() is None:
            try:
                await self.send_raw(
                    session_id,
                    "exit\r\n",
                )
            except Exception:
                try:
                    session.process.terminate()
                except Exception:
                    pass

        session.closed = True

    def get(
        self,
        session_id: str,
    ) -> TerminalSession | None:
        return self.sessions.get(session_id)


# signal import kept at end for Windows-specific use
import signal

terminal_manager = TerminalManager()
