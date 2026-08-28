from __future__ import annotations

"""Relational learning mapping migration/backfill.

This replaces JSON-only learning lineage with explicit DB identity:

misjudgment_group -> group_case -> misjudgment_case
misjudgment_group -> learning_dataset -> learning_problem
misjudgment_group -> pc_application

Every table has its own ``id`` primary key. Existing JSON fields are retained only for
backward compatibility while relational rows become the authoritative lineage.
"""

import hashlib
import uuid
from datetime import datetime

from sqlalchemy import select, text

from app.core import database as db
from app.models.learning_entities import (
    LlmLearningDataset,
    LlmLearningPcApplication,
    LlmLearningProblem,
    LlmMisjudgmentCase,
    LlmMisjudgmentGroup,
    LlmMisjudgmentGroupCase,
)
from app.services import learning_collection_service as collection
from app.services.llm_learning_service import _case_dict


def _semantic_group_key(source: dict) -> str:
    normalized = collection._normalize(str(source.get("user_request") or ""))
    payload = "|".join([
        str(source.get("provider") or ""),
        str(source.get("model") or ""),
        str(source.get("detection_reason") or ""),
        normalized,
    ])
    return "misgrp:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


async def ensure_learning_relational_schema() -> dict:
    """Add relational columns/tables and backfill existing learning data safely."""
    # Existing tables need ALTER because create_all(checkfirst) never adds columns.
    target_schema = db.runtime_schema or "public"
    qschema = db.quote_identifier(target_schema)
    statements = [
        f'ALTER TABLE {qschema}."llm_misjudgment_cases" ADD COLUMN IF NOT EXISTS group_id VARCHAR(64) NOT NULL DEFAULT \'\'',
        f'ALTER TABLE {qschema}."llm_learning_datasets" ADD COLUMN IF NOT EXISTS group_id VARCHAR(64) NOT NULL DEFAULT \'\'',
        f'ALTER TABLE {qschema}."llm_learning_pc_applications" ADD COLUMN IF NOT EXISTS group_id VARCHAR(64) NOT NULL DEFAULT \'\'',
        f'CREATE INDEX IF NOT EXISTS ix_llm_misjudgment_cases_group_id ON {qschema}."llm_misjudgment_cases"(group_id)',
        f'CREATE INDEX IF NOT EXISTS ix_llm_learning_datasets_group_id ON {qschema}."llm_learning_datasets"(group_id)',
        f'CREATE INDEX IF NOT EXISTS ix_llm_learning_pc_applications_group_id ON {qschema}."llm_learning_pc_applications"(group_id)',
    ]
    async with db.engine.begin() as conn:
        for statement in statements:
            await conn.execute(text(statement))
        # New tables all have an explicit id PK and are created additively.
        await conn.run_sync(db.Base.metadata.create_all)

    return await backfill_learning_relational_mappings()


