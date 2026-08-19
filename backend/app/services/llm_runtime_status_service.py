from __future__ import annotations

import asyncio
import socket
from urllib.parse import urlparse

import httpx

from app.core.config import get_settings


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
        return {
            "connected": False,
            "url": normalized,
            "port_open": False,
            "message": "Ollama 연결 안됨",
            "models": [],
        }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(2.0, connect=1.0)) as client:
            response = await client.get(f"{normalized}/api/tags")
            response.raise_for_status()
            models = [
                str(item.get("name") or "")
                for item in response.json().get("models", [])
                if item.get("name")
            ]
        return {
            "connected": True,
            "url": normalized,
            "port_open": True,
            "message": "Ollama 연결됨",
            "models": models,
        }
    except Exception as exc:
        return {
            "connected": False,
            "url": normalized,
            "port_open": True,
            "message": f"Ollama 응답 오류: {type(exc).__name__}",
            "models": [],
        }


def _provider_model(provider: str, *, openai_model: str, ollama_model: str) -> str:
    return ollama_model if provider.lower() == "ollama" else openai_model


async def get_llm_runtime_status() -> dict:
    settings = get_settings()
    local_provider = (settings.local_llm_provider or "ollama").lower()
    coding_provider = (settings.coding_llm_provider or "openai").lower()
    requirements_provider = (settings.requirements_llm_provider or "openai").lower()

    providers = {local_provider, coding_provider, requirements_provider}
    if providers == {"openai"}:
        mode = "openai"
    elif providers == {"ollama"}:
        mode = "ollama"
    else:
        mode = "auto"

    ollama = await _ollama_status(settings.ollama_base_url)
    openai_configured = bool((settings.openai_api_key or "").strip())

    routing = {
        "local": {
            "provider": local_provider,
            "model": _provider_model(
                local_provider,
                openai_model=settings.openai_model,
                ollama_model=settings.ollama_model,
            ),
        },
        "coding": {
            "provider": coding_provider,
            "model": _provider_model(
                coding_provider,
                openai_model=settings.openai_model,
                ollama_model=settings.ollama_model,
            ),
        },
        "requirements": {
            "provider": requirements_provider,
            "model": _provider_model(
                requirements_provider,
                openai_model=settings.openai_model,
                ollama_model=settings.ollama_model,
            ),
        },
    }

    primary = routing["coding"]
    return {
        "ok": True,
        "mode": mode,
        "primary_provider": primary["provider"],
        "primary_model": primary["model"],
        "routing": routing,
        "providers": {
            "openai": {
                "configured": openai_configured,
                "model": settings.openai_model,
                "status": "설정됨" if openai_configured else "API Key 미설정",
            },
            "ollama": {
                **ollama,
                "model": settings.ollama_model,
            },
        },
    }
