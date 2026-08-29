from __future__ import annotations

"""Automatically bootstrap CUDA PyTorch into the configured fine-tune cache.

If NVIDIA hardware is visible but none of AgentStudio's Python candidates has a CUDA
Torch build, readiness remains usable and the actual job installs a CUDA 12.8 PyTorch
runtime into the fine-tune package directory under DEFAULT_CACHE_ROOT. The worker already
prepends that package directory to sys.path, so no system/AgentStudio venv is modified.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from app.services import learning_finetune_job_service as finetune


_ORIGINAL_CAPABILITY = finetune.get_weight_finetune_capability
_ORIGINAL_INSTALL_RUNTIME = finetune._install_finetune_runtime_sync
CUDA_TORCH_INDEX = "https://download.pytorch.org/whl/cu128"


def _python_for_bootstrap() -> str:
    configured = str(os.environ.get("AGENTSTUDIO_FINETUNE_PYTHON") or "").strip()
    if configured and Path(configured).exists():
        return configured
    return sys.executable


def _probe_cached_cuda(python_exe: str) -> dict:
    package_dir = finetune._package_dir()
    code = (
        "import json,sys\n"
        f"sys.path.insert(0, {str(package_dir)!r})\n"
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
            [python_exe, "-c", code],
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
        result = json.loads(lines[-1]) if lines else {"ok": False, "error": "CUDA cache probe output is empty"}
        result["python"] = python_exe
        result["package_dir"] = str(package_dir)
        return result
    except Exception as exc:
        return {"ok": False, "python": python_exe, "package_dir": str(package_dir), "error": str(exc)}


def _install_cuda_torch(job_id: str, python_exe: str) -> None:
    target = finetune._package_dir()
    probe = _probe_cached_cuda(python_exe)
    if probe.get("ok"):
        finetune._append_log(job_id, f"CUDA PyTorch 캐시 확인 완료 · torch {probe.get('torch')} / CUDA {probe.get('cuda')}")
        return

    finetune._append_log(job_id, f"CUDA PyTorch 자동 준비 시작 · {target}")
    command = [
        python_exe,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--target",
        str(target),
        "--index-url",
        CUDA_TORCH_INDEX,
        "torch",
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=os.environ.copy(),
    )
    if process.stdout is None:
        raise RuntimeError("CUDA PyTorch 설치 출력을 읽을 수 없습니다.")
    for line in process.stdout:
        value = line.strip()
        if value:
            finetune._append_log(job_id, value)
    code = process.wait()
    if code != 0:
        raise RuntimeError(
            f"CUDA PyTorch 자동 설치 실패 (ExitCode={code}). "
            f"Cache={target}, Index={CUDA_TORCH_INDEX}"
        )

    probe = _probe_cached_cuda(python_exe)
    if not probe.get("ok"):
        raise RuntimeError(
            "CUDA PyTorch 설치는 완료됐지만 CUDA 사용 확인에 실패했습니다. "
            + str(probe.get("error") or "torch.cuda.is_available()=False")
        )
    finetune._append_log(
        job_id,
        f"CUDA PyTorch 준비 완료 · {probe.get('name')} · torch {probe.get('torch')} / CUDA {probe.get('cuda')}",
    )


def _install_runtime_with_cuda_bootstrap(job_id: str) -> None:
    python_exe = _python_for_bootstrap()
    os.environ["AGENTSTUDIO_FINETUNE_PYTHON"] = python_exe
    _install_cuda_torch(job_id, python_exe)
    _ORIGINAL_INSTALL_RUNTIME(job_id)


async def _capability_allowing_cuda_bootstrap() -> dict:
    result = await _ORIGINAL_CAPABILITY()
    python_exe = _python_for_bootstrap()
    cached = _probe_cached_cuda(python_exe)

    if cached.get("ok"):
        reasons = [
            str(value) for value in list(result.get("reasons") or [])
            if not str(value).startswith("NVIDIA GPU는 감지되지만")
            and not str(value).startswith("CUDA GPU를 사용할 수 없습니다")
            and not str(value).startswith("GPU VRAM이 부족합니다")
        ]
        memory = float(cached.get("memory_gb") or result.get("gpu_memory_gb") or 0.0)
        if memory < 6.0:
            reasons.insert(0, f"GPU VRAM이 부족합니다. 현재 {memory}GB, 권장 6GB 이상")
        result.update({
            "ready": not reasons,
            "reasons": reasons,
            "cuda_available": True,
            "gpu_name": str(cached.get("name") or result.get("gpu_name") or ""),
            "gpu_memory_gb": memory,
            "torch_version": str(cached.get("torch") or ""),
            "torch_cuda_version": str(cached.get("cuda") or ""),
            "finetune_python": python_exe,
            "cuda_runtime_bootstrap_required": False,
            "cuda_runtime_package_dir": str(finetune._package_dir()),
        })
        return result

    # NVIDIA is visible: lack of a CUDA Torch wheel is recoverable because the job can
    # install it in G:\Cache (or the configured DEFAULT_CACHE_ROOT) after confirmation.
    if bool(result.get("nvidia_gpu_detected")):
        reasons = [
            str(value) for value in list(result.get("reasons") or [])
            if not str(value).startswith("NVIDIA GPU는 감지되지만")
            and not str(value).startswith("CUDA GPU를 사용할 수 없습니다")
            and not str(value).startswith("GPU VRAM이 부족합니다")
        ]
        memory = float(result.get("gpu_memory_gb") or 0.0)
        if memory and memory < 6.0:
            reasons.insert(0, f"GPU VRAM이 부족합니다. 현재 {memory}GB, 권장 6GB 이상")
        result.update({
            "ready": not reasons,
            "reasons": reasons,
            "finetune_python": python_exe,
            "cuda_runtime_bootstrap_required": True,
            "cuda_runtime_package_dir": str(finetune._package_dir()),
            "cuda_runtime_note": "파인튜닝 시작 시 Cache 경로에 CUDA PyTorch(cu128)를 자동 설치합니다.",
        })
    return result


finetune._install_finetune_runtime_sync = _install_runtime_with_cuda_bootstrap
finetune.get_weight_finetune_capability = _capability_allowing_cuda_bootstrap
