from __future__ import annotations

import asyncio
import json
import os
import random
import re
import subprocess
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from app.core.config import get_settings
from app.services.active_ollama_model_service import BASE_MODEL_NAME, resolve_active_ollama_model
from app.core.database import SessionLocal
from app.core.machine_identity import current_pc_name
from app.models.learning_entities import LlmLearningDataset, LlmLearningProblem, LlmMisjudgmentCase
from app.services.llm_provider import get_chat_model
from app.services.llm_usage_service import UsageTrackedChatModel, llm_history_log_path


_CORRECTION_MARKERS = (
    "아니", "잘못", "틀렸", "다시", "수정해", "요청했는데", "왜", "안된다", "안돼",
    "incorrect", "wrong", "fix", "retry", "not what", "instead",
)
_ERROR_MARKERS = ("error", "exception", "traceback", "실패", "오류", "invalid", "not found")
_ALLOWED_CASE_STATUS = {"candidate", "confirmed", "rejected"}
_ALLOWED_DATASET_STATUS = {"draft", "review", "validated", "training", "trained", "deployed"}

# True QLoRA/adapter pipeline remains explicitly compatible with Qwen3.5-4B.
# This is separate from AgentStudio's current runtime/recommended Qwen model.
WEIGHT_TRAINING_OLLAMA_BASE_MODEL = "qwen3.5:4b"
WEIGHT_TRAINING_HF_BASE_MODEL = "Qwen/Qwen3.5-4B"


def _artifact_dir() -> Path:
    override = str(os.environ.get("THEANOVA_AGENTSTUDIO_DATA_DIR") or "").strip()
    if override:
        root = Path(os.path.expanduser(override)).resolve()
    else:
        local = str(os.environ.get("LOCALAPPDATA") or "").strip()
        root = Path(local) / "THEANOVA" / "AgentStudio" if local else Path.home() / ".theanova" / "AgentStudio"
    path = root / "learning"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten_text(item) for item in value)
    return str(value)


def _safe_excerpt(value: Any, limit: int = 2400) -> str:
    return re.sub(r"\s+", " ", _flatten_text(value)).strip()[:limit]


def _history_rows(limit: int = 4000) -> list[dict]:
    """Read this PC's local LLM exchange log; candidates are persisted to the shared DB."""
    path = llm_history_log_path()
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    rows.sort(key=lambda row: str(row.get("timestamp") or ""))
    return rows[-max(1, int(limit)):]


def _candidate_reason(row: dict, next_row: dict | None) -> tuple[str, float] | None:
    if str(row.get("status") or "").lower() == "error":
        return "llm_or_tool_error", 0.96
    response_text = _safe_excerpt(row.get("response"), 1600).casefold()
    if any(marker in response_text for marker in _ERROR_MARKERS):
        return "error_signal_in_response", 0.72
    if next_row and str(next_row.get("thread_id") or "") == str(row.get("thread_id") or ""):
        next_request = _safe_excerpt(next_row.get("request"), 1600).casefold()
        if any(marker in next_request for marker in _CORRECTION_MARKERS):
            return "user_correction_after_response", 0.86
    return None


def _case_dict(row: LlmMisjudgmentCase) -> dict:
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
        "status": row.status,
        "provider": row.provider,
        "model": row.model,
        "task": row.task,
        "project_root": row.project_root,
        "thread_id": row.thread_id,
        "source_exchange_id": row.source_exchange_id,
        "source_pc_name": row.source_pc_name,
        "updated_by_pc_name": row.updated_by_pc_name,
        "detection_reason": row.detection_reason,
        "confidence": row.confidence,
        "user_request": row.user_request,
        "wrong_output": row.wrong_output,
        "correction_evidence": row.correction_evidence,
        "expected_output": row.expected_output,
        "error_type": row.error_type,
        "error_reason": row.error_reason,
        "domain": row.domain,
        "topic": row.topic,
        "training_eligible": row.training_eligible,
    }


