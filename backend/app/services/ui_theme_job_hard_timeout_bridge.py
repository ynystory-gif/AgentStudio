"""Backend-authoritative hard deadline for dynamic Theme import jobs.

The frontend watchdog is only UX. This bridge attaches an independent backend watchdog
to every Theme import execution. At 180 seconds it marks the job terminal, kills all
AgentStudio-owned Theme worker process trees, cancels the owning asyncio task and then
reasserts the timeout state so the route's CancelledError handler cannot downgrade the
result to a normal user cancellation.
"""
from __future__ import annotations

import asyncio
from datetime import datetime

from app.api import ui_theme_dynamic_routes as routes
from app.services.ui_theme_killable_process_service import shutdown_theme_workers

HARD_JOB_TIMEOUT_SECONDS = 180


def _age_seconds(job: dict) -> int:
    try:
        created = datetime.fromisoformat(str(job.get("created_at") or ""))
        return max(0, int((datetime.utcnow() - created).total_seconds()))
    except Exception:
        return 0


def _mark_hard_timeout(job: dict) -> None:
    job.update(
        cancel_requested=True,
        hard_timeout_triggered=True,
        status="failed",
        stage="timeout",
        progress=min(99, int(job.get("progress") or 0)),
        message="Backend 전체 제한 3분을 초과하여 Theme 분석 작업과 Worker Process를 강제 종료했습니다.",
        error="Theme 통합 분석 Backend hard timeout",
        updated_at=datetime.utcnow().isoformat(),
    )


def enforce_job_deadline(job_id: str) -> bool:
    job = routes._DYNAMIC_IMPORT_JOBS.get(job_id)
    if not job:
        return False
    status = str(job.get("status") or "")
    if status not in {"queued", "running", "cancelling"}:
        return False
    if _age_seconds(job) < HARD_JOB_TIMEOUT_SECONDS:
        return False

    _mark_hard_timeout(job)
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
    snapshot["hard_timeout_triggered"] = bool(job.get("hard_timeout_triggered"))
    return snapshot


_original_execute_job = routes._execute_job


async def _independent_deadline_watchdog(job_id: str, owner_task: asyncio.Task | None) -> None:
    """Expire a Theme job even if no browser tab ever polls its status."""
    try:
        await asyncio.sleep(HARD_JOB_TIMEOUT_SECONDS)
        job = routes._DYNAMIC_IMPORT_JOBS.get(job_id)
        if not job:
            return
        if str(job.get("status") or "") not in {"queued", "running", "cancelling"}:
            return

        _mark_hard_timeout(job)
        # Theme imports are serialized by the UI in normal use. Kill every worker owned
        # by this Backend instance so stuck regex/Playwright/Node descendants cannot
        # keep Python alive after the job has expired.
        try:
            await shutdown_theme_workers()
        finally:
            if owner_task and not owner_task.done():
                owner_task.cancel()
    except asyncio.CancelledError:
        return


async def _execute_job_with_backend_deadline(job_id: str, req) -> None:
    owner = asyncio.current_task()
    watchdog = asyncio.create_task(_independent_deadline_watchdog(job_id, owner))
    try:
        await _original_execute_job(job_id, req)
    finally:
        if not watchdog.done():
            watchdog.cancel()
        job = routes._DYNAMIC_IMPORT_JOBS.get(job_id)
        if job and job.get("hard_timeout_triggered"):
            # _original_execute_job catches CancelledError and labels it "cancelled".
            # Reassert the authoritative backend timeout after that handler finishes.
            _mark_hard_timeout(job)
            try:
                await shutdown_theme_workers()
            except Exception:
                pass


routes._JOB_TIMEOUT_SECONDS = HARD_JOB_TIMEOUT_SECONDS
routes._URL_ANALYSIS_TIMEOUT_SECONDS = min(100, HARD_JOB_TIMEOUT_SECONDS - 20)
routes._job_snapshot = _deadline_snapshot
routes._execute_job = _execute_job_with_backend_deadline
