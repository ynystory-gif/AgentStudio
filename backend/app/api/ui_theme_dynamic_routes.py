from __future__ import annotations

import asyncio
import uuid
from datetime import datetime
from typing import Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.database import SessionLocal
from app.core.machine_identity import current_pc_name
from app.models.entities import UITheme
from app.services.ui_theme_layout_contract_service import analyze_theme_with_layout_contract
from app.services.ui_theme_service import build_rules, merge_theme_analyses

router = APIRouter(prefix="/ui-themes", tags=["UI Theme Dynamic Import"])


class DynamicThemeImageReference(BaseModel):
    file_name: str = ""
    reference_role: str = "default"
    tokens: dict = Field(default_factory=dict)
    component_rules: dict = Field(default_factory=dict)
    layout_rules: dict = Field(default_factory=dict)
    preview_colors: list[str] = Field(default_factory=list)


class DynamicThemeImportRequest(BaseModel):
    name: str = ""
    urls: list[str] = Field(default_factory=list)
    images: list[DynamicThemeImageReference] = Field(default_factory=list)
    scope: str = "GLOBAL"


# Theme import jobs are intentionally in-memory. They exist to provide live UX
# feedback and are not expected to survive an AgentStudio restart.
_DYNAMIC_IMPORT_JOBS: dict[str, dict] = {}
_DYNAMIC_IMPORT_TASKS: dict[str, asyncio.Task] = {}
_JOB_LIMIT = 50
_JOB_TIMEOUT_SECONDS = 300
_URL_ANALYSIS_TIMEOUT_SECONDS = _JOB_TIMEOUT_SECONDS
_STALL_WARNING_SECONDS = 60


def _utcnow_iso() -> str:
    return datetime.utcnow().isoformat()


def _seconds_since(value: str | None) -> int:
    if not value:
        return 0
    try:
        stamp = datetime.fromisoformat(value)
        return max(0, int((datetime.utcnow() - stamp).total_seconds()))
    except Exception:
        return 0


def _job_snapshot(job: dict) -> dict:
    stalled_seconds = _seconds_since(str(job.get("updated_at") or ""))
    status = str(job.get("status") or "")
    active = status in {"queued", "running", "cancelling"}
    return {
        "job_id": job.get("job_id"),
        "status": status,
        "progress": int(job.get("progress") or 0),
        "stage": job.get("stage") or "",
        "message": job.get("message") or "",
        "current": int(job.get("current") or 0),
        "total": int(job.get("total") or 0),
        "result": job.get("result"),
        "error": job.get("error"),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
        "stalled_seconds": stalled_seconds,
        "stalled": bool(active and stalled_seconds >= _STALL_WARNING_SECONDS),
        "stall_warning_seconds": _STALL_WARNING_SECONDS,
        "url_timeout_seconds": _URL_ANALYSIS_TIMEOUT_SECONDS,
        "job_timeout_seconds": _JOB_TIMEOUT_SECONDS,
        "cancel_requested": bool(job.get("cancel_requested")),
        "can_cancel": active and not bool(job.get("cancel_requested")),
    }


def list_dynamic_import_job_snapshots() -> list[dict]:
    """Return live/recent Theme jobs for the AgentStudio Scheduler workspace."""
    _prune_jobs()
    return [_job_snapshot(job) for job in _DYNAMIC_IMPORT_JOBS.values()]


def _prune_jobs() -> None:
    if len(_DYNAMIC_IMPORT_JOBS) <= _JOB_LIMIT:
        return
    completed = sorted(
        (
            item
            for item in _DYNAMIC_IMPORT_JOBS.values()
            if item.get("status") in {"completed", "failed", "cancelled"}
        ),
        key=lambda item: str(item.get("updated_at") or ""),
    )
    while len(_DYNAMIC_IMPORT_JOBS) > _JOB_LIMIT and completed:
        old = completed.pop(0)
        job_id = str(old.get("job_id") or "")
        _DYNAMIC_IMPORT_JOBS.pop(job_id, None)
        _DYNAMIC_IMPORT_TASKS.pop(job_id, None)


def _image_analysis(item: DynamicThemeImageReference) -> dict:
    tokens = dict(item.tokens or {})
    components = dict(item.component_rules or {})
    layout = dict(item.layout_rules or {})
    if not components or not layout:
        inferred_components, inferred_layout = build_rules(tokens)
        if not components:
            components = inferred_components
        if not layout:
            layout = inferred_layout
    return {
        "tokens": tokens,
        "component_rules": components,
        "layout_rules": layout,
        "preview_colors": list(item.preview_colors or []),
        "source_type": "IMAGE",
        "source_label": item.file_name,
        "file_name": item.file_name,
        "reference_role": item.reference_role or "default",
        "analysis_source": "IMAGE",
    }


