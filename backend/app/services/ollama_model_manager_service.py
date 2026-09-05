from __future__ import annotations

import asyncio
import json
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

LATEST_RECOMMENDED_MODEL = "qwen3.8:27b-mtp-q4_K_M"
_MODEL_JOBS: dict[str, dict] = {}
_MODEL_STATUS_CACHE: dict = {}
_MODEL_STATUS_CACHE_AT: float = 0.0
_MODEL_STATUS_TTL_SECONDS = 600.0


def qwen_model_metadata(model_name: str) -> dict:
    model = str(model_name or "").strip()
    lowered = model.casefold()
    version_match = re.search(r"qwen\s*(\d+(?:\.\d+)?)", lowered)
    parameter_match = re.search(r"(?:^|:|-)(\d+(?:\.\d+)?b)(?:-|$)", lowered)
    quant_match = re.search(r"(q\d+_[a-z0-9_]+)$", lowered)
    return {
        "provider": "ollama",
        "family": "qwen",
        "model": model,
        "version": version_match.group(1) if version_match else "",
        "parameter": parameter_match.group(1) if parameter_match else "",
        "quantization": quant_match.group(1) if quant_match else "",
        "mtp": "-mtp-" in lowered or lowered.endswith("-mtp"),
    }


def _installed_models_from_api_sync(base_url: str) -> list[str]:
    target = f"{str(base_url or 'http://127.0.0.1:11434').rstrip('/')}/api/tags"
    try:
        with urllib.request.urlopen(target, timeout=2.5) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
        return [str(item.get("name") or "").strip() for item in list(payload.get("models") or []) if str(item.get("name") or "").strip()]
    except Exception:
        return []


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


def _persist_backend_env_value(key: str, value: str) -> None:
    """Persist PC-local model selection so the next backend boot keeps the same model.

    app_settings can move to a runtime Supabase DB after bootstrap, so only writing the
    runtime DB is not enough for the next process start. backend/.env is local to this PC
    and is therefore the correct durable bootstrap fallback for OLLAMA_MODEL and the
    common model root.
    """
    env_path = Path(__file__).resolve().parents[2] / ".env"
    lines = env_path.read_text(encoding="utf-8", errors="replace").splitlines() if env_path.exists() else []
    prefix = f"{key}="
    replaced = False
    output: list[str] = []
    for line in lines:
        if line.strip().startswith(prefix):
            output.append(f"{key}={value}")
            replaced = True
        else:
            output.append(line)
    if not replaced:
        output.append(f"{key}={value}")
    env_path.parent.mkdir(parents=True, exist_ok=True)
    env_path.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


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
                _set_job(job_id, overall, "download", f"{LATEST_RECOMMENDED_MODEL} 다운로드 중... {percent}%", status="running")
            elif "pulling manifest" in clean.lower():
                _set_job(job_id, 37, "download", f"{LATEST_RECOMMENDED_MODEL} manifest 확인 중...", status="running")
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
    if result.returncode != 0 or LATEST_RECOMMENDED_MODEL.casefold() not in output.casefold():
        raise RuntimeError(f"다운로드 명령은 완료됐지만 Ollama 모델 목록에서 {LATEST_RECOMMENDED_MODEL}를 확인하지 못했습니다. " + output[-2000:])
    return output


async def get_recommended_model_status(force_refresh: bool = False) -> dict:
    """Return the recommended-model status with a short per-process cache.

    The installed/current model and common model root are configuration-like values, not
    live training telemetry. v5.445 therefore reuses the last successful check for ten
    minutes instead of re-reading settings and scanning Ollama executable paths on every
    Learning Center navigation. A model apply/download invalidates this cache.
    """
    global _MODEL_STATUS_CACHE, _MODEL_STATUS_CACHE_AT
    now = time.monotonic()
    if (
        not force_refresh
        and _MODEL_STATUS_CACHE
        and now - _MODEL_STATUS_CACHE_AT < _MODEL_STATUS_TTL_SECONDS
    ):
        cached = dict(_MODEL_STATUS_CACHE)
        cached["cache_hit"] = True
        cached["cache_ttl_seconds"] = int(_MODEL_STATUS_TTL_SECONDS)
        return cached

    settings = get_settings()
    common_root = await _pc_setting("COMMON_MODELS_ROOT") or str(os.environ.get("COMMON_MODELS_ROOT", "") or "").strip() or str(settings.common_models_root or "").strip()
    current_model = await _pc_setting("OLLAMA_MODEL") or str(os.environ.get("OLLAMA_MODEL", "") or "").strip() or str(settings.ollama_model or "").strip()
    ollama_exe = next(iter(_candidate_ollama_executables()), "")
    installed_models = await asyncio.to_thread(_installed_models_from_api_sync, str(settings.ollama_base_url or "http://127.0.0.1:11434"))
    recommended_installed = any(str(name).casefold() == LATEST_RECOMMENDED_MODEL.casefold() for name in installed_models)
    metadata = qwen_model_metadata(LATEST_RECOMMENDED_MODEL)
    result = {
        "ok": True,
        "recommended_model": LATEST_RECOMMENDED_MODEL,
        "recommended_model_info": metadata,
        "provider": metadata.get("provider"),
        "family": metadata.get("family"),
        "version": metadata.get("version"),
        "parameter": metadata.get("parameter"),
        "quantization": metadata.get("quantization"),
        "mtp": metadata.get("mtp"),
        "installed": recommended_installed,
        "installed_models": installed_models,
        "current_model": current_model,
        "common_models_root": common_root,
        "ollama_executable": ollama_exe,
        "ready": bool(common_root and ollama_exe),
        "pc_name": current_pc_name(),
        "cache_hit": False,
        "cache_ttl_seconds": int(_MODEL_STATUS_TTL_SECONDS),
        "latest_model_already_selected": current_model.strip().lower() == LATEST_RECOMMENDED_MODEL.lower(),
    }
    _MODEL_STATUS_CACHE = dict(result)
    _MODEL_STATUS_CACHE_AT = now
    return result


