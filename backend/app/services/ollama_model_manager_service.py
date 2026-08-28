from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.machine_identity import current_pc_name
from app.models.entities import AppSetting

LATEST_RECOMMENDED_MODEL = "qwen3.5:4b"


def _candidate_ollama_executables() -> list[str]:
    candidates: list[str] = []
    for name in ("ollama.exe", "ollama"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        candidates.append(str(Path(local_app_data) / "Programs" / "Ollama" / "ollama.exe"))
    for drive in ("C", "D", "E", "F", "G"):
        candidates.append(f"{drive}:\\Ollama\\App\\ollama.exe")
    seen: set[str] = set()
    result: list[str] = []
    for raw in candidates:
        value = str(raw or "").strip()
        key = value.lower()
        if value and key not in seen and Path(value).exists():
            seen.add(key)
            result.append(value)
    return result


async def _pc_setting(key: str) -> str:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(AppSetting).where(
                    AppSetting.pc_name == pc_name,
                    AppSetting.key == key,
                )
            )
        ).scalar_one_or_none()
        return str(row.value or "").strip() if row else ""


async def _set_pc_setting(key: str, value: str) -> None:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(AppSetting).where(
                    AppSetting.pc_name == pc_name,
                    AppSetting.key == key,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            session.add(
                AppSetting(
                    pc_name=pc_name,
                    key=key,
                    value=value,
                    is_secret=False,
                    updated_at=datetime.utcnow(),
                )
            )
        else:
            row.value = value
            row.updated_at = datetime.utcnow()
        await session.commit()


def _http_ok(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return 200 <= int(response.status) < 500
    except Exception:
        return False


def _wait_ollama_sync(base_url: str, seconds: int = 30) -> bool:
    for _ in range(max(1, seconds * 2)):
        if _http_ok(f"{base_url.rstrip('/')}/api/tags"):
            return True
        time.sleep(0.5)
    return False


def _persist_windows_ollama_models(path: str) -> None:
    if os.name != "nt":
        return
    try:
        subprocess.run(
            ["setx", "OLLAMA_MODELS", path],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except Exception:
        pass


def _restart_local_ollama_sync(ollama_exe: str, model_root: Path, base_url: str) -> dict:
    parsed = urlparse(base_url)
    host = (parsed.hostname or "127.0.0.1").lower()
    port = int(parsed.port or 11434)
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("원격 Ollama 서버에는 로컬 공통 모델 경로를 자동 적용할 수 없습니다.")

    env = os.environ.copy()
    env["OLLAMA_MODELS"] = str(model_root)
    env["OLLAMA_HOST"] = f"127.0.0.1:{port}"

    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/IM", "ollama.exe", "/F"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        time.sleep(1.0)
        flags = 0
        for name in ("CREATE_NEW_PROCESS_GROUP", "DETACHED_PROCESS", "CREATE_NO_WINDOW"):
            flags |= int(getattr(subprocess, name, 0))
        subprocess.Popen(
            [ollama_exe, "serve"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=True,
        )
    else:
        subprocess.run(["pkill", "-f", "ollama serve"], capture_output=True, check=False)
        subprocess.Popen(
            [ollama_exe, "serve"],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )

    base = f"http://127.0.0.1:{port}"
    if not _wait_ollama_sync(base, 35):
        raise RuntimeError(f"공통 모델 경로로 Ollama 서버를 재시작하지 못했습니다: {base}")
    return {"base_url": base, "env": env}


def _pull_model_sync(ollama_exe: str, env: dict[str, str]) -> str:
    result = subprocess.run(
        [ollama_exe, "pull", LATEST_RECOMMENDED_MODEL],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=7200,
        check=False,
    )
    output = str(result.stdout or "")
    if result.returncode != 0:
        raise RuntimeError(
            f"{LATEST_RECOMMENDED_MODEL} 다운로드 실패 (ExitCode={result.returncode}): "
            f"{output[-4000:]}"
        )
    return output


def _verify_model_sync(ollama_exe: str, env: dict[str, str]) -> str:
    result = subprocess.run(
        [ollama_exe, "list"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    output = str(result.stdout or "")
    if result.returncode != 0 or "qwen3.5:4b" not in output.lower():
        raise RuntimeError(
            "다운로드 명령은 완료됐지만 Ollama 모델 목록에서 qwen3.5:4b를 확인하지 못했습니다. "
            + output[-2000:]
        )
    return output


async def get_recommended_model_status() -> dict:
    settings = get_settings()
    common_root = (
        await _pc_setting("COMMON_MODELS_ROOT")
        or str(settings.common_models_root or "").strip()
        or str(os.environ.get("COMMON_MODELS_ROOT", "") or "").strip()
    )
    current_model = await _pc_setting("OLLAMA_MODEL") or str(settings.ollama_model or "").strip()
    ollama_exe = next(iter(_candidate_ollama_executables()), "")
    return {
        "ok": True,
        "recommended_model": LATEST_RECOMMENDED_MODEL,
        "current_model": current_model,
        "common_models_root": common_root,
        "ollama_executable": ollama_exe,
        "ready": bool(common_root and ollama_exe),
        "pc_name": current_pc_name(),
    }


async def download_and_apply_recommended_model() -> dict:
    status = await get_recommended_model_status()
    common_root = str(status.get("common_models_root") or "").strip()
    if not common_root:
        raise ValueError(
            "공통 모델 관리 경로(COMMON_MODELS_ROOT)가 설정되어 있지 않습니다. "
            "시스템 관리에서 공통 모델 경로를 먼저 저장하세요."
        )
    ollama_exe = str(status.get("ollama_executable") or "").strip()
    if not ollama_exe:
        raise RuntimeError("Ollama 실행 파일을 찾을 수 없습니다. Ollama 설치/실행 경로를 확인하세요.")

    settings = get_settings()
    model_root = Path(common_root).expanduser().resolve()
    model_root.mkdir(parents=True, exist_ok=True)

    # main.py uses WindowsSelectorEventLoopPolicy, which cannot create asyncio
    # subprocesses on Windows. All Ollama process work therefore runs in a worker
    # thread with standard subprocess APIs.
    _persist_windows_ollama_models(str(model_root))
    restart = await asyncio.to_thread(
        _restart_local_ollama_sync,
        ollama_exe,
        model_root,
        str(settings.ollama_base_url or "http://127.0.0.1:11434"),
    )
    env = dict(restart["env"])
    output = await asyncio.to_thread(_pull_model_sync, ollama_exe, env)
    list_output = await asyncio.to_thread(_verify_model_sync, ollama_exe, env)

    await _set_pc_setting("COMMON_MODELS_ROOT", str(model_root))
    await _set_pc_setting("OLLAMA_MODEL", LATEST_RECOMMENDED_MODEL)
    os.environ["COMMON_MODELS_ROOT"] = str(model_root)
    os.environ["OLLAMA_MODELS"] = str(model_root)
    os.environ["OLLAMA_MODEL"] = LATEST_RECOMMENDED_MODEL
    get_settings.cache_clear()

    return {
        "ok": True,
        "message": (
            f"{LATEST_RECOMMENDED_MODEL}을 공통 모델 경로에 다운로드하고 "
            "현재 PC 기본 Ollama 모델로 적용했습니다."
        ),
        "model": LATEST_RECOMMENDED_MODEL,
        "common_models_root": str(model_root),
        "pc_name": current_pc_name(),
        "ollama_base_url": restart["base_url"],
        "output_tail": output[-2000:],
        "list_tail": list_output[-1000:],
        "ollama_restarted": True,
    }
