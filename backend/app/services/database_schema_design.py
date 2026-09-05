from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from app.core.table_naming_policy import primary_key_column_name


_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
_ALLOWED_TYPES = {
    "BIGSERIAL", "BIGINT", "INTEGER", "SMALLINT", "TEXT", "VARCHAR(64)",
    "VARCHAR(128)", "VARCHAR(255)", "BOOLEAN", "NUMERIC(18,2)", "NUMERIC(12,2)",
    "TIMESTAMPTZ", "DATE", "JSONB", "UUID", "BYTEA", "VECTOR",
}


def _col(
    name: str,
    data_type: str,
    *,
    nullable: bool = True,
    primary_key: bool = False,
    unique: bool = False,
    default: str = "",
    references: str = "",
) -> dict:
    return {
        "name": name,
        "type": data_type,
        "nullable": nullable,
        "primary_key": primary_key,
        "unique": unique,
        "default": default,
        "references": references,
    }


def _table(name: str, module: str, purpose: str, columns: list[dict], indexes: list[list[str]] | None = None) -> dict:
    return {
        "name": name,
        "module": module,
        "purpose": purpose,
        "source": "module_registry",
        "columns": columns,
        "indexes": indexes or [],
    }

def _infer_table_crud(table: dict) -> list[str]:
    explicit = table.get("crud")
    if isinstance(explicit, str):
        values = [x.strip().upper() for x in re.split(r"[,/\s]+", explicit) if x.strip()]
    elif isinstance(explicit, (list, tuple, set)):
        values = [str(x).strip().upper() for x in explicit if str(x).strip()]
    else:
        values = []
    normalized = []
    aliases = {"CREATE": "C", "READ": "R", "UPDATE": "U", "DELETE": "D", "C": "C", "R": "R", "U": "U", "D": "D"}
    for value in values:
        mapped = aliases.get(value)
        if mapped and mapped not in normalized:
            normalized.append(mapped)
    if normalized:
        return normalized

    name = str(table.get("name") or "").lower()
    purpose = str(table.get("purpose") or "").lower()
    source = str(table.get("source") or "").lower()
    module = str(table.get("module") or "").upper()
    text = f"{name} {purpose}"
    columns = {str(x.get("name") or "") for x in table.get("columns") or [] if isinstance(x, dict)}

    append_only_markers = ("log", "logs", "history", "event", "events", "run_steps", "artifact", "version", "message", "chunk", "audit")
    if any(marker in text for marker in append_only_markers):
        return ["C", "R"]
    if "updated_at" in columns:
        crud = ["C", "R", "U"]
        if "is_deleted" in columns or source == "llm_custom_business":
            crud.append("D")
        return crud
    if source == "llm_custom_business":
        return ["C", "R", "U", "D"]
    if module in {"CORE", "MEMORY"} and name not in {"agent_versions", "workflows", "workflow_nodes", "workflow_edges"}:
        return ["C", "R", "U", "D"]
    return ["C", "R"]


def _policy_column(name: str) -> dict:
    if name == "id":
        return _col("id", "BIGSERIAL", nullable=False, primary_key=True)
    if name == "created_at":
        return _col("created_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP")
    if name == "updated_at":
        return _col("updated_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP")
    if name == "is_deleted":
        return _col("is_deleted", "BOOLEAN", nullable=False, default="FALSE")
    if name in {"created_by", "updated_by"}:
        return _col(name, "BIGINT", nullable=True)
    raise KeyError(name)


