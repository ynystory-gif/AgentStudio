from __future__ import annotations

import asyncio
import socket
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings
from app.services.codex_app_server_service import codex_app_server_manager
from app.services.model_router import LLMTask, provider_candidates_for
from app.services.active_ollama_model_service import resolve_active_ollama_model


def _tcp_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.8):
            return True
    except OSError:
        return False


async def _ollama_status(base_url: str) -> dict:
    normalized = (base_url or "http://127.0.0.1:11434").rstrip("/")
    parsed = urlparse(normalized)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    port_open = await asyncio.to_thread(_tcp_open, host, port)

    if not port_open:
        return {"connected": False, "url": normalized, "port_open": False, "message": "Ollama 연결 안됨", "models": []}

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(2.0, connect=1.0)) as client:
            response = await client.get(f"{normalized}/api/tags")
            response.raise_for_status()
            models = [str(item.get("name") or "") for item in response.json().get("models", []) if item.get("name")]
        return {"connected": True, "url": normalized, "port_open": True, "message": "Ollama 연결됨", "models": models}
    except Exception as exc:
        return {"connected": False, "url": normalized, "port_open": True, "message": f"Ollama 응답 오류: {type(exc).__name__}", "models": []}


def _provider_model(provider: str, *, openai_model: str, ollama_model: str) -> str:
    name = provider.lower()
    if name == "ollama":
        return ollama_model
    if name == "openai":
        return openai_model
    if name == "codex":
        return "ChatGPT Codex"
    return ""


async def get_llm_runtime_status() -> dict:
    settings = get_settings()
    selected = await resolve_active_ollama_model()
    selected_ollama_model = str(selected.get("active_model") or "").strip()
    ollama = await _ollama_status(settings.ollama_base_url)
    openai_configured = bool((settings.openai_api_key or "").strip())
    codex_status = codex_app_server_manager.status()

    task_map = {
        "local": LLMTask.SIMPLE_QUESTION,
        "coding": LLMTask.CODE_GENERATION,
        "requirements": LLMTask.REQUIREMENTS_ANALYSIS,
        "workflow_design": LLMTask.WORKFLOW_DESIGN,
        "database_design": LLMTask.DATABASE_SCHEMA_DESIGN,
        "multi_file_change": LLMTask.MULTI_FILE_CODE_CHANGE,
        "debugging": LLMTask.EXECUTION_DEBUG_REPAIR,
    }
    routing: dict[str, dict] = {}
    for label, task in task_map.items():
        candidates = provider_candidates_for(task)
        primary = candidates[0]
        routing[label] = {
            "provider": primary,
            "model": _provider_model(primary, openai_model=settings.openai_model, ollama_model=selected_ollama_model),
            "candidates": candidates,
        }

    strategy = (settings.ai_provider_strategy or "ollama_first").lower()
    if strategy == "ollama_first":
        mode = "auto"
    else:
        configured_local = (settings.local_llm_provider or "auto").lower()
        configured_coding = (settings.coding_llm_provider or "auto").lower()
        configured_requirements = (settings.requirements_llm_provider or "auto").lower()
        if configured_coding == "codex" and configured_requirements == "codex":
            mode = "codex"
        elif configured_local == configured_coding == configured_requirements and configured_local in {"ollama", "openai"}:
            mode = configured_local
        else:
            mode = "auto"

    primary = routing["coding"]
    return {
        "ok": True,
        "mode": mode,
        "strategy": strategy,
        "openai_enabled": bool(settings.openai_enabled),
        "codex_enabled": bool(settings.codex_enabled),
        "local_only": not settings.openai_enabled and not settings.codex_enabled,
        "primary_provider": primary["provider"],
        "primary_model": primary["model"],
        "routing": routing,
        "providers": {
            "openai": {
                "enabled": bool(settings.openai_enabled),
                "configured": openai_configured,
                "model": settings.openai_model,
                "status": "비사용" if not settings.openai_enabled else ("설정됨" if openai_configured else "API Key 미설정"),
            },
            "ollama": {**ollama, "enabled": True, "model": selected_ollama_model, "model_resolution": selected},
            "codex": {
                "enabled": bool(settings.codex_enabled),
                "installed": bool(codex_status.get("installed")),
                "running": bool(codex_status.get("running")),
                "initialized": bool(codex_status.get("initialized")),
                "connected": bool(codex_status.get("account")),
                "account": codex_status.get("account"),
                "version": codex_status.get("version") or "",
                "status": (
                    "비사용"
                    if not settings.codex_enabled
                    else ("ChatGPT 연결됨" if codex_status.get("account") else ("Codex 준비됨 · 로그인 필요" if codex_status.get("initialized") else "Codex 시작 필요"))
                ),
            },
        },
    }
