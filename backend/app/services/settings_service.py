from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from datetime import datetime
import platform

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.entities import AppSetting, AgentStudioMachine, Project
from app.core.machine_identity import (
    current_pc_name,
    ensure_pc_name_env,
    detect_system_pc_name,
    set_pc_name_env,
    validate_pc_name,
    pending_pc_name,
    set_pending_pc_name_env,
    clear_pending_pc_name_env,
)


ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
ENV_EXAMPLE_PATH = Path(__file__).resolve().parents[2] / ".env.example"

# DB 연결 이전에도 필요한 최소 bootstrap 설정만 .env에 유지합니다.
DB_CONNECTION_ENV_ONLY_KEYS = {
    "DATABASE_URL",
    "LANGGRAPH_DATABASE_URL",
}

BOOTSTRAP_KEYS = {
    "AGENTSTUDIO_PC_NAME",
    "AGENTSTUDIO_SYSTEM_HOST_NAME",
    "DATABASE_URL",
    "LANGGRAPH_DATABASE_URL",
    "POSTGRESQL18_ROOT",
    "AGENTSTUDIO_BACKEND_PORT",
    "AGENTSTUDIO_FRONTEND_PORT",
    "OLLAMA_AUTO_START",
}

SETTING_KEYS = [
    "POSTGRESQL18_ROOT",
    "AGENTSTUDIO_BACKEND_PORT",
    "AGENTSTUDIO_FRONTEND_PORT",
    "DATABASE_URL",
    "LANGGRAPH_DATABASE_URL",
    "DEFAULT_PROJECT_ROOT",
    "DEFAULT_CACHE_ROOT",
    "DEFAULT_TEMP_ROOT",
    "DEFAULT_OUTPUT_ROOT",
    "COMMON_MODELS_ROOT",
    "OPENAI_ENABLED",
    "CODEX_ENABLED",
    "AI_PROVIDER_STRATEGY",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_EMBEDDING_MODEL",
    "OLLAMA_BASE_URL",
    "OLLAMA_MODEL",
    "OLLAMA_EMBEDDING_MODEL",
    "OLLAMA_AUTO_START",
    "LOCAL_LLM_PROVIDER",
    "CODING_LLM_PROVIDER",
    "REQUIREMENTS_LLM_PROVIDER",
    "MEMORY_EMBEDDING_PROVIDER",
    "TAVILY_API_KEY",
    "LANGSMITH_TRACING",
    "LANGSMITH_API_KEY",
    "LANGSMITH_PROJECT",
    "ALLOWED_PROJECT_ROOTS",
    "MAX_COMMAND_SECONDS",
    "AUTO_APPROVE_RISK_LEVEL",
    "MAX_DEBUG_ITERATIONS",
    "PROJECT_ANALYZER_MAX_FILES",
    "MCP_DEFAULT_TIMEOUT_SECONDS",
    "MCP_REGISTRY_REFRESH_SECONDS",
    "SANDBOX_ROOT",
    "WEATHER_AUTO_LOCATION",
    "WEATHER_LOCATION",
    "WEATHER_EXTRA_LOCATIONS",
]

SECRET_KEYS = {
    "OPENAI_API_KEY",
    "TAVILY_API_KEY",
    "LANGSMITH_API_KEY",
}

LOCAL_PENDING_SETTINGS_KEY = "AGENTSTUDIO_SETTINGS_PENDING"

DEFAULT_SETTING_VALUES = {
    "OPENAI_ENABLED": "true",
    "CODEX_ENABLED": "false",
    "AI_PROVIDER_STRATEGY": "ollama_first",
    "LOCAL_LLM_PROVIDER": "auto",
    "CODING_LLM_PROVIDER": "auto",
    "REQUIREMENTS_LLM_PROVIDER": "auto",
    "MEMORY_EMBEDDING_PROVIDER": "ollama",
    "AGENTSTUDIO_BACKEND_PORT": "8000",
    "AGENTSTUDIO_FRONTEND_PORT": "5173",
    "OLLAMA_AUTO_START": "true",
    "WEATHER_AUTO_LOCATION": "true",
}


def _normalize_database_driver(value: str) -> str:
    if value.startswith("postgresql+asyncpg://"):
        return value.replace(
            "postgresql+asyncpg://",
            "postgresql+psycopg://",
            1,
        )
    return value