def apply_common_table_policy(plan: dict) -> dict:
    """Apply AgentStudio's default relational table policy before Preview/DDL generation.

    v5.595 database identity rule:
    - Never generate a bare ``id`` PK for a new table.
    - Default PK is ``{logical_table_name}_id``.
    - Technical prefixes such as ``rag_`` / ``app_`` are stripped.
    - A project-specific prefix can be supplied through ``common_policy.id_prefixes``.
    - Existing explicit non-``id`` PKs are preserved.
    """
    result = copy.deepcopy(plan or {})
    pk_name_by_table: dict[str, str] = {}
    for table in result.get("tables") or []:
        if not isinstance(table, dict):
            continue
        table_name = str(table.get("name") or "").strip().lower()
        crud = _infer_table_crud(table)
        columns = [dict(x) for x in table.get("columns") or [] if isinstance(x, dict)]
        policy = table.get("common_policy") if isinstance(table.get("common_policy"), dict) else {}
        overrides = policy.get("overrides") if isinstance(policy.get("overrides"), dict) else {}
        id_prefixes = policy.get("id_prefixes") if isinstance(policy.get("id_prefixes"), (list, tuple, set)) else []
        default_id_name = primary_key_column_name(table_name, prefixes=id_prefixes)

        # The user's global rule applies to generated default IDs. Explicit business/natural PKs remain intact.
        pk_columns = [x for x in columns if x.get("primary_key")]
        if not pk_columns:
            id_col = _policy_column("id")
            id_col["name"] = default_id_name
            columns.insert(0, id_col)
            pk_columns = [id_col]
        elif len(pk_columns) == 1 and str(pk_columns[0].get("name") or "").strip().lower() == "id":
            pk_columns[0]["name"] = default_id_name

        pk_name_by_table[table_name] = str(pk_columns[0].get("name") or default_id_name) if pk_columns else default_id_name
        names = {str(x.get("name") or "") for x in columns}

        wants_update = "U" in crud
        wants_delete = wants_update and "D" in crud
        recommendations = {
            "id": True,
            "created_at": wants_update,
            "updated_at": wants_update,
            "is_deleted": wants_delete,
            "created_by": wants_update,
            "updated_by": wants_update,
        }
        for key, default_enabled in list(recommendations.items()):
            if key in overrides:
                recommendations[key] = bool(overrides[key])

        for name in ("created_at", "updated_at", "is_deleted", "created_by", "updated_by"):
            enabled = recommendations[name]
            if enabled and name not in names:
                columns.append(_policy_column(name))
                names.add(name)
            elif not enabled and name in names and name in overrides:
                columns = [x for x in columns if str(x.get("name") or "") != name]
                names.discard(name)

        reason = []
        if wants_update:
            reason.append("수정 가능한 데이터로 판단하여 등록/수정 시각과 작업 주체 추적 컬럼을 추천")
        else:
            reason.append("생성 후 수정하지 않는 조회/로그성 데이터로 판단하여 수정 Audit 컬럼 제외")
        if wants_delete:
            reason.append("수정·삭제 기능이 있어 Soft Delete(is_deleted) 추천")
        else:
            reason.append("삭제 기능이 명시되지 않아 is_deleted 제외")
        if any(bool(x.get("unique")) for x in columns) and recommendations.get("is_deleted"):
            reason.append("Soft Delete + UNIQUE 충돌 방지를 위해 활성 데이터 Partial Unique Index 사용")

        table["columns"] = columns
        table["crud"] = crud
        table["common_policy"] = {
            **policy,
            "status": "USER_FIXED" if overrides else "RECOMMENDED",
            "recommendations": recommendations,
            "overrides": overrides,
            "reason": reason,
            "id_name": pk_name_by_table.get(table_name, default_id_name),
            "identity_strategy": "BIGINT GENERATED BY DEFAULT AS IDENTITY",
            "updated_at_strategy": "shared trigger function",
        }

    # Registry/custom plans historically referenced ``target_table.id``. Rewrite those references
    # to the normalized physical PK column so generated DDL never points at a non-existent bare id.
    for table in result.get("tables") or []:
        if not isinstance(table, dict):
            continue
        for column in table.get("columns") or []:
            if not isinstance(column, dict):
                continue
            ref = str(column.get("references") or "").strip().lower()
            if not ref or "." not in ref:
                continue
            ref_table, ref_column = ref.split(".", 1)
            if ref_column == "id" and ref_table in pk_name_by_table:
                column["references"] = f"{ref_table}.{pk_name_by_table[ref_table]}"
    return result


def apply_common_table_policy_overrides(plan: dict, overrides: dict | None) -> dict:
    result = copy.deepcopy(plan or {})
    override_map = overrides if isinstance(overrides, dict) else {}
    for table in result.get("tables") or []:
        name = str(table.get("name") or "")
        value = override_map.get(name)
        if not isinstance(value, dict):
            continue
        policy = table.get("common_policy") if isinstance(table.get("common_policy"), dict) else {}
        table["common_policy"] = {**policy, "overrides": {**(policy.get("overrides") or {}), **value}}
    return apply_common_table_policy(result)


