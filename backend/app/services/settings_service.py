from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from sqlalchemy import select
from datetime import datetime
import platform

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.models.entities import AppSetting, AgentStudioMachine
from app.core.machine_identity import (
    current_pc_name,
    ensure_pc_name_env,
    detect_system_pc_name,
    set_pc_name_env,
    validate_pc_name,
)


ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
ENV_EXAMPLE_PATH = Path(__file__).resolve().parents[2] / ".env.example"

# DB 연결 이전에도 필요한 최소 bootstrap 설정만 .env에 유지합니다.
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

DEFAULT_SETTING_VALUES = {
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


def _read_env_lines() -> list[str]:
    if ENV_PATH.exists():
        return ENV_PATH.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()
    if ENV_EXAMPLE_PATH.exists():
        return ENV_EXAMPLE_PATH.read_text(
            encoding="utf-8",
            errors="replace",
        ).splitlines()
    return []


def read_env_dict() -> dict[str, str]:
    data: dict[str, str] = {}
    for line in _read_env_lines():
        stripped = line.strip()
        if (
            not stripped
            or stripped.startswith("#")
            or "=" not in line
        ):
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip()
    return data


def _write_bootstrap_values(values: dict[str, str]) -> None:
    existing_lines = _read_env_lines()
    current = read_env_dict()

    for key, value in values.items():
        if key in BOOTSTRAP_KEYS:
            current[key] = value

    seen: set[str] = set()
    output: list[str] = []

    for line in existing_lines:
        if (
            "=" in line
            and not line.lstrip().startswith("#")
        ):
            key = line.split("=", 1)[0].strip()
            if key in BOOTSTRAP_KEYS and key in current:
                output.append(f"{key}={current[key]}")
                seen.add(key)
                continue

            # DB로 이관된 일반 설정은 .env에서 제거
            if key in SETTING_KEYS and key not in BOOTSTRAP_KEYS:
                continue

        output.append(line)

    for key in BOOTSTRAP_KEYS:
        if key in current and key not in seen:
            output.append(f"{key}={current[key]}")

    ENV_PATH.write_text(
        "\n".join(output).rstrip() + "\n",
        encoding="utf-8",
    )


async def _read_db_settings() -> dict[str, str]:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(AppSetting).where(
                    AppSetting.pc_name == pc_name,
                    AppSetting.key.in_(SETTING_KEYS),
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
    """Rename the current PC scope, enforcing a globally unique pc_name."""
    new_name = validate_pc_name(new_pc_name)
    old_name = current_pc_name()
    system_host_name = detect_system_pc_name()

    if new_name == old_name:
        identity = set_pc_name_env(new_name)
        await register_current_machine()
        return {
            "ok": True,
            "changed": False,
            "pc_name": new_name,
            "system_host_name": system_host_name,
            "message": f"PC 이름 [{new_name}]을 유지합니다.",
            "settings": await get_editable_settings(),
        }

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
        if duplicate_machine is not None or duplicate_setting is not None:
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

        # Write .env before DB commit; if commit fails, restore the previous alias.
        set_pc_name_env(new_name)
        try:
            await session.commit()
        except Exception:
            set_pc_name_env(old_name)
            raise

    return {
        "ok": True,
        "changed": True,
        "old_pc_name": old_name,
        "pc_name": new_name,
        "system_host_name": system_host_name,
        "message": (
            f"PC 이름을 [{old_name}] → [{new_name}]으로 변경했습니다. "
            "기존 PC별 app_settings도 새 이름으로 함께 이동했습니다."
        ),
        "settings": await get_editable_settings(),
    }


async def migrate_env_settings_to_db() -> dict:
    """
    기존 .env 일반 설정을 DB로 1회 이관합니다.
    DB에 이미 값이 있는 key는 덮어쓰지 않습니다.
    """
    env_data = read_env_dict()

    async with SessionLocal() as session:
        pc_name = current_pc_name()
        existing_rows = (
            await session.execute(
                select(AppSetting).where(AppSetting.pc_name == pc_name)
            )
        ).scalars().all()

        existing = {row.key for row in existing_rows}
        migrated = 0

        for key in SETTING_KEYS:
            if key in BOOTSTRAP_KEYS:
                continue
            if key in existing:
                continue
            if key not in env_data:
                continue

            session.add(
                AppSetting(
                    pc_name=pc_name,
                    key=key,
                    value=env_data.get(key, ""),
                    is_secret=key in SECRET_KEYS,
                )
            )
            migrated += 1

        await session.commit()

    if migrated:
        # 일반 설정은 DB 이관 후 .env에서 제거
        _write_bootstrap_values({
            key: env_data.get(key, "")
            for key in BOOTSTRAP_KEYS
            if key in env_data
        })

    return {
        "ok": True,
        "migrated": migrated,
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

    return {
        "ok": True,
        "loaded": len(runtime_values),
    }


async def get_editable_settings() -> dict[str, Any]:
    env_data = read_env_dict()

    try:
        db_data = await _read_db_settings()
    except Exception:
        # 최초 DB 생성 전에는 .env/기본값으로 화면을 유지
        db_data = {}

    result: dict[str, Any] = {}

    for key in SETTING_KEYS:
        default_value = DEFAULT_SETTING_VALUES.get(key, "")
        if key in BOOTSTRAP_KEYS:
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
        "unique": True,
        "scope": "PC_NAME",
        "env_key": "AGENTSTUDIO_PC_NAME",
    }
    result["_storage"] = {
        "primary": "PostgreSQL",
        "table": "app_settings",
        "scope": "pc_name + key",
        "pc_name": pc_name,
        "bootstrap": sorted(BOOTSTRAP_KEYS),
    }

    return result


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

    # 비밀값이 빈 문자열이면 기존 DB 값을 유지
    for key, value in values.items():
        if key not in SETTING_KEYS:
            continue
        if value is None:
            continue

        value = str(value)

        if (
            key == "DATABASE_URL"
            and isinstance(value, str)
        ):
            value = _normalize_database_driver(value)

        if key in SECRET_KEYS and value == "":
            continue

        if key in BOOTSTRAP_KEYS:
            bootstrap_values[key] = value
        else:
            db_values[key] = value

    # DB bootstrap 정보는 .env에도 유지
    if bootstrap_values:
        _write_bootstrap_values(bootstrap_values)
        get_settings.cache_clear()

    # 일반 설정은 PostgreSQL app_settings에 upsert
    if db_values:
        async with SessionLocal() as session:
            pc_name = current_pc_name()
            rows = (
                await session.execute(
                    select(AppSetting).where(
                        AppSetting.pc_name == pc_name,
                        AppSetting.key.in_(
                            list(db_values.keys())
                        ),
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

        # 저장 직후 Backend 런타임에도 즉시 반영
        _apply_runtime_values(db_values)

    return {
        "ok": True,
        "message": (
            f"설정이 PC [{current_pc_name()}] 기준으로 PostgreSQL app_settings 테이블에 저장되고 Backend 런타임에 즉시 반영되었습니다. "
            "DB 연결/서비스 시작용 bootstrap 설정과 PC 이름은 .env에도 유지됩니다."
        ),
        "settings": await get_editable_settings(),
    }
