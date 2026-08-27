from __future__ import annotations

import asyncio
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse, quote

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.core.database import Base
from app.services.pgvector_installer import (
    install_pgvector_windows18,
    detect_postgresql18_root,
    validate_postgresql18_root,
)

# 모든 SQLAlchemy 모델을 Base.metadata에 등록
import app.models.entities  # noqa: F401


AGENTSTUDIO_CORE_TABLES = [
    "agentstudio_machines",
    "project_analyses",
    "app_settings",
    "projects",
    "agent_design_projects",
    "agent_design_project_versions",
    "ui_themes",
    "conversation_messages",
    "requirements",
    "mcp_servers",
    "tool_registry",
    "approval_requests",
    "memory_records",
    "project_file_index",
    "evaluation_records",
    "usage_records",
    "jobs",
]


def _parse_database_url(url: str) -> dict:
    raw = (
        url.replace("postgresql+psycopg://", "postgresql://", 1)
        .replace("postgresql+psycopg://", "postgresql://", 1)
    )
    parsed = urlparse(raw)
    return {
        "host": parsed.hostname or "127.0.0.1",
        "port": parsed.port or 5432,
        "database": (parsed.path or "/postgres").lstrip("/") or "postgres",
        "user": parsed.username or "",
        "password": parsed.password or "",
    }


def _safe_identifier(value: str, label: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value or ""):
        raise RuntimeError(
            f"{label}에는 영문자, 숫자, 밑줄(_)만 사용할 수 있습니다: {value!r}"
        )
    return value


def _run_psql(
    psql: Path,
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    sql: str,
    timeout: int = 30,
) -> dict:
    env = os.environ.copy()
    env["PGPASSWORD"] = password
    env["PGCONNECT_TIMEOUT"] = "10"

    args = [
        str(psql),
        "-X",
        "-v", "ON_ERROR_STOP=1",
        "-h", host,
        "-p", str(port),
        "-U", user,
        "-d", database,
        "-c", sql,
    ]

    env["PGCLIENTENCODING"] = "UTF8"

    proc = subprocess.run(
        args,
        env=env,
        capture_output=True,
        text=False,
        timeout=timeout,
    )

    def _decode(data: bytes | None) -> str:
        raw = data or b""
        if not raw:
            return ""
        for encoding in ("utf-8", "cp949"):
            try:
                return raw.decode(encoding).strip()
            except UnicodeDecodeError:
                pass
        return raw.decode("utf-8", errors="replace").strip()

    return {
        "returncode": proc.returncode,
        "stdout": _decode(proc.stdout),
        "stderr": _decode(proc.stderr),
    }


async def _create_agentstudio_tables(database_url: str) -> dict:
    """
    새 AgentStudio DB에 SQLAlchemy 모델 테이블을 생성합니다.
    현재 실행 중인 기존 engine을 사용하지 않고 새 URL로 임시 engine을 만듭니다.
    """
    # 사용자/환경설정에는 기존 호환 형식(postgresql+asyncpg)을 유지하되
    # AgentStudio 내부 연결은 Windows SelectorEventLoop에서 안정적인 psycopg async를 사용합니다.
    runtime_database_url = database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
    new_engine = create_async_engine(
        runtime_database_url,
        pool_pre_ping=True,
    )

    try:
        async with new_engine.begin() as conn:
            # pgvector는 이미 관리자 계정으로 활성화되었지만 안전하게 존재 확인
            await conn.execute(
                text(
                    "SELECT extname FROM pg_extension "
                    "WHERE extname='vector'"
                )
            )
            await conn.run_sync(Base.metadata.create_all)

        async with new_engine.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        """
                        SELECT tablename
                        FROM pg_tables
                        WHERE schemaname='public'
                        ORDER BY tablename
                        """
                    )
                )
            ).scalars().all()

        present = set(rows)
        missing = [
            table
            for table in AGENTSTUDIO_CORE_TABLES
            if table not in present
        ]

        return {
            "ok": not missing,
            "tables": rows,
            "missing": missing,
            "message": (
                f"AgentStudio 기본 테이블 {len(AGENTSTUDIO_CORE_TABLES)}개 생성 완료"
                if not missing
                else f"일부 AgentStudio 테이블이 없습니다: {', '.join(missing)}"
            ),
        }
    finally:
        await new_engine.dispose()


