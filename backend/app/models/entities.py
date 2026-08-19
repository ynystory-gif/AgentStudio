from datetime import datetime
from sqlalchemy import String, Text, DateTime, Integer, Boolean, JSON, ForeignKey, Float, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector
from app.core.database import Base

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    root_path: Mapped[str] = mapped_column(String(1000), unique=True)
    cache_path: Mapped[str] = mapped_column(String(1000), default="")
    temp_path: Mapped[str] = mapped_column(String(1000), default="")
    output_path: Mapped[str] = mapped_column(String(1000), default="")
    venv_path: Mapped[str] = mapped_column(String(1000), default="")
    models_path: Mapped[str] = mapped_column(String(1000), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_favorite: Mapped[bool] = mapped_column(Boolean, default=False)

class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    thread_id: Mapped[str] = mapped_column(String(100), default="default")
    role: Mapped[str] = mapped_column(String(30))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Requirement(Base):
    __tablename__ = "requirements"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    key: Mapped[str] = mapped_column(String(150))
    value: Mapped[str] = mapped_column(Text)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=True)

class MCPServer(Base):
    __tablename__ = "mcp_servers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), unique=True)
    transport: Mapped[str] = mapped_column(String(50), default="streamable_http")
    endpoint: Mapped[str] = mapped_column(String(1000), default="")
    command: Mapped[str] = mapped_column(String(1000), default="")
    args: Mapped[list] = mapped_column(JSON, default=list)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # 승인 정책 강화
    trust_level: Mapped[str] = mapped_column(String(30), default="UNTRUSTED")  # UNTRUSTED / TRUSTED / SYSTEM
    allow_read_without_prompt: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_write_without_prompt: Mapped[bool] = mapped_column(Boolean, default=False)

    last_status: Mapped[str] = mapped_column(String(50), default="UNKNOWN")
    protocol_version: Mapped[str] = mapped_column(String(50), default="")
    supports_tool_list_changed: Mapped[bool] = mapped_column(Boolean, default=False)
    discovered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ToolRecord(Base):
    __tablename__ = "tool_registry"
    __table_args__ = (UniqueConstraint("mcp_server_id", "name", name="uq_mcp_tool"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    mcp_server_id: Mapped[int | None] = mapped_column(ForeignKey("mcp_servers.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(200))
    name: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(100), default="UNKNOWN")
    subcategory: Mapped[str] = mapped_column(String(100), default="UNKNOWN")
    capability: Mapped[str] = mapped_column(String(200), default="unknown")
    risk_level: Mapped[int] = mapped_column(Integer, default=0)
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    input_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    annotations: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    thread_id: Mapped[str] = mapped_column(String(100))
    action_type: Mapped[str] = mapped_column(String(100))
    summary: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    risk_level: Mapped[int] = mapped_column(Integer, default=0)
    server_trust_level: Mapped[str] = mapped_column(String(30), default="UNTRUSTED")
    status: Mapped[str] = mapped_column(String(30), default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class MemoryRecord(Base):
    __tablename__ = "memory_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    memory_type: Mapped[str] = mapped_column(String(30))  # SESSION / PROJECT / KNOWLEDGE
    key: Mapped[str] = mapped_column(String(250))
    content: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ProjectFileIndex(Base):
    __tablename__ = "project_file_index"
    __table_args__ = (UniqueConstraint("project_id", "path", name="uq_project_file"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    path: Mapped[str] = mapped_column(String(1200))
    language: Mapped[str] = mapped_column(String(50), default="")
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str] = mapped_column(Text, default="")
    symbols: Mapped[list] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class EvaluationRecord(Base):
    __tablename__ = "evaluation_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    metric: Mapped[str] = mapped_column(String(100))
    score: Mapped[float] = mapped_column(Float, default=0.0)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class UsageRecord(Base):
    __tablename__ = "usage_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int | None] = mapped_column(ForeignKey("projects.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(100))
    model: Mapped[str] = mapped_column(String(150))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class JobRecord(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    kind: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), default="QUEUED")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    message: Mapped[str] = mapped_column(Text, default="")
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AgentStudioMachine(Base):
    __tablename__ = "agentstudio_machines"
    id: Mapped[int] = mapped_column(primary_key=True)
    pc_name: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    host_name: Mapped[str] = mapped_column(String(255), default="")
    os_name: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AppSetting(Base):
    __tablename__ = "app_settings"
    __table_args__ = (
        UniqueConstraint("pc_name", "key", name="uq_app_settings_pc_name_key"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    pc_name: Mapped[str] = mapped_column(String(255), default="", index=True)
    key: Mapped[str] = mapped_column(String(150), index=True)
    value: Mapped[str] = mapped_column(Text, default="")
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class ProjectAnalysis(Base):
    __tablename__ = "project_analyses"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"))
    project_root: Mapped[str] = mapped_column(String(1200))
    project_name: Mapped[str] = mapped_column(String(300), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    tech_stack: Mapped[list] = mapped_column(JSON, default=list)
    entry_points: Mapped[list] = mapped_column(JSON, default=list)
    major_files: Mapped[list] = mapped_column(JSON, default=list)
    mcp_tools: Mapped[list] = mapped_column(JSON, default=list)
    structure: Mapped[dict] = mapped_column(JSON, default=dict)
    raw_analysis: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
