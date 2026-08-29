from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.learning_finetune_job_service import (
    get_weight_finetune_capability,
    get_weight_finetune_job,
    start_weight_finetune_job,
)

router = APIRouter(prefix="/learning/weight-finetune", tags=["LLM Learning"])


@router.get("/capability")
async def weight_finetune_capability():
    """Return GPU/Dataset/disk/Ollama readiness for a true QLoRA training run."""
    try:
        return await get_weight_finetune_capability()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc) or type(exc).__name__) from exc


@router.post("/jobs")
async def create_weight_finetune_job():
    """Start QLoRA -> merge -> Ollama quantize/smoke-test/promote."""
    try:
        return await start_weight_finetune_job()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc) or type(exc).__name__) from exc


@router.get("/jobs/{job_id}")
async def read_weight_finetune_job(job_id: str):
    try:
        return await get_weight_finetune_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc) or type(exc).__name__) from exc