async def _create_langgraph_tables(langgraph_database_url: str) -> dict:
    """
    LangGraph PostgreSQL Checkpointer가 필요한 테이블을 setup()으로 생성합니다.
    """
    try:
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        async with AsyncPostgresSaver.from_conn_string(
            langgraph_database_url
        ) as checkpointer:
            await checkpointer.setup()

        # 실제 생성 테이블을 확인
        async_url = langgraph_database_url.replace(
            "postgresql://",
            "postgresql+psycopg://",
            1,
        )
        engine = create_async_engine(async_url, pool_pre_ping=True)

        try:
            async with engine.connect() as conn:
                rows = (
                    await conn.execute(
                        text(
                            """
                            SELECT tablename
                            FROM pg_tables
                            WHERE schemaname='public'
                              AND (
                                tablename LIKE 'checkpoint%'
                                OR tablename LIKE 'writes%'
                              )
                            ORDER BY tablename
                            """
                        )
                    )
                ).scalars().all()
        finally:
            await engine.dispose()

        return {
            "ok": True,
            "tables": rows,
            "message": (
                "LangGraph Checkpointer 테이블 초기화 완료"
                + (f" ({', '.join(rows)})" if rows else "")
            ),
        }

    except Exception as e:
        return {
            "ok": False,
            "tables": [],
            "message": f"LangGraph Checkpointer 초기화 실패: {e}",
        }



def _pgvector_files_installed(pgroot: Path) -> bool:
    dll = pgroot / "lib" / "vector.dll"
    control = pgroot / "share" / "extension" / "vector.control"
    sql_files = list(
        (pgroot / "share" / "extension").glob("vector--*.sql")
    )
    return dll.exists() and control.exists() and bool(sql_files)


