from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime
from difflib import SequenceMatcher

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.machine_identity import current_pc_name
from app.models.learning_entities import LlmLearningDataset, LlmLearningPcApplication, LlmMisjudgmentCase
from app.services.llm_learning_service import (
    _case_dict,
    _dataset_dict,
    _generate_problem_batch,
    analyze_learning_scope,
    ensure_dataset_problem_storage,
    sync_misjudgment_candidates,
)

AUTO_CONFIRM_THRESHOLD = 0.75
_PROBLEM_JOBS: dict[str, dict] = {}


def _normalize(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").strip().casefold())
    text = re.sub(r"[^0-9a-z가-힣_+.#:/ -]+", "", text)
    return text[:1200]


def _same_family(a: dict, b: dict) -> bool:
    if str(a.get("provider") or "") != str(b.get("provider") or ""):
        return False
    if str(a.get("model") or "") != str(b.get("model") or ""):
        return False
    if str(a.get("detection_reason") or "") != str(b.get("detection_reason") or ""):
        return False
    ar = _normalize(a.get("user_request", ""))
    br = _normalize(b.get("user_request", ""))
    if not ar or not br:
        return False
    if ar == br:
        return True
    if ar in br or br in ar:
        short = min(len(ar), len(br))
        long = max(len(ar), len(br))
        if long and short / long >= 0.72:
            return True
    return SequenceMatcher(None, ar, br).ratio() >= 0.88


def _parse_iso(value: str) -> datetime:
    try:
        return datetime.fromisoformat(str(value or "").replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return datetime.min


async def _auto_confirm_high_confidence() -> int:
    changed = 0
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(LlmMisjudgmentCase).where(
                    LlmMisjudgmentCase.status == "candidate",
                    LlmMisjudgmentCase.confidence >= AUTO_CONFIRM_THRESHOLD,
                )
            )
        ).scalars().all()
        for row in rows:
            row.status = "confirmed"
            row.training_eligible = True
            row.updated_by_pc_name = current_pc_name()
            changed += 1
        if changed:
            await session.commit()
    return changed


async def _current_pc_applied_families() -> list[dict]:
    """Return source error cases that were already applied on this PC.

    Items that happened before application are hidden. If the same family fails again after
    application, that new failure remains visible so AgentStudio can learn the regression.
    """
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        apps = (
            await session.execute(
                select(LlmLearningPcApplication).where(
                    LlmLearningPcApplication.pc_name == pc_name,
                    LlmLearningPcApplication.enabled == True,
                    LlmLearningPcApplication.installed == True,
                )
            )
        ).scalars().all()
        if not apps:
            return []
        dataset_ids = [row.dataset_id for row in apps]
        datasets = (
            await session.execute(
                select(LlmLearningDataset).where(LlmLearningDataset.id.in_(dataset_ids))
            )
        ).scalars().all()
        source_ids = [row.source_case_id for row in datasets if row.source_case_id]
        sources = (
            await session.execute(
                select(LlmMisjudgmentCase).where(LlmMisjudgmentCase.id.in_(source_ids))
            )
        ).scalars().all() if source_ids else []

    source_by_id = {row.id: _case_dict(row) for row in sources}
    dataset_by_id = {row.id: row for row in datasets}
    result: list[dict] = []
    for app in apps:
        dataset = dataset_by_id.get(app.dataset_id)
        if not dataset:
            continue
        source = source_by_id.get(dataset.source_case_id)
        if not source:
            continue
        result.append({
            "source": source,
            "applied_at": app.applied_at or app.updated_at or datetime.utcnow(),
            "dataset_id": dataset.id,
            "model_name": app.model_name,
        })
    return result


def _hidden_by_applied_family(item: dict, applied_families: list[dict]) -> bool:
    occurred = _parse_iso(str(item.get("created_at") or item.get("updated_at") or ""))
    for applied in applied_families:
        source = applied.get("source") or {}
        applied_at = applied.get("applied_at") or datetime.min
        if _same_family(source, item) and occurred <= applied_at:
            return True
    return False


