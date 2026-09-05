from __future__ import annotations

"""Single source of truth for the Ollama model used by AgentStudio requests.

Priority policy (v5.602):
1. ``theanova-learn:latest`` when it is applied to the current PC.
2. Explicitly configured Ollama/Qwen model (existing qwen3.5 settings are preserved).
3. Current recommended Qwen model for new/default configuration.
4. Another installed non-embedding model only as a last-resort fallback.

The weight fine-tuning pipeline may still keep its explicit Qwen3.5 compatibility
base. Runtime recommendation and weight-training compatibility are intentionally
separate concerns.
"""

import os
import time
from pathlib import Path

import httpx
from sqlalchemy import select

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.machine_identity import current_pc_name
from app.models.learning_entities import LlmLearningPcApplication
from app.models.account_setting_entities import AccountProjectSetting, AccountSettingProfile
from app.services.account_setting_service import normalize_project_key
from app.services.ollama_model_manager_service import LATEST_RECOMMENDED_MODEL, get_recommended_model_status, qwen_model_metadata

LEARNED_MODEL_NAME = "theanova-learn:latest"
BASE_MODEL_NAME = LATEST_RECOMMENDED_MODEL
LEGACY_MODEL_NAMES = {
    "qwen2.5:7b",
    "qwen2.5:3b",
    "qwen2.5:1.5b",
}

_CACHE: dict = {}
_CACHE_AT = 0.0
_CACHE_TTL_SECONDS = 15.0


def _normalized(value: object) -> str:
    return str(value or "").strip()


def _key(value: object) -> str:
    return _normalized(value).casefold()


def _backend_env_model() -> str:
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return ""
    try:
        for raw in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in raw:
                continue
            name, value = raw.split("=", 1)
            if name.strip().upper() == "OLLAMA_MODEL":
                return value.strip()
    except Exception:
        return ""
    return ""


def _is_legacy(model: str) -> bool:
    return _key(model) in LEGACY_MODEL_NAMES


def _is_usable_chat_model(model: str) -> bool:
    lowered = _key(model)
    if not lowered:
        return False
    if _is_legacy(model):
        return False
    if lowered.startswith("theanova-learn-") and lowered != LEARNED_MODEL_NAME:
        return False
    if any(token in lowered for token in ("embed", "embedding", "nomic-embed", "bge-", "e5-")):
        return False
    return True


def current_runtime_ollama_model() -> str:
    """Return the model name that synchronous request builders must use.

    Startup synchronizes the DB/application state into ``OLLAMA_MODEL``. Reading
    backend/.env before inherited process state also prevents a stale Windows
    parent environment from resurrecting an old qwen2.5 model after restart.
    """
    candidates = (
        _backend_env_model(),
        os.environ.get("OLLAMA_MODEL", ""),
        getattr(get_settings(), "ollama_model", ""),
    )
    for raw in candidates:
        model = _normalized(raw)
        if model and not _is_legacy(model):
            return model
    return BASE_MODEL_NAME


async def _has_applied_learned_model() -> bool:
    try:
        async with SessionLocal() as session:
            rows = (
                await session.execute(
                    select(LlmLearningPcApplication).where(
                        LlmLearningPcApplication.pc_name == current_pc_name(),
                        LlmLearningPcApplication.model_name == LEARNED_MODEL_NAME,
                        LlmLearningPcApplication.enabled == True,
                        LlmLearningPcApplication.installed == True,
                    )
                )
            ).scalars().all()
        return any(str(row.status or "").strip().lower() in {"applied", "deployed", "completed"} for row in rows)
    except Exception:
        return False


async def _installed_models(base_url: str) -> tuple[list[str], bool]:
    normalized = str(base_url or "http://127.0.0.1:11434").rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3.0, connect=1.2)) as client:
            response = await client.get(f"{normalized}/api/tags")
            response.raise_for_status()
            names = [
                _normalized(item.get("name"))
                for item in list(response.json().get("models") or [])
                if _normalized(item.get("name"))
            ]
        return names, True
    except Exception:
        return [], False


def _first_matching(installed: list[str], wanted: str) -> str:
    target = _key(wanted)
    for name in installed:
        if _key(name) == target:
            return name
    return ""


