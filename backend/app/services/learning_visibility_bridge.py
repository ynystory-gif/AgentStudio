from __future__ import annotations

"""Show only current-PC unlearned or post-learning recurrent misjudgments.

The key rule is explicit identity mapping, not fuzzy display inference:

    misjudgment group case ids -> Dataset.deployment_json -> PC application

New Datasets receive ``source_group_case_ids`` when problems are collected. Legacy
Datasets are backfilled from their representative source and application cutoff. The
backfill can run both at AgentStudio startup and lazily during list reads, so existing
Datasets do not need to be regenerated or relearned.
"""

# Block internal Teacher/Validator/problem-generation telemetry before it can re-enter
# the user learning queue, and install explicit group mapping for future Datasets.
import app.services.learning_internal_call_filter_bridge  # noqa: F401
import app.services.learning_group_mapping_bridge  # noqa: F401

from datetime import datetime
import hashlib

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


def _group_key(case_ids: set[str]) -> str:
    payload = "|".join(sorted(case_ids))
    return "misgrp:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


async def _current_pc_learned_case_ids() -> tuple[set[str], list[dict], int]:
    """Return exact learned case ids and family metadata for current PC.

    For modern Datasets the exact group snapshot comes from deployment_json.
    For legacy Datasets that only have source_case_id, reconstruct the family only up to
    the PC application timestamp, persist that mapping, and use it from then on.
    """
    pc_name = current_pc_name()
    backfilled = 0

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
            return set(), [], 0

        dataset_ids = {str(row.dataset_id) for row in apps if row.dataset_id}
        datasets = (
            await session.execute(
                select(LlmLearningDataset).where(LlmLearningDataset.id.in_(dataset_ids))
            )
        ).scalars().all()
        dataset_by_id = {str(row.id): row for row in datasets}

        source_ids = {str(row.source_case_id) for row in datasets if row.source_case_id}
        source_rows = (
            await session.execute(
                select(LlmMisjudgmentCase).where(LlmMisjudgmentCase.id.in_(source_ids))
            )
        ).scalars().all() if source_ids else []
        source_by_id = {str(row.id): row for row in source_rows}

        # Load all candidate rows once for deterministic legacy backfill.
        all_cases = (
            await session.execute(select(LlmMisjudgmentCase))
        ).scalars().all()

        learned_ids: set[str] = set()
        families: list[dict] = []
        changed = False

        for app in apps:
            dataset = dataset_by_id.get(str(app.dataset_id))
            if dataset is None:
                continue
            applied_at = app.applied_at or app.updated_at or datetime.utcnow()
            deployment = dict(dataset.deployment_json or {})
            mapped_ids = {
                str(value)
                for value in (deployment.get("source_group_case_ids") or [])
                if value
            }

            source_row = source_by_id.get(str(dataset.source_case_id or ""))
            source_dict = _case_dict(source_row) if source_row is not None else {}

            if not mapped_ids:
                # Legacy Dataset: recover the historical family snapshot. Never include
                # occurrences newer than applied_at; those remain true recurrences.
                if source_row is not None:
                    for row in all_cases:
                        candidate = _case_dict(row)
                        if _case_time(candidate) <= applied_at and collection._same_family(source_dict, candidate):
                            mapped_ids.add(str(row.id))
                if dataset.source_case_id:
                    mapped_ids.add(str(dataset.source_case_id))

                if mapped_ids:
                    deployment["source_case_id"] = str(dataset.source_case_id or "")
                    deployment["source_group_case_ids"] = sorted(mapped_ids)
                    deployment["source_group_key"] = _group_key(mapped_ids)
                    deployment["source_group_mapped_at"] = datetime.utcnow().isoformat()
                    deployment["source_group_mapping_version"] = 1
                    deployment["source_group_mapping_backfilled"] = True
                    dataset.deployment_json = deployment
                    changed = True
                    backfilled += 1

            learned_ids.update(mapped_ids)
            group_key = str(deployment.get("source_group_key") or "")
            if not group_key and mapped_ids:
                group_key = _group_key(mapped_ids)
            families.append({
                "dataset_id": str(dataset.id),
                "source": source_dict,
                "source_group_key": group_key,
                "source_group_case_ids": sorted(mapped_ids),
                "applied_at": applied_at,
            })

        if changed:
            await session.commit()

    return learned_ids, families, backfilled


async def backfill_current_pc_learning_group_mappings() -> dict:
    """Persist missing group mappings for already-applied legacy Datasets.

    This is intentionally safe to call repeatedly. Existing explicit mappings are left
    untouched; only legacy Datasets without ``source_group_case_ids`` are repaired.
    """
    learned_ids, families, backfilled = await _current_pc_learned_case_ids()
    return {
        "ok": True,
        "pc_name": current_pc_name(),
        "backfilled_dataset_count": backfilled,
        "learned_case_count": len(learned_ids),
        "learned_family_count": len(families),
    }


async def list_aggregated_misjudgment_cases_current_pc_unlearned_only(
    provider: str = "",
    status: str = "",
    limit: int = 500,
) -> dict:
    result = await _original_list_aggregated_misjudgment_cases(provider, status, limit)
    learned_case_ids, learned_families, backfilled = await _current_pc_learned_case_ids()

    aggregated = list(result.get("items") or [])
    all_group_ids: set[str] = set()
    for item in aggregated:
        ids = item.get("group_case_ids") or [item.get("id")]
        all_group_ids.update(str(value) for value in ids if value)

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
            member_id = str(member.get("id") or "")
            if str(member.get("status") or "").strip().lower() == "rejected":
                continue
            if float(member.get("confidence") or 0.0) < 0.75:
                continue

            # Primary rule: exact key mapping from Dataset snapshot.
            if member_id and member_id in learned_case_ids:
                hidden_learned_members += 1
                continue

            # A post-learning recurrence is intentionally not in the stored snapshot.
            actionable.append(member)

        if not actionable:
            hidden_learned_groups += 1
            continue

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

        related_learned_family = next((
            family for family in learned_families
            if family.get("source") and collection._same_family(family.get("source") or {}, representative)
        ), None)
        representative["current_pc_learning_state"] = "unlearned_recurrence" if related_learned_family else "unlearned"
        representative["current_pc_learning_label"] = (
            "학습 후 재발 · 현재 PC 미학습" if related_learned_family else "현재 PC 미학습"
        )
        representative["learning_group_key"] = str((related_learned_family or {}).get("source_group_key") or "")
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
    result["current_pc_learned_case_count"] = len(learned_case_ids)
    result["current_pc_learned_family_count"] = len(learned_families)
    result["legacy_group_mapping_backfilled"] = backfilled
    result["hidden_learned_member_count"] = hidden_learned_members
    result["hidden_learned_group_count"] = hidden_learned_groups
    result["visible_scope"] = "explicit_group_key_unlearned_or_recurrence_only"
    result["visible_scope_label"] = "현재 PC 미학습 또는 학습 후 재발 오판만 표시"
    result["visible_confidence_min"] = 0.75
    return result


# learning_routes imports the function after main imports this bridge.
collection.list_aggregated_misjudgment_cases = list_aggregated_misjudgment_cases_current_pc_unlearned_only