def _parse_env_lines(lines: list[str]) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def _read_actual_env_lines() -> list[str]:
    if ENV_PATH.exists():
        return ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    if ENV_EXAMPLE_PATH.exists():
        return ENV_EXAMPLE_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    return []


def read_env_dict() -> dict[str, str]:
    # 신규 clone에서 .env가 일부 키만 가진 경우에도 .env.example의 기본값을
    # 화면에 정상 표시하되 실제 .env 값이 항상 우선합니다.
    data: dict[str, str] = {}
    if ENV_EXAMPLE_PATH.exists():
        data.update(_parse_env_lines(ENV_EXAMPLE_PATH.read_text(encoding="utf-8", errors="replace").splitlines()))
    if ENV_PATH.exists():
        data.update(_parse_env_lines(ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines()))
    return data


def read_actual_env_dict() -> dict[str, str]:
    """backend/.env에 실제로 저장된 값만 반환합니다 (.env.example 제외)."""
    if not ENV_PATH.exists():
        return {}
    return _parse_env_lines(
        ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    )


def get_database_env_settings() -> dict[str, str]:
    """DB 연결 bootstrap 값은 오직 backend/.env를 source of truth로 사용합니다."""
    actual = read_actual_env_dict()
    merged = read_env_dict()
    return {
        key: actual.get(key, merged.get(key, DEFAULT_SETTING_VALUES.get(key, "")))
        for key in DB_CONNECTION_ENV_ONLY_KEYS
    }


def _write_env_values(values: dict[str, str]) -> None:
    """PC 로컬 .env를 안전한 오프라인 fallback cache로 유지합니다."""
    existing_lines = _read_actual_env_lines()
    update_values = {str(k): str(v) for k, v in values.items()}
    seen: set[str] = set()
    output: list[str] = []

    for line in existing_lines:
        if "=" in line and not line.lstrip().startswith("#"):
            key = line.split("=", 1)[0].strip()
            if key in update_values:
                output.append(f"{key}={update_values[key]}")
                seen.add(key)
                continue
        output.append(line)

    missing = [key for key in update_values if key not in seen]
    if missing:
        if output and output[-1].strip():
            output.append("")
        output.append("# AgentStudio local settings fallback cache")
        for key in missing:
            output.append(f"{key}={update_values[key]}")

    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    content = "\n".join(output).rstrip() + "\n"
    temp_path = ENV_PATH.with_suffix(ENV_PATH.suffix + ".tmp")
    temp_path.write_text(content, encoding="utf-8")
    temp_path.replace(ENV_PATH)

    # 실제 파일에 기록됐는지 즉시 검증합니다.
    persisted = _parse_env_lines(ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines())
    missing_or_mismatch = [
        key for key, value in update_values.items()
        if persisted.get(key) != value
    ]
    if missing_or_mismatch:
        raise OSError(
            "설정 파일 저장 검증에 실패했습니다: " + ", ".join(missing_or_mismatch)
        )




def write_env_values(values: dict[str, str]) -> None:
    """Public wrapper for local bootstrap/runtime settings that must stay in backend/.env."""
    _write_env_values(values)

def _write_bootstrap_values(values: dict[str, str]) -> None:
    filtered = {key: value for key, value in values.items() if key in BOOTSTRAP_KEYS}
    if filtered:
        _write_env_values(filtered)


def _pending_setting_keys() -> set[str]:
    actual = {}
    if ENV_PATH.exists():
        actual = _parse_env_lines(ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines())
    raw = str(actual.get(LOCAL_PENDING_SETTINGS_KEY, "") or "")
    return {key for key in raw.split(";") if key in SETTING_KEYS and key not in BOOTSTRAP_KEYS}


def _write_pending_setting_keys(keys: set[str]) -> None:
    _write_env_values({LOCAL_PENDING_SETTINGS_KEY: ";".join(sorted(keys))})


def _mark_pending_settings(keys: set[str]) -> None:
    pending = _pending_setting_keys()
    pending.update({key for key in keys if key in SETTING_KEYS and key not in BOOTSTRAP_KEYS})
    _write_pending_setting_keys(pending)


def _clear_pending_settings(keys: set[str]) -> None:
    pending = _pending_setting_keys()
    pending.difference_update(keys)
    _write_pending_setting_keys(pending)


