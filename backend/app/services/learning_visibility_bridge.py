from __future__ import annotations

"""Harden current-PC learning visibility for the misjudgment list.

The Learning Center must show only actionable, current-PC unlearned errors.
A Dataset is created from an aggregated error family, so applying that Dataset means
all occurrences of the same family that happened on or before the application time
are learned as well. Only a genuinely new recurrence after learning may reappear.
"""

# Load first so AgentStudio's own Teacher/Validator/problem-generation telemetry can
# never feed back into the user misjudgment queue. It also quarantines legacy polluted
# rows on the next sync/list request.
import app.services.learning_internal_call_filter_bridge  # noqa: F401

from datetime import datetime

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.machine_identity import current_pc_name
from app.models.learning_entities import (
    LlmLearningDataset,
    LlmLearningPcApplication,
    LlmMisjudgmentCase,
)
from app.services import learning_collection_service as collection
from app.services.llm_learning_service import _case_dict


_original_list_aggregated_misjudgment_cases = collection.list_aggregated_misjudgment_cases


def _case_time(item: dict) -> datetime:
    value = str(item.get("created_at") or item.get("updated_at") or "").strip()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return datetime.min


async def _current_pc_applied_families() -> tuple[set[str], list[dict]]:
    """Return exact applied source ids and their learned-family cutoff times."""
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
            return set(), []

        dataset_ids = {str(row.dataset_id) for row in apps if row.dataset_id}
        datasets = (
            await session.execute(
                select(LlmLearningDataset).where(LlmLearningDataset.id.in_(dataset_ids))
            )
        ).scalars().all()
        dataset_by_id = {str(row.id): row for row in datasets}

        source_ids = {
            str(row.source_case_id)
            for row in datasets
            if row.source_case_id
        }
        source_rows = (
            await session.execute(
                select(LlmMisjudgmentCase).where(LlmMisjudgmentCase.id.in_(source_ids))
            )
        ).scalars().all() if source_ids else []
        source_by_id = {str(row.id): _case_dict(row) for row in source_rows}

    exact_ids: set[str] = set()
    families: list[dict] = []
    for app in apps:
        dataset = dataset_by_id.get(str(app.dataset_id))
        if not dataset or not dataset.source_case_id:
            continue
        source_id = str(dataset.source_case_id)
        source = source_by_id.get(source_id)
        if not source:
            continue
        exact_ids.add(source_id)
        families.append({
            "source": source,
            "applied_at": app.applied_at or app.updated_at or datetime.utcnow(),
            "dataset_id": str(dataset.id),
        })
    return exact_ids, families


def _member_is_learned(member: dict, exact_ids: set[str], families: list[dict]) -> bool:
    member_id = str(member.get("id") or "")
    if member_id and member_id in exact_ids:
        return True

    occurred = _case_time(member)
    for learned in families:
        source = learned.get("source") or {}
        applied_at = learned.get("applied_at") or datetime.min
        # A Dataset represents the whole aggregated error family, not only its one
        # source row. Historical same-family occurrences are therefore learned too.
        if collection._same_family(source, member) and occurred <= applied_at:
            return True
    return False


async def list_aggregated_misjudgment_cases_current_pc_unlearned_only(
    provider: str = "",
    status: str = "",
    limit: int = 500,
) -> dict:
    result = await _original_list_aggregated_misjudgment_cases(provider, status, limit)
    exact_ids, learned_families = await _current_pc_applied_families()

    aggregated = list(result.get("items") or [])
    all_group_ids: set[str] = set()
    for item in aggregated:
        ids = item.get("group_case_ids") or [item.get("id")]
        all_group_ids.update(str(value) for value in ids if value)

    # Re-read the raw group members. This is necessary because the aggregated
    # representative can itself be an old learned row while one new recurrence keeps
    # the group visible. We rebuild the displayed representative from unlearned members.
    async with SessionLocal() as session:
        member_rows = (
            await session.execute(
                select(LlmMisjudgmentCase).where(LlmMisjudgmentCase.id.in_(all_group_ids))
            )
        ).scalars().all() if all_group_ids else []
    members_by_id = {str(row.id): _case_dict(row) for row in member_rows}

    visible: list[dict] = []
    hidden_learned_members = 0
    hidden_learned_groups = 0

    for original in aggregated:
        group_ids = [
            str(value)
            for value in (original.get("group_case_ids") or [original.get("id")])
            if value
        ]
        raw_members = [members_by_id[value] for value in group_ids if value in members_by_id]
        if not raw_members:
            raw_members = [dict(original)]

        actionable: list[dict] = []
        for member in raw_members:
            if str(member.get("status") or "").strip().lower() == "rejected":
                continue
            if float(member.get("confidence") or 0.0) < 0.75:
                continue
            if _member_is_learned(member, exact_ids, learned_families):
                hidden_learned_members += 1
                continue
            actionable.append(member)

        if not actionable:
            hidden_learned_groups += 1
            continue

        # Show only the newest genuinely unlearned/recurrent member as representative.
        actionable.sort(
            key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""),
            reverse=True,
        )
        representative = dict(actionable[0])
        representative["occurrence_count"] = len(actionable)
        representative["group_case_ids"] = [str(item.get("id") or "") for item in actionable]
        representative["first_occurred_at"] = min(
            (str(item.get("created_at") or "") for item in actionable),
            default="",
        )
        representative["last_occurred_at"] = max(
            (str(item.get("updated_at") or item.get("created_at") or "") for item in actionable),
            default="",
        )
        representative["confidence"] = max(float(item.get("confidence") or 0.0) for item in actionable)
        representative["status"] = "confirmed"
        representative["current_pc_learning_state"] = "unlearned_recurrence" if learned_families else "unlearned"
        representative["current_pc_learning_label"] = (
            "학습 후 재발 · 현재 PC 미학습"
            if any(collection._same_family(family.get("source") or {}, representative) for family in learned_families)
            else "현재 PC 미학습"
        )
        visible.append(representative)

    visible.sort(
        key=lambda item: str(item.get("last_occurred_at") or item.get("updated_at") or ""),
        reverse=True,
    )
    visible = visible[: max(1, min(int(limit or 500), 2000))]

    providers: dict[str, int] = {}
    for row in visible:
        key = f"{row.get('provider', 'unknown')}::{row.get('model', 'unknown')}"
        providers[key] = providers.get(key, 0) + int(row.get("occurrence_count") or 1)

    result["items"] = visible
    result["total"] = len(visible)
    result["providers"] = providers
    result["current_pc_applied_source_count"] = len(exact_ids)
    result["current_pc_learned_family_count"] = len(learned_families)
    result["hidden_learned_member_count"] = hidden_learned_members
    result["hidden_learned_group_count"] = hidden_learned_groups
    result["visible_scope"] = "current_pc_unlearned_or_post_learning_recurrence_only"
    result["visible_scope_label"] = "현재 PC 미학습 또는 학습 후 재발 오판만 표시"
    result["visible_confidence_min"] = 0.75
    return result


# learning_routes imports the function after main imports this bridge.
collection.list_aggregated_misjudgment_cases = list_aggregated_misjudgment_cases_current_pc_unlearned_only