def _dataset_dict(row: LlmLearningDataset, problems: list[dict] | None = None) -> dict:
    resolved_problems = list(problems if problems is not None else (row.problems_json or []))
    resolved_count = len([item for item in resolved_problems if isinstance(item, dict)])
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
        "status": row.status,
        "source_case_id": row.source_case_id,
        "source_pc_name": row.source_pc_name,
        "updated_by_pc_name": row.updated_by_pc_name,
        "provider": row.provider,
        "source_provider": row.source_provider,
        "source_model": row.source_model,
        "scope": row.scope_json or {},
        "target_count": row.target_count,
        "problem_count": resolved_count or int(row.problem_count or 0),
        "problems": resolved_problems,
        "validation": row.validation_json or {},
        "split": row.split_json or {},
        "training": row.training_json or {},
        "evaluation": row.evaluation_json or {},
        "deployment": row.deployment_json or {},
    }


def _normalized_problem_dict(row: LlmLearningProblem) -> dict:
    return {
        # problem_key is the stable logical ID used by legacy validation/UI. The DB row
        # id remains available for diagnostics without changing the public contract.
        "id": str(row.problem_key or row.id),
        "db_id": str(row.id),
        "source_case_id": str(row.source_case_id or ""),
        "instruction": str(row.instruction or ""),
        "input": str(row.input_text or ""),
        "output": str(row.output_text or ""),
        "domain": str(row.domain or ""),
        "topic": str(row.topic or ""),
        "subtopic": str(row.subtopic or ""),
        "difficulty": str(row.difficulty or "medium"),
        "problem_type": str(row.problem_type or "scenario"),
        "validated": bool(row.validated),
    }


def _legacy_problem_key(problem: dict, index: int) -> str:
    value = str(problem.get("id") or problem.get("problem_key") or "").strip()
    return value or f"legacy-{index + 1}"


async def ensure_dataset_problem_storage(dataset_id: str) -> dict:
    """Reconcile legacy Dataset JSON and normalized problem rows for one Dataset.

    v5.439 makes the relational ``llm_learning_problems`` rows authoritative for reads,
    while keeping ``problems_json`` populated for older training/validation code. A
    collection job is only considered complete after this reconciliation succeeds.
    """
    async with SessionLocal() as session:
        dataset = await session.get(LlmLearningDataset, str(dataset_id or ""))
        if dataset is None:
            raise KeyError("Dataset을 찾을 수 없습니다.")

        normalized = (
            await session.execute(
                select(LlmLearningProblem)
                .where(LlmLearningProblem.dataset_id == dataset.id)
                .order_by(LlmLearningProblem.created_at.asc(), LlmLearningProblem.id.asc())
            )
        ).scalars().all()
        legacy = [item for item in list(dataset.problems_json or []) if isinstance(item, dict)]
        changed = False

        if legacy:
            existing_keys = {str(row.problem_key or "") for row in normalized}
            for index, problem in enumerate(legacy):
                problem_key = _legacy_problem_key(problem, index)
                if problem_key in existing_keys:
                    continue
                row = LlmLearningProblem(
                    id=uuid.uuid4().hex,
                    dataset_id=dataset.id,
                    group_id=str(getattr(dataset, "group_id", "") or ""),
                    source_case_id=str(dataset.source_case_id or ""),
                    problem_key=problem_key,
                    instruction=str(problem.get("instruction") or ""),
                    input_text=str(problem.get("input") or ""),
                    output_text=str(problem.get("output") or ""),
                    domain=str(problem.get("domain") or (dataset.scope_json or {}).get("domain") or ""),
                    topic=str(problem.get("topic") or (dataset.scope_json or {}).get("topic") or ""),
                    subtopic=str(problem.get("subtopic") or ""),
                    difficulty=str(problem.get("difficulty") or "medium"),
                    problem_type=str(problem.get("problem_type") or "scenario"),
                    validated=bool(problem.get("validated")),
                )
                session.add(row)
                normalized.append(row)
                existing_keys.add(problem_key)
                changed = True
            if changed:
                await session.flush()

        if normalized:
            hydrated = [_normalized_problem_dict(row) for row in normalized]
            # Keep the legacy JSON mirror alive because validation/curriculum paths from
            # older projects still read it. Do not allow a normalized-only Dataset to
            # look empty in the UI.
            legacy_keys = {_legacy_problem_key(item, index) for index, item in enumerate(legacy)}
            normalized_keys = {str(item.get("id") or "") for item in hydrated}
            if not legacy or legacy_keys != normalized_keys or len(legacy) != len(hydrated):
                dataset.problems_json = hydrated
                changed = True
            if int(dataset.problem_count or 0) != len(hydrated):
                dataset.problem_count = len(hydrated)
                changed = True
            validation = dict(dataset.validation_json or {})
            if str(dataset.status or "") == "review":
                approved = sum(1 for item in hydrated if bool(item.get("validated")))
                expected = {"approved": approved, "rejected": 0, "pending": max(0, len(hydrated) - approved)}
                if any(int(validation.get(key) or 0) != value for key, value in expected.items()):
                    validation.update(expected)
                    dataset.validation_json = validation
                    changed = True
            if changed:
                dataset.updated_by_pc_name = current_pc_name()
                await session.commit()
                await session.refresh(dataset)
            return {
                "ok": True,
                "dataset": _dataset_dict(dataset, hydrated),
                "problem_count": len(hydrated),
                "problem_storage": "relational+legacy_mirror",
                "reconciled": changed,
            }

        # A Dataset with no problem rows and no JSON is genuinely empty. Returning this
        # explicitly lets the job fail instead of announcing a false successful collection.
        if int(dataset.problem_count or 0) != 0:
            dataset.problem_count = 0
            dataset.updated_by_pc_name = current_pc_name()
            await session.commit()
            await session.refresh(dataset)
        return {
            "ok": True,
            "dataset": _dataset_dict(dataset, []),
            "problem_count": 0,
            "problem_storage": "empty",
            "reconciled": changed,
        }