async def list_aggregated_misjudgment_cases(provider: str = "", status: str = "", limit: int = 500) -> dict:
    # v5.445: list GET is read-only with respect to history synchronization.
    # History scanning runs once at AgentStudio startup and on the explicit `오판 수집` action.
    # Auto-confirm remains inexpensive and keeps the 75% eligibility policy consistent.
    sync_result = {"ok": True, "skipped": True, "reason": "read_only_list"}
    auto_confirmed = await _auto_confirm_high_confidence()
    applied_families = await _current_pc_applied_families()
    async with SessionLocal() as session:
        stmt = select(LlmMisjudgmentCase)
        if provider:
            stmt = stmt.where(LlmMisjudgmentCase.provider == provider)
        if status:
            stmt = stmt.where(LlmMisjudgmentCase.status == status)
        rows = (await session.execute(stmt.order_by(LlmMisjudgmentCase.updated_at.desc()))).scalars().all()

    raw_all = [_case_dict(row) for row in rows]
    raw = [item for item in raw_all if not _hidden_by_applied_family(item, applied_families)]
    groups: list[dict] = []
    for item in raw:
        matched = None
        for group in groups:
            if _same_family(group["representative"], item):
                matched = group
                break
        if matched is None:
            groups.append({"representative": item, "items": [item]})
        else:
            matched["items"].append(item)
            rep = matched["representative"]
            if str(item.get("updated_at") or "") > str(rep.get("updated_at") or ""):
                matched["representative"] = item

    items: list[dict] = []
    for group in groups:
        members = group["items"]
        rep = dict(group["representative"])
        rep["occurrence_count"] = len(members)
        rep["first_occurred_at"] = min((str(x.get("created_at") or "") for x in members), default="")
        rep["last_occurred_at"] = max((str(x.get("updated_at") or x.get("created_at") or "") for x in members), default="")
        rep["group_case_ids"] = [str(x.get("id") or "") for x in members]
        rep["confidence"] = max(float(x.get("confidence") or 0) for x in members)
        if rep["confidence"] >= AUTO_CONFIRM_THRESHOLD:
            rep["status"] = "confirmed"
        items.append(rep)

    items.sort(key=lambda x: str(x.get("last_occurred_at") or ""), reverse=True)
    items = items[: max(1, min(int(limit or 500), 2000))]
    providers: dict[str, int] = {}
    for row in items:
        key = f"{row.get('provider','unknown')}::{row.get('model','unknown')}"
        providers[key] = providers.get(key, 0) + int(row.get("occurrence_count") or 1)
    return {
        "ok": True,
        "items": items,
        "total": len(items),
        "raw_total": len(raw_all),
        "hidden_applied_count": len(raw_all) - len(raw),
        "providers": providers,
        "auto_confirmed": auto_confirmed,
        "threshold": AUTO_CONFIRM_THRESHOLD,
        "storage": "runtime_db_shared",
        "sync": sync_result,
    }


async def _generate_candidate_dataset(case_row: LlmMisjudgmentCase, target_count: int, provider: str) -> LlmLearningDataset:
    case = _case_dict(case_row)
    scope = await asyncio.to_thread(analyze_learning_scope, case, provider)
    generated = await asyncio.to_thread(_generate_problem_batch, case, scope, target_count, provider)
    pc_name = current_pc_name()
    dataset = LlmLearningDataset(
        id=uuid.uuid4().hex,
        source_case_id=case_row.id,
        source_pc_name=pc_name,
        updated_by_pc_name=pc_name,
        status="review",
        provider=provider,
        source_provider=str(case.get("provider") or ""),
        source_model=str(case.get("model") or ""),
        scope_json=scope,
        target_count=target_count,
        problem_count=len(generated),
        problems_json=generated,
        validation_json={"approved": 0, "rejected": 0, "pending": len(generated)},
        split_json={},
        training_json={},
        evaluation_json={},
        deployment_json={"source": "problem_collection", "requires_validation": True},
    )
    return dataset


