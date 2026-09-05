from __future__ import annotations

import asyncio
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.services.active_ollama_model_service import BASE_MODEL_NAME
from app.core.database import SessionLocal
from app.core.machine_identity import current_pc_name
from app.models.learning_entities import LlmLearningDataset, LlmLearningPcApplication


def _row_dict(row: LlmLearningPcApplication) -> dict:
    return {
        "id": row.id,
        "dataset_id": row.dataset_id,
        "pc_name": row.pc_name,
        "model_name": row.model_name,
        "base_model": row.base_model,
        "adapter_path": row.adapter_path,
        "installed": row.installed,
        "enabled": row.enabled,
        "status": row.status,
        "last_error": row.last_error,
        "applied_at": row.applied_at.isoformat() if row.applied_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
        "metadata": row.metadata_json or {},
    }


def _create_ollama_model(base_model: str, adapter: Path, model_name: str, dataset_id: str) -> dict:
    data_root = Path(adapter).parent
    model_dir = data_root / "ollama_apply" / dataset_id
    model_dir.mkdir(parents=True, exist_ok=True)
    modelfile = model_dir / "Modelfile"
    modelfile.write_text(
        f"FROM {base_model}\nADAPTER {adapter}\nPARAMETER temperature 0\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        ["ollama", "create", model_name, "-f", str(modelfile)],
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "ollama create 실패").strip())
    return {
        "model_name": model_name,
        "base_model": base_model,
        "adapter_path": str(adapter),
        "modelfile": str(modelfile),
        "stdout": (completed.stdout or "")[-2000:],
    }


async def list_pc_applications(dataset_id: str = "", include_all_pcs: bool = True) -> dict:
    """Return application states.

    Dataset/problem data is global. This table is the only machine-scoped part.
    include_all_pcs=True lets every PC see whether A/B/etc. have applied the model.
    """
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        stmt = select(LlmLearningPcApplication)
        if dataset_id:
            stmt = stmt.where(LlmLearningPcApplication.dataset_id == dataset_id)
        if not include_all_pcs:
            stmt = stmt.where(LlmLearningPcApplication.pc_name == pc_name)
        rows = (await session.execute(
            stmt.order_by(LlmLearningPcApplication.dataset_id, LlmLearningPcApplication.pc_name)
        )).scalars().all()
    return {
        "ok": True,
        "current_pc_name": pc_name,
        "items": [_row_dict(row) for row in rows],
        "scope": "per_pc_application_shared_visibility",
    }


async def apply_to_ollama_for_current_pc(dataset_id: str, model_name: str, adapter_path: str = "") -> dict:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        dataset = await session.get(LlmLearningDataset, dataset_id)
        if not dataset:
            raise KeyError("Dataset을 찾을 수 없습니다.")
        if not bool((dataset.evaluation_json or {}).get("passed")):
            raise ValueError("기존 모델 대비 평가 Gate를 통과한 학습 모델만 PC에 적용할 수 있습니다.")

        training = dict(dataset.training_json or {})
        adapter = Path(adapter_path or training.get("adapter_dir") or "")
        if not adapter.exists():
            raise ValueError(
                "이 PC에 학습 Adapter가 없습니다. 학습 데이터는 공용 조회되지만 "
                "실제 Adapter 파일은 PC별 로컬 산출물입니다."
            )
        base_model = str(training.get("ollama_base_model") or BASE_MODEL_NAME)

        stmt = select(LlmLearningPcApplication).where(
            LlmLearningPcApplication.dataset_id == dataset_id,
            LlmLearningPcApplication.pc_name == pc_name,
        )
        application = (await session.execute(stmt)).scalar_one_or_none()
        if application is None:
            application = LlmLearningPcApplication(
                id=uuid.uuid4().hex,
                dataset_id=dataset_id,
                pc_name=pc_name,
            )
            session.add(application)

        application.model_name = model_name
        application.base_model = base_model
        application.adapter_path = str(adapter)
        application.status = "applying"
        application.last_error = ""
        application.enabled = False
        await session.commit()

    try:
        details = await asyncio.to_thread(_create_ollama_model, base_model, adapter, model_name, dataset_id)
    except Exception as exc:
        async with SessionLocal() as session:
            stmt = select(LlmLearningPcApplication).where(
                LlmLearningPcApplication.dataset_id == dataset_id,
                LlmLearningPcApplication.pc_name == pc_name,
            )
            application = (await session.execute(stmt)).scalar_one()
            application.installed = False
            application.enabled = False
            application.status = "failed"
            application.last_error = str(exc)
            application.metadata_json = {"error": str(exc)}
            await session.commit()
        raise

    async with SessionLocal() as session:
        stmt = select(LlmLearningPcApplication).where(
            LlmLearningPcApplication.dataset_id == dataset_id,
            LlmLearningPcApplication.pc_name == pc_name,
        )
        application = (await session.execute(stmt)).scalar_one()
        application.installed = True
        application.enabled = True
        application.status = "applied"
        application.last_error = ""
        application.applied_at = datetime.utcnow()
        application.metadata_json = details
        await session.commit()
        await session.refresh(application)
        return {
            "ok": True,
            "application": _row_dict(application),
            "dataset_scope": "shared_all_pcs",
            "application_scope": "current_pc_only",
        }


async def set_current_pc_application_enabled(dataset_id: str, enabled: bool) -> dict:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        stmt = select(LlmLearningPcApplication).where(
            LlmLearningPcApplication.dataset_id == dataset_id,
            LlmLearningPcApplication.pc_name == pc_name,
        )
        application = (await session.execute(stmt)).scalar_one_or_none()
        if not application:
            raise KeyError("현재 PC에는 이 학습 모델의 적용 이력이 없습니다.")
        if enabled and not application.installed:
            raise ValueError("현재 PC에 설치되지 않은 학습 모델은 활성화할 수 없습니다.")
        application.enabled = bool(enabled)
        application.status = "applied" if enabled else "disabled"
        application.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(application)
        return {"ok": True, "application": _row_dict(application)}