async def _read_db_settings() -> dict[str, str]:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(AppSetting).where(
                    AppSetting.pc_name == pc_name,
                    AppSetting.key.in_([key for key in SETTING_KEYS if key not in DB_CONNECTION_ENV_ONLY_KEYS]),
                )
            )
        ).scalars().all()

    return {row.key: row.value for row in rows}


async def register_current_machine() -> dict:
    """Register/update this AgentStudio PC profile in the shared database."""
    identity = ensure_pc_name_env()
    pc_name = identity["pc_name"]
    system_host_name = identity.get("system_host_name") or detect_system_pc_name()
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(AgentStudioMachine).where(AgentStudioMachine.pc_name == pc_name)
            )
        ).scalar_one_or_none()
        now = datetime.utcnow()
        if row is None:
            row = AgentStudioMachine(
                pc_name=pc_name,
                host_name=system_host_name,
                os_name=platform.platform(),
                created_at=now,
                last_seen_at=now,
            )
            session.add(row)
        else:
            # pc_name is the user-managed unique alias; host_name is diagnostic.
            row.host_name = system_host_name
            row.os_name = platform.platform()
            row.last_seen_at = now
        await session.commit()
    return {
        "ok": True,
        "pc_name": pc_name,
        "system_host_name": system_host_name,
        "env_path": identity.get("env_path", ""),
        "env_updated": bool(identity.get("changed")),
    }


async def rename_current_machine(new_pc_name: str) -> dict:
    """
    Rename the current shared-DB PC scope.

    DB가 오프라인이면 유니크 여부를 확인할 수 없으므로 활성 이름을 바꾸지 않고
    요청 이름을 .env의 PENDING 값으로 보존합니다. DB 복구 후 자동 검증합니다.
    """
    new_name = validate_pc_name(new_pc_name)
    old_name = current_pc_name()
    system_host_name = detect_system_pc_name()

    if new_name == old_name:
        identity = set_pc_name_env(new_name)
        clear_pending_pc_name_env()
        db_synced = True
        db_error = ""
        try:
            await register_current_machine()
        except Exception as exc:
            db_synced = False
            db_error = str(exc)
        settings = await get_editable_settings()
        return {
            "ok": True,
            "changed": False,
            "pc_name": new_name,
            "system_host_name": system_host_name,
            "db_synced": db_synced,
            "db_error": db_error,
            "message": (
                f"PC 이름 [{new_name}]을 유지합니다."
                if db_synced else
                f"PC 이름 [{new_name}]은 .env에 유지했습니다. 공용 DB 연결 후 유니크 등록을 다시 확인합니다."
            ),
            "settings": settings,
        }

    try:
        async with SessionLocal() as session:
            duplicate_machine = (
                await session.execute(
                    select(AgentStudioMachine).where(AgentStudioMachine.pc_name == new_name)
                )
            ).scalar_one_or_none()
            duplicate_setting = (
                await session.execute(
                    select(AppSetting.id).where(AppSetting.pc_name == new_name).limit(1)
                )
            ).first()
            duplicate_project = (
                await session.execute(
                    select(Project.id).where(Project.pc_name == new_name).limit(1)
                )
            ).first()
            if duplicate_machine is not None or duplicate_setting is not None or duplicate_project is not None:
                raise ValueError(
                    f"PC 이름 [{new_name}]은(는) 이미 공용 DB에서 사용 중입니다. 다른 유니크한 이름을 입력하세요."
                )

            source_machine = (
                await session.execute(
                    select(AgentStudioMachine).where(AgentStudioMachine.pc_name == old_name)
                )
            ).scalar_one_or_none()
            settings_rows = (
                await session.execute(
                    select(AppSetting).where(AppSetting.pc_name == old_name)
                )
            ).scalars().all()
            project_rows = (
                await session.execute(
                    select(Project).where(Project.pc_name == old_name)
                )
            ).scalars().all()

            if source_machine is None:
                source_machine = AgentStudioMachine(
                    pc_name=new_name,
                    host_name=system_host_name,
                    os_name=platform.platform(),
                    created_at=datetime.utcnow(),
                    last_seen_at=datetime.utcnow(),
                )
                session.add(source_machine)
            else:
                source_machine.pc_name = new_name
                source_machine.host_name = system_host_name
                source_machine.os_name = platform.platform()
                source_machine.last_seen_at = datetime.utcnow()

            for row in settings_rows:
                row.pc_name = new_name
            for row in project_rows:
                row.pc_name = new_name

            await session.commit()

        set_pc_name_env(new_name)
        clear_pending_pc_name_env()
    except ValueError:
        raise
    except Exception as exc:
        set_pending_pc_name_env(new_name)
        settings = await get_editable_settings()
        settings.setdefault("_machine", {})["pending_pc_name"] = new_name
        return {
            "ok": True,
            "changed": False,
            "pending": True,
            "pc_name": old_name,
            "pending_pc_name": new_name,
            "system_host_name": system_host_name,
            "db_synced": False,
            "db_error": str(exc),
            "message": (
                f"공용 DB에 연결할 수 없어 PC 이름 [{new_name}]의 유니크 검증을 보류했습니다. "
                ".env에 변경 요청을 안전하게 저장했으며 DB 연결이 복구되면 자동 검증 후 적용합니다."
            ),
            "settings": settings,
        }

    return {
        "ok": True,
        "changed": True,
        "old_pc_name": old_name,
        "pc_name": new_name,
        "system_host_name": system_host_name,
        "db_synced": True,
        "message": (
            f"PC 이름을 [{old_name}] → [{new_name}]으로 변경했습니다. "
            "공용 DB의 기존 PC별 app_settings도 새 이름으로 함께 이동했습니다."
        ),
        "settings": await get_editable_settings(),
    }