async def _select_problem_sources(
    max_cases: int,
    source_case_ids: list[str] | None = None,
) -> list[LlmMisjudgmentCase]:
    """Resolve problem-generation sources.

    v5.442 identity rule:
    - When the Learning Center sends visible ``source_case_ids``, those exact case IDs
      are authoritative and are preserved in the same order.
    - The legacy automatic selector is used only when no explicit IDs were supplied.

    This prevents an aggregated UI row from silently being replaced by another
    same-family raw case, which previously broke Dataset -> misjudgment -> PC learning
    traceability after applying a Dataset.
    """
    explicit_ids: list[str] = []
    seen: set[str] = set()
    for value in list(source_case_ids or []):
        case_id = str(value or "").strip()
        if case_id and case_id not in seen:
            explicit_ids.append(case_id)
            seen.add(case_id)
        if len(explicit_ids) >= max_cases:
            break

    async with SessionLocal() as session:
        if explicit_ids:
            rows = (
                await session.execute(
                    select(LlmMisjudgmentCase).where(LlmMisjudgmentCase.id.in_(explicit_ids))
                )
            ).scalars().all()
            by_id = {str(row.id): row for row in rows}
            selected: list[LlmMisjudgmentCase] = []
            for case_id in explicit_ids:
                row = by_id.get(case_id)
                if row is None:
                    continue
                if str(row.status or "").lower() != "confirmed":
                    continue
                selected.append(row)
            return selected[:max_cases]

        confirmed = (
            await session.execute(
                select(LlmMisjudgmentCase)
                .where(LlmMisjudgmentCase.status == "confirmed")
                .order_by(LlmMisjudgmentCase.updated_at.desc())
            )
        ).scalars().all()
        existing_source_ids = set((await session.execute(select(LlmLearningDataset.source_case_id))).scalars().all())
        selected: list[LlmMisjudgmentCase] = []
        for row in confirmed:
            if row.id in existing_source_ids:
                continue
            candidate = _case_dict(row)
            if any(_same_family(_case_dict(other), candidate) for other in selected):
                continue
            selected.append(row)
            if len(selected) >= max_cases:
                break
        return selected


async def collect_learning_problems(
    target_per_case: int = 100,
    max_cases: int = 20,
    provider: str = "ollama",
    source_case_ids: list[str] | None = None,
) -> dict:
    await sync_misjudgment_candidates()
    await _auto_confirm_high_confidence()
    target_per_case = max(10, min(int(target_per_case or 100), 500))
    max_cases = max(1, min(int(max_cases or 20), 20))
    selected = await _select_problem_sources(max_cases, source_case_ids)

    created: list[dict] = []
    errors: list[dict] = []
    for row in selected:
        try:
            dataset = await _generate_candidate_dataset(row, target_per_case, provider)
            async with SessionLocal() as session:
                session.add(dataset)
                await session.commit()
                await session.refresh(dataset)
            persisted = await ensure_dataset_problem_storage(str(dataset.id))
            if int(persisted.get("problem_count") or 0) <= 0:
                raise RuntimeError("Dataset 저장 후 학습 문제를 확인하지 못했습니다.")
            created.append(dict(persisted.get("dataset") or _dataset_dict(dataset)))
        except Exception as exc:
            errors.append({"case_id": row.id, "message": str(exc) or type(exc).__name__})

    return {
        "ok": not errors,
        "created": len(created),
        "datasets": created,
        "requested_source_case_ids": [str(row.id) for row in selected],
        "created_source_case_ids": [str(item.get("source_case_id") or "") for item in created],
        "errors": errors,
        "message": (
            f"확정 오판 주제 {len(created)}개에서 후보 학습 문제를 수집했습니다. Dataset 검증 전에는 학습에 사용되지 않습니다."
            if created else "새로 문제를 수집할 확정 오판 주제가 없습니다."
        ),
    }


def _set_problem_job(job_id: str, progress: int, stage: str, message: str, **extra) -> None:
    job = _PROBLEM_JOBS.setdefault(job_id, {})
    job.update({
        "id": job_id,
        "progress": max(0, min(100, int(progress))),
        "stage": stage,
        "message": message,
        "updated_at": datetime.utcnow().isoformat(),
        **extra,
    })