async def resolve_active_ollama_model(*, force_refresh: bool = False, persist: bool = False) -> dict:
    """Resolve and optionally persist the current PC's single active Ollama model."""
    global _CACHE, _CACHE_AT
    now = time.monotonic()
    if not force_refresh and _CACHE and now - _CACHE_AT < _CACHE_TTL_SECONDS:
        cached = dict(_CACHE)
        cached["cache_hit"] = True
        return cached

    settings = get_settings()
    manager_status = await get_recommended_model_status(force_refresh=force_refresh)
    configured = _normalized(manager_status.get("current_model")) or current_runtime_ollama_model()
    learned_applied = await _has_applied_learned_model()
    installed, ollama_reachable = await _installed_models(str(settings.ollama_base_url or ""))

    learned_installed = _first_matching(installed, LEARNED_MODEL_NAME)
    base_installed = _first_matching(installed, BASE_MODEL_NAME)
    configured_installed = _first_matching(installed, configured)

    selected = ""
    reason = ""

    # Applied/current learned model wins. When Ollama is temporarily offline, the
    # persisted application state is still authoritative and must not regress.
    if learned_applied and (learned_installed or not ollama_reachable):
        selected = learned_installed or LEARNED_MODEL_NAME
        reason = "current_pc_learned_model"
    elif _key(configured) == LEARNED_MODEL_NAME and (learned_installed or not ollama_reachable):
        selected = learned_installed or LEARNED_MODEL_NAME
        reason = "configured_learned_model"
    elif configured_installed and _is_usable_chat_model(configured_installed):
        selected = configured_installed
        reason = "configured_installed_model"
    elif base_installed:
        selected = base_installed
        reason = "recommended_base_model"
    else:
        selected = next((name for name in installed if _is_usable_chat_model(name)), "")
        if selected:
            reason = "installed_fallback_model"

    if not selected:
        # Ollama may be stopped during startup. Never resurrect qwen2.5 just
        # because the server cannot currently answer /api/tags.
        if configured and not _is_legacy(configured):
            selected = configured
            reason = "configured_offline_model"
        else:
            selected = BASE_MODEL_NAME
            reason = "recommended_base_fallback"

    previous_runtime = _normalized(os.environ.get("OLLAMA_MODEL"))
    os.environ["OLLAMA_MODEL"] = selected
    get_settings.cache_clear()

    persisted = False
    if persist and selected and _key(configured) != _key(selected):
        # Lazy import avoids a module cycle while keeping DB + backend/.env +
        # process environment aligned to the same resolved model.
        from app.services.ollama_model_manager_service import persist_current_ollama_model
        await persist_current_ollama_model(selected, str(manager_status.get("common_models_root") or ""))
        persisted = True

    result = {
        "ok": True,
        "active_model": selected,
        "base_model": BASE_MODEL_NAME,
        "learned_model": LEARNED_MODEL_NAME,
        "learned_applied": learned_applied,
        "ollama_reachable": ollama_reachable,
        "installed_models": installed,
        "configured_model": configured,
        "previous_runtime_model": previous_runtime,
        "reason": reason,
        "persisted": persisted,
        "cache_hit": False,
        "fine_tuning_required_for_combined_runtime": False,
        "current_learning_mode": "ollama_base_plus_cumulative_system_prompt",
    }
    _CACHE = dict(result)
    _CACHE_AT = now
    return result


_QWEN_VALUE_KEYS = (
    "qwen_model",
    "ollama_model",
    "model_name",
    "model",
    "default_model",
    "selected_model",
)


def _is_qwen_family_model(value: object) -> bool:
    text = _normalized(value).casefold()
    if not text or any(token in text for token in ("embed", "embedding")):
        return False
    tail = text.rsplit("/", 1)[-1]
    return tail.startswith("qwen")


def _extract_qwen_model(value: object, path: str = "") -> str:
    if isinstance(value, dict):
        lowered = {str(key).casefold(): item for key, item in value.items()}
        for key in _QWEN_VALUE_KEYS:
            candidate = lowered.get(key)
            if isinstance(candidate, str) and _is_qwen_family_model(candidate):
                return _normalized(candidate)
        for key, item in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            if "embed" in child_path.casefold():
                continue
            found = _extract_qwen_model(item, child_path)
            if found:
                return found
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found = _extract_qwen_model(item, f"{path}[{index}]")
            if found:
                return found
    elif isinstance(value, str) and _is_qwen_family_model(value) and "embed" not in path.casefold():
        return _normalized(value)
    return ""


async def _project_qwen_model(member_id: str, project_root: str) -> tuple[str, str]:
    member = _normalized(member_id)
    root = _normalized(project_root)
    if not member or not root:
        return "", ""
    key = normalize_project_key(root)
    preferred_groups = ("LLM_MODEL", "MODEL", "RUNTIME", "EXECUTION_ENVIRONMENT", "AGENT_DESIGN")
    try:
        async with SessionLocal() as session:
            rows = (
                await session.execute(
                    select(AccountProjectSetting).where(
                        AccountProjectSetting.member_id == member,
                        AccountProjectSetting.project_key == key,
                    )
                )
            ).scalars().all()
    except Exception:
        return "", ""
    ordered = sorted(
        rows,
        key=lambda row: preferred_groups.index(str(row.setting_group or "").upper())
        if str(row.setting_group or "").upper() in preferred_groups
        else len(preferred_groups),
    )
    for row in ordered:
        model = _extract_qwen_model(row.value_json or {})
        if model:
            return model, f"project:{row.setting_group}/{row.setting_key}"
    return "", ""


