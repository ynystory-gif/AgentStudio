from __future__ import annotations

"""Prevent AgentStudio's own learning/Teacher calls from becoming new misjudgments.

Learning generation, validation and Teacher calls are implementation telemetry, not
user-facing tasks. If they are fed back into the misjudgment collector the system can
recursively learn from its own prompts and pollute the queue.
"""

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.learning_entities import LlmMisjudgmentCase
from app.services import llm_learning_service as learning

_INTERNAL_TASK_PREFIXES = (
    "llm_learning_",
    "learning_teacher_",
    "learning_validator_",
    "learning_dataset_",
)
_INTERNAL_REQUEST_MARKERS = (
    "llm_learning_teacher_generation",
    "llm_learning_dataset_generation",
    "llm_learning_scope_analysis",
    "llm_learning_validation",
    "theanova agentstudio의 llm 학습 데이터 설계 teacher",
    "theanova agentstudio의 llm 학습 데이터 설계 validator",
    "theanova agentstudio 학습 데이터 생성기",
)

_original_candidate_reason = learning._candidate_reason
_original_sync_misjudgment_candidates = learning.sync_misjudgment_candidates


def _is_internal_learning_history_row(row: dict) -> bool:
    task = str(row.get("task") or "").strip().casefold()
    if any(task.startswith(prefix) for prefix in _INTERNAL_TASK_PREFIXES):
        return True
    request = learning._safe_excerpt(row.get("request"), 2400).casefold()
    return any(marker in request for marker in _INTERNAL_REQUEST_MARKERS)


def _candidate_reason_without_internal_learning(row: dict, next_row: dict | None):
    if _is_internal_learning_history_row(row):
        return None
    safe_next = None if (next_row and _is_internal_learning_history_row(next_row)) else next_row
    return _original_candidate_reason(row, safe_next)


async def _quarantine_existing_internal_learning_cases() -> int:
    changed = 0
    async with SessionLocal() as session:
        rows = (await session.execute(select(LlmMisjudgmentCase))).scalars().all()
        for row in rows:
            task = str(row.task or "").strip().casefold()
            request = str(row.user_request or "").strip().casefold()
            internal = any(task.startswith(prefix) for prefix in _INTERNAL_TASK_PREFIXES) or any(
                marker in request for marker in _INTERNAL_REQUEST_MARKERS
            )
            if not internal:
                continue
            if row.status != "rejected" or float(row.confidence or 0.0) != 0.0 or row.training_eligible:
                row.status = "rejected"
                row.confidence = 0.0
                row.training_eligible = False
                row.error_reason = "internal_learning_operation_excluded"
                changed += 1
        if changed:
            await session.commit()
    return changed


async def sync_misjudgment_candidates_without_internal_learning() -> dict:
    # The runtime DB may be an older AgentStudio schema. Ensure the relational learning
    # columns/tables exist before any ORM INSERT/SELECT references group_id.
    from app.services.learning_relational_schema_service import ensure_learning_relational_schema

    relational = await ensure_learning_relational_schema()
    result = await _original_sync_misjudgment_candidates()
    quarantined = await _quarantine_existing_internal_learning_cases()
    result["internal_learning_quarantined"] = quarantined
    result["relational_mapping"] = relational
    return result


learning._candidate_reason = _candidate_reason_without_internal_learning
learning.sync_misjudgment_candidates = sync_misjudgment_candidates_without_internal_learning

try:
    from app.services import learning_collection_service as collection
    collection.sync_misjudgment_candidates = sync_misjudgment_candidates_without_internal_learning
except Exception:
    pass
