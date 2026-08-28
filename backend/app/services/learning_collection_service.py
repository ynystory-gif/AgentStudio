from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime
from difflib import SequenceMatcher

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.machine_identity import current_pc_name
from app.models.learning_entities import LlmLearningDataset, LlmMisjudgmentCase
from app.services.llm_learning_service import (
    _case_dict,
    _dataset_dict,
    _generate_problem_batch,
    analyze_learning_scope,
    sync_misjudgment_candidates,
)

AUTO_CONFIRM_THRESHOLD = 0.75


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


def _date_value(value) -> datetime:
    return value if isinstance(value, datetime) else datetime.min


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
            # Automatic confirmation means the signal is trusted as an error case.
            # Generated answers are still only candidate learning data until Dataset validation.
            row.training_eligible = True
            row.updated_by_pc_name = current_pc_name()
            changed += 1
        if changed:
            await session.commit()
    return changed


async def list_aggregated_misjudgment_cases(provider: str = "", status: str = "", limit: int = 500) -> dict:
    sync_result = await sync_misjudgment_candidates()
    auto_confirmed = await _auto_confirm_high_confidence()
    async with SessionLocal() as session:
        stmt = select(LlmMisjudgmentCase)
        if provider:
            stmt = stmt.where(LlmMisjudgmentCase.provider == provider)
        if status:
            stmt = stmt.where(LlmMisjudgmentCase.status == status)
        rows = (await session.execute(stmt.order_by(LlmMisjudgmentCase.updated_at.desc()))).scalars().all()

    raw = [_case_dict(row) for row in rows]
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
        "raw_total": len(raw),
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


async def collect_learning_problems(
    target_per_case: int = 100,
    max_cases: int = 5,
    provider: str = "ollama",
) -> dict:
    """Generate candidate learning problems from confirmed error families.

    This is intentionally separate from error collection. Generated answers are NOT
    trusted training truth; datasets stay in review until the existing Validator flow
    marks them validated.
    """
    await sync_misjudgment_candidates()
    await _auto_confirm_high_confidence()
    target_per_case = max(10, min(int(target_per_case or 100), 500))
    max_cases = max(1, min(int(max_cases or 5), 20))

    async with SessionLocal() as session:
        confirmed = (
            await session.execute(
                select(LlmMisjudgmentCase)
                .where(LlmMisjudgmentCase.status == "confirmed")
                .order_by(LlmMisjudgmentCase.updated_at.desc())
            )
        ).scalars().all()
        existing_source_ids = set(
            (await session.execute(select(LlmLearningDataset.source_case_id))).scalars().all()
        )
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

    created: list[dict] = []
    errors: list[dict] = []
    for row in selected:
        try:
            dataset = await _generate_candidate_dataset(row, target_per_case, provider)
            async with SessionLocal() as session:
                session.add(dataset)
                await session.commit()
                await session.refresh(dataset)
            created.append(_dataset_dict(dataset))
        except Exception as exc:
            errors.append({"case_id": row.id, "message": str(exc) or type(exc).__name__})

    return {
        "ok": not errors,
        "created": len(created),
        "datasets": created,
        "errors": errors,
        "message": (
            f"확정 오판 범위 {len(created)}건에서 후보 학습 문제를 수집했습니다. Dataset 검증 전에는 학습에 사용되지 않습니다."
            if created else
            "새로 문제를 수집할 확정 오판 범위가 없습니다."
        ),
    }
