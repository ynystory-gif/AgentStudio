from __future__ import annotations

"""Bind true weight fine-tuning to AgentStudio's saved PC path settings.

The first implementation used %LOCALAPPDATA% for working files and caches, which made
large QLoRA jobs consume the system drive even when System Admin had explicit G:\\Temp
and G:\\Cache roots. This bridge keeps the training service intact but makes its path
helpers and subprocess environment honor the persisted per-PC settings.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.machine_identity import current_pc_name
from app.models.entities import AppSetting
from app.services import learning_finetune_job_service as finetune


_SETTING_KEYS = ("DEFAULT_TEMP_ROOT", "DEFAULT_CACHE_ROOT", "COMMON_MODELS_ROOT")
_ORIGINAL_CAPABILITY = finetune.get_weight_finetune_capability
_ORIGINAL_START_JOB = finetune.start_weight_finetune_job


def _default_base(name: str) -> Path:
    local = str(os.environ.get("LOCALAPPDATA") or "").strip()
    if local:
        return Path(local) / "THEANOVA" / "AgentStudio" / name
    return Path.home() / ".theanova" / "AgentStudio" / name


def _temp_work_root() -> Path:
    configured = str(os.environ.get("AGENTSTUDIO_FINETUNE_TEMP_ROOT") or "").strip()
    path = Path(configured) if configured else _default_base("temp")
    path = path / "THEANOVA" / "AgentStudio" / "learning" / "weight_finetune"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_work_root() -> Path:
    configured = str(os.environ.get("AGENTSTUDIO_FINETUNE_CACHE_ROOT") or "").strip()
    path = Path(configured) if configured else _default_base("cache")
    path = path / "THEANOVA" / "AgentStudio" / "learning" / "weight_finetune"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _package_dir() -> Path:
    path = _cache_work_root() / "python_packages"
    path.mkdir(parents=True, exist_ok=True)
    return path


async def _read_pc_paths() -> dict[str, str]:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(AppSetting).where(
                    AppSetting.pc_name == pc_name,
                    AppSetting.key.in_(_SETTING_KEYS),
                )
            )
        ).scalars().all()
    values = {str(row.key): str(row.value or "").strip() for row in rows}
    # Runtime environment is a safe fallback when DB settings have not yet been loaded.
    for key in _SETTING_KEYS:
        if not values.get(key):
            values[key] = str(os.environ.get(key) or "").strip()
    return values


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _apply_process_cache_environment(temp_root: Path, cache_root: Path) -> dict[str, str]:
    temp_dir = _ensure_dir(temp_root / "runtime_temp")
    hf_home = _ensure_dir(cache_root / "huggingface")
    hf_hub = _ensure_dir(hf_home / "hub")
    transformers = _ensure_dir(hf_home / "transformers")
    pip_cache = _ensure_dir(cache_root / "pip")
    torch_cache = _ensure_dir(cache_root / "torch")

    values = {
        "TEMP": str(temp_dir),
        "TMP": str(temp_dir),
        "TMPDIR": str(temp_dir),
        "HF_HOME": str(hf_home),
        "HUGGINGFACE_HUB_CACHE": str(hf_hub),
        "TRANSFORMERS_CACHE": str(transformers),
        "PIP_CACHE_DIR": str(pip_cache),
        "TORCH_HOME": str(torch_cache),
        "AGENTSTUDIO_FINETUNE_TEMP_ROOT": str(Path(os.environ.get("AGENTSTUDIO_FINETUNE_TEMP_ROOT") or temp_root.parents[3])),
        "AGENTSTUDIO_FINETUNE_CACHE_ROOT": str(Path(os.environ.get("AGENTSTUDIO_FINETUNE_CACHE_ROOT") or cache_root.parents[3])),
    }
    os.environ.update(values)
    return values


async def configure_weight_finetune_paths() -> dict:
    settings = await _read_pc_paths()
    raw_temp = str(settings.get("DEFAULT_TEMP_ROOT") or "").strip()
    raw_cache = str(settings.get("DEFAULT_CACHE_ROOT") or "").strip()
    raw_models = str(settings.get("COMMON_MODELS_ROOT") or "").strip()

    if raw_temp:
        os.environ["AGENTSTUDIO_FINETUNE_TEMP_ROOT"] = raw_temp
    if raw_cache:
        os.environ["AGENTSTUDIO_FINETUNE_CACHE_ROOT"] = raw_cache

    temp_root = _temp_work_root()
    cache_root = _cache_work_root()
    env = _apply_process_cache_environment(temp_root, cache_root)

    return {
        "temp_setting": raw_temp,
        "cache_setting": raw_cache,
        "common_models_root": raw_models,
        "temp_work_root": str(temp_root),
        "cache_work_root": str(cache_root),
        "python_packages_root": str(_package_dir()),
        "hf_home": env["HF_HOME"],
        "pip_cache": env["PIP_CACHE_DIR"],
    }


def _python_cuda_probe() -> dict:
    code = (
        "import json\n"
        "try:\n"
        " import torch\n"
        " ok=bool(torch.cuda.is_available())\n"
        " name=str(torch.cuda.get_device_name(0)) if ok else ''\n"
        " mem=round(float(torch.cuda.get_device_properties(0).total_memory)/(1024**3),1) if ok else 0\n"
        " print(json.dumps({'ok':ok,'name':name,'memory_gb':mem,'torch':str(torch.__version__),'cuda':str(torch.version.cuda or '')}))\n"
        "except Exception as e:\n"
        " print(json.dumps({'ok':False,'error':str(e)}))\n"
    )
    try:
        completed = subprocess.run(
            [sys.executable, "-c", code],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
            env=os.environ.copy(),
        )
        lines = [line.strip() for line in str(completed.stdout or "").splitlines() if line.strip()]
        return json.loads(lines[-1]) if lines else {"ok": False, "error": "CUDA probe output is empty"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _nvidia_smi_probe() -> dict:
    exe = shutil.which("nvidia-smi") or shutil.which("nvidia-smi.exe")
    if not exe:
        return {"available": False}
    try:
        completed = subprocess.run(
            [exe, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            check=False,
        )
        first = str(completed.stdout or "").splitlines()[0].strip() if completed.stdout else ""
        if completed.returncode != 0 or not first:
            return {"available": False, "error": first}
        parts = [value.strip() for value in first.split(",")]
        return {
            "available": True,
            "name": parts[0] if parts else "NVIDIA GPU",
            "memory_gb": round(float(parts[1]) / 1024, 1) if len(parts) > 1 else 0.0,
        }
    except Exception as exc:
        return {"available": False, "error": str(exc)}


async def get_weight_finetune_capability_configured() -> dict:
    paths = await configure_weight_finetune_paths()
    result = await _ORIGINAL_CAPABILITY()

    temp_free = round(shutil.disk_usage(Path(paths["temp_work_root"])).free / (1024 ** 3), 1)
    cache_free = round(shutil.disk_usage(Path(paths["cache_work_root"])).free / (1024 ** 3), 1)
    effective_free = min(temp_free, cache_free)

    cuda = _python_cuda_probe()
    nvidia = _nvidia_smi_probe()
    reasons = [
        str(value) for value in list(result.get("reasons") or [])
        if not str(value).startswith("디스크 여유 공간이 부족합니다")
        and not str(value).startswith("CUDA GPU를 사용할 수 없습니다")
        and not str(value).startswith("GPU VRAM이 부족합니다")
    ]

    cuda_ok = bool(cuda.get("ok"))
    gpu_name = str(cuda.get("name") or nvidia.get("name") or result.get("gpu_name") or "")
    gpu_memory = float(cuda.get("memory_gb") or nvidia.get("memory_gb") or result.get("gpu_memory_gb") or 0.0)
    if not cuda_ok:
        if nvidia.get("available"):
            reasons.insert(0, "NVIDIA GPU는 감지되지만 AgentStudio Python의 PyTorch에서 CUDA를 사용할 수 없습니다. CUDA 지원 PyTorch 환경을 확인하세요.")
        else:
            reasons.insert(0, "CUDA GPU를 사용할 수 없습니다.")
    elif gpu_memory < 6.0:
        reasons.insert(0, f"GPU VRAM이 부족합니다. 현재 {gpu_memory}GB, 권장 6GB 이상")

    # Merge/Safetensors and HF cache can each need substantial room. Both configured
    # locations must therefore have enough space; never fall back to the system drive.
    if temp_free < 20:
        reasons.append(f"Temp 경로 여유 공간이 부족합니다. {paths['temp_setting'] or paths['temp_work_root']} 현재 {temp_free}GB, 권장 20GB 이상")
    if cache_free < 20:
        reasons.append(f"Cache 경로 여유 공간이 부족합니다. {paths['cache_setting'] or paths['cache_work_root']} 현재 {cache_free}GB, 권장 20GB 이상")

    result.update({
        "ready": not reasons,
        "reasons": reasons,
        "cuda_available": cuda_ok,
        "gpu_name": gpu_name,
        "gpu_memory_gb": gpu_memory,
        "torch_error": str(cuda.get("error") or ""),
        "torch_version": str(cuda.get("torch") or ""),
        "torch_cuda_version": str(cuda.get("cuda") or ""),
        "nvidia_gpu_detected": bool(nvidia.get("available")),
        "disk_free_gb": effective_free,
        "temp_disk_free_gb": temp_free,
        "cache_disk_free_gb": cache_free,
        **paths,
        "path_source": "agentstudio_saved_pc_settings",
    })
    return result


async def start_weight_finetune_job_configured() -> dict:
    await configure_weight_finetune_paths()
    return await _ORIGINAL_START_JOB()


# Patch path helpers used by all worker/job internals. The wrapper calls above configure
# the environment before the original capability/job implementation runs.
finetune._root = _temp_work_root
finetune._package_dir = _package_dir
finetune.get_weight_finetune_capability = get_weight_finetune_capability_configured
finetune.start_weight_finetune_job = start_weight_finetune_job_configured
