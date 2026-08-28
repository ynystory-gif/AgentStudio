from __future__ import annotations

"""Persist explicit misjudgment-group mappings on generated learning Datasets.

A Dataset historically stored only one representative ``source_case_id`` even though the
Learning Center groups several similar misjudgment rows into one visible topic.  That made
post-training visibility depend on fuzzy matching.  This bridge stores the exact group
snapshot used by a Dataset in ``deployment_json`` so the chain is explicit:

    misjudgment case ids -> Dataset -> PC application

No schema migration is required; the mapping lives in the existing JSON deployment field.
"""

import hashlib
from datetime import datetime

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.learning_entities import LlmMisjudgmentCase
from app.services import learning_collection_service as collection
from app.services.llm_learning_service import _case_dict


_original_generate_candidate_dataset = collection._generate_candidate_dataset


def _group_key(case_ids: list[str]) -> str:
    normalized = "|".join(sorted({str(value) for value in case_ids if value}))
    return "misgrp:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


async def _family_snapshot(source_case_id: str) -> list[str]:
    async with SessionLocal() as session:
        source = await session.get(LlmMisjudgmentCase, source_case_id)
        if source is None:
            return [source_case_id] if source_case_id else []
        source_dict = _case_dict(source)
        rows = (
            await session.execute(
                select(LlmMisjudgmentCase).where(
                    LlmMisjudgmentCase.provider == source.provider,
                    LlmMisjudgmentCase.model == source.model,
                    LlmMisjudgmentCase.detection_reason == source.detection_reason,
                )
            )
        ).scalars().all()

    ids: list[str] = []
    for row in rows:
        if collection._same_family(source_dict, _case_dict(row)):
            ids.append(str(row.id))
    if source_case_id and source_case_id not in ids:
        ids.append(source_case_id)
    return sorted(set(ids))


async def _generate_candidate_dataset_with_group_mapping(
    case_row: LlmMisjudgmentCase,
    target_count: int,
    provider: str,
):
    dataset = await _original_generate_candidate_dataset(case_row, target_count, provider)
    group_case_ids = await _family_snapshot(str(case_row.id))
    deployment = dict(dataset.deployment_json or {})
    deployment.update({
        "source_case_id": str(case_row.id),
        "source_group_case_ids": group_case_ids,
        "source_group_key": _group_key(group_case_ids),
        "source_group_mapped_at": datetime.utcnow().isoformat(),
        "source_group_mapping_version": 1,
    })
    dataset.deployment_json = deployment
    return dataset


# The problem-collection job resolves this module global at runtime.  main imports this
# bridge after the Teacher bridge, so the wrapper preserves the Teacher implementation.
collection._generate_candidate_dataset = _generate_candidate_dataset_with_group_mapping
