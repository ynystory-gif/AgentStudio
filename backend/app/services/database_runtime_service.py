from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import UniqueConstraint, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.database import (
    Base,
    create_agentstudio_async_engine,
    ensure_runtime_metadata_tables,
    migrate_agentstudio_schema,
    migrate_agentstudio_schema_on_connection,
    prepare_rag_primary_key_compatibility_for_create_all,
    normalize_async_database_url,
    normalize_schema_name,
    postgres_search_path,
    quote_identifier,
    rebind_database,
)
from app.core.machine_identity import current_pc_name
from app.models.entities import AppSetting
from app.services.langgraph_postgres_connection import open_schema_pinned_checkpointer


PROVIDER_LOCAL = "local"
PROVIDER_SUPABASE = "supabase"
SUPPORTED_PROVIDERS = {PROVIDER_LOCAL, PROVIDER_SUPABASE}

PROVIDER_SETTING_KEY = "AGENTSTUDIO_DATABASE_PROVIDER"
SUPABASE_TARGET_SETTING_KEY = "AGENTSTUDIO_SUPABASE_TARGET"

ENV_PROVIDER_KEY = "AGENTSTUDIO_DATABASE_PROVIDER"
ENV_SUPABASE_DATABASE_URL = "SUPABASE_DATABASE_URL"
ENV_SUPABASE_LANGGRAPH_DATABASE_URL = "SUPABASE_LANGGRAPH_DATABASE_URL"
ENV_SUPABASE_DB_SCHEMA = "SUPABASE_DB_SCHEMA"
DEFAULT_SUPABASE_DB_SCHEMA = "theanova_agentstudio"

_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "sql" / "supabase_agentstudio_full_schema.sql"

_ACTIVE_PROVIDER = PROVIDER_LOCAL
_LAST_ERROR = ""


def _normalize_provider(value: str | None) -> str:
    provider = str(value or "").strip().lower()
    return provider if provider in SUPPORTED_PROVIDERS else PROVIDER_LOCAL


def _langgraph_url_from_database_url(value: str) -> str:
    url = str(value or "").strip()
    for prefix in (
        "postgresql+asyncpg://",
        "postgresql+psycopg://",
        "postgresql+psycopg_async://",
    ):
        if url.startswith(prefix):
            return "postgresql://" + url[len(prefix):]
    return url


def _postgres_url_with_search_path(value: str, schema: str) -> str:
    """Add a psycopg startup search_path without persisting it into the saved URL."""
    base = _langgraph_url_from_database_url(value)
    target_schema = normalize_schema_name(schema, default=DEFAULT_SUPABASE_DB_SCHEMA)
    parts = urlsplit(base)
    query = [(key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True) if key.lower() != "options"]
    query.append(("options", f"-csearch_path={postgres_search_path(target_schema)}"))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def configured_supabase_schema() -> str:
    settings = get_settings()
    return normalize_schema_name(
        getattr(settings, "supabase_db_schema", ""),
        default=DEFAULT_SUPABASE_DB_SCHEMA,
    )


def _validate_supabase_persistent_connection(value: str) -> None:
    """AgentStudio is a persistent backend; avoid Supabase transaction pooler for schema-pinned sessions."""
    parsed = urlsplit(_langgraph_url_from_database_url(value))
    host = str(parsed.hostname or "").lower()
    port = parsed.port or 5432
    if host.endswith(".pooler.supabase.com") and port == 6543:
        raise ValueError(
            "AgentStudio의 Supabase custom schema/LangGraph 연결은 transaction pooler(6543)가 아니라 "
            "Session pooler(5432) 또는 Direct connection을 사용해야 합니다."
        )