async def resolve_pending_machine_name() -> dict:
    requested = pending_pc_name()
    if not requested:
        return {"ok": True, "pending": False}
    try:
        result = await rename_current_machine(requested)
        return result
    except ValueError as exc:
        # 중복이면 사용자가 다른 이름을 선택할 수 있도록 pending 값을 유지합니다.
        return {"ok": False, "pending": True, "pending_pc_name": requested, "message": str(exc)}


async def migrate_env_settings_to_db() -> dict:
    """
    .env 로컬 fallback 값을 공용 DB와 동기화합니다.

    - DB에 없는 값은 최초 PC 설정으로 등록
    - DB 오프라인 중 사용자가 수정해 PENDING 표시된 값은 기존 DB 값도 갱신
    - 단순 캐시 값은 DB의 기존 값을 덮어쓰지 않음
    """
    env_data = read_env_dict()
    pending = _pending_setting_keys()

    async with SessionLocal() as session:
        pc_name = current_pc_name()
        # 구버전에서 잘못 저장됐을 수 있는 DB 연결 bootstrap 행은 제거합니다.
        # 이후 DATABASE_URL/LANGGRAPH_DATABASE_URL은 backend/.env만 source of truth입니다.
        await session.execute(
            delete(AppSetting).where(
                AppSetting.key.in_(list(DB_CONNECTION_ENV_ONLY_KEYS))
            )
        )
        existing_rows = (
            await session.execute(
                select(AppSetting).where(AppSetting.pc_name == pc_name)
            )
        ).scalars().all()
        existing = {row.key: row for row in existing_rows}
        inserted = 0
        updated = 0
        synced_pending: set[str] = set()

        for key in SETTING_KEYS:
            if key in BOOTSTRAP_KEYS or key not in env_data:
                continue
            value = env_data.get(key, "")
            row = existing.get(key)
            if row is None:
                session.add(
                    AppSetting(
                        pc_name=pc_name,
                        key=key,
                        value=value,
                        is_secret=key in SECRET_KEYS,
                    )
                )
                inserted += 1
                if key in pending:
                    synced_pending.add(key)
            elif key in pending:
                row.value = value
                row.is_secret = key in SECRET_KEYS
                updated += 1
                synced_pending.add(key)

        await session.commit()

    if synced_pending:
        _clear_pending_settings(synced_pending)

    return {
        "ok": True,
        "migrated": inserted,
        "updated": updated,
        "pending_synced": sorted(synced_pending),
    }



def _apply_runtime_values(values: dict[str, str]) -> None:
    """
    PostgreSQL app_settings 값을 Backend 런타임 환경변수에 반영합니다.
    BaseSettings는 OS 환경변수를 .env보다 우선 사용하므로,
    get_settings.cache_clear() 후 즉시 새 값을 읽습니다.
    """
    for key, value in values.items():
        if key not in SETTING_KEYS:
            continue
        if key in BOOTSTRAP_KEYS:
            continue

        os.environ[key] = str(value)

    get_settings.cache_clear()

    # v5.493: path settings are operational immediately, not cosmetic.
    if any(key in values for key in {"DEFAULT_TEMP_ROOT", "DEFAULT_CACHE_ROOT", "DEFAULT_OUTPUT_ROOT"}):
        from app.services.runtime_path_policy import apply_runtime_path_policy
        apply_runtime_path_policy()


