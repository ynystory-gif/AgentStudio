from __future__ import annotations

import uuid

from app.core.machine_identity import current_pc_name
from app.models.learning_entities import LlmLearningDataset, LlmMisjudgmentCase
from app.services import learning_collection_service as collection
from app.services.learning_teacher_router_v2 import (
    generate_dataset_with_priority_v2,
    get_latest_generation_progress,
)
from app.services.llm_learning_service import _case_dict


async def _generate_candidate_dataset_with_priority(
    case_row: LlmMisjudgmentCase,
    target_count: int,
    provider: str = "auto",
) -> LlmLearningDataset:
    """Generate a shared Dataset using AgentStudio's configured provider priority.

    The legacy ``provider`` argument is intentionally ignored. Existing frontend/API
    callers may still send provider=ollama, but learning generation follows the
    high-level provider order configured for AgentStudio.
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
    metrics = dict(generated.get("generation_metrics") or {})
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
            "generation_metrics": metrics,
        },
    )


_original_get_problem_collection_job = collection.get_problem_collection_job


async def _get_problem_collection_job_with_generation_progress(job_id: str) -> dict:
    """Keep the existing job API while adding live Teacher/batch/ETA metrics."""
    job = await _original_get_problem_collection_job(job_id)
    if str(job.get("status") or "") == "running":
        detail = get_latest_generation_progress()
        if detail:
            merged = dict(job)
            merged["generation"] = detail
            if detail.get("message"):
                merged["message"] = str(detail["message"])
            target = max(1, int(detail.get("target_count") or job.get("target_per_topic") or 1))
            generated = max(0, min(target, int(detail.get("generated_count") or 0)))
            current_topic = max(1, int(job.get("current_topic") or 1))
            total_topics = max(1, int(job.get("total_topics") or 1))
            # Preserve topic-level progress while making progress move inside the current topic.
            topic_fraction = generated / target
            overall_fraction = ((current_topic - 1) + topic_fraction) / total_topics
            merged["progress"] = max(int(job.get("progress") or 0), min(99, 10 + int(overall_fraction * 80)))
            return merged
    return job


# Patch the single internal hook used by synchronous and Job-based problem collection.
collection._generate_candidate_dataset = _generate_candidate_dataset_with_priority
# The API imports this function from the collection module after the bridge is loaded in main.py.
collection.get_problem_collection_job = _get_problem_collection_job_with_generation_progress