MODULE_REGISTRY: dict[str, dict[str, Any]] = {
    "CORE": {
        "label": "Agent Core",
        "reason": "Agent 정의, 버전, 기능, 설정, Workflow를 공통 관리합니다.",
        "tables": [
            _table("agents", "CORE", "Agent 기본 정보", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("name", "VARCHAR(128)", nullable=False, unique=True),
                _col("agent_type", "VARCHAR(64)", nullable=False, default="'custom'"),
                _col("description", "TEXT"),
                _col("status", "VARCHAR(64)", nullable=False, default="'ACTIVE'"),
                _col("metadata", "JSONB", nullable=False, default="'{}'::jsonb"),
                _col("created_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
                _col("updated_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
            ]),
            _table("agent_versions", "CORE", "Agent 버전 이력", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("agent_id", "BIGINT", nullable=False, references="agents.id"),
                _col("version", "VARCHAR(64)", nullable=False),
                _col("definition", "JSONB", nullable=False, default="'{}'::jsonb"),
                _col("created_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
            ], [["agent_id", "version"]]),
            _table("agent_features", "CORE", "Agent 기능 등록 및 기능별 설정", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("agent_id", "BIGINT", nullable=False, references="agents.id"),
                _col("feature_type", "VARCHAR(64)", nullable=False),
                _col("feature_name", "VARCHAR(128)", nullable=False),
                _col("enabled", "BOOLEAN", nullable=False, default="TRUE"),
                _col("config", "JSONB", nullable=False, default="'{}'::jsonb"),
                _col("created_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
            ], [["agent_id", "feature_type"]]),
            _table("agent_settings", "CORE", "런타임 설정과 비밀값 참조 메타데이터", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("agent_id", "BIGINT", nullable=False, references="agents.id"),
                _col("setting_key", "VARCHAR(128)", nullable=False),
                _col("setting_value", "JSONB", nullable=False, default="'{}'::jsonb"),
                _col("is_secret", "BOOLEAN", nullable=False, default="FALSE"),
                _col("updated_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
            ], [["agent_id", "setting_key"]]),
            _table("workflows", "CORE", "Agent Workflow 정의", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("agent_id", "BIGINT", nullable=False, references="agents.id"),
                _col("name", "VARCHAR(128)", nullable=False),
                _col("version", "VARCHAR(64)", nullable=False, default="'1'"),
                _col("definition", "JSONB", nullable=False, default="'{}'::jsonb"),
                _col("created_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
            ]),
            _table("workflow_nodes", "CORE", "Workflow Node 정의", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("workflow_id", "BIGINT", nullable=False, references="workflows.id"),
                _col("node_key", "VARCHAR(128)", nullable=False),
                _col("node_type", "VARCHAR(64)", nullable=False),
                _col("name", "VARCHAR(128)", nullable=False),
                _col("config", "JSONB", nullable=False, default="'{}'::jsonb"),
                _col("position_x", "INTEGER"),
                _col("position_y", "INTEGER"),
            ], [["workflow_id", "node_key"]]),
            _table("workflow_edges", "CORE", "Workflow Node 간 연결", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("workflow_id", "BIGINT", nullable=False, references="workflows.id"),
                _col("source_node_key", "VARCHAR(128)", nullable=False),
                _col("target_node_key", "VARCHAR(128)", nullable=False),
                _col("condition", "TEXT"),
                _col("metadata", "JSONB", nullable=False, default="'{}'::jsonb"),
            ], [["workflow_id", "source_node_key"]]),
        ],
    },
    "OBSERVABILITY": {
        "label": "Agent Run / Observability",
        "reason": "실행 단계, Tool/LLM 오류와 산출물을 추적하여 디버깅할 수 있게 합니다.",
        "tables": [
            _table("agent_runs", "OBSERVABILITY", "Agent 실행 이력", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("agent_id", "BIGINT", nullable=False, references="agents.id"),
                _col("status", "VARCHAR(64)", nullable=False),
                _col("input", "JSONB", nullable=False, default="'{}'::jsonb"),
                _col("output", "JSONB", nullable=False, default="'{}'::jsonb"),
                _col("started_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
                _col("finished_at", "TIMESTAMPTZ"),
            ], [["agent_id", "started_at"]]),
            _table("agent_run_steps", "OBSERVABILITY", "Agent 실행 단계별 기록", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("run_id", "BIGINT", nullable=False, references="agent_runs.id"),
                _col("step_name", "VARCHAR(128)", nullable=False),
                _col("step_type", "VARCHAR(64)", nullable=False),
                _col("status", "VARCHAR(64)", nullable=False),
                _col("duration_ms", "INTEGER"),
                _col("detail", "JSONB", nullable=False, default="'{}'::jsonb"),
                _col("created_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
            ], [["run_id", "created_at"]]),
            _table("artifacts", "OBSERVABILITY", "Agent 실행 결과 파일/리포트 메타데이터", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("run_id", "BIGINT", references="agent_runs.id"),
                _col("artifact_type", "VARCHAR(64)", nullable=False),
                _col("path", "TEXT", nullable=False),
                _col("metadata", "JSONB", nullable=False, default="'{}'::jsonb"),
                _col("created_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
            ]),
        ],
    },
    "CONVERSATION": {
        "label": "Conversation",
        "reason": "상담/챗/인터뷰의 Session과 Message 이력을 저장합니다.",
        "tables": [
            _table("conversations", "CONVERSATION", "대화 세션", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("agent_id", "BIGINT", nullable=False, references="agents.id"),
                _col("external_user_id", "VARCHAR(128)"),
                _col("state", "JSONB", nullable=False, default="'{}'::jsonb"),
                _col("created_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
                _col("updated_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
            ], [["agent_id", "updated_at"]]),
            _table("messages", "CONVERSATION", "대화 메시지", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("conversation_id", "BIGINT", nullable=False, references="conversations.id"),
                _col("role", "VARCHAR(64)", nullable=False),
                _col("content", "TEXT", nullable=False),
                _col("metadata", "JSONB", nullable=False, default="'{}'::jsonb"),
                _col("created_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
            ], [["conversation_id", "created_at"]]),
        ],
    },
    "MEMORY": {
        "label": "Memory",
        "reason": "세션 밖에서도 유지되는 장기/의미 기억을 관리합니다.",
        "tables": [
            _table("long_term_memory", "MEMORY", "Agent 장기 기억", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("agent_id", "BIGINT", nullable=False, references="agents.id"),
                _col("external_user_id", "VARCHAR(128)"),
                _col("memory_type", "VARCHAR(64)", nullable=False),
                _col("content", "TEXT", nullable=False),
                _col("metadata", "JSONB", nullable=False, default="'{}'::jsonb"),
                _col("embedding", "VECTOR"),
                _col("created_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
                _col("updated_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
            ], [["agent_id", "memory_type"]]),
        ],
    },
    "FILE": {
        "label": "File / Document",
        "reason": "업로드/참고 문서와 분석 결과를 버전 단위로 관리합니다.",
        "tables": [
            _table("documents", "FILE", "문서 기본 정보", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("agent_id", "BIGINT", references="agents.id"),
                _col("file_name", "VARCHAR(255)", nullable=False),
                _col("source_uri", "TEXT"),
                _col("mime_type", "VARCHAR(128)"),
                _col("sha256", "VARCHAR(64)"),
                _col("metadata", "JSONB", nullable=False, default="'{}'::jsonb"),
                _col("created_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
            ], [["sha256"]]),
            _table("document_versions", "FILE", "문서 버전과 추출 텍스트", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("document_id", "BIGINT", nullable=False, references="documents.id"),
                _col("version_no", "INTEGER", nullable=False, default="1"),
                _col("extracted_text", "TEXT"),
                _col("metadata", "JSONB", nullable=False, default="'{}'::jsonb"),
                _col("created_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
            ], [["document_id", "version_no"]]),
            _table("document_analysis", "FILE", "문서 분석/요구사항 추출 결과", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("document_id", "BIGINT", nullable=False, references="documents.id"),
                _col("analysis_type", "VARCHAR(64)", nullable=False),
                _col("summary", "TEXT"),
                _col("requirements", "JSONB", nullable=False, default="'{}'::jsonb"),
                _col("technologies", "JSONB", nullable=False, default="'[]'::jsonb"),
                _col("provider", "VARCHAR(64)"),
                _col("model", "VARCHAR(128)"),
                _col("created_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
            ], [["document_id", "analysis_type"]]),
        ],
    },
    "RAG": {
        "label": "RAG / Vector",
        "reason": "Knowledge Base, Chunk, Embedding 검색을 관리합니다.",
        "tables": [
            _table("knowledge_bases", "RAG", "RAG Knowledge Base", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("agent_id", "BIGINT", nullable=False, references="agents.id"),
                _col("name", "VARCHAR(128)", nullable=False),
                _col("config", "JSONB", nullable=False, default="'{}'::jsonb"),
                _col("created_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
            ]),
            _table("document_chunks", "RAG", "RAG 검색 단위 Chunk와 Embedding", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("knowledge_base_id", "BIGINT", nullable=False, references="knowledge_bases.id"),
                _col("document_id", "BIGINT", references="documents.id"),
                _col("chunk_index", "INTEGER", nullable=False),
                _col("content", "TEXT", nullable=False),
                _col("metadata", "JSONB", nullable=False, default="'{}'::jsonb"),
                _col("embedding", "VECTOR"),
                _col("created_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
            ], [["knowledge_base_id", "chunk_index"]]),
            _table("retrieval_logs", "RAG", "RAG 검색 품질/근거 이력", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("run_id", "BIGINT", references="agent_runs.id"),
                _col("query", "TEXT", nullable=False),
                _col("top_k", "INTEGER", nullable=False, default="5"),
                _col("results", "JSONB", nullable=False, default="'[]'::jsonb"),
                _col("created_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
            ]),
        ],
    },
    "MCP_TOOL": {
        "label": "MCP / Tool",
        "reason": "Tool Registry와 MCP Server 연결을 Agent와 다대다로 관리합니다.",
        "tables": [
            _table("tools", "MCP_TOOL", "재사용 가능한 Tool 정의", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("name", "VARCHAR(128)", nullable=False, unique=True),
                _col("description", "TEXT"),
                _col("capability", "VARCHAR(128)"),
                _col("risk_level", "VARCHAR(64)", nullable=False, default="'LOW'"),
                _col("input_schema", "JSONB", nullable=False, default="'{}'::jsonb"),
                _col("created_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
            ]),
            _table("mcp_servers", "MCP_TOOL", "MCP Server/Transport 설정", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("name", "VARCHAR(128)", nullable=False, unique=True),
                _col("transport", "VARCHAR(64)", nullable=False),
                _col("endpoint", "TEXT"),
                _col("config", "JSONB", nullable=False, default="'{}'::jsonb"),
                _col("enabled", "BOOLEAN", nullable=False, default="TRUE"),
                _col("created_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
            ]),
            _table("agent_tool_bindings", "MCP_TOOL", "Agent와 Tool/MCP 연결", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("agent_id", "BIGINT", nullable=False, references="agents.id"),
                _col("tool_id", "BIGINT", references="tools.id"),
                _col("mcp_server_id", "BIGINT", references="mcp_servers.id"),
                _col("enabled", "BOOLEAN", nullable=False, default="TRUE"),
                _col("policy", "JSONB", nullable=False, default="'{}'::jsonb"),
            ], [["agent_id", "tool_id"]]),
        ],
    },
    "CUSTOMER": {
        "label": "Customer",
        "reason": "고객/회원 식별과 업무 데이터를 Agent 시스템 데이터와 분리합니다.",
        "tables": [
            _table("customers", "CUSTOMER", "업무 고객 정보", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("external_customer_id", "VARCHAR(128)", unique=True),
                _col("name", "VARCHAR(128)"),
                _col("email", "VARCHAR(255)"),
                _col("metadata", "JSONB", nullable=False, default="'{}'::jsonb"),
                _col("created_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
            ]),
        ],
    },
    "PRODUCT": {
        "label": "Product",
        "reason": "상품/서비스 Catalog를 독립된 업무 Entity로 관리합니다.",
        "tables": [
            _table("products", "PRODUCT", "상품/서비스 정보", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("product_code", "VARCHAR(128)", nullable=False, unique=True),
                _col("name", "VARCHAR(255)", nullable=False),
                _col("description", "TEXT"),
                _col("price", "NUMERIC(18,2)"),
                _col("active", "BOOLEAN", nullable=False, default="TRUE"),
                _col("metadata", "JSONB", nullable=False, default="'{}'::jsonb"),
                _col("created_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
            ]),
        ],
    },
    "ORDER": {
        "label": "Order",
        "reason": "주문과 주문 품목을 분리하여 확장 가능한 거래 모델을 구성합니다.",
        "tables": [
            _table("orders", "ORDER", "주문 Header", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("customer_id", "BIGINT", references="customers.id"),
                _col("order_status", "VARCHAR(64)", nullable=False, default="'CREATED'"),
                _col("total_amount", "NUMERIC(18,2)"),
                _col("metadata", "JSONB", nullable=False, default="'{}'::jsonb"),
                _col("created_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
            ], [["customer_id", "created_at"]]),
            _table("order_items", "ORDER", "주문 품목", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("order_id", "BIGINT", nullable=False, references="orders.id"),
                _col("product_id", "BIGINT", references="products.id"),
                _col("quantity", "INTEGER", nullable=False, default="1"),
                _col("unit_price", "NUMERIC(18,2)"),
                _col("metadata", "JSONB", nullable=False, default="'{}'::jsonb"),
            ], [["order_id"]]),
        ],
    },
    "REPORT": {
        "label": "Report / Dashboard",
        "reason": "생성 리포트와 Dashboard 집계 결과를 재사용할 수 있게 저장합니다.",
        "tables": [
            _table("reports", "REPORT", "리포트 메타데이터와 결과", [
                _col("id", "BIGSERIAL", nullable=False, primary_key=True),
                _col("agent_id", "BIGINT", references="agents.id"),
                _col("report_type", "VARCHAR(64)", nullable=False),
                _col("title", "VARCHAR(255)", nullable=False),
                _col("payload", "JSONB", nullable=False, default="'{}'::jsonb"),
                _col("created_at", "TIMESTAMPTZ", nullable=False, default="CURRENT_TIMESTAMP"),
            ], [["agent_id", "created_at"]]),
        ],
    },
}


