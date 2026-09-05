import re
from typing import Any

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings
from app.core.machine_identity import current_pc_name


_SCHEMA_NAME_RE = re.compile(r"^[a-z_][a-z0-9_]*$")
DEFAULT_EXTENSION_SCHEMA = "extensions"


def normalize_async_database_url(url: str) -> str:
    value = (url or "").strip()
    if value.startswith("postgresql+asyncpg://"):
        return value.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


def normalize_schema_name(value: str | None, *, default: str = "") -> str:
    schema = str(value or default or "").strip()
    if not schema:
        return ""
    if not _SCHEMA_NAME_RE.fullmatch(schema):
        raise ValueError(
            "PostgreSQL 스키마 이름은 소문자 영문/숫자/_만 사용할 수 있고 영문 또는 _로 시작해야 합니다."
        )
    return schema


def quote_identifier(value: str) -> str:
    """Quote an already validated PostgreSQL identifier."""
    normalized = normalize_schema_name(value)
    return '"' + normalized.replace('"', '""') + '"'


def postgres_search_path(schema: str) -> str:
    target = normalize_schema_name(schema)
    if not target:
        return ""
    # target first prevents AgentStudio from accidentally resolving public tables.
    ordered = [target, DEFAULT_EXTENSION_SCHEMA, "public"]
    unique: list[str] = []
    for item in ordered:
        if item not in unique:
            unique.append(item)
    return ",".join(unique)


def _pin_search_path_on_checkout(async_engine, target_schema: str) -> None:
    """Pin PostgreSQL search_path on every SQLAlchemy pool checkout.

    Supabase Session Pooler can accept a PostgreSQL startup ``options`` value while the
    server session still reports ``public`` as ``current_schema()``.  AgentStudio therefore
    applies the session setting on the exact DBAPI connection that SQLAlchemy checks out.

    The SET is executed in autocommit mode so a later transaction rollback cannot undo the
    session-level search_path.  ``schema_translate_map`` remains enabled as a second guard
    so ORM-owned AgentStudio tables are explicitly schema-qualified as well.
    """
    target = normalize_schema_name(target_schema)
    if not target:
        return

    qschema = quote_identifier(target)
    statement = f'SET search_path TO {qschema}, "{DEFAULT_EXTENSION_SCHEMA}", "public"'

    @event.listens_for(async_engine.sync_engine, "checkout")
    def _set_search_path(dbapi_connection, connection_record, connection_proxy) -> None:  # noqa: ARG001
        _apply_dbapi_search_path(dbapi_connection, statement)


def _apply_dbapi_search_path(dbapi_connection, statement: str) -> None:
    """Apply one session-level search_path statement without leaving a transaction open."""
    previous_autocommit = bool(getattr(dbapi_connection, "autocommit", False))
    cursor = None
    try:
        if not previous_autocommit:
            dbapi_connection.autocommit = True
        cursor = dbapi_connection.cursor()
        cursor.execute(statement)
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass
        if not previous_autocommit:
            dbapi_connection.autocommit = False


def create_agentstudio_async_engine(database_url_value: str, *, schema: str = ""):
    """
    Build the SQLAlchemy async engine used by AgentStudio.

    For a custom Supabase schema we use both:
    - schema_translate_map: SQLAlchemy ORM tables are explicitly schema-qualified.
    - DBAPI checkout pinning: every pooled PostgreSQL connection executes an explicit
      session-level search_path on the exact connection before AgentStudio uses it.
    """
    normalized_url = normalize_async_database_url(database_url_value)
    target_schema = normalize_schema_name(schema)
    kwargs: dict[str, Any] = {"pool_pre_ping": True}
    if target_schema:
        kwargs["execution_options"] = {"schema_translate_map": {None: target_schema}}
    candidate = create_async_engine(normalized_url, **kwargs)
    if target_schema:
        _pin_search_path_on_checkout(candidate, target_schema)
    return candidate


settings = get_settings()
database_url = normalize_async_database_url(settings.database_url)
runtime_schema = ""

if not database_url:
    raise RuntimeError(
        "DATABASE_URL이 설정되지 않았습니다. 프로젝트 루트 .env에 "
        "DATABASE_URL을 설정하세요. AgentStudio는 DB 계정/비밀번호를 하드코딩해 대체하지 않습니다."
    )

engine = create_agentstudio_async_engine(database_url)

SessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def rebind_database(new_database_url: str, *, schema: str = "") -> dict:
    """
    저장된 DATABASE_URL을 현재 Backend 프로세스에 즉시 적용합니다.

    v5.297: Supabase custom schema가 지정된 경우 새 Engine의 모든 ORM SQL은
    schema_translate_map으로 해당 스키마를 명시하고, SQLAlchemy pool checkout마다
    실제 DBAPI 연결에 search_path를 직접 적용해 스키마 -> extensions -> public 순서로 고정합니다.
    """
    global engine, database_url, runtime_schema

    normalized = normalize_async_database_url(new_database_url)
    target_schema = normalize_schema_name(schema)
    candidate = create_agentstudio_async_engine(normalized, schema=target_schema)
    try:
        async with candidate.connect() as conn:
            await conn.execute(text("SELECT 1"))
            if target_schema:
                exists = bool((await conn.execute(
                    text("SELECT to_regnamespace(:schema_name) IS NOT NULL"),
                    {"schema_name": target_schema},
                )).scalar())
                if not exists:
                    raise RuntimeError(f"PostgreSQL 스키마 '{target_schema}'가 존재하지 않습니다.")
                active_schema = str((await conn.execute(text("SELECT current_schema()"))).scalar() or "")
                if active_schema != target_schema:
                    raise RuntimeError(
                        f"PostgreSQL search_path 적용 실패: 기대={target_schema}, 실제={active_schema or '-'}"
                    )
    except Exception:
        await candidate.dispose()
        raise

    old_engine = engine
    engine = candidate
    database_url = normalized
    runtime_schema = target_schema
    SessionLocal.configure(bind=candidate)
    try:
        await old_engine.dispose()
    except Exception:
        pass

    return {
        "ok": True,
        "database_url": new_database_url,
        "runtime_database_url": normalized,
        "schema": target_schema or "public/default",
    }


class Base(DeclarativeBase):
    pass


async def get_db():
    async with SessionLocal() as session:
        yield session


async def ensure_runtime_metadata_tables() -> dict:
    """Create newly-added ORM tables on the *currently active* runtime DB.

    v5.597 migration-order guard:
    legacy v5.588-v5.594 RAG tables can still physically expose ``id`` while the
    current metadata references table-specific keys such as ``sources_id``.  Those
    existing columns must be renamed *before* SQLAlchemy tries to CREATE a new table
    whose FK points at the renamed key; otherwise PostgreSQL rejects CREATE TABLE with
    UndefinedColumn.  The pre-create migration is idempotent and never drops data.
    """
    import app.models.entities  # noqa: F401
    import app.models.rag_entities  # noqa: F401
    import app.models.account_setting_entities  # noqa: F401
    precreate_pk_renames: list[str] = []
    async with engine.begin() as conn:
        precreate_pk_renames = await prepare_rag_primary_key_compatibility_for_create_all(
            conn, schema=runtime_schema
        )
        await conn.run_sync(Base.metadata.create_all)
    return {
        "ok": True,
        "schema": runtime_schema or "public/default",
        "table_count": len(Base.metadata.tables),
        "precreate_pk_renames": precreate_pk_renames,
    }


async def init_db():
    import app.models.entities  # noqa: F401
    import app.models.rag_entities  # noqa: F401
    import app.models.account_setting_entities  # noqa: F401
    async with engine.begin() as conn:
        await conn.execute(
            text("SELECT extname FROM pg_extension WHERE extname='vector'")
        )
        precreate_pk_renames = await prepare_rag_primary_key_compatibility_for_create_all(
            conn, schema=runtime_schema
        )
        if precreate_pk_renames:
            print(
                "[완료되었습니다] Legacy RAG PK 사전 보정: "
                f"{len(precreate_pk_renames)}개 · create_all 이전 적용"
            )
        await conn.run_sync(Base.metadata.create_all)




# v5.595: Newly introduced RAG tables follow the global AgentStudio PK rule.
# The Python ORM attribute remains ``id`` for API/backward compatibility, while the
# physical PostgreSQL column is table-specific (for example rag_chunks.chunks_id).
_RAG_PRIMARY_KEY_COLUMN_RENAMES: dict[str, str] = {
    "rag_studio_settings": "studio_settings_id",
    "rag_collections": "collections_id",
    "rag_sources": "sources_id",
    "rag_collection_sources": "collection_sources_id",
    "rag_documents": "documents_id",
    "rag_chunks": "chunks_id",
    "rag_embeddings": "embeddings_id",
    "rag_index_jobs": "index_jobs_id",
    "rag_retrieval_settings": "retrieval_settings_id",
    "rag_search_logs": "search_logs_id",
    "rag_agent_tools": "agent_tools_id",
    "rag_workflow_bindings": "workflow_bindings_id",
    "rag_agent_test_logs": "agent_test_logs_id",
    "rag_intelligence_settings": "intelligence_settings_id",
    "rag_recommendation_runs": "recommendation_runs_id",
    "rag_source_operation_settings": "source_operation_settings_id",
    "rag_sync_jobs": "sync_jobs_id",
    "rag_document_versions": "document_versions_id",
    "rag_document_security": "document_security_id",
    "rag_access_rules": "access_rules_id",
    "rag_search_audit_logs": "search_audit_logs_id",
    "rag_evaluation_cases": "evaluation_cases_id",
    "rag_evaluation_runs": "evaluation_runs_id",
}


