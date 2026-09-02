from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.machine_identity import current_pc_name
from app.models.learning_entities import LlmLearningDataset, LlmLearningPcApplication
from app.services.ollama_model_manager_service import (
    LATEST_RECOMMENDED_MODEL,
    get_recommended_model_status,
    persist_current_ollama_model,
)

_APPLY_JOBS: dict[str, dict] = {}
CUMULATIVE_MODEL_NAME = "theanova-learn:latest"


def _set_job(job_id: str, progress: int, stage: str, message: str, **extra) -> None:
    job = _APPLY_JOBS.setdefault(job_id, {})
    job.update({
        "id": job_id,
        "progress": max(0, min(100, int(progress))),
        "stage": stage,
        "message": message,
        "updated_at": datetime.utcnow().isoformat(),
        **extra,
    })


def _artifact_root() -> Path:
    local = str(os.environ.get("LOCALAPPDATA") or "").strip()
    root = Path(local) / "THEANOVA" / "AgentStudio" if local else Path.home() / ".theanova" / "AgentStudio"
    path = root / "learning" / "applied_models" / "theanova-learn" / "latest"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _clean_text(value: object, limit: int = 6000) -> str:
    return str(value or "").replace("\x00", " ").strip()[:limit]


def _valid_problems(dataset: LlmLearningDataset) -> list[dict]:
    return [
        item for item in list(dataset.problems_json or [])
        if isinstance(item, dict)
        and str(item.get("instruction") or "").strip()
        and str(item.get("output") or "").strip()
    ]


def _problem_fingerprint(item: dict) -> str:
    text = " ".join([
        str(item.get("instruction") or ""),
        str(item.get("input") or ""),
        str(item.get("output") or ""),
    ]).casefold()
    return re.sub(r"\s+", " ", text).strip()[:4000]


def _build_cumulative_curriculum(datasets: list[LlmLearningDataset]) -> tuple[str, dict[str, int]]:
    sections = [
        "THEANOVA AgentStudio 누적 오판 보정 학습 모델입니다.",
        "현재 PC에서 학습 적용된 모든 Dataset을 누적 반영합니다.",
        "아래 학습 규칙과 검증 예시는 참고 우선순위가 높지만, 사용자의 실제 요구사항·현재 프로젝트 파일·도구 실행 결과와 충돌하면 실제 근거를 우선합니다.",
        "같은 유형의 과거 오판을 반복하지 말고, 불확실한 경우 확인·검증 후 답합니다.",
    ]
    seen: set[str] = set()
    counts: dict[str, int] = {}
    global_index = 0

    for dataset_index, dataset in enumerate(datasets, start=1):
        valid = _valid_problems(dataset)
        scope = dict(dataset.scope_json or {})
        sections.extend([
            f"\n=== Dataset {dataset_index}: {dataset.id} ===",
            f"Domain: {_clean_text(scope.get('domain'), 500)}",
            f"Topic: {_clean_text(scope.get('topic'), 800)}",
            f"Learning objective: {_clean_text(scope.get('learning_objective'), 1600)}",
            f"Root cause to avoid: {_clean_text(scope.get('root_cause'), 1600)}",
            "Subtopics: " + json.dumps(scope.get("subtopics") or [], ensure_ascii=False),
            "Pitfalls: " + json.dumps(scope.get("pitfalls") or [], ensure_ascii=False),
            "검증 학습 예시:",
        ])
        included = 0
        for item in valid:
            fingerprint = _problem_fingerprint(item)
            if not fingerprint or fingerprint in seen:
                continue
            seen.add(fingerprint)
            included += 1
            global_index += 1
            instruction = _clean_text(item.get("instruction"), 1800)
            input_text = _clean_text(item.get("input"), 1200)
            output = _clean_text(item.get("output"), 2600)
            sections.append(f"[{global_index}] 요청: {instruction}")
            if input_text:
                sections.append(f"입력/상황: {input_text}")
            sections.append(f"권장 응답/판단: {output}")
        counts[dataset.id] = included

    return "\n".join(sections), counts


