"""Backend-authoritative hard deadline for dynamic Theme import jobs.

The frontend watchdog is only UX. This bridge attaches an independent backend watchdog
to every Theme import execution and also enforces the same deadline whenever the job
snapshot is requested. At 180 seconds it marks the job terminal, kills all AgentStudio-
owned Theme worker process trees, cancels the owning asyncio task and reasserts timeout
state so a CancelledError handler cannot downgrade it to a normal user cancellation.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from app.api import ui_theme_dynamic_routes as routes
from app.services.ui_theme_killable_process_service import (
    active_theme_worker_pids,
    shutdown_theme_workers,
)

HARD_JOB_TIMEOUT_SECONDS = 180


def _age_seconds(job: dict) -> int:
    try:
        created = datetime.fromisoformat(str(job.get("created_at") or ""))
        return max(0, int((datetime.utcnow() - created).total_seconds()))
    except Exception:
        return 0


def _deadline_iso(job: dict) -> str:
    try:
        created = datetime.fromisoformat(str(job.get("created_at") or ""))
        return (created + timedelta(seconds=HARD_JOB_TIMEOUT_SECONDS)).isoformat()
    except Exception:
        return ""


def _mark_hard_timeout(job: dict, *, source: str = "backend_watchdog") -> None:
    job.update(
        cancel_requested=True,
        hard_timeout_triggered=True,
        hard_timeout_source=source,
        status="failed",
        stage="timeout",
        progress=min(99, int(job.get("progress") or 0)),
        message="Backend 전체 제한 3분을 초과하여 Theme 분석 작업과 Worker Process를 강제 종료했습니다.",
        error="Theme 통합 분석 Backend hard timeout",
        updated_at=datetime.utcnow().isoformat(),
    )


async def _terminate_expired_job(job_id: str, *, source: str) -> bool:
    job = routes._DYNAMIC_IMPORT_JOBS.get(job_id)
    if not job:
        return False
    status = str(job.get("status") or "")
    if status not in {"queued", "running", "cancelling"}:
        return False
    if _age_seconds(job) < HARD_JOB_TIMEOUT_SECONDS:
        return False

    _mark_hard_timeout(job, source=source)
    try:
        await shutdown_theme_workers()
    finally:
        task = routes._DYNAMIC_IMPORT_TASKS.get(job_id)
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()
    return True


def enforce_job_deadline(job_id: str) -> bool:
    """Synchronous status guard used by snapshots.

    The terminal state is set immediately. Process cleanup is scheduled on the running
    event loop so a status GET cannot block while Windows taskkill waits on descendants.
    """
    job = routes._DYNAMIC_IMPORT_JOBS.get(job_id)
    if not job:
        return False
    status = str(job.get("status") or "")
    if status not in {"queued", "running", "cancelling"}:
        return False
    if _age_seconds(job) < HARD_JOB_TIMEOUT_SECONDS:
        return False

    _mark_hard_timeout(job, source="status_snapshot")
    task = routes._DYNAMIC_IMPORT_TASKS.get(job_id)
    if task and not task.done():
        task.cancel()
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(shutdown_theme_workers())
    except RuntimeError:
        pass
    return True


_original_snapshot = routes._job_snapshot


def _deadline_snapshot(job: dict) -> dict:
    job_id = str(job.get("job_id") or "")
    if job_id:
        enforce_job_deadline(job_id)
    snapshot = _original_snapshot(job)
    snapshot["backend_hard_timeout_seconds"] = HARD_JOB_TIMEOUT_SECONDS
    snapshot["backend_deadline_enforced"] = True
    snapshot["backend_watchdog_started"] = bool(job.get("backend_watchdog_started"))
    snapshot["backend_watchdog_started_at"] = str(job.get("backend_watchdog_started_at") or "")
    snapshot["backend_deadline_at"] = str(job.get("backend_deadline_at") or _deadline_iso(job))
    snapshot["job_age_seconds"] = _age_seconds(job)
    snapshot["hard_timeout_triggered"] = bool(job.get("hard_timeout_triggered"))
    snapshot["hard_timeout_source"] = str(job.get("hard_timeout_source") or "")
    snapshot["active_theme_worker_pids"] = active_theme_worker_pids()
    return snapshot


_original_execute_job = routes._execute_job


async def _independent_deadline_watchdog(job_id: str, owner_task: asyncio.Task | None) -> None:
    """Expire a Theme job even if no browser tab ever polls its status."""
    try:
        job = routes._DYNAMIC_IMPORT_JOBS.get(job_id)
        if job:
            job.update(
                backend_watchdog_started=True,
                backend_watchdog_started_at=datetime.utcnow().isoformat(),
                backend_deadline_at=_deadline_iso(job),
            )
        await asyncio.sleep(HARD_JOB_TIMEOUT_SECONDS)
        expired = await _terminate_expired_job(job_id, source="independent_watchdog")
        if expired and owner_task and not owner_task.done():
            owner_task.cancel()
    except asyncio.CancelledError:
        return


async def _execute_job_with_backend_deadline(job_id: str, req) -> None:
    owner = asyncio.current_task()
    job = routes._DYNAMIC_IMPORT_JOBS.get(job_id)
    if job:
        job.update(
            backend_watchdog_started=True,
            backend_watchdog_started_at=datetime.utcnow().isoformat(),
            backend_deadline_at=_deadline_iso(job),
        )
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
            _mark_hard_timeout(job, source=str(job.get("hard_timeout_source") or "finalizer"))
            try:
                await shutdown_theme_workers()
            except Exception:
                pass


routes._JOB_TIMEOUT_SECONDS = HARD_JOB_TIMEOUT_SECONDS
routes._URL_ANALYSIS_TIMEOUT_SECONDS = min(100, HARD_JOB_TIMEOUT_SECONDS - 20)
routes._job_snapshot = _deadline_snapshot
routes._execute_job = _execute_job_with_backend_deadline