def _payload_text(request: str, design: dict | None) -> str:
    design = design or {}
    focused = {
        "requirement_spec": design.get("requirement_spec") or {},
        "capability_plan": design.get("capability_plan") or {},
        "agent_architecture": design.get("agent_architecture") or {},
    }
    return (request + "\n" + json.dumps(focused, ensure_ascii=False)).casefold()


def _database_explicitly_disabled(text: str) -> bool:
    return any(x in text for x in (
        "db 사용하지", "db는 사용하지", "database 사용하지", "database를 사용하지",
        "데이터베이스를 사용하지", "데이터베이스는 사용하지",
        "db 미사용", "데이터베이스 미사용", "database disabled",
    ))


def _database_needed(text: str, design: dict | None) -> bool:
    if _database_explicitly_disabled(text):
        return False
    markers = (
        "postgres", "postgresql", "supabase", "database", "데이터베이스", " db ",
        "rag", "pgvector", "vector db", "벡터 db", "embedding 저장", "임베딩 저장",
        "장기 메모리", "long term memory", "대화 이력 저장", "conversation history 저장",
        "주문", "고객", "상품", "결제", "inventory", "재고",
    )
    if any(x in text for x in markers):
        return True
    persistence = json.dumps(
        (design or {}).get("agent_architecture", {}).get("persistence") or [],
        ensure_ascii=False,
    ).casefold()
    return any(x in persistence for x in ("postgres", "database", "db", "pgvector", "supabase"))


