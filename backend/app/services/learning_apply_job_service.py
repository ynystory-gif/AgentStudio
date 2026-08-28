from __future__ import annotations

import asyncio
import json
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


def _artifact_root(dataset_id: str) -> Path:
    import os
    local = str(os.environ.get("LOCALAPPDATA") or "").strip()
    root = Path(local) / "THEANOVA" / "AgentStudio" if local else Path.home() / ".theanova" / "AgentStudio"
    path = root / "learning" / "applied_models" / dataset_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _clean_text(value: object, limit: int = 6000) -> str:
    text = str(value or "").replace("\x00", " ").strip()
    return text[:limit]


def _build_curriculum_prompt(dataset: LlmLearningDataset, valid_problems: list[dict]) -> str:
    scope = dict(dataset.scope_json or {})
    sections = [
        "THEANOVA AgentStudio에서 검증된 오판 보정 학습 규칙을 적용합니다.",
        "아래 학습 범위와 예시를 우선 참고하되 사용자의 실제 요구사항, 현재 프로젝트 파일, 도구 실행 결과와 충돌하면 실제 근거를 우선합니다.",
        f"Domain: {_clean_text(scope.get('domain'), 500)}",
        f"Topic: {_clean_text(scope.get('topic'), 800)}",
        f"Learning objective: {_clean_text(scope.get('learning_objective'), 1600)}",
        f"Root cause to avoid: {_clean_text(scope.get('root_cause'), 1600)}",
        "Subtopics: " + json.dumps(scope.get("subtopics") or [], ensure_ascii=False),
        "Pitfalls: " + json.dumps(scope.get("pitfalls") or [], ensure_ascii=False),
        "\n검증 학습 예시:",
    ]
    # Keep the Modelfile reasonably sized. The complete Dataset remains in the shared DB;
    # this PC-local applied model receives a representative curriculum slice.
    for index, item in enumerate(valid_problems[:40], start=1):
        instruction = _clean_text(item.get("instruction"), 1800)
        input_text = _clean_text(item.get("input"), 1000)
        output = _clean_text(item.get("output"), 2400)
        sections.append(f"[{index}] 요청: {instruction}")
        if input_text:
            sections.append(f"입력/상황: {input_text}")
        sections.append(f"권장 응답/판단: {output}")
    return "\n".join(sections)


def _write_modelfile(dataset_id: str, base_model: str, prompt: str) -> Path:
    out = _artifact_root(dataset_id)
    modelfile = out / "Modelfile"
    safe_prompt = prompt.replace('"""', '\"\"\"')
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
        raise RuntimeError(f"Ollama 학습 적용 모델 생성 실패 (ExitCode={completed.returncode}): {output[-4000:]}")
    return output


async def _ensure_application(dataset_id: str, model_name: str, base_model: str, status: str) -> None:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(LlmLearningPcApplication).where(
                    LlmLearningPcApplication.dataset_id == dataset_id,
                    LlmLearningPcApplication.pc_name == pc_name,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = LlmLearningPcApplication(
                id=uuid.uuid4().hex,
                dataset_id=dataset_id,
                pc_name=pc_name,
            )
            session.add(row)
        row.model_name = model_name
        row.base_model = base_model
        row.status = status
        row.enabled = False
        row.last_error = ""
        await session.commit()


async def _finish_application(dataset_id: str, model_name: str, base_model: str, modelfile: Path, problem_count: int) -> None:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(LlmLearningPcApplication).where(
                    LlmLearningPcApplication.dataset_id == dataset_id,
                    LlmLearningPcApplication.pc_name == pc_name,
                )
            )
        ).scalar_one()
        row.model_name = model_name
        row.base_model = base_model
        row.adapter_path = ""
        row.installed = True
        row.enabled = True
        row.status = "applied"
        row.last_error = ""
        row.applied_at = datetime.utcnow()
        row.metadata_json = {
            "application_method": "ollama_curriculum_system_prompt",
            "modelfile": str(modelfile),
            "validated_problem_count": problem_count,
            "dataset_scope": "shared_all_pcs",
            "application_scope": "current_pc_only",
        }
        dataset = await session.get(LlmLearningDataset, dataset_id)
        if dataset:
            deployment = dict(dataset.deployment_json or {})
            history = list(deployment.get("pc_history") or [])
            history.append({
                "pc_name": pc_name,
                "model_name": model_name,
                "method": "ollama_curriculum_system_prompt",
                "applied_at": datetime.utcnow().isoformat(),
            })
            deployment["pc_history"] = history[-100:]
            dataset.deployment_json = deployment
            dataset.updated_by_pc_name = pc_name
        await session.commit()