async def _run_problem_collection_job(
    job_id: str,
    target_per_case: int,
    max_cases: int,
    provider: str,
    source_case_ids: list[str] | None = None,
) -> None:
    try:
        _set_problem_job(job_id, 5, "sync", "오판 수집 기록을 공용 DB와 동기화 중...", status="running")
        await sync_misjudgment_candidates()
        await _auto_confirm_high_confidence()
        selected = await _select_problem_sources(max_cases, source_case_ids)
        if source_case_ids and len(selected) != len({str(value) for value in source_case_ids if str(value or "").strip()}):
            resolved_ids = {str(row.id) for row in selected}
            missing_ids = [str(value) for value in source_case_ids if str(value or "").strip() and str(value) not in resolved_ids]
            raise ValueError("요청한 오판 ID를 정확히 찾지 못했습니다: " + ", ".join(missing_ids))
        if not selected:
            _set_problem_job(job_id, 100, "done", "새로 문제를 수집할 확정 오판 주제가 없습니다.", status="completed", result={"created": 0, "datasets": []})
            return

        total = len(selected)
        created: list[dict] = []
        errors: list[dict] = []
        for index, row in enumerate(selected, start=1):
            start_progress = 10 + int(((index - 1) / total) * 80)
            _set_problem_job(
                job_id,
                start_progress,
                "generate",
                f"오판 주제 {index}/{total} 분석 및 관련 문제 {target_per_case}개 생성 중...",
                status="running",
                current_topic=index,
                total_topics=total,
            )
            try:
                dataset = await _generate_candidate_dataset(row, target_per_case, provider)
                async with SessionLocal() as session:
                    session.add(dataset)
                    await session.commit()
                    await session.refresh(dataset)
                persisted = await ensure_dataset_problem_storage(str(dataset.id))
                if int(persisted.get("problem_count") or 0) <= 0:
                    raise RuntimeError("Dataset 저장 후 학습 문제를 확인하지 못했습니다.")
                created.append(dict(persisted.get("dataset") or _dataset_dict(dataset)))
            except Exception as exc:
                errors.append({"case_id": row.id, "message": str(exc) or type(exc).__name__})
            end_progress = 10 + int((index / total) * 80)
            _set_problem_job(
                job_id,
                end_progress,
                "generate",
                f"오판 주제 {index}/{total} 처리 완료 · Dataset {len(created)}개 생성",
                status="running",
                current_topic=index,
                total_topics=total,
            )

        generated_problem_count = sum(int(item.get("problem_count") or len(item.get("problems") or [])) for item in created)
        result = {
            "created": len(created),
            "datasets": created,
            "requested_source_case_ids": [str(row.id) for row in selected],
            "created_source_case_ids": [str(item.get("source_case_id") or "") for item in created],
            "source_mapping_verified": [str(item.get("source_case_id") or "") for item in created] == [str(row.id) for row in selected],
            "errors": errors,
            "generated_problem_count": generated_problem_count,
            "persistence_verified": bool(created) and generated_problem_count > 0,
        }
        if created and generated_problem_count > 0 and result["source_mapping_verified"]:
            _set_problem_job(
                job_id,
                100,
                "done",
                f"문제 수집 완료 · Dataset {len(created)}개 / 문제 {generated_problem_count}개 DB 저장 확인.",
                status="completed" if not errors else "completed",
                result=result,
            )
        else:
            mapping_error = "오판 ID와 Dataset source_case_id 매핑 검증에 실패했습니다." if created and not result["source_mapping_verified"] else ""
            error_text = "; ".join(x["message"] for x in errors) or mapping_error or "문제 Dataset을 생성하지 못했습니다."
            _set_problem_job(job_id, 100, "failed", error_text, status="failed", error=error_text, result=result)
    except Exception as exc:
        _set_problem_job(job_id, int(_PROBLEM_JOBS.get(job_id, {}).get("progress") or 0), "failed", str(exc) or type(exc).__name__, status="failed", error=str(exc) or type(exc).__name__)


async def start_problem_collection_job(
    target_per_case: int = 100,
    max_cases: int = 20,
    provider: str = "ollama",
    source_case_ids: list[str] | None = None,
) -> dict:
    target = max(10, min(int(target_per_case or 100), 500))
    maximum = max(1, min(int(max_cases or 20), 20))
    for job in _PROBLEM_JOBS.values():
        if job.get("status") == "running":
            return dict(job)
    job_id = uuid.uuid4().hex
    _set_problem_job(
        job_id,
        1,
        "queued",
        "문제 수집 작업을 준비합니다.",
        status="running",
        target_per_topic=target,
        max_topics=maximum,
        source_case_ids=[str(value) for value in list(source_case_ids or []) if str(value or "").strip()][:maximum],
        created_at=datetime.utcnow().isoformat(),
    )
    asyncio.create_task(_run_problem_collection_job(job_id, target, maximum, provider, source_case_ids))
    return dict(_PROBLEM_JOBS[job_id])


async def get_problem_collection_job(job_id: str) -> dict:
    job = _PROBLEM_JOBS.get(str(job_id or ""))
    if not job:
        raise KeyError("문제 수집 작업을 찾을 수 없습니다.")
    return dict(job)