def _selected_modules(text: str) -> list[str]:
    selected = ["CORE", "OBSERVABILITY"]

    rules = [
        ("CONVERSATION", ("chat", "챗", "대화", "상담", "인터뷰", "conversation")),
        ("MEMORY", ("memory", "메모리", "장기 기억", "long term")),
        ("FILE", ("file", "파일", "document", "문서", "pdf", "csv", "xlsx", "ppt", "업로드")),
        ("RAG", ("rag", "pgvector", "vector", "벡터", "embedding", "임베딩", "knowledge base")),
        ("MCP_TOOL", ("mcp", "tool", "도구", "tool registry")),
        ("CUSTOMER", ("customer", "고객", "회원", "사용자 정보")),
        ("PRODUCT", ("product", "상품", "제품", "catalog", "카탈로그")),
        ("ORDER", ("order", "주문", "장바구니", "결제")),
        ("REPORT", ("report", "리포트", "dashboard", "대시보드", "통계", "분석 결과")),
    ]
    for module_id, markers in rules:
        if any(marker in text for marker in markers):
            selected.append(module_id)

    if "RAG" in selected and "FILE" not in selected:
        selected.append("FILE")
    if "ORDER" in selected:
        for dep in ("CUSTOMER", "PRODUCT"):
            if dep not in selected:
                selected.append(dep)
    return selected


def _normalize_type(value: str) -> str:
    raw = str(value or "TEXT").strip().upper()
    raw = re.sub(r"\s+", " ", raw)
    if raw.startswith("VARCHAR(") and re.fullmatch(r"VARCHAR\((?:[1-9]\d{0,3})\)", raw):
        return raw
    if raw.startswith("NUMERIC(") and re.fullmatch(r"NUMERIC\(\d{1,2},\d{1,2}\)", raw):
        return raw
    return raw if raw in _ALLOWED_TYPES else "TEXT"


