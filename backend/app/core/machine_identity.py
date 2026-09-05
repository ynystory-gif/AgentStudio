from __future__ import annotations

import os
import platform
import re
import socket
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
ENV_PATH = PROJECT_ROOT / ".env"
ENV_EXAMPLE_PATH = PROJECT_ROOT / ".env.example"
PC_NAME_KEY = "AGENTSTUDIO_PC_NAME"
SYSTEM_HOST_KEY = "AGENTSTUDIO_SYSTEM_HOST_NAME"
PENDING_PC_NAME_KEY = "AGENTSTUDIO_PC_NAME_PENDING"
PC_NAME_PATTERN = re.compile(r"^[0-9A-Za-z가-힣._-]{2,64}$")


def detect_system_pc_name() -> str:
    """Return the physical OS host name, preferring Windows COMPUTERNAME."""
    candidates = [
        os.environ.get("COMPUTERNAME", ""),
        platform.node(),
        socket.gethostname(),
        os.environ.get("HOSTNAME", ""),
    ]
    for value in candidates:
        value = str(value or "").strip()
        if value:
            return value
    return "UNKNOWN-PC"


# Backward-compatible alias used by older modules.
def detect_pc_name() -> str:
    return detect_system_pc_name()


def _parse_env_file(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip().upper()] = value.strip()
    return result


def _read_env_values() -> dict[str, str]:
    # .env.example은 신규 PC의 기본 템플릿이고 실제 .env가 우선합니다.
    result = _parse_env_file(ENV_EXAMPLE_PATH)
    result.update(_parse_env_file(ENV_PATH))
    return result


def _base_env_lines() -> list[str]:
    # 신규 clone 직후 .env가 없을 때 PC 이름만 들어간 빈 .env를 만들지 않고
    # .env.example 전체를 복사한 뒤 장치 식별 정보를 덮어씁니다.
    if ENV_PATH.exists():
        return ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    if ENV_EXAMPLE_PATH.exists():
        return ENV_EXAMPLE_PATH.read_text(encoding="utf-8", errors="replace").splitlines()
    return []


def validate_pc_name(value: str) -> str:
    name = str(value or "").strip()
    if not name:
        raise ValueError("PC 이름을 입력하세요.")
    if not PC_NAME_PATTERN.fullmatch(name):
        raise ValueError(
            "PC 이름은 2~64자의 영문/숫자/한글 및 . _ - 문자만 사용할 수 있습니다."
        )
    return name


def current_pc_name() -> str:
    """
    Return the user-managed AgentStudio PC name.

    The physical Windows/OS hostname is kept separately as host_name and is not
    used as the shared-DB settings scope once the user assigns a custom name.
    """
    env_value = str(os.environ.get(PC_NAME_KEY, "") or "").strip()
    if not env_value:
        env_value = _read_env_values().get(PC_NAME_KEY, "").strip()
    if env_value:
        return env_value
    return detect_system_pc_name()


def _write_identity_env(pc_name: str, system_host_name: str) -> dict:
    lines: list[str] = _base_env_lines()

    replacements = {
        PC_NAME_KEY: pc_name,
        SYSTEM_HOST_KEY: system_host_name,
    }
    previous: dict[str, str] = {}
    seen: set[str] = set()
    output: list[str] = []

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("#") or "=" not in line:
            output.append(line)
            continue
        left, right = line.split("=", 1)
        key = left.strip().upper()
        if key in replacements:
            previous[key] = right.strip()
            output.append(f"{key}={replacements[key]}")
            seen.add(key)
        else:
            output.append(line)

    missing = [key for key in replacements if key not in seen]
    if missing:
        if output and output[-1].strip():
            output.append("")
        output.append("# AgentStudio machine identity (user PC name + physical host)")
        for key in missing:
            output.append(f"{key}={replacements[key]}")

    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    ENV_PATH.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")

    os.environ[PC_NAME_KEY] = pc_name
    os.environ[SYSTEM_HOST_KEY] = system_host_name
    try:
        from app.core.config import get_settings
        get_settings.cache_clear()
    except Exception:
        pass

    return {
        "previous_pc_name": previous.get(PC_NAME_KEY, ""),
        "previous_system_host_name": previous.get(SYSTEM_HOST_KEY, ""),
    }


def pending_pc_name() -> str:
    return str(_parse_env_file(ENV_PATH).get(PENDING_PC_NAME_KEY, "") or "").strip()


def _write_single_env_value(key: str, value: str) -> None:
    lines = _base_env_lines()
    output: list[str] = []
    seen = False
    for line in lines:
        if "=" in line and not line.lstrip().startswith("#"):
            left = line.split("=", 1)[0].strip().upper()
            if left == key.upper():
                if value:
                    output.append(f"{key}={value}")
                seen = True
                continue
        output.append(line)
    if value and not seen:
        if output and output[-1].strip():
            output.append("")
        output.append(f"{key}={value}")
    ENV_PATH.parent.mkdir(parents=True, exist_ok=True)
    ENV_PATH.write_text("\n".join(output).rstrip() + "\n", encoding="utf-8")


def set_pending_pc_name_env(pc_name: str) -> dict:
    normalized = validate_pc_name(pc_name)
    _write_single_env_value(PENDING_PC_NAME_KEY, normalized)
    return {"ok": True, "pending_pc_name": normalized, "env_path": str(ENV_PATH)}


def clear_pending_pc_name_env() -> None:
    _write_single_env_value(PENDING_PC_NAME_KEY, "")


def ensure_pc_name_env() -> dict:
    """
    Ensure an editable AgentStudio PC name exists in the project-root .env.

    The user-managed AGENTSTUDIO_PC_NAME is preserved. On first run it defaults
    to the physical Windows/OS host name. The physical host name is stored
    separately in AGENTSTUDIO_SYSTEM_HOST_NAME for diagnostics.
    """
    system_host_name = detect_system_pc_name()
    env_data = _read_env_values()
    configured_name = str(
        os.environ.get(PC_NAME_KEY, "")
        or env_data.get(PC_NAME_KEY, "")
        or ""
    ).strip()
    pc_name = configured_name or system_host_name
    try:
        pc_name = validate_pc_name(pc_name)
    except ValueError:
        # A legacy/system hostname can contain characters outside the editable
        # naming rule. Keep a deterministic safe initial value.
        safe = re.sub(r"[^0-9A-Za-z가-힣._-]+", "-", system_host_name).strip("-._")
        pc_name = (safe or "AGENTSTUDIO-PC")[:64]
        if len(pc_name) < 2:
            pc_name = "PC-01"

    previous = _write_identity_env(pc_name, system_host_name)
    return {
        "ok": True,
        "pc_name": pc_name,
        "system_host_name": system_host_name,
        "previous": previous.get("previous_pc_name", ""),
        "changed": previous.get("previous_pc_name", "") != pc_name,
        "env_path": str(ENV_PATH),
    }


def set_pc_name_env(pc_name: str) -> dict:
    """Persist a validated user-managed AgentStudio PC name to the project-root .env."""
    normalized = validate_pc_name(pc_name)
    system_host_name = detect_system_pc_name()
    previous = _write_identity_env(normalized, system_host_name)
    return {
        "ok": True,
        "pc_name": normalized,
        "system_host_name": system_host_name,
        "previous": previous.get("previous_pc_name", ""),
        "changed": previous.get("previous_pc_name", "") != normalized,
        "env_path": str(ENV_PATH),
    }