async def sync_misjudgment_candidates() -> dict:
    """Collect this PC's suspicious exchanges into the common runtime DB.

    The DB record is global. PC name is provenance only and is never used as a read filter.
    """
    rows = await asyncio.to_thread(_history_rows)
    pc_name = current_pc_name()
    added = 0
    async with SessionLocal() as session:
        existing = set((await session.execute(select(LlmMisjudgmentCase.source_key))).scalars().all())
        for index, row in enumerate(rows):
            source_id = str(row.get("id") or "")
            if not source_id:
                continue
            source_key = f"{pc_name}::{source_id}"
            if source_key in existing:
                continue
            next_row = rows[index + 1] if index + 1 < len(rows) else None
            signal = _candidate_reason(row, next_row)
            if not signal:
                continue
            reason, confidence = signal
            session.add(LlmMisjudgmentCase(
                id=uuid.uuid4().hex,
                source_key=source_key,
                source_pc_name=pc_name,
                updated_by_pc_name=pc_name,
                status="candidate",
                provider=str(row.get("provider") or "unknown"),
                model=str(row.get("model") or "unknown"),
                task=str(row.get("task") or ""),
                project_root=str(row.get("project_root") or ""),
                thread_id=str(row.get("thread_id") or ""),
                source_exchange_id=source_id,
                detection_reason=reason,
                confidence=confidence,
                user_request=_safe_excerpt(row.get("request")),
                wrong_output=_safe_excerpt(row.get("response") or row.get("error")),
                correction_evidence=(
                    _safe_excerpt(next_row.get("request"))
                    if reason == "user_correction_after_response" and next_row else ""
                ),
                expected_output="",
                error_type="unclassified",
                error_reason="",
                domain="",
                topic="",
                training_eligible=False,
            ))
            existing.add(source_key)
            added += 1
        await session.commit()
        total = int((await session.execute(select(func.count()).select_from(LlmMisjudgmentCase))).scalar() or 0)
    return {"ok": True, "added": added, "total": total, "scanned": len(rows), "storage": "runtime_db_shared", "source_pc_name": pc_name}