async def load_db_settings_into_runtime() -> dict:
    """
    Backend 시작 시 PostgreSQL app_settings의 설정을 런타임에 복원합니다.
    API Key 같은 비밀값도 Backend 프로세스 내부에만 설정되며
    Frontend에는 실제 값이 반환되지 않습니다.
    """
    db_data = await _read_db_settings()

    runtime_values = {
        key: value
        for key, value in db_data.items()
        if key not in BOOTSTRAP_KEYS
    }

    _apply_runtime_values(runtime_values)
    if runtime_values:
        _write_env_values(runtime_values)

    return {
        "ok": True,
        "loaded": len(runtime_values),
    }


async def get_editable_settings() -> dict[str, Any]:
    env_data = read_env_dict()
    actual_env_data = read_actual_env_dict()

    db_connected = True
    db_error = ""
    try:
        db_data = await _read_db_settings()
    except Exception as exc:
        # 최초 DB 생성 전/인증 실패 시에도 .env + .env.example 기본값으로 화면을 유지합니다.
        db_data = {}
        db_connected = False
        db_error = str(exc)

    result: dict[str, Any] = {}

    for key in SETTING_KEYS:
        default_value = DEFAULT_SETTING_VALUES.get(key, "")
        if key in DB_CONNECTION_ENV_ONLY_KEYS:
            # DATABASE_URL/LANGGRAPH_DATABASE_URL은 DB 자체에 연결하기 위한 bootstrap 값이므로
            # app_settings를 절대 조회하지 않고 backend/.env 실제 저장값만 사용합니다.
            value = actual_env_data.get(key, env_data.get(key, default_value))
        elif key in BOOTSTRAP_KEYS:
            value = env_data.get(key, default_value)
        else:
            value = db_data.get(
                key,
                env_data.get(key, default_value),
            )

        if key in SECRET_KEYS:
            result[key] = {
                "configured": bool(value),
                "masked": ("*" * 8 if value else ""),
                "value": "",
            }
        else:
            result[key] = value

    pc_name = current_pc_name()
    system_host_name = detect_system_pc_name()
    result["_machine"] = {
        "pc_name": pc_name,
        "system_host_name": system_host_name,
        "editable": True,
        "unique": db_connected and not pending_pc_name(),
        "scope": "PC_NAME",
        "env_key": "AGENTSTUDIO_PC_NAME",
        "pending_pc_name": pending_pc_name(),
        "unique_verified": db_connected and not pending_pc_name(),
    }
    result["_storage"] = {
        "primary": "PostgreSQL",
        "fallback": ".env",
        "table": "app_settings",
        "scope": "pc_name + key",
        "pc_name": pc_name,
        "bootstrap": sorted(BOOTSTRAP_KEYS),
        "env_only": sorted(DB_CONNECTION_ENV_ONLY_KEYS),
        "database_connection_source": str(ENV_PATH),
        "database_connection_storage": "backend/.env only (app_settings 미사용)",
        "db_connected": db_connected,
        "db_error": db_error,
        "mode": "shared_db+local_env" if db_connected else "local_env_fallback",
        "pending_settings": sorted(_pending_setting_keys()),
    }

    return result