async def _mark_application_failed(dataset_id: str, error: str) -> None:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(LlmLearningPcApplication).where(
                    LlmLearningPcApplication.dataset_id == dataset_id,
                    LlmLearningPcApplication.pc_name == pc_name,
                )
            )
        ).scalar_one_or_none()
        if row:
            row.status = "failed"
            row.installed = False
            row.enabled = False
            row.last_error = error
            await session.commit()


async def _run_apply_job(job_id: str, dataset_id: str) -> None:
    model_name = f"theanova-learn-{dataset_id[:8]}"
    try:
        _set_job(job_id, 5, "load", "공용 DB에서 수집 문제 Dataset을 불러오는 중...", status="running")
        async with SessionLocal() as session:
            dataset = await session.get(LlmLearningDataset, dataset_id)
            if not dataset:
                raise KeyError("Dataset을 찾을 수 없습니다.")
            problems = list(dataset.problems_json or [])
            valid = [
                item for item in problems
                if str(item.get("instruction") or "").strip() and str(item.get("output") or "").strip()
            ]
            if len(valid) < 10:
                raise ValueError("학습 적용에는 유효한 수집 문제 10개 이상이 필요합니다.")
            _set_job(job_id, 18, "validate", f"수집 문제 {len(valid)}개 구조 검증 완료. Dataset 검증 상태를 반영 중...", status="running")
            for item in problems:
                item["validated"] = item in valid
            dataset.problems_json = problems
            dataset.validation_json = {"approved": len(valid), "rejected": len(problems) - len(valid), "pending": 0}
            dataset.status = "validated"
            dataset.updated_by_pc_name = current_pc_name()
            await session.commit()
            await session.refresh(dataset)
            prompt = _build_curriculum_prompt(dataset, valid)

        status = await get_recommended_model_status()
        ollama_exe = str(status.get("ollama_executable") or "").strip()
        if not ollama_exe:
            raise RuntimeError("Ollama 실행 파일을 찾을 수 없습니다.")
        installed = {str(name).lower() for name in (await _ollama_model_names())}
        base_model = LATEST_RECOMMENDED_MODEL if LATEST_RECOMMENDED_MODEL.lower() in installed else str(status.get("current_model") or "").strip()
        if not base_model:
            raise ValueError("학습 적용에 사용할 Ollama Base Model이 없습니다.")

        await _ensure_application(dataset_id, model_name, base_model, "preparing")
        _set_job(job_id, 35, "prepare", f"현재 PC용 학습 모델 {model_name} 구성 파일을 생성 중...", status="running", model_name=model_name)
        modelfile = await asyncio.to_thread(_write_modelfile, dataset_id, base_model, prompt)
        _set_job(job_id, 52, "create", f"Ollama에서 {model_name} 모델을 생성 중...", status="running", model_name=model_name)
        output = await asyncio.to_thread(_ollama_create, ollama_exe, model_name, modelfile)
        _set_job(job_id, 84, "activate", f"현재 PC 기본 모델을 {model_name}으로 전환 중...", status="running", model_name=model_name)
        await persist_current_ollama_model(model_name, str(status.get("common_models_root") or ""))
        await _finish_application(dataset_id, model_name, base_model, modelfile, len(valid))
        _set_job(
            job_id,
            100,
            "done",
            f"학습 적용 완료 · 현재 PC에서 {model_name}을 사용합니다.",
            status="completed",
            result={
                "dataset_id": dataset_id,
                "model_name": model_name,
                "base_model": base_model,
                "validated_problem_count": len(valid),
                "application_method": "ollama_curriculum_system_prompt",
                "output_tail": output[-1200:],
            },
        )
    except Exception as exc:
        error = str(exc) or type(exc).__name__
        await _mark_application_failed(dataset_id, error)
        _set_job(job_id, int(_APPLY_JOBS.get(job_id, {}).get("progress") or 0), "failed", error, status="failed", error=error)


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


async def start_learning_apply_job(dataset_id: str) -> dict:
    dataset_id = str(dataset_id or "").strip()
    if not dataset_id:
        raise ValueError("Dataset ID가 필요합니다.")
    for job in _APPLY_JOBS.values():
        if job.get("status") == "running" and job.get("dataset_id") == dataset_id:
            return dict(job)
    job_id = uuid.uuid4().hex
    _set_job(
        job_id,
        1,
        "queued",
        "학습 적용 작업을 준비합니다.",
        status="running",
        dataset_id=dataset_id,
        pc_name=current_pc_name(),
        created_at=datetime.utcnow().isoformat(),
    )
    asyncio.create_task(_run_apply_job(job_id, dataset_id))
    return dict(_APPLY_JOBS[job_id])


async def get_learning_apply_job(job_id: str) -> dict:
    job = _APPLY_JOBS.get(str(job_id or ""))
    if not job:
        raise KeyError("학습 적용 작업을 찾을 수 없습니다.")
    return dict(job)
