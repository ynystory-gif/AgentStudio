from __future__ import annotations

import asyncio
from typing import Any

from .daily_cache import read_daily, write_daily
from .huggingface_provider import collect_huggingface_trends
from .korean_translation import translate_categories_to_korean

_collection_lock = asyncio.Lock()


async def build_ai_trends_dashboard(*, force_refresh: bool = False) -> dict[str, Any]:
    # "새로고침"은 오늘 저장본을 다시 읽는 의미입니다.
    # force_refresh는 관리자/향후 명시적 강제 재수집용으로만 남겨 둡니다.
    if not force_refresh:
        cached = read_daily()
        if cached:
            result = dict(cached)
            result["cache"] = {"hit": True, "daily": True}
            return result

    async with _collection_lock:
        if not force_refresh:
            cached = read_daily()
            if cached:
                result = dict(cached)
                result["cache"] = {"hit": True, "daily": True}
                return result

        result = await collect_huggingface_trends()
        categories = {key: result.get(key) for key in ("models", "papers", "news", "spaces", "datasets")}
        try:
            result["translation"] = await translate_categories_to_korean(categories)
        except Exception as exc:
            # Collection remains useful even if the configured LLM is temporarily unavailable.
            # Do not cache an untranslated result as today's completed Korean dashboard: the next
            # request should retry translation instead of hiding the failure for the whole day.
            result["translation"] = {"status": "ERROR", "translated_items": 0, "message": str(exc)}
            result["cache"] = {"hit": False, "daily": False}
            return result
        write_daily(result)
        return result