def _target_label(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlsplit(_langgraph_url_from_database_url(raw))
        user = parsed.username or ""
        host = parsed.hostname or ""
        port = parsed.port or 5432
        database = (parsed.path or "").lstrip("/")
        auth = f"{user}@" if user else ""
        return f"{auth}{host}:{port}/{database}".rstrip("/")
    except Exception:
        return "설정됨"


def _validate_postgresql_url(value: str, label: str) -> str:
    url = str(value or "").strip()
    if not url:
        raise ValueError(f"{label}이 비어 있습니다.")
    accepted = (
        "postgresql://",
        "postgresql+asyncpg://",
        "postgresql+psycopg://",
        "postgresql+psycopg_async://",
    )
    if not url.startswith(accepted):
        raise ValueError(f"{label}은 PostgreSQL URL 형식이어야 합니다.")
    return url


def schema_script_path() -> Path:
    return _SCHEMA_PATH


def schema_script_info() -> dict[str, Any]:
    return {
        "path": str(_SCHEMA_PATH),
        "exists": _SCHEMA_PATH.exists(),
        "file_name": _SCHEMA_PATH.name,
        "default_schema": DEFAULT_SUPABASE_DB_SCHEMA,
    }


def local_database_url() -> str:
    settings = get_settings()
    return str(getattr(settings, "local_database_url", "") or settings.database_url or "").strip()


def local_langgraph_database_url() -> str:
    settings = get_settings()
    return str(
        getattr(settings, "local_langgraph_database_url", "")
        or settings.langgraph_database_url
        or ""
    ).strip()


def configured_supabase_database_url() -> str:
    settings = get_settings()
    return str(getattr(settings, "supabase_database_url", "") or "").strip()


def configured_supabase_langgraph_url() -> str:
    settings = get_settings()
    return str(
        getattr(settings, "supabase_langgraph_database_url", "")
        or _langgraph_url_from_database_url(configured_supabase_database_url())
        or ""
    ).strip()


def current_runtime_database_url() -> str:
    if _ACTIVE_PROVIDER == PROVIDER_SUPABASE:
        return configured_supabase_database_url() or local_database_url()
    return local_database_url()


def current_runtime_langgraph_url() -> str:
    if _ACTIVE_PROVIDER == PROVIDER_SUPABASE:
        return configured_supabase_langgraph_url() or local_langgraph_database_url()
    return local_langgraph_database_url()


async def _local_sessionmaker() -> tuple[async_sessionmaker[AsyncSession], Any]:
    url = _validate_postgresql_url(local_database_url(), "로컬 PostgreSQL DATABASE URL")
    local_engine = create_async_engine(normalize_async_database_url(url), pool_pre_ping=True)
    Session = async_sessionmaker(local_engine, expire_on_commit=False, class_=AsyncSession)
    return Session, local_engine


async def _load_local_provider_state() -> dict[str, str]:
    Session, local_engine = await _local_sessionmaker()
    try:
        async with Session() as session:
            rows = (
                await session.execute(
                    select(AppSetting).where(
                        AppSetting.pc_name == current_pc_name(),
                        AppSetting.key.in_([PROVIDER_SETTING_KEY, SUPABASE_TARGET_SETTING_KEY]),
                    )
                )
            ).scalars().all()
            return {row.key: row.value for row in rows}
    finally:
        await local_engine.dispose()


async def _save_local_provider_state(provider: str, supabase_url: str = "") -> None:
    """Always persist the provider choice in the local PostgreSQL control DB."""
    Session, local_engine = await _local_sessionmaker()
    try:
        async with Session() as session:
            pc_name = current_pc_name()
            values = {
                PROVIDER_SETTING_KEY: provider,
                SUPABASE_TARGET_SETTING_KEY: _target_label(supabase_url),
            }
            rows = (
                await session.execute(
                    select(AppSetting).where(
                        AppSetting.pc_name == pc_name,
                        AppSetting.key.in_(list(values.keys())),
                    )
                )
            ).scalars().all()
            existing = {row.key: row for row in rows}
            for key, value in values.items():
                row = existing.get(key)
                if row:
                    row.value = value
                    row.is_secret = False
                else:
                    session.add(AppSetting(pc_name=pc_name, key=key, value=value, is_secret=False))
            await session.commit()
    finally:
        await local_engine.dispose()


async def _test_target_database(database_url: str, *, schema: str = "") -> None:
    target_schema = normalize_schema_name(schema)
    candidate = create_agentstudio_async_engine(database_url, schema=target_schema)
    try:
        async with candidate.connect() as conn:
            await conn.execute(text("SELECT 1"))
            if target_schema:
                exists = bool((await conn.execute(
                    text("SELECT to_regnamespace(:schema_name) IS NOT NULL"),
                    {"schema_name": target_schema},
                )).scalar())
                if not exists:
                    raise RuntimeError(f"Supabase 스키마 '{target_schema}'가 존재하지 않습니다.")
                actual = str((await conn.execute(text("SELECT current_schema()"))).scalar() or "")
                if actual != target_schema:
                    raise RuntimeError(
                        f"Supabase search_path 적용 실패: 기대={target_schema}, 실제={actual or '-'}"
                    )
    finally:
        await candidate.dispose()


LANGGRAPH_REQUIRED_TABLES = {
    "checkpoint_migrations",
    "checkpoints",
    "checkpoint_blobs",
    "checkpoint_writes",
}


def _ensure_metadata_indexes(sync_conn, schema: str) -> list[str]:
    """Create metadata-defined indexes using an explicit schema-aware existence check."""
    target_schema = normalize_schema_name(schema, default="public")
    inspector = inspect(sync_conn)
    translated = sync_conn.execution_options(schema_translate_map={None: target_schema})
    created_or_verified: list[str] = []
    for table in Base.metadata.sorted_tables:
        existing = {
            str(item.get("name") or "")
            for item in inspector.get_indexes(table.name, schema=target_schema)
        }
        for index in sorted(table.indexes, key=lambda item: item.name or ""):
            if index.name and index.name not in existing:
                index.create(bind=translated, checkfirst=False)
            if index.name:
                created_or_verified.append(index.name)
    return created_or_verified


def _inspect_agentstudio_schema(sync_conn, schema: str) -> dict[str, Any]:
    """Compare one explicit AgentStudio schema with the current SQLAlchemy metadata."""
    inspector = inspect(sync_conn)
    schema = normalize_schema_name(schema, default="public")
    actual_tables = set(inspector.get_table_names(schema=schema))

    expected_tables = {table.name for table in Base.metadata.sorted_tables}
    missing_tables = sorted(expected_tables - actual_tables)
    missing_columns: dict[str, list[str]] = {}
    missing_primary_keys: dict[str, list[str]] = {}
    missing_unique_constraints: dict[str, list[list[str]]] = {}
    missing_indexes: dict[str, list[str]] = {}
    missing_foreign_keys: dict[str, list[str]] = {}

    for table in Base.metadata.sorted_tables:
        if table.name not in actual_tables:
            continue

        actual_columns = {
            str(item.get("name") or "")
            for item in inspector.get_columns(table.name, schema=schema)
        }
        expected_columns = {column.name for column in table.columns}
        missing = sorted(expected_columns - actual_columns)
        if missing:
            missing_columns[table.name] = missing

        expected_pk = {column.name for column in table.primary_key.columns}
        actual_pk = set(
            (inspector.get_pk_constraint(table.name, schema=schema) or {}).get("constrained_columns")
            or []
        )
        if expected_pk and expected_pk != actual_pk:
            missing_primary_keys[table.name] = sorted(expected_pk)

        expected_unique_sets: set[tuple[str, ...]] = set()
        for constraint in table.constraints:
            if isinstance(constraint, UniqueConstraint):
                names = tuple(sorted(column.name for column in constraint.columns))
                if names:
                    expected_unique_sets.add(names)
        for column in table.columns:
            if bool(column.unique):
                expected_unique_sets.add((column.name,))

        actual_unique_sets: set[tuple[str, ...]] = set()
        for item in inspector.get_unique_constraints(table.name, schema=schema):
            cols = tuple(sorted(str(name) for name in (item.get("column_names") or []) if name))
            if cols:
                actual_unique_sets.add(cols)
        actual_indexes = inspector.get_indexes(table.name, schema=schema)
        for item in actual_indexes:
            if item.get("unique"):
                cols = tuple(sorted(str(name) for name in (item.get("column_names") or []) if name))
                if cols:
                    actual_unique_sets.add(cols)
        missing_uniques = sorted(expected_unique_sets - actual_unique_sets)
        if missing_uniques:
            missing_unique_constraints[table.name] = [list(cols) for cols in missing_uniques]

        expected_index_names = {index.name for index in table.indexes if index.name}
        actual_index_names = {str(item.get("name") or "") for item in actual_indexes}
        missing_index_names = sorted(expected_index_names - actual_index_names)
        if missing_index_names:
            missing_indexes[table.name] = missing_index_names

        expected_fks: set[tuple[tuple[str, ...], str, tuple[str, ...]]] = set()
        for constraint in table.foreign_key_constraints:
            local_cols = tuple(column.name for column in constraint.columns)
            target_table = ""
            target_cols: list[str] = []
            for element in constraint.elements:
                target_table = element.column.table.name
                target_cols.append(element.column.name)
            expected_fks.add((local_cols, target_table, tuple(target_cols)))

        actual_fks: set[tuple[tuple[str, ...], str, tuple[str, ...]]] = set()
        for item in inspector.get_foreign_keys(table.name, schema=schema):
            actual_fks.add((
                tuple(str(name) for name in (item.get("constrained_columns") or [])),
                str(item.get("referred_table") or ""),
                tuple(str(name) for name in (item.get("referred_columns") or [])),
            ))
        missing_fk_sets = sorted(expected_fks - actual_fks)
        if missing_fk_sets:
            missing_foreign_keys[table.name] = [
                f"{','.join(local)} -> {target}({','.join(remote)})"
                for local, target, remote in missing_fk_sets
            ]

    ok = not any((
        missing_tables,
        missing_columns,
        missing_primary_keys,
        missing_unique_constraints,
        missing_indexes,
        missing_foreign_keys,
    ))
    return {
        "ok": ok,
        "schema": schema,
        "expected_table_count": len(expected_tables),
        "actual_agentstudio_table_count": len(expected_tables & actual_tables),
        "expected_tables": sorted(expected_tables),
        "missing_tables": missing_tables,
        "missing_columns": missing_columns,
        "missing_primary_keys": missing_primary_keys,
        "missing_unique_constraints": missing_unique_constraints,
        "missing_indexes": missing_indexes,
        "missing_foreign_keys": missing_foreign_keys,
    }


async def _prepare_agentstudio_schema_transaction(candidate, schema: str) -> dict[str, Any]:
    """Prepare pgvector + AgentStudio tables in one PostgreSQL transaction."""
    import app.models.entities  # noqa: F401

    target_schema = normalize_schema_name(schema, default=DEFAULT_SUPABASE_DB_SCHEMA)
    qschema = quote_identifier(target_schema)
    migration: dict[str, Any] = {"ok": False, "count": 0, "applied": []}
    verification: dict[str, Any] = {"ok": False}
    indexes: list[str] = []
    extension_status = ""

    async with candidate.begin() as conn:
        # User schema is isolated from public. pgvector follows Supabase's extensions schema.
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {qschema}"))
        await conn.execute(text('CREATE SCHEMA IF NOT EXISTS "extensions"'))

        available = bool((await conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name='vector')"
        ))).scalar())
        installed_before = bool((await conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector')"
        ))).scalar())
        if not available and not installed_before:
            raise RuntimeError("Supabase PostgreSQL에서 pgvector(vector) 확장을 사용할 수 없습니다.")

        if not installed_before:
            await conn.execute(text('CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA "extensions"'))
        installed_after = bool((await conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector')"
        ))).scalar())
        if not installed_after:
            raise RuntimeError("pgvector(vector) 확장 설치 확인에 실패했습니다.")

        vector_schema = str((await conn.execute(text(
            """
            SELECT n.nspname
            FROM pg_extension e
            JOIN pg_namespace n ON n.oid = e.extnamespace
            WHERE e.extname = 'vector'
            """
        ))).scalar() or "")
        if vector_schema != "extensions":
            raise RuntimeError(
                "pgvector(vector)가 extensions 스키마가 아닌 "
                f"'{vector_schema or 'unknown'}'에 설치되어 있습니다. "
                "AgentStudio는 Supabase의 extensions.vector 구성을 사용합니다."
            )
        extension_status = "already_installed" if installed_before else "installed"

        # CREATE SCHEMA 이후 transaction의 search_path도 즉시 맞춘다.
        await conn.execute(text(
            f'SET LOCAL search_path TO {qschema}, "extensions", "public"'
        ))

        # v5.597: existing v5.588-v5.594 RAG tables can still use a physical ``id``
        # PK. Rename those columns before create_all creates new tables whose FKs
        # already target table-specific keys such as rag_sources.sources_id.
        await prepare_rag_primary_key_compatibility_for_create_all(
            conn, schema=target_schema
        )
        # schema_translate_map explicitly qualifies all SQLAlchemy ORM tables.
        await conn.run_sync(Base.metadata.create_all)
        migration = await migrate_agentstudio_schema_on_connection(conn, schema=target_schema)
        indexes = await conn.run_sync(
            lambda sync_conn: _ensure_metadata_indexes(sync_conn, target_schema)
        )
        verification = await conn.run_sync(
            lambda sync_conn: _inspect_agentstudio_schema(sync_conn, target_schema)
        )
        if not verification.get("ok"):
            raise RuntimeError(
                "AgentStudio 스키마 검증 실패: " + _schema_problem_summary(verification)
            )

    return {
        "ok": True,
        "schema": target_schema,
        "vector": extension_status,
        "vector_schema": "extensions",
        "migration": migration,
        "indexes": indexes,
        "verification": verification,
    }


