from __future__ import annotations

import asyncio
import socket
import traceback
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sqlalchemy import text

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


async def test_postgresql() -> dict:
    try:
        from app.core.database import engine
        async with engine.connect() as conn:
            value = await conn.scalar(text("SELECT 1"))
        return {"ok": value == 1, "message": "PostgreSQL 연결 성공"}
    except Exception as e:
        return {"ok": False, "message": f"PostgreSQL 연결 실패: {e}"}


async def test_pgvector() -> dict:
    try:
        from app.core.database import engine
        async with engine.connect() as conn:
            version = await conn.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
        if version:
            return {"ok": True, "message": f"pgvector 사용 가능 ({version})"}
        return {"ok": False, "message": "pgvector extension이 설치되지 않았습니다."}
    except Exception as e:
        return {"ok": False, "message": f"pgvector 확인 실패: {e}"}


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
