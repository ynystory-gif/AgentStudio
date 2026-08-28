from __future__ import annotations

import asyncio
import os
import shutil
from datetime import datetime
from pathlib import Path

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
    # AgentStudio users may relocate Ollama to another drive. Keep common known
    # portable locations after PATH/LOCALAPPDATA without making them mandatory.
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
        if row:
            return str(row.value or "").strip()
    return ""


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
            row = AppSetting(
                pc_name=pc_name,
                key=key,
                value=value,
                is_secret=False,
                updated_at=datetime.utcnow(),
            )
            session.add(row)
        else:
            row.value = value
            row.updated_at = datetime.utcnow()
        await session.commit()


async def get_recommended_model_status() -> dict:
    settings = get_settings()
    common_root = (
        await _pc_setting("COMMON_MODELS_ROOT")
        or str(settings.common_models_root or "").strip()
        or str(os.environ.get("COMMON_MODELS_ROOT", "") or "").strip()
    )
    current_model = (
        await _pc_setting("OLLAMA_MODEL")
        or str(settings.ollama_model or "").strip()
    )
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
            "공통 모델 관리 경로(COMMON_MODELS_ROOT)가 설정되어 있지 않습니다. 시스템 관리에서 공통 모델 경로를 먼저 저장하세요."
        )
    ollama_exe = str(status.get("ollama_executable") or "").strip()
    if not ollama_exe:
        raise RuntimeError("Ollama 실행 파일을 찾을 수 없습니다. Ollama 설치/실행 경로를 확인하세요.")

    model_root = Path(common_root).expanduser()
    model_root.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    # Ollama stores manifests/blobs under OLLAMA_MODELS. Point that root at the
    # user-configured AgentStudio common model path so every AgentStudio model
    # download obeys the same storage policy.
    env["OLLAMA_MODELS"] = str(model_root)

    process = await asyncio.create_subprocess_exec(
        ollama_exe,
        "pull",
        LATEST_RECOMMENDED_MODEL,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env=env,
    )
    stdout, _ = await process.communicate()
    output = stdout.decode("utf-8", errors="replace") if stdout else ""
    if process.returncode != 0:
        raise RuntimeError(
            f"{LATEST_RECOMMENDED_MODEL} 다운로드 실패 (ExitCode={process.returncode}): {output[-4000:]}"
        )

    # Persist the selected model in the current PC's app_settings and update the
    # running process environment/cache so subsequent LLM creation uses it now.
    await _set_pc_setting("OLLAMA_MODEL", LATEST_RECOMMENDED_MODEL)
    os.environ["OLLAMA_MODEL"] = LATEST_RECOMMENDED_MODEL
    os.environ["OLLAMA_MODELS"] = str(model_root)
    get_settings.cache_clear()

    return {
        "ok": True,
        "message": f"{LATEST_RECOMMENDED_MODEL} 다운로드 및 현재 PC 적용이 완료되었습니다.",
        "model": LATEST_RECOMMENDED_MODEL,
        "common_models_root": str(model_root),
        "pc_name": current_pc_name(),
        "output_tail": output[-2000:],
    }