def _schema_problem_summary(verification: dict[str, Any]) -> str:
    parts: list[str] = []
    if verification.get("missing_tables"):
        parts.append("누락 테이블=" + ", ".join(verification["missing_tables"]))
    if verification.get("missing_columns"):
        value = "; ".join(
            f"{table}({', '.join(columns)})"
            for table, columns in verification["missing_columns"].items()
        )
        parts.append("누락 컬럼=" + value)
    if verification.get("missing_primary_keys"):
        parts.append("PK 불일치=" + ", ".join(verification["missing_primary_keys"].keys()))
    if verification.get("missing_unique_constraints"):
        parts.append("UNIQUE 누락=" + ", ".join(verification["missing_unique_constraints"].keys()))
    if verification.get("missing_indexes"):
        parts.append("INDEX 누락=" + ", ".join(verification["missing_indexes"].keys()))
    if verification.get("missing_foreign_keys"):
        parts.append("FK 누락=" + ", ".join(verification["missing_foreign_keys"].keys()))
    return " / ".join(parts) or "세부 정보를 확인하세요."


async def _setup_and_verify_langgraph(langgraph_database_url: str, schema: str) -> dict[str, Any]:
    """
    Use the installed LangGraph package as the authoritative checkpoint migration source.

    Python langgraph-checkpoint-postgres currently uses unqualified table names, so
    the official setup/runtime is pinned to the same custom schema through the
    PostgreSQL connection search_path.
    """
    target_schema = normalize_schema_name(schema, default=DEFAULT_SUPABASE_DB_SCHEMA)
    scoped_url = _postgres_url_with_search_path(langgraph_database_url, target_schema)
    try:
        # v5.296: do not rely on PgBouncer/startup URL options for custom schema.
        # Pin search_path on the exact psycopg session used by LangGraph setup().
        async with open_schema_pinned_checkpointer(
            scoped_url,
            schema=target_schema,
        ) as checkpointer:
            await checkpointer.setup()
    except Exception as exc:
        return {
            "ok": False,
            "phase": "langgraph_setup",
            "schema": target_schema,
            "tables": [],
            "missing_tables": sorted(LANGGRAPH_REQUIRED_TABLES),
            "message": f"LangGraph 공식 Checkpointer migration 실패: {exc}",
        }

    engine = create_agentstudio_async_engine(langgraph_database_url, schema=target_schema)
    try:
        async with engine.connect() as conn:
            rows = (
                await conn.execute(text(
                    """
                    SELECT tablename
                    FROM pg_tables
                    WHERE schemaname = :schema_name
                      AND tablename IN (
                        'checkpoint_migrations',
                        'checkpoints',
                        'checkpoint_blobs',
                        'checkpoint_writes'
                      )
                    ORDER BY tablename
                    """
                ), {"schema_name": target_schema})
            ).scalars().all()
            tables = {str(name) for name in rows}
            missing = sorted(LANGGRAPH_REQUIRED_TABLES - tables)
            public_rows = (
                await conn.execute(text(
                    """
                    SELECT tablename
                    FROM pg_tables
                    WHERE schemaname = 'public'
                      AND tablename IN (
                        'checkpoint_migrations',
                        'checkpoints',
                        'checkpoint_blobs',
                        'checkpoint_writes'
                      )
                    ORDER BY tablename
                    """
                ))
            ).scalars().all()
            misplaced_public_tables = [str(name) for name in public_rows]
            migration_count = 0
            if "checkpoint_migrations" in tables:
                qschema = quote_identifier(target_schema)
                migration_count = int((await conn.execute(text(
                    f'SELECT COUNT(*) FROM {qschema}."checkpoint_migrations"'
                ))).scalar() or 0)
    finally:
        await engine.dispose()

    return {
        "ok": not missing,
        "phase": "langgraph_verify",
        "schema": target_schema,
        "tables": sorted(tables),
        "missing_tables": missing,
        "migration_count": migration_count,
        "misplaced_public_tables": misplaced_public_tables,
        "message": (
            f"LangGraph 공식 Checkpointer setup/검증 완료 ({target_schema})"
            if not missing
            else (
                "LangGraph 필수 테이블 누락: " + ", ".join(missing)
                + (
                    " / public에 잘못 생성된 기존 테이블 감지: "
                    + ", ".join(misplaced_public_tables)
                    if misplaced_public_tables else ""
                )
            )
        ),
    }


