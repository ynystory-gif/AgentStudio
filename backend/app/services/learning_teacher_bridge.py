from __future__ import annotations

import uuid

from app.core.machine_identity import current_pc_name
from app.models.learning_entities import LlmLearningDataset, LlmMisjudgmentCase
from app.services import learning_collection_service as collection
from app.services.learning_teacher_router_v2 import generate_dataset_with_priority_v2
from app.services.llm_learning_service import _case_dict


async def _generate_candidate_dataset_with_priority(
    case_row: LlmMisjudgmentCase,
    target_count: int,
    provider: str = "auto",
) -> LlmLearningDataset:
    """Generate a shared Dataset using AgentStudio's configured provider priority.

    The legacy ``provider`` argument is intentionally ignored. Existing frontend/API
    callers may still send provider=ollama, but learning generation must follow the
    same high-level provider order configured for AgentStudio instead of pinning one
    provider.
    """
    case = _case_dict(case_row)
    generated = await generate_dataset_with_priority_v2(case, target_count)
    pc_name = current_pc_name()
    teacher = {
        "provider": generated["teacher_provider"],
        "model": generated["teacher_model"],
        "strategy": generated["teacher_strategy"],
        "priority": generated["teacher_priority"],
        "attempts": generated["teacher_attempts"],
    }
    scope = dict(generated.get("scope") or {})
    scope["_teacher"] = teacher
    problems = list(generated.get("problems") or [])
    return LlmLearningDataset(
        id=uuid.uuid4().hex,
        source_case_id=case_row.id,
        source_pc_name=pc_name,
        updated_by_pc_name=pc_name,
        status="review",
        provider=str(teacher["provider"] or "auto"),
        source_provider=str(case.get("provider") or ""),
        source_model=str(case.get("model") or ""),
        scope_json=scope,
        target_count=target_count,
        problem_count=len(problems),
        problems_json=problems,
        validation_json={
            "approved": 0,
            "rejected": 0,
            "pending": len(problems),
            "teacher_provider": teacher["provider"],
            "teacher_model": teacher["model"],
        },
        split_json={},
        training_json={},
        evaluation_json={},
        deployment_json={
            "source": "problem_collection",
            "requires_validation": True,
            "teacher": teacher,
        },
    )


# Patch the single internal hook used by synchronous and Job-based problem collection.
collection._generate_candidate_dataset = _generate_candidate_dataset_with_priority