async def list_misjudgment_cases(provider: str = "", status: str = "", limit: int = 500) -> dict:
    await sync_misjudgment_candidates()
    async with SessionLocal() as session:
        stmt = select(LlmMisjudgmentCase)
        if provider:
            stmt = stmt.where(LlmMisjudgmentCase.provider == provider)
        if status:
            stmt = stmt.where(LlmMisjudgmentCase.status == status)
        stmt = stmt.order_by(LlmMisjudgmentCase.updated_at.desc()).limit(max(1, min(int(limit or 500), 2000)))
        rows = (await session.execute(stmt)).scalars().all()
        total_stmt = select(func.count()).select_from(LlmMisjudgmentCase)
        if provider:
            total_stmt = total_stmt.where(LlmMisjudgmentCase.provider == provider)
        if status:
            total_stmt = total_stmt.where(LlmMisjudgmentCase.status == status)
        total = int((await session.execute(total_stmt)).scalar() or 0)
    providers: dict[str, int] = {}
    items = [_case_dict(row) for row in rows]
    for row in items:
        key = f"{row.get('provider','unknown')}::{row.get('model','unknown')}"
        providers[key] = providers.get(key, 0) + 1
    return {"ok": True, "items": items, "total": total, "providers": providers, "storage": "runtime_db_shared"}


async def review_misjudgment_case(case_id: str, patch: dict) -> dict:
    async with SessionLocal() as session:
        target = await session.get(LlmMisjudgmentCase, case_id)
        if not target:
            raise KeyError("오판 후보를 찾을 수 없습니다.")
        status = str(patch.get("status") or target.status or "candidate").lower()
        if status not in _ALLOWED_CASE_STATUS:
            raise ValueError("지원하지 않는 오판 검토 상태입니다.")
        for key in ("expected_output", "error_type", "error_reason", "domain", "topic"):
            if key in patch:
                setattr(target, key, str(patch.get(key) or "").strip())
        target.status = status
        target.training_eligible = status == "confirmed" and bool(str(target.expected_output or "").strip())
        target.updated_by_pc_name = current_pc_name()
        await session.commit()
        await session.refresh(target)
        return {"ok": True, "item": _case_dict(target), "storage": "runtime_db_shared"}


async def add_manual_misjudgment_case(payload: dict) -> dict:
    pc_name = current_pc_name()
    row = LlmMisjudgmentCase(
        id=uuid.uuid4().hex,
        source_key=f"manual::{uuid.uuid4().hex}",
        source_pc_name=pc_name,
        updated_by_pc_name=pc_name,
        status="candidate",
        provider=str(payload.get("provider") or "unknown").strip().lower(),
        model=str(payload.get("model") or "unknown").strip(),
        task=str(payload.get("task") or "manual"),
        project_root=str(payload.get("project_root") or ""),
        thread_id="",
        source_exchange_id="",
        detection_reason="manual",
        confidence=1.0,
        user_request=str(payload.get("user_request") or "").strip(),
        wrong_output=str(payload.get("wrong_output") or "").strip(),
        correction_evidence=str(payload.get("correction_evidence") or "").strip(),
        expected_output=str(payload.get("expected_output") or "").strip(),
        error_type=str(payload.get("error_type") or "unclassified"),
        error_reason=str(payload.get("error_reason") or ""),
        domain=str(payload.get("domain") or ""),
        topic=str(payload.get("topic") or ""),
        training_eligible=False,
    )
    async with SessionLocal() as session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return {"ok": True, "item": _case_dict(row), "storage": "runtime_db_shared"}


def _parse_json_payload(text: str) -> Any:
    value = str(text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.I)
        value = re.sub(r"\s*```$", "", value)
    starts = [pos for pos in (value.find("{"), value.find("[")) if pos >= 0]
    if starts:
        value = value[min(starts):]
    for end_char in ("}", "]"):
        end = value.rfind(end_char)
        if end >= 0:
            try:
                return json.loads(value[: end + 1])
            except Exception:
                pass
    return json.loads(value)