async def _migrate_rag_primary_key_column_names(conn, *, schema: str) -> list[str]:
    """Rename legacy v5.588-v5.594 RAG ``id`` PK columns without dropping data.

    PostgreSQL automatically updates dependent FK constraint targets when a referenced
    column is renamed. The migration is idempotent and safe for fresh databases where
    the new physical column names already exist.
    """
    target_schema = normalize_schema_name(schema, default="public")
    qschema = quote_identifier(target_schema)
    applied: list[str] = []
    for table_name, target_column in _RAG_PRIMARY_KEY_COLUMN_RENAMES.items():
        result = await conn.execute(
            text(
                """
                SELECT
                  EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema=:schema_name AND table_name=:table_name AND column_name='id'
                  ) AS has_legacy_id,
                  EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_schema=:schema_name AND table_name=:table_name AND column_name=:target_column
                  ) AS has_target_id
                """
            ),
            {"schema_name": target_schema, "table_name": table_name, "target_column": target_column},
        )
        row = result.first()
        has_legacy_id = bool(row[0]) if row else False
        has_target_id = bool(row[1]) if row else False
        if has_legacy_id and not has_target_id:
            await conn.execute(
                text(f'ALTER TABLE {qschema}."{table_name}" RENAME COLUMN "id" TO "{target_column}"')
            )
            applied.append(f"{target_schema}.{table_name}.id -> {target_column}")
    return applied


async def prepare_rag_primary_key_compatibility_for_create_all(conn, *, schema: str = "") -> list[str]:
    """Rename legacy physical RAG PK columns before SQLAlchemy ``create_all``.

    This is intentionally smaller than the full AgentStudio migration because fresh
    databases may not have core tables such as ``app_settings``/``projects`` yet.
    It is safe to call on both fresh and previously provisioned local/Supabase schemas.
    """
    target_schema = await _resolve_connection_schema(conn, schema)
    return await _migrate_rag_primary_key_column_names(conn, schema=target_schema)


async def migrate_agentstudio_schema() -> dict:
    """현재 AgentStudio runtime engine의 스키마를 안전하게 보정합니다."""
    return await migrate_agentstudio_schema_on_engine(engine, schema=runtime_schema)


async def migrate_agentstudio_schema_on_engine(target_engine, *, schema: str = "") -> dict:
    """지정한 PostgreSQL engine의 AgentStudio 스키마를 삭제 없이 보정합니다."""
    async with target_engine.begin() as conn:
        return await migrate_agentstudio_schema_on_connection(conn, schema=schema)


async def _resolve_connection_schema(conn, requested_schema: str = "") -> str:
    target = normalize_schema_name(requested_schema)
    if target:
        return target
    current = str((await conn.execute(text("SELECT current_schema()"))).scalar() or "public")
    return normalize_schema_name(current, default="public")


