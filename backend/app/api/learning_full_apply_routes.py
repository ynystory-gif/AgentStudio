from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.learning_apply_job_service import start_full_learning_apply_job
# Must load before importing the fine-tune functions below. It binds QLoRA work/cache
# directories to System Admin's saved DEFAULT_TEMP_ROOT / DEFAULT_CACHE_ROOT values.
import app.services.learning_finetune_paths_bridge  # noqa: F401
# Reconcile legacy Dataset validation into normalized learning-problem rows and select
# the CUDA-capable AgentStudio Python/venv before API functions are bound.
import app.services.learning_finetune_readiness_bridge  # noqa: F401
# If NVIDIA hardware is present but no CUDA Torch is available, allow the job to bootstrap
# a private cu128 Torch runtime under the configured Cache path instead of blocking UI.
import app.services.learning_finetune_cuda_bootstrap_bridge  # noqa: F401
from app.services.learning_finetune_job_service import (
    get_weight_finetune_capability,
    get_weight_finetune_job,
    start_weight_finetune_job,
)
from app.services.learning_weight_model_status_service import get_active_weight_model_status

router = APIRouter(prefix="/learning", tags=["LLM Learning"])


@router.post("/full-learning-apply-job")
async def full_learning_apply_job():
    """Rebuild the prompt/curriculum model only while no merged weight model is active."""
    try:
        weight_state = await get_active_weight_model_status()
        if weight_state.get("weight_model_active"):
            raise ValueError(
                "현재 PC는 실제 QLoRA 가중치가 Merge된 theanova-learn:latest를 사용 중입니다. "
                "기존 '모두 학습 적용'은 이 독립 모델을 덮어쓸 수 있으므로 차단했습니다. "
                "새 Dataset은 '독립 모델 재학습'으로 반영하세요."
            )
        return await start_full_learning_apply_job()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc) or type(exc).__name__) from exc


@router.get("/weight-finetune/capability")
async def weight_finetune_capability():
    """GPU/Dataset/disk/Ollama readiness plus current independent-model state."""
    try:
        capability = await get_weight_finetune_capability()
        weight_state = await get_active_weight_model_status()
        return {**capability, **weight_state}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc) or type(exc).__name__) from exc


@router.post("/weight-finetune/jobs")
async def create_weight_finetune_job():
    """Start QLoRA -> merge -> quantize -> smoke test -> safe model promotion."""
    try:
        return await start_weight_finetune_job()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc) or type(exc).__name__) from exc


@router.get("/weight-finetune/jobs/{job_id}")
async def read_weight_finetune_job(job_id: str):
    try:
        return await get_weight_finetune_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc) or type(exc).__name__) from exc