def _normalize_custom_table(raw: dict) -> dict | None:
    name = str(raw.get("name") or "").strip().lower()
    if not _IDENTIFIER_RE.fullmatch(name):
        return None
    columns: list[dict] = []
    seen: set[str] = set()
    for item in raw.get("columns") or []:
        if not isinstance(item, dict):
            continue
        column_name = str(item.get("name") or "").strip().lower()
        if not _IDENTIFIER_RE.fullmatch(column_name) or column_name in seen:
            continue
        seen.add(column_name)
        references = str(item.get("references") or "").strip().lower()
        if references and not re.fullmatch(r"[a-z][a-z0-9_]{0,62}\.[a-z][a-z0-9_]{0,62}", references):
            references = ""
        columns.append(_col(
            column_name,
            _normalize_type(item.get("type") or item.get("data_type") or "TEXT"),
            nullable=bool(item.get("nullable", True)),
            primary_key=bool(item.get("primary_key") or item.get("pk")),
            unique=bool(item.get("unique")),
            default=str(item.get("default") or "").strip(),
            references=references,
        ))
    if not columns:
        return None
    if not any(c["primary_key"] for c in columns):
        columns.insert(0, _col(primary_key_column_name(name), "BIGSERIAL", nullable=False, primary_key=True))
    return {
        "name": name,
        "module": "CUSTOM_BUSINESS",
        "purpose": str(raw.get("purpose") or "업무 전용 Entity").strip(),
        "source": "llm_custom_business",
        "columns": columns,
        "indexes": [x for x in (raw.get("indexes") or []) if isinstance(x, list)],
    }


def validate_database_plan(plan: dict) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    tables = plan.get("tables") or []
    names: set[str] = set()
    table_columns: dict[str, set[str]] = {}

    for table in tables:
        name = str(table.get("name") or "")
        if not _IDENTIFIER_RE.fullmatch(name):
            errors.append(f"허용되지 않는 테이블명: {name or '(empty)'}")
            continue
        if name in names:
            errors.append(f"중복 테이블명: {name}")
            continue
        names.add(name)
        columns = table.get("columns") or []
        col_names: set[str] = set()
        if not columns:
            errors.append(f"컬럼이 없는 테이블: {name}")
        for column in columns:
            cname = str(column.get("name") or "")
            if not _IDENTIFIER_RE.fullmatch(cname):
                errors.append(f"{name}: 허용되지 않는 컬럼명 {cname or '(empty)'}")
                continue
            if cname in col_names:
                errors.append(f"{name}: 중복 컬럼 {cname}")
            col_names.add(cname)
        if columns and not any(bool(x.get("primary_key")) for x in columns):
            warnings.append(f"{name}: 명시적인 Primary Key가 없습니다.")
        if any(bool(x.get("primary_key")) and str(x.get("name") or "").strip().lower() == "id" for x in columns):
            errors.append(f"{name}: 기본 Primary Key에 단순 id를 사용할 수 없습니다. 테이블명 기반 *_id를 사용하세요.")
        table_columns[name] = col_names

    for table in tables:
        for column in table.get("columns") or []:
            ref = str(column.get("references") or "")
            if not ref:
                continue
            ref_table, _, ref_col = ref.partition(".")
            if ref_table not in names:
                errors.append(f"{table.get('name')}.{column.get('name')}: 존재하지 않는 FK 테이블 {ref_table}")
            elif ref_col not in table_columns.get(ref_table, set()):
                errors.append(f"{table.get('name')}.{column.get('name')}: 존재하지 않는 FK 컬럼 {ref}")

    selected = [x.get("id") for x in plan.get("modules") or [] if isinstance(x, dict)]
    if plan.get("enabled") and "CORE" not in selected:
        errors.append("DB를 사용하는 Agent는 CORE 모듈이 필요합니다.")
    if "RAG" in selected and "FILE" not in selected:
        warnings.append("RAG 모듈은 FILE 모듈과 함께 사용하는 것을 권장합니다.")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "table_count": len(tables),
        "module_count": len(selected),
    }


