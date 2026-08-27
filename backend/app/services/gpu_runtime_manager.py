from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from app.core.config import get_settings


def _runtime_dir() -> Path:
    if os.name == "nt":
        local = str(os.getenv("LOCALAPPDATA") or "").strip()
        if local:
            return Path(local) / "THEANOVA" / "AgentStudio" / "runtime"
    return Path(__file__).resolve().parents[2] / "logs" / "gpu_runtime"


STATE_FILE = _runtime_dir() / "gpu_runtime.json"


def _read_state() -> dict:
    try:
        if STATE_FILE.exists():
            raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
    except Exception:
        pass
    return {}


def _write_state(enabled: bool) -> dict:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "enabled": bool(enabled),
        "updated_at": datetime.now().isoformat(),
        "owner": "THEANOVA AgentStudio",
    }
    STATE_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _nvidia_smi_path() -> str:
    found = shutil.which("nvidia-smi")
    if found:
        return found
    if os.name == "nt":
        candidate = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32" / "nvidia-smi.exe"
        if candidate.exists():
            return str(candidate)
    return ""


def _query_nvidia() -> list[dict]:
    exe = _nvidia_smi_path()
    if not exe:
        return []
    try:
        completed = subprocess.run(
            [
                exe,
                "--query-gpu=index,name,memory.total,memory.used,utilization.gpu,driver_version",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=4,
        )
        if completed.returncode != 0:
            return []
        rows: list[dict] = []
        for raw in (completed.stdout or "").splitlines():
            parts = [part.strip() for part in raw.split(",")]
            if len(parts) < 6:
                continue
            rows.append(
                {
                    "index": int(parts[0]) if parts[0].isdigit() else parts[0],
                    "name": parts[1],
                    "memory_total_mb": int(float(parts[2])) if parts[2] else 0,
                    "memory_used_mb": int(float(parts[3])) if parts[3] else 0,
                    "utilization_percent": int(float(parts[4])) if parts[4] else 0,
                    "driver_version": parts[5],
                }
            )
        return rows
    except Exception:
        return []


def gpu_runtime_enabled() -> bool:
    state = _read_state()
    if "enabled" in state:
        return bool(state.get("enabled"))
    # Preserve the historical AgentStudio behaviour: when a supported local GPU
    # exists, acceleration is available by default until the user explicitly
    # presses "GPU 정지".
    return bool(_query_nvidia())


def gpu_runtime_environment(base_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(base_env or os.environ)
    if gpu_runtime_enabled():
        # A previous CPU-only launch may have inherited these flags. Remove them
        # so CUDA-capable runtimes can discover the device again.
        for key in ("CUDA_VISIBLE_DEVICES", "HIP_VISIBLE_DEVICES", "ROCR_VISIBLE_DEVICES"):
            if env.get(key) == "-1":
                env.pop(key, None)
        env["AGENTSTUDIO_GPU_ACCELERATION"] = "1"
    else:
        # Widely respected by CUDA/ROCm-aware Python runtimes and Ollama child
        # processes. This does not power off the physical GPU; it disables GPU
        # acceleration for AgentStudio-managed workloads.
        env["CUDA_VISIBLE_DEVICES"] = "-1"
        env["HIP_VISIBLE_DEVICES"] = "-1"
        env["ROCR_VISIBLE_DEVICES"] = "-1"
        env["AGENTSTUDIO_GPU_ACCELERATION"] = "0"
    return env


def get_gpu_runtime_status() -> dict:
    devices = _query_nvidia()
    available = bool(devices)
    enabled = gpu_runtime_enabled() if available else False
    state = _read_state()
    return {
        "ok": True,
        "available": available,
        "enabled": enabled,
        "mode": "gpu" if enabled else "cpu",
        "vendor": "NVIDIA" if available else "",
        "devices": devices,
        "device_count": len(devices),
        "nvidia_smi": _nvidia_smi_path(),
        "state_file": str(STATE_FILE),
        "updated_at": str(state.get("updated_at") or ""),
        "message": (
            "AgentStudio GPU 가속이 활성화되어 있습니다."
            if enabled
            else "GPU는 감지되었지만 AgentStudio GPU 가속이 정지되어 있습니다."
            if available
            else "지원되는 NVIDIA GPU를 감지하지 못했습니다."
        ),
        "note": "GPU 시작/정지는 물리 GPU 전원을 켜고 끄는 기능이 아니라 AgentStudio 관리 작업의 GPU 가속 사용 여부를 제어합니다.",
    }


def set_gpu_runtime_enabled(enabled: bool) -> dict:
    devices = _query_nvidia()
    if enabled and not devices:
        return {
            **get_gpu_runtime_status(),
            "ok": False,
            "message": "GPU 가속을 시작할 수 없습니다. 지원되는 NVIDIA GPU/드라이버를 확인하세요.",
        }
    _write_state(bool(enabled))
    return get_gpu_runtime_status()


def gpu_recommendation(*, request: str = "", confirmed_requirements: dict | None = None, ai_mode: str = "", phase: str = "") -> dict:
    """Return whether GPU acceleration is recommended for the requested action.

    Recommendation is deliberately narrow: Ollama-only local inference, local
    embeddings, or image/video AI workloads. It never makes GPU a hard system
    requirement; callers may still explicitly continue on CPU when no GPU is
    available.
    """
    confirmed = confirmed_requirements if isinstance(confirmed_requirements, dict) else {}
    blob = "\n".join(
        [
            str(request or ""),
            json.dumps(confirmed, ensure_ascii=False, default=str),
        ]
    ).casefold()

    reasons: list[str] = []
    mode = str(ai_mode or "").strip().casefold()

    # Explicit UI Ollama mode means the current design/development request is
    # intentionally local-only even when OpenAI credentials remain configured.
    settings = get_settings()
    if mode == "ollama" or (not settings.openai_enabled and not settings.codex_enabled):
        reasons.append("Ollama 로컬 LLM 전용 모드")

    local_embedding_terms = (
        "local embedding",
        "local embeddings",
        "로컬 embedding",
        "로컬 임베딩",
        "sentence-transformers",
        "sentence transformer",
        "huggingface embedding",
        "허깅페이스 임베딩",
    )
    if any(term in blob for term in local_embedding_terms) or any(
        term in blob
        for term in (
            "ollama embedding", "ollama embeddings", "ollama 임베딩",
            "nomic-embed", "bge-m3", "bge-small", "bge-base", "e5-small", "e5-base",
        )
    ):
        reasons.append("로컬 Embedding 모델 사용")

    media_terms = (
        "image generation", "image agent", "image analysis", "image classification",
        "object detection", "computer vision", "vision model",
        "video generation", "video agent", "video analysis", "video processing",
        "이미지 생성", "이미지 분석", "이미지 분류", "객체 탐지", "비전 모델",
        "이미지 agent", "이미지 에이전트",
        "영상 생성", "영상 분석", "영상 처리", "비디오 생성", "비디오 분석",
        "영상 agent", "영상 에이전트",
        "comfyui", "stable diffusion", "flux",
    )
    if any(term in blob for term in media_terms):
        reasons.append("이미지/영상 AI Agent 테스트")

    # A selected local embedding Provider is also a local model workload. This
    # is checked by the frontend's current runtime configuration and may be sent
    # explicitly in confirmed_requirements.
    embedding_provider = str(
        confirmed.get("embedding_provider")
        or (confirmed.get("llm") or {}).get("embedding_provider")
        or ""
    ).casefold()
    if embedding_provider in {"ollama", "local", "huggingface", "sentence_transformers"}:
        if "로컬 Embedding 모델 사용" not in reasons:
            reasons.append("로컬 Embedding 모델 사용")

    status = get_gpu_runtime_status()
    return {
        "ok": True,
        "recommended": bool(reasons),
        "reasons": reasons,
        "phase": str(phase or ""),
        "gpu": status,
    }