def _prepare_request(req: DynamicThemeImportRequest) -> tuple[str, list[str], list[DynamicThemeImageReference]]:
    name = str(req.name or "").strip()
    if not name:
        raise ValueError("Theme 이름을 입력하세요.")

    urls: list[str] = []
    for raw in req.urls or []:
        value = str(raw or "").strip()
        if value and value not in urls:
            urls.append(value)
    if len(urls) > 20:
        raise ValueError("웹사이트 URL은 한 번에 최대 20개까지 분석할 수 있습니다.")

    images = list(req.images or [])
    if len(images) > 20:
        raise ValueError("화면 캡처 이미지는 한 번에 최대 20개까지 분석할 수 있습니다.")
    if not urls and not images:
        raise ValueError("웹사이트 URL 또는 화면 캡처 이미지를 하나 이상 추가하세요.")
    return name, urls, images


async def _run_dynamic_import(
    req: DynamicThemeImportRequest,
    progress: Callable[..., None] | None = None,
) -> dict:
    def report(value: int, stage: str, message: str, *, current: int = 0, total: int = 0) -> None:
        if progress:
            progress(value, stage, message, current=current, total=total)

    name, urls, images = _prepare_request(req)
    total_sources = len(urls) + len(images)
    report(5, "prepare", "참고 자료를 확인하고 있습니다.", total=total_sources)

    analyses: list[dict] = []
    warnings: list[str] = []
    url_count = len(urls)
    for index, url in enumerate(urls, start=1):
        start = 8
        span = 57
        before = start + int(span * (index - 1) / max(1, url_count))
        report(
            before,
            "url_analysis",
            f"웹사이트 분석 중 {index}/{url_count} · {url}",
            current=index,
            total=url_count,
        )
        try:
            # v5.429: no shorter per-URL elapsed-time cutoff. The whole import job has
            # one backend-authoritative 5-minute hard deadline. Cancellation at that
            # deadline propagates into killable Theme workers and browser cleanup.
            analysis = await analyze_theme_with_layout_contract(url)
            analyses.append(analysis)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            warnings.append(f"URL {index} 분석 실패: {url} · {str(exc) or type(exc).__name__}")
        after = start + int(span * index / max(1, url_count))
        report(
            after,
            "url_analysis",
            f"웹사이트 처리 완료 {index}/{url_count}",
            current=index,
            total=url_count,
        )

    report(
        68,
        "image_analysis",
        f"화면 캡처 분석 결과 {len(images)}개를 통합 준비 중입니다.",
        current=len(images),
        total=len(images),
    )
    for image in images:
        if image.tokens:
            analyses.append(_image_analysis(image))

    if not analyses:
        raise ValueError("추가한 참고 자료를 분석하지 못했습니다. " + " | ".join(warnings[:5]))

    report(76, "merge", "URL/이미지 분석 결과를 하나의 Layout + Theme 규칙으로 통합하고 있습니다.")
    merged = merge_theme_analyses(analyses)
    report(86, "rules", "컴포넌트 상태와 레이아웃 규칙을 정리하고 있습니다.")

    tokens = dict(merged.get("tokens") or {})
    component_rules = dict(merged.get("component_rules") or {})
    layout_rules = dict(merged.get("layout_rules") or {})
    preview_colors = list(merged.get("preview_colors") or [])
    if not component_rules or not layout_rules:
        inferred_components, inferred_layout = build_rules(tokens)
        component_rules = component_rules or inferred_components
        layout_rules = layout_rules or inferred_layout

    source_type = "COMBINED" if urls and images else ("URL" if urls else "IMAGE")
    source_parts = [
        *urls,
        *[str(item.file_name or "").strip() for item in images if str(item.file_name or "").strip()],
    ]
    now = datetime.utcnow()
    row = UITheme(
        pc_name=current_pc_name(),
        name=name,
        theme_type="IMPORTED",
        source_type=source_type,
        source_url="\n".join(urls),
        source_label=" · ".join(source_parts)[:1000],
        scope=str(req.scope or "GLOBAL").strip().upper() or "GLOBAL",
        tokens=tokens,
        component_rules=component_rules,
        layout_rules=layout_rules,
        preview_colors=preview_colors,
        created_at=now,
        updated_at=now,
    )
    report(92, "save", "통합 Theme을 데이터베이스에 저장하고 있습니다.")
    async with SessionLocal() as session:
        session.add(row)
        await session.commit()
        await session.refresh(row)

    report(99, "finalize", "저장 결과를 확인하고 있습니다.")
    return {
        "ok": True,
        "theme": {
            "id": row.id,
            "pc_name": row.pc_name,
            "name": row.name,
            "source_type": row.source_type,
            "source_url": row.source_url,
            "source_label": row.source_label,
            "scope": row.scope,
            "tokens": row.tokens or {},
            "component_rules": row.component_rules or {},
            "layout_rules": row.layout_rules or {},
            "preview_colors": row.preview_colors or [],
        },
        "url_count": len(urls),
        "image_count": len(images),
        "warnings": warnings,
        "message": f"URL {len(urls)}개 · 이미지 {len(images)}개 참고 자료를 통합 분석해 Theme을 저장했습니다.",
    }


