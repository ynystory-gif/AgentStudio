from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.learning_apply_job_service import start_full_learning_apply_job
from app.services.learning_finetune_job_service import (
    get_weight_finetune_capability,
    get_weight_finetune_job,
    start_weight_finetune_job,
)

router = APIRouter(prefix="/learning", tags=["LLM Learning"])


@router.post("/full-learning-apply-job")
async def full_learning_apply_job():
    """Rebuild the single current-PC cumulative model from every usable shared Dataset."""
    try:
        return await start_full_learning_apply_job()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc) or type(exc).__name__) from exc


@router.get("/weight-finetune/capability")
async def weight_finetune_capability():
    """GPU/Dataset/disk/Ollama readiness for a true QLoRA weight training run."""
    try:
        return await get_weight_finetune_capability()
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
