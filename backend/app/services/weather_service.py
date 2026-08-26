from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
NOMINATIM_SEARCH_URL = "https://nominatim.openstreetmap.org/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_CACHE_VERSION = 2
GEOCODE_CACHE_DAYS = 30
_NOMINATIM_MIN_INTERVAL_SECONDS = 1.05
_nominatim_lock = asyncio.Lock()
_nominatim_last_request_at = 0.0
_cache_lock = asyncio.Lock()


@dataclass(frozen=True)
class WeatherLocation:
    name: str
    latitude: float
    longitude: float
    country: str = ""
    admin1: str = ""
    source: str = "configured"
    query: str = ""
    geocoder: str = ""


def _persistent_agentstudio_data_dir() -> Path:
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


def weather_cache_path() -> Path:
    path = _persistent_agentstudio_data_dir() / "cache" / "weather_today.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _today_key() -> str:
    return datetime.now().astimezone().date().isoformat()


def _read_cache() -> dict[str, Any]:
    path = weather_cache_path()
    if not path.exists():
        return {"version": WEATHER_CACHE_VERSION, "forecast": {}, "geocode": {}}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("weather cache root must be an object")
    except Exception:
        return {"version": WEATHER_CACHE_VERSION, "forecast": {}, "geocode": {}}

    payload.setdefault("version", WEATHER_CACHE_VERSION)
    payload.setdefault("forecast", {})
    payload.setdefault("geocode", {})
    return payload


def _write_cache(payload: dict[str, Any]) -> None:
    path = weather_cache_path()
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temp, path)


def _prune_cache(payload: dict[str, Any]) -> dict[str, Any]:
    today = _today_key()
    forecast = payload.get("forecast") or {}
    payload["forecast"] = {
        key: value
        for key, value in forecast.items()
        if isinstance(value, dict) and str(value.get("date") or "") == today
    }

    cutoff = datetime.now().astimezone() - timedelta(days=GEOCODE_CACHE_DAYS)
    geocode = payload.get("geocode") or {}
    kept: dict[str, Any] = {}
    for key, value in geocode.items():
        if not isinstance(value, dict):
            continue
        try:
            cached_at = datetime.fromisoformat(str(value.get("cached_at") or ""))
            if cached_at.tzinfo is None:
                cached_at = cached_at.replace(tzinfo=datetime.now().astimezone().tzinfo)
            if cached_at >= cutoff:
                kept[key] = value
        except Exception:
            continue
    payload["geocode"] = kept
    payload["version"] = WEATHER_CACHE_VERSION
    return payload


def _normalize_query(value: str) -> str:
    return " ".join(str(value or "").strip().split())


def _query_cache_key(value: str) -> str:
    return _normalize_query(value).casefold()


def _forecast_cache_key(location: WeatherLocation) -> str:
    return f"{round(float(location.latitude), 4):.4f}:{round(float(location.longitude), 4):.4f}"


def _weather_code_meta(code: int) -> tuple[str, str]:
    if code == 0:
        return "☀️", "맑음"
    if code in {1, 2}:
        return "🌤️", "대체로 맑음"
    if code == 3:
        return "☁️", "흐림"
    if code in {45, 48}:
        return "🌫️", "안개"
    if code in {51, 53, 55, 56, 57}:
        return "🌦️", "이슬비"
    if code in {61, 63, 65, 66, 67, 80, 81, 82}:
        return "🌧️", "비"
    if code in {71, 73, 75, 77, 85, 86}:
        return "🌨️", "눈"
    if code in {95, 96, 99}:
        return "⛈️", "뇌우"
    return "🌡️", "날씨"


def _location_display_name(location: WeatherLocation) -> str:
    # 사용자가 직접 입력한 주소/지역명은 카드 제목에서 그대로 알아볼 수 있게 우선합니다.
    if location.query:
        return location.query
    parts = [location.name]
    if location.admin1 and location.admin1 not in parts:
        parts.append(location.admin1)
    return " · ".join(x for x in parts if x)


