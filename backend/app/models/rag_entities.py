from __future__ import annotations

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


# v5.589: RAG Studio phase-2 uses one fixed pgvector storage dimension so the
# HNSW index can be created consistently for both OpenAI(1536 default) and
# smaller local embeddings such as nomic-embed-text(768). Smaller vectors are
# zero padded by the indexing service; original dimensions are retained in DB.
RAG_VECTOR_STORAGE_DIMENSION = 1536


class RagStudioSetting(Base):
    __tablename__ = "rag_studio_settings"
    __table_args__ = (
        UniqueConstraint("pc_name", "project_root", name="uq_rag_studio_settings_pc_root"),
    )

    id: Mapped[int] = mapped_column("studio_settings_id", Integer, primary_key=True, autoincrement=True)
    pc_name: Mapped[str] = mapped_column(String(255), default="", index=True)
    project_root: Mapped[str] = mapped_column(String(1200), default="", index=True)
    rag_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    db_provider: Mapped[str] = mapped_column(String(80), default="POSTGRESQL_PGVECTOR")
    connection_mode: Mapped[str] = mapped_column(String(40), default="RUNTIME")
    db_schema: Mapped[str] = mapped_column(String(120), default="")
    scope: Mapped[str] = mapped_column(String(40), default="AGENT")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RagCollection(Base):
    __tablename__ = "rag_collections"
    __table_args__ = (
        UniqueConstraint("pc_name", "project_root", "name", name="uq_rag_collection_pc_root_name"),
    )

    id: Mapped[int] = mapped_column("collections_id", Integer, primary_key=True, autoincrement=True)
    pc_name: Mapped[str] = mapped_column(String(255), default="", index=True)
    project_root: Mapped[str] = mapped_column(String(1200), default="", index=True)
    agent_design_project_id: Mapped[int | None] = mapped_column(ForeignKey("agent_design_projects.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(300), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    scope: Mapped[str] = mapped_column(String(40), default="AGENT")
    security_level: Mapped[str] = mapped_column(String(40), default="INTERNAL")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RagSource(Base):
    __tablename__ = "rag_sources"

    id: Mapped[int] = mapped_column("sources_id", Integer, primary_key=True, autoincrement=True)
    pc_name: Mapped[str] = mapped_column(String(255), default="", index=True)
    project_root: Mapped[str] = mapped_column(String(1200), default="", index=True)
    source_type: Mapped[str] = mapped_column(String(50), default="FILE", index=True)
    source_uri: Mapped[str] = mapped_column(String(2000), default="")
    display_name: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(50), default="REGISTERED", index=True)
    suitability: Mapped[str] = mapped_column(String(40), default="UNKNOWN")
    risk_level: Mapped[str] = mapped_column(String(40), default="UNKNOWN")
    recommendation_reason: Mapped[str] = mapped_column(Text, default="")
    recommended_chunking: Mapped[str] = mapped_column(String(120), default="")
    analysis_engine: Mapped[str] = mapped_column(String(100), default="")
    analysis_result: Mapped[dict] = mapped_column(JSON, default=dict)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RagCollectionSource(Base):
    __tablename__ = "rag_collection_sources"
    __table_args__ = (
        UniqueConstraint("collection_id", "source_id", name="uq_rag_collection_source_pair"),
    )

    id: Mapped[int] = mapped_column("collection_sources_id", Integer, primary_key=True, autoincrement=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("rag_collections.collections_id"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("rag_sources.sources_id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RagDocument(Base):
    """One logical document discovered inside a registered RAG Source."""

    __tablename__ = "rag_documents"
    __table_args__ = (
        UniqueConstraint("source_id", "path", name="uq_rag_document_source_path"),
    )

    id: Mapped[int] = mapped_column("documents_id", Integer, primary_key=True, autoincrement=True)
    pc_name: Mapped[str] = mapped_column(String(255), default="", index=True)
    project_root: Mapped[str] = mapped_column(String(1200), default="", index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("rag_sources.sources_id"), index=True)
    path: Mapped[str] = mapped_column(String(2000), default="")
    filename: Mapped[str] = mapped_column(String(500), default="")
    document_type: Mapped[str] = mapped_column(String(80), default="UNKNOWN", index=True)
    language: Mapped[str] = mapped_column(String(80), default="")
    checksum: Mapped[str] = mapped_column(String(64), default="", index=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    safety_level: Mapped[str] = mapped_column(String(40), default="LOW")
    safety_result: Mapped[dict] = mapped_column(JSON, default=dict)
    duplicate_of_document_id: Mapped[int | None] = mapped_column(ForeignKey("rag_documents.documents_id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(50), default="DISCOVERED", index=True)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RagChunk(Base):
    """Chunk text and structural provenance generated from a RagDocument."""

    __tablename__ = "rag_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_rag_chunk_document_index"),
    )

    id: Mapped[int] = mapped_column("chunks_id", Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("rag_documents.documents_id"), index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("rag_sources.sources_id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, default=0)
    content: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(64), default="", index=True)
    char_count: Mapped[int] = mapped_column(Integer, default=0)
    token_estimate: Mapped[int] = mapped_column(Integer, default=0)
    start_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    end_line: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heading: Mapped[str] = mapped_column(String(500), default="")
    symbol_name: Mapped[str] = mapped_column(String(500), default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RagEmbedding(Base):
    """pgvector embedding persisted separately from chunk text."""

    __tablename__ = "rag_embeddings"
    __table_args__ = (
        UniqueConstraint("chunk_id", name="uq_rag_embedding_chunk"),
    )

    id: Mapped[int] = mapped_column("embeddings_id", Integer, primary_key=True, autoincrement=True)
    chunk_id: Mapped[int] = mapped_column(ForeignKey("rag_chunks.chunks_id"), index=True)
    provider: Mapped[str] = mapped_column(String(80), default="")
    model: Mapped[str] = mapped_column(String(200), default="")
    source_dimension: Mapped[int] = mapped_column(Integer, default=0)
    storage_dimension: Mapped[int] = mapped_column(Integer, default=RAG_VECTOR_STORAGE_DIMENSION)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(RAG_VECTOR_STORAGE_DIMENSION), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RagIndexJob(Base):
    """Persisted progress for phase-2 Chunk / Embedding / HNSW indexing."""

    __tablename__ = "rag_index_jobs"

    id: Mapped[int] = mapped_column("index_jobs_id", Integer, primary_key=True, autoincrement=True)
    pc_name: Mapped[str] = mapped_column(String(255), default="", index=True)
    project_root: Mapped[str] = mapped_column(String(1200), default="", index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("rag_sources.sources_id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="PENDING", index=True)
    stage: Mapped[str] = mapped_column(String(80), default="QUEUED")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    documents_total: Mapped[int] = mapped_column(Integer, default=0)
    documents_processed: Mapped[int] = mapped_column(Integer, default=0)
    duplicates_skipped: Mapped[int] = mapped_column(Integer, default=0)
    safety_warnings: Mapped[int] = mapped_column(Integer, default=0)
    chunks_created: Mapped[int] = mapped_column(Integer, default=0)
    embeddings_created: Mapped[int] = mapped_column(Integer, default=0)
    embedding_provider: Mapped[str] = mapped_column(String(80), default="")
    embedding_model: Mapped[str] = mapped_column(String(200), default="")
    embedding_dimension: Mapped[int] = mapped_column(Integer, default=0)
    index_name: Mapped[str] = mapped_column(String(200), default="")
    index_ready: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str] = mapped_column(Text, default="")
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class RagRetrievalSetting(Base):
    """Persisted phase-3 Retrieval configuration for one AgentStudio project."""

    __tablename__ = "rag_retrieval_settings"
    __table_args__ = (
        UniqueConstraint("pc_name", "project_root", name="uq_rag_retrieval_settings_pc_root"),
    )

    id: Mapped[int] = mapped_column("retrieval_settings_id", Integer, primary_key=True, autoincrement=True)
    pc_name: Mapped[str] = mapped_column(String(255), default="", index=True)
    project_root: Mapped[str] = mapped_column(String(1200), default="", index=True)
    search_mode: Mapped[str] = mapped_column(String(40), default="HYBRID")
    top_k: Mapped[int] = mapped_column(Integer, default=5)
    similarity_threshold: Mapped[float] = mapped_column(Float, default=0.20)
    metadata_filter: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RagSearchLog(Base):
    """Phase-3 Retrieval audit/debug log. Every table keeps an auto-increment id."""

    __tablename__ = "rag_search_logs"

    id: Mapped[int] = mapped_column("search_logs_id", Integer, primary_key=True, autoincrement=True)
    pc_name: Mapped[str] = mapped_column(String(255), default="", index=True)
    project_root: Mapped[str] = mapped_column(String(1200), default="", index=True)
    query_text: Mapped[str] = mapped_column(Text, default="")
    search_mode: Mapped[str] = mapped_column(String(40), default="HYBRID", index=True)
    top_k: Mapped[int] = mapped_column(Integer, default=5)
    similarity_threshold: Mapped[float] = mapped_column(Float, default=0.20)
    metadata_filter: Mapped[dict] = mapped_column(JSON, default=dict)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    vector_candidate_count: Mapped[int] = mapped_column(Integer, default=0)
    keyword_candidate_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    embedding_provider: Mapped[str] = mapped_column(String(80), default="")
    embedding_model: Mapped[str] = mapped_column(String(200), default="")
    result_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)



class RagAgentTool(Base):
    """Phase-4 RAG Tool definition linked to Prompt/Tool Studio and Workflow."""

    __tablename__ = "rag_agent_tools"
    __table_args__ = (
        UniqueConstraint("pc_name", "project_root", "tool_name", name="uq_rag_agent_tool_pc_root_name"),
    )

    id: Mapped[int] = mapped_column("agent_tools_id", Integer, primary_key=True, autoincrement=True)
    pc_name: Mapped[str] = mapped_column(String(255), default="", index=True)
    project_root: Mapped[str] = mapped_column(String(1200), default="", index=True)
    agent_design_project_id: Mapped[int | None] = mapped_column(ForeignKey("agent_design_projects.id"), nullable=True, index=True)
    collection_id: Mapped[int | None] = mapped_column(ForeignKey("rag_collections.collections_id"), nullable=True, index=True)
    tool_name: Mapped[str] = mapped_column(String(200), default="", index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    search_mode: Mapped[str] = mapped_column(String(40), default="HYBRID")
    top_k: Mapped[int] = mapped_column(Integer, default=5)
    similarity_threshold: Mapped[float] = mapped_column(Float, default=0.20)
    metadata_filter: Mapped[dict] = mapped_column(JSON, default=dict)
    input_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    output_schema: Mapped[dict] = mapped_column(JSON, default=dict)
    prompt_context_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    prompt_context_mode: Mapped[str] = mapped_column(String(50), default="TOOL_RESULT")
    prompt_tool_registered: Mapped[bool] = mapped_column(Boolean, default=False)
    workflow_bound: Mapped[bool] = mapped_column(Boolean, default=False)
    workflow_step_name: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(40), default="ACTIVE", index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RagWorkflowBinding(Base):
    """Persisted mapping from a RAG Tool to a target Agent Workflow step."""

    __tablename__ = "rag_workflow_bindings"
    __table_args__ = (
        UniqueConstraint("tool_id", "agent_design_project_id", name="uq_rag_workflow_binding_tool_project"),
    )

    id: Mapped[int] = mapped_column("workflow_bindings_id", Integer, primary_key=True, autoincrement=True)
    tool_id: Mapped[int] = mapped_column(ForeignKey("rag_agent_tools.agent_tools_id"), index=True)
    agent_design_project_id: Mapped[int | None] = mapped_column(ForeignKey("agent_design_projects.id"), nullable=True, index=True)
    node_name: Mapped[str] = mapped_column(String(200), default="")
    node_label: Mapped[str] = mapped_column(String(300), default="RAG Knowledge 검색")
    trigger_condition: Mapped[str] = mapped_column(Text, default="Knowledge 검색이 필요한 경우")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RagAgentTestLog(Base):
    """Phase-4 RAG Tool / Agent Test preparation and execution audit log."""

    __tablename__ = "rag_agent_test_logs"

    id: Mapped[int] = mapped_column("agent_test_logs_id", Integer, primary_key=True, autoincrement=True)
    pc_name: Mapped[str] = mapped_column(String(255), default="", index=True)
    project_root: Mapped[str] = mapped_column(String(1200), default="", index=True)
    tool_id: Mapped[int] = mapped_column(ForeignKey("rag_agent_tools.agent_tools_id"), index=True)
    test_mode: Mapped[str] = mapped_column(String(40), default="TOOL", index=True)
    query_text: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), default="READY", index=True)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str] = mapped_column(Text, default="")
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class RagIntelligenceSetting(Base):
    """Phase-5 Retrieval Router / Reranking configuration for one project."""

    __tablename__ = "rag_intelligence_settings"
    __table_args__ = (
        UniqueConstraint("pc_name", "project_root", name="uq_rag_intelligence_settings_pc_root"),
    )

    id: Mapped[int] = mapped_column("intelligence_settings_id", Integer, primary_key=True, autoincrement=True)
    pc_name: Mapped[str] = mapped_column(String(255), default="", index=True)
    project_root: Mapped[str] = mapped_column(String(1200), default="", index=True)
    router_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    reranking_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    rerank_top_n: Mapped[int] = mapped_column(Integer, default=12)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RagRecommendationRun(Base):
    """Phase-5 explainable AI RAG recommendation snapshot and apply history."""

    __tablename__ = "rag_recommendation_runs"

    id: Mapped[int] = mapped_column("recommendation_runs_id", Integer, primary_key=True, autoincrement=True)
    pc_name: Mapped[str] = mapped_column(String(255), default="", index=True)
    project_root: Mapped[str] = mapped_column(String(1200), default="", index=True)
    provider: Mapped[str] = mapped_column(String(80), default="")
    status: Mapped[str] = mapped_column(String(40), default="COMPLETED", index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    current_config: Mapped[dict] = mapped_column(JSON, default=dict)
    recommended_config: Mapped[dict] = mapped_column(JSON, default=dict)
    diff_json: Mapped[list] = mapped_column(JSON, default=list)
    evaluation_json: Mapped[dict] = mapped_column(JSON, default=dict)
    test_insights: Mapped[list] = mapped_column(JSON, default=list)
    warnings: Mapped[list] = mapped_column(JSON, default=list)
    applied_keys: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    applied_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class RagSourceOperationSetting(Base):
    """Phase-6 sync policy for one registered Knowledge Source."""

    __tablename__ = "rag_source_operation_settings"
    __table_args__ = (
        UniqueConstraint("source_id", name="uq_rag_source_operation_setting_source"),
    )

    id: Mapped[int] = mapped_column("source_operation_settings_id", Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("rag_sources.sources_id"), index=True)
    sync_mode: Mapped[str] = mapped_column(String(40), default="MANUAL")
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_change_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RagSyncJob(Base):
    """Incremental change-detection / re-index execution record."""

    __tablename__ = "rag_sync_jobs"

    id: Mapped[int] = mapped_column("sync_jobs_id", Integer, primary_key=True, autoincrement=True)
    pc_name: Mapped[str] = mapped_column(String(255), default="", index=True)
    project_root: Mapped[str] = mapped_column(String(1200), default="", index=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("rag_sources.sources_id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="PENDING", index=True)
    stage: Mapped[str] = mapped_column(String(80), default="QUEUED")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    added_count: Mapped[int] = mapped_column(Integer, default=0)
    changed_count: Mapped[int] = mapped_column(Integer, default=0)
    removed_count: Mapped[int] = mapped_column(Integer, default=0)
    unchanged_count: Mapped[int] = mapped_column(Integer, default=0)
    chunks_updated: Mapped[int] = mapped_column(Integer, default=0)
    embeddings_updated: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str] = mapped_column(Text, default="")
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RagDocumentVersion(Base):
    """Rollback-safe snapshot of one indexed document and its Chunk structure."""

    __tablename__ = "rag_document_versions"
    __table_args__ = (
        UniqueConstraint("document_id", "version_no", name="uq_rag_document_version_no"),
    )

    id: Mapped[int] = mapped_column("document_versions_id", Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("rag_documents.documents_id"), index=True)
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    checksum: Mapped[str] = mapped_column(String(64), default="", index=True)
    document_type: Mapped[str] = mapped_column(String(80), default="UNKNOWN")
    language: Mapped[str] = mapped_column(String(80), default="")
    safety_level: Mapped[str] = mapped_column(String(40), default="LOW")
    safety_result: Mapped[dict] = mapped_column(JSON, default=dict)
    chunk_snapshot: Mapped[list] = mapped_column(JSON, default=list)
    source_revision: Mapped[str] = mapped_column(String(300), default="")
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[str] = mapped_column(String(200), default="AGENTSTUDIO")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RagDocumentSecurity(Base):
    """Document-level security grade kept separate from Safety Scan severity."""

    __tablename__ = "rag_document_security"
    __table_args__ = (
        UniqueConstraint("document_id", name="uq_rag_document_security_document"),
    )

    id: Mapped[int] = mapped_column("document_security_id", Integer, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("rag_documents.documents_id"), index=True)
    security_level: Mapped[str] = mapped_column(String(40), default="INTERNAL", index=True)
    note: Mapped[str] = mapped_column(Text, default="")
    updated_by: Mapped[str] = mapped_column(String(200), default="AGENTSTUDIO")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RagAccessRule(Base):
    """Collection access rule. Explicit DENY wins; ALLOW rows make a collection allow-listed."""

    __tablename__ = "rag_access_rules"

    id: Mapped[int] = mapped_column("access_rules_id", Integer, primary_key=True, autoincrement=True)
    pc_name: Mapped[str] = mapped_column(String(255), default="", index=True)
    project_root: Mapped[str] = mapped_column(String(1200), default="", index=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("rag_collections.collections_id"), index=True)
    subject_type: Mapped[str] = mapped_column(String(30), default="ROLE")
    subject_value: Mapped[str] = mapped_column(String(200), default="DEVELOPER", index=True)
    effect: Mapped[str] = mapped_column(String(20), default="ALLOW", index=True)
    permission: Mapped[str] = mapped_column(String(40), default="SEARCH")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RagSearchAuditLog(Base):
    """Security-aware search audit trail independent of Retrieval debug logs."""

    __tablename__ = "rag_search_audit_logs"

    id: Mapped[int] = mapped_column("search_audit_logs_id", Integer, primary_key=True, autoincrement=True)
    pc_name: Mapped[str] = mapped_column(String(255), default="", index=True)
    project_root: Mapped[str] = mapped_column(String(1200), default="", index=True)
    search_log_id: Mapped[int | None] = mapped_column(ForeignKey("rag_search_logs.search_logs_id"), nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(String(200), default="")
    role: Mapped[str] = mapped_column(String(100), default="DEVELOPER", index=True)
    security_clearance: Mapped[str] = mapped_column(String(40), default="INTERNAL")
    query_text: Mapped[str] = mapped_column(Text, default="")
    decision: Mapped[str] = mapped_column(String(40), default="ALLOW", index=True)
    allowed_collection_ids: Mapped[list] = mapped_column(JSON, default=list)
    denied_collection_ids: Mapped[list] = mapped_column(JSON, default=list)
    allowed_source_count: Mapped[int] = mapped_column(Integer, default=0)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class RagEvaluationCase(Base):
    """Repeatable Retrieval quality test case with explicit expected evidence."""

    __tablename__ = "rag_evaluation_cases"

    id: Mapped[int] = mapped_column("evaluation_cases_id", Integer, primary_key=True, autoincrement=True)
    pc_name: Mapped[str] = mapped_column(String(255), default="", index=True)
    project_root: Mapped[str] = mapped_column(String(1200), default="", index=True)
    question: Mapped[str] = mapped_column(Text, default="")
    expected_document_path: Mapped[str] = mapped_column(String(1200), default="")
    expected_text: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class RagEvaluationRun(Base):
    """Repeatable RAG Retrieval evaluation result."""

    __tablename__ = "rag_evaluation_runs"

    id: Mapped[int] = mapped_column("evaluation_runs_id", Integer, primary_key=True, autoincrement=True)
    pc_name: Mapped[str] = mapped_column(String(255), default="", index=True)
    project_root: Mapped[str] = mapped_column(String(1200), default="", index=True)
    status: Mapped[str] = mapped_column(String(40), default="PENDING", index=True)
    total_cases: Mapped[int] = mapped_column(Integer, default=0)
    passed_cases: Mapped[int] = mapped_column(Integer, default=0)
    hit_rate: Mapped[float] = mapped_column(Float, default=0.0)
    mrr: Mapped[float] = mapped_column(Float, default=0.0)
    recall_at_k: Mapped[float] = mapped_column(Float, default=0.0)
    zero_result_rate: Mapped[float] = mapped_column(Float, default=0.0)
    avg_duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    security_context: Mapped[dict] = mapped_column(JSON, default=dict)
    result_json: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str] = mapped_column(Text, default="")
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
