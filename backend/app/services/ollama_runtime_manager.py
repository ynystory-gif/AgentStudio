from __future__ import annotations

import asyncio
import json
import os
import signal
import socket
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.services.ollama_installer import detect_ollama_exe
from app.services.gpu_runtime_manager import gpu_runtime_enabled, gpu_runtime_environment


RUNTIME_DIR = Path(__file__).resolve().parents[2] / "logs" / "ollama_server"
PID_FILE = RUNTIME_DIR / "managed_ollama.pid"
LOG_FILE = RUNTIME_DIR / "ollama_server.log"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _parse_target(base_url: str) -> tuple[str, int, str]:
    value = (base_url or "http://127.0.0.1:11434").rstrip("/")
    parsed = urlparse(value)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    return host, port, value


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            completed = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
            )
            return str(pid) in (completed.stdout or "")
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _managed_pid() -> int | None:
    try:
        if not PID_FILE.exists():
            return None
        raw = json.loads(PID_FILE.read_text(encoding="utf-8"))
        pid = int(raw.get("pid") or 0)
        if _pid_alive(pid):
            return pid
    except Exception:
        pass
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception:
        pass
    return None


def _write_pid(pid: int, exe: Path, base_url: str) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(
        json.dumps(
            {
                "pid": pid,
                "exe": str(exe),
                "base_url": base_url,
                "started_at": datetime.now().isoformat(),
                "owner": "THEANOVA AgentStudio",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.8):
            return True
    except OSError:
        return False


async def _api_status(base_url: str) -> dict:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3.0, connect=1.5)) as client:
            version_res = await client.get(f"{base_url}/api/version")
            version_res.raise_for_status()
            version = str((version_res.json() or {}).get("version") or "")
            tags_res = await client.get(f"{base_url}/api/tags")
            tags_res.raise_for_status()
            models = [
                str(item.get("name") or "")
                for item in (tags_res.json() or {}).get("models", [])
                if item.get("name")
            ]
        return {"running": True, "version": version, "models": models, "error": ""}
    except Exception as exc:
        return {
            "running": False,
            "version": "",
            "models": [],
            "error": f"{type(exc).__name__}: {exc}",
        }


async def get_ollama_runtime_status() -> dict:
    settings = get_settings()
    host, port, base_url = _parse_target(settings.ollama_base_url)
    exe = detect_ollama_exe()
    managed_pid = _managed_pid()
    api = await _api_status(base_url)
    local = host.lower() in LOCAL_HOSTS

    return {
        "ok": True,
        "installed": bool(exe),
        "ollama_exe": str(exe) if exe else "",
        "base_url": base_url,
        "host": host,
        "port": port,
        "local": local,
        "manageable": bool(local and exe),
        "running": bool(api["running"]),
        "port_open": await asyncio.to_thread(_port_open, host, port),
        "version": api["version"],
        "models": api["models"],
        "managed_by_agentstudio": bool(managed_pid),
        "managed_pid": managed_pid or 0,
        "log_path": str(LOG_FILE.resolve()),
        "status_message": (
            "Ollama 서버 연결됨"
            if api["running"]
            else "Ollama는 설치되어 있지만 서버가 중지되어 있습니다."
            if exe and local
            else "원격 Ollama URL은 AgentStudio에서 시작/중지하지 않습니다."
            if not local
            else "Ollama가 설치되어 있지 않습니다."
        ),
        "last_error": api["error"],
        "gpu_acceleration_enabled": gpu_runtime_enabled(),
    }


