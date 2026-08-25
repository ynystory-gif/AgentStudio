from __future__ import annotations

import asyncio
import socket
import traceback
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy import text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.services.ollama_installer import detect_ollama_exe


CONNECTION_LOG_DIR = Path(__file__).resolve().parents[2] / "logs" / "connection_tests"


def _write_connection_failure_log(service: str, lines: list[str]) -> str:
    CONNECTION_LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = (CONNECTION_LOG_DIR / f"{stamp}_{service}_connection.log").resolve()
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def _can_connect(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.5):
            return True
    except OSError:
        return False


def _ollama_recommendation(*, exe: Path | None, port_open: bool, error: Exception) -> str:
    if exe is None:
        return "Ollama 실행 파일을 찾지 못했습니다. Ollama 설치 여부를 확인하거나 'Ollama 설치'를 실행하세요."
    if not port_open:
        return "Ollama 기본 서비스 포트에 연결할 수 없습니다. Ollama 앱/서비스가 실행 중인지 확인하고 필요하면 'ollama serve'를 실행하세요."
    if isinstance(error, httpx.HTTPStatusError):
        return "Ollama HTTP 서비스에는 연결되었지만 오류 상태가 반환되었습니다. 로그의 HTTP 상태와 응답 내용을 확인하세요."
    return "Ollama URL, 실행 상태, 방화벽/보안 프로그램 및 로그의 상세 예외를 확인하세요."


def _safe_database_target(database_url: str) -> dict:
    try:
        url = make_url(database_url)
        return {
            "host": url.host or "127.0.0.1",
            "port": int(url.port or 5432),
            "database": url.database or "postgres",
            "user": url.username or "",
        }
    except Exception:
        return {"host": "127.0.0.1", "port": 5432, "database": "", "user": ""}


def _database_sqlstate(error: Exception) -> str:
    candidates = [error, getattr(error, "orig", None)]
    orig = getattr(error, "orig", None)
    if orig is not None:
        candidates.extend([getattr(orig, "__cause__", None), getattr(orig, "__context__", None)])
    for item in candidates:
        if item is None:
            continue
        for attr in ("sqlstate", "pgcode"):
            value = getattr(item, attr, None)
            if value:
                return str(value)
    return ""


def _friendly_database_failure(error: Exception, target: dict, *, prefix: str) -> dict:
    code = _database_sqlstate(error)
    label = f"{target.get('user') or '?'}@{target.get('host')}:{target.get('port')}/{target.get('database') or '?'}"
    if code == "28P01":
        message = f"{prefix} 실패 - {label} 비밀번호 인증에 실패했습니다."
        recommendation = "현재 테스트는 화면의 임시 관리자 비밀번호가 아니라 표시된 연결 대상 계정의 비밀번호를 사용합니다. DATABASE_URL 또는 관리자 계정 테스트 대상을 확인하세요."
    elif code == "3D000":
        message = f"{prefix} 실패 - 데이터베이스가 없습니다: {target.get('database') or '?'}"
        recommendation = "AgentStudio 전용 DB 생성 여부와 DATABASE_URL의 데이터베이스 이름을 확인하세요."
    elif code.startswith("08"):
        message = f"{prefix} 실패 - PostgreSQL 서버 연결이 끊겼습니다: {target.get('host')}:{target.get('port')}"
        recommendation = "PostgreSQL 서비스 실행 상태와 포트, 서버 로그를 확인한 뒤 다시 테스트하세요."
    else:
        message = f"{prefix} 실패 - {label} 연결을 확인하세요."
        recommendation = "호스트/포트/사용자/비밀번호/데이터베이스를 확인하세요."
    return {
        "ok": False,
        "message": message,
        "sqlstate": code,
        "target": target,
        "detail": str(error),
        "recommendation": recommendation,
    }


async def _with_database(database_url: str, callback):
    # 화면에 입력된 DATABASE_URL을 즉시 테스트할 수 있도록 요청값을 우선 사용합니다.
    # 실제 SQLAlchemy 연결은 Windows SelectorEventLoop 안정성을 위해 psycopg async로 정규화합니다.
    from app.core.database import normalize_async_database_url
    url = normalize_async_database_url(database_url)
    temp_engine = create_async_engine(url, pool_pre_ping=True)
    try:
        async with temp_engine.connect() as conn:
            return await callback(conn)
    finally:
        await temp_engine.dispose()


async def test_postgresql(database_url: str | None = None) -> dict:
    effective_url = (database_url or get_settings().database_url or "").strip()
    target = _safe_database_target(effective_url)
    try:
        async def _probe(conn):
            return await conn.scalar(text("SELECT 1"))
        value = await _with_database(effective_url, _probe)
        return {
            "ok": value == 1,
            "message": f"AgentStudio DB 연결 성공 ({target['user']}@{target['host']}:{target['port']}/{target['database']})",
            "target": target,
        }
    except Exception as e:
        return _friendly_database_failure(e, target, prefix="AgentStudio DB 연결")