def _safe_default(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    upper = raw.upper()
    if upper in {"CURRENT_TIMESTAMP", "TRUE", "FALSE", "NULL"}:
        return upper
    if re.fullmatch(r"-?\d+(?:\.\d+)?", raw):
        return raw
    if re.fullmatch(r"'[^']*'(?:::[a-z0-9_]+)?", raw, re.I):
        return raw
    return ""


def generate_postgresql_ddl(plan: dict) -> str:
    if not plan.get("enabled"):
        return "-- Database module is disabled for this Agent.\n"

    selected = {str(x.get("id") or "") for x in plan.get("modules") or [] if isinstance(x, dict)}
    lines = [
        "-- Generated by THEANOVA AgentStudio DB Module Designer",
        "-- Review/confirm this migration before applying it to a database.",
        "BEGIN;",
        "",
    ]
    if "RAG" in selected or "MEMORY" in selected:
        lines.extend(["CREATE EXTENSION IF NOT EXISTS vector;", ""])

    foreign_keys: list[tuple[str, str, str, str]] = []
    partial_unique_indexes: list[tuple[str, str]] = []
    updated_at_tables: list[str] = []
    tables = apply_common_table_policy(plan).get("tables") or []
    # 모든 테이블을 먼저 만든 뒤 FK를 추가하여 Custom Entity 간 참조 순서에 의존하지 않습니다.
    for table in tables:
        name = str(table.get("name") or "")
        purpose = str(table.get("purpose") or "").replace("\n", " ")
        lines.append(f"-- {purpose}")
        lines.append(f"CREATE TABLE IF NOT EXISTS {name} (")
        definitions: list[str] = []
        for column in table.get("columns") or []:
            cname = str(column.get("name") or "")
            ctype = _normalize_type(column.get("type") or "TEXT")
            if column.get("primary_key") and ctype == "BIGSERIAL":
                row = f"    {cname} BIGINT GENERATED BY DEFAULT AS IDENTITY"
            else:
                row = f"    {cname} {ctype}"
            if column.get("primary_key"):
                row += " PRIMARY KEY"
            if not bool(column.get("nullable", True)):
                row += " NOT NULL"
            soft_delete = any(str(x.get("name") or "") == "is_deleted" for x in table.get("columns") or [] if isinstance(x, dict))
            if column.get("unique") and soft_delete:
                partial_unique_indexes.append((name, cname))
            elif column.get("unique"):
                row += " UNIQUE"
            default = _safe_default(column.get("default") or "")
            if default:
                row += f" DEFAULT {default}"
            ref = str(column.get("references") or "")
            if ref and re.fullmatch(r"[a-z][a-z0-9_]{0,62}\.[a-z][a-z0-9_]{0,62}", ref):
                ref_table, ref_column = ref.split(".", 1)
                foreign_keys.append((name, cname, ref_table, ref_column))
            definitions.append(row)
        lines.append(",\n".join(definitions))
        lines.extend([");", ""])

        for index_no, index_columns in enumerate(table.get("indexes") or [], 1):
            cols = [str(x).lower() for x in index_columns if _IDENTIFIER_RE.fullmatch(str(x).lower())]
            if not cols:
                continue
            index_name = f"idx_{name}_{'_'.join(cols)}"
            if len(index_name) > 63:
                index_name = f"idx_{name}_{index_no}"
            lines.append(f"CREATE INDEX IF NOT EXISTS {index_name} ON {name} ({', '.join(cols)});")
        if table.get("indexes"):
            lines.append("")
        if any(str(x.get("name") or "") == "updated_at" for x in table.get("columns") or [] if isinstance(x, dict)):
            updated_at_tables.append(name)

    for table_name, column_name in partial_unique_indexes:
        index_name = f"ux_{table_name}_{column_name}_active"[:63]
        lines.append(f"CREATE UNIQUE INDEX IF NOT EXISTS {index_name} ON {table_name} ({column_name}) WHERE is_deleted = FALSE;")
    if partial_unique_indexes:
        lines.append("")

    if updated_at_tables:
        lines.extend([
            "CREATE OR REPLACE FUNCTION agentstudio_set_updated_at()",
            "RETURNS TRIGGER AS $$",
            "BEGIN",
            "    NEW.updated_at = CURRENT_TIMESTAMP;",
            "    RETURN NEW;",
            "END;",
            "$$ LANGUAGE plpgsql;",
            "",
        ])
        for table_name in updated_at_tables:
            trigger_name = f"trg_{table_name}_updated_at"[:63]
            lines.extend([
                f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name};",
                f"CREATE TRIGGER {trigger_name} BEFORE UPDATE ON {table_name}",
                "FOR EACH ROW EXECUTE FUNCTION agentstudio_set_updated_at();",
            ])
        lines.append("")

    if foreign_keys:
        lines.extend(["-- Foreign keys are applied after all tables exist.", ""])
    for table_name, column_name, ref_table, ref_column in foreign_keys:
        constraint = f"fk_{table_name}_{column_name}"
        if len(constraint) > 63:
            constraint = constraint[:63]
        # Migration은 1회 적용을 전제로 하되, 삭제 연쇄는 보수적으로 RESTRICT합니다.
        lines.append(
            f"ALTER TABLE {table_name} ADD CONSTRAINT {constraint} "
            f"FOREIGN KEY ({column_name}) REFERENCES {ref_table}({ref_column}) ON DELETE RESTRICT;"
        )
    if foreign_keys:
        lines.append("")

    lines.extend(["COMMIT;", ""])
    return "\n".join(lines)