async def provision_agentstudio_database(
    *,
    postgresql_root: str,
    admin_user: str,
    admin_password: str,
    app_user: str,
    app_password: str,
    database_name: str = "theanova_agentstudio",
) -> dict:
    database_name = _safe_identifier(
        database_name,
        "데이터베이스 이름",
    )
    app_user = _safe_identifier(
        app_user,
        "애플리케이션 사용자명",
    )

    if not admin_user.strip():
        raise RuntimeError(
            "PostgreSQL 관리자 사용자명이 비어 있습니다."
        )
    if not admin_password:
        raise RuntimeError(
            "PostgreSQL 관리자 비밀번호가 비어 있습니다."
        )
    if not app_password:
        raise RuntimeError(
            "애플리케이션 사용자 비밀번호가 비어 있습니다."
        )

    pgroot = detect_postgresql18_root(
        postgresql_root
    )
    if not pgroot:
        checked = validate_postgresql18_root(
            postgresql_root
        )
        raise RuntimeError(
            checked.get("message")
            or "PostgreSQL 18 설치 경로를 확인하지 못했습니다."
        )

    psql = pgroot / "bin" / "psql.exe"

    current = _parse_database_url(
        get_settings().database_url
    )
    host = current["host"]
    port = current["port"]

    safe_app_literal = app_user.replace(
        "'",
        "''",
    )

    # --------------------------------------------------
    # 1. 관리자 접속 확인
    # --------------------------------------------------
    admin_check = await asyncio.to_thread(
        _run_psql,
        psql,
        host=host,
        port=port,
        user=admin_user,
        password=admin_password,
        database="postgres",
        sql="SELECT current_user, current_database();",
    )

    if admin_check["returncode"] != 0:
        detail = admin_check["stderr"] or admin_check["stdout"]
        raise RuntimeError(
            f"PostgreSQL 관리자 계정 접속 실패 ({admin_user}@{host}:{port}/postgres). "
            "입력한 관리자 비밀번호가 이 PostgreSQL 인스턴스의 계정과 일치하는지 확인하고 "
            "[관리자 계정 테스트]를 먼저 실행하세요."
            + (f" 상세: {detail}" if detail else "")
        )

    # --------------------------------------------------
    # 2. 앱 Role 생성 또는 갱신
    # --------------------------------------------------
    role_check = await asyncio.to_thread(
        _run_psql,
        psql,
        host=host,
        port=port,
        user=admin_user,
        password=admin_password,
        database="postgres",
        sql=(
            "SELECT 1 FROM pg_roles "
            f"WHERE rolname='{safe_app_literal}';"
        ),
    )

    if role_check["returncode"] != 0:
        raise RuntimeError(
            "AgentStudio Role 확인 실패: "
            + (
                role_check["stderr"]
                or role_check["stdout"]
            )
        )

    role_exists = bool(
        re.search(
            r"\b1\b",
            role_check["stdout"],
        )
    )

    escaped_pw = app_password.replace(
        "'",
        "''",
    )

    if role_exists:
        role_sql = (
            f"ALTER ROLE {app_user} "
            f"WITH LOGIN PASSWORD '{escaped_pw}';"
        )
    else:
        role_sql = (
            f"CREATE ROLE {app_user} "
            f"WITH LOGIN PASSWORD '{escaped_pw}';"
        )

    role_result = await asyncio.to_thread(
        _run_psql,
        psql,
        host=host,
        port=port,
        user=admin_user,
        password=admin_password,
        database="postgres",
        sql=role_sql,
    )

    if role_result["returncode"] != 0:
        raise RuntimeError(
            "AgentStudio 앱 Role 설정 실패: "
            + (
                role_result["stderr"]
                or role_result["stdout"]
            )
        )

    # --------------------------------------------------
    # 3. DB 생성 또는 OWNER 보정
    # --------------------------------------------------
    safe_db_literal = database_name.replace(
        "'",
        "''",
    )

    db_check = await asyncio.to_thread(
        _run_psql,
        psql,
        host=host,
        port=port,
        user=admin_user,
        password=admin_password,
        database="postgres",
        sql=(
            "SELECT 1 FROM pg_database "
            f"WHERE datname='{safe_db_literal}';"
        ),
    )

    if db_check["returncode"] != 0:
        raise RuntimeError(
            "AgentStudio DB 확인 실패: "
            + (
                db_check["stderr"]
                or db_check["stdout"]
            )
        )

    db_exists = bool(
        re.search(
            r"\b1\b",
            db_check["stdout"],
        )
    )

    if not db_exists:
        db_sql = (
            f"CREATE DATABASE {database_name} "
            f"OWNER {app_user};"
        )
    else:
        db_sql = (
            f"ALTER DATABASE {database_name} "
            f"OWNER TO {app_user};"
        )

    db_result = await asyncio.to_thread(
        _run_psql,
        psql,
        host=host,
        port=port,
        user=admin_user,
        password=admin_password,
        database="postgres",
        sql=db_sql,
    )

    if db_result["returncode"] != 0:
        raise RuntimeError(
            "AgentStudio DB 생성/OWNER 설정 실패: "
            + (
                db_result["stderr"]
                or db_result["stdout"]
            )
        )

    # --------------------------------------------------
    # 4. pgvector 바이너리 확인 / 자동 설치
    # --------------------------------------------------
    if not _pgvector_files_installed(pgroot):
        install_result = await install_pgvector_windows18(
            progress_cb=None,
            postgresql_root=str(pgroot),
            admin_user=admin_user,
            admin_password=admin_password,
            database_url=(
                f"postgresql://{admin_user}:"
                f"{quote(admin_password, safe='')}"
                f"@{host}:{port}/postgres"
            ),
        )

        if not install_result.get("ok"):
            raise RuntimeError(
                "pgvector 바이너리 자동 설치 실패: "
                + install_result.get("message", "알 수 없는 오류")
            )

    if not _pgvector_files_installed(pgroot):
        raise RuntimeError(
            "pgvector 설치 작업 후에도 vector.dll / vector.control / SQL 파일을 "
            "확인하지 못했습니다."
        )

    # --------------------------------------------------
    # 5. pgvector extension + schema 권한
    # --------------------------------------------------
    setup_sql = (
        f"GRANT CONNECT ON DATABASE {database_name} TO {app_user}; "
        "CREATE EXTENSION IF NOT EXISTS vector; "
        "ALTER SCHEMA public OWNER TO "
        f"{app_user}; "
        f"GRANT USAGE, CREATE ON SCHEMA public TO {app_user}; "
        f"GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO {app_user}; "
        f"GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO {app_user}; "
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT ALL PRIVILEGES ON TABLES TO {app_user}; "
        f"ALTER DEFAULT PRIVILEGES IN SCHEMA public "
        f"GRANT ALL PRIVILEGES ON SEQUENCES TO {app_user};"
    )

    setup_result = await asyncio.to_thread(
        _run_psql,
        psql,
        host=host,
        port=port,
        user=admin_user,
        password=admin_password,
        database=database_name,
        sql=setup_sql,
        timeout=60,
    )

    if setup_result["returncode"] != 0:
        raise RuntimeError(
            "AgentStudio DB 권한/pgvector 설정 실패: "
            + (
                setup_result["stderr"]
                or setup_result["stdout"]
            )
        )

    # --------------------------------------------------
    # 6. 연결 문자열 생성
    # --------------------------------------------------
    encoded_user = quote(
        app_user,
        safe="",
    )
    encoded_password = quote(
        app_password,
        safe="",
    )

    database_url = (
        f"postgresql+asyncpg://"
        f"{encoded_user}:{encoded_password}"
        f"@{host}:{port}/{database_name}"
    )
    langgraph_url = (
        f"postgresql://"
        f"{encoded_user}:{encoded_password}"
        f"@{host}:{port}/{database_name}"
    )

    # --------------------------------------------------
    # 7. AgentStudio SQLAlchemy 테이블 생성
    # --------------------------------------------------
    app_tables = await _create_agentstudio_tables(
        database_url
    )

    if not app_tables["ok"]:
        raise RuntimeError(
            app_tables["message"]
        )

    # --------------------------------------------------
    # 8. LangGraph Checkpointer 테이블 생성
    # --------------------------------------------------
    langgraph_tables = await _create_langgraph_tables(
        langgraph_url
    )

    if not langgraph_tables["ok"]:
        raise RuntimeError(
            langgraph_tables["message"]
        )

    # --------------------------------------------------
    # 9. 앱 계정으로 최종 검증
    # --------------------------------------------------
    verify_sql = (
        "SELECT current_database(), current_user; "
        "SELECT extname, extversion "
        "FROM pg_extension "
        "WHERE extname='vector'; "
        "SELECT COUNT(*) AS table_count "
        "FROM pg_tables "
        "WHERE schemaname='public';"
    )

    verify = await asyncio.to_thread(
        _run_psql,
        psql,
        host=host,
        port=port,
        user=app_user,
        password=app_password,
        database=database_name,
        sql=verify_sql,
        timeout=30,
    )

    if verify["returncode"] != 0:
        raise RuntimeError(
            "AgentStudio DB 최종 검증 실패: "
            + (
                verify["stderr"]
                or verify["stdout"]
            )
        )

    all_tables = sorted(
        set(
            app_tables["tables"]
            + langgraph_tables["tables"]
        )
    )

    return {
        "ok": True,
        "message": (
            f"{database_name} 생성 + 권한 + pgvector + "
            f"AgentStudio/LangGraph 테이블 초기화 완료"
        ),
        "database_name": database_name,
        "app_user": app_user,
        "host": host,
        "port": port,
        "database_url": database_url,
        "langgraph_database_url": langgraph_url,
        "agentstudio_tables": app_tables["tables"],
        "langgraph_tables": langgraph_tables["tables"],
        "table_count": len(all_tables),
        "verification": verify["stdout"],
    }