async def test_postgresql_admin(*, admin_user: str, admin_password: str) -> dict:
    current = _safe_database_target(get_settings().database_url)
    target = {
        "host": current["host"],
        "port": current["port"],
        "database": "postgres",
        "user": (admin_user or "postgres").strip() or "postgres",
    }
    if not admin_password:
        return {
            "ok": False,
            "message": "PostgreSQL 관리자 비밀번호를 입력하세요.",
            "target": target,
            "recommendation": "이 비밀번호는 저장하지 않으며 관리자 계정 연결 확인에만 사용합니다.",
        }
    url = URL.create(
        "postgresql+psycopg",
        username=target["user"],
        password=admin_password,
        host=target["host"],
        port=target["port"],
        database="postgres",
    )
    temp_engine = create_async_engine(url, pool_pre_ping=True)
    try:
        async with temp_engine.connect() as conn:
            value = await conn.scalar(text("SELECT 1"))
        return {
            "ok": value == 1,
            "message": f"PostgreSQL 관리자 계정 연결 성공 ({target['user']}@{target['host']}:{target['port']}/postgres)",
            "target": target,
        }
    except Exception as e:
        return _friendly_database_failure(e, target, prefix="PostgreSQL 관리자 계정 연결")
    finally:
        await temp_engine.dispose()


async def test_pgvector(database_url: str | None = None) -> dict:
    effective_url = (database_url or get_settings().database_url or "").strip()
    target = _safe_database_target(effective_url)
    try:
        async def _probe(conn):
            return await conn.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
        version = await _with_database(effective_url, _probe)
        if version:
            return {"ok": True, "message": f"AgentStudio DB pgvector 사용 가능 ({version})", "target": target}
        return {"ok": False, "message": "AgentStudio DB에 pgvector extension이 설치되지 않았습니다.", "target": target}
    except Exception as e:
        return _friendly_database_failure(e, target, prefix="AgentStudio DB pgvector 확인")


async def test_ollama() -> dict:
    s = get_settings()
    base_url = (s.ollama_base_url or "http://127.0.0.1:11434").rstrip("/")
    parsed = urlparse(base_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    exe = detect_ollama_exe()
    port_open = False
    http_status: int | None = None
    response_preview = ""

    try:
        port_open = await asyncio.to_thread(_can_connect, host, port)

        async with httpx.AsyncClient(timeout=httpx.Timeout(5.0, connect=3.0)) as client:
            res = await client.get(f"{base_url}/api/tags")
            http_status = res.status_code
            response_preview = (res.text or "")[:1000]
            res.raise_for_status()
            names = [m.get("name") for m in res.json().get("models", [])]

        return {
            "ok": True,
            "message": "Ollama 연결 성공",
            "models": names,
            "url": base_url,
            "port_open": True,
            "ollama_exe": str(exe) if exe else "",
        }
    except Exception as e:
        tb = traceback.format_exc()
        recommendation = _ollama_recommendation(exe=exe, port_open=port_open, error=e)
        lines = [
            f"timestamp={datetime.now().isoformat()}",
            "service=ollama",
            f"url={base_url}",
            f"host={host}",
            f"port={port}",
            f"port_open={port_open}",
            f"ollama_exe={str(exe) if exe else 'NOT_FOUND'}",
            f"http_status={http_status if http_status is not None else '-'}",
            f"error_type={type(e).__name__}",
            f"error={e}",
            f"recommendation={recommendation}",
            "",
            "response_preview:",
            response_preview or "-",
            "",
            "traceback:",
            tb,
        ]
        log_path = _write_connection_failure_log("ollama", lines)
        return {
            "ok": False,
            "message": f"Ollama 연결 실패: {e}",
            "error_type": type(e).__name__,
            "url": base_url,
            "host": host,
            "port": port,
            "port_open": port_open,
            "ollama_exe": str(exe) if exe else "",
            "recommendation": recommendation,
            "log_path": log_path,
        }


async def test_openai() -> dict:
    s = get_settings()
    if not s.openai_enabled:
        return {
            "ok": True,
            "skipped": True,
            "enabled": False,
            "message": "OpenAI 비사용 설정입니다. 외부 OpenAI API는 호출하지 않습니다. LLM 작업은 Ollama를 우선 사용하고, Codex가 켜져 있으면 지원 작업에서 Codex fallback을 사용할 수 있습니다.",
        }
    if not s.openai_api_key:
        return {"ok": False, "message": "OPENAI_API_KEY가 설정되지 않았습니다."}
    try:
        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=s.openai_api_key)
        models = await client.models.list()
        return {"ok": True, "message": "OpenAI API 연결 성공", "model_count": len(models.data)}
    except Exception as e:
        return {"ok": False, "message": f"OpenAI API 연결 실패: {e}"}


async def test_tavily() -> dict:
    s = get_settings()
    if not s.tavily_api_key:
        return {"ok": False, "message": "TAVILY_API_KEY가 설정되지 않았습니다."}
    try:
        from tavily import AsyncTavilyClient
        client = AsyncTavilyClient(api_key=s.tavily_api_key)
        result = await client.search(query="FastAPI", max_results=1)
        return {"ok": True, "message": "Tavily API 연결 성공", "result_count": len(result.get("results", []))}
    except Exception as e:
        return {"ok": False, "message": f"Tavily API 연결 실패: {e}"}


async def test_langsmith() -> dict:
    s = get_settings()
    if not s.langsmith_api_key:
        return {"ok": False, "message": "LANGSMITH_API_KEY가 설정되지 않았습니다."}
    try:
        from langsmith import Client
        client = Client(api_key=s.langsmith_api_key)
        list(client.list_projects(limit=1))
        return {"ok": True, "message": "LangSmith 연결 성공"}
    except Exception as e:
        return {"ok": False, "message": f"LangSmith 연결 실패: {e}"}


async def test_all() -> dict:
    return {
        "postgresql": await test_postgresql(),
        "pgvector": await test_pgvector(),
        "ollama": await test_ollama(),
        "openai": await test_openai(),
        "tavily": await test_tavily(),
        "langsmith": await test_langsmith(),
    }
