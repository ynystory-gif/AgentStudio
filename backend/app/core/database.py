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
    """
    기존 AgentStudio DB를 삭제하지 않고 필요한 컬럼/기본값을 안전하게 보정합니다.

    SQLAlchemy create_all()은 기존 테이블에 새 컬럼을 추가하지 않으므로,
    버전 업 시 필요한 ALTER TABLE을 별도로 실행합니다.
    """
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

    async with engine.begin() as conn:
        # 기존 로컬 DB의 app_settings는 현재 PC 설정으로 귀속시켜 보존합니다.
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
            applied.append(
                " ".join(sql.strip().split())
            )

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
