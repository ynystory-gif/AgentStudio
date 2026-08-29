from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_ACTIVE_WORKERS: dict[int, subprocess.Popen] = {}
_ACTIVE_LOCK = asyncio.Lock()
_POLL_INTERVAL_SECONDS = 0.10


def _kill_process_tree_sync(pid: int, proc: subprocess.Popen | None = None) -> None:
    """Terminate one AgentStudio-owned Theme worker and all child processes."""
    if pid <= 0:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=4,
                check=False,
                creationflags=int(getattr(subprocess, "CREATE_NO_WINDOW", 0)),
            )
        except Exception:
            if proc and proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass
    else:
        try:
            os.killpg(pid, signal.SIGTERM)
            time.sleep(0.20)
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        except ProcessLookupError:
            pass
        except Exception:
            if proc and proc.poll() is None:
                try:
                    proc.kill()
                except Exception:
                    pass

    if proc and proc.poll() is None:
        try:
            proc.kill()
        except Exception:
            pass
    if proc:
        try:
            proc.wait(timeout=2)
        except Exception:
            pass


async def _kill_process_tree(pid: int, proc: subprocess.Popen | None = None) -> None:
    # The scoped taskkill/kill operation is short and only runs during cancel/timeout/shutdown.
    _kill_process_tree_sync(pid, proc)
    await asyncio.sleep(0)


async def run_theme_worker(operation: str, payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
    """Run CPU/Playwright Theme work in a disposable Python process.

    subprocess.Popen is intentionally used instead of asyncio subprocess APIs because
    AgentStudio uses WindowsSelectorEventLoopPolicy for psycopg compatibility. The
    process is polled asynchronously, so no ThreadPool worker is created in FastAPI.
    """
    temp_root = Path(tempfile.mkdtemp(prefix="agentstudio-theme-worker-"))
    input_path = temp_root / "input.json"
    output_path = temp_root / "output.json"
    stdout_path = temp_root / "stdout.log"
    stderr_path = temp_root / "stderr.log"
    input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    kwargs: dict[str, Any] = {}
    if os.name == "nt":
        kwargs["creationflags"] = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)) | int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        kwargs["start_new_session"] = True

    stdout_file = stdout_path.open("wb")
    stderr_file = stderr_path.open("wb")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "app.services.ui_theme_worker_process",
            str(operation or ""),
            str(input_path),
            str(output_path),
        ],
        cwd=str(_BACKEND_ROOT),
        stdout=stdout_file,
        stderr=stderr_file,
        stdin=subprocess.DEVNULL,
        **kwargs,
    )
    async with _ACTIVE_LOCK:
        _ACTIVE_WORKERS[int(proc.pid or 0)] = proc

    deadline = time.monotonic() + max(1.0, float(timeout))
    try:
        try:
            while proc.poll() is None:
                if time.monotonic() >= deadline:
                    await _kill_process_tree(int(proc.pid or 0), proc)
                    raise TimeoutError(f"Theme worker '{operation}' 제한시간 {timeout:.0f}초 초과")
                await asyncio.sleep(_POLL_INTERVAL_SECONDS)
        except asyncio.CancelledError:
            await _kill_process_tree(int(proc.pid or 0), proc)
            raise

        stdout_file.flush()
        stderr_file.flush()
        if proc.returncode != 0:
            detail = ""
            try:
                detail = stderr_path.read_text(encoding="utf-8", errors="replace").strip()
                if not detail:
                    detail = stdout_path.read_text(encoding="utf-8", errors="replace").strip()
            except Exception:
                pass
            raise RuntimeError(f"Theme worker '{operation}' 실패 (ExitCode={proc.returncode}): {detail[-2000:]}")
        if not output_path.exists():
            raise RuntimeError(f"Theme worker '{operation}' 결과 파일이 생성되지 않았습니다.")
        result = json.loads(output_path.read_text(encoding="utf-8"))
        if not isinstance(result, dict):
            raise RuntimeError(f"Theme worker '{operation}' 결과 형식이 올바르지 않습니다.")
        if result.get("ok") is False:
            raise RuntimeError(str(result.get("error") or f"Theme worker '{operation}' 실패"))
        return dict(result.get("result") or {})
    finally:
        async with _ACTIVE_LOCK:
            _ACTIVE_WORKERS.pop(int(proc.pid or 0), None)
        try:
            stdout_file.close()
        except Exception:
            pass
        try:
            stderr_file.close()
        except Exception:
            pass
        if proc.poll() is None:
            _kill_process_tree_sync(int(proc.pid or 0), proc)
        shutil.rmtree(temp_root, ignore_errors=True)


async def shutdown_theme_workers() -> int:
    """Kill every Theme worker owned by this Backend instance."""
    async with _ACTIVE_LOCK:
        rows = list(_ACTIVE_WORKERS.items())
    if not rows:
        return 0
    for pid, proc in rows:
        _kill_process_tree_sync(pid, proc)
    async with _ACTIVE_LOCK:
        for pid, _ in rows:
            _ACTIVE_WORKERS.pop(pid, None)
    await asyncio.sleep(0)
    return len(rows)


def active_theme_worker_pids() -> list[int]:
    return sorted(pid for pid, proc in _ACTIVE_WORKERS.items() if pid > 0 and proc.poll() is None)
