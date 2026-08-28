from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.learning_collection_service import get_problem_collection_job
from app.services.learning_failure_log_service import attach_failure_log

router = APIRouter(prefix="/learning", tags=["LLM Learning Diagnostics"])


@router.get("/problems/collect-job/{job_id}")
async def problem_collection_job_with_diagnostics(job_id: str):
    try:
        job = await get_problem_collection_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return attach_failure_log(job, kind="problem_collection")
