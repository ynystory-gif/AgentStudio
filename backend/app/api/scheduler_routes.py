from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app.api import ui_theme_dynamic_routes
from app.services.job_manager import job_manager

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])

_ACTIVE_JOB_STATUSES = {"QUEUED", "PENDING", "RUNNING", "WAITING_USER"}
_ACTIVE_THEME_STATUSES = {"QUEUED", "RUNNING", "CANCELLING"}


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _normalize_agent_job(job) -> dict:
    status = str(getattr(job, "status", "") or "").upper()
    job_id = str(getattr(job, "id", "") or "")
    task = job_manager.tasks.get(job_id)
    active = status in _ACTIVE_JOB_STATUSES
    return {
        "id": job_id,
        "source": "AGENT_JOB",
        "source_label": "AgentStudio Background Job",
        "kind": str(getattr(job, "kind", "") or "BACKGROUND"),
        "status": status,
        "progress": int(getattr(job, "progress", 0) or 0),
        "stage": str(getattr(job, "last_node", "") or ""),
        "message": str(getattr(job, "message", "") or ""),
        "created_at": str(getattr(job, "created_at", "") or ""),
        "updated_at": str(getattr(job, "updated_at", "") or ""),
        "active": active,
        "can_cancel": bool(active and task is not None and not task.done()),
    }


def _normalize_theme_job(snapshot: dict) -> dict:
    status = str(snapshot.get("status") or "").upper()
    backend_execution_active = bool(snapshot.get("backend_execution_active"))
    active = status in _ACTIVE_THEME_STATUSES or backend_execution_active
    return {
        "id": str(snapshot.get("job_id") or ""),
        "source": "UI_THEME",
        "source_label": "UI / Layout Theme Analyzer",
        "kind": "UI_THEME_ANALYSIS",
        "status": status,
        "progress": int(snapshot.get("progress") or 0),
        "stage": str(snapshot.get("stage") or ""),
        "message": str(snapshot.get("message") or ""),
        "created_at": str(snapshot.get("created_at") or ""),
        "updated_at": str(snapshot.get("updated_at") or ""),
        "active": active,
        "can_cancel": bool(snapshot.get("can_cancel")) and status in _ACTIVE_THEME_STATUSES,
        "hard_timeout_triggered": bool(snapshot.get("hard_timeout_triggered")),
        "backend_cleanup_state": str(snapshot.get("backend_cleanup_state") or ""),
        "backend_cleanup_completed": bool(snapshot.get("backend_cleanup_completed")),
        "backend_execution_active": backend_execution_active,
        "backend_analysis_ended": bool(snapshot.get("backend_analysis_ended")),
        "backend_terminated_at": str(snapshot.get("backend_terminated_at") or ""),
        "backend_worker_process_count": int(snapshot.get("backend_worker_process_count") or 0),
    }


def _all_scheduler_rows() -> list[dict]:
    rows = [_normalize_agent_job(job) for job in job_manager.jobs.values()]
    rows.extend(
        _normalize_theme_job(snapshot)
        for snapshot in ui_theme_dynamic_routes.list_dynamic_import_job_snapshots()
    )
    rows.sort(
        key=lambda row: (
            1 if row.get("active") else 0,
            str(row.get("updated_at") or row.get("created_at") or ""),
        ),
        reverse=True,
    )
    return rows


def _summary(rows: list[dict]) -> dict:
    def count(*statuses: str) -> int:
        wanted = {value.upper() for value in statuses}
        return sum(1 for row in rows if str(row.get("status") or "").upper() in wanted)

    return {
        "total": len(rows),
        "active": sum(1 for row in rows if row.get("active")),
        "running": count("RUNNING"),
        "queued": count("QUEUED", "PENDING", "WAITING_USER"),
        "cancelling": count("CANCELLING"),
        "success": count("SUCCESS", "COMPLETED"),
        "failed": count("FAILED", "ERROR"),
        "cancelled": count("CANCELLED"),
    }


@router.get("/jobs")
async def scheduler_jobs(
    include_terminal: bool = Query(False),
    limit: int = Query(100, ge=1, le=500),
):
    all_rows = _all_scheduler_rows()
    visible = all_rows if include_terminal else [row for row in all_rows if row.get("active")]
    return {
        "ok": True,
        "generated_at": _now_iso(),
        "include_terminal": include_terminal,
        "summary": _summary(all_rows),
        "jobs": visible[:limit],
    }


@router.post("/jobs/{source}/{job_id}/cancel")
async def cancel_scheduler_job(source: str, job_id: str):
    source_key = str(source or "").strip().upper()
    job_key = str(job_id or "").strip()
    if not job_key:
        raise HTTPException(status_code=422, detail="취소할 Scheduler 작업 ID가 없습니다.")

    if source_key == "AGENT_JOB":
        job = job_manager.jobs.get(job_key)
        if not job:
            raise HTTPException(status_code=404, detail="Background Job을 찾을 수 없습니다.")
        status = str(job.status or "").upper()
        if status not in _ACTIVE_JOB_STATUSES:
            return {"ok": True, "cancelled": False, "job": _normalize_agent_job(job)}
        cancelled = await job_manager.cancel(job_key)
        # asyncio cancellation is delivered on the next event-loop turn. Return the
        # current row immediately; Scheduler polling will show CANCELLED afterwards.
        return {"ok": True, "cancelled": bool(cancelled), "job": _normalize_agent_job(job)}

    if source_key == "UI_THEME":
        snapshot = await ui_theme_dynamic_routes.cancel_ui_theme_dynamic_import_job(job_key)
        return {"ok": True, "cancelled": True, "job": _normalize_theme_job(snapshot)}

    raise HTTPException(status_code=404, detail=f"지원하지 않는 Scheduler 작업 유형입니다: {source_key}")
