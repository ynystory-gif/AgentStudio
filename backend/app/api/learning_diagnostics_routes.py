from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.core.config import get_settings
from app.services.learning_collection_service import get_problem_collection_job, start_problem_collection_job
from app.services.learning_failure_log_service import attach_failure_log
from app.services.ollama_model_manager_service import get_recommended_model_status

router = APIRouter(prefix="/learning", tags=["LLM Learning Diagnostics"])


class ProblemCollectionStartRequest(BaseModel):
    target_per_case: int = 100
    max_cases: int = 20
    provider: str = "ollama"


async def _sync_active_ollama_model() -> str:
    status = await get_recommended_model_status()
    current_model = str(status.get("current_model") or "").strip()
    if current_model:
        os.environ["OLLAMA_MODEL"] = current_model
        get_settings.cache_clear()
    return current_model


@router.post("/problems/collect-job")
async def start_problem_collection_with_runtime_model(req: ProblemCollectionStartRequest):
    try:
        current_model = await _sync_active_ollama_model()
        job = await start_problem_collection_job(req.target_per_case, req.max_cases, req.provider)
        if current_model:
            job["runtime_model"] = current_model
        return job
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc) or type(exc).__name__) from exc


@router.get("/problems/collect-job/{job_id}")
async def problem_collection_job_with_diagnostics(job_id: str):
    try:
        job = await get_problem_collection_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return attach_failure_log(job, kind="problem_collection")