async def _account_qwen_model(member_id: str) -> tuple[str, str]:
    member = _normalized(member_id)
    if not member:
        return "", ""
    try:
        async with SessionLocal() as session:
            rows = (
                await session.execute(
                    select(AccountSettingProfile)
                    .where(
                        AccountSettingProfile.member_id == member,
                        AccountSettingProfile.is_default == True,
                    )
                    .order_by(AccountSettingProfile.updated_at.desc())
                )
            ).scalars().all()
    except Exception:
        return "", ""
    preferred = [row for row in rows if str(row.setting_group or "").upper() in {"LLM_MODEL", "MODEL", "RUNTIME"}]
    for row in preferred + [row for row in rows if row not in preferred]:
        model = _extract_qwen_model(row.value_json or {})
        if model:
            return model, f"account:{row.setting_group}/{row.profile_name}"
    return "", ""


async def _learned_model_base_qwen() -> str:
    try:
        async with SessionLocal() as session:
            rows = (
                await session.execute(
                    select(LlmLearningPcApplication)
                    .where(
                        LlmLearningPcApplication.pc_name == current_pc_name(),
                        LlmLearningPcApplication.model_name == LEARNED_MODEL_NAME,
                        LlmLearningPcApplication.enabled == True,
                    )
                    .order_by(LlmLearningPcApplication.updated_at.desc())
                )
            ).scalars().all()
        for row in rows:
            candidate = _normalized(getattr(row, "base_model", ""))
            if _is_qwen_family_model(candidate):
                return candidate
    except Exception:
        pass
    return ""


async def resolve_qwen_model_context(
    *,
    member_id: str = "",
    project_root: str = "",
    force_refresh: bool = False,
) -> dict:
    """Resolve the Qwen model shown by project-aware UI surfaces.

    Display priority follows the product rule: project setting -> account/default
    setting -> current AgentStudio runtime/default -> installed Qwen fallback.
    Existing qwen3.5 project/account settings are never rewritten to qwen3.8.
    """
    manager_status = await get_recommended_model_status(force_refresh=force_refresh)
    project_model, project_source = await _project_qwen_model(member_id, project_root)
    account_model, account_source = await _account_qwen_model(member_id)
    runtime_model = current_runtime_ollama_model()
    source = ""
    selected = ""

    if project_model:
        selected, source = project_model, project_source
    elif account_model:
        selected, source = account_model, account_source
    elif _is_qwen_family_model(runtime_model):
        selected, source = runtime_model, "runtime:OLLAMA_MODEL"
    elif _key(runtime_model) == LEARNED_MODEL_NAME:
        learned_base = await _learned_model_base_qwen()
        if learned_base:
            selected, source = learned_base, "runtime:learned_base_model"
    if not selected:
        selected, source = LATEST_RECOMMENDED_MODEL, "agentstudio:recommended_default"

    installed_models = [str(item or "").strip() for item in list(manager_status.get("installed_models") or []) if str(item or "").strip()]
    if not _is_qwen_family_model(selected):
        installed_qwen = next((name for name in installed_models if _is_qwen_family_model(name)), "")
        if installed_qwen:
            selected, source = installed_qwen, "ollama:installed_fallback"

    metadata = qwen_model_metadata(selected)
    dataset_query = selected.split(":", 1)[0].rsplit("/", 1)[-1].strip() if selected else "qwen"
    installed = any(_key(name) == _key(selected) for name in installed_models)
    return {
        "ok": True,
        "provider": "ollama",
        "family": "qwen",
        "model": selected,
        "source": source,
        "dataset_query": dataset_query or "qwen",
        "recommended_model": LATEST_RECOMMENDED_MODEL,
        "recommended_model_info": qwen_model_metadata(LATEST_RECOMMENDED_MODEL),
        "current_runtime_model": runtime_model,
        "installed": installed,
        "installed_models": installed_models,
        **metadata,
    }


async def sync_active_ollama_model() -> dict:
    """Synchronize DB/application state, backend/.env and request runtime."""
    return await resolve_active_ollama_model(force_refresh=True, persist=True)


def invalidate_active_ollama_model_cache() -> None:
    global _CACHE, _CACHE_AT
    _CACHE = {}
    _CACHE_AT = 0.0
