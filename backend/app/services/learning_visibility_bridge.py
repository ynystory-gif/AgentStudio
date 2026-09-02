from __future__ import annotations

"""Show only current-PC unlearned or post-learning recurrent misjudgments.

The key rule is explicit identity mapping, not fuzzy display inference:

    misjudgment group case ids -> Dataset.deployment_json -> PC application

New Datasets receive ``source_group_case_ids`` when problems are collected. Legacy
Datasets are backfilled from their representative source and application cutoff. The
backfill can run both at AgentStudio startup and lazily during list reads, so existing
Datasets do not need to be regenerated or relearned.

Important: an existing mapping is not assumed to be complete. Every applied Dataset is
reconciled against historical same-family cases up to its application time. This repairs
partial mappings created by older builds without treating a later recurrence as learned.

The visible misjudgment rows are also enriched with learning-data status so the UI can
show whether the error family already has Dataset/problem data and whether that Dataset
is applied on the current PC.
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


def _problem_count(dataset: LlmLearningDataset) -> int:
    """Return the most useful problem count for display."""
    problems = list(dataset.problems_json or [])
    if problems:
        return len([item for item in problems if isinstance(item, dict)])
    return int(dataset.problem_count or 0)


async def _current_pc_learned_case_ids(repair_mappings: bool = True) -> tuple[set[str], list[dict], int]:
    """Return exact learned case ids and family metadata for current PC.

    For modern Datasets the group snapshot comes from deployment_json. For every applied
    Dataset we additionally reconcile that snapshot against same-family historical cases
    that occurred on or before the application time. This means partial legacy mappings
    are repaired even when ``source_group_case_ids`` already exists.
    """
    pc_name = current_pc_name()
    repaired = 0

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

        # v5.445: full family reconciliation is a maintenance/write operation. It runs
        # at startup and after learning-apply, not on every list GET. Normal screen reads
        # use the persisted source_group_case_ids snapshot and exact source ID only.
        all_cases = (
            (await session.execute(select(LlmMisjudgmentCase))).scalars().all()
            if repair_mappings else []
        )

        learned_ids: set[str] = set()
        families: list[dict] = []
        changed = False

        for app in apps:
            dataset = dataset_by_id.get(str(app.dataset_id))
            if dataset is None:
                continue

            applied_at = app.applied_at or app.updated_at or datetime.utcnow()
            if applied_at.tzinfo is not None:
                applied_at = applied_at.replace(tzinfo=None)
            deployment = dict(dataset.deployment_json or {})
            mapped_ids = {
                str(value)
                for value in (deployment.get("source_group_case_ids") or [])
                if value
            }

            source_row = source_by_id.get(str(dataset.source_case_id or ""))
            source_dict = _case_dict(source_row) if source_row is not None else {}

            # Always reconcile, even when a mapping already exists. Older builds could
            # persist only the representative source_case_id. Applying a Dataset teaches
            # the whole error family that existed at application time, so all historical
            # same-family rows belong to the learned snapshot. Cases after applied_at are
            # deliberately excluded and remain visible as true recurrences.
            reconciled_ids = set(mapped_ids)
            if repair_mappings and source_row is not None:
                for row in all_cases:
                    candidate = _case_dict(row)
                    if (
                        str(candidate.get("status") or "").lower() != "rejected"
                        and _case_time(candidate) <= applied_at
                        and collection._same_family(source_dict, candidate)
                    ):
                        reconciled_ids.add(str(row.id))
            if dataset.source_case_id:
                reconciled_ids.add(str(dataset.source_case_id))

            if repair_mappings and (reconciled_ids != mapped_ids or not deployment.get("source_group_key")):
                deployment["source_case_id"] = str(dataset.source_case_id or "")
                deployment["source_group_case_ids"] = sorted(reconciled_ids)
                deployment["source_group_key"] = _group_key(reconciled_ids) if reconciled_ids else ""
                deployment["source_group_mapped_at"] = datetime.utcnow().isoformat()
                deployment["source_group_mapping_version"] = 2
                deployment["source_group_mapping_reconciled"] = True
                deployment["source_group_mapping_case_count"] = len(reconciled_ids)
                dataset.deployment_json = deployment
                changed = True
                repaired += 1

            mapped_ids = reconciled_ids
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

    return learned_ids, families, repaired


async def backfill_current_pc_learning_group_mappings() -> dict:
    """Repair missing or incomplete group mappings for already-applied Datasets.

    Safe to call repeatedly. It never adds cases that happened after the Dataset's current
    PC application time, so genuine post-learning recurrences remain actionable.
    """
    learned_ids, families, repaired = await _current_pc_learned_case_ids(repair_mappings=True)
    return {
        "ok": True,
        "pc_name": current_pc_name(),
        "repaired_dataset_count": repaired,
        "backfilled_dataset_count": repaired,
        "learned_case_count": len(learned_ids),
        "learned_family_count": len(families),
    }


async def list_aggregated_misjudgment_cases_current_pc_unlearned_only(
    provider: str = "",
    status: str = "",
    limit: int = 500,
) -> dict:
    result = await _original_list_aggregated_misjudgment_cases(provider, status, limit)
    learned_case_ids, learned_families, repaired = await _current_pc_learned_case_ids(repair_mappings=False)

    aggregated = list(result.get("items") or [])
    all_group_ids: set[str] = set()
    for item in aggregated:
        ids = item.get("group_case_ids") or [item.get("id")]
        all_group_ids.update(str(value) for value in ids if value)

    pc_name = current_pc_name()
    async with SessionLocal() as session:
        member_rows = (
            await session.execute(
                select(LlmMisjudgmentCase).where(LlmMisjudgmentCase.id.in_(all_group_ids))
            )
        ).scalars().all() if all_group_ids else []

        # Learning data is shared across PCs. Load it once and correlate every visible
        # error group using explicit case mapping first, then same-family compatibility
        # matching for legacy Datasets.
        all_datasets = (
            await session.execute(select(LlmLearningDataset))
        ).scalars().all()
        dataset_source_ids = {
            str(row.source_case_id) for row in all_datasets if row.source_case_id
        }
        dataset_source_rows = (
            await session.execute(
                select(LlmMisjudgmentCase).where(LlmMisjudgmentCase.id.in_(dataset_source_ids))
            )
        ).scalars().all() if dataset_source_ids else []
        dataset_source_by_id = {str(row.id): _case_dict(row) for row in dataset_source_rows}

        pc_apps = (
            await session.execute(
                select(LlmLearningPcApplication).where(
                    LlmLearningPcApplication.pc_name == pc_name
                )
            )
        ).scalars().all()
        pc_app_by_dataset = {str(row.dataset_id): row for row in pc_apps if row.dataset_id}

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

            # Primary rule: exact case-id mapping reconciled from applied Datasets.
            if member_id and member_id in learned_case_ids:
                hidden_learned_members += 1
                continue

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

        # Determine whether reusable learning data already exists for this error family.
        # Exact group membership is preferred. Same-family matching keeps old Datasets
        # useful until group_id becomes a first-class relational key.
        original_group_ids = set(group_ids)
        matched_datasets: list[LlmLearningDataset] = []
        for dataset in all_datasets:
            deployment = dict(dataset.deployment_json or {})
            mapped_case_ids = {
                str(value)
                for value in (deployment.get("source_group_case_ids") or [])
                if value
            }
            exact_match = bool(
                (dataset.source_case_id and str(dataset.source_case_id) in original_group_ids)
                or mapped_case_ids.intersection(original_group_ids)
            )
            source_dict = dataset_source_by_id.get(str(dataset.source_case_id or "")) or {}
            family_match = bool(
                source_dict and collection._same_family(source_dict, representative)
            )
            if exact_match or family_match:
                matched_datasets.append(dataset)

        dataset_ids = [str(row.id) for row in matched_datasets]
        problem_count = sum(_problem_count(row) for row in matched_datasets)
        applied_apps = [
            pc_app_by_dataset[dataset_id]
            for dataset_id in dataset_ids
            if dataset_id in pc_app_by_dataset
            and bool(pc_app_by_dataset[dataset_id].installed)
            and bool(pc_app_by_dataset[dataset_id].enabled)
        ]
        exact_source_datasets = [
            row for row in matched_datasets
            if str(row.source_case_id or "") == str(representative.get("id") or "")
        ]
        representative["learning_data_exists"] = bool(matched_datasets and problem_count > 0)
        representative["learning_dataset_exists"] = bool(matched_datasets)
        # v5.442 distinguishes a same-family reusable Dataset from a Dataset that is
        # directly anchored to the exact visible representative ID. This lets users
        # recover legacy collections that were accidentally generated from a different
        # same-family raw case without creating duplicates once the exact ID is repaired.
        representative["learning_exact_source_dataset_exists"] = bool(exact_source_datasets)
        representative["learning_exact_source_dataset_ids"] = [str(row.id) for row in exact_source_datasets]
        representative["learning_dataset_count"] = len(matched_datasets)
        representative["learning_problem_count"] = problem_count
        representative["learning_dataset_ids"] = dataset_ids
        representative["learning_data_current_pc_applied"] = bool(applied_apps)
        representative["learning_data_label"] = (
            f"학습 데이터 있음 · Dataset {len(matched_datasets)}개 · 문제 {problem_count}개"
            if matched_datasets and problem_count > 0
            else (
                f"Dataset 있음 · 문제 0개"
                if matched_datasets
                else "학습 데이터 없음"
            )
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
    result["current_pc_learned_case_count"] = len(learned_case_ids)
    result["current_pc_learned_family_count"] = len(learned_families)
    result["legacy_group_mapping_backfilled"] = repaired
    result["group_mapping_repaired_dataset_count"] = repaired
    result["hidden_learned_member_count"] = hidden_learned_members
    result["hidden_learned_group_count"] = hidden_learned_groups
    result["visible_scope"] = "explicit_group_key_unlearned_or_recurrence_only"
    result["visible_scope_label"] = "현재 PC 미학습 또는 학습 후 재발 오판만 표시"
    result["visible_confidence_min"] = 0.75
    return result


# learning_routes imports the function after main imports this bridge.
collection.list_aggregated_misjudgment_cases = list_aggregated_misjudgment_cases_current_pc_unlearned_only