def build_database_plan(request: str, design: dict | None = None) -> dict:
    design = design or {}
    text = _payload_text(request, design)
    enabled = _database_needed(text, design)
    if not enabled:
        return {
            "enabled": False,
            "engine": "none",
            "strategy": "DB가 필요하지 않은 Agent로 판단되어 스키마를 생성하지 않습니다.",
            "modules": [],
            "tables": [],
            "relationships": [],
            "jsonb_policy": "설정성/확장 메타데이터만 JSONB로 저장합니다.",
            "validation": {"valid": True, "errors": [], "warnings": [], "table_count": 0, "module_count": 0},
            "confirmed": True,
            "finalized": True,
            "migration_files": [],
            "ddl": "-- Database module is disabled for this Agent.\n",
        }

    module_ids = _selected_modules(text)
    modules = [
        {
            "id": module_id,
            "label": MODULE_REGISTRY[module_id]["label"],
            "reason": MODULE_REGISTRY[module_id]["reason"],
            "required": module_id in {"CORE", "OBSERVABILITY"},
        }
        for module_id in module_ids
    ]

    tables: list[dict] = []
    seen: set[str] = set()
    for module_id in module_ids:
        for table in MODULE_REGISTRY[module_id]["tables"]:
            value = copy.deepcopy(table)
            if value["name"] not in seen:
                seen.add(value["name"])
                tables.append(value)

    raw_plan = design.get("database_plan") or {}
    for raw in raw_plan.get("custom_tables") or raw_plan.get("tables") or []:
        if not isinstance(raw, dict):
            continue
        custom = _normalize_custom_table(raw)
        if custom and custom["name"] not in seen:
            seen.add(custom["name"])
            tables.append(custom)

    policy_seed = {"tables": tables}
    policy_seed = apply_common_table_policy(policy_seed)
    tables = policy_seed.get("tables") or tables

    relationships: list[dict] = []
    for table in tables:
        for column in table.get("columns") or []:
            ref = str(column.get("references") or "")
            if ref:
                relationships.append({
                    "from": f"{table['name']}.{column['name']}",
                    "to": ref,
                    "type": "many-to-one",
                })

    plan = {
        "enabled": True,
        "engine": "PostgreSQL",
        "schema_name": str(raw_plan.get("schema_name") or "public"),
        "strategy": "공통 Core + 기능별 Module + 검증된 Custom Business Entity 조립",
        "modules": modules,
        "tables": tables,
        "relationships": relationships,
        "jsonb_policy": "기능 설정/metadata/확장 필드는 JSONB, 검색·JOIN·집계가 필요한 핵심 업무 값은 정규 컬럼으로 저장합니다.",
        "custom_design_notes": raw_plan.get("custom_design_notes") or [],
        "confirmed": False,
        "finalized": False,
        "migration_files": [
            {"path": "backend/migrations/001_initial_schema.sql", "purpose": "확정된 PostgreSQL 초기 DDL"},
            {"path": "backend/migrations/README.md", "purpose": "DB 모듈/적용 순서/검증 안내"},
        ],
    }
    plan["validation"] = validate_database_plan(plan)
    return plan


def finalize_database_plan(plan: dict) -> dict:
    result = apply_common_table_policy(copy.deepcopy(plan or {}))
    if not result.get("enabled"):
        result.update({"confirmed": True, "finalized": True, "ddl": "-- Database module is disabled for this Agent.\n"})
        result["validation"] = validate_database_plan(result)
        return result

    validation = validate_database_plan(result)
    result["validation"] = validation
    if not validation["valid"]:
        result["confirmed"] = False
        result["finalized"] = False
        result.pop("ddl", None)
        return result
    result["ddl"] = generate_postgresql_ddl(result)
    result["confirmed"] = True
    result["finalized"] = True
    return result


def database_plan_readme(plan: dict) -> str:
    module_lines = [
        f"- `{x.get('id')}` {x.get('label')}: {x.get('reason')}"
        for x in plan.get("modules") or []
        if isinstance(x, dict)
    ]
    table_lines = [
        f"- `{x.get('name')}` ({x.get('module')}): {x.get('purpose')}"
        for x in plan.get("tables") or []
        if isinstance(x, dict)
    ]
    return "\n".join([
        "# Database Design",
        "",
        "THEANOVA AgentStudio가 Agent 설계 인터뷰와 Workflow를 기준으로 생성한 DB Module 설계입니다.",
        "DDL은 사용자 확인을 거쳐 확정된 계획만 저장됩니다.",
        "",
        "## Selected Modules",
        *(module_lines or ["- 없음"]),
        "",
        "## Tables",
        *(table_lines or ["- 없음"]),
        "",
        "## Apply",
        "1. 대상 PostgreSQL 연결 정보를 확인합니다.",
        "2. `001_initial_schema.sql`을 검토합니다.",
        "3. 개발/검증 DB에 먼저 적용합니다.",
        "4. Migration 적용 결과를 테스트한 뒤 운영 DB에 반영합니다.",
        "",
        "JSONB는 설정/metadata 확장용으로만 사용하고 핵심 조회/관계 값은 정규 컬럼으로 유지합니다.",
        "",
    ])


def materialize_database_plan(project_root: str, plan: dict) -> list[str]:
    if not plan or not plan.get("enabled") or not plan.get("finalized"):
        return []
    validation = validate_database_plan(plan)
    if not validation.get("valid"):
        raise ValueError("검증되지 않은 DB 설계는 Migration으로 저장할 수 없습니다.")
    root = Path(project_root).expanduser().resolve()
    migration_dir = (root / "backend" / "migrations").resolve()
    migration_dir.relative_to(root)
    migration_dir.mkdir(parents=True, exist_ok=True)
    ddl_path = migration_dir / "001_initial_schema.sql"
    readme_path = migration_dir / "README.md"
    ddl_path.write_text(str(plan.get("ddl") or generate_postgresql_ddl(plan)), encoding="utf-8")
    readme_path.write_text(database_plan_readme(plan), encoding="utf-8")
    return [str(ddl_path), str(readme_path)]