async def save_database_env_settings(values: dict[str, Any]) -> dict[str, Any]:
    """
    DATABASE_URL / LANGGRAPH_DATABASE_URL은 DB 연결 자체를 만들기 위한 bootstrap 설정입니다.
    따라서 PostgreSQL app_settings에 절대 저장하지 않고 backend/.env에만 저장합니다.
    DB가 완전히 오프라인이어도 저장/재조회가 가능해야 합니다.
    """
    allowed = DB_CONNECTION_ENV_ONLY_KEYS | {"POSTGRESQL18_ROOT"}
    env_values: dict[str, str] = {}
    for key, value in values.items():
        if key not in allowed or value is None:
            continue
        env_values[key] = str(value).strip()

    if not env_values:
        raise ValueError("저장할 DB 환경 설정이 없습니다.")

    # v5.284: DATABASE_URL/LANGGRAPH_DATABASE_URL은 항상 기본 로컬 PostgreSQL을 뜻합니다.
    # Supabase runtime을 선택해도 이 값을 덮어쓰지 않고 별도 SUPABASE_* 키를 사용합니다.
    if "DATABASE_URL" in env_values:
        env_values["AGENTSTUDIO_LOCAL_DATABASE_URL"] = env_values["DATABASE_URL"]
    if "LANGGRAPH_DATABASE_URL" in env_values:
        env_values["AGENTSTUDIO_LOCAL_LANGGRAPH_DATABASE_URL"] = env_values["LANGGRAPH_DATABASE_URL"]

    # DB 접속 없이 파일에 먼저 확정 저장합니다.
    _write_env_values(env_values)
    get_settings.cache_clear()

    # .env.example이나 app_settings가 아니라 실제 backend/.env를 다시 읽어 검증합니다.
    actual = read_actual_env_dict()
    mismatched = [key for key, value in env_values.items() if actual.get(key) != value]
    if mismatched:
        raise OSError("backend/.env 저장 확인 실패: " + ", ".join(mismatched))

    database_rebound = False
    database_rebind_error = ""
    database_url = str(env_values.get("DATABASE_URL") or actual.get("DATABASE_URL") or "").strip()
    active_provider = str(actual.get("AGENTSTUDIO_DATABASE_PROVIDER") or "local").strip().lower()
    if database_url and active_provider != "supabase":
        try:
            from app.core.database import rebind_database
            await rebind_database(database_url)
            database_rebound = True
        except Exception as exc:
            # 연결 실패는 저장 실패가 아닙니다. .env에는 이미 안전하게 저장됐습니다.
            database_rebind_error = str(exc)

    # LANGGRAPH_DATABASE_URL도 .env 저장 직후 현재 런타임 Checkpointer에 즉시 반영합니다.
    # Backend 시작 당시 DB 인증이 실패했더라도 시스템 관리에서 올바른 URL을 저장하면
    # Backend 재시작 없이 LangGraph 영속화를 복구할 수 있습니다.
    langgraph_rebound = False
    langgraph_rebind_error = ""
    if "LANGGRAPH_DATABASE_URL" in env_values and active_provider != "supabase":
        try:
            from app.services.langgraph_runtime import agent_graph_runtime
            await agent_graph_runtime.set_database_url(str(env_values["LANGGRAPH_DATABASE_URL"]), restart=False)
            langgraph_rebound = bool(await agent_graph_runtime.restart())
            if not langgraph_rebound:
                langgraph_rebind_error = agent_graph_runtime.last_error
        except Exception as exc:
            langgraph_rebind_error = str(exc)

    # 반환값도 DB를 거치지 않고 .env에서 직접 구성합니다.
    persisted = {key: actual.get(key, "") for key in env_values}
    message = f"DB 연결 설정을 {ENV_PATH}에 저장했습니다. PostgreSQL app_settings에는 저장하지 않습니다."
    if database_rebound:
        message += " 현재 Backend DB 연결에도 즉시 적용했습니다."
    elif database_rebind_error:
        message += " 현재 DB 재연결은 실패했지만 .env 저장은 완료되었습니다. 연결 정보를 수정한 뒤 다시 테스트할 수 있습니다."

    if "LANGGRAPH_DATABASE_URL" in env_values:
        if langgraph_rebound:
            message += " LangGraph PostgreSQL Checkpointer도 즉시 재연결했습니다."
        elif langgraph_rebind_error:
            message += " LangGraph Checkpointer 재연결은 실패했지만 .env 저장값은 유지됩니다."

    return {
        "ok": True,
        "storage": "env_only",
        "env_path": str(ENV_PATH),
        "saved": persisted,
        "database_rebound": database_rebound,
        "database_rebind_error": database_rebind_error,
        "langgraph_rebound": langgraph_rebound,
        "langgraph_rebind_error": langgraph_rebind_error,
        "message": message,
    }


