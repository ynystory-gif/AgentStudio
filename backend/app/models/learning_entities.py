from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LlmMisjudgmentCase(Base):
    """Global AgentStudio learning case shared by every PC on the same runtime DB.

    source_pc_name records provenance only. Queries intentionally do not scope by PC.
    """

    __tablename__ = "llm_misjudgment_cases"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_key: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    source_pc_name: Mapped[str] = mapped_column(String(255), default="", index=True)
    updated_by_pc_name: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(30), default="candidate", index=True)
    provider: Mapped[str] = mapped_column(String(100), default="unknown", index=True)
    model: Mapped[str] = mapped_column(String(200), default="unknown", index=True)
    task: Mapped[str] = mapped_column(String(200), default="")
    project_root: Mapped[str] = mapped_column(String(1200), default="")
    thread_id: Mapped[str] = mapped_column(String(200), default="")
    source_exchange_id: Mapped[str] = mapped_column(String(100), default="")
    detection_reason: Mapped[str] = mapped_column(String(100), default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    user_request: Mapped[str] = mapped_column(Text, default="")
    wrong_output: Mapped[str] = mapped_column(Text, default="")
    correction_evidence: Mapped[str] = mapped_column(Text, default="")
    expected_output: Mapped[str] = mapped_column(Text, default="")
    error_type: Mapped[str] = mapped_column(String(120), default="unclassified")
    error_reason: Mapped[str] = mapped_column(Text, default="")
    domain: Mapped[str] = mapped_column(String(200), default="")
    topic: Mapped[str] = mapped_column(String(300), default="")
    training_eligible: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class LlmLearningDataset(Base):
    """Generated/validated learning data shared across every AgentStudio PC.

    Dataset state is global. Whether a trained model is installed/enabled is intentionally
    NOT stored here because deployment is machine-specific.
    """

    __tablename__ = "llm_learning_datasets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_case_id: Mapped[str] = mapped_column(String(64), index=True)
    source_pc_name: Mapped[str] = mapped_column(String(255), default="", index=True)
    updated_by_pc_name: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(30), default="review", index=True)
    provider: Mapped[str] = mapped_column(String(100), default="ollama")
    source_provider: Mapped[str] = mapped_column(String(100), default="")
    source_model: Mapped[str] = mapped_column(String(200), default="")
    scope_json: Mapped[dict] = mapped_column(JSON, default=dict)
    target_count: Mapped[int] = mapped_column(Integer, default=0)
    problem_count: Mapped[int] = mapped_column(Integer, default=0)
    problems_json: Mapped[list] = mapped_column(JSON, default=list)
    validation_json: Mapped[dict] = mapped_column(JSON, default=dict)
    split_json: Mapped[dict] = mapped_column(JSON, default=dict)
    training_json: Mapped[dict] = mapped_column(JSON, default=dict)
    evaluation_json: Mapped[dict] = mapped_column(JSON, default=dict)
    deployment_json: Mapped[dict] = mapped_column(JSON, default=dict)  # legacy/global history only; new per-PC state is below.


class LlmLearningPcApplication(Base):
    """Per-PC application state for one shared learning dataset/model.

    A and B PCs can read the same dataset while independently installing, enabling,
    disabling, or selecting different learned Ollama models.
    """

    __tablename__ = "llm_learning_pc_applications"
    __table_args__ = (
        UniqueConstraint("dataset_id", "pc_name", name="uq_llm_learning_dataset_pc"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(64), index=True)
    pc_name: Mapped[str] = mapped_column(String(255), index=True)
    model_name: Mapped[str] = mapped_column(String(300), default="")
    base_model: Mapped[str] = mapped_column(String(300), default="")
    adapter_path: Mapped[str] = mapped_column(String(1600), default="")
    installed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    status: Mapped[str] = mapped_column(String(40), default="not_applied", index=True)
    last_error: Mapped[str] = mapped_column(Text, default="")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
