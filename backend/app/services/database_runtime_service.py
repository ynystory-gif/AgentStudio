from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import UniqueConstraint, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.core.database import (
    Base,
    migrate_agentstudio_schema_on_connection,
    normalize_async_database_url,
    rebind_database,
)
from app.core.machine_identity import current_pc_name
from app.models.entities import AppSetting


PROVIDER_LOCAL = "local"
PROVIDER_SUPABASE = "supabase"
SUPPORTED_PROVIDERS = {PROVIDER_LOCAL, PROVIDER_SUPABASE}

PROVIDER_SETTING_KEY = "AGENTSTUDIO_DATABASE_PROVIDER"
SUPABASE_TARGET_SETTING_KEY = "AGENTSTUDIO_SUPABASE_TARGET"

ENV_PROVIDER_KEY = "AGENTSTUDIO_DATABASE_PROVIDER"
ENV_SUPABASE_DATABASE_URL = "SUPABASE_DATABASE_URL"
ENV_SUPABASE_LANGGRAPH_DATABASE_URL = "SUPABASE_LANGGRAPH_DATABASE_URL"

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


async def _test_target_database(database_url: str) -> None:
    candidate = create_async_engine(normalize_async_database_url(database_url), pool_pre_ping=True)
    try:
        async with candidate.connect() as conn:
            await conn.execute(text("SELECT 1"))
    finally:
        await candidate.dispose()


LANGGRAPH_REQUIRED_TABLES = {
    "checkpoint_migrations",
    "checkpoints",
    "checkpoint_blobs",
    "checkpoint_writes",
}


def _ensure_metadata_indexes(sync_conn) -> list[str]:
    """Create metadata-defined indexes only when they are missing."""
    created_or_verified: list[str] = []
    for table in Base.metadata.sorted_tables:
        for index in sorted(table.indexes, key=lambda item: item.name or ""):
            index.create(bind=sync_conn, checkfirst=True)
            if index.name:
                created_or_verified.append(index.name)
    return created_or_verified


def _inspect_agentstudio_schema(sync_conn) -> dict[str, Any]:
    """Compare the live PostgreSQL schema with the current SQLAlchemy metadata."""
    inspector = inspect(sync_conn)
    schema = inspector.default_schema_name or "public"
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


