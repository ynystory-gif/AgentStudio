from __future__ import annotations

import asyncio
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
_ACTIVE_WORKERS: dict[int, asyncio.subprocess.Process] = {}
_ACTIVE_LOCK = asyncio.Lock()


async def _kill_process_tree(pid: int, proc: asyncio.subprocess.Process | None = None) -> None:
    """Terminate one AgentStudio-owned Theme worker and all of its children.

    On Windows the worker can own Playwright/Node helper processes, so killing only the
    Python PID is insufficient. taskkill /T /F is scoped to the tracked worker PID and
    never targets every python.exe process on the machine.
    """
    if pid <= 0:
        return
    if os.name == "nt":
        try:
            killer = await asyncio.create_subprocess_exec(
                "taskkill", "/PID", str(pid), "/T", "/F",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            try:
                await asyncio.wait_for(killer.wait(), timeout=4)
            except asyncio.TimeoutError:
                try:
                    killer.kill()
                except Exception:
                    pass
        except Exception:
            if proc and proc.returncode is None:
                try:
                    proc.kill()
                except Exception:
                    pass
    else:
        try:
            os.killpg(pid, signal.SIGTERM)
            await asyncio.sleep(0.25)
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        except ProcessLookupError:
            pass
        except Exception:
            if proc and proc.returncode is None:
                try:
                    proc.kill()
                except Exception:
                    pass

    if proc and proc.returncode is None:
        try:
            await asyncio.wait_for(proc.wait(), timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


async def run_theme_worker(operation: str, payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
    """Run CPU/Playwright Theme work in a disposable Python process.

    Cancellation, timeout and Backend shutdown all terminate the tracked process tree,
    preventing non-daemon ThreadPool/Playwright workers from keeping FastAPI alive.
    """
    temp_root = Path(tempfile.mkdtemp(prefix="agentstudio-theme-worker-"))
    input_path = temp_root / "input.json"
    output_path = temp_root / "output.json"
    input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    creationflags = 0
    kwargs: dict[str, Any] = {}
    if os.name == "nt":
        creationflags = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)) | int(getattr(subprocess, "CREATE_NO_WINDOW", 0))
        kwargs["creationflags"] = creationflags
    else:
        kwargs["start_new_session"] = True

    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "app.services.ui_theme_worker_process",
        str(operation or ""),
        str(input_path),
        str(output_path),
        cwd=str(_BACKEND_ROOT),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        **kwargs,
    )
    async with _ACTIVE_LOCK:
        _ACTIVE_WORKERS[int(proc.pid or 0)] = proc

    try:
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=max(1.0, float(timeout)))
        except asyncio.TimeoutError:
            await _kill_process_tree(int(proc.pid or 0), proc)
            raise TimeoutError(f"Theme worker '{operation}' 제한시간 {timeout:.0f}초 초과")
        except asyncio.CancelledError:
            await _kill_process_tree(int(proc.pid or 0), proc)
            raise

        if proc.returncode != 0:
            detail = (stderr or stdout or b"").decode("utf-8", errors="replace").strip()
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
        shutil.rmtree(temp_root, ignore_errors=True)


async def shutdown_theme_workers() -> int:
    """Kill every Theme worker owned by this Backend instance."""
    async with _ACTIVE_LOCK:
        rows = list(_ACTIVE_WORKERS.items())
    if not rows:
        return 0
    await asyncio.gather(*(_kill_process_tree(pid, proc) for pid, proc in rows), return_exceptions=True)
    async with _ACTIVE_LOCK:
        for pid, _ in rows:
            _ACTIVE_WORKERS.pop(pid, None)
    return len(rows)


def active_theme_worker_pids() -> list[int]:
    return sorted(pid for pid, proc in _ACTIVE_WORKERS.items() if pid > 0 and proc.returncode is None)
