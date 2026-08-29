from __future__ import annotations

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.machine_identity import current_pc_name
from app.models.learning_entities import LlmLearningPcApplication


async def get_active_weight_model_status() -> dict:
    """Return whether this PC currently uses a true merged QLoRA model.

    The DB application record is authoritative; no browser/local JSON flag is used.
    """
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(LlmLearningPcApplication).where(
                    LlmLearningPcApplication.pc_name == pc_name,
                    LlmLearningPcApplication.enabled == True,
                    LlmLearningPcApplication.installed == True,
                    LlmLearningPcApplication.model_name == "theanova-learn:latest",
                )
            )
        ).scalars().all()
    weight_rows = [
        row for row in rows
        if bool(dict(row.metadata_json or {}).get("weight_trained"))
        or str(dict(row.metadata_json or {}).get("application_method") or "").startswith("qlora_weight_finetune")
    ]
    latest = max(
        (row.applied_at for row in weight_rows if row.applied_at is not None),
        default=None,
    )
    return {
        "weight_model_active": bool(weight_rows),
        "weight_model_name": "theanova-learn:latest" if weight_rows else "",
        "weight_model_dataset_count": len(weight_rows),
        "weight_model_applied_at": latest.isoformat() if latest else "",
        "legacy_apply_should_be_disabled": bool(weight_rows),
    }