def _location_from_cached_geocode(query: str, cached: dict[str, Any]) -> WeatherLocation | None:
    try:
        return WeatherLocation(
            name=str(cached.get("name") or query),
            latitude=float(cached["latitude"]),
            longitude=float(cached["longitude"]),
            country=str(cached.get("country") or ""),
            admin1=str(cached.get("admin1") or ""),
            source="configured",
            query=query,
            geocoder=str(cached.get("geocoder") or "cache"),
        )
    except Exception:
        return None


async def _cached_geocode(query: str) -> WeatherLocation | None:
    key = _query_cache_key(query)
    async with _cache_lock:
        payload = _prune_cache(_read_cache())
        cached = (payload.get("geocode") or {}).get(key)
    if not isinstance(cached, dict):
        return None
    return _location_from_cached_geocode(query, cached)


async def _store_geocode(query: str, location: WeatherLocation) -> None:
    key = _query_cache_key(query)
    async with _cache_lock:
        payload = _prune_cache(_read_cache())
        payload.setdefault("geocode", {})[key] = {
            "name": location.name,
            "latitude": location.latitude,
            "longitude": location.longitude,
            "country": location.country,
            "admin1": location.admin1,
            "geocoder": location.geocoder,
            "cached_at": datetime.now().astimezone().isoformat(),
        }
        _write_cache(payload)