async def initialize_supabase_schema(
    database_url: str,
    langgraph_database_url: str = "",
    schema: str = "",
) -> dict[str, Any]:
    """
    Create/upgrade the selected Supabase PostgreSQL idempotently.

    AgentStudio DDL is transactional. LangGraph tables are NEVER hand-maintained here;
    the installed AsyncPostgresSaver.setup() is the authoritative migration source.
    """
    database_url = str(database_url or configured_supabase_database_url()).strip()
    database_url = _validate_postgresql_url(database_url, "Supabase DATABASE URL")
    _validate_supabase_persistent_connection(database_url)
    target_schema = normalize_schema_name(
        schema or configured_supabase_schema(),
        default=DEFAULT_SUPABASE_DB_SCHEMA,
    )
    langgraph_database_url = str(
        langgraph_database_url
        or configured_supabase_langgraph_url()
        or _langgraph_url_from_database_url(database_url)
    ).strip()
    langgraph_database_url = _validate_postgresql_url(
        langgraph_database_url,
        "Supabase LangGraph DB URL",
    )

    candidate = create_agentstudio_async_engine(database_url, schema=target_schema)
    try:
        try:
            async with candidate.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception as exc:
            return {
                "ok": False,
                "phase": "connection",
                "target": _target_label(database_url),
                "schema": target_schema,
                "rolled_back": True,
                "message": f"Supabase 연결 확인 실패: {exc}",
            }

        try:
            agentstudio = await _prepare_agentstudio_schema_transaction(candidate, target_schema)
        except Exception as exc:
            # candidate.begin() guarantees rollback for AgentStudio DDL on this phase.
            return {
                "ok": False,
                "phase": "agentstudio_schema",
                "target": _target_label(database_url),
                "schema": target_schema,
                "rolled_back": True,
                "message": f"Supabase AgentStudio 스키마 준비 실패(변경사항 rollback): {exc}",
            }
    finally:
        await candidate.dispose()

    langgraph = await _setup_and_verify_langgraph(langgraph_database_url, target_schema)
    verification = dict(agentstudio.get("verification") or {})
    if not langgraph.get("ok"):
        return {
            "ok": False,
            "phase": "langgraph",
            "target": _target_label(database_url),
            "schema": target_schema,
            "rolled_back": False,
            "agentstudio_schema_committed": True,
            "agentstudio_table_count": int(verification.get("actual_agentstudio_table_count") or 0),
            "verification": verification,
            "langgraph": langgraph,
            "schema_script": schema_script_info(),
            "message": (
                "AgentStudio 테이블은 정상 준비되었지만 LangGraph 공식 migration/검증이 실패했습니다. "
                "Runtime DB는 전환하지 않습니다. 다시 실행해도 기존 데이터는 삭제되지 않습니다. "
                + str(langgraph.get("message") or "")
            ),
        }

    return {
        "ok": True,
        "phase": "complete",
        "target": _target_label(database_url),
        "schema": target_schema,
        "vector": agentstudio.get("vector"),
        "agentstudio_table_count": int(verification.get("actual_agentstudio_table_count") or 0),
        "tables": verification.get("expected_tables") or [],
        "migration_count": int((agentstudio.get("migration") or {}).get("count") or 0),
        "verification": verification,
        "langgraph": langgraph,
        "langgraph_ok": True,
        "langgraph_error": "",
        "schema_script": schema_script_info(),
        "message": (
            f"Supabase 스키마 준비/재검증 완료 [{target_schema}]: AgentStudio {verification.get('actual_agentstudio_table_count', 0)}개 테이블"
            f" · LangGraph {len(langgraph.get('tables') or [])}개 테이블 · 재실행 안전"
        ),
    }


