from __future__ import annotations

import asyncio
import json
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


AGENTSTUDIO_CODEX_CLIENT_NAME = "theanova_agentstudio"
AGENTSTUDIO_CODEX_CLIENT_TITLE = "THEANOVA AgentStudio"
AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.435"
CODEX_APPROVAL_POLICY = "untrusted"
CODEX_THREAD_SANDBOX = "workspace-write"


@dataclass
class _PendingRequest:
    event: threading.Event
    result: Any = None
    error: Any = None


class CodexAppServerManager:
    """Small stdio JSON-RPC client for the official `codex app-server`.

    The AgentStudio backend uses a Windows Selector event loop for psycopg, so the
    Codex subprocess and its JSONL pipes are intentionally owned by blocking reader
    threads instead of asyncio subprocess APIs.  The FastAPI layer calls synchronous
    request methods through ``asyncio.to_thread``.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._write_lock = threading.Lock()
        self._process: subprocess.Popen[str] | None = None
        self._stdout_thread: threading.Thread | None = None
        self._stderr_thread: threading.Thread | None = None
        self._request_id = 0
        self._pending: dict[int, _PendingRequest] = {}
        self._subscribers: dict[str, queue.Queue[dict[str, Any]]] = {}
        self._running = False
        self._initialized = False
        self._last_error = ""
        self._stderr_tail: list[str] = []
        self._codex_path = ""
        self._codex_version = ""
        self._account: dict[str, Any] | None = None
        self._requires_openai_auth = True
        self._models: list[dict[str, Any]] = []
        self._current_thread_id = ""
        self._active_turn_id = ""
        self._pending_server_requests: dict[str, dict[str, Any]] = {}
        self._started_cwd = ""
        self._last_event_at = 0.0
        self._rate_limits: dict[str, Any] = {}
        self._rate_limits_error = ""
        self._rate_limits_refreshed_at = 0.0
        self._completion_lock = threading.Lock()
        self._last_runtime_error: dict[str, Any] = {}
        self._runtime_error_history: list[dict[str, Any]] = []
        self._last_command: list[str] = []

    # ------------------------------------------------------------------
    # Discovery / process lifecycle
    # ------------------------------------------------------------------
    def _candidate_paths(self) -> list[str]:
        candidates: list[str] = []
        for name in ("codex", "codex.exe", "codex.cmd"):
            found = shutil.which(name)
            if found:
                candidates.append(found)

        if os.name == "nt":
            home = Path(os.environ.get("USERPROFILE") or Path.home())
            local = Path(os.environ.get("LOCALAPPDATA") or home / "AppData" / "Local")
            roaming = Path(os.environ.get("APPDATA") or home / "AppData" / "Roaming")
            guesses = [
                home / ".local" / "bin" / "codex.exe",
                local / "Programs" / "codex" / "codex.exe",
                local / "OpenAI" / "Codex" / "codex.exe",
                roaming / "npm" / "codex.cmd",
            ]
            candidates.extend(str(path) for path in guesses if path.exists())

            # v5.327: if the user already has the official VS Code Codex extension,
            # reuse its bundled native binary before asking for another install.
            vscode_extensions = home / ".vscode" / "extensions"
            if vscode_extensions.exists():
                bundled = sorted(
                    vscode_extensions.glob(
                        "openai.chatgpt-*-win32-x64/bin/windows-x86_64/codex.exe"
                    ),
                    key=lambda path: path.stat().st_mtime if path.exists() else 0,
                    reverse=True,
                )
                candidates.extend(str(path) for path in bundled)

        seen: set[str] = set()
        answer: list[str] = []
        for value in candidates:
            key = os.path.normcase(os.path.abspath(value))
            if key in seen:
                continue
            seen.add(key)
            answer.append(value)
        return answer

    def _resolve_codex(self) -> str:
        candidates = self._candidate_paths()
        return candidates[0] if candidates else ""

    def _command_for(self, executable: str) -> list[str]:
        suffix = Path(executable).suffix.casefold()
        if os.name == "nt" and suffix in {".cmd", ".bat"}:
            # Windows npm global shims are .cmd files and cannot be passed to
            # CreateProcess directly.  Use cmd.exe only for that wrapper.
            quoted = f'"{executable}" app-server --listen stdio://'
            return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", quoted]
        return [executable, "app-server", "--listen", "stdio://"]

    def _read_version(self, executable: str) -> str:
        try:
            cmd = self._command_for(executable)
            self._last_command = list(cmd)
            # replace app-server arguments with --version
            if os.name == "nt" and Path(executable).suffix.casefold() in {".cmd", ".bat"}:
                cmd = [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/s", "/c", f'"{executable}" --version']
            else:
                cmd = [executable, "--version"]
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=4, check=False)
            return (done.stdout or done.stderr or "").strip().splitlines()[0][:200]
        except Exception:
            return ""

    def install_info(self) -> dict[str, Any]:
        executable = self._codex_path if self._codex_path and Path(self._codex_path).exists() else self._resolve_codex()
        if executable and executable != self._codex_path:
            self._codex_path = executable
            self._codex_version = self._read_version(executable)
        return {
            "installed": bool(executable),
            "path": executable,
            "version": self._codex_version if executable else "",
            "windows_install_command": (
                'powershell -ExecutionPolicy ByPass -c "irm https://chatgpt.com/codex/install.ps1 | iex"'
            ),
            "npm_install_command": "npm install -g @openai/codex",
        }

    def ensure_started(self, cwd: str = "") -> dict[str, Any]:
        from app.core.config import get_settings

        if not get_settings().codex_enabled:
            self._last_error = "Codex 사용 설정이 꺼져 있습니다. 시스템 설정에서 Codex 사용을 먼저 켜세요."
            return self.status()

        with self._lock:
            if self._process is not None and self._process.poll() is None and self._initialized:
                return self.status()

            self._stop_locked()
            executable = self._resolve_codex()
            if not executable:
                self._last_error = "Codex CLI가 설치되어 있지 않거나 PATH에서 찾을 수 없습니다."
                return self.status()

            target_cwd = str(Path(cwd).resolve()) if cwd and Path(cwd).exists() else str(Path.home())
            cmd = self._command_for(executable)
            env = os.environ.copy()
            env.setdefault("RUST_LOG", "warn")
            env.setdefault("LOG_FORMAT", "json")

            creationflags = 0
            if os.name == "nt":
                creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)

            try:
                self._process = subprocess.Popen(
                    cmd,
                    cwd=target_cwd,
                    env=env,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    creationflags=creationflags,
                )
            except Exception as exc:
                self._last_error = f"Codex app-server 시작 실패: {type(exc).__name__}: {exc}"
                self._process = None
                return self.status()

            self._codex_path = executable
            self._codex_version = self._read_version(executable)
            self._started_cwd = target_cwd
            self._running = True
            self._initialized = False
            self._last_error = ""
            self._stderr_tail = []

            self._stdout_thread = threading.Thread(target=self._stdout_reader, name="agentstudio-codex-stdout", daemon=True)
            self._stderr_thread = threading.Thread(target=self._stderr_reader, name="agentstudio-codex-stderr", daemon=True)
            self._stdout_thread.start()
            self._stderr_thread.start()

        # Perform protocol handshake outside the manager lock because responses
        # are delivered by the stdout thread.
        try:
            init = self.request(
                "initialize",
                {
                    "clientInfo": {
                        "name": AGENTSTUDIO_CODEX_CLIENT_NAME,
                        "title": AGENTSTUDIO_CODEX_CLIENT_TITLE,
                        "version": AGENTSTUDIO_CODEX_CLIENT_VERSION,
                    },
                    "capabilities": {"experimentalApi": True},
                },
                timeout=12,
            )
            self.notify("initialized", {})
            self._initialized = True
            self._broadcast({"type": "codex/state", "status": self.status(), "initialize": init})
            self.refresh_account()
            self.refresh_models()
        except Exception as exc:
            self._last_error = f"Codex 초기화 실패: {type(exc).__name__}: {exc}"
            self._broadcast({"type": "codex/error", "message": self._last_error})
            # Do not leave a failed app-server process running in the background.
            # The UI only retries when the user explicitly presses the restart button.
            with self._lock:
                self._stop_locked()
        return self.status()

    def _terminate_process_tree(self, proc: subprocess.Popen[str]) -> None:
        if proc.poll() is not None:
            return
        if os.name == "nt":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    check=False,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                proc.wait(timeout=2)
                return
            except Exception:
                pass
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass

    def _fail_pending_requests(self, message: str) -> None:
        with self._lock:
            pending_rows = list(self._pending.values())
            self._pending.clear()
        for pending in pending_rows:
            pending.error = {"message": message}
            pending.event.set()

    def _stop_locked(self) -> None:
        proc = self._process
        self._process = None
        self._running = False
        self._initialized = False
        self._current_thread_id = ""
        self._active_turn_id = ""
        self._pending_server_requests.clear()
        if proc is not None:
            self._terminate_process_tree(proc)
        for pending in self._pending.values():
            pending.error = {"message": "Codex app-server가 종료되었습니다."}
            pending.event.set()
        self._pending.clear()

    def shutdown_sync(self) -> None:
        with self._lock:
            self._stop_locked()
        self._broadcast({"type": "codex/state", "status": self.status()})

    async def shutdown(self) -> None:
        await asyncio.to_thread(self.shutdown_sync)

    # ------------------------------------------------------------------
    # Wire protocol
    # ------------------------------------------------------------------
    def _write_json(self, payload: dict[str, Any]) -> None:
        with self._write_lock:
            proc = self._process
            if proc is None or proc.poll() is not None or proc.stdin is None:
                raise RuntimeError("Codex app-server가 실행 중이 아닙니다.")
            proc.stdin.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
            proc.stdin.flush()

    def request(self, method: str, params: dict[str, Any] | None = None, timeout: float = 30.0) -> Any:
        with self._lock:
            self._request_id += 1
            request_id = self._request_id
            pending = _PendingRequest(event=threading.Event())
            self._pending[request_id] = pending
        self._write_json({"method": method, "id": request_id, "params": params or {}})
        if not pending.event.wait(timeout):
            with self._lock:
                self._pending.pop(request_id, None)
            raise TimeoutError(f"Codex 요청 시간 초과: {method}")
        if pending.error is not None:
            message = pending.error.get("message") if isinstance(pending.error, dict) else str(pending.error)
            raise RuntimeError(message or f"Codex 요청 실패: {method}")
        return pending.result

    def notify(self, method: str, params: dict[str, Any] | None = None) -> None:
        self._write_json({"method": method, "params": params or {}})

    def _stdout_reader(self) -> None:
        proc = self._process
        if proc is None or proc.stdout is None:
            return
        try:
            for raw in proc.stdout:
                line = raw.strip()
                if not line:
                    continue
                try:
                    message = json.loads(line)
                except Exception:
                    self._broadcast({"type": "codex/protocol-warning", "message": line[:2000]})
                    continue
                self._handle_message(message)
        finally:
            code = proc.poll()
            with self._lock:
                # A deliberately stopped/restarted older process must never clobber
                # the state of a newer app-server instance when its reader exits late.
                if self._process is not proc:
                    return
                self._process = None
                self._running = False
                self._initialized = False
                self._active_turn_id = ""
                self._pending_server_requests.clear()
            message = f"Codex app-server 종료: ExitCode={code}"
            if code not in (None, 0) and not self._last_error:
                self._last_error = message
            self._fail_pending_requests(message)
            self._broadcast({"type": "codex/process-exited", "exit_code": code, "message": message, "status": self.status()})

    def _stderr_reader(self) -> None:
        proc = self._process
        if proc is None or proc.stderr is None:
            return
        for raw in proc.stderr:
            line = raw.rstrip()
            if not line:
                continue
            self._stderr_tail.append(line)
            self._stderr_tail = self._stderr_tail[-80:]
            # stderr contains tracing logs. Keep them available diagnostically but
            # do not flood the visible transcript.

    def _handle_message(self, message: dict[str, Any]) -> None:
        self._last_event_at = time.time()
        if "id" in message and ("result" in message or "error" in message) and "method" not in message:
            try:
                request_id = int(message.get("id"))
            except Exception:
                return
            with self._lock:
                pending = self._pending.pop(request_id, None)
            if pending:
                pending.result = message.get("result")
                pending.error = message.get("error")
                pending.event.set()
            return

        method = str(message.get("method") or "")
        params = message.get("params") or {}

        # Server initiated JSON-RPC requests need a client response. Keep command
        # and file approvals pending for the React panel. Unknown blocking requests
        # are surfaced instead of silently accepting them.
        if "id" in message and method:
            request_key = str(message.get("id"))
            request_payload = {
                "request_id": request_key,
                "method": method,
                "params": params,
            }
            self._pending_server_requests[request_key] = request_payload
            self._broadcast({"type": "codex/server-request", **request_payload})
            return

        if method == "account/updated":
            auth_mode = params.get("authMode")
            plan = params.get("planType")
            existing = dict(self._account or {})
            existing.update({"authMode": auth_mode, "planType": plan})
            self._account = existing
        elif method == "account/rateLimits/updated":
            snapshot = params.get("rateLimits") or {}
            if isinstance(snapshot, dict):
                current = dict(self._rate_limits or {})
                current["rateLimits"] = {**dict(current.get("rateLimits") or {}), **snapshot}
                limit_id = snapshot.get("limitId")
                if limit_id:
                    by_id = dict(current.get("rateLimitsByLimitId") or {})
                    by_id[str(limit_id)] = {**dict(by_id.get(str(limit_id)) or {}), **snapshot}
                    current["rateLimitsByLimitId"] = by_id
                self._rate_limits = current
                self._rate_limits_refreshed_at = time.time()
        elif method == "account/login/completed":
            # account/read gives the canonical account structure; refresh shortly
            # via the event-consuming UI or the explicit status endpoint.
            pass
        elif method == "turn/started":
            turn = params.get("turn") or {}
            self._active_turn_id = str(turn.get("id") or self._active_turn_id)
        elif method == "turn/completed":
            turn = params.get("turn") or {}
            if str(turn.get("id") or "") == self._active_turn_id:
                self._active_turn_id = ""
        elif method == "serverRequest/resolved":
            request_id = str(params.get("requestId") or "")
            if request_id:
                self._pending_server_requests.pop(request_id, None)

        self._broadcast({"type": "codex/event", "method": method, "params": params})

    def _broadcast(self, event: dict[str, Any]) -> None:
        for subscriber in list(self._subscribers.values()):
            try:
                subscriber.put_nowait(event)
            except queue.Full:
                try:
                    subscriber.get_nowait()
                    subscriber.put_nowait(event)
                except Exception:
                    pass

    def subscribe(self) -> tuple[str, queue.Queue[dict[str, Any]]]:
        sid = uuid.uuid4().hex
        q: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1000)
        with self._lock:
            self._subscribers[sid] = q
        return sid, q

    def unsubscribe(self, sid: str) -> None:
        with self._lock:
            self._subscribers.pop(sid, None)


    @staticmethod
    def _looks_like_sandbox_infrastructure_failure(value: str) -> bool:
        text = str(value or "").casefold()
        markers = (
            "codex-windows-sandbox-setup",
            "windows sandbox helper",
            "sandbox helper",
            "sandbox setup",
            "failed to setup sandbox",
            "failed to set up sandbox",
            "sandbox initialization",
        )
        return any(marker in text for marker in markers)

    def _sandbox_helper_details(self, message: str) -> dict[str, Any]:
        raw = "\n".join([str(message or ""), *[str(x) for x in self._stderr_tail[-40:]]])
        paths = re.findall(
            r'(?i)([A-Z]:[\\/][^\r\n"<>|]*?codex-windows-sandbox-setup\.exe)',
            raw,
        )
        helper_path = str(paths[-1]).strip() if paths else ""
        if not helper_path and self._codex_path:
            base = Path(self._codex_path).resolve().parent
            candidates = [
                base / "codex-windows-sandbox-setup.exe",
                base.parent / "codex-windows-sandbox-setup.exe",
                base / "bin" / "windows-x86_64" / "codex-windows-sandbox-setup.exe",
            ]
            found = next((path for path in candidates if path.is_file()), None)
            if found:
                helper_path = str(found)
        winerror_match = re.search(r'(?i)winerror\s*[:=]?\s*(\d+)', raw)
        exit_match = re.search(r'(?i)(?:exit\s*code|exitcode)\s*[:=]?\s*(-?\d+)', raw)
        return {
            "path": helper_path,
            "exists": bool(helper_path and Path(helper_path).is_file()),
            "winerror": int(winerror_match.group(1)) if winerror_match else None,
            "exit_code": int(exit_match.group(1)) if exit_match else None,
            "raw_error": raw[-8000:],
        }

    def _record_runtime_error(self, operation: str, message: str, cwd: str = "", **extra: Any) -> dict[str, Any]:
        sandbox_failure = bool(extra.get("sandbox_infrastructure_failure")) or self._looks_like_sandbox_infrastructure_failure(message)
        row = {
            "timestamp": time.time(),
            "operation": str(operation or "codex"),
            "message": str(message or ""),
            "cwd": str(cwd or self._started_cwd or ""),
            "codex_path": self._codex_path,
            "codex_version": self._codex_version,
            "command": list(self._last_command or []),
            "stderr_tail": list(self._stderr_tail[-40:]),
            "sandbox_infrastructure_failure": sandbox_failure,
            "sandbox_helper": self._sandbox_helper_details(message) if sandbox_failure else {},
            **extra,
        }
        self._last_runtime_error = row
        self._runtime_error_history.append(row)
        self._runtime_error_history = self._runtime_error_history[-20:]
        return row

    # ------------------------------------------------------------------
    # Codex high level operations
    # ------------------------------------------------------------------
    def refresh_account(self) -> dict[str, Any]:
        if not self._initialized:
            return self.status()
        try:
            result = self.request("account/read", {"refreshToken": False}, timeout=12) or {}
            self._account = result.get("account")
            self._requires_openai_auth = bool(result.get("requiresOpenaiAuth", True))
        except Exception as exc:
            self._last_error = f"Codex 계정 상태 확인 실패: {exc}"
        return self.status()

    def refresh_rate_limits(self, force: bool = False) -> dict[str, Any]:
        """Read supported Codex quota/rate-limit information from app-server.

        This uses the public v2 ``account/rateLimits/read`` method. The response
        can contain a backward-compatible bucket plus additional limit-id buckets.
        A short cache avoids hammering the account endpoint from UI polling.
        """
        if not self._initialized or not self._account:
            return self._rate_limits
        if not force and self._rate_limits and time.time() - self._rate_limits_refreshed_at < 30:
            return self._rate_limits
        try:
            result = self.request("account/rateLimits/read", {}, timeout=12) or {}
            self._rate_limits = dict(result) if isinstance(result, dict) else {}
            self._rate_limits_error = ""
            self._rate_limits_refreshed_at = time.time()
        except Exception as exc:
            self._rate_limits_error = f"Codex 사용량 확인 실패: {exc}"
        return self._rate_limits

    def refresh_models(self) -> list[dict[str, Any]]:
        if not self._initialized:
            return []
        try:
            result = self.request("model/list", {"includeHidden": False}, timeout=15) or {}
            data = result.get("data") or result.get("models") or []
            self._models = list(data) if isinstance(data, list) else []
        except Exception as exc:
            self._last_error = f"Codex 모델 목록 확인 실패: {exc}"
        return self._models

    def start_chatgpt_login(self) -> dict[str, Any]:
        if not self._initialized:
            raise RuntimeError("Codex app-server가 준비되지 않았습니다.")
        return self.request("account/login/start", {"type": "chatgpt"}, timeout=15) or {}

    def logout(self) -> dict[str, Any]:
        if not self._initialized:
            return self.status()
        try:
            self.request("account/logout", {}, timeout=10)
        except Exception:
            # Older app-server versions may not expose logout; keep a clear error.
            raise
        self._account = None
        self._rate_limits = {}
        self._rate_limits_error = ""
        self._rate_limits_refreshed_at = 0.0
        return self.status()

    def _start_ephemeral_readonly_thread(self, cwd: str, model: str = "", effort: str = "") -> dict[str, Any]:
        root = str(Path(cwd).resolve()) if cwd and Path(cwd).exists() else str(Path.home())
        self._validate_model_effort(model, effort)
        params: dict[str, Any] = {
            "cwd": root,
            "approvalPolicy": "never",
            "sandbox": "read-only",
            "ephemeral": True,
        }
        if model:
            params["model"] = model
        if effort:
            params["config"] = {"model_reasoning_effort": effort}
        result = self.request("thread/start", params, timeout=25) or {}
        return result.get("thread") or {}

    def run_text_completion(
        self,
        prompt: str,
        cwd: str = "",
        model: str = "",
        effort: str = "",
        timeout: float = 180.0,
    ) -> str:
        """Use Codex as a read-only text provider for AgentStudio fallback routing.

        A private ephemeral thread is used so normal AgentStudio interview/code-edit
        calls do not appear in the user's persistent right-panel conversation list.
        ``approvalPolicy=never`` + ``read-only`` prevents this adapter from changing
        project files. The dedicated Codex panel keeps workspace-write behavior.
        """
        text = str(prompt or "").strip()
        if not text:
            raise ValueError("Codex에 전달할 Prompt가 비어 있습니다.")

        from app.core.config import get_settings
        if not get_settings().codex_enabled:
            raise RuntimeError("Codex 사용 설정이 꺼져 있습니다.")

        with self._completion_lock:
            status = self.ensure_started(cwd)
            if not status.get("initialized"):
                raise RuntimeError(status.get("last_error") or "Codex app-server 초기화 실패")
            self.refresh_account()
            if not self._account:
                raise RuntimeError("Codex ChatGPT 계정이 연결되어 있지 않습니다.")

            subscriber_id, event_queue = self.subscribe()
            try:
                thread = self._start_ephemeral_readonly_thread(cwd, model, effort)
                thread_id = str(thread.get("id") or "")
                if not thread_id:
                    raise RuntimeError("Codex 임시 thread id를 받지 못했습니다.")

                params: dict[str, Any] = {
                    "threadId": thread_id,
                    "input": [{"type": "text", "text": text, "text_elements": []}],
                    "approvalPolicy": "never",
                    "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
                }
                if model:
                    params["model"] = model
                if effort:
                    params["effort"] = effort
                result = self.request("turn/start", params, timeout=20) or {}
                turn = result.get("turn") or {}
                turn_id = str(turn.get("id") or "")
                if not turn_id:
                    raise RuntimeError("Codex 임시 turn id를 받지 못했습니다.")

                chunks: list[str] = []
                final_text = ""
                deadline = time.time() + max(20.0, float(timeout))
                while time.time() < deadline:
                    remaining = max(0.05, min(0.5, deadline - time.time()))
                    try:
                        event = event_queue.get(timeout=remaining)
                    except queue.Empty:
                        continue
                    if event.get("type") == "codex/error":
                        message = str(event.get("message") or "Codex 실행 오류")
                        self._record_runtime_error(
                            "text_completion_event",
                            message,
                            cwd,
                            thread_id=thread_id,
                            turn_id=turn_id,
                            sandbox_infrastructure_failure=self._looks_like_sandbox_infrastructure_failure(message),
                        )
                        raise RuntimeError(message)
                    if event.get("type") != "codex/event":
                        continue
                    method = str(event.get("method") or "")
                    params = event.get("params") or {}
                    event_thread = str(params.get("threadId") or params.get("thread_id") or "")
                    event_turn = str(params.get("turnId") or params.get("turn_id") or params.get("turn", {}).get("id") or "")
                    if event_thread and event_thread != thread_id:
                        continue
                    if event_turn and event_turn != turn_id:
                        continue
                    if method == "item/agentMessage/delta":
                        chunks.append(str(params.get("delta") or ""))
                    elif method == "item/completed":
                        item = params.get("item") or {}
                        if str(item.get("type") or "") == "agentMessage":
                            value = item.get("text") or item.get("content") or ""
                            if isinstance(value, list):
                                value = "".join(str(x.get("text") or x) if isinstance(x, dict) else str(x) for x in value)
                            if str(value).strip():
                                final_text = str(value).strip()
                    elif method == "turn/completed":
                        completed = params.get("turn") or {}
                        if str(completed.get("status") or "").lower() == "failed":
                            err = completed.get("error") or {}
                            message = str(err.get("message") or "Codex turn 실패")
                            self._record_runtime_error(
                                "text_completion_turn",
                                message,
                                cwd,
                                thread_id=thread_id,
                                turn_id=turn_id,
                                sandbox_infrastructure_failure=self._looks_like_sandbox_infrastructure_failure(message),
                            )
                            raise RuntimeError(message)
                        answer = final_text or "".join(chunks).strip()
                        if not answer:
                            message = "Codex가 빈 응답을 반환했습니다."
                            self._record_runtime_error("text_completion_empty", message, cwd, thread_id=thread_id, turn_id=turn_id)
                            raise RuntimeError(message)
                        # Some Codex Windows sandbox failures are returned as an assistant
                        # message instead of a protocol error. Treat those as provider
                        # infrastructure failures so model_router can transparently fall
                        # through to OpenAI/Ollama instead of accepting an empty Patch plan.
                        if self._looks_like_sandbox_infrastructure_failure(answer):
                            self._record_runtime_error(
                                "text_completion_answer",
                                answer[:4000],
                                cwd,
                                thread_id=thread_id,
                                turn_id=turn_id,
                                sandbox_infrastructure_failure=True,
                            )
                            raise RuntimeError(
                                "Codex Windows sandbox helper를 사용할 수 없어 Codex 결과를 채택하지 않았습니다. "
                                + answer[:1200]
                            )
                        return answer
                message = "Codex 텍스트 응답 대기 시간이 초과되었습니다."
                self._record_runtime_error("text_completion_timeout", message, cwd, thread_id=thread_id, turn_id=turn_id)
                raise TimeoutError(message)
            finally:
                self.unsubscribe(subscriber_id)

    def list_threads(self, cwd: str = "", limit: int = 20) -> list[dict[str, Any]]:
        if not self._initialized:
            return []
        params: dict[str, Any] = {"limit": max(1, min(int(limit), 50)), "archived": False}
        if cwd:
            params["cwd"] = str(Path(cwd).resolve())
        result = self.request("thread/list", params, timeout=15) or {}
        data = result.get("data") or result.get("threads") or []
        return list(data) if isinstance(data, list) else []

    @staticmethod
    def _reasoning_effort_value(value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            return str(
                value.get("reasoningEffort")
                or value.get("effort")
                or value.get("value")
                or value.get("label")
                or ""
            )
        return ""

    def _validate_model_effort(self, model: str, effort: str) -> None:
        if not model or not effort:
            return
        selected = next(
            (
                row for row in self._models
                if str(row.get("model") or row.get("id") or "") == model
            ),
            None,
        )
        if not selected:
            return
        supported = [
            self._reasoning_effort_value(value)
            for value in (selected.get("supportedReasoningEfforts") or [])
        ]
        supported = [value for value in supported if value]
        if supported and effort not in supported:
            raise ValueError(
                f'모델 "{model}"은 reasoning effort "{effort}"를 지원하지 않습니다. '
                f'지원 값: {", ".join(supported)}'
            )

    def start_thread(self, cwd: str, model: str = "", effort: str = "") -> dict[str, Any]:
        root = str(Path(cwd).resolve())
        self._validate_model_effort(model, effort)
        params: dict[str, Any] = {
            "cwd": root,
            "approvalPolicy": CODEX_APPROVAL_POLICY,
            "sandbox": CODEX_THREAD_SANDBOX,
        }
        if model:
            params["model"] = model
        if effort:
            # Current app-server thread/start carries reasoning effort through
            # the normal config layer; turn/start then uses the typed `effort` field.
            params["config"] = {"model_reasoning_effort": effort}
        result = self.request("thread/start", params, timeout=25) or {}
        thread = result.get("thread") or {}
        self._current_thread_id = str(thread.get("id") or "")
        return thread

    def resume_thread(self, thread_id: str, cwd: str = "") -> dict[str, Any]:
        params: dict[str, Any] = {
            "threadId": thread_id,
            "approvalPolicy": CODEX_APPROVAL_POLICY,
            "sandbox": CODEX_THREAD_SANDBOX,
        }
        if cwd:
            params["cwd"] = str(Path(cwd).resolve())
        result = self.request("thread/resume", params, timeout=25) or {}
        thread = result.get("thread") or {}
        self._current_thread_id = str(thread.get("id") or thread_id)
        return thread

    def start_turn(
        self,
        thread_id: str,
        text: str,
        cwd: str = "",
        model: str = "",
        effort: str = "",
        attachment_context: str = "",
    ) -> dict[str, Any]:
        self._validate_model_effort(model, effort)
        user_text = str(text or "").strip()
        attachment_text = str(attachment_context or "").strip()
        if attachment_text:
            user_text += (
                "\n\n" + attachment_text
                + "\n\n위 첨부 파일은 사용자가 이번 작업의 참고자료로 직접 등록했습니다. "
                  "내용을 분석하여 요청에 반영하되, 참고 파일 자체를 수정 대상으로 간주하지 마세요."
            )
        params: dict[str, Any] = {
            "threadId": thread_id,
            "input": [{"type": "text", "text": user_text, "text_elements": []}],
            "approvalPolicy": CODEX_APPROVAL_POLICY,
        }
        if cwd:
            root = str(Path(cwd).resolve())
            params["cwd"] = root
            params["sandboxPolicy"] = {
                "type": "workspaceWrite",
                "writableRoots": [root],
                "networkAccess": True,
                "excludeTmpdirEnvVar": False,
                "excludeSlashTmp": False,
            }
        if model:
            params["model"] = model
        if effort:
            params["effort"] = effort
        result = self.request("turn/start", params, timeout=20) or {}
        turn = result.get("turn") or {}
        self._active_turn_id = str(turn.get("id") or "")
        self._current_thread_id = thread_id
        return turn

    def interrupt_turn(self, thread_id: str, turn_id: str) -> None:
        if not thread_id or not turn_id:
            return
        self.request("turn/interrupt", {"threadId": thread_id, "turnId": turn_id}, timeout=10)

    def resolve_server_request(self, request_id: str, decision: str, payload: dict[str, Any] | None = None) -> None:
        pending = self._pending_server_requests.get(str(request_id))
        if not pending:
            raise RuntimeError("이미 처리되었거나 존재하지 않는 Codex 승인 요청입니다.")
        method = str(pending.get("method") or "")
        response: dict[str, Any]
        if method in {
            "item/commandExecution/requestApproval",
            "item/fileChange/requestApproval",
        }:
            response = {"decision": decision}
        elif method == "item/tool/requestUserInput":
            response = payload or {"answers": {}}
        else:
            response = payload or {"decision": decision}
        self._write_json({"id": self._coerce_request_id(request_id), "result": response})
        self._pending_server_requests.pop(str(request_id), None)

    @staticmethod
    def _coerce_request_id(value: str) -> int | str:
        try:
            return int(value)
        except Exception:
            return value

    def status(self) -> dict[str, Any]:
        install = self.install_info()
        proc = self._process
        running = bool(proc is not None and proc.poll() is None and self._running)
        from app.core.config import get_settings
        return {
            **install,
            "enabled": bool(get_settings().codex_enabled),
            "running": running,
            "initialized": bool(running and self._initialized),
            "pid": proc.pid if running and proc else None,
            "started_cwd": self._started_cwd,
            "account": self._account,
            "requires_openai_auth": self._requires_openai_auth,
            "models": self._models,
            "current_thread_id": self._current_thread_id,
            "active_turn_id": self._active_turn_id,
            "pending_requests": list(self._pending_server_requests.values()),
            "rate_limits": self._rate_limits,
            "rate_limits_error": self._rate_limits_error,
            "rate_limits_refreshed_at": self._rate_limits_refreshed_at,
            "last_error": self._last_error,
            "stderr_tail": self._stderr_tail[-20:],
            "last_command": list(self._last_command or []),
            "last_runtime_error": dict(self._last_runtime_error or {}),
            "runtime_error_history": list(self._runtime_error_history[-10:]),
            "last_event_at": self._last_event_at,
        }


codex_app_server_manager = CodexAppServerManager()