async def _geocode_open_meteo(query: str) -> WeatherLocation | None:
    timeout = httpx.Timeout(8.0, connect=4.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(
            GEOCODING_URL,
            params={
                "name": query,
                "count": 1,
                "language": "ko",
                "format": "json",
            },
            headers={"User-Agent": "THEANOVA-AgentStudio/5.368"},
        )
        response.raise_for_status()
        payload = response.json()

    rows = payload.get("results") or []
    if not rows:
        return None
    row = rows[0]
    return WeatherLocation(
        name=str(row.get("name") or query),
        latitude=float(row["latitude"]),
        longitude=float(row["longitude"]),
        country=str(row.get("country") or ""),
        admin1=str(row.get("admin1") or ""),
        source="configured",
        query=query,
        geocoder="Open-Meteo",
    )


async def _geocode_nominatim(query: str) -> WeatherLocation | None:
    # Open-Meteo geocoder는 도시/지역 검색에 적합하고 상세 도로명 주소는 결과가 없을 수 있어
    # Nominatim free-form address 검색을 fallback으로 사용합니다. public service 보호를 위해
    # 요청 간격을 두고, 결과는 30일 로컬 캐시에 저장합니다.
    global _nominatim_last_request_at
    async with _nominatim_lock:
        elapsed = time.monotonic() - _nominatim_last_request_at
        if elapsed < _NOMINATIM_MIN_INTERVAL_SECONDS:
            await asyncio.sleep(_NOMINATIM_MIN_INTERVAL_SECONDS - elapsed)

        timeout = httpx.Timeout(10.0, connect=4.0)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(
                NOMINATIM_SEARCH_URL,
                params={
                    "q": query,
                    "format": "jsonv2",
                    "limit": 1,
                    "addressdetails": 1,
                    "accept-language": "ko",
                },
                headers={
                    "User-Agent": "THEANOVA-AgentStudio/5.368 (local desktop weather geocoding)",
                    "Accept-Language": "ko,en;q=0.8",
                },
            )
            _nominatim_last_request_at = time.monotonic()
            response.raise_for_status()
            rows = response.json()

    if not isinstance(rows, list) or not rows:
        return None
    row = rows[0]
    address = row.get("address") or {}
    admin1 = str(address.get("state") or address.get("province") or "")
    country = str(address.get("country") or "")
    short_name = str(
        address.get("road")
        or address.get("neighbourhood")
        or address.get("suburb")
        or address.get("city")
        or row.get("name")
        or query
    )
    return WeatherLocation(
        name=short_name,
        latitude=float(row["lat"]),
        longitude=float(row["lon"]),
        country=country,
        admin1=admin1,
        source="configured",
        query=query,
        geocoder="Nominatim",
    )


async def geocode_location(name: str) -> WeatherLocation | None:
    query = _normalize_query(name)
    if not query:
        return None

    cached = await _cached_geocode(query)
    if cached:
        return cached

    primary_error: Exception | None = None
    try:
        location = await _geocode_open_meteo(query)
        if location:
            await _store_geocode(query, location)
            return location
    except Exception as exc:
        primary_error = exc

    try:
        location = await _geocode_nominatim(query)
        if location:
            await _store_geocode(query, location)
            return location
    except Exception:
        if primary_error:
            raise primary_error
        raise

    return None


async def reverse_geocode_label(latitude: float, longitude: float) -> str:
    return "현재 위치"


async def _fetch_today_forecast_remote(location: WeatherLocation) -> dict[str, Any]:
    timeout = httpx.Timeout(10.0, connect=4.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        response = await client.get(
            FORECAST_URL,
            params={
                "latitude": location.latitude,
                "longitude": location.longitude,
                "hourly": "temperature_2m,weather_code,precipitation_probability",
                "daily": "weather_code,temperature_2m_max,temperature_2m_min",
                "forecast_days": 1,
                "timezone": "auto",
            },
            headers={"User-Agent": "THEANOVA-AgentStudio/5.368"},
        )
        response.raise_for_status()
        payload = response.json()

    hourly = payload.get("hourly") or {}
    times = list(hourly.get("time") or [])
    temperatures = list(hourly.get("temperature_2m") or [])
    codes = list(hourly.get("weather_code") or [])
    rain_probs = list(hourly.get("precipitation_probability") or [])

    by_hour: dict[int, int] = {}
    for index, value in enumerate(times):
        try:
            hour = int(str(value).split("T", 1)[1][:2])
        except Exception:
            continue
        by_hour[hour] = index

    periods = [
        ("morning", "아침", 8),
        ("lunch", "점심", 12),
        ("evening", "저녁", 18),
        ("night", "밤", 22),
    ]
    items: list[dict[str, Any]] = []
    for key, label, target_hour in periods:
        if not by_hour:
            continue
        nearest_hour = min(by_hour.keys(), key=lambda hour: abs(hour - target_hour))
        index = by_hour[nearest_hour]
        code = int(codes[index]) if index < len(codes) and codes[index] is not None else -1
        icon, condition = _weather_code_meta(code)
        temperature = temperatures[index] if index < len(temperatures) else None
        rain_probability = rain_probs[index] if index < len(rain_probs) else None
        items.append(
            {
                "key": key,
                "label": label,
                "hour": nearest_hour,
                "icon": icon,
                "condition": condition,
                "temperature": temperature,
                "precipitation_probability": rain_probability,
                "weather_code": code,
            }
        )

    daily = payload.get("daily") or {}
    max_values = list(daily.get("temperature_2m_max") or [])
    min_values = list(daily.get("temperature_2m_min") or [])
    daily_codes = list(daily.get("weather_code") or [])
    daily_code = int(daily_codes[0]) if daily_codes else -1
    daily_icon, daily_condition = _weather_code_meta(daily_code)

    return {
        "name": _location_display_name(location),
        "latitude": location.latitude,
        "longitude": location.longitude,
        "country": location.country,
        "admin1": location.admin1,
        "source": location.source,
        "query": location.query,
        "geocoder": location.geocoder,
        "timezone": payload.get("timezone") or "",
        "timezone_abbreviation": payload.get("timezone_abbreviation") or "",
        "date": (list(daily.get("time") or [""]) or [""])[0],
        "daily": {
            "icon": daily_icon,
            "condition": daily_condition,
            "temperature_max": max_values[0] if max_values else None,
            "temperature_min": min_values[0] if min_values else None,
        },
        "periods": items,
    }


async def fetch_today_forecast(
    location: WeatherLocation,
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    cache_key = _forecast_cache_key(location)
    today = _today_key()

    if not force_refresh:
        async with _cache_lock:
            payload = _prune_cache(_read_cache())
            cached = (payload.get("forecast") or {}).get(cache_key)
        if isinstance(cached, dict) and str(cached.get("date") or "") == today:
            result = dict(cached.get("data") or {})
            if result:
                # 같은 좌표라도 현재 설정의 표시 이름/source를 유지합니다.
                result["name"] = _location_display_name(location)
                result["source"] = location.source
                result["query"] = location.query
                result["geocoder"] = location.geocoder or result.get("geocoder", "")
                result["cache"] = {
                    "hit": True,
                    "cached_at": cached.get("cached_at") or "",
                    "date": today,
                }
                return result

    result = await _fetch_today_forecast_remote(location)
    cached_at = datetime.now().astimezone().isoformat()
    result["cache"] = {"hit": False, "cached_at": cached_at, "date": today}

    async with _cache_lock:
        payload = _prune_cache(_read_cache())
        payload.setdefault("forecast", {})[cache_key] = {
            "date": str(result.get("date") or today),
            "cached_at": cached_at,
            "data": result,
        }
        _write_cache(payload)
    return result


def weather_config() -> dict[str, Any]:
    settings = get_settings()
    extra_raw = str(settings.weather_extra_locations or "")
    # 세미콜론과 줄바꿈을 모두 지원합니다. 주소에 포함될 수 있는 쉼표는 구분자로 사용하지 않습니다.
    normalized_extra = extra_raw.replace("\r\n", ";").replace("\n", ";").replace("\r", ";")
    extras: list[str] = []
    seen: set[str] = set()
    for item in normalized_extra.split(";"):
        value = _normalize_query(item)
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        extras.append(value)
        if len(extras) >= 4:
            break

    return {
        "auto_location": bool(settings.weather_auto_location),
        "location": _normalize_query(settings.weather_location),
        "extra_locations": extras,
        "provider": "Open-Meteo",
        "cache_path": str(weather_cache_path()),
    }


async def build_weather_dashboard(
    latitude: float | None = None,
    longitude: float | None = None,
    *,
    force_refresh: bool = False,
) -> dict[str, Any]:
    config = weather_config()
    cards: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()

    async def append_location(location: WeatherLocation) -> None:
        key = _forecast_cache_key(location)
        if key in seen:
            return
        seen.add(key)
        try:
            cards.append(await fetch_today_forecast(location, force_refresh=force_refresh))
        except Exception as exc:
            errors.append(f"{_location_display_name(location)}: {exc}")

    if latitude is not None and longitude is not None:
        label = await reverse_geocode_label(latitude, longitude)
        await append_location(
            WeatherLocation(
                name=label,
                latitude=float(latitude),
                longitude=float(longitude),
                source="device",
                query=label,
                geocoder="device",
            )
        )

    configured_name = str(config.get("location") or "").strip()
    if configured_name:
        try:
            configured = await geocode_location(configured_name)
            if configured:
                await append_location(configured)
            else:
                errors.append(f"설정 지역을 찾을 수 없습니다: {configured_name}")
        except Exception as exc:
            errors.append(f"{configured_name}: {exc}")

    # 추가 지역은 기본 지역/현재 위치 성공 여부와 무관하게 각각 독립 조회합니다.
    for extra_name in config.get("extra_locations") or []:
        try:
            extra = await geocode_location(extra_name)
            if extra:
                await append_location(extra)
            else:
                errors.append(f"추가 지역을 찾을 수 없습니다: {extra_name}")
        except Exception as exc:
            errors.append(f"{extra_name}: {exc}")

    cache_hits = sum(1 for card in cards if bool((card.get("cache") or {}).get("hit")))
    return {
        "ok": bool(cards),
        "provider": "Open-Meteo",
        "auto_location": bool(config.get("auto_location")),
        "needs_device_location": bool(config.get("auto_location")) and latitude is None,
        "configured_location": configured_name,
        "extra_locations": config.get("extra_locations") or [],
        "locations": cards,
        "errors": errors,
        "cache": {
            "date": _today_key(),
            "hits": cache_hits,
            "total": len(cards),
            "all_cached": bool(cards) and cache_hits == len(cards),
            "path": str(weather_cache_path()),
        },
        "message": (
            "오늘 저장된 날씨 데이터를 표시했습니다."
            if cards and cache_hits == len(cards)
            else "오늘 날씨를 불러와 저장했습니다."
            if cards
            else "표시할 날씨 지역이 없습니다. 위치 권한을 허용하거나 설정에서 지역을 입력하세요."
        ),
    }
