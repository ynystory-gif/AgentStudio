"""Backend-authoritative hard deadline for dynamic Theme import jobs.

v5.433 keeps the 5 minute (300 second) hard deadline, but also exposes an explicit
backend cleanup lifecycle. A timeout is not considered fully ended until the owning
Theme task has unwound and AgentStudio-owned worker processes are gone. Frontend and
Scheduler can therefore distinguish `FAILED + cleanup running` from `FAILED + backend
execution ended` instead of guessing from the terminal status alone.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

from app.api import ui_theme_dynamic_routes as routes
from app.services.ui_theme_killable_process_service import (
    active_theme_worker_pids,
    shutdown_theme_workers,
)

HARD_JOB_TIMEOUT_SECONDS = 300


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
    """Mark timeout immediately, while making cleanup progress explicit."""
    worker_pids = active_theme_worker_pids()
    job.update(
        cancel_requested=True,
        hard_timeout_triggered=True,
        hard_timeout_source=source,
        status="failed",
        stage="timeout_cleanup",
        progress=min(99, int(job.get("progress") or 0)),
        message=(
            "Backend 최대 분석시간 5분(300초)을 초과했습니다. 실패 처리 후 "
            "Theme Worker/실행 Task 종료를 확인하고 있습니다."
        ),
        error="Theme 통합 분석 Backend hard timeout (5분/300초 초과)",
        backend_cleanup_state="running",
        backend_cleanup_completed=False,
        backend_execution_active=True,
        backend_analysis_ended=False,
        backend_worker_pids=worker_pids,
        backend_worker_process_count=len(worker_pids),
        updated_at=datetime.utcnow().isoformat(),
    )


def _mark_cleanup_complete(job: dict, *, killed_count: int = 0, source: str = "finalizer") -> None:
    worker_pids = active_theme_worker_pids()
    ended_at = datetime.utcnow().isoformat()
    job.update(
        status="failed",
        stage="timeout",
        backend_cleanup_state="complete",
        backend_cleanup_completed=True,
        backend_execution_active=False,
        backend_analysis_ended=True,
        backend_cleanup_completed_at=ended_at,
        backend_terminated_at=ended_at,
        backend_worker_pids=worker_pids,
        backend_worker_process_count=len(worker_pids),
        backend_workers_killed=max(int(job.get("backend_workers_killed") or 0), int(killed_count or 0)),
        message=(
            "Backend 최대 분석시간 5분(300초)을 초과하여 Theme 분석을 실패 처리했습니다. "
            f"Backend 작업 종료 확인됨 · Worker Process {len(worker_pids)}개 남음."
        ),
        hard_timeout_source=str(job.get("hard_timeout_source") or source),
        updated_at=ended_at,
    )


async def _terminate_expired_job(job_id: str, *, source: str) -> bool:
    job = routes._DYNAMIC_IMPORT_JOBS.get(job_id)
    if not job:
        return False
    status = str(job.get("status") or "")
    if status not in {"queued", "running", "cancelling", "failed"}:
        return False
    if job.get("hard_timeout_triggered"):
        return False
    if _age_seconds(job) < HARD_JOB_TIMEOUT_SECONDS:
        return False

    _mark_hard_timeout(job, source=source)
    killed = 0
    try:
        killed = await shutdown_theme_workers()
        job["backend_workers_killed"] = int(killed or 0)
        job["backend_worker_pids"] = active_theme_worker_pids()
        job["backend_worker_process_count"] = len(job["backend_worker_pids"])
    finally:
        task = routes._DYNAMIC_IMPORT_TASKS.get(job_id)
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()
        elif not task or task.done():
            # No owning task remains, so cleanup can be declared complete here.
            _mark_cleanup_complete(job, killed_count=killed, source=source)
    return True


async def _snapshot_cleanup(job_id: str) -> None:
    """Best-effort cleanup when a status read is the first code path to detect expiry."""
    job = routes._DYNAMIC_IMPORT_JOBS.get(job_id)
    if not job:
        return
    killed = 0
    try:
        killed = await shutdown_theme_workers()
        task = routes._DYNAMIC_IMPORT_TASKS.get(job_id)
        if task and not task.done() and task is not asyncio.current_task():
            task.cancel()
            # The wrapped owner finalizer marks the authoritative completion state.
            return
    finally:
        task = routes._DYNAMIC_IMPORT_TASKS.get(job_id)
        if (not task or task.done()) and job.get("hard_timeout_triggered"):
            _mark_cleanup_complete(job, killed_count=killed, source="status_snapshot_cleanup")


def enforce_job_deadline(job_id: str) -> bool:
    """Synchronous status guard used by snapshots.

    The timeout failure is visible immediately, but the snapshot also reports whether
    backend cleanup is still running. Cleanup itself is scheduled on the event loop.
    """
    job = routes._DYNAMIC_IMPORT_JOBS.get(job_id)
    if not job:
        return False
    status = str(job.get("status") or "")
    if status not in {"queued", "running", "cancelling", "failed"}:
        return False
    if job.get("hard_timeout_triggered"):
        return False
    if _age_seconds(job) < HARD_JOB_TIMEOUT_SECONDS:
        return False

    _mark_hard_timeout(job, source="status_snapshot")
    task = routes._DYNAMIC_IMPORT_TASKS.get(job_id)
    if task and not task.done():
        task.cancel()
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_snapshot_cleanup(job_id))
    except RuntimeError:
        pass
    return True


_original_snapshot = routes._job_snapshot


def _deadline_snapshot(job: dict) -> dict:
    job_id = str(job.get("job_id") or "")
    if job_id:
        enforce_job_deadline(job_id)
    snapshot = _original_snapshot(job)
    worker_pids = active_theme_worker_pids()
    raw_status = str(snapshot.get("status") or "").lower()
    default_cleanup_state = "idle" if raw_status in {"queued", "running", "cancelling"} else "complete"
    cleanup_state = str(job.get("backend_cleanup_state") or default_cleanup_state)
    snapshot["backend_hard_timeout_seconds"] = HARD_JOB_TIMEOUT_SECONDS
    snapshot["backend_deadline_enforced"] = True
    snapshot["backend_watchdog_started"] = bool(job.get("backend_watchdog_started"))
    snapshot["backend_watchdog_started_at"] = str(job.get("backend_watchdog_started_at") or "")
    snapshot["backend_deadline_at"] = str(job.get("backend_deadline_at") or _deadline_iso(job))
    snapshot["job_age_seconds"] = _age_seconds(job)
    snapshot["hard_timeout_triggered"] = bool(job.get("hard_timeout_triggered"))
    snapshot["hard_timeout_source"] = str(job.get("hard_timeout_source") or "")
    snapshot["backend_cleanup_state"] = cleanup_state
    snapshot["backend_cleanup_completed"] = bool(job.get("backend_cleanup_completed"))
    snapshot["backend_execution_active"] = bool(job.get("backend_execution_active"))
    snapshot["backend_analysis_ended"] = bool(job.get("backend_analysis_ended"))
    snapshot["backend_cleanup_completed_at"] = str(job.get("backend_cleanup_completed_at") or "")
    snapshot["backend_terminated_at"] = str(job.get("backend_terminated_at") or "")
    snapshot["backend_workers_killed"] = int(job.get("backend_workers_killed") or 0)
    snapshot["active_theme_worker_pids"] = worker_pids
    snapshot["backend_worker_pids"] = worker_pids
    snapshot["backend_worker_process_count"] = len(worker_pids)
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
                backend_cleanup_state="idle",
                backend_cleanup_completed=False,
                backend_execution_active=True,
                backend_analysis_ended=False,
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
            backend_cleanup_state="idle",
            backend_cleanup_completed=False,
            backend_execution_active=True,
            backend_analysis_ended=False,
        )
    watchdog = asyncio.create_task(_independent_deadline_watchdog(job_id, owner))
    try:
        await _original_execute_job(job_id, req)
    finally:
        if not watchdog.done():
            watchdog.cancel()
        job = routes._DYNAMIC_IMPORT_JOBS.get(job_id)
        if job and not job.get("hard_timeout_triggered"):
            # asyncio.wait_for inside the legacy executor also reaches 300 seconds. If it
            # wins the race against the independent watchdog by a few milliseconds,
            # normalize that terminal timeout into the same authoritative hard-timeout
            # lifecycle instead of exposing two different kinds of 5-minute failure.
            timed_out = (
                str(job.get("status") or "").lower() == "failed"
                and str(job.get("stage") or "").lower() == "timeout"
                and _age_seconds(job) >= HARD_JOB_TIMEOUT_SECONDS - 1
            )
            if timed_out:
                _mark_hard_timeout(job, source="executor_wait_for")

        if job and job.get("hard_timeout_triggered"):
            # _original_execute_job catches CancelledError and can temporarily label the
            # request "cancelled". Reassert timeout only after the nested analysis stack
            # has unwound, then verify that no AgentStudio Theme worker remains.
            killed = 0
            try:
                killed = await shutdown_theme_workers()
            except Exception:
                pass
            _mark_cleanup_complete(job, killed_count=killed, source=str(job.get("hard_timeout_source") or "finalizer"))
        elif job:
            # Normal success/failure/cancel has also left the owning execution stack.
            worker_pids = active_theme_worker_pids()
            job.update(
                backend_cleanup_state="complete",
                backend_cleanup_completed=True,
                backend_execution_active=False,
                backend_analysis_ended=True,
                backend_cleanup_completed_at=datetime.utcnow().isoformat(),
                backend_terminated_at=datetime.utcnow().isoformat(),
                backend_worker_pids=worker_pids,
                backend_worker_process_count=len(worker_pids),
            )


routes._JOB_TIMEOUT_SECONDS = HARD_JOB_TIMEOUT_SECONDS
routes._URL_ANALYSIS_TIMEOUT_SECONDS = HARD_JOB_TIMEOUT_SECONDS
routes._job_snapshot = _deadline_snapshot
routes._execute_job = _execute_job_with_backend_deadline