async def _get_or_create_group(session, source: LlmMisjudgmentCase) -> LlmMisjudgmentGroup:
    source_dict = _case_dict(source)
    # Reuse an already-related group first. This allows future recurrences to join the same
    # semantic group instead of generating a snapshot-only identity.
    groups = (await session.execute(select(LlmMisjudgmentGroup))).scalars().all()
    if groups:
        group_ids = [row.id for row in groups]
        mappings = (
            await session.execute(
                select(LlmMisjudgmentGroupCase).where(LlmMisjudgmentGroupCase.group_id.in_(group_ids))
            )
        ).scalars().all()
        mapped_case_ids = [row.case_id for row in mappings]
        mapped_cases = (
            await session.execute(
                select(LlmMisjudgmentCase).where(LlmMisjudgmentCase.id.in_(mapped_case_ids))
            )
        ).scalars().all() if mapped_case_ids else []
        case_by_id = {str(row.id): row for row in mapped_cases}
        for mapping in mappings:
            candidate = case_by_id.get(str(mapping.case_id))
            if candidate is not None and collection._same_family(_case_dict(candidate), source_dict):
                return next(row for row in groups if str(row.id) == str(mapping.group_id))

    key = _semantic_group_key(source_dict)
    existing = (
        await session.execute(select(LlmMisjudgmentGroup).where(LlmMisjudgmentGroup.group_key == key))
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    group = LlmMisjudgmentGroup(
        id=uuid.uuid4().hex,
        group_key=key,
        provider=str(source.provider or "unknown"),
        model=str(source.model or "unknown"),
        detection_reason=str(source.detection_reason or ""),
        domain=str(source.domain or ""),
        topic=str(source.topic or ""),
        error_type=str(source.error_type or "unclassified"),
        status="active",
    )
    session.add(group)
    await session.flush()
    return group


async def backfill_learning_relational_mappings() -> dict:
    created_groups = 0
    created_group_cases = 0
    linked_datasets = 0
    created_problems = 0
    linked_apps = 0

    async with db.SessionLocal() as session:
        cases = (await session.execute(select(LlmMisjudgmentCase).order_by(LlmMisjudgmentCase.created_at.asc()))).scalars().all()
        case_by_id = {str(row.id): row for row in cases}

        # First form stable groups and explicit group-case mapping rows.
        handled: set[str] = set()
        for case in cases:
            if str(case.id) in handled or str(case.status or "").lower() == "rejected":
                continue
            before = int((await session.execute(select(LlmMisjudgmentGroup))).scalars().all().__len__())
            group = await _get_or_create_group(session, case)
            after = int((await session.execute(select(LlmMisjudgmentGroup))).scalars().all().__len__())
            if after > before:
                created_groups += 1

            family = [candidate for candidate in cases if str(candidate.status or "").lower() != "rejected" and collection._same_family(_case_dict(case), _case_dict(candidate))]
            for member in family:
                member.group_id = group.id
                handled.add(str(member.id))
                exists = (
                    await session.execute(
                        select(LlmMisjudgmentGroupCase).where(
                            LlmMisjudgmentGroupCase.group_id == group.id,
                            LlmMisjudgmentGroupCase.case_id == member.id,
                        )
                    )
                ).scalar_one_or_none()
                if exists is None:
                    session.add(LlmMisjudgmentGroupCase(
                        id=uuid.uuid4().hex,
                        group_id=group.id,
                        case_id=member.id,
                        mapping_source="backfill_same_family",
                    ))
                    created_group_cases += 1

        await session.flush()

        datasets = (await session.execute(select(LlmLearningDataset))).scalars().all()
        for dataset in datasets:
            source = case_by_id.get(str(dataset.source_case_id or ""))
            if source is not None and source.group_id:
                if dataset.group_id != source.group_id:
                    dataset.group_id = source.group_id
                    linked_datasets += 1

            existing_problem_keys = set((
                await session.execute(
                    select(LlmLearningProblem.problem_key).where(LlmLearningProblem.dataset_id == dataset.id)
                )
            ).scalars().all())
            for index, problem in enumerate(list(dataset.problems_json or [])):
                if not isinstance(problem, dict):
                    continue
                problem_key = str(problem.get("id") or f"legacy-{index + 1}")
                if problem_key in existing_problem_keys:
                    continue
                session.add(LlmLearningProblem(
                    id=uuid.uuid4().hex,
                    dataset_id=dataset.id,
                    group_id=str(dataset.group_id or ""),
                    source_case_id=str(dataset.source_case_id or ""),
                    problem_key=problem_key,
                    instruction=str(problem.get("instruction") or ""),
                    input_text=str(problem.get("input") or ""),
                    output_text=str(problem.get("output") or ""),
                    domain=str(problem.get("domain") or ""),
                    topic=str(problem.get("topic") or ""),
                    subtopic=str(problem.get("subtopic") or ""),
                    difficulty=str(problem.get("difficulty") or "medium"),
                    problem_type=str(problem.get("problem_type") or "scenario"),
                    validated=bool(problem.get("validated")),
                ))
                created_problems += 1

        apps = (await session.execute(select(LlmLearningPcApplication))).scalars().all()
        dataset_group = {str(row.id): str(row.group_id or "") for row in datasets}
        for app in apps:
            group_id = dataset_group.get(str(app.dataset_id), "")
            if group_id and app.group_id != group_id:
                app.group_id = group_id
                linked_apps += 1

        await session.commit()

    return {
        "ok": True,
        "created_group_count": created_groups,
        "created_group_case_mapping_count": created_group_cases,
        "linked_dataset_count": linked_datasets,
        "created_problem_row_count": created_problems,
        "linked_pc_application_count": linked_apps,
        "id_policy": "all_learning_tables_have_id_primary_key",
        "mapped_at": datetime.utcnow().isoformat(),
    }
