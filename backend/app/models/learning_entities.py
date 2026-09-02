from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LlmMisjudgmentGroup(Base):
    """Stable weak-area group for related misjudgment cases."""

    __tablename__ = "llm_misjudgment_groups"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    group_key: Mapped[str] = mapped_column(String(300), unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(100), default="unknown", index=True)
    model: Mapped[str] = mapped_column(String(200), default="unknown", index=True)
    detection_reason: Mapped[str] = mapped_column(String(100), default="", index=True)
    domain: Mapped[str] = mapped_column(String(200), default="")
    topic: Mapped[str] = mapped_column(String(300), default="")
    error_type: Mapped[str] = mapped_column(String(120), default="unclassified")
    status: Mapped[str] = mapped_column(String(30), default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LlmMisjudgmentCase(Base):
    """Global AgentStudio learning case shared by every PC on the same runtime DB."""

    __tablename__ = "llm_misjudgment_cases"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    group_id: Mapped[str] = mapped_column(String(64), default="", index=True)
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


class LlmMisjudgmentGroupCase(Base):
    """Explicit group-to-case mapping with its own primary key and mapping history."""

    __tablename__ = "llm_misjudgment_group_cases"
    __table_args__ = (
        UniqueConstraint("group_id", "case_id", name="uq_llm_misjudgment_group_case"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    group_id: Mapped[str] = mapped_column(ForeignKey("llm_misjudgment_groups.id"), index=True)
    case_id: Mapped[str] = mapped_column(ForeignKey("llm_misjudgment_cases.id"), index=True)
    mapping_source: Mapped[str] = mapped_column(String(50), default="automatic")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class LlmLearningDataset(Base):
    """Generated/validated learning data shared across every AgentStudio PC."""

    __tablename__ = "llm_learning_datasets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    group_id: Mapped[str] = mapped_column(String(64), default="", index=True)
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
    problems_json: Mapped[list] = mapped_column(JSON, default=list)  # legacy compatibility; normalized rows live below.
    validation_json: Mapped[dict] = mapped_column(JSON, default=dict)
    split_json: Mapped[dict] = mapped_column(JSON, default=dict)
    training_json: Mapped[dict] = mapped_column(JSON, default=dict)
    evaluation_json: Mapped[dict] = mapped_column(JSON, default=dict)
    deployment_json: Mapped[dict] = mapped_column(JSON, default=dict)


class LlmLearningProblem(Base):
    """One generated learning problem, relationally linked to its Dataset and error group."""

    __tablename__ = "llm_learning_problems"
    __table_args__ = (
        UniqueConstraint("dataset_id", "problem_key", name="uq_llm_learning_dataset_problem_key"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("llm_learning_datasets.id"), index=True)
    group_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    source_case_id: Mapped[str] = mapped_column(String(64), default="", index=True)
    problem_key: Mapped[str] = mapped_column(String(160), default="")
    instruction: Mapped[str] = mapped_column(Text, default="")
    input_text: Mapped[str] = mapped_column(Text, default="")
    output_text: Mapped[str] = mapped_column(Text, default="")
    domain: Mapped[str] = mapped_column(String(200), default="")
    topic: Mapped[str] = mapped_column(String(300), default="")
    subtopic: Mapped[str] = mapped_column(String(300), default="")
    difficulty: Mapped[str] = mapped_column(String(50), default="medium")
    problem_type: Mapped[str] = mapped_column(String(80), default="scenario")
    validated: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LlmLearningPcApplication(Base):
    """Per-PC application state for one shared learning Dataset/model."""

    __tablename__ = "llm_learning_pc_applications"
    __table_args__ = (
        UniqueConstraint("dataset_id", "pc_name", name="uq_llm_learning_dataset_pc"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    dataset_id: Mapped[str] = mapped_column(String(64), index=True)
    group_id: Mapped[str] = mapped_column(String(64), default="", index=True)
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
