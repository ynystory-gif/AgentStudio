from __future__ import annotations

"""Harden current-PC learning visibility for the misjudgment list.

The normal collection service already hides applied families, but this bridge adds an
exact Dataset.source_case_id guard. It makes the UI contract explicit: items returned
by /learning/misjudgments are current-PC *unlearned* items only.
"""

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.machine_identity import current_pc_name
from app.models.learning_entities import LlmLearningDataset, LlmLearningPcApplication
from app.services import learning_collection_service as collection


_original_list_aggregated_misjudgment_cases = collection.list_aggregated_misjudgment_cases


async def _current_pc_applied_source_ids() -> set[str]:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        dataset_ids = set((
            await session.execute(
                select(LlmLearningPcApplication.dataset_id).where(
                    LlmLearningPcApplication.pc_name == pc_name,
                    LlmLearningPcApplication.enabled == True,
                    LlmLearningPcApplication.installed == True,
                )
            )
        ).scalars().all())
        if not dataset_ids:
            return set()
        source_ids = set((
            await session.execute(
                select(LlmLearningDataset.source_case_id).where(
                    LlmLearningDataset.id.in_(dataset_ids)
                )
            )
        ).scalars().all())
    return {str(value) for value in source_ids if value}


async def list_aggregated_misjudgment_cases_current_pc_unlearned_only(
    provider: str = "",
    status: str = "",
    limit: int = 500,
) -> dict:
    result = await _original_list_aggregated_misjudgment_cases(provider, status, limit)
    applied_source_ids = await _current_pc_applied_source_ids()

    visible: list[dict] = []
    exact_hidden = 0
    for original in list(result.get("items") or []):
        item = dict(original)
        item_id = str(item.get("id") or "")
        group_ids = {str(value) for value in (item.get("group_case_ids") or []) if value}

        # Exact source rows that are already represented by an enabled+installed
        # Dataset on this PC must never reappear in the collection list.
        if item_id in applied_source_ids:
            exact_hidden += 1
            continue

        # If an aggregated group consists only of already-applied exact source rows,
        # hide it as well. A group containing any new/unapplied case remains visible.
        if group_ids and group_ids.issubset(applied_source_ids):
            exact_hidden += 1
            continue

        item["current_pc_learning_state"] = "unlearned"
        item["current_pc_learning_label"] = "현재 PC 미학습"
        visible.append(item)

    result["items"] = visible[: max(1, min(int(limit or 500), 2000))]
    result["total"] = len(result["items"])
    result["exact_source_hidden_count"] = exact_hidden
    result["current_pc_applied_source_count"] = len(applied_source_ids)
    result["visible_scope"] = "current_pc_unlearned_only"
    result["visible_scope_label"] = "현재 PC 미학습 오판만 표시"
    return result


# learning_routes imports the function after main imports this bridge.
collection.list_aggregated_misjudgment_cases = list_aggregated_misjudgment_cases_current_pc_unlearned_only
