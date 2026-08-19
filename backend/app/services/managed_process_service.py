from __future__ import annotations

import os
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from typing import Any


class ManagedProcessService:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._processes: dict[str, subprocess.Popen] = {}
        self._meta: dict[str, dict[str, Any]] = {}

    def start_cmd(self, root: str, relative_path: str) -> dict[str, Any]:
        if sys.platform != "win32":
            raise RuntimeError("CMD 파일 실행은 Windows에서만 지원합니다.")
        project_root = Path(root).expanduser().resolve()
        target = (project_root / Path(relative_path.replace("\\", "/"))).resolve()
        target.relative_to(project_root)
        if target.suffix.lower() != ".cmd":
            raise ValueError(".cmd 파일만 실행할 수 있습니다.")
        if not target.is_file():
            raise FileNotFoundError(str(target))

        execution_id = str(uuid.uuid4())
        flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        process = subprocess.Popen(
            ["cmd.exe", "/d", "/c", str(target)],
            cwd=str(target.parent),
            creationflags=flags,
        )
        with self._lock:
            self._processes[execution_id] = process
            self._meta[execution_id] = {
                "path": str(target),
                "root": str(project_root),
                "pid": process.pid,
            }
        return {
            "ok": True,
            "execution_id": execution_id,
            "pid": process.pid,
            "path": str(target),
            "running": True,
        }

    def status(self, execution_id: str) -> dict[str, Any]:
        with self._lock:
            process = self._processes.get(execution_id)
            meta = dict(self._meta.get(execution_id) or {})
        if not process:
            return {"ok": False, "running": False, "execution_id": execution_id, "message": "실행 정보를 찾을 수 없습니다."}
        code = process.poll()
        if code is not None:
            with self._lock:
                self._processes.pop(execution_id, None)
        return {"ok": True, "running": code is None, "returncode": code, "execution_id": execution_id, **meta}

    def stop(self, execution_id: str) -> dict[str, Any]:
        with self._lock:
            process = self._processes.get(execution_id)
            meta = dict(self._meta.get(execution_id) or {})
        if not process:
            return {"ok": True, "cancelled": False, "execution_id": execution_id, "message": "현재 실행 중인 CMD가 없습니다."}
        if process.poll() is not None:
            return {"ok": True, "cancelled": False, "execution_id": execution_id, "returncode": process.returncode, **meta}
        try:
            # Windows: taskkill /T terminates the cmd.exe child tree as well.
            if sys.platform == "win32":
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    check=False,
                )
            else:
                process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
        finally:
            with self._lock:
                self._processes.pop(execution_id, None)
        return {"ok": True, "cancelled": True, "execution_id": execution_id, **meta, "message": "CMD 실행을 중지했습니다."}


managed_process_service = ManagedProcessService()