def _learning_model(provider: str = "ollama") -> UsageTrackedChatModel:
    return UsageTrackedChatModel(get_chat_model(provider), provider, "llm_learning_dataset_generation")


def analyze_learning_scope(case: dict, provider: str = "ollama") -> dict:
    prompt = f"""당신은 THEANOVA AgentStudio의 LLM 학습 데이터 설계 Validator입니다.
아래 확정 오판 한 건의 취약한 지식/판단 범위를 넓게 정의하세요. JSON 객체만 반환하세요.
필드: domain, topic, root_cause, learning_objective, subtopics(6~15개), variation_axes(5~10개), pitfalls(5~10개), prerequisites(0~8개).
사용자 요청: {case.get('user_request','')}
잘못된 결과: {case.get('wrong_output','')}
기대 결과: {case.get('expected_output','')}
오류 유형: {case.get('error_type','')}
오류 원인: {case.get('error_reason','')}
"""
    result = _learning_model(provider).invoke(prompt)
    parsed = _parse_json_payload(getattr(result, "content", str(result)))
    if not isinstance(parsed, dict):
        raise ValueError("학습 범위 분석 결과가 JSON 객체가 아닙니다.")
    return parsed


def _validate_problem(item: dict) -> dict | None:
    if not isinstance(item, dict):
        return None
    instruction = str(item.get("instruction") or "").strip()
    output = str(item.get("output") or "").strip()
    if len(instruction) < 8 or len(output) < 2:
        return None
    return {
        "id": uuid.uuid4().hex,
        "instruction": instruction,
        "input": str(item.get("input") or "").strip(),
        "output": output,
        "domain": str(item.get("domain") or "").strip(),
        "topic": str(item.get("topic") or "").strip(),
        "subtopic": str(item.get("subtopic") or "").strip(),
        "difficulty": str(item.get("difficulty") or "medium").strip().lower(),
        "problem_type": str(item.get("problem_type") or "scenario").strip().lower(),
        "source": "expanded_from_confirmed_misjudgment",
        "validated": False,
    }