async def runtime_status() -> dict[str, Any]:
    provider = _ACTIVE_PROVIDER
    # Project-root .env is authoritative for provider selection. The local control DB
    # mirrors the choice for diagnostics only and must never override .env at startup.
    desired = _normalize_provider(getattr(get_settings(), "agentstudio_database_provider", PROVIDER_LOCAL))
    local_state_error = ""
    try:
        await _load_local_provider_state()
    except Exception as exc:
        local_state_error = str(exc)

    return {
        "ok": True,
        "default_provider": PROVIDER_LOCAL,
        "selected_provider": desired,
        "active_provider": provider,
        "local_target": _target_label(local_database_url()),
        "supabase_configured": bool(configured_supabase_database_url()),
        "supabase_target": _target_label(configured_supabase_database_url()),
        "supabase_schema": configured_supabase_schema(),
        "langgraph_target": _target_label(current_runtime_langgraph_url()),
        "local_settings_db": _target_label(local_database_url()),
        "local_state_error": local_state_error,
        "last_error": _LAST_ERROR,
        "schema_script": schema_script_info(),
    }


async def save_supabase_runtime_settings(
    database_url: str = "",
    langgraph_database_url: str = "",
    schema: str = "",
) -> dict[str, Any]:
    """Persist Supabase connection information without changing the active runtime provider.

    Secrets stay in backend/.env only. The API never returns the raw URLs.
    A blank LangGraph URL intentionally means "derive it from SUPABASE_DATABASE_URL".
    """
    from app.services.settings_service import write_env_values

    resolved_database_url = str(database_url or configured_supabase_database_url()).strip()
    resolved_database_url = _validate_postgresql_url(resolved_database_url, "Supabase DATABASE URL")
    _validate_supabase_persistent_connection(resolved_database_url)

    # 빈 값은 기존에 별도 저장된 LangGraph URL을 유지합니다. 별도 값이 없으면
    # configured_supabase_langgraph_url()이 DATABASE URL에서 자동 파생합니다.
    existing_explicit_langgraph = str(
        getattr(get_settings(), "supabase_langgraph_database_url", "") or ""
    ).strip()
    raw_langgraph_url = str(langgraph_database_url or existing_explicit_langgraph or "").strip()
    if raw_langgraph_url:
        _validate_postgresql_url(raw_langgraph_url, "Supabase LangGraph DB URL")
        _validate_supabase_persistent_connection(raw_langgraph_url)

    target_schema = normalize_schema_name(
        schema or configured_supabase_schema(),
        default=DEFAULT_SUPABASE_DB_SCHEMA,
    )

    write_env_values({
        ENV_SUPABASE_DATABASE_URL: resolved_database_url,
        ENV_SUPABASE_LANGGRAPH_DATABASE_URL: raw_langgraph_url,
        ENV_SUPABASE_DB_SCHEMA: target_schema,
    })
    get_settings.cache_clear()

    # Verify persistence through the same Settings path used after a Backend restart.
    persisted_database_url = configured_supabase_database_url()
    persisted_schema = configured_supabase_schema()
    if persisted_database_url != resolved_database_url or persisted_schema != target_schema:
        raise OSError("Supabase 연결 정보를 backend/.env에 저장한 뒤 재조회하는 데 실패했습니다.")

    persisted_explicit_langgraph = str(
        getattr(get_settings(), "supabase_langgraph_database_url", "") or ""
    ).strip()
    if persisted_explicit_langgraph != raw_langgraph_url:
        raise OSError("Supabase LangGraph DB URL 저장 확인에 실패했습니다.")

    return {
        "ok": True,
        "storage": "backend/.env",
        "target": _target_label(resolved_database_url),
        "supabase_schema": target_schema,
        "langgraph_mode": "separate_url" if raw_langgraph_url else "database_url_auto",
        "active_provider": _ACTIVE_PROVIDER,
        "runtime_changed": False,
        "message": (
            "Supabase PostgreSQL 연결 정보를 backend/.env에 저장했습니다. "
            "현재 Runtime DB는 변경하지 않았습니다. 이후 URL 입력칸을 비워도 저장된 정보를 자동 사용합니다."
        ),
    }


