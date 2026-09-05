from __future__ import annotations

import asyncio
from typing import Any

from .daily_cache import read_daily, write_daily
from .huggingface_provider import collect_huggingface_trends
from .korean_translation import translate_categories_to_korean
from app.services.active_ollama_model_service import resolve_qwen_model_context

_collection_lock = asyncio.Lock()


async def build_ai_trends_dashboard(
    *,
    force_refresh: bool = False,
    member_id: str = "",
    project_root: str = "",
) -> dict[str, Any]:
    model_context = await resolve_qwen_model_context(
        member_id=member_id,
        project_root=project_root,
        force_refresh=force_refresh,
    )
    active_model = str(model_context.get("model") or "").strip()
    dataset_query = str(model_context.get("dataset_query") or "qwen").strip() or "qwen"
    cache_key = dataset_query.casefold()

    # Cache is model-family scoped so switching projects cannot leave a qwen3.5
    # dataset card visible while the selected project is configured for qwen3.8.
    if not force_refresh:
        cached = read_daily(cache_key)
        if cached:
            result = dict(cached)
            result["active_model"] = active_model
            result["dataset_query"] = dataset_query
            result["model_context"] = model_context
            result["cache"] = {"hit": True, "daily": True, "key": cache_key}
            return result

    async with _collection_lock:
        if not force_refresh:
            cached = read_daily(cache_key)
            if cached:
                result = dict(cached)
                result["active_model"] = active_model
                result["dataset_query"] = dataset_query
                result["model_context"] = model_context
                result["cache"] = {"hit": True, "daily": True, "key": cache_key}
                return result

        result = await collect_huggingface_trends(active_model=active_model, dataset_query=dataset_query)
        result["model_context"] = model_context
        categories = {key: result.get(key) for key in ("models", "papers", "news", "spaces", "datasets")}
        try:
            result["translation"] = await translate_categories_to_korean(categories)
        except Exception as exc:
            result["translation"] = {"status": "ERROR", "translated_items": 0, "message": str(exc)}
            result["cache"] = {"hit": False, "daily": False, "key": cache_key}
            return result
        write_daily(result, cache_key)
        result["cache"] = {"hit": False, "daily": True, "key": cache_key}
        return result