async def _execute_job(job_id: str, req: DynamicThemeImportRequest) -> None:
    job = _DYNAMIC_IMPORT_JOBS.get(job_id)
    if not job:
        return

    def progress(value: int, stage: str, message: str, **extra) -> None:
        if job.get("cancel_requested"):
            raise asyncio.CancelledError()
        job.update(
            progress=max(int(job.get("progress") or 0), min(99, int(value))),
            stage=stage,
            message=message,
            updated_at=_utcnow_iso(),
            **extra,
        )

    try:
        job.update(
            status="running",
            stage="prepare",
            progress=2,
            message="통합 분석을 시작합니다.",
            updated_at=_utcnow_iso(),
        )
        result = await asyncio.wait_for(
            _run_dynamic_import(req, progress),
            timeout=_JOB_TIMEOUT_SECONDS,
        )
        if job.get("cancel_requested"):
            raise asyncio.CancelledError()
        job.update(
            status="completed",
            progress=100,
            stage="completed",
            message=result.get("message") or "Theme 저장이 완료되었습니다.",
            result=result,
            error=None,
            updated_at=_utcnow_iso(),
        )
    except asyncio.CancelledError:
        job.update(
            status="cancelled",
            stage="cancelled",
            message="사용자가 통합 분석 작업을 취소했습니다.",
            error=None,
            updated_at=_utcnow_iso(),
        )
    except asyncio.TimeoutError:
        job.update(
            status="failed",
            stage="timeout",
            message=f"전체 통합 분석 제한시간 {_JOB_TIMEOUT_SECONDS // 60}분을 초과하여 중단했습니다.",
            error="Theme 통합 분석 시간 초과",
            updated_at=_utcnow_iso(),
        )
    except Exception as exc:
        job.update(
            status="failed",
            stage="failed",
            message="통합 분석 저장에 실패했습니다.",
            error=str(exc) or type(exc).__name__,
            updated_at=_utcnow_iso(),
        )
    finally:
        _DYNAMIC_IMPORT_TASKS.pop(job_id, None)


@router.post("/import-dynamic/jobs")
async def start_ui_theme_dynamic_import_job(req: DynamicThemeImportRequest):
    try:
        _prepare_request(req)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _prune_jobs()
    job_id = uuid.uuid4().hex
    now = _utcnow_iso()
    _DYNAMIC_IMPORT_JOBS[job_id] = {
        "job_id": job_id,
        "status": "queued",
        "progress": 0,
        "stage": "queued",
        "message": "통합 분석 작업을 준비하고 있습니다.",
        "current": 0,
        "total": len(req.urls or []) + len(req.images or []),
        "result": None,
        "error": None,
        "cancel_requested": False,
        "created_at": now,
        "updated_at": now,
    }
    task = asyncio.create_task(_execute_job(job_id, req))
    _DYNAMIC_IMPORT_TASKS[job_id] = task
    return _job_snapshot(_DYNAMIC_IMPORT_JOBS[job_id])


@router.get("/import-dynamic/jobs/{job_id}")
async def get_ui_theme_dynamic_import_job(job_id: str):
    job = _DYNAMIC_IMPORT_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Theme 통합 분석 작업을 찾을 수 없습니다.")
    return _job_snapshot(job)


@router.post("/import-dynamic/jobs/{job_id}/cancel")
async def cancel_ui_theme_dynamic_import_job(job_id: str):
    job = _DYNAMIC_IMPORT_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Theme 통합 분석 작업을 찾을 수 없습니다.")
    status = str(job.get("status") or "")
    if status in {"completed", "failed", "cancelled"}:
        return _job_snapshot(job)
    job.update(
        cancel_requested=True,
        status="cancelling",
        stage="cancelling",
        message="작업 취소 요청을 처리하고 있습니다.",
        updated_at=_utcnow_iso(),
    )
    task = _DYNAMIC_IMPORT_TASKS.get(job_id)
    if task and not task.done():
        task.cancel()
    return _job_snapshot(job)


@router.post("/import-dynamic")
async def import_ui_theme_dynamic(req: DynamicThemeImportRequest):
    """Compatibility endpoint for older frontend builds."""
    try:
        return await asyncio.wait_for(_run_dynamic_import(req), timeout=_JOB_TIMEOUT_SECONDS)
    except asyncio.TimeoutError as exc:
        raise HTTPException(
            status_code=408,
            detail=f"Theme 통합 분석 제한시간 {_JOB_TIMEOUT_SECONDS // 60}분을 초과했습니다.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Theme 통합 분석 실패: {str(exc) or type(exc).__name__}") from exc
