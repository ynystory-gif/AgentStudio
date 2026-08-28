from __future__ import annotations

import asyncio
import os
import re
import shutil
import subprocess
import time
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.machine_identity import current_pc_name
from app.models.entities import AppSetting

LATEST_RECOMMENDED_MODEL = "qwen3.5:4b"
_MODEL_JOBS: dict[str, dict] = {}


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
            session.add(AppSetting(pc_name=pc_name, key=key, value=value, is_secret=False, updated_at=datetime.utcnow()))
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
        subprocess.run(["setx", "OLLAMA_MODELS", path], capture_output=True, text=True, timeout=15, check=False)
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
        subprocess.run(["taskkill", "/IM", "ollama.exe", "/F"], capture_output=True, text=True, timeout=20, check=False)
        time.sleep(1.0)
        flags = 0
        for name in ("CREATE_NEW_PROCESS_GROUP", "DETACHED_PROCESS", "CREATE_NO_WINDOW"):
            flags |= int(getattr(subprocess, name, 0))
        subprocess.Popen([ollama_exe, "serve"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, creationflags=flags, close_fds=True)
    else:
        subprocess.run(["pkill", "-f", "ollama serve"], capture_output=True, check=False)
        subprocess.Popen([ollama_exe, "serve"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, start_new_session=True)
    base = f"http://127.0.0.1:{port}"
    if not _wait_ollama_sync(base, 35):
        raise RuntimeError(f"공통 모델 경로로 Ollama 서버를 재시작하지 못했습니다: {base}")
    return {"base_url": base, "env": env}


def _set_job(job_id: str, progress: int, stage: str, message: str, **extra) -> None:
    job = _MODEL_JOBS.setdefault(job_id, {})
    job.update({"id": job_id, "progress": max(0, min(100, int(progress))), "stage": stage, "message": message, "updated_at": datetime.utcnow().isoformat(), **extra})


def _pull_model_with_progress_sync(job_id: str, ollama_exe: str, env: dict[str, str]) -> str:
    process = subprocess.Popen(
        [ollama_exe, "pull", LATEST_RECOMMENDED_MODEL],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    if process.stdout is None:
        raise RuntimeError("Ollama 다운로드 출력을 읽을 수 없습니다.")
    output_parts: list[str] = []
    buffer = ""
    while True:
        char = process.stdout.read(1)
        if char == "" and process.poll() is not None:
            break
        if not char:
            time.sleep(0.05)
            continue
        output_parts.append(char)
        buffer += char
        if char in {"\r", "\n"} or len(buffer) > 500:
            clean = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", buffer).strip()
            match = re.search(r"(\d{1,3})%", clean)
            if match:
                percent = max(0, min(100, int(match.group(1))))
                overall = 35 + int(percent * 0.50)
                _set_job(job_id, overall, "download", f"qwen3.5:4b 다운로드 중... {percent}%", status="running")
            elif "pulling manifest" in clean.lower():
                _set_job(job_id, 37, "download", "qwen3.5:4b manifest 확인 중...", status="running")
            elif clean:
                _set_job(job_id, int(_MODEL_JOBS.get(job_id, {}).get("progress") or 35), "download", clean[-180:], status="running")
            buffer = ""
    return_code = process.wait(timeout=30)
    output = "".join(output_parts)
    if return_code != 0:
        raise RuntimeError(f"{LATEST_RECOMMENDED_MODEL} 다운로드 실패 (ExitCode={return_code}): {output[-4000:]}")
    return output


def _verify_model_sync(ollama_exe: str, env: dict[str, str]) -> str:
    result = subprocess.run([ollama_exe, "list"], env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", timeout=30, check=False)
    output = str(result.stdout or "")
    if result.returncode != 0 or "qwen3.5:4b" not in output.lower():
        raise RuntimeError("다운로드 명령은 완료됐지만 Ollama 모델 목록에서 qwen3.5:4b를 확인하지 못했습니다. " + output[-2000:])
    return output


async def get_recommended_model_status() -> dict:
    settings = get_settings()
    common_root = await _pc_setting("COMMON_MODELS_ROOT") or str(settings.common_models_root or "").strip() or str(os.environ.get("COMMON_MODELS_ROOT", "") or "").strip()
    current_model = await _pc_setting("OLLAMA_MODEL") or str(settings.ollama_model or "").strip()
    ollama_exe = next(iter(_candidate_ollama_executables()), "")
    return {"ok": True, "recommended_model": LATEST_RECOMMENDED_MODEL, "current_model": current_model, "common_models_root": common_root, "ollama_executable": ollama_exe, "ready": bool(common_root and ollama_exe), "pc_name": current_pc_name()}


async def _run_download_job(job_id: str, status: dict) -> None:
    try:
        common_root = str(status.get("common_models_root") or "").strip()
        ollama_exe = str(status.get("ollama_executable") or "").strip()
        settings = get_settings()
        model_root = Path(common_root).expanduser().resolve()
        _set_job(job_id, 5, "prepare", f"공통 모델 경로 확인: {model_root}", status="running")
        await asyncio.to_thread(model_root.mkdir, parents=True, exist_ok=True)
        _set_job(job_id, 12, "environment", "OLLAMA_MODELS 공통 경로를 Windows 환경에 적용 중...", status="running")
        await asyncio.to_thread(_persist_windows_ollama_models, str(model_root))
        _set_job(job_id, 22, "restart", "Ollama 서버를 공통 모델 경로로 재시작 중...", status="running")
        restart = await asyncio.to_thread(_restart_local_ollama_sync, ollama_exe, model_root, str(settings.ollama_base_url or "http://127.0.0.1:11434"))
        _set_job(job_id, 35, "download", "qwen3.5:4b 다운로드 시작... 약 3.4GB입니다.", status="running")
        output = await asyncio.to_thread(_pull_model_with_progress_sync, job_id, ollama_exe, dict(restart["env"]))
        _set_job(job_id, 88, "verify", "다운로드 완료. Ollama 모델 목록을 검증 중...", status="running")
        list_output = await asyncio.to_thread(_verify_model_sync, ollama_exe, dict(restart["env"]))
        _set_job(job_id, 94, "apply", "현재 PC 기본 모델을 qwen3.5:4b로 변경 중...", status="running")
        await _set_pc_setting("COMMON_MODELS_ROOT", str(model_root))
        await _set_pc_setting("OLLAMA_MODEL", LATEST_RECOMMENDED_MODEL)
        os.environ["COMMON_MODELS_ROOT"] = str(model_root)
        os.environ["OLLAMA_MODELS"] = str(model_root)
        os.environ["OLLAMA_MODEL"] = LATEST_RECOMMENDED_MODEL
        get_settings.cache_clear()
        _set_job(job_id, 100, "done", "qwen3.5:4b 다운로드 및 현재 PC 적용이 완료되었습니다.", status="completed", result={"model": LATEST_RECOMMENDED_MODEL, "common_models_root": str(model_root), "ollama_base_url": restart["base_url"], "output_tail": output[-1200:], "list_tail": list_output[-800:]})
    except Exception as exc:
        _set_job(job_id, int(_MODEL_JOBS.get(job_id, {}).get("progress") or 0), "failed", str(exc) or type(exc).__name__, status="failed", error=str(exc) or type(exc).__name__)


async def start_recommended_model_job() -> dict:
    status = await get_recommended_model_status()
    if not str(status.get("common_models_root") or "").strip():
        raise ValueError("공통 모델 관리 경로(COMMON_MODELS_ROOT)가 설정되어 있지 않습니다. 시스템 관리에서 공통 모델 경로를 먼저 저장하세요.")
    if not str(status.get("ollama_executable") or "").strip():
        raise RuntimeError("Ollama 실행 파일을 찾을 수 없습니다. Ollama 설치/실행 경로를 확인하세요.")
    for job in _MODEL_JOBS.values():
        if job.get("status") == "running":
            return dict(job)
    job_id = uuid.uuid4().hex
    _set_job(job_id, 1, "queued", "qwen3.5:4b 다운로드 작업을 준비합니다.", status="running", created_at=datetime.utcnow().isoformat())
    asyncio.create_task(_run_download_job(job_id, status))
    return dict(_MODEL_JOBS[job_id])


async def get_recommended_model_job(job_id: str) -> dict:
    job = _MODEL_JOBS.get(str(job_id or ""))
    if not job:
        raise KeyError("모델 다운로드 작업을 찾을 수 없습니다.")
    return dict(job)


async def download_and_apply_recommended_model() -> dict:
    job = await start_recommended_model_job()
    job_id = job["id"]
    while True:
        current = await get_recommended_model_job(job_id)
        if current.get("status") == "completed":
            return {"ok": True, "message": current.get("message", "완료"), **dict(current.get("result") or {})}
        if current.get("status") == "failed":
            raise RuntimeError(str(current.get("error") or current.get("message") or "모델 다운로드 실패"))
        await asyncio.sleep(1)
