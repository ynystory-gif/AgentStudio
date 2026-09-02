from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.learning_collection_service import get_problem_collection_job, start_problem_collection_job
from app.services.learning_failure_log_service import attach_failure_log
from app.services.learning_teacher_router import learning_teacher_priority
from app.services.active_ollama_model_service import sync_active_ollama_model

router = APIRouter(prefix="/learning", tags=["LLM Learning Diagnostics"])


class ProblemCollectionStartRequest(BaseModel):
    target_per_case: int = 100
    max_cases: int = 20
    # Kept only for backward compatibility. v5.426 ignores provider pinning and
    # uses AgentStudio's configured high-level provider priority.
    provider: str = "auto"


async def _sync_active_ollama_model() -> str:
    resolved = await sync_active_ollama_model()
    return str(resolved.get("active_model") or "")


@router.get("/teacher-policy")
async def teacher_policy():
    """Show the actual model priority used by learning problem collection."""
    policy = await learning_teacher_priority()
    return {"ok": True, **policy, "mode": "reuse_agentstudio_provider_priority"}


@router.post("/problems/collect-job")
async def start_problem_collection_with_runtime_model(req: ProblemCollectionStartRequest):
    try:
        current_model = await _sync_active_ollama_model()
        # The legacy provider value is intentionally not used by the patched
        # Dataset generator. It follows /learning/teacher-policy instead.
        job = await start_problem_collection_job(req.target_per_case, req.max_cases, "auto")
        if current_model:
            job["runtime_model"] = current_model
        job["teacher_policy"] = await learning_teacher_priority()
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