async def start_ollama_server() -> dict:
    settings = get_settings()
    host, port, base_url = _parse_target(settings.ollama_base_url)
    if host.lower() not in LOCAL_HOSTS:
        return {
            "ok": False,
            "message": "원격 Ollama URL은 AgentStudio가 로컬 프로세스로 시작할 수 없습니다.",
            "base_url": base_url,
        }

    current = await get_ollama_runtime_status()
    if current.get("running"):
        return {
            **current,
            "ok": True,
            "already_running": True,
            "message": "Ollama 서버가 이미 실행 중입니다.",
        }

    exe = detect_ollama_exe()
    if not exe:
        return {
            **current,
            "ok": False,
            "message": "Ollama 실행 파일을 찾지 못했습니다. 먼저 Ollama를 설치하세요.",
        }

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    log_handle = LOG_FILE.open("ab", buffering=0)
    env = gpu_runtime_environment(os.environ.copy())
    env["OLLAMA_HOST"] = f"{host}:{port}"

    kwargs: dict = {
        "cwd": str(exe.parent),
        "env": env,
        "stdin": subprocess.DEVNULL,
        "stdout": log_handle,
        "stderr": subprocess.STDOUT,
    }
    if os.name == "nt":
        kwargs["creationflags"] = (
            getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    else:
        kwargs["start_new_session"] = True

    try:
        proc = subprocess.Popen([str(exe), "serve"], **kwargs)
        _write_pid(proc.pid, exe, base_url)
    except Exception as exc:
        log_handle.close()
        return {
            "ok": False,
            "message": f"Ollama 서버 시작 실패: {type(exc).__name__}: {exc}",
            "ollama_exe": str(exe),
            "base_url": base_url,
            "log_path": str(LOG_FILE.resolve()),
        }
    finally:
        try:
            log_handle.close()
        except Exception:
            pass

    for _ in range(40):
        await asyncio.sleep(0.5)
        status = await get_ollama_runtime_status()
        if status.get("running"):
            return {
                **status,
                "ok": True,
                "started": True,
                "message": "Ollama 서버가 시작되었습니다.",
            }
        if proc.poll() is not None:
            break

    status = await get_ollama_runtime_status()
    if not status.get("running"):
        try:
            await stop_ollama_server()
        except Exception:
            pass
    return {
        **status,
        "ok": False,
        "message": "Ollama 프로세스를 시작했지만 API가 정상 응답하지 않았습니다. 로그를 확인하세요.",
        "log_path": str(LOG_FILE.resolve()),
    }


async def stop_ollama_server() -> dict:
    pid = _managed_pid()
    status_before = await get_ollama_runtime_status()
    if not pid:
        return {
            **status_before,
            "ok": False,
            "message": (
                "현재 Ollama 서버는 AgentStudio가 시작한 프로세스가 아니므로 안전을 위해 자동 종료하지 않습니다."
                if status_before.get("running")
                else "AgentStudio가 관리 중인 Ollama 서버 프로세스가 없습니다."
            ),
        }

    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                timeout=10,
            )
        else:
            os.killpg(pid, signal.SIGTERM)
    except Exception as exc:
        return {
            **status_before,
            "ok": False,
            "message": f"Ollama 서버 종료 실패: {type(exc).__name__}: {exc}",
        }
    finally:
        try:
            PID_FILE.unlink(missing_ok=True)
        except Exception:
            pass

    for _ in range(20):
        await asyncio.sleep(0.25)
        status = await get_ollama_runtime_status()
        if not status.get("running"):
            return {
                **status,
                "ok": True,
                "message": "AgentStudio가 시작한 Ollama 서버를 종료했습니다.",
            }

    status = await get_ollama_runtime_status()
    return {
        **status,
        "ok": not status.get("running"),
        "message": "Ollama 서버 종료 상태를 확인했습니다." if not status.get("running") else "Ollama 서버가 계속 응답하고 있습니다.",
    }


async def restart_managed_ollama_for_gpu_mode() -> dict:
    """Restart only an AgentStudio-owned Ollama process after GPU mode changes.

    External/user-started Ollama instances are never terminated automatically.
    """
    status = await get_ollama_runtime_status()
    if not status.get("running"):
        return {**status, "ok": True, "restarted": False, "message": "Ollama 서버가 중지 상태라 GPU 모드만 저장했습니다."}
    if not status.get("managed_by_agentstudio"):
        return {
            **status,
            "ok": True,
            "restarted": False,
            "external_ollama": True,
            "message": "외부에서 실행한 Ollama는 안전을 위해 재시작하지 않았습니다. AgentStudio GPU 설정은 다른 관리 작업에 즉시 적용됩니다.",
        }
    stopped = await stop_ollama_server()
    if not stopped.get("ok"):
        return {**stopped, "restarted": False}
    started = await start_ollama_server()
    return {**started, "restarted": bool(started.get("ok"))}