async def _prepare_learning_schema_after_runtime_rebind() -> dict[str, Any]:
    """Run learning DDL/backfill only after an explicit AgentStudio runtime DB switch."""
    from app.services.learning_relational_schema_service import ensure_learning_relational_schema

    return await ensure_learning_relational_schema(force=True, run_backfill=True)


async def activate_database_provider(
    provider: str,
    *,
    supabase_database_url: str = "",
    supabase_langgraph_database_url: str = "",
    supabase_db_schema: str = "",
    initialize_schema: bool = True,
) -> dict[str, Any]:
    global _ACTIVE_PROVIDER, _LAST_ERROR

    provider = _normalize_provider(provider)
    previous_provider = _ACTIVE_PROVIDER
    from app.services.settings_service import write_env_values
    from app.services.langgraph_runtime import agent_graph_runtime

    if provider == PROVIDER_LOCAL:
        target_database_url = _validate_postgresql_url(local_database_url(), "로컬 PostgreSQL DATABASE URL")
        target_langgraph_url = _validate_postgresql_url(local_langgraph_database_url(), "로컬 LangGraph DB URL")
        await _test_target_database(target_database_url)
        await _save_local_provider_state(PROVIDER_LOCAL, "")
        write_env_values({ENV_PROVIDER_KEY: PROVIDER_LOCAL})
        get_settings.cache_clear()
        await rebind_database(target_database_url)
        await migrate_agentstudio_schema()
        await _prepare_learning_schema_after_runtime_rebind()
        await agent_graph_runtime.set_database_url(target_langgraph_url, restart=True)
        _ACTIVE_PROVIDER = PROVIDER_LOCAL
        _LAST_ERROR = ""
        return {
            "ok": True,
            "active_provider": PROVIDER_LOCAL,
            "target": _target_label(target_database_url),
            "local_settings_updated": True,
            "message": "기본 로컬 PostgreSQL로 전환했습니다. 로컬 DB의 선택 설정도 local로 업데이트했습니다.",
        }

    database_url = str(supabase_database_url or configured_supabase_database_url()).strip()
    database_url = _validate_postgresql_url(database_url, "Supabase DATABASE URL")
    _validate_supabase_persistent_connection(database_url)
    langgraph_url = str(
        supabase_langgraph_database_url
        or configured_supabase_langgraph_url()
        or _langgraph_url_from_database_url(database_url)
    ).strip()
    langgraph_url = _validate_postgresql_url(langgraph_url, "Supabase LangGraph DB URL")
    target_schema = normalize_schema_name(
        supabase_db_schema or configured_supabase_schema(),
        default=DEFAULT_SUPABASE_DB_SCHEMA,
    )

    schema_result = None
    if initialize_schema:
        schema_result = await initialize_supabase_schema(database_url, langgraph_url, target_schema)
        if not bool(schema_result.get("ok")):
            _LAST_ERROR = str(schema_result.get("message") or "Supabase 스키마 준비 실패")
            active_label = "로컬 PostgreSQL" if previous_provider == PROVIDER_LOCAL else "기존 Supabase PostgreSQL"
            return {
                "ok": False,
                "active_provider": previous_provider,
                "target": _target_label(database_url),
                "local_settings_updated": False,
                "schema": schema_result,
                "message": _LAST_ERROR + f" · Runtime 전환 없이 {active_label}을 계속 사용합니다.",
            }
    else:
        await _test_target_database(database_url, schema=target_schema)

    local_url = _validate_postgresql_url(local_database_url(), "로컬 PostgreSQL DATABASE URL")
    local_langgraph_url = _validate_postgresql_url(
        local_langgraph_database_url(),
        "로컬 LangGraph DB URL",
    )

    # Supabase 비밀정보는 provider 활성화 전에도 backend/.env에만 보관할 수 있습니다.
    # provider 값은 전환이 끝날 때까지 local로 유지합니다.
    write_env_values({
        ENV_SUPABASE_DATABASE_URL: database_url,
        ENV_SUPABASE_LANGGRAPH_DATABASE_URL: langgraph_url,
        ENV_SUPABASE_DB_SCHEMA: target_schema,
    })
    get_settings.cache_clear()

    # Control DB가 실제로 기록 가능해야 전환을 시작합니다. 실패하면 runtime은 건드리지 않습니다.
    await _test_target_database(local_url)
    await _save_local_provider_state(PROVIDER_SUPABASE, database_url)

    try:
        await rebind_database(database_url, schema=target_schema)
        # v5.308: project machine-scope schema changes must also be present when
        # callers skip the full schema initializer. The migration is idempotent.
        await migrate_agentstudio_schema()
        # v5.446: learning DDL is a lifecycle migration, never a Learning Center page-read side effect.
        await _prepare_learning_schema_after_runtime_rebind()
        scoped_langgraph_url = _postgres_url_with_search_path(langgraph_url, target_schema)
        langgraph_ok = bool(await agent_graph_runtime.set_database_url(scoped_langgraph_url, restart=True))
        if not langgraph_ok:
            raise RuntimeError(
                agent_graph_runtime.last_error
                or "Supabase LangGraph Checkpointer runtime 전환에 실패했습니다."
            )

        # DB + LangGraph runtime이 모두 살아난 뒤에만 활성 provider를 확정합니다.
        write_env_values({ENV_PROVIDER_KEY: PROVIDER_SUPABASE})
        get_settings.cache_clear()
        _ACTIVE_PROVIDER = PROVIDER_SUPABASE
        _LAST_ERROR = ""
    except Exception as exc:
        # 부분 전환 방지: runtime과 Control DB 선택 상태를 모두 local로 되돌립니다.
        rollback_errors: list[str] = []
        try:
            await rebind_database(local_url)
        except Exception as rollback_exc:
            rollback_errors.append(f"DB runtime 복귀 실패: {rollback_exc}")
        try:
            await agent_graph_runtime.set_database_url(local_langgraph_url, restart=True)
        except Exception as rollback_exc:
            rollback_errors.append(f"LangGraph 복귀 실패: {rollback_exc}")
        try:
            await _save_local_provider_state(PROVIDER_LOCAL, "")
        except Exception as rollback_exc:
            rollback_errors.append(f"로컬 선택 상태 복귀 실패: {rollback_exc}")
        try:
            write_env_values({ENV_PROVIDER_KEY: PROVIDER_LOCAL})
            get_settings.cache_clear()
        except Exception as rollback_exc:
            rollback_errors.append(f".env provider 복귀 실패: {rollback_exc}")

        _ACTIVE_PROVIDER = PROVIDER_LOCAL
        _LAST_ERROR = f"Supabase Runtime 전환 실패: {exc}. 로컬 PostgreSQL로 복귀했습니다."
        if rollback_errors:
            _LAST_ERROR += " / " + " / ".join(rollback_errors)
        return {
            "ok": False,
            "active_provider": PROVIDER_LOCAL,
            "target": _target_label(database_url),
            "local_settings_updated": True,
            "schema": schema_result,
            "langgraph_ok": False,
            "langgraph_error": str(exc),
            "message": _LAST_ERROR,
        }

    return {
        "ok": True,
        "active_provider": PROVIDER_SUPABASE,
        "target": _target_label(database_url),
        "supabase_schema": target_schema,
        "local_settings_updated": True,
        "schema": schema_result,
        "langgraph_ok": True,
        "langgraph_error": "",
        "message": (
            f"Supabase PostgreSQL [{target_schema}] 스키마로 안전하게 전환했습니다. 스키마/DB/LangGraph 검증이 모두 성공한 뒤 "
            "로컬 PostgreSQL app_settings와 backend/.env provider 상태를 supabase로 확정했습니다."
        ),
    }