async def update_settings(
    values: dict[str, Any],
) -> dict[str, Any]:
    bootstrap_values: dict[str, str] = {}
    db_values: dict[str, str] = {}

    if (
        "AGENTSTUDIO_BACKEND_PORT" in values
        or "AGENTSTUDIO_FRONTEND_PORT" in values
    ):
        current = read_env_dict()
        backend_raw = values.get(
            "AGENTSTUDIO_BACKEND_PORT",
            current.get("AGENTSTUDIO_BACKEND_PORT", "8000"),
        )
        frontend_raw = values.get(
            "AGENTSTUDIO_FRONTEND_PORT",
            current.get("AGENTSTUDIO_FRONTEND_PORT", "5173"),
        )
        try:
            backend_port = int(str(backend_raw))
            frontend_port = int(str(frontend_raw))
        except ValueError as exc:
            raise ValueError("서비스 포트는 숫자로 입력해야 합니다.") from exc

        for label, port in (
            ("Backend", backend_port),
            ("Frontend", frontend_port),
        ):
            if port < 1024 or port > 65535:
                raise ValueError(
                    f"{label} 포트는 1024~65535 사이여야 합니다."
                )
        if backend_port == frontend_port:
            raise ValueError(
                "Backend와 Frontend는 서로 다른 포트를 사용해야 합니다."
            )

    # v5.330: OpenAI OFF means OpenAI is removed from the adaptive fallback
    # chain, but Codex can remain available when the user explicitly enabled it.
    # Embeddings stay local because Codex is not an embedding provider.
    normalized_openai_enabled = None
    if "OPENAI_ENABLED" in values and values.get("OPENAI_ENABLED") is not None:
        raw_enabled = str(values.get("OPENAI_ENABLED") or "").strip().lower()
        normalized_openai_enabled = raw_enabled not in {"0", "false", "no", "off"}
        values = dict(values)
        values["OPENAI_ENABLED"] = "true" if normalized_openai_enabled else "false"
        if not normalized_openai_enabled:
            values["MEMORY_EMBEDDING_PROVIDER"] = "ollama"

    if "CODEX_ENABLED" in values and values.get("CODEX_ENABLED") is not None:
        raw_codex = str(values.get("CODEX_ENABLED") or "").strip().lower()
        values = dict(values)
        values["CODEX_ENABLED"] = "false" if raw_codex in {"0", "false", "no", "off"} else "true"

    if "AI_PROVIDER_STRATEGY" in values and values.get("AI_PROVIDER_STRATEGY") is not None:
        strategy = str(values.get("AI_PROVIDER_STRATEGY") or "ollama_first").strip().lower()
        if strategy not in {"ollama_first", "manual"}:
            raise ValueError("AI Provider 전략은 ollama_first 또는 manual만 사용할 수 있습니다.")
        values = dict(values)
        values["AI_PROVIDER_STRATEGY"] = strategy

    provider_rules = {
        "LOCAL_LLM_PROVIDER": {"auto", "ollama", "openai"},
        "CODING_LLM_PROVIDER": {"auto", "ollama", "openai", "codex"},
        "REQUIREMENTS_LLM_PROVIDER": {"auto", "ollama", "openai", "codex"},
    }
    for key, allowed in provider_rules.items():
        if key not in values or values.get(key) is None:
            continue
        provider = str(values.get(key) or "auto").strip().lower()
        if provider not in allowed:
            raise ValueError(f"{key} Provider는 {', '.join(sorted(allowed))} 중 하나여야 합니다.")
        values = dict(values)
        values[key] = provider

    # 비밀값이 빈 문자열이면 기존 DB 값을 유지
    for key, value in values.items():
        if key not in SETTING_KEYS:
            continue
        if value is None:
            continue

        value = str(value)

        if key in SECRET_KEYS and value == "":
            continue

        if key in BOOTSTRAP_KEYS:
            bootstrap_values[key] = value
        else:
            db_values[key] = value

    # 모든 설정을 PC 로컬 .env fallback cache에 먼저 저장합니다.
    # 공용 DB가 죽어 있어도 시스템 관리 화면에서 설정을 잃지 않습니다.
    if "DATABASE_URL" in bootstrap_values:
        bootstrap_values["AGENTSTUDIO_LOCAL_DATABASE_URL"] = bootstrap_values["DATABASE_URL"]
    if "LANGGRAPH_DATABASE_URL" in bootstrap_values:
        bootstrap_values["AGENTSTUDIO_LOCAL_LANGGRAPH_DATABASE_URL"] = bootstrap_values["LANGGRAPH_DATABASE_URL"]

    local_values = {**bootstrap_values, **db_values}
    database_rebound = False
    database_rebind_error = ""
    if local_values:
        _write_env_values(local_values)
        get_settings.cache_clear()

    # DATABASE_URL 저장은 파일 기록만으로 끝내지 않고 현재 Backend DB Engine에도
    # 즉시 반영합니다. 테스트가 성공한 화면 값과 실제 프로젝트/설정 DB가 달라지는
    # 문제를 방지합니다. 실패하더라도 .env 저장값은 유지하여 재시작 후 복구할 수 있습니다.
    active_provider = str(read_env_dict().get("AGENTSTUDIO_DATABASE_PROVIDER") or "local").strip().lower()
    if active_provider != "supabase" and "DATABASE_URL" in bootstrap_values and str(bootstrap_values.get("DATABASE_URL") or "").strip():
        try:
            from app.core.database import rebind_database
            await rebind_database(str(bootstrap_values["DATABASE_URL"]).strip())
            database_rebound = True
        except Exception as exc:
            database_rebind_error = str(exc)

    # 저장 직후 현재 Backend 프로세스에도 일반 설정을 반영합니다.
    if db_values:
        _apply_runtime_values(db_values)

    db_synced = True
    db_error = ""
    if db_values:
        try:
            async with SessionLocal() as session:
                pc_name = current_pc_name()
                rows = (
                    await session.execute(
                        select(AppSetting).where(
                            AppSetting.pc_name == pc_name,
                            AppSetting.key.in_(list(db_values.keys())),
                        )
                    )
                ).scalars().all()

                existing = {row.key: row for row in rows}
                for key, value in db_values.items():
                    row = existing.get(key)
                    if row:
                        row.value = value
                        row.is_secret = key in SECRET_KEYS
                    else:
                        session.add(
                            AppSetting(
                                pc_name=pc_name,
                                key=key,
                                value=value,
                                is_secret=key in SECRET_KEYS,
                            )
                        )
                await session.commit()
            _clear_pending_settings(set(db_values.keys()))
        except Exception as exc:
            db_synced = False
            db_error = str(exc)
            _mark_pending_settings(set(db_values.keys()))

    # v5.494: a manually saved/stale Ollama model value must not diverge from
    # the model actually used by AgentStudio requests. Re-resolve after DB commit.
    active_ollama_sync = {}
    if "OLLAMA_MODEL" in db_values:
        try:
            from app.services.active_ollama_model_service import sync_active_ollama_model
            active_ollama_sync = await sync_active_ollama_model()
        except Exception as exc:
            active_ollama_sync = {"ok": False, "error": str(exc) or type(exc).__name__}

    restart_required = any(
        key in bootstrap_values
        for key in ("LANGGRAPH_DATABASE_URL", "AGENTSTUDIO_BACKEND_PORT", "AGENTSTUDIO_FRONTEND_PORT")
    )

    if db_synced:
        message = (
            f"설정을 PC [{current_pc_name()}] 기준으로 .env에 저장했습니다. "
            + ("공용 PostgreSQL app_settings에도 동기화했습니다." if db_values else "bootstrap 설정을 저장했습니다.")
        )
    else:
        message = (
            f"공용 DB에 연결할 수 없어 설정을 PC [{current_pc_name()}]의 .env에 먼저 저장했습니다. "
            "DB 연결이 복구되면 '설정 DB 이관' 또는 다음 시작 시 자동으로 공용 DB에 동기화됩니다."
        )
    if database_rebound:
        message += " DATABASE_URL은 저장 후 현재 Backend DB 연결에도 즉시 적용했습니다."
    elif database_rebind_error:
        message += " DATABASE_URL은 .env에 저장했지만 현재 Backend DB 재연결은 실패했습니다. 연결 정보를 확인하거나 SYSTEM_ADMIN.cmd를 다시 실행하세요."
    if restart_required:
        message += " LangGraph DB URL/서비스 포트 변경은 SYSTEM_ADMIN.cmd 재실행 후 관련 런타임에 완전히 적용됩니다."

    saved_bootstrap = {}
    persisted_env = read_env_dict()
    for key in bootstrap_values:
        if key in persisted_env:
            saved_bootstrap[key] = persisted_env[key]

    return {
        "ok": True,
        "db_synced": db_synced,
        "db_error": db_error,
        "local_saved": True,
        "database_rebound": database_rebound,
        "database_rebind_error": database_rebind_error,
        "saved_bootstrap": saved_bootstrap,
        "restart_required": restart_required,
        "active_ollama_sync": active_ollama_sync,
        "message": message,
        "settings": await get_editable_settings(),
    }