async def persist_current_ollama_model(model_name: str, common_root: str = "") -> None:
    global _MODEL_STATUS_CACHE, _MODEL_STATUS_CACHE_AT
    model = str(model_name or "").strip()
    if not model:
        raise ValueError("적용할 Ollama 모델 이름이 없습니다.")
    root = str(common_root or await _pc_setting("COMMON_MODELS_ROOT") or os.environ.get("COMMON_MODELS_ROOT", "") or "").strip()
    await _set_pc_setting("OLLAMA_MODEL", model)
    if root:
        await _set_pc_setting("COMMON_MODELS_ROOT", root)
    await asyncio.to_thread(_persist_backend_env_value, "OLLAMA_MODEL", model)
    if root:
        await asyncio.to_thread(_persist_backend_env_value, "COMMON_MODELS_ROOT", root)
    os.environ["OLLAMA_MODEL"] = model
    if root:
        os.environ["COMMON_MODELS_ROOT"] = root
        os.environ["OLLAMA_MODELS"] = root
    get_settings.cache_clear()
    _MODEL_STATUS_CACHE = {}
    _MODEL_STATUS_CACHE_AT = 0.0
    try:
        from app.services.active_ollama_model_service import invalidate_active_ollama_model_cache
        invalidate_active_ollama_model_cache()
    except Exception:
        pass


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
        _set_job(job_id, 35, "download", f"{LATEST_RECOMMENDED_MODEL} 다운로드 시작...", status="running")
        output = await asyncio.to_thread(_pull_model_with_progress_sync, job_id, ollama_exe, dict(restart["env"]))
        _set_job(job_id, 88, "verify", "다운로드 완료. Ollama 모델 목록을 검증 중...", status="running")
        list_output = await asyncio.to_thread(_verify_model_sync, ollama_exe, dict(restart["env"]))
        _set_job(job_id, 94, "apply", f"현재 PC 기본 모델을 {LATEST_RECOMMENDED_MODEL}로 변경 중...", status="running")
        await persist_current_ollama_model(LATEST_RECOMMENDED_MODEL, str(model_root))
        _set_job(job_id, 100, "done", f"{LATEST_RECOMMENDED_MODEL} 다운로드 및 현재 PC 적용이 완료되었습니다.", status="completed", result={"model": LATEST_RECOMMENDED_MODEL, "common_models_root": str(model_root), "ollama_base_url": restart["base_url"], "output_tail": output[-1200:], "list_tail": list_output[-800:]})
    except Exception as exc:
        _set_job(job_id, int(_MODEL_JOBS.get(job_id, {}).get("progress") or 0), "failed", str(exc) or type(exc).__name__, status="failed", error=str(exc) or type(exc).__name__)


async def start_recommended_model_job() -> dict:
    status = await get_recommended_model_status(force_refresh=True)
    if not str(status.get("common_models_root") or "").strip():
        raise ValueError("공통 모델 관리 경로(COMMON_MODELS_ROOT)가 설정되어 있지 않습니다. 시스템 관리에서 공통 모델 경로를 먼저 저장하세요.")
    if not str(status.get("ollama_executable") or "").strip():
        raise RuntimeError("Ollama 실행 파일을 찾을 수 없습니다. Ollama 설치/실행 경로를 확인하세요.")
    for job in _MODEL_JOBS.values():
        if job.get("status") == "running":
            return dict(job)
    job_id = uuid.uuid4().hex
    _set_job(job_id, 1, "queued", f"{LATEST_RECOMMENDED_MODEL} 다운로드 작업을 준비합니다.", status="running", created_at=datetime.utcnow().isoformat())
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
