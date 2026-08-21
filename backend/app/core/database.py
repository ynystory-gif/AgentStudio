from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import get_settings
from app.core.machine_identity import current_pc_name


def normalize_async_database_url(url: str) -> str:
    value = (url or "").strip()
    if value.startswith("postgresql+asyncpg://"):
        return value.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    if value.startswith("postgresql://"):
        return value.replace("postgresql://", "postgresql+psycopg://", 1)
    return value


settings = get_settings()
database_url = normalize_async_database_url(settings.database_url)

engine = create_async_engine(
    database_url,
    pool_pre_ping=True,
)

SessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def rebind_database(new_database_url: str) -> dict:
    """
    저장된 DATABASE_URL을 현재 Backend 프로세스에 즉시 적용합니다.

    새 Engine으로 SELECT 1 연결 검증에 성공한 경우에만 전역 engine과
    기존 SessionLocal async_sessionmaker의 bind를 교체합니다. 따라서
    settings_service 등에서 이미 import한 SessionLocal 참조도 새 DB를 사용합니다.
    """
    global engine, database_url

    normalized = normalize_async_database_url(new_database_url)
    candidate = create_async_engine(normalized, pool_pre_ping=True)
    try:
        async with candidate.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        await candidate.dispose()
        raise

    old_engine = engine
    engine = candidate
    database_url = normalized
    SessionLocal.configure(bind=candidate)
    try:
        await old_engine.dispose()
    except Exception:
        pass

    return {
        "ok": True,
        "database_url": new_database_url,
        "runtime_database_url": normalized,
    }


class Base(DeclarativeBase):
    pass


async def get_db():
    async with SessionLocal() as session:
        yield session


async def init_db():
    import app.models.entities  # noqa: F401
    async with engine.begin() as conn:
        await conn.execute(
            text("SELECT extname FROM pg_extension WHERE extname='vector'")
        )
        await conn.run_sync(Base.metadata.create_all)


async def migrate_agentstudio_schema() -> dict:
    """현재 AgentStudio runtime engine의 스키마를 안전하게 보정합니다."""
    return await migrate_agentstudio_schema_on_engine(engine)


async def migrate_agentstudio_schema_on_engine(target_engine) -> dict:
    """
    지정한 PostgreSQL engine의 AgentStudio 스키마를 삭제 없이 보정합니다.

    v5.284에서는 신규/기존 Supabase 모두 같은 migration을 반복 실행할 수 있도록
    실제 SQL 적용부를 connection 단위 함수로 분리했습니다.
    """
    async with target_engine.begin() as conn:
        return await migrate_agentstudio_schema_on_connection(conn)


async def migrate_agentstudio_schema_on_connection(conn) -> dict:
    """이미 열린 transaction 안에서 AgentStudio 호환 migration을 적용합니다."""
    # Project ORM이 요구하는 전체 컬럼을 보정합니다.
    # create_all()은 이미 존재하는 projects 테이블에 새 컬럼을 추가하지 않으므로
    # 과거 버전 DB에서도 현재 ORM SELECT가 실패하지 않도록 모두 IF NOT EXISTS로 관리합니다.
    pc_name = current_pc_name()

    # v5.264: shared PostgreSQL DB에서도 PC별 환경 설정이 섞이지 않도록
    # app_settings를 (pc_name, key) 복합키 구조로 보정합니다.
    machine_setting_statements = [
        """
        ALTER TABLE app_settings
        ADD COLUMN IF NOT EXISTS pc_name VARCHAR(255) NOT NULL DEFAULT ''
        """,
        """
        DO $$
        DECLARE r RECORD;
        BEGIN
          FOR r IN
            SELECT c.conname
            FROM pg_constraint c
            JOIN pg_class t ON t.oid = c.conrelid
            WHERE t.relname = 'app_settings'
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
            EXECUTE format('ALTER TABLE app_settings DROP CONSTRAINT %I', r.conname);
          END LOOP;
        END $$
        """,
        """
        DROP INDEX IF EXISTS ix_app_settings_key
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_app_settings_key
        ON app_settings(key)
        """,
        """
        CREATE INDEX IF NOT EXISTS ix_app_settings_pc_name
        ON app_settings(pc_name)
        """,
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_app_settings_pc_name_key
        ON app_settings(pc_name, key)
        """,
    ]

    statements = [
        """
        ALTER TABLE projects
        ADD COLUMN IF NOT EXISTS cache_path VARCHAR(1000) NOT NULL DEFAULT ''
        """,
        """
        ALTER TABLE projects
        ADD COLUMN IF NOT EXISTS temp_path VARCHAR(1000) NOT NULL DEFAULT ''
        """,
        """
        ALTER TABLE projects
        ADD COLUMN IF NOT EXISTS output_path VARCHAR(1000) NOT NULL DEFAULT ''
        """,
        """
        ALTER TABLE projects
        ADD COLUMN IF NOT EXISTS venv_path VARCHAR(1000) NOT NULL DEFAULT ''
        """,
        """
        ALTER TABLE projects
        ADD COLUMN IF NOT EXISTS models_path VARCHAR(1000) NOT NULL DEFAULT ''
        """,
        """
        ALTER TABLE projects
        ADD COLUMN IF NOT EXISTS description TEXT NOT NULL DEFAULT ''
        """,
        """
        ALTER TABLE projects
        ADD COLUMN IF NOT EXISTS created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        """,
        """
        ALTER TABLE projects
        ADD COLUMN IF NOT EXISTS last_opened_at TIMESTAMP NULL
        """,
        """
        ALTER TABLE projects
        ADD COLUMN IF NOT EXISTS is_favorite BOOLEAN NOT NULL DEFAULT FALSE
        """,
    ]

    applied = []

    # 기존 DB의 app_settings는 현재 PC 설정으로 귀속시켜 보존합니다.
    # 먼저 pc_name 컬럼만 만든 뒤 기존 빈 값을 현재 PC 이름으로 채웁니다.
    await conn.execute(text(machine_setting_statements[0]))
    applied.append(" ".join(machine_setting_statements[0].strip().split()))
    await conn.execute(
        text("UPDATE app_settings SET pc_name = :pc_name WHERE COALESCE(pc_name, '') = ''"),
        {"pc_name": pc_name},
    )
    applied.append(f"app_settings legacy rows -> pc_name={pc_name}")

    for sql in machine_setting_statements[1:]:
        await conn.execute(text(sql))
        applied.append(" ".join(sql.strip().split()))

    for sql in statements:
        await conn.execute(text(sql))
        applied.append(" ".join(sql.strip().split()))

    return {
        "ok": True,
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
        "id",
        "name",
        "root_path",
        "cache_path",
        "temp_path",
        "output_path",
        "venv_path",
        "models_path",
        "description",
        "created_at",
        "last_opened_at",
        "is_favorite",
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

        existing = {
            str(row[0])
            for row in result.fetchall()
        }

    missing = sorted(required - existing)

    return {
        "ok": not missing,
        "required": sorted(required),
        "existing": sorted(existing),
        "missing": missing,
    }