def _generate_problem_batch(case: dict, scope: dict, target_count: int, provider: str) -> list[dict]:
    generated: list[dict] = []
    fingerprints: set[str] = set()
    batch_size = 20
    attempts = 0
    while len(generated) < target_count and attempts < max(4, (target_count // batch_size) + 5):
        attempts += 1
        need = min(batch_size, target_count - len(generated))
        prompt = f"""THEANOVA AgentStudio 학습 데이터 생성기입니다.
확정 오판의 취약 범위를 학습하기 위한 서로 다른 문제 {need}개를 만드세요.
단순 문장 치환 금지. 실제 개발/Agent/Tool/DB/예외 상황을 다양하게 구성하세요.
난이도 easy/medium/hard, 유형 concept/scenario/code/tool_selection/debug/edge_case를 섞으세요.
JSON 배열만 반환하세요. 필드: instruction,input,output,domain,topic,subtopic,difficulty,problem_type.
학습 범위: {json.dumps(scope, ensure_ascii=False)}
사용자 요청={case.get('user_request','')}
잘못된 결과={case.get('wrong_output','')}
기대 결과={case.get('expected_output','')}
"""
        result = _learning_model(provider).invoke(prompt)
        parsed = _parse_json_payload(getattr(result, "content", str(result)))
        if isinstance(parsed, dict):
            parsed = parsed.get("items") or parsed.get("problems") or []
        if not isinstance(parsed, list):
            continue
        for raw in parsed:
            problem = _validate_problem(raw)
            if not problem:
                continue
            fingerprint = re.sub(r"\W+", "", (problem["instruction"] + problem["input"]).casefold())[:600]
            if not fingerprint or fingerprint in fingerprints:
                continue
            fingerprints.add(fingerprint)
            generated.append(problem)
            if len(generated) >= target_count:
                break
    return generated


async def generate_problem_dataset(case_id: str, target_count: int = 100, provider: str = "ollama") -> dict:
    target_count = max(10, min(int(target_count or 100), 2000))
    async with SessionLocal() as session:
        case_row = await session.get(LlmMisjudgmentCase, case_id)
        if not case_row:
            raise KeyError("오판 후보를 찾을 수 없습니다.")
        case = _case_dict(case_row)
    if case.get("status") != "confirmed" or not case.get("training_eligible"):
        raise ValueError("오판이 확정되고 기대 결과가 검증된 경우에만 대량 문제를 생성할 수 있습니다.")
    scope = await asyncio.to_thread(analyze_learning_scope, case, provider)
    generated = await asyncio.to_thread(_generate_problem_batch, case, scope, target_count, provider)
    pc_name = current_pc_name()
    dataset = LlmLearningDataset(
        id=uuid.uuid4().hex,
        source_case_id=case_id,
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
        split_json={}, training_json={}, evaluation_json={}, deployment_json={},
    )
    async with SessionLocal() as session:
        session.add(dataset)
        await session.commit()
        await session.refresh(dataset)
    return {"ok": True, "dataset": _dataset_dict(dataset), "storage": "runtime_db_shared"}


async def list_datasets() -> dict:
    """Fast, read-only shared Dataset list.

    v5.445 no longer runs one repair transaction per Dataset whenever the Learning
    Center is opened.  Relational/legacy reconciliation already runs at AgentStudio
    startup and immediately after Dataset creation, so normal list reads can load all
    Dataset/problem rows in two bulk queries.
    """
    async with SessionLocal() as session:
        dataset_rows = (
            await session.execute(
                select(LlmLearningDataset).order_by(LlmLearningDataset.updated_at.desc())
            )
        ).scalars().all()
        problem_rows = (
            await session.execute(
                select(LlmLearningProblem).order_by(
                    LlmLearningProblem.dataset_id.asc(),
                    LlmLearningProblem.created_at.asc(),
                    LlmLearningProblem.id.asc(),
                )
            )
        ).scalars().all()

    problems_by_dataset: dict[str, list[dict]] = {}
    for problem in problem_rows:
        problems_by_dataset.setdefault(str(problem.dataset_id), []).append(_normalized_problem_dict(problem))

    items: list[dict] = []
    empty = 0
    for dataset in dataset_rows:
        normalized = problems_by_dataset.get(str(dataset.id), [])
        # Relational rows are authoritative when present. Legacy JSON remains a safe
        # fallback for a Dataset created by an older process before startup repair.
        resolved = normalized if normalized else [item for item in list(dataset.problems_json or []) if isinstance(item, dict)]
        item = _dataset_dict(dataset, resolved)
        items.append(item)
        empty += int(int(item.get("problem_count") or 0) <= 0)

    return {
        "ok": True,
        "items": items,
        "total": len(items),
        "storage": "runtime_db_shared",
        "problem_storage": "relational_authoritative_with_legacy_mirror",
        "repaired_dataset_count": 0,
        "empty_dataset_count": empty,
        "read_mode": "bulk_read_only",
        "repair_policy": "startup_and_dataset_write_path",
    }


async def validate_dataset(dataset_id: str, approved_problem_ids: list[str] | None = None) -> dict:
    await ensure_dataset_problem_storage(dataset_id)
    async with SessionLocal() as session:
        dataset = await session.get(LlmLearningDataset, dataset_id)
        if not dataset:
            raise KeyError("Dataset을 찾을 수 없습니다.")
        problems = list(dataset.problems_json or [])
        approved_set = set(approved_problem_ids or []) or {str(item.get("id")) for item in problems}
        approved = 0
        for problem in problems:
            problem["validated"] = str(problem.get("id")) in approved_set
            approved += int(bool(problem["validated"]))
        if approved < 10:
            raise ValueError("검증 완료 문제는 최소 10개 이상이어야 합니다.")
        normalized_rows = (
            await session.execute(
                select(LlmLearningProblem).where(LlmLearningProblem.dataset_id == dataset.id)
            )
        ).scalars().all()
        for row in normalized_rows:
            row.validated = str(row.problem_key or row.id) in approved_set
        dataset.problems_json = problems
        dataset.status = "validated"
        dataset.validation_json = {"approved": approved, "rejected": len(problems) - approved, "pending": 0}
        dataset.updated_by_pc_name = current_pc_name()
        await session.commit()
        await session.refresh(dataset)
        return {"ok": True, "dataset": _dataset_dict(dataset), "storage": "runtime_db_shared"}


def _split_items(items: list[dict], seed: int = 5413) -> tuple[list[dict], list[dict], list[dict]]:
    values = list(items)
    random.Random(seed).shuffle(values)
    count = len(values)
    train_end = max(1, int(count * 0.8))
    validation_end = min(count, train_end + max(1, int(count * 0.1)))
    return values[:train_end], values[train_end:validation_end], values[validation_end:]


async def prepare_training(dataset_id: str, base_model: str = "") -> dict:
    settings = get_settings()
    async with SessionLocal() as session:
        dataset = await session.get(LlmLearningDataset, dataset_id)
        if not dataset:
            raise KeyError("Dataset을 찾을 수 없습니다.")
        if dataset.status != "validated":
            raise ValueError("검증 완료(validated) Dataset만 학습 단계로 이동할 수 있습니다.")
        items = [item for item in (dataset.problems_json or []) if item.get("validated")]
        train, validation, test = _split_items(items)
        out = _artifact_dir() / "datasets" / dataset_id
        out.mkdir(parents=True, exist_ok=True)
        for name, rows in (("train", train), ("validation", validation), ("test", test)):
            with (out / f"{name}.jsonl").open("w", encoding="utf-8") as handle:
                for item in rows:
                    handle.write(json.dumps({"instruction": item["instruction"], "input": item.get("input", ""), "output": item["output"]}, ensure_ascii=False) + "\n")
        selected_base = str(base_model or WEIGHT_TRAINING_OLLAMA_BASE_MODEL)
        hf_base = {WEIGHT_TRAINING_OLLAMA_BASE_MODEL.casefold(): WEIGHT_TRAINING_HF_BASE_MODEL}.get(selected_base.casefold(), selected_base)
        manifest = {
            "dataset_id": dataset_id,
            "prepared_by_pc_name": current_pc_name(),
            "ollama_base_model": selected_base,
            "training_base_model": hf_base,
            "method": "QLoRA",
            "split": {"train": len(train), "validation": len(validation), "test": len(test)},
            "dataset_dir": str(out),
            "adapter_dir": str(out / "adapter"),
            "artifact_scope": "local_pc",
            "dataset_scope": "runtime_db_shared",
            "gate": "evaluation_pass_required_before_ollama_apply",
        }
        (out / "training_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        dataset.status = "training"
        dataset.split_json = manifest["split"]
        dataset.training_json = manifest
        dataset.updated_by_pc_name = current_pc_name()
        await session.commit()
        return {"ok": True, "manifest": manifest, "storage": "runtime_db_shared"}


async def record_evaluation(dataset_id: str, baseline_score: float, trained_score: float, minimum_gain: float = 0.03) -> dict:
    async with SessionLocal() as session:
        dataset = await session.get(LlmLearningDataset, dataset_id)
        if not dataset:
            raise KeyError("Dataset을 찾을 수 없습니다.")
        baseline = float(baseline_score)
        trained = float(trained_score)
        gain = trained - baseline
        passed = trained >= baseline and gain >= float(minimum_gain)
        evaluation = {"baseline_score": baseline, "trained_score": trained, "gain": gain, "minimum_gain": float(minimum_gain), "passed": passed, "evaluated_by_pc_name": current_pc_name()}
        dataset.evaluation_json = evaluation
        dataset.status = "trained" if passed else "validated"
        dataset.updated_by_pc_name = current_pc_name()
        await session.commit()
        return {"ok": True, "passed": passed, "evaluation": evaluation, "storage": "runtime_db_shared"}


def _apply_ollama_local(base_model: str, adapter: Path, model_name: str, dataset_id: str) -> dict:
    model_dir = _artifact_dir() / "models" / dataset_id
    model_dir.mkdir(parents=True, exist_ok=True)
    modelfile = model_dir / "Modelfile"
    modelfile.write_text(f"FROM {base_model}\nADAPTER {adapter}\nPARAMETER temperature 0\n", encoding="utf-8")
    completed = subprocess.run(["ollama", "create", model_name, "-f", str(modelfile)], capture_output=True, text=True, timeout=600, check=False)
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "ollama create 실패").strip())
    return {"model_name": model_name, "base_model": base_model, "adapter_path": str(adapter), "applied_pc_name": current_pc_name(), "stdout": (completed.stdout or "")[-2000:]}


async def apply_to_ollama(dataset_id: str, model_name: str, adapter_path: str = "") -> dict:
    async with SessionLocal() as session:
        dataset = await session.get(LlmLearningDataset, dataset_id)
        if not dataset:
            raise KeyError("Dataset을 찾을 수 없습니다.")
        if not bool((dataset.evaluation_json or {}).get("passed")):
            raise ValueError("기존 모델 대비 평가 Gate를 통과한 학습 모델만 Ollama에 적용할 수 있습니다.")
        training = dict(dataset.training_json or {})
        adapter = Path(adapter_path or training.get("adapter_dir") or "")
        if not adapter.exists():
            raise ValueError("학습 Adapter 경로가 이 PC에 존재하지 않습니다. Dataset은 공용이지만 학습 산출물은 PC 로컬 파일입니다.")
        base_model = str(training.get("ollama_base_model") or WEIGHT_TRAINING_OLLAMA_BASE_MODEL)
        deployment = await asyncio.to_thread(_apply_ollama_local, base_model, adapter, model_name, dataset_id)
        dataset.status = "deployed"
        dataset.deployment_json = deployment
        dataset.updated_by_pc_name = current_pc_name()
        await session.commit()
        return {"ok": True, "deployment": deployment, "storage": "runtime_db_shared"}


async def learning_summary() -> dict:
    # v5.445: summary GET is read-only. History -> misjudgment synchronization runs at
    # AgentStudio startup and only when the operator presses `오판 수집`.
    async with SessionLocal() as session:
        case_counts = {}
        for status in _ALLOWED_CASE_STATUS:
            case_counts[status] = int((await session.execute(select(func.count()).select_from(LlmMisjudgmentCase).where(LlmMisjudgmentCase.status == status))).scalar() or 0)
        dataset_counts = {}
        for status in _ALLOWED_DATASET_STATUS:
            dataset_counts[status] = int((await session.execute(select(func.count()).select_from(LlmLearningDataset).where(LlmLearningDataset.status == status))).scalar() or 0)
    settings = get_settings()
    active_ollama = await resolve_active_ollama_model()
    return {
        "ok": True,
        "cases": case_counts,
        "datasets": dataset_counts,
        "current_ollama_model": str(active_ollama.get("active_model") or BASE_MODEL_NAME),
        "current_strategy": settings.ai_provider_strategy,
        "storage": "runtime_db_shared",
        "shared_across_pcs": True,
        "current_pc_name": current_pc_name(),
        "artifact_dir": str(_artifact_dir()),
        "note": "오판/문제/Dataset/검증/평가 메타데이터는 공용 Runtime DB에 저장됩니다. QLoRA adapter 같은 대용량 학습 산출물만 실행 PC 로컬 파일로 유지됩니다.",
        "safety_gate": "confirmed case -> validated dataset -> evaluation pass -> ollama apply",
    }