def _write_modelfile(base_model: str, prompt: str) -> Path:
    modelfile = _artifact_root() / "Modelfile"
    safe_prompt = prompt.replace('"""', '\\"\\"\\"')
    modelfile.write_text(
        f'FROM {base_model}\nSYSTEM """{safe_prompt}"""\nPARAMETER temperature 0\n',
        encoding="utf-8",
    )
    return modelfile


def _ollama_create(ollama_exe: str, model_name: str, modelfile: Path) -> str:
    completed = subprocess.run(
        [ollama_exe, "create", model_name, "-f", str(modelfile)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=1800,
        check=False,
    )
    output = (completed.stdout or "") + "\n" + (completed.stderr or "")
    if completed.returncode != 0:
        raise RuntimeError(f"Ollama 누적 학습 모델 생성 실패 (ExitCode={completed.returncode}): {output[-4000:]}")
    return output


def _ollama_remove(ollama_exe: str, model_name: str) -> bool:
    try:
        completed = subprocess.run(
            [ollama_exe, "rm", model_name],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
            check=False,
        )
        return completed.returncode == 0
    except Exception:
        return False


async def _ollama_model_names() -> list[str]:
    import httpx
    from app.core.config import get_settings
    base = str(get_settings().ollama_base_url or "http://127.0.0.1:11434").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{base}/api/tags")
            response.raise_for_status()
            return [str(item.get("name") or "") for item in response.json().get("models", []) if item.get("name")]
    except Exception:
        return []


async def _load_rebuild_datasets(target_dataset_id: str = "", include_all: bool = False) -> list[LlmLearningDataset]:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        all_datasets = (
            await session.execute(select(LlmLearningDataset).order_by(LlmLearningDataset.created_at.asc()))
        ).scalars().all()
        if include_all:
            selected = [row for row in all_datasets if _valid_problems(row)]
        else:
            enabled_ids = set((
                await session.execute(
                    select(LlmLearningPcApplication.dataset_id).where(
                        LlmLearningPcApplication.pc_name == pc_name,
                        LlmLearningPcApplication.enabled == True,
                    )
                )
            ).scalars().all())
            if target_dataset_id:
                enabled_ids.add(target_dataset_id)
            selected = [row for row in all_datasets if row.id in enabled_ids and _valid_problems(row)]
    return selected


async def _mark_datasets_validated(dataset_ids: list[str]) -> None:
    if not dataset_ids:
        return
    async with SessionLocal() as session:
        rows = (
            await session.execute(select(LlmLearningDataset).where(LlmLearningDataset.id.in_(dataset_ids)))
        ).scalars().all()
        for dataset in rows:
            problems = list(dataset.problems_json or [])
            valid = _valid_problems(dataset)
            valid_ids = {id(item) for item in valid}
            for item in problems:
                if isinstance(item, dict):
                    item["validated"] = id(item) in valid_ids or bool(str(item.get("instruction") or "").strip() and str(item.get("output") or "").strip())
            dataset.problems_json = problems
            dataset.validation_json = {
                "approved": len(valid),
                "rejected": len(problems) - len(valid),
                "pending": 0,
            }
            dataset.status = "validated"
            dataset.updated_by_pc_name = current_pc_name()
        await session.commit()


async def _save_cumulative_applications(
    datasets: list[LlmLearningDataset],
    base_model: str,
    modelfile: Path,
    problem_counts: dict[str, int],
    include_all: bool,
) -> None:
    pc_name = current_pc_name()
    included_ids = {row.id for row in datasets}
    now = datetime.utcnow()
    total_problem_count = sum(problem_counts.values())
    async with SessionLocal() as session:
        existing = (
            await session.execute(
                select(LlmLearningPcApplication).where(LlmLearningPcApplication.pc_name == pc_name)
            )
        ).scalars().all()
        by_dataset = {row.dataset_id: row for row in existing}
        for dataset in datasets:
            row = by_dataset.get(dataset.id)
            if row is None:
                row = LlmLearningPcApplication(
                    id=uuid.uuid4().hex,
                    dataset_id=dataset.id,
                    pc_name=pc_name,
                )
                session.add(row)
            row.model_name = CUMULATIVE_MODEL_NAME
            row.base_model = base_model
            row.adapter_path = ""
            row.installed = True
            row.enabled = True
            row.status = "applied"
            row.last_error = ""
            row.applied_at = now
            row.metadata_json = {
                "application_method": "ollama_cumulative_curriculum_system_prompt",
                "modelfile": str(modelfile),
                "dataset_problem_count": int(problem_counts.get(dataset.id) or 0),
                "cumulative_dataset_count": len(datasets),
                "cumulative_problem_count": total_problem_count,
                "model_alias": CUMULATIVE_MODEL_NAME,
                "full_rebuild": bool(include_all),
            }
            deployment = dict(dataset.deployment_json or {})
            history = list(deployment.get("pc_history") or [])
            history.append({
                "pc_name": pc_name,
                "model_name": CUMULATIVE_MODEL_NAME,
                "method": "ollama_cumulative_curriculum_system_prompt",
                "applied_at": now.isoformat(),
                "full_rebuild": bool(include_all),
            })
            deployment["pc_history"] = history[-100:]
            dataset.deployment_json = deployment
            dataset.updated_by_pc_name = pc_name

        if include_all:
            for row in existing:
                if row.dataset_id not in included_ids:
                    row.enabled = False
                    row.status = "not_applied"
        await session.commit()


async def _run_rebuild_job(job_id: str, target_dataset_id: str = "", include_all: bool = False) -> None:
    try:
        mode_text = "전체 재학습" if include_all else "누적 학습"
        _set_job(job_id, 5, "load", f"{mode_text} 대상 Dataset을 공용 DB에서 불러오는 중...", status="running")
        datasets = await _load_rebuild_datasets(target_dataset_id, include_all)
        if not datasets:
            raise ValueError("학습 적용할 유효한 Dataset이 없습니다.")

        dataset_ids = [row.id for row in datasets]
        _set_job(job_id, 16, "validate", f"Dataset {len(datasets)}개 문제 구조를 검증 중...", status="running", dataset_count=len(datasets))
        await _mark_datasets_validated(dataset_ids)
        # Reload after validation so JSON/status reflects committed DB state.
        datasets = await _load_rebuild_datasets(target_dataset_id, include_all)
        prompt, counts = _build_cumulative_curriculum(datasets)
        total_problems = sum(counts.values())
        if total_problems < 1:
            raise ValueError("누적 학습에 사용할 유효한 문제가 없습니다.")

        status = await get_recommended_model_status()
        ollama_exe = str(status.get("ollama_executable") or "").strip()
        if not ollama_exe:
            raise RuntimeError("Ollama 실행 파일을 찾을 수 없습니다.")
        installed_names = await _ollama_model_names()
        installed_lower = {str(name).lower() for name in installed_names}
        base_model = LATEST_RECOMMENDED_MODEL if LATEST_RECOMMENDED_MODEL.lower() in installed_lower else ""
        if not base_model:
            # Never use a previous theanova-learn model as the rebuild base. That would make
            # curriculum rules recursively accumulate and become impossible to reproduce.
            current = str(status.get("current_model") or "").strip()
            if current and not current.lower().startswith("theanova-learn"):
                base_model = current
        if not base_model:
            raise ValueError(f"누적 재빌드 Base Model({LATEST_RECOMMENDED_MODEL})을 찾을 수 없습니다.")

        _set_job(job_id, 35, "prepare", f"Dataset {len(datasets)}개 · 문제 {total_problems}개를 {CUMULATIVE_MODEL_NAME}에 누적 구성 중...", status="running", model_name=CUMULATIVE_MODEL_NAME, dataset_count=len(datasets), problem_count=total_problems)
        modelfile = await asyncio.to_thread(_write_modelfile, base_model, prompt)
        _set_job(job_id, 52, "create", f"Ollama에서 {CUMULATIVE_MODEL_NAME} 전체 모델을 재생성 중...", status="running", model_name=CUMULATIVE_MODEL_NAME, dataset_count=len(datasets), problem_count=total_problems)
        output = await asyncio.to_thread(_ollama_create, ollama_exe, CUMULATIVE_MODEL_NAME, modelfile)

        _set_job(job_id, 82, "activate", f"현재 PC 기본 모델을 {CUMULATIVE_MODEL_NAME}으로 전환 중...", status="running", model_name=CUMULATIVE_MODEL_NAME)
        await persist_current_ollama_model(CUMULATIVE_MODEL_NAME, str(status.get("common_models_root") or ""))
        await _save_cumulative_applications(datasets, base_model, modelfile, counts, include_all)

        # Old per-Dataset models are no longer needed once the reproducible :latest model
        # has been created and activated. Cleanup is best-effort and never fails the job.
        removed_old_models: list[str] = []
        for name in installed_names:
            normalized = str(name or "").strip()
            if normalized.lower().startswith("theanova-learn-"):
                if await asyncio.to_thread(_ollama_remove, ollama_exe, normalized):
                    removed_old_models.append(normalized)

        _set_job(
            job_id,
            100,
            "done",
            f"{mode_text} 완료 · Dataset {len(datasets)}개 / 문제 {total_problems}개 → {CUMULATIVE_MODEL_NAME}",
            status="completed",
            result={
                "dataset_ids": dataset_ids,
                "dataset_count": len(datasets),
                "model_name": CUMULATIVE_MODEL_NAME,
                "base_model": base_model,
                "validated_problem_count": total_problems,
                "application_method": "ollama_cumulative_curriculum_system_prompt",
                "full_rebuild": bool(include_all),
                "removed_old_models": removed_old_models,
                "modelfile": str(modelfile),
                "output_tail": output[-1200:],
            },
        )
    except Exception as exc:
        error = str(exc) or type(exc).__name__
        _set_job(job_id, int(_APPLY_JOBS.get(job_id, {}).get("progress") or 0), "failed", error, status="failed", error=error)


async def start_learning_apply_job(dataset_id: str) -> dict:
    dataset_id = str(dataset_id or "").strip()
    if not dataset_id:
        raise ValueError("Dataset ID가 필요합니다.")
    for job in _APPLY_JOBS.values():
        if job.get("status") == "running":
            return dict(job)
    job_id = uuid.uuid4().hex
    _set_job(
        job_id,
        1,
        "queued",
        "기존 적용 Dataset + 선택 Dataset 누적 학습 작업을 준비합니다.",
        status="running",
        dataset_id=dataset_id,
        full_rebuild=False,
        pc_name=current_pc_name(),
        created_at=datetime.utcnow().isoformat(),
    )
    asyncio.create_task(_run_rebuild_job(job_id, target_dataset_id=dataset_id, include_all=False))
    return dict(_APPLY_JOBS[job_id])


async def start_full_learning_apply_job() -> dict:
    for job in _APPLY_JOBS.values():
        if job.get("status") == "running":
            return dict(job)
    job_id = uuid.uuid4().hex
    _set_job(
        job_id,
        1,
        "queued",
        "모든 Dataset 전체 재학습 적용 작업을 준비합니다.",
        status="running",
        dataset_id="",
        full_rebuild=True,
        pc_name=current_pc_name(),
        created_at=datetime.utcnow().isoformat(),
    )
    asyncio.create_task(_run_rebuild_job(job_id, include_all=True))
    return dict(_APPLY_JOBS[job_id])


async def get_learning_apply_job(job_id: str) -> dict:
    job = _APPLY_JOBS.get(str(job_id or ""))
    if not job:
        raise KeyError("학습 적용 작업을 찾을 수 없습니다.")
    return dict(job)
