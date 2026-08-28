from __future__ import annotations

"""Automatically guarantee the recommended Ollama base model before learning rebuilds.

AgentStudio's learned model is a reproducible derived Ollama model:

    qwen3.5:4b + validated cumulative curriculum -> theanova-learn:latest

Users must not have to manually pull/select qwen3.5:4b before applying learning.
This bridge wraps the existing rebuild job before API routes import the service.
"""

from app.services import learning_apply_job_service as apply_service
from app.services.ollama_model_manager_service import (
    LATEST_RECOMMENDED_MODEL,
    download_and_apply_recommended_model,
)


_original_run_rebuild_job = apply_service._run_rebuild_job


async def _ensure_recommended_base_for_learning(job_id: str) -> None:
    installed = {
        str(name or "").strip().lower()
        for name in await apply_service._ollama_model_names()
        if str(name or "").strip()
    }
    if LATEST_RECOMMENDED_MODEL.lower() in installed:
        apply_service._set_job(
            job_id,
            max(3, int(apply_service._APPLY_JOBS.get(job_id, {}).get("progress") or 0)),
            "base_check",
            f"학습 Base Model {LATEST_RECOMMENDED_MODEL} 확인 완료 · 누적 학습 모델을 준비합니다.",
            status="running",
            base_model=LATEST_RECOMMENDED_MODEL,
            learned_model=apply_service.CUMULATIVE_MODEL_NAME,
            model_stack=f"{apply_service.CUMULATIVE_MODEL_NAME} + {LATEST_RECOMMENDED_MODEL}",
        )
        return

    apply_service._set_job(
        job_id,
        3,
        "base_install",
        f"학습 Base Model {LATEST_RECOMMENDED_MODEL}이 없어 AgentStudio가 자동 다운로드/적용합니다...",
        status="running",
        base_model=LATEST_RECOMMENDED_MODEL,
        learned_model=apply_service.CUMULATIVE_MODEL_NAME,
        model_stack=f"{apply_service.CUMULATIVE_MODEL_NAME} + {LATEST_RECOMMENDED_MODEL}",
    )
    await download_and_apply_recommended_model()

    installed_after = {
        str(name or "").strip().lower()
        for name in await apply_service._ollama_model_names()
        if str(name or "").strip()
    }
    if LATEST_RECOMMENDED_MODEL.lower() not in installed_after:
        raise RuntimeError(
            f"AgentStudio가 {LATEST_RECOMMENDED_MODEL} 자동 준비를 완료했지만 Ollama 모델 목록에서 확인하지 못했습니다."
        )


async def _run_rebuild_job_with_auto_base(
    job_id: str,
    target_dataset_id: str = "",
    include_all: bool = False,
) -> None:
    try:
        await _ensure_recommended_base_for_learning(job_id)
    except Exception as exc:
        error = str(exc) or type(exc).__name__
        apply_service._set_job(
            job_id,
            int(apply_service._APPLY_JOBS.get(job_id, {}).get("progress") or 0),
            "failed",
            f"학습 Base Model 자동 준비 실패: {error}",
            status="failed",
            error=error,
            base_model=LATEST_RECOMMENDED_MODEL,
            learned_model=apply_service.CUMULATIVE_MODEL_NAME,
        )
        return

    await _original_run_rebuild_job(
        job_id,
        target_dataset_id=target_dataset_id,
        include_all=include_all,
    )


# start_learning_apply_job/start_full_learning_apply_job resolve this module global
# at runtime, so replacing it here affects both individual and full rebuilds.
apply_service._run_rebuild_job = _run_rebuild_job_with_auto_base
