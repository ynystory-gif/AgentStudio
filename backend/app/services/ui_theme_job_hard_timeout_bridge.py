"""Backend-side hard deadline for dynamic Theme import jobs.

The frontend watchdog is only UX. This bridge makes the backend job state authoritative:
when a job exceeds its deadline, the asyncio task is cancelled and the job is moved to a
terminal timeout state even if the browser tab stops polling.
"""
from __future__ import annotations

import asyncio
from datetime import datetime

from app.api import ui_theme_dynamic_routes as routes

HARD_JOB_TIMEOUT_SECONDS = 180


def _age_seconds(job: dict) -> int:
    try:
        created = datetime.fromisoformat(str(job.get("created_at") or ""))
        return max(0, int((datetime.utcnow() - created).total_seconds()))
    except Exception:
        return 0


def enforce_job_deadline(job_id: str) -> bool:
    job = routes._DYNAMIC_IMPORT_JOBS.get(job_id)
    if not job:
        return False
    status = str(job.get("status") or "")
    if status not in {"queued", "running", "cancelling"}:
        return False
    if _age_seconds(job) < HARD_JOB_TIMEOUT_SECONDS:
        return False

    job.update(
        cancel_requested=True,
        status="failed",
        stage="timeout",
        progress=min(99, int(job.get("progress") or 0)),
        message="Backend 전체 제한 3분을 초과하여 Theme 분석 작업을 강제 종료했습니다.",
        error="Theme 통합 분석 Backend hard timeout",
        updated_at=datetime.utcnow().isoformat(),
    )
    task = routes._DYNAMIC_IMPORT_TASKS.get(job_id)
    if task and not task.done():
        task.cancel()
    return True


_original_snapshot = routes._job_snapshot


def _deadline_snapshot(job: dict) -> dict:
    job_id = str(job.get("job_id") or "")
    if job_id:
        enforce_job_deadline(job_id)
    snapshot = _original_snapshot(job)
    snapshot["backend_hard_timeout_seconds"] = HARD_JOB_TIMEOUT_SECONDS
    snapshot["backend_deadline_enforced"] = True
    return snapshot


routes._JOB_TIMEOUT_SECONDS = HARD_JOB_TIMEOUT_SECONDS
routes._URL_ANALYSIS_TIMEOUT_SECONDS = min(100, HARD_JOB_TIMEOUT_SECONDS - 20)
routes._job_snapshot = _deadline_snapshot