async def migrate_agentstudio_schema_on_connection(conn, *, schema: str = "") -> dict:
    """이미 열린 transaction 안에서 AgentStudio 호환 migration을 적용합니다."""
    pc_name = current_pc_name()
    target_schema = await _resolve_connection_schema(conn, schema)
    qschema = quote_identifier(target_schema)
    app_settings = f'{qschema}."app_settings"'
    projects = f'{qschema}."projects"'

    machine_setting_statements = [
        f"""
        ALTER TABLE {app_settings}
        ADD COLUMN IF NOT EXISTS pc_name VARCHAR(255) NOT NULL DEFAULT ''
        """,
        f"""
        DO $$
        DECLARE r RECORD;
        BEGIN
          FOR r IN
            SELECT c.conname
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = '{target_schema}'
              AND t.relname = 'app_settings'
              AND c.contype = 'u'
              AND array_length(c.conkey, 1) = 1
              AND EXISTS (
                SELECT 1
                FROM unnest(c.conkey) AS k(attnum)
                JOIN pg_attribute a
                  ON a.attrelid = c.conrelid AND a.attnum = k.attnum
                WHERE a.attname = 'key'
              )
          LOOP
            EXECUTE format('ALTER TABLE %I.%I DROP CONSTRAINT %I', '{target_schema}', 'app_settings', r.conname);
          END LOOP;
        END $$
        """,
        f"DROP INDEX IF EXISTS {qschema}.\"ix_app_settings_key\"",
        f"CREATE INDEX IF NOT EXISTS ix_app_settings_key ON {app_settings}(key)",
        f"CREATE INDEX IF NOT EXISTS ix_app_settings_pc_name ON {app_settings}(pc_name)",
        f"CREATE UNIQUE INDEX IF NOT EXISTS uq_app_settings_pc_name_key ON {app_settings}(pc_name, key)",
    ]

    project_scope_statements = [
        f"ALTER TABLE {projects} ADD COLUMN IF NOT EXISTS pc_name VARCHAR(255) NOT NULL DEFAULT ''",
        f"""
        DO $$
        DECLARE r RECORD;
        BEGIN
          FOR r IN
            SELECT c.conname
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = t.relnamespace
            WHERE n.nspname = '{target_schema}'
              AND t.relname = 'projects'
              AND c.contype = 'u'
              AND array_length(c.conkey, 1) = 1
              AND EXISTS (
                SELECT 1
                FROM unnest(c.conkey) AS k(attnum)
                JOIN pg_attribute a
                  ON a.attrelid = c.conrelid AND a.attnum = k.attnum
                WHERE a.attname = 'root_path'
              )
          LOOP
            EXECUTE format('ALTER TABLE %I.%I DROP CONSTRAINT %I', '{target_schema}', 'projects', r.conname);
          END LOOP;
        END $$
        """,
        f"CREATE INDEX IF NOT EXISTS ix_projects_pc_name ON {projects}(pc_name)",
        f"CREATE UNIQUE INDEX IF NOT EXISTS uq_projects_pc_name_root_path ON {projects}(pc_name, root_path)",
    ]

    statements = [
        f"ALTER TABLE {projects} ADD COLUMN IF NOT EXISTS cache_path VARCHAR(1000) NOT NULL DEFAULT ''",
        f"ALTER TABLE {projects} ADD COLUMN IF NOT EXISTS temp_path VARCHAR(1000) NOT NULL DEFAULT ''",
        f"ALTER TABLE {projects} ADD COLUMN IF NOT EXISTS output_path VARCHAR(1000) NOT NULL DEFAULT ''",
        f"ALTER TABLE {projects} ADD COLUMN IF NOT EXISTS venv_path VARCHAR(1000) NOT NULL DEFAULT ''",
        f"ALTER TABLE {projects} ADD COLUMN IF NOT EXISTS models_path VARCHAR(1000) NOT NULL DEFAULT ''",
        f"ALTER TABLE {projects} ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT ''",
        f"ALTER TABLE {projects} ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP",
        f"ALTER TABLE {projects} ADD COLUMN IF NOT EXISTS last_opened_at TIMESTAMP NULL",
        f"ALTER TABLE {projects} ADD COLUMN IF NOT EXISTS is_favorite BOOLEAN NOT NULL DEFAULT FALSE",
    ]

    applied = []
    applied.extend(await _migrate_rag_primary_key_column_names(conn, schema=target_schema))
    await conn.execute(text(machine_setting_statements[0]))
    applied.append(" ".join(machine_setting_statements[0].strip().split()))
    await conn.execute(
        text(f"UPDATE {app_settings} SET pc_name = :pc_name WHERE COALESCE(pc_name, '') = ''"),
        {"pc_name": pc_name},
    )
    applied.append(f"{target_schema}.app_settings legacy rows -> pc_name={pc_name}")

    for sql in machine_setting_statements[1:]:
        await conn.execute(text(sql))
        applied.append(" ".join(sql.strip().split()))

    for sql in project_scope_statements:
        await conn.execute(text(sql))
        applied.append(" ".join(sql.strip().split()))

    for sql in statements:
        await conn.execute(text(sql))
        applied.append(" ".join(sql.strip().split()))

    return {
        "ok": True,
        "schema": target_schema,
        "applied": applied,
        "count": len(applied),
    }


def current_event_loop_name() -> str:
    try:
        import asyncio
        loop = asyncio.get_running_loop()
        return type(loop).__name__
    except Exception:
        return "no-running-loop"


async def verify_project_schema() -> dict:
    """현재 projects 테이블의 필수 컬럼 존재 여부를 확인합니다."""
    required = {
        "id", "pc_name", "name", "root_path", "cache_path", "temp_path", "output_path",
        "venv_path", "models_path", "description", "created_at", "last_opened_at", "is_favorite",
    }

    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = 'projects'
                """
            )
        )
        existing = {str(row[0]) for row in result.fetchall()}

    missing = sorted(required - existing)
    return {
        "ok": not missing,
        "required": sorted(required),
        "existing": sorted(existing),
        "missing": missing,
    }
