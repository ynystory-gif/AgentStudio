from __future__ import annotations

import asyncio
import base64
import ipaddress
import json
import queue
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import traceback
import uuid
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse
from urllib.request import ProxyHandler, build_opener

try:
    from playwright.sync_api import Browser, BrowserContext, CDPSession, Page, Playwright, Route, sync_playwright
except Exception:  # pragma: no cover
    Browser = BrowserContext = CDPSession = Page = Playwright = Route = Any  # type: ignore[misc,assignment]
    sync_playwright = None  # type: ignore[assignment]

BROWSER_IDLE_SECONDS = 60 * 60
BROWSER_STARTUP_RETRY_LOCK_SECONDS = 5 * 60
BROWSER_HANDOFF_GRACE_SECONDS = 3.0
MAX_REMOTE_PAGES = 24
DEFAULT_VIEWPORT_WIDTH = 1280
DEFAULT_VIEWPORT_HEIGHT = 720
MIN_VIEWPORT_WIDTH = 320
MIN_VIEWPORT_HEIGHT = 220
MAX_VIEWPORT_WIDTH = 3840
MAX_VIEWPORT_HEIGHT = 2160


class ChromiumBrowserError(RuntimeError):
    def __init__(self, message: str, status_code: int = 400, diagnostics: dict[str, Any] | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.diagnostics = diagnostics or {}


@dataclass
class ChromiumPopup:
    session_id: str
    url: str
    title: str


@dataclass
class ChromiumPageSession:
    session_id: str
    page: Page
    cdp: CDPSession | None = None
    last_used: float = field(default_factory=time.time)
    loading: bool = False
    popups: list[ChromiumPopup] = field(default_factory=list)
    popup_parent_id: str = ""
    frame_data: str = ""
    frame_revision: int = 0
    viewport_width: int = DEFAULT_VIEWPORT_WIDTH
    viewport_height: int = DEFAULT_VIEWPORT_HEIGHT
    screencast_active: bool = False


class ChromiumBrowserManager:
    """System Chrome + CDP browser used only for public Internet sites.

    Chrome itself is launched directly, so AgentStudio does not depend on a
    Playwright-downloaded browser binary. Playwright is used only as a CDP
    client. Page.startScreencast frames are streamed to React over AgentStudio's
    own WebSocket endpoint.
    """

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="agentstudio-cdp")
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._chrome_process: subprocess.Popen[Any] | None = None
        self._profile_dir: Path | None = None
        self._runtime_profile_dir: Path | None = None
        self._cdp_http_url = ""
        self._cdp_ws_url = ""
        self._startup_log_path: Path | None = None
        self._sessions: dict[str, ChromiumPageSession] = {}
        self._allowed_host_cache: dict[str, tuple[float, bool]] = {}
        self._shutdown_requested = False
        self._startup_failed_latched = False
        self._startup_failure_at = 0.0
        self._startup_failure_message = ""
        self._startup_diagnostics: dict[str, Any] = self._new_startup_diagnostics()
        # v5.326: Playwright runs in a dedicated helper process on Windows so
        # FastAPI/psycopg can keep WindowsSelectorEventLoopPolicy while the
        # Playwright Node driver uses the normal Proactor subprocess support.
        self._worker_process: subprocess.Popen[Any] | None = None
        self._worker_responses: queue.Queue[dict[str, Any]] = queue.Queue()
        self._worker_reader_thread: threading.Thread | None = None
        self._worker_request_id = 0
        self._worker_ready = False
        self._worker_log_path: Path | None = None
        self._worker_log_file: Any | None = None
        self._diagnostic_log_write_error = ""


    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    @staticmethod
    def _diagnostic_log_path() -> Path:
        root = os.getenv("LOCALAPPDATA") or str(Path.home() / ".theanova")
        return Path(root) / "THEANOVA" / "AgentStudio" / "logs" / "browser_cdp_diagnostics.log"

    def _new_startup_diagnostics(self) -> dict[str, Any]:
        return {
            "status": "idle",
            "stage": "idle",
            "message": "외부 브라우저를 아직 시작하지 않았습니다.",
            "hint": "",
            "started_at": "",
            "updated_at": self._utc_now_iso(),
            "proxy": {
                "http_proxy_set": bool(os.getenv("HTTP_PROXY") or os.getenv("http_proxy")),
                "https_proxy_set": bool(os.getenv("HTTPS_PROXY") or os.getenv("https_proxy")),
                "no_proxy": str(os.getenv("NO_PROXY") or os.getenv("no_proxy") or ""),
            },
            "candidates": [],
            "attempts": [],
            "cdp_http_url": "",
            "cdp_ws_url": "",
            "guard": {
                "failure_latched": bool(getattr(self, "_startup_failed_latched", False)),
                "failure_at": float(getattr(self, "_startup_failure_at", 0.0) or 0.0),
                "failure_message": str(getattr(self, "_startup_failure_message", "") or ""),
            },
            "log_path": str(self._diagnostic_log_path()),
            "log_exists": self._diagnostic_log_path().is_file(),
            "log_write_error": str(getattr(self, "_diagnostic_log_write_error", "") or ""),
            "worker": {
                "mode": "dedicated-playwright-helper",
                "pid": None,
                "python": sys.executable,
                "log_path": "",
                "log_exists": False,
                "exception_type": "",
                "exception_repr": "",
                "traceback": "",
            },
        }

    def _diagnostic_snapshot_sync(self) -> dict[str, Any]:
        # JSON round-trip returns a detached payload safe for FastAPI/other threads.
        snapshot = json.loads(json.dumps(self._startup_diagnostics, ensure_ascii=False, default=str))
        log_path = Path(str(snapshot.get("log_path") or self._diagnostic_log_path()))
        snapshot["log_exists"] = log_path.is_file()
        try:
            snapshot["log_size_bytes"] = int(log_path.stat().st_size) if log_path.is_file() else 0
        except Exception:
            snapshot["log_size_bytes"] = 0
        snapshot["log_write_error"] = str(self._diagnostic_log_write_error or snapshot.get("log_write_error") or "")
        worker = snapshot.setdefault("worker", {})
        worker_log = Path(str(worker.get("log_path") or self._worker_log_path or "")) if (worker.get("log_path") or self._worker_log_path) else None
        worker["log_exists"] = bool(worker_log and worker_log.is_file())
        if worker_log and worker_log.is_file():
            try:
                text = worker_log.read_text(encoding="utf-8", errors="replace")
                worker["log_tail"] = text[-8000:]
            except Exception as exc:
                worker["log_tail"] = f"worker log read failed: {type(exc).__name__}: {exc!r}"
        else:
            worker.setdefault("log_tail", "")
        return snapshot

    def _write_diagnostic_log_sync(self) -> None:
        primary = self._diagnostic_log_path()
        fallback = Path(__file__).resolve().parents[3] / "logs" / "browser_cdp_diagnostics.log"
        errors: list[str] = []
        for path in (primary, fallback):
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                snapshot = self._diagnostic_snapshot_sync()
                with path.open("a", encoding="utf-8") as fp:
                    fp.write("\n" + "=" * 92 + "\n")
                    fp.write(f"[{self._utc_now_iso()}] Chrome CDP diagnostics\n")
                    fp.write(json.dumps(snapshot, ensure_ascii=False, indent=2))
                    fp.write("\n")
                    fp.flush()
                self._diagnostic_log_write_error = ""
                self._startup_diagnostics["log_path"] = str(path)
                self._startup_diagnostics["log_exists"] = path.is_file()
                self._startup_diagnostics["log_write_error"] = ""
                return
            except Exception as exc:
                errors.append(f"{path}: {type(exc).__name__}: {exc!r}")
        self._diagnostic_log_write_error = " | ".join(errors)
        self._startup_diagnostics["log_exists"] = False
        self._startup_diagnostics["log_write_error"] = self._diagnostic_log_write_error

    def _diag_update(self, stage: str, message: str, *, status: str | None = None, hint: str | None = None, **extra: Any) -> None:
        self._startup_diagnostics["stage"] = stage
        self._startup_diagnostics["message"] = message
        self._startup_diagnostics["updated_at"] = self._utc_now_iso()
        if status is not None:
            self._startup_diagnostics["status"] = status
        if hint is not None:
            self._startup_diagnostics["hint"] = hint
        for key, value in extra.items():
            self._startup_diagnostics[key] = value

    def _diag_attempt(self, executable: str, runtime: Path, log_path: Path, args: list[str]) -> dict[str, Any]:
        item = {
            "browser": Path(executable).name,
            "executable": str(executable),
            "runtime_profile_dir": str(runtime),
            "startup_log_path": str(log_path),
            "command": [str(part) for part in args],
            "pid": None,
            "exit_code": None,
            "devtools_active_port_exists": False,
            "devtools_active_port": "",
            "cdp_http_url": "",
            "cdp_ws_url": "",
            "last_error": "",
            "startup_log_tail": "",
            "handoff_detected": False,
            "handoff_pids": [],
            "cleanup_killed": 0,
            "cleanup_remaining": 0,
        }
        self._startup_diagnostics.setdefault("attempts", []).append(item)
        self._startup_diagnostics["updated_at"] = self._utc_now_iso()
        return item

    async def _run(self, fn: Callable[..., Any], *args: Any) -> Any:
        if self._shutdown_requested:
            raise ChromiumBrowserError("외부 Chrome 브라우저가 종료되었습니다.", 503)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, fn, *args)

    @staticmethod
    def _safe_session_id(value: str) -> str:
        cleaned = "".join(ch if ch.isalnum() or ch in "-_." else "-" for ch in str(value or ""))[:160]
        return cleaned or f"browser-{uuid.uuid4().hex[:12]}"

    @staticmethod
    def _viewport(width: int | None, height: int | None) -> dict[str, int]:
        try: w = int(width or DEFAULT_VIEWPORT_WIDTH)
        except Exception: w = DEFAULT_VIEWPORT_WIDTH
        try: h = int(height or DEFAULT_VIEWPORT_HEIGHT)
        except Exception: h = DEFAULT_VIEWPORT_HEIGHT
        return {
            "width": max(MIN_VIEWPORT_WIDTH, min(MAX_VIEWPORT_WIDTH, w)),
            "height": max(MIN_VIEWPORT_HEIGHT, min(MAX_VIEWPORT_HEIGHT, h)),
        }

    @staticmethod
    def _candidate_executables() -> list[str]:
        candidates: list[str] = []
        explicit = str(os.getenv("AGENTSTUDIO_BROWSER_EXECUTABLE", "") or "").strip()
        if explicit: candidates.append(explicit)
        for name in ("chrome", "google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "msedge"):
            found = shutil.which(name)
            if found: candidates.append(found)
        local = os.getenv("LOCALAPPDATA", "")
        pf = os.getenv("PROGRAMFILES", "")
        pfx86 = os.getenv("PROGRAMFILES(X86)", "")
        for root, tail in (
            (pf, r"Google\Chrome\Application\chrome.exe"),
            (pfx86, r"Google\Chrome\Application\chrome.exe"),
            (local, r"Google\Chrome\Application\chrome.exe"),
            (pf, r"Microsoft\Edge\Application\msedge.exe"),
            (pfx86, r"Microsoft\Edge\Application\msedge.exe"),
        ):
            if root: candidates.append(str(Path(root) / tail))
        result: list[str] = []
        seen: set[str] = set()
        for item in candidates:
            path = str(item or "").strip()
            key = path.lower()
            if path and key not in seen and Path(path).is_file():
                seen.add(key); result.append(path)
        return result

    @staticmethod
    def _literal_is_private(hostname: str) -> bool:
        host = str(hostname or "").strip().lower().strip("[]")
        if host in {"localhost", "localhost.localdomain"}: return True
        try: return not ipaddress.ip_address(host).is_global
        except ValueError: return False

    def _validate_public_target_sync(self, value: str) -> str:
        raw = str(value or "").strip()
        try: parsed = urlparse(raw)
        except Exception as exc: raise ChromiumBrowserError(f"올바른 URL이 아닙니다: {exc}") from exc
        if parsed.scheme not in {"http", "https"}: raise ChromiumBrowserError("외부 Chrome은 http/https URL만 허용합니다.")
        if not parsed.hostname: raise ChromiumBrowserError("URL에 host가 없습니다.")
        if parsed.username or parsed.password: raise ChromiumBrowserError("사용자명/비밀번호가 URL에 포함된 주소는 열 수 없습니다.")
        hostname = str(parsed.hostname).strip().lower().strip("[]")
        if self._literal_is_private(hostname):
            raise ChromiumBrowserError("localhost/내부 IP는 기존 직접 표시 방식을 사용하세요.", 403)
        try: port = parsed.port or (443 if parsed.scheme == "https" else 80)
        except ValueError as exc: raise ChromiumBrowserError("잘못된 포트입니다.") from exc
        try: literal = ipaddress.ip_address(hostname)
        except ValueError: literal = None
        if literal is not None:
            if not literal.is_global: raise ChromiumBrowserError("공인 IP가 아닌 주소는 차단됩니다.", 403)
            return raw
        cache_key = f"{parsed.scheme}://{hostname}:{port}"
        now = time.time(); cached = self._allowed_host_cache.get(cache_key)
        if cached and now - cached[0] < 300:
            if not cached[1]: raise ChromiumBrowserError("공인 인터넷 주소가 아닌 대상은 차단됩니다.", 403)
            return raw
        try: infos = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        except socket.gaierror as exc:
            self._allowed_host_cache[cache_key] = (now, False)
            raise ChromiumBrowserError(f"도메인 주소를 확인할 수 없습니다: {hostname}", 502) from exc
        addresses = {str(info[4][0]) for info in infos if info[4]}
        allowed = bool(addresses) and all(ipaddress.ip_address(addr).is_global for addr in addresses)
        self._allowed_host_cache[cache_key] = (now, allowed)
        if not allowed: raise ChromiumBrowserError(f"공인 인터넷 주소가 아닌 IP로 해석되는 도메인은 차단됩니다: {hostname}", 403)
        return raw

    def _route_guard_sync(self, route: Route) -> None:
        url = str(route.request.url or "")
        parsed = urlparse(url)
        if parsed.scheme in {"data", "blob", "about"}:
            route.continue_(); return
        if parsed.scheme not in {"http", "https"}:
            route.abort("blockedbyclient"); return
        try:
            self._validate_public_target_sync(url)
            route.continue_()
        except ChromiumBrowserError:
            route.abort("blockedbyclient")

    def _websocket_guard_sync(self, ws_route: Any) -> None:
        try:
            raw = str(ws_route.url or "")
            parsed = urlparse(raw)
            if parsed.scheme not in {"ws", "wss"}:
                ws_route.close(code=1008, reason="Blocked by AgentStudio"); return
            equivalent = ("https" if parsed.scheme == "wss" else "http") + "://" + str(parsed.netloc) + (parsed.path or "/")
            if parsed.query: equivalent += "?" + parsed.query
            self._validate_public_target_sync(equivalent)
            ws_route.connect_to_server()
        except Exception:
            try: ws_route.close(code=1008, reason="Private/non-public WebSocket blocked")
            except Exception: pass

    @staticmethod
    def _find_free_port() -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    @staticmethod
    def _default_profile_dir() -> Path:
        from app.services.runtime_path_policy import resolve_cache_root
        return resolve_cache_root() / "browser" / "profile"

    @staticmethod
    def _runtime_profile_root() -> Path:
        from app.services.runtime_path_policy import resolve_temp_root
        return resolve_temp_root() / "browser" / "runtime"

    @staticmethod
    def _ensure_localhost_no_proxy() -> None:
        # urllib and the Playwright driver inherit the user's proxy variables.
        # Corporate Windows environments frequently proxy even loopback when
        # NO_PROXY is absent, which makes /json/version hang until timeout.
        required = ["127.0.0.1", "localhost"]
        for key in ("NO_PROXY", "no_proxy"):
            values = [item.strip() for item in str(os.environ.get(key, "") or "").split(",") if item.strip()]
            lowered = {item.lower() for item in values}
            for item in required:
                if item.lower() not in lowered:
                    values.append(item)
            os.environ[key] = ",".join(values)

    @staticmethod
    def _read_startup_log(log_path: Path | None, limit: int = 1800) -> str:
        if not log_path or not log_path.is_file():
            return ""
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace").strip()
        except Exception:
            return ""
        if len(text) > limit:
            text = text[-limit:]
        return text

    @staticmethod
    def _powershell_processes_for_runtime(runtime: Path | None = None) -> list[dict[str, Any]]:
        """Return AgentStudio Chrome/Edge processes whose command line owns BrowserRuntime.

        Windows Chrome may hand off from the initial Popen PID to another browser PID and
        exit with code 0.  The Runtime user-data-dir is therefore the authoritative owner
        key, not the original PID.
        """
        if os.name != "nt":
            return []
        needle = str(runtime or ChromiumBrowserManager._runtime_profile_root())
        escaped = needle.replace("'", "''")
        script = (
            "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);"
            f"$needle='{escaped}';"
            "$items=Get-CimInstance Win32_Process | Where-Object {"
            "($_.Name -eq 'chrome.exe' -or $_.Name -eq 'msedge.exe') -and "
            "$_.CommandLine -and $_.CommandLine.Contains($needle)" 
            "} | Select-Object ProcessId,ParentProcessId,Name,CommandLine;"
            "if($items){$items | ConvertTo-Json -Compress}else{'[]'}"
        )
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            completed = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=12,
                creationflags=flags,
                check=False,
            )
            raw = (completed.stdout or "").strip()
            if not raw:
                return []
            value = json.loads(raw)
            if isinstance(value, dict):
                value = [value]
            if not isinstance(value, list):
                return []
            result: list[dict[str, Any]] = []
            for item in value:
                if not isinstance(item, dict):
                    continue
                try:
                    pid = int(item.get("ProcessId") or 0)
                    ppid = int(item.get("ParentProcessId") or 0)
                except Exception:
                    continue
                if pid > 0:
                    result.append({
                        "pid": pid,
                        "ppid": ppid,
                        "name": str(item.get("Name") or ""),
                        "command_line": str(item.get("CommandLine") or ""),
                    })
            return result
        except Exception:
            return []

    @staticmethod
    def _kill_pid_tree_sync(pid: int) -> None:
        if pid <= 0:
            return
        if os.name == "nt":
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            try:
                subprocess.run(
                    ["taskkill.exe", "/PID", str(pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=8,
                    creationflags=flags,
                    check=False,
                )
            except Exception:
                pass
            return
        try:
            os.killpg(pid, 15)
        except Exception:
            try:
                os.kill(pid, 15)
            except Exception:
                pass

    def _runtime_processes_sync(self, runtime: Path | None = None) -> list[dict[str, Any]]:
        if os.name == "nt":
            return self._powershell_processes_for_runtime(runtime)
        # On Unix the launched browser is placed in its own process group.  We do not
        # need a process-table scan for normal cleanup; the tracked group is sufficient.
        proc = self._chrome_process
        if proc and proc.poll() is None:
            return [{"pid": int(proc.pid), "ppid": 0, "name": "chromium", "command_line": str(runtime or "")}]
        return []

    def _kill_runtime_processes_sync(self, runtime: Path | None = None) -> dict[str, int]:
        """Kill every browser process that references one AgentStudio Runtime profile."""
        runtime_path = runtime or self._runtime_profile_dir
        killed = 0
        if os.name != "nt":
            proc = self._chrome_process
            if proc and proc.poll() is None:
                self._kill_pid_tree_sync(int(proc.pid))
                killed += 1
            return {"killed": killed, "remaining": 0}
        for _ in range(5):
            items = self._runtime_processes_sync(runtime_path)
            if not items:
                return {"killed": killed, "remaining": 0}
            ids = {int(item["pid"]) for item in items}
            roots = [item for item in items if int(item.get("ppid") or 0) not in ids]
            if not roots:
                roots = items
            for item in roots:
                self._kill_pid_tree_sync(int(item["pid"]))
                killed += 1
            time.sleep(0.18)
        remaining = len(self._runtime_processes_sync(runtime_path))
        return {"killed": killed, "remaining": remaining}

    def _cleanup_all_stale_runtime_sync(self) -> dict[str, int]:
        """Remove BrowserRuntime leaks without serial taskkill storms.

        v5.325 could spend a long time issuing taskkill once per leaked browser root.
        v5.326 kills only processes whose command line contains AgentStudio BrowserRuntime,
        but does it in one bounded PowerShell pass so FastAPI startup is not held hostage.
        """
        if os.name != "nt":
            return {"killed": 0, "remaining": 0}
        current_runtime_token = f"runtime-{os.getpid()}-".lower()
        before = [
            item for item in self._powershell_processes_for_runtime(self._runtime_profile_root())
            if current_runtime_token not in str(item.get("command_line") or "").lower()
        ]
        if not before:
            return {"killed": 0, "remaining": 0}
        needle = str(self._runtime_profile_root()).replace("'", "''")
        current_token = current_runtime_token.replace("'", "''")
        script = (
            "$ErrorActionPreference='SilentlyContinue';"
            f"$needle='{needle}';"
            f"$current='{current_token}';"
            "$items=@(Get-CimInstance Win32_Process | Where-Object {"
            "($_.Name -eq 'chrome.exe' -or $_.Name -eq 'msedge.exe') -and "
            "$_.CommandLine -and $_.CommandLine.Contains($needle) -and "
            "-not $_.CommandLine.ToLower().Contains($current)});"
            "$ids=@($items | ForEach-Object {[int]$_.ProcessId});"
            "if($ids.Count -gt 0){Stop-Process -Id $ids -Force -ErrorAction SilentlyContinue};"
            "Start-Sleep -Milliseconds 350;"
            "$left=@(Get-CimInstance Win32_Process | Where-Object {"
            "($_.Name -eq 'chrome.exe' -or $_.Name -eq 'msedge.exe') -and "
            "$_.CommandLine -and $_.CommandLine.Contains($needle) -and "
            "-not $_.CommandLine.ToLower().Contains($current)});"
            "if($left.Count -gt 0){$leftIds=@($left | ForEach-Object {[int]$_.ProcessId});"
            "Stop-Process -Id $leftIds -Force -ErrorAction SilentlyContinue;Start-Sleep -Milliseconds 250};"
        )
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=8,
                creationflags=flags,
                check=False,
            )
        except Exception:
            pass
        remaining = len([
            item for item in self._powershell_processes_for_runtime(self._runtime_profile_root())
            if current_runtime_token not in str(item.get("command_line") or "").lower()
        ])
        runtime_root = self._runtime_profile_root()
        try:
            if remaining == 0 and runtime_root.is_dir():
                for child in runtime_root.glob("runtime-*"):
                    if child.name.lower().startswith(current_runtime_token):
                        continue
                    shutil.rmtree(child, ignore_errors=True)
        except Exception:
            pass
        return {"killed": max(0, len(before) - remaining), "remaining": remaining}

    def _wait_devtools(
        self,
        profile_dir: Path,
        process: subprocess.Popen[Any],
        log_path: Path | None,
        attempt: dict[str, Any] | None = None,
        timeout_seconds: float = 30.0,
    ) -> tuple[str, str]:
        active = profile_dir / "DevToolsActivePort"
        started = time.time()
        deadline = started + max(5.0, timeout_seconds)
        last_error = "DevToolsActivePort 대기 중"
        port = 0
        opener = build_opener(ProxyHandler({}))
        while time.time() < deadline:
            exit_code = process.poll()
            if exit_code is not None:
                live_runtime = self._runtime_processes_sync(profile_dir)
                # On Windows Chrome/Edge can intentionally hand off the browser to a
                # different PID and let the Popen PID exit with code 0.  Treat that as
                # a valid startup transition instead of launching another browser.
                if exit_code == 0 and live_runtime:
                    if attempt is not None:
                        attempt["exit_code"] = exit_code
                        attempt["handoff_detected"] = True
                        attempt["handoff_pids"] = [int(item["pid"]) for item in live_runtime]
                    self._diag_update(
                        "process_handoff",
                        f"{Path(str(attempt.get('executable') if attempt else 'Chrome')).name} PID handoff 감지 · 실제 Runtime 프로세스 {len(live_runtime)}개",
                        status="starting",
                    )
                elif exit_code == 0 and (time.time() - started) < BROWSER_HANDOFF_GRACE_SECONDS:
                    # Give the child browser a short window to become visible in the
                    # process table/DevToolsActivePort file.
                    time.sleep(0.08)
                    continue
                else:
                    log_tail = self._read_startup_log(log_path)
                    if attempt is not None:
                        attempt["exit_code"] = exit_code
                        attempt["devtools_active_port_exists"] = active.is_file()
                        attempt["startup_log_tail"] = log_tail
                        attempt["last_error"] = "Chrome 프로세스가 DevTools 포트를 열기 전에 종료됨"
                    detail = f"Chrome 프로세스가 조기 종료되었습니다. ExitCode={exit_code}."
                    if exit_code == 0:
                        detail += " Runtime handoff 프로세스도 확인되지 않았습니다."
                    if log_tail:
                        detail += f" 시작 로그: {log_tail}"
                    self._diag_update(
                        "wait_devtools",
                        detail,
                        status="failed",
                        hint="Chrome/Edge 정책, 보안 프로그램, 실행 옵션 제한 또는 Runtime handoff를 확인하세요.",
                    )
                    self._write_diagnostic_log_sync()
                    raise ChromiumBrowserError(detail, 503, self._diagnostic_snapshot_sync())
            try:
                if active.is_file():
                    lines = active.read_text(encoding="utf-8", errors="ignore").splitlines()
                    if attempt is not None:
                        attempt["devtools_active_port_exists"] = True
                        attempt["devtools_active_port"] = "\n".join(lines[:3])
                    if lines and lines[0].strip().isdigit():
                        port = int(lines[0].strip())
                if port > 0:
                    with opener.open(f"http://127.0.0.1:{port}/json/version", timeout=0.8) as response:
                        data = json.loads(response.read().decode("utf-8"))
                    ws_url = str(data.get("webSocketDebuggerUrl") or "").strip()
                    if ws_url:
                        parsed = urlparse(ws_url)
                        ws_port = parsed.port or port
                        path = parsed.path or "/"
                        if parsed.query:
                            path += "?" + parsed.query
                        normalized_ws = f"ws://127.0.0.1:{ws_port}{path}"
                        cdp_http = f"http://127.0.0.1:{port}"
                        if attempt is not None:
                            attempt["cdp_http_url"] = cdp_http
                            attempt["cdp_ws_url"] = normalized_ws
                            attempt["last_error"] = ""
                        self._diag_update(
                            "devtools_ready",
                            "Chrome DevTools endpoint 확인 완료",
                            cdp_http_url=cdp_http,
                            cdp_ws_url=normalized_ws,
                        )
                        return cdp_http, normalized_ws
            except Exception as exc:
                last_error = str(exc)
                if attempt is not None:
                    attempt["last_error"] = last_error
                    attempt["devtools_active_port_exists"] = active.is_file()
            time.sleep(0.12)
        log_tail = self._read_startup_log(log_path)
        if attempt is not None:
            attempt["exit_code"] = process.poll()
            attempt["devtools_active_port_exists"] = active.is_file()
            attempt["startup_log_tail"] = log_tail
            attempt["last_error"] = last_error
        detail = f"Chrome DevTools 포트 연결에 실패했습니다. {last_error}"
        if log_tail:
            detail += f" 시작 로그: {log_tail}"
        self._diag_update(
            "wait_devtools",
            detail,
            status="failed",
            hint="DevToolsActivePort, localhost proxy, Chrome 정책 및 보안 프로그램을 확인하세요.",
        )
        self._write_diagnostic_log_sync()
        raise ChromiumBrowserError(detail, 503, self._diagnostic_snapshot_sync())

    def _cleanup_runtime_profile_sync(self) -> None:
        runtime = self._runtime_profile_dir
        self._runtime_profile_dir = None
        if not runtime or not runtime.exists():
            return
        try:
            shutil.rmtree(runtime, ignore_errors=True)
        except Exception:
            pass

    def _launch_one_browser_sync(self, executable: str) -> tuple[str, str]:
        persistent = self._default_profile_dir()
        persistent.mkdir(parents=True, exist_ok=True)
        self._profile_dir = persistent
        runtime_root = self._runtime_profile_root()
        runtime_root.mkdir(parents=True, exist_ok=True)
        runtime = runtime_root / f"runtime-{os.getpid()}-{uuid.uuid4().hex[:10]}"
        runtime.mkdir(parents=True, exist_ok=True)
        self._runtime_profile_dir = runtime
        try:
            from app.services.runtime_path_policy import resolve_output_root
            download_dir = resolve_output_root() / "browser-downloads"
            download_dir.mkdir(parents=True, exist_ok=True)
            default_dir = runtime / "Default"
            default_dir.mkdir(parents=True, exist_ok=True)
            (default_dir / "Preferences").write_text(json.dumps({"download": {"default_directory": str(download_dir), "prompt_for_download": False, "directory_upgrade": True}, "safebrowsing": {"enabled": True}}, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
        log_path = runtime / "chrome_startup.log"
        self._startup_log_path = log_path
        args = [
            executable,
            "--remote-debugging-port=0",
            "--remote-debugging-address=127.0.0.1",
            "--remote-allow-origins=*",
            f"--user-data-dir={runtime}",
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-component-update",
            "--disable-dev-shm-usage",
            "--window-size=1280,720",
            "about:blank",
        ]
        if os.name != "nt" and hasattr(os, "geteuid") and os.geteuid() == 0:
            args.insert(1, "--no-sandbox")
        attempt = self._diag_attempt(executable, runtime, log_path, args)
        self._diag_update("launch", f"{Path(executable).name} 실행 시도", status="starting")
        creationflags = 0
        popen_kwargs: dict[str, Any] = {}
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            popen_kwargs["start_new_session"] = True
        try:
            with log_path.open("wb") as log_file:
                process = subprocess.Popen(
                    args,
                    stdout=log_file,
                    stderr=subprocess.STDOUT,
                    creationflags=creationflags,
                    **popen_kwargs,
                )
            self._chrome_process = process
            attempt["pid"] = process.pid
            self._diag_update("process_started", f"브라우저 프로세스 시작 PID={process.pid}")
        except Exception as exc:
            attempt["last_error"] = str(exc)
            self._diag_update("launch", f"시스템 Chrome 실행 실패: {exc}", status="failed", hint="브라우저 실행 권한과 보안 프로그램 차단 여부를 확인하세요.")
            self._write_diagnostic_log_sync()
            self._cleanup_runtime_profile_sync()
            raise ChromiumBrowserError(f"시스템 Chrome 실행 실패: {exc}", 503, self._diagnostic_snapshot_sync()) from exc
        try:
            return self._wait_devtools(runtime, process, log_path, attempt)
        except Exception:
            cleanup = self._kill_runtime_processes_sync(runtime)
            if attempt is not None:
                attempt["cleanup_killed"] = int(cleanup.get("killed") or 0)
                attempt["cleanup_remaining"] = int(cleanup.get("remaining") or 0)
            try:
                if process.poll() is None:
                    process.terminate(); process.wait(timeout=1)
            except Exception:
                try: process.kill()
                except Exception: pass
            self._chrome_process = None
            raise

    def _launch_system_chrome_sync(self) -> tuple[str, str]:
        self._startup_diagnostics = self._new_startup_diagnostics()
        self._diag_update("discover", "Chrome/Edge 실행 파일 탐색 중", status="starting")
        self._startup_diagnostics["started_at"] = self._utc_now_iso()
        executables = self._candidate_executables()
        self._startup_diagnostics["candidates"] = list(executables)
        if not executables:
            self._diag_update("discover", "Google Chrome 또는 Microsoft Edge 실행 파일을 찾지 못했습니다.", status="failed", hint="Chrome 또는 Edge 설치 경로를 확인하거나 AGENTSTUDIO_BROWSER_EXECUTABLE을 지정하세요.")
            self._write_diagnostic_log_sync()
            raise ChromiumBrowserError("Google Chrome 또는 Microsoft Edge 실행 파일을 찾지 못했습니다.", 503, self._diagnostic_snapshot_sync())
        self._ensure_localhost_no_proxy()
        self._startup_diagnostics["proxy"]["no_proxy"] = str(os.getenv("NO_PROXY") or os.getenv("no_proxy") or "")
        failures: list[str] = []
        # Try at most one Chrome-family executable and one Edge executable.  Duplicate
        # install paths must never create an unbounded candidate loop.
        selected: list[str] = []
        seen_family: set[str] = set()
        for executable in executables:
            name = Path(executable).name.lower()
            family = "edge" if "edge" in name else "chrome"
            if family in seen_family:
                continue
            seen_family.add(family)
            selected.append(executable)
            if len(selected) >= 2:
                break
        for executable in selected:
            runtime_before = self._runtime_profile_dir
            try:
                return self._launch_one_browser_sync(executable)
            except ChromiumBrowserError as exc:
                failures.append(f"{Path(executable).name}: {exc}")
                runtime = self._runtime_profile_dir or runtime_before
                cleanup = self._kill_runtime_processes_sync(runtime)
                attempts = self._startup_diagnostics.get("attempts") or []
                if attempts:
                    attempts[-1]["cleanup_killed"] = int(cleanup.get("killed") or 0)
                    attempts[-1]["cleanup_remaining"] = int(cleanup.get("remaining") or 0)
                self._cleanup_runtime_profile_sync()
        summary = " | ".join(failures[-3:])
        message = f"설치된 Chrome/Edge에서 CDP를 시작하지 못했습니다. {summary}"
        self._diag_update("all_candidates_failed", message, status="failed", hint=self._startup_diagnostics.get("hint") or "진단 로그의 각 브라우저 시도 결과를 확인하세요.")
        self._write_diagnostic_log_sync()
        raise ChromiumBrowserError(message, 503, self._diagnostic_snapshot_sync())


    def _storage_state_path(self) -> Path:
        profile = self._default_profile_dir()
        profile.mkdir(parents=True, exist_ok=True)
        return profile / "storage_state.json"

    def _restore_storage_state_sync(self) -> None:
        if not self._context:
            return
        state_path = self._storage_state_path()
        if not state_path.is_file():
            return
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            return
        cookies = state.get("cookies") if isinstance(state, dict) else None
        if isinstance(cookies, list) and cookies:
            try:
                self._context.add_cookies(cookies)
            except Exception:
                pass
        origins = state.get("origins") if isinstance(state, dict) else None
        if isinstance(origins, list) and origins:
            origin_map: dict[str, list[dict[str, str]]] = {}
            for entry in origins:
                if not isinstance(entry, dict):
                    continue
                origin = str(entry.get("origin") or "").strip()
                values = entry.get("localStorage")
                if origin and isinstance(values, list):
                    cleaned = []
                    for item in values:
                        if isinstance(item, dict) and "name" in item and "value" in item:
                            cleaned.append({"name": str(item["name"]), "value": str(item["value"])})
                    if cleaned:
                        origin_map[origin] = cleaned
            if origin_map:
                payload = json.dumps(origin_map, ensure_ascii=False)
                script = """(() => {
                    const states = __STATE__;
                    const items = states[location.origin];
                    if (!items) return;
                    for (const item of items) {
                        try { localStorage.setItem(item.name, item.value); } catch (_) {}
                    }
                })()""".replace("__STATE__", payload)
                try:
                    self._context.add_init_script(script)
                except Exception:
                    pass

    def _save_storage_state_sync(self) -> None:
        if not self._context:
            return
        state_path = self._storage_state_path()
        try:
            state_path.parent.mkdir(parents=True, exist_ok=True)
            self._context.storage_state(path=str(state_path))
        except Exception:
            pass

    def _worker_reader_loop(self, process: subprocess.Popen[Any]) -> None:
        stream = process.stdout
        if stream is None:
            return
        try:
            for raw in stream:
                raw = str(raw or "").strip()
                if not raw:
                    continue
                try:
                    payload = json.loads(raw)
                except Exception:
                    payload = {"id": -1, "ok": False, "error": "Invalid worker JSON", "raw": raw[-4000:]}
                self._worker_responses.put(payload)
        except Exception as exc:
            self._worker_responses.put({"id": -1, "ok": False, "error": f"worker stdout reader failed: {exc!r}"})

    def _worker_diag_sync(self, **values: Any) -> None:
        worker = self._startup_diagnostics.setdefault("worker", {})
        worker.update(values)
        log_path = self._worker_log_path
        worker["log_path"] = str(log_path or worker.get("log_path") or "")
        worker["log_exists"] = bool(log_path and log_path.is_file())

    def _start_playwright_worker_sync(self) -> None:
        if self._worker_process and self._worker_process.poll() is None and self._worker_ready:
            return
        self._stop_playwright_worker_sync(graceful=False)
        while True:
            try:
                self._worker_responses.get_nowait()
            except queue.Empty:
                break
        if not self._cdp_ws_url:
            raise ChromiumBrowserError("Chrome CDP WebSocket endpoint가 준비되지 않았습니다.", 503, self._diagnostic_snapshot_sync())

        logs_dir = self._diagnostic_log_path().parent
        try:
            logs_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            logs_dir = Path(__file__).resolve().parents[3] / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
        self._worker_log_path = logs_dir / f"browser_cdp_worker_{os.getpid()}_{int(time.time())}.log"
        worker_script = Path(__file__).with_name("chromium_playwright_worker.py")
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        for key in ("NO_PROXY", "no_proxy"):
            current = str(env.get(key, "") or "")
            parts = [item.strip() for item in current.split(",") if item.strip()]
            lowered = {item.lower() for item in parts}
            for item in ("127.0.0.1", "localhost"):
                if item.lower() not in lowered:
                    parts.append(item)
            env[key] = ",".join(parts)

        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        try:
            self._worker_log_file = self._worker_log_path.open("a", encoding="utf-8")
            self._worker_log_file.write(
                f"[{self._utc_now_iso()}] dedicated Playwright worker start\n"
                f"python={sys.executable}\nendpoint={self._cdp_ws_url}\n"
                f"backend_event_loop_policy={type(asyncio.get_event_loop_policy()).__name__}\n"
            )
            self._worker_log_file.flush()
            process = subprocess.Popen(
                [sys.executable, str(worker_script), self._cdp_ws_url, str(self._storage_state_path())],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=self._worker_log_file,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creationflags,
                env=env,
            )
            self._worker_process = process
            self._worker_ready = False
            self._worker_reader_thread = threading.Thread(
                target=self._worker_reader_loop,
                args=(process,),
                name="agentstudio-cdp-worker-reader",
                daemon=True,
            )
            self._worker_reader_thread.start()
            self._worker_diag_sync(pid=process.pid, python=sys.executable, exception_type="", exception_repr="", traceback="")
            self._diag_update("playwright_worker_start", f"전용 Playwright Helper 시작 PID={process.pid}", status="starting")
        except Exception as exc:
            self._worker_diag_sync(exception_type=type(exc).__name__, exception_repr=repr(exc), traceback=traceback.format_exc()[-12000:])
            self._write_diagnostic_log_sync()
            raise ChromiumBrowserError(f"Playwright Helper 프로세스 시작 실패: {type(exc).__name__}: {exc!r}", 503, self._diagnostic_snapshot_sync()) from exc

        deadline = time.time() + 20.0
        ready: dict[str, Any] | None = None
        while time.time() < deadline:
            if process.poll() is not None and self._worker_responses.empty():
                break
            try:
                payload = self._worker_responses.get(timeout=0.25)
            except queue.Empty:
                continue
            if int(payload.get("id", -1)) == 0:
                ready = payload
                break
        if not ready or not ready.get("ok"):
            if ready:
                self._worker_diag_sync(
                    exception_type=str(ready.get("exception_type") or ""),
                    exception_repr=str(ready.get("exception_repr") or ready.get("error") or ""),
                    traceback=str(ready.get("traceback") or "")[-12000:],
                )
            else:
                self._worker_diag_sync(
                    exception_type="WorkerStartupTimeout" if process.poll() is None else "WorkerExited",
                    exception_repr=f"exit_code={process.poll()}",
                )
            self._diag_update(
                "connect_over_cdp",
                "전용 Playwright Helper에서 Chrome CDP 연결에 실패했습니다.",
                status="failed",
                hint="진단 로그의 Helper 예외 타입/repr/traceback과 browser_cdp_worker 로그를 확인하세요.",
            )
            self._write_diagnostic_log_sync()
            diagnostics = self._diagnostic_snapshot_sync()
            self._stop_playwright_worker_sync(graceful=False)
            detail = (ready or {}).get("error") or (ready or {}).get("exception_repr") or f"worker exit={process.poll()}"
            raise ChromiumBrowserError(
                f"Playwright Helper CDP 연결 실패: {(ready or {}).get('exception_type') or 'Unknown'}: {detail}",
                503,
                diagnostics,
            )
        self._worker_ready = True
        self._worker_diag_sync(
            pid=process.pid,
            event_loop_policy=str(ready.get("event_loop_policy") or ""),
            platform=str(ready.get("platform") or ""),
            endpoint=str(ready.get("endpoint") or self._cdp_ws_url),
        )
        self._diag_update("ready", "시스템 Chrome CDP + 전용 Playwright Helper 연결 완료", status="ready", hint="")
        self._write_diagnostic_log_sync()

    def _worker_rpc_sync(self, op: str, timeout: float = 35.0, **payload: Any) -> Any:
        process = self._worker_process
        if not process or process.poll() is not None or not self._worker_ready or process.stdin is None:
            raise ChromiumBrowserError("Playwright Helper가 실행 중이 아닙니다. 다시 연결하세요.", 409, self._diagnostic_snapshot_sync())
        self._worker_request_id += 1
        request_id = self._worker_request_id
        request = {"id": request_id, "op": op, **payload}
        try:
            process.stdin.write(json.dumps(request, ensure_ascii=False, separators=(",", ":")) + "\n")
            process.stdin.flush()
        except Exception as exc:
            self._worker_ready = False
            raise ChromiumBrowserError(f"Playwright Helper 요청 전송 실패: {type(exc).__name__}: {exc!r}", 503, self._diagnostic_snapshot_sync()) from exc
        deadline = time.time() + max(1.0, timeout)
        deferred: list[dict[str, Any]] = []
        try:
            while time.time() < deadline:
                if process.poll() is not None and self._worker_responses.empty():
                    break
                try:
                    response = self._worker_responses.get(timeout=min(0.25, max(0.01, deadline-time.time())))
                except queue.Empty:
                    continue
                if int(response.get("id", -999)) != request_id:
                    deferred.append(response)
                    continue
                if not response.get("ok"):
                    self._worker_diag_sync(
                        exception_type=str(response.get("exception_type") or ""),
                        exception_repr=str(response.get("exception_repr") or response.get("error") or ""),
                        traceback=str(response.get("traceback") or "")[-12000:],
                    )
                    self._write_diagnostic_log_sync()
                    message = str(response.get("error") or response.get("exception_repr") or "Helper operation failed")
                    raise ChromiumBrowserError(
                        f"웹브라우저 Helper 동작 실패({op}) · {response.get('exception_type') or 'Error'}: {message}",
                        500,
                        self._diagnostic_snapshot_sync(),
                    )
                return response.get("result")
        finally:
            for item in deferred:
                self._worker_responses.put(item)
        self._worker_ready = False
        raise ChromiumBrowserError(
            f"Playwright Helper 응답 timeout({op}, {timeout:.0f}s). exit={process.poll()}",
            504,
            self._diagnostic_snapshot_sync(),
        )

    def _stop_playwright_worker_sync(self, graceful: bool = True) -> None:
        process = self._worker_process
        self._worker_ready = False
        if process and process.poll() is None and graceful:
            try:
                self._worker_request_id += 1
                rid = self._worker_request_id
                if process.stdin:
                    process.stdin.write(json.dumps({"id": rid, "op": "shutdown"}) + "\n")
                    process.stdin.flush()
                process.wait(timeout=2.5)
            except Exception:
                pass
        if process and process.poll() is None:
            try:
                self._kill_pid_tree_sync(int(process.pid))
            except Exception:
                try:
                    process.kill()
                except Exception:
                    pass
        self._worker_process = None
        try:
            if self._worker_log_file:
                self._worker_log_file.flush()
                self._worker_log_file.close()
        except Exception:
            pass
        self._worker_log_file = None
        self._worker_reader_thread = None
        self._worker_diag_sync(pid=None)

    def _ensure_started_sync(self, force_restart: bool = False) -> None:
        if self._worker_process and self._worker_process.poll() is None and self._worker_ready:
            return
        if self._startup_failed_latched and not force_restart:
            elapsed = max(0.0, time.time() - self._startup_failure_at)
            remaining = max(0, int(BROWSER_STARTUP_RETRY_LOCK_SECONDS - elapsed))
            message = self._startup_failure_message or "외부 Chrome CDP 시작이 이전 시도에서 실패했습니다."
            raise ChromiumBrowserError(
                f"{message} 자동 재시도는 차단되었습니다. '다시 연결' 버튼으로만 재시도하세요. (보호 잠금 {remaining}초)",
                503,
                self._diagnostic_snapshot_sync(),
            )
        if force_restart:
            self._stop_browser_runtime_sync(clear_failure=True)
        try:
            self._cdp_http_url, self._cdp_ws_url = self._launch_system_chrome_sync()
            self._diag_update("playwright_worker", "Backend와 분리된 Playwright Helper 연결 준비 중", status="starting")
            self._start_playwright_worker_sync()
            self._startup_failed_latched = False
            self._startup_failure_at = 0.0
            self._startup_failure_message = ""
            self._diag_update(
                "ready",
                "시스템 Chrome CDP 연결 완료",
                status="ready",
                hint="",
                cdp_http_url=self._cdp_http_url,
                cdp_ws_url=self._cdp_ws_url,
            )
            self._write_diagnostic_log_sync()
        except ChromiumBrowserError as exc:
            self._startup_failed_latched = True
            self._startup_failure_at = time.time()
            self._startup_failure_message = str(exc)
            self._stop_browser_runtime_sync(clear_failure=False)
            diagnostics = self._diagnostic_snapshot_sync()
            raise ChromiumBrowserError(str(exc), exc.status_code, diagnostics) from exc
        except Exception as exc:
            self._worker_diag_sync(
                exception_type=type(exc).__name__,
                exception_repr=repr(exc),
                traceback=traceback.format_exc()[-12000:],
            )
            self._diag_update(
                "connect_over_cdp",
                f"시스템 Chrome CDP 연결 실패 · {type(exc).__name__}: {exc!r}",
                status="failed",
                hint="전용 Playwright Helper 로그와 예외 type/repr/traceback을 확인하세요.",
            )
            self._write_diagnostic_log_sync()
            self._startup_failed_latched = True
            self._startup_failure_at = time.time()
            self._startup_failure_message = f"시스템 Chrome CDP 연결 실패 · {type(exc).__name__}: {exc!r}"
            self._stop_browser_runtime_sync(clear_failure=False)
            diagnostics = self._diagnostic_snapshot_sync()
            raise ChromiumBrowserError(self._startup_failure_message, 503, diagnostics) from exc

    def _start_screencast_sync(self, item: ChromiumPageSession) -> None:
        if not self._context: return
        try:
            if item.cdp is not None:
                try: item.cdp.send("Page.stopScreencast")
                except Exception: pass
                try: item.cdp.detach()
                except Exception: pass
            cdp = self._context.new_cdp_session(item.page)
            item.cdp = cdp
            def on_frame(event: dict[str, Any]) -> None:
                data = str(event.get("data") or "")
                if data:
                    item.frame_data = data
                    item.frame_revision += 1
                    item.last_used = time.time()
                sid = event.get("sessionId")
                if sid is not None:
                    try: cdp.send("Page.screencastFrameAck", {"sessionId": sid})
                    except Exception: pass
            cdp.on("Page.screencastFrame", on_frame)
            cdp.send("Page.enable")
            cdp.send("Page.startScreencast", {
                "format": "jpeg", "quality": 78,
                "maxWidth": item.viewport_width, "maxHeight": item.viewport_height,
                "everyNthFrame": 2,
            })
            item.screencast_active = True
        except Exception as exc:
            raise ChromiumBrowserError(f"CDP Screencast 시작 실패: {exc}", 500) from exc

    def _register_page_events_sync(self, item: ChromiumPageSession) -> None:
        item.page.on("load", lambda: setattr(item, "loading", False))
        item.page.on("domcontentloaded", lambda: setattr(item, "loading", False))
        item.page.on("popup", lambda popup: self._register_popup_sync(item.session_id, popup))

    def _register_popup_sync(self, parent_session_id: str, popup: Page) -> None:
        popup_id = self._safe_session_id(f"popup-{uuid.uuid4().hex}")
        item = ChromiumPageSession(session_id=popup_id, page=popup, loading=True, popup_parent_id=parent_session_id)
        self._sessions[popup_id] = item
        self._register_page_events_sync(item)
        self._start_screencast_sync(item)
        raw_url = str(popup.url or "")
        if raw_url.startswith(("http://", "https://")):
            try: self._validate_public_target_sync(raw_url)
            except ChromiumBrowserError:
                try: popup.close()
                except Exception: pass
                self._sessions.pop(popup_id, None); return
        try: title = popup.title() or "Popup"
        except Exception: title = "Popup"
        parent = self._sessions.get(parent_session_id)
        if parent:
            parent.popups.append(ChromiumPopup(popup_id, raw_url, title)); parent.last_used = time.time()

    def _state_sync(self, session_id: str, consume_popups: bool = True) -> dict[str, Any]:
        if not self._worker_process or self._worker_process.poll() is not None or not self._worker_ready:
            raise ChromiumBrowserError(
                "외부 브라우저 세션이 실행 중이 아닙니다. URL 이동 또는 '다시 연결'을 사용하세요.",
                409,
                self._diagnostic_snapshot_sync(),
            )
        result = dict(self._worker_rpc_sync("state", timeout=6.0, session_id=self._safe_session_id(session_id), consume_popups=consume_popups) or {})
        result["profile_dir"] = str(self._profile_dir or "")
        result["runtime_profile_dir"] = str(self._runtime_profile_dir or "")
        result["cdp_endpoint"] = str(self._cdp_http_url or "")
        return result

    def _navigate_sync(self, session_id: str, url: str, width: int | None, height: int | None, force_restart: bool = False) -> dict[str, Any]:
        target = self._validate_public_target_sync(url)
        self._ensure_started_sync(force_restart=force_restart)
        result = dict(self._worker_rpc_sync(
            "navigate",
            timeout=40.0,
            session_id=self._safe_session_id(session_id),
            url=target,
            width=width,
            height=height,
        ) or {})
        result["profile_dir"] = str(self._profile_dir or "")
        result["runtime_profile_dir"] = str(self._runtime_profile_dir or "")
        result["cdp_endpoint"] = str(self._cdp_http_url or "")
        return result

    def _action_sync(self, session_id: str, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        result = dict(self._worker_rpc_sync(
            "action",
            timeout=25.0,
            session_id=self._safe_session_id(session_id),
            action=str(action or ""),
            payload=dict(payload or {}),
        ) or {})
        result["profile_dir"] = str(self._profile_dir or "")
        result["runtime_profile_dir"] = str(self._runtime_profile_dir or "")
        result["cdp_endpoint"] = str(self._cdp_http_url or "")
        return result

    def _next_frame_sync(self, session_id: str, after_revision: int) -> dict[str, Any]:
        return dict(self._worker_rpc_sync(
            "next_frame",
            timeout=2.0,
            session_id=self._safe_session_id(session_id),
            after_revision=int(after_revision or 0),
        ) or {})

    def _screenshot_sync(self, session_id: str) -> bytes:
        result = dict(self._worker_rpc_sync(
            "screenshot",
            timeout=12.0,
            session_id=self._safe_session_id(session_id),
        ) or {})
        data = str(result.get("data") or "")
        if not data:
            raise ChromiumBrowserError("웹브라우저 화면 캡처 데이터가 비어 있습니다.", 500)
        try:
            return base64.b64decode(data)
        except Exception as exc:
            raise ChromiumBrowserError(f"웹브라우저 화면 캡처 decode 실패: {exc!r}", 500) from exc

    def _close_sync(self, session_id: str) -> dict[str, Any]:
        key = self._safe_session_id(session_id)
        if not self._worker_process or self._worker_process.poll() is not None or not self._worker_ready:
            return {"ok": True, "session_id": key}
        result = dict(self._worker_rpc_sync("close", timeout=8.0, session_id=key) or {})
        if int(result.get("remaining_sessions") or 0) <= 0:
            self._stop_browser_runtime_sync(clear_failure=False)
        return {"ok": True, "session_id": key, **result}

    def _archive_runtime_logs_sync(self, runtime: Path | None) -> None:
        if not runtime:
            return
        source = runtime / "chrome_startup.log"
        if not source.is_file():
            return
        try:
            logs_dir = self._diagnostic_log_path().parent
            logs_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            logs_dir = Path(__file__).resolve().parents[3] / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
        try:
            target = logs_dir / f"chrome_startup_{runtime.name}_{int(time.time())}.log"
            shutil.copy2(source, target)
            attempts = self._startup_diagnostics.get("attempts") or []
            if attempts:
                attempts[-1]["startup_log_archived_path"] = str(target)
                attempts[-1]["startup_log_archived_exists"] = target.is_file()
        except Exception as exc:
            attempts = self._startup_diagnostics.get("attempts") or []
            if attempts:
                attempts[-1]["startup_log_archive_error"] = f"{type(exc).__name__}: {exc!r}"

    def _stop_browser_runtime_sync(self, clear_failure: bool = False) -> None:
        runtime = self._runtime_profile_dir
        # The helper owns Playwright/Page objects. Shut it down first so storage state
        # is saved before killing the system Chrome Runtime profile.
        self._stop_playwright_worker_sync(graceful=True)
        self._sessions.clear()
        self._browser = None
        self._context = None
        self._playwright = None
        self._archive_runtime_logs_sync(runtime)
        proc = self._chrome_process
        self._chrome_process = None
        if proc and proc.poll() is None:
            self._kill_pid_tree_sync(int(proc.pid))
        cleanup = self._kill_runtime_processes_sync(runtime)
        attempts = self._startup_diagnostics.get("attempts") or []
        if attempts:
            attempts[-1]["cleanup_killed"] = int(cleanup.get("killed") or 0)
            attempts[-1]["cleanup_remaining"] = int(cleanup.get("remaining") or 0)
        self._cdp_http_url = ""
        self._cdp_ws_url = ""
        self._cleanup_runtime_profile_sync()
        self._write_diagnostic_log_sync()
        if clear_failure:
            self._startup_failed_latched = False
            self._startup_failure_at = 0.0
            self._startup_failure_message = ""

    def _shutdown_sync(self) -> None:
        self._stop_browser_runtime_sync(clear_failure=False)

    def _startup_cleanup_sync(self) -> dict[str, int]:
        result = self._cleanup_all_stale_runtime_sync()
        if result.get("killed") or result.get("remaining"):
            self._diag_update(
                "startup_stale_cleanup",
                f"이전 AgentStudio BrowserRuntime 정리 · kill root {result.get('killed', 0)} · remaining {result.get('remaining', 0)}",
            )
            self._write_diagnostic_log_sync()
        return result

    async def diagnostics(self) -> dict[str, Any]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._diagnostic_snapshot_sync)

    async def cleanup_stale_processes(self) -> dict[str, int]:
        # Cleanup uses a separate default worker thread so Browser navigation is never
        # queued behind stale-process scanning.
        return await asyncio.to_thread(self._startup_cleanup_sync)
    async def navigate(self, session_id: str, url: str, width: int | None = None, height: int | None = None, force_restart: bool = False) -> dict[str, Any]:
        return await self._run(self._navigate_sync, session_id, url, width, height, force_restart)
    async def state(self, session_id: str, consume_popups: bool = True) -> dict[str, Any]:
        return await self._run(self._state_sync, session_id, consume_popups)
    async def screenshot(self, session_id: str) -> bytes:
        return await self._run(self._screenshot_sync, session_id)
    async def action(self, session_id: str, action: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._run(self._action_sync, session_id, action, payload)
    async def next_frame(self, session_id: str, after_revision: int) -> dict[str, Any]:
        return await self._run(self._next_frame_sync, session_id, after_revision)
    async def close(self, session_id: str) -> dict[str, Any]:
        return await self._run(self._close_sync, session_id)
    async def shutdown(self) -> None:
        if self._shutdown_requested: return
        try:
            loop = asyncio.get_running_loop(); await loop.run_in_executor(self._executor, self._shutdown_sync)
        finally:
            self._shutdown_requested = True; self._executor.shutdown(wait=False, cancel_futures=True)

chromium_browser_manager = ChromiumBrowserManager()