async def apply_saved_database_provider() -> dict[str, Any]:
    """Startup: bootstrap locally, then apply the provider declared in project-root .env.

    The local PostgreSQL app_settings provider row is a mirror/cache only. It must not
    override AGENTSTUDIO_DATABASE_PROVIDER from the user-managed project-root .env.
    """
    global _ACTIVE_PROVIDER, _LAST_ERROR
    from app.services.langgraph_runtime import agent_graph_runtime

    desired = _normalize_provider(getattr(get_settings(), "agentstudio_database_provider", PROVIDER_LOCAL))

    if desired != PROVIDER_SUPABASE:
        _ACTIVE_PROVIDER = PROVIDER_LOCAL
        _LAST_ERROR = ""
        await agent_graph_runtime.set_database_url(local_langgraph_database_url(), restart=False)
        return {
            "ok": True,
            "selected_provider": PROVIDER_LOCAL,
            "active_provider": PROVIDER_LOCAL,
            "target": _target_label(local_database_url()),
            "message": "기본 로컬 PostgreSQL 사용",
        }

    database_url = configured_supabase_database_url()
    langgraph_url = configured_supabase_langgraph_url()
    target_schema = configured_supabase_schema()
    if not database_url:
        _ACTIVE_PROVIDER = PROVIDER_LOCAL
        _LAST_ERROR = "Supabase가 선택되어 있지만 SUPABASE_DATABASE_URL이 없습니다. 로컬 PostgreSQL로 안전 복귀했습니다."
        await agent_graph_runtime.set_database_url(local_langgraph_database_url(), restart=False)
        return {"ok": False, "selected_provider": PROVIDER_SUPABASE, "active_provider": PROVIDER_LOCAL, "message": _LAST_ERROR}

    try:
        await rebind_database(database_url, schema=target_schema)
        # Saved Supabase providers are rebound after the local bootstrap migration.
        # v5.388: create newly-added ORM tables (for example ui_themes) on the actual
        # active Supabase schema before compatibility migrations or API queries run.
        await ensure_runtime_metadata_tables()
        await migrate_agentstudio_schema()
        scoped_langgraph_url = _postgres_url_with_search_path(
            langgraph_url or _langgraph_url_from_database_url(database_url),
            target_schema,
        )
        langgraph_ok = bool(await agent_graph_runtime.set_database_url(
            scoped_langgraph_url,
            restart=False,
        ))
        if not langgraph_ok:
            raise RuntimeError(agent_graph_runtime.last_error or "Supabase LangGraph Checkpointer 연결 실패")
        _ACTIVE_PROVIDER = PROVIDER_SUPABASE
        _LAST_ERROR = ""
        return {
            "ok": True,
            "selected_provider": PROVIDER_SUPABASE,
            "active_provider": PROVIDER_SUPABASE,
            "target": _target_label(database_url),
            "supabase_schema": target_schema,
            "message": f"저장된 선택에 따라 Supabase PostgreSQL [{target_schema}] runtime을 적용했습니다.",
        }
    except Exception as exc:
        _ACTIVE_PROVIDER = PROVIDER_LOCAL
        _LAST_ERROR = f"Supabase 자동 전환 실패: {exc}. 로컬 PostgreSQL을 계속 사용합니다."
        try:
            await rebind_database(local_database_url())
        except Exception:
            pass
        await agent_graph_runtime.set_database_url(local_langgraph_database_url(), restart=False)
        return {"ok": False, "selected_provider": PROVIDER_SUPABASE, "active_provider": PROVIDER_LOCAL, "message": _LAST_ERROR}
