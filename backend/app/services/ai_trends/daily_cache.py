from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

CACHE_VERSION = 5
SEOUL = ZoneInfo("Asia/Seoul")


def persistent_data_dir() -> Path:
    override = str(os.environ.get("THEANOVA_AGENTSTUDIO_DATA_DIR") or "").strip()
    if override:
        return Path(os.path.expanduser(override)).resolve()
    local_app_data = str(os.environ.get("LOCALAPPDATA") or "").strip()
    if local_app_data:
        return Path(local_app_data) / "THEANOVA" / "AgentStudio"
    app_data = str(os.environ.get("APPDATA") or "").strip()
    if app_data:
        return Path(app_data) / "THEANOVA" / "AgentStudio"
    return Path.home() / ".theanova" / "AgentStudio"


def _safe_cache_key(value: str) -> str:
    raw = str(value or "default").strip().casefold() or "default"
    safe = "".join(ch if ch.isalnum() or ch in {"-", "_", "."} else "_" for ch in raw)
    return safe[:80] or "default"


def cache_path(cache_key: str = "default") -> Path:
    path = persistent_data_dir() / "cache" / f"ai_trends_daily_{_safe_cache_key(cache_key)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def today_key() -> str:
    return datetime.now(SEOUL).date().isoformat()


def read_daily(cache_key: str = "default") -> dict[str, Any] | None:
    path = cache_path(cache_key)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    if int(payload.get("cache_version") or 0) != CACHE_VERSION:
        return None
    if str(payload.get("collection_date") or "") != today_key():
        return None
    data = payload.get("data")
    return data if isinstance(data, dict) else None


def write_daily(data: dict[str, Any], cache_key: str = "default") -> None:
    path = cache_path(cache_key)
    payload = {
        "cache_version": CACHE_VERSION,
        "collection_date": today_key(),
        "saved_at": datetime.now(SEOUL).isoformat(),
        "data": data,
    }
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temp, path)
