from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.learning_apply_job_service import start_full_learning_apply_job

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