async def _prepare_agentstudio_schema_transaction(candidate) -> dict[str, Any]:
    """Prepare pgvector + AgentStudio tables in one PostgreSQL transaction."""
    import app.models.entities  # noqa: F401

    migration: dict[str, Any] = {"ok": False, "count": 0, "applied": []}
    verification: dict[str, Any] = {"ok": False}
    indexes: list[str] = []
    extension_status = ""

    async with candidate.begin() as conn:
        # Preflight first. Supabase normally exposes vector, but a project/role can still deny CREATE EXTENSION.
        available = bool((await conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM pg_available_extensions WHERE name='vector')"
        ))).scalar())
        installed_before = bool((await conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector')"
        ))).scalar())
        if not available and not installed_before:
            raise RuntimeError("Supabase PostgreSQL에서 pgvector(vector) 확장을 사용할 수 없습니다.")

        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        installed_after = bool((await conn.execute(text(
            "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector')"
        ))).scalar())
        if not installed_after:
            raise RuntimeError("pgvector(vector) 확장 설치 확인에 실패했습니다.")
        extension_status = "already_installed" if installed_before else "installed"

        # create_all + compatibility ALTERs + index reconciliation share this transaction.
        await conn.run_sync(Base.metadata.create_all)
        migration = await migrate_agentstudio_schema_on_connection(conn)
        indexes = await conn.run_sync(_ensure_metadata_indexes)
        verification = await conn.run_sync(_inspect_agentstudio_schema)
        if not verification.get("ok"):
            raise RuntimeError(
                "AgentStudio 스키마 검증 실패: "
                + _schema_problem_summary(verification)
            )

    return {
        "ok": True,
        "vector": extension_status,
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


async def _setup_and_verify_langgraph(langgraph_database_url: str) -> dict[str, Any]:
    """Use the installed LangGraph package as the authoritative checkpoint migration source."""
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        async with AsyncPostgresSaver.from_conn_string(langgraph_database_url) as checkpointer:
            await checkpointer.setup()
    except Exception as exc:
        return {
            "ok": False,
            "phase": "langgraph_setup",
            "tables": [],
            "missing_tables": sorted(LANGGRAPH_REQUIRED_TABLES),
            "message": f"LangGraph 공식 Checkpointer migration 실패: {exc}",
        }

    engine = create_async_engine(
        normalize_async_database_url(langgraph_database_url),
        pool_pre_ping=True,
    )
    try:
        async with engine.connect() as conn:
            rows = (
                await conn.execute(text(
                    """
                    SELECT tablename
                    FROM pg_tables
                    WHERE schemaname = current_schema()
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
            tables = {str(name) for name in rows}
            missing = sorted(LANGGRAPH_REQUIRED_TABLES - tables)
            migration_count = 0
            if "checkpoint_migrations" in tables:
                migration_count = int((await conn.execute(text(
                    "SELECT COUNT(*) FROM checkpoint_migrations"
                ))).scalar() or 0)
    finally:
        await engine.dispose()

    return {
        "ok": not missing,
        "phase": "langgraph_verify",
        "tables": sorted(tables),
        "missing_tables": missing,
        "migration_count": migration_count,
        "message": (
            "LangGraph 공식 Checkpointer setup/검증 완료"
            if not missing
            else "LangGraph 필수 테이블 누락: " + ", ".join(missing)
        ),
    }


async def initialize_supabase_schema(database_url: str, langgraph_database_url: str = "") -> dict[str, Any]:
    """
    Create/upgrade the selected Supabase PostgreSQL idempotently.

    AgentStudio DDL is transactional. LangGraph tables are NEVER hand-maintained here;
    the installed AsyncPostgresSaver.setup() is the authoritative migration source.
    """
    database_url = str(database_url or configured_supabase_database_url()).strip()
    database_url = _validate_postgresql_url(database_url, "Supabase DATABASE URL")
    langgraph_database_url = str(
        langgraph_database_url
        or configured_supabase_langgraph_url()
        or _langgraph_url_from_database_url(database_url)
    ).strip()
    langgraph_database_url = _validate_postgresql_url(
        langgraph_database_url,
        "Supabase LangGraph DB URL",
    )

    candidate = create_async_engine(
        normalize_async_database_url(database_url),
        pool_pre_ping=True,
    )
    try:
        try:
            async with candidate.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception as exc:
            return {
                "ok": False,
                "phase": "connection",
                "target": _target_label(database_url),
                "rolled_back": True,
                "message": f"Supabase 연결 확인 실패: {exc}",
            }

        try:
            agentstudio = await _prepare_agentstudio_schema_transaction(candidate)
        except Exception as exc:
            # candidate.begin() guarantees rollback for AgentStudio DDL on this phase.
            return {
                "ok": False,
                "phase": "agentstudio_schema",
                "target": _target_label(database_url),
                "rolled_back": True,
                "message": f"Supabase AgentStudio 스키마 준비 실패(변경사항 rollback): {exc}",
            }
    finally:
        await candidate.dispose()

    langgraph = await _setup_and_verify_langgraph(langgraph_database_url)
    verification = dict(agentstudio.get("verification") or {})
    if not langgraph.get("ok"):
        return {
            "ok": False,
            "phase": "langgraph",
            "target": _target_label(database_url),
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
            f"Supabase 스키마 준비/재검증 완료: AgentStudio {verification.get('actual_agentstudio_table_count', 0)}개 테이블"
            f" · LangGraph {len(langgraph.get('tables') or [])}개 테이블 · 재실행 안전"
        ),
    }


async def runtime_status() -> dict[str, Any]:
    provider = _ACTIVE_PROVIDER
    desired = PROVIDER_LOCAL
    local_state_error = ""
    try:
        state = await _load_local_provider_state()
        desired = _normalize_provider(state.get(PROVIDER_SETTING_KEY))
    except Exception as exc:
        local_state_error = str(exc)
        desired = _normalize_provider(getattr(get_settings(), "agentstudio_database_provider", PROVIDER_LOCAL))

    return {
        "ok": True,
        "default_provider": PROVIDER_LOCAL,
        "selected_provider": desired,
        "active_provider": provider,
        "local_target": _target_label(local_database_url()),
        "supabase_configured": bool(configured_supabase_database_url()),
        "supabase_target": _target_label(configured_supabase_database_url()),
        "langgraph_target": _target_label(current_runtime_langgraph_url()),
        "local_settings_db": _target_label(local_database_url()),
        "local_state_error": local_state_error,
        "last_error": _LAST_ERROR,
        "schema_script": schema_script_info(),
    }


async def activate_database_provider(
    provider: str,
    *,
    supabase_database_url: str = "",
    supabase_langgraph_database_url: str = "",
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
    langgraph_url = str(
        supabase_langgraph_database_url
        or configured_supabase_langgraph_url()
        or _langgraph_url_from_database_url(database_url)
    ).strip()
    langgraph_url = _validate_postgresql_url(langgraph_url, "Supabase LangGraph DB URL")

    schema_result = None
    if initialize_schema:
        schema_result = await initialize_supabase_schema(database_url, langgraph_url)
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
        await _test_target_database(database_url)

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
    })
    get_settings.cache_clear()

    # Control DB가 실제로 기록 가능해야 전환을 시작합니다. 실패하면 runtime은 건드리지 않습니다.
    await _test_target_database(local_url)
    await _save_local_provider_state(PROVIDER_SUPABASE, database_url)

    try:
        await rebind_database(database_url)
        langgraph_ok = bool(await agent_graph_runtime.set_database_url(langgraph_url, restart=True))
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
        "local_settings_updated": True,
        "schema": schema_result,
        "langgraph_ok": True,
        "langgraph_error": "",
        "message": (
            "Supabase PostgreSQL로 안전하게 전환했습니다. 스키마/DB/LangGraph 검증이 모두 성공한 뒤 "
            "로컬 PostgreSQL app_settings와 backend/.env provider 상태를 supabase로 확정했습니다."
        ),
    }


async def apply_saved_database_provider() -> dict[str, Any]:
    """Startup: bootstrap locally first, then rebind to saved Supabase when selected."""
    global _ACTIVE_PROVIDER, _LAST_ERROR
    from app.services.langgraph_runtime import agent_graph_runtime

    desired = PROVIDER_LOCAL
    try:
        state = await _load_local_provider_state()
        desired = _normalize_provider(state.get(PROVIDER_SETTING_KEY))
    except Exception:
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
    if not database_url:
        _ACTIVE_PROVIDER = PROVIDER_LOCAL
        _LAST_ERROR = "Supabase가 선택되어 있지만 SUPABASE_DATABASE_URL이 없습니다. 로컬 PostgreSQL로 안전 복귀했습니다."
        await agent_graph_runtime.set_database_url(local_langgraph_database_url(), restart=False)
        return {"ok": False, "selected_provider": PROVIDER_SUPABASE, "active_provider": PROVIDER_LOCAL, "message": _LAST_ERROR}

    try:
        await rebind_database(database_url)
        langgraph_ok = bool(await agent_graph_runtime.set_database_url(
            langgraph_url or _langgraph_url_from_database_url(database_url),
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
            "message": "저장된 선택에 따라 Supabase PostgreSQL runtime을 적용했습니다.",
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
