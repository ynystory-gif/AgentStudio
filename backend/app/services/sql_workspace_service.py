from __future__ import annotations

import base64
import ctypes
import json
import os
import shutil
import sqlite3
import subprocess
import threading
import time
import uuid
from datetime import date, datetime, time as dt_time
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID


_LEGACY_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_LEGACY_PROFILE_FILE = _LEGACY_DATA_DIR / "sql_workspace_profiles.json"
_LOCK = threading.RLock()
_SUPPORTED_DB_TYPES = {"postgresql", "mssql", "oracle", "sqlite3"}
# project_key -> connection_id -> live DB runtime
_RUNTIME: dict[str, dict[str, dict[str, Any]]] = {}
# project_key -> currently selected live/saved connection id
_ACTIVE_RUNTIME: dict[str, str] = {}
# project_key -> active SQL execution handle
_ACTIVE_EXECUTIONS: dict[str, dict[str, Any]] = {}


def _persistent_data_dir() -> Path:
    """Return a user-stable AgentStudio data folder that survives app upgrades."""
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


_PROFILE_FILE = _persistent_data_dir() / "sql_workspace_profiles.json"


def _project_key(root: str) -> str:
    raw = str(root or "").strip()
    if not raw:
        raise ValueError("프로젝트 root가 필요합니다.")
    resolved = os.path.abspath(os.path.expanduser(raw))
    return os.path.normcase(resolved)


def _default_connection_name(db_type: str) -> str:
    kind = str(db_type or "postgresql").lower()
    return {
        "postgresql": "PostgreSQL 연결",
        "mssql": "MSSQL 연결",
        "oracle": "Oracle 연결",
        "sqlite3": "SQLite3 연결",
    }.get(kind, "DB 연결")


def _default_profile(db_type: str = "postgresql") -> dict[str, Any]:
    kind = (db_type or "postgresql").strip().lower()
    common = {
        "connection_id": "",
        "name": _default_connection_name(kind),
        "db_type": kind,
        "host": "",
        "port": 0,
        "database": "",
        "username": "",
        "driver": "",
        "service_name": "",
        "trust_server_certificate": True,
    }
    if kind == "sqlite3":
        return {**common, "driver": "Python sqlite3 (stdlib)"}
    if kind == "mssql":
        return {
            **common,
            "host": "127.0.0.1",
            "port": 1433,
            "driver": "ODBC Driver 18 for SQL Server",
        }
    if kind == "oracle":
        return {
            **common,
            "host": "127.0.0.1",
            "port": 1521,
            "service_name": "FREEPDB1",
        }
    return {
        **common,
        "db_type": "postgresql",
        "host": "127.0.0.1",
        "port": 5432,
        "username": "postgres",
    }


def _read_json_dict(path: Path) -> dict[str, Any]:
    try:
        if not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _sanitized_profile(profile: dict[str, Any] | None) -> dict[str, Any]:
    src = dict(profile or {})
    kind = str(src.get("db_type") or "postgresql").lower()
    if kind not in _SUPPORTED_DB_TYPES:
        kind = "postgresql"
    result = _default_profile(kind)
    for key in result:
        if key in src and src[key] is not None:
            result[key] = src[key]
    try:
        result["port"] = int(result.get("port") or _default_profile(kind)["port"] or 0)
    except Exception:
        result["port"] = int(_default_profile(kind)["port"] or 0)
    result["db_type"] = kind
    result["connection_id"] = str(result.get("connection_id") or "").strip()
    result["name"] = str(result.get("name") or _default_connection_name(kind)).strip() or _default_connection_name(kind)
    return result


def _legacy_connection_id(project_key: str, db_type: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"theanova-agentstudio:{project_key}:{db_type}"))


def _normalize_stored_profile(profile: dict[str, Any], *, connection_id: str = "") -> dict[str, Any]:
    clean = _sanitized_profile(profile)
    clean["connection_id"] = str(connection_id or clean.get("connection_id") or uuid.uuid4()).strip()
    secret = str(profile.get("_password_dpapi") or "").strip()
    if secret:
        clean["_password_dpapi"] = secret
    clean["updated_at"] = profile.get("updated_at")
    return clean


def _normalize_database_history(value: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return rows
    for item in value:
        if not isinstance(item, dict):
            continue
        db_type = str(item.get("db_type") or "").strip().lower()
        host = str(item.get("host") or "").strip()
        database = str(item.get("database") or "").strip()
        if db_type not in {"postgresql", "mssql"} or not host or not database:
            continue
        try:
            port = int(item.get("port") or 0)
        except Exception:
            port = 0
        rows.append({
            "db_type": db_type,
            "host": host,
            "port": port,
            "database": database,
            "username": str(item.get("username") or "").strip(),
            "last_connected_at": item.get("last_connected_at"),
        })
    return rows[:100]


def _normalize_profile_store(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Normalize legacy per-type stores into the v5.239 multi-connection format."""
    normalized: dict[str, dict[str, Any]] = {}
    for project_key, value in (raw or {}).items():
        if not isinstance(value, dict):
            continue

        # v5.239+: project -> {active_connection_id, connections:{id:profile}}
        if isinstance(value.get("connections"), dict):
            connections: dict[str, dict[str, Any]] = {}
            for raw_id, profile in value.get("connections", {}).items():
                if not isinstance(profile, dict):
                    continue
                cid = str(profile.get("connection_id") or raw_id or uuid.uuid4()).strip()
                connections[cid] = _normalize_stored_profile(profile, connection_id=cid)
            active = str(value.get("active_connection_id") or "").strip()
            if active not in connections:
                active = next(iter(connections), "")
            normalized[str(project_key)] = {
                "active_connection_id": active,
                "connections": connections,
                "database_history": _normalize_database_history(value.get("database_history")),
                "updated_at": value.get("updated_at"),
            }
            continue

        # v5.227-v5.238: project -> {active_db_type, profiles:{db_type:profile}}
        if isinstance(value.get("profiles"), dict):
            connections = {}
            active_kind = str(value.get("active_db_type") or "").lower()
            active_id = ""
            for raw_kind, profile in value.get("profiles", {}).items():
                if not isinstance(profile, dict):
                    continue
                kind = str(profile.get("db_type") or raw_kind or "postgresql").lower()
                cid = _legacy_connection_id(str(project_key), kind)
                migrated = _normalize_stored_profile({
                    **profile,
                    "name": profile.get("name") or f"{_default_connection_name(kind)} (기존)",
                }, connection_id=cid)
                connections[cid] = migrated
                if kind == active_kind:
                    active_id = cid
            if not active_id:
                active_id = next(iter(connections), "")
            normalized[str(project_key)] = {
                "active_connection_id": active_id,
                "connections": connections,
                "database_history": [],
                "updated_at": value.get("updated_at"),
            }
            continue

        # Older format: project -> one DB profile.
        kind = str(value.get("db_type") or "postgresql").lower()
        cid = _legacy_connection_id(str(project_key), kind)
        migrated = _normalize_stored_profile({
            **value,
            "name": value.get("name") or f"{_default_connection_name(kind)} (기존)",
        }, connection_id=cid)
        normalized[str(project_key)] = {
            "active_connection_id": cid,
            "connections": {cid: migrated},
            "database_history": [],
            "updated_at": value.get("updated_at"),
        }
    return normalized


def _write_profiles(profiles: dict[str, dict[str, Any]]) -> None:
    _PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _PROFILE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(profiles, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(_PROFILE_FILE)


def _load_profiles() -> dict[str, dict[str, Any]]:
    """Load stable profiles and transparently migrate older install-local formats."""
    current = _normalize_profile_store(_read_json_dict(_PROFILE_FILE))
    legacy = _normalize_profile_store(_read_json_dict(_LEGACY_PROFILE_FILE))
    changed = False

    for project_key, legacy_entry in legacy.items():
        target = current.setdefault(project_key, {
            "active_connection_id": legacy_entry.get("active_connection_id") or "",
            "connections": {},
            "updated_at": legacy_entry.get("updated_at"),
        })
        target_connections = target.setdefault("connections", {})
        for cid, profile in legacy_entry.get("connections", {}).items():
            if cid not in target_connections:
                target_connections[cid] = profile
                changed = True
        if not target.get("active_connection_id"):
            target["active_connection_id"] = legacy_entry.get("active_connection_id") or next(iter(target_connections), "")
            changed = True

    if changed and current:
        try:
            _write_profiles(current)
        except Exception:
            pass
    return current


def _dpapi_available() -> bool:
    return os.name == "nt"


def _protect_password(password: str) -> str:
    """Encrypt a password with Windows DPAPI in the current-user scope."""
    if not password or not _dpapi_available():
        return ""

    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    raw = str(password).encode("utf-8")
    input_buffer = ctypes.create_string_buffer(raw)
    input_blob = DATA_BLOB(len(raw), ctypes.cast(input_buffer, ctypes.POINTER(ctypes.c_byte)))
    output_blob = DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(DATA_BLOB), wintypes.LPCWSTR, ctypes.POINTER(DATA_BLOB),
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    ok = crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        "THEANOVA AgentStudio SQL Workspace",
        None,
        None,
        None,
        0,
        ctypes.byref(output_blob),
    )
    if not ok:
        raise ctypes.WinError()
    try:
        encrypted = ctypes.string_at(output_blob.pbData, output_blob.cbData)
        return base64.b64encode(encrypted).decode("ascii")
    finally:
        if output_blob.pbData:
            kernel32.LocalFree(ctypes.cast(output_blob.pbData, ctypes.c_void_p))


def _unprotect_password(encoded: str) -> str:
    if not encoded or not _dpapi_available():
        return ""

    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

    encrypted = base64.b64decode(str(encoded).encode("ascii"))
    input_buffer = ctypes.create_string_buffer(encrypted)
    input_blob = DATA_BLOB(len(encrypted), ctypes.cast(input_buffer, ctypes.POINTER(ctypes.c_byte)))
    output_blob = DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(DATA_BLOB), ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(DATA_BLOB),
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    ok = crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(output_blob),
    )
    if not ok:
        raise ctypes.WinError()
    try:
        plain = ctypes.string_at(output_blob.pbData, output_blob.cbData)
        return plain.decode("utf-8")
    finally:
        if output_blob.pbData:
            kernel32.LocalFree(ctypes.cast(output_blob.pbData, ctypes.c_void_p))


def _public_profile(stored: dict[str, Any] | None) -> dict[str, Any]:
    clean = _sanitized_profile(stored)
    clean["credential_saved"] = bool(stored and stored.get("_password_dpapi"))
    clean["updated_at"] = (stored or {}).get("updated_at")
    return clean


def _runtime_bucket(key: str, *, create: bool = False) -> dict[str, dict[str, Any]]:
    if create:
        return _RUNTIME.setdefault(key, {})
    return _RUNTIME.get(key) or {}


def _saved_entry(key: str, profiles: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    store = profiles if profiles is not None else _load_profiles()
    return store.get(key) or {"active_connection_id": "", "connections": {}, "database_history": [], "updated_at": None}


def _connection_sort_key(profile: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(profile.get("name") or "").casefold(),
        str(profile.get("db_type") or "").casefold(),
        str(profile.get("connection_id") or ""),
    )


def list_profiles(root: str) -> dict[str, Any]:
    key = _project_key(root)
    with _LOCK:
        profiles = _load_profiles()
        entry = _saved_entry(key, profiles)
        runtime_bucket = dict(_runtime_bucket(key))
        active_id = str(_ACTIVE_RUNTIME.get(key) or entry.get("active_connection_id") or "")
        items = []
        for cid, stored in (entry.get("connections") or {}).items():
            public = _public_profile(stored)
            runtime = runtime_bucket.get(cid)
            public.update({
                "connected": bool(runtime and runtime.get("connection") is not None),
                "connected_at": runtime.get("connected_at") if runtime else None,
                "active": cid == active_id,
            })
            items.append(public)
    items.sort(key=_connection_sort_key)
    return {
        "ok": True,
        "connections": items,
        "active_connection_id": active_id,
        "saved_connection_count": len(items),
        "connected_connection_count": sum(1 for item in items if item.get("connected")),
        "database_history": _normalize_database_history(entry.get("database_history")),
        **profile_storage_info(root),
    }


def get_profile(root: str, db_type: str | None = None, connection_id: str | None = None) -> dict[str, Any]:
    key = _project_key(root)
    requested_kind = str(db_type or "").strip().lower()
    requested_id = str(connection_id or "").strip()
    with _LOCK:
        profiles = _load_profiles()
        entry = _saved_entry(key, profiles)
        saved = entry.get("connections") or {}
        stored = None
        if requested_id:
            stored = saved.get(requested_id)
        elif requested_kind in _SUPPORTED_DB_TYPES:
            active_id = str(entry.get("active_connection_id") or "")
            active = saved.get(active_id)
            if active and str(active.get("db_type") or "").lower() == requested_kind:
                stored = active
            else:
                stored = next((p for p in saved.values() if str(p.get("db_type") or "").lower() == requested_kind), None)
        else:
            active_id = str(_ACTIVE_RUNTIME.get(key) or entry.get("active_connection_id") or "")
            stored = saved.get(active_id)
    if stored:
        return _public_profile(stored)
    return _public_profile(_default_profile(requested_kind if requested_kind in _SUPPORTED_DB_TYPES else "postgresql"))


def _make_profile_name(clean: dict[str, Any]) -> str:
    existing = str(clean.get("name") or "").strip()
    if existing:
        return existing
    kind = str(clean.get("db_type") or "postgresql")
    if kind == "sqlite3":
        target = str(clean.get("database") or "").strip()
    elif kind == "oracle":
        target = f"{clean.get('host') or ''}/{clean.get('service_name') or ''}".strip("/")
    else:
        target = f"{clean.get('host') or ''}/{clean.get('database') or ''}".strip("/")
    return f"{_default_connection_name(kind)} · {target}" if target else _default_connection_name(kind)


def save_profile(root: str, profile: dict[str, Any], password: str | None = None) -> dict[str, Any]:
    key = _project_key(root)
    clean = _sanitized_profile(profile)
    cid = str(clean.get("connection_id") or uuid.uuid4()).strip()
    clean["connection_id"] = cid
    clean["name"] = _make_profile_name(clean)
    clean["updated_at"] = datetime.now().isoformat(timespec="seconds")

    with _LOCK:
        profiles = _load_profiles()
        entry = profiles.setdefault(key, {"active_connection_id": cid, "connections": {}, "database_history": [], "updated_at": None})
        connections = entry.setdefault("connections", {})
        previous = connections.get(cid) if isinstance(connections.get(cid), dict) else None

        # Keep profile labels unambiguous even when users add several MSSQL/PostgreSQL
        # connections without renaming the default label.
        base_name = str(clean.get("name") or _default_connection_name(clean["db_type"])).strip()
        used_names = {
            str(item.get("name") or "").strip().casefold()
            for other_id, item in connections.items()
            if other_id != cid and isinstance(item, dict)
        }
        candidate = base_name
        suffix = 2
        while candidate.casefold() in used_names:
            candidate = f"{base_name} {suffix}"
            suffix += 1
        clean["name"] = candidate

        # Preserve a saved credential only when the DB type did not change.
        secret = ""
        if previous and str(previous.get("db_type") or "").lower() == clean["db_type"]:
            secret = str(previous.get("_password_dpapi") or "")
        if password is not None and str(password) != "":
            secret = _protect_password(str(password)) if _dpapi_available() else ""
        if secret:
            clean["_password_dpapi"] = secret

        connections[cid] = clean
        entry["active_connection_id"] = cid
        entry["updated_at"] = clean["updated_at"]
        _write_profiles(profiles)
        _ACTIVE_RUNTIME[key] = cid
    return _public_profile(clean)


def delete_profile(root: str, connection_id: str) -> dict[str, Any]:
    key = _project_key(root)
    cid = str(connection_id or "").strip()
    if not cid:
        raise ValueError("삭제할 DB 연결 ID가 필요합니다.")

    runtime = None
    with _LOCK:
        runtime = _runtime_bucket(key).pop(cid, None)
        profiles = _load_profiles()
        entry = profiles.get(key)
        if not entry or cid not in (entry.get("connections") or {}):
            raise ValueError("저장된 DB 연결을 찾을 수 없습니다.")
        entry["connections"].pop(cid, None)
        next_id = next(iter(entry["connections"]), "")
        if str(entry.get("active_connection_id") or "") == cid:
            entry["active_connection_id"] = next_id
        entry["updated_at"] = datetime.now().isoformat(timespec="seconds")
        _ACTIVE_RUNTIME[key] = str(entry.get("active_connection_id") or "")
        _write_profiles(profiles)
    _close_connection(runtime)
    return status(root)


def activate_profile(root: str, connection_id: str) -> dict[str, Any]:
    key = _project_key(root)
    cid = str(connection_id or "").strip()
    if not cid:
        raise ValueError("선택할 DB 연결 ID가 필요합니다.")
    with _LOCK:
        profiles = _load_profiles()
        entry = profiles.get(key)
        if not entry or cid not in (entry.get("connections") or {}):
            raise ValueError("저장된 DB 연결을 찾을 수 없습니다.")
        entry["active_connection_id"] = cid
        entry["updated_at"] = datetime.now().isoformat(timespec="seconds")
        _write_profiles(profiles)
        _ACTIVE_RUNTIME[key] = cid
    return status(root, verify=True)


def profile_storage_info(root: str) -> dict[str, Any]:
    key = _project_key(root)
    with _LOCK:
        profiles = _load_profiles()
        entry = _saved_entry(key, profiles)
        connections = entry.get("connections") or {}
    saved_db_types = sorted({str(p.get("db_type") or "").lower() for p in connections.values() if p.get("db_type")})
    return {
        "storage_path": str(_PROFILE_FILE),
        "saved_db_types": saved_db_types,
        "active_connection_id": entry.get("active_connection_id") or "",
        "password_persisted": _dpapi_available(),
        "credential_storage": "Windows DPAPI (현재 Windows 사용자 범위)" if _dpapi_available() else "비밀번호 영구 저장 미지원",
    }


def _close_connection(runtime: dict[str, Any] | None) -> None:
    if not runtime:
        return
    conn = runtime.get("connection")
    if conn is None:
        return
    try:
        conn.close()
    except Exception:
        pass


def _active_connection_id(root: str) -> str:
    key = _project_key(root)
    with _LOCK:
        profiles = _load_profiles()
        entry = _saved_entry(key, profiles)
        cid = str(_ACTIVE_RUNTIME.get(key) or entry.get("active_connection_id") or "")
    return cid


def _get_active_runtime(root: str) -> tuple[str, dict[str, Any] | None]:
    key = _project_key(root)
    cid = _active_connection_id(root)
    with _LOCK:
        runtime = _runtime_bucket(key).get(cid) if cid else None
    return cid, runtime


def _stored_password(root: str, connection_id: str) -> str:
    key = _project_key(root)
    with _LOCK:
        entry = _saved_entry(key)
        stored = (entry.get("connections") or {}).get(str(connection_id or ""))
        secret = str((stored or {}).get("_password_dpapi") or "")
    if not secret:
        return ""
    try:
        return _unprotect_password(secret)
    except Exception as exc:
        raise RuntimeError("저장된 DB 비밀번호를 Windows 보안 저장소에서 복호화하지 못했습니다. 비밀번호를 다시 입력해 저장하세요.") from exc


def disconnect(root: str, connection_id: str | None = None, *, all_connections: bool = False) -> dict[str, Any]:
    key = _project_key(root)
    cid = str(connection_id or "").strip() or _active_connection_id(root)
    closed: list[dict[str, Any]] = []
    with _LOCK:
        bucket = _runtime_bucket(key)
        if all_connections:
            items = list(bucket.items())
            _RUNTIME.pop(key, None)
        else:
            runtime = bucket.pop(cid, None) if cid else None
            items = [(cid, runtime)] if runtime else []
        for item_id, runtime in items:
            if runtime:
                closed.append(runtime)
    for runtime in closed:
        _close_connection(runtime)
    return status(root)


def release_sqlite_file_locks(root: str, relative_paths: list[str]) -> list[str]:
    """Release AgentStudio-owned SQLite connections that lock target project files."""
    key = _project_key(root)
    project_root = Path(key).resolve()
    targets: set[str] = set()
    for raw in relative_paths or []:
        rel = str(raw or "").strip().replace("\\", "/").lstrip("/")
        if not rel:
            continue
        try:
            resolved = (project_root / Path(rel)).resolve()
            resolved.relative_to(project_root)
        except Exception:
            continue
        targets.add(os.path.normcase(str(resolved)))

    if not targets:
        return []

    to_close: list[dict[str, Any]] = []
    released: list[str] = []
    with _LOCK:
        bucket = _runtime_bucket(key)
        for cid, runtime in list(bucket.items()):
            profile = dict(runtime.get("profile") or {}) if runtime else {}
            if str(profile.get("db_type") or "").lower() != "sqlite3":
                continue
            raw_database = str(profile.get("database") or "").strip().strip('"')
            if not raw_database:
                continue
            database_path = Path(raw_database).expanduser()
            if not database_path.is_absolute():
                database_path = project_root / database_path
            try:
                database_path = database_path.resolve()
            except Exception:
                continue
            if os.path.normcase(str(database_path)) not in targets:
                continue
            bucket.pop(cid, None)
            to_close.append(runtime)
            released.append(str(database_path))
    for runtime in to_close:
        _close_connection(runtime)
    return released


def _connect_postgresql(profile: dict[str, Any], password: str):
    try:
        import psycopg
    except Exception as exc:
        raise RuntimeError("PostgreSQL 드라이버 psycopg가 설치되어 있지 않습니다.") from exc

    return psycopg.connect(
        host=profile["host"],
        port=int(profile["port"]),
        dbname=profile["database"],
        user=profile["username"],
        password=password,
        connect_timeout=8,
        application_name="THEANOVA AgentStudio SQL Workspace",
    )


def _connect_mssql(profile: dict[str, Any], password: str):
    try:
        import pyodbc
    except Exception as exc:
        raise RuntimeError(
            "MSSQL 드라이버 pyodbc가 설치되어 있지 않습니다. "
            "Microsoft ODBC Driver 18 for SQL Server도 Windows에 설치되어 있어야 합니다."
        ) from exc

    driver = profile.get("driver") or "ODBC Driver 18 for SQL Server"
    trust = "yes" if profile.get("trust_server_certificate", True) else "no"
    server = profile.get("host") or "127.0.0.1"
    port = int(profile.get("port") or 1433)
    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={server},{port};"
        f"DATABASE={profile.get('database','')};"
        f"UID={profile.get('username','')};"
        f"PWD={password};"
        "Encrypt=yes;"
        f"TrustServerCertificate={trust};"
        "Connection Timeout=8;"
    )
    return pyodbc.connect(conn_str, autocommit=False)


def _connect_oracle(profile: dict[str, Any], password: str):
    try:
        import oracledb
    except Exception as exc:
        raise RuntimeError("Oracle 드라이버 oracledb가 설치되어 있지 않습니다.") from exc

    service_name = str(profile.get("service_name") or profile.get("database") or "").strip()
    if not service_name:
        raise RuntimeError("Oracle Service Name이 필요합니다.")
    dsn = oracledb.makedsn(
        profile.get("host") or "127.0.0.1",
        int(profile.get("port") or 1521),
        service_name=service_name,
    )
    return oracledb.connect(
        user=profile.get("username") or "",
        password=password,
        dsn=dsn,
    )


def _resolve_sqlite_database_path(root: str, database: str) -> Path:
    project_root = Path(_project_key(root)).resolve()
    raw = str(database or "").strip().strip('"')
    if not raw:
        raise RuntimeError("SQLite DB 파일 경로가 필요합니다. 예: data/app.db")
    if raw == ":memory:":
        raise RuntimeError("SQLite :memory: 연결은 프로젝트 DB 파일 유지 목적에 맞지 않아 지원하지 않습니다.")
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = project_root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise RuntimeError("SQLite DB 파일은 현재 프로젝트 폴더 안에 있어야 합니다.") from exc
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def _connect_sqlite(root: str, profile: dict[str, Any]):
    database_path = _resolve_sqlite_database_path(root, str(profile.get("database") or ""))
    conn = sqlite3.connect(str(database_path), timeout=8, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    profile["database"] = str(database_path)
    return conn


def _ping_connection(conn: Any, db_type: str) -> None:
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT 1 FROM DUAL" if db_type == "oracle" else "SELECT 1")
        cursor.fetchone()
    finally:
        try:
            cursor.close()
        except Exception:
            pass


def _remember_database_history(root: str, profile: dict[str, Any]) -> None:
    db_type = str(profile.get("db_type") or "").strip().lower()
    if db_type not in {"postgresql", "mssql"}:
        return
    host = str(profile.get("host") or "").strip()
    database = str(profile.get("database") or "").strip()
    if not host or not database:
        return
    try:
        port = int(profile.get("port") or 0)
    except Exception:
        port = 0
    row = {
        "db_type": db_type,
        "host": host,
        "port": port,
        "database": database,
        "username": str(profile.get("username") or "").strip(),
        "last_connected_at": datetime.now().isoformat(timespec="seconds"),
    }
    key = _project_key(root)
    with _LOCK:
        profiles = _load_profiles()
        entry = profiles.setdefault(key, {"active_connection_id": "", "connections": {}, "database_history": [], "updated_at": None})
        history = _normalize_database_history(entry.get("database_history"))
        identity = (db_type, host.casefold(), port, database.casefold())
        history = [item for item in history if (
            str(item.get("db_type") or "").lower(),
            str(item.get("host") or "").casefold(),
            int(item.get("port") or 0),
            str(item.get("database") or "").casefold(),
        ) != identity]
        entry["database_history"] = [row, *history][:100]
        entry["updated_at"] = row["last_connected_at"]
        _write_profiles(profiles)


def connect(root: str, profile: dict[str, Any], password: str = "") -> dict[str, Any]:
    key = _project_key(root)
    clean = _sanitized_profile(profile)
    supplied_password = str(password or "")
    if not clean.get("database") and clean["db_type"] != "oracle":
        raise RuntimeError("SQLite DB 파일 경로가 필요합니다." if clean["db_type"] == "sqlite3" else "Database 이름이 필요합니다.")
    if clean["db_type"] != "sqlite3" and not clean.get("username"):
        raise RuntimeError("사용자 이름이 필요합니다.")

    saved = save_profile(root, clean, password=supplied_password if supplied_password else None)
    cid = str(saved.get("connection_id") or "")
    effective_password = supplied_password
    if clean["db_type"] != "sqlite3" and not effective_password and saved.get("credential_saved"):
        effective_password = _stored_password(root, cid)

    if clean["db_type"] == "sqlite3":
        conn = _connect_sqlite(root, saved)
    elif clean["db_type"] == "mssql":
        conn = _connect_mssql(saved, effective_password)
    elif clean["db_type"] == "oracle":
        conn = _connect_oracle(saved, effective_password)
    else:
        conn = _connect_postgresql(saved, effective_password)

    try:
        _ping_connection(conn, clean["db_type"])
    except Exception:
        try:
            conn.close()
        except Exception:
            pass
        raise

    _remember_database_history(root, saved)

    runtime = {
        "connection": conn,
        "profile": saved,
        "connected_at": datetime.now().isoformat(timespec="seconds"),
        "password_in_memory": bool(effective_password),
    }
    with _LOCK:
        bucket = _runtime_bucket(key, create=True)
        old = bucket.pop(cid, None)
        bucket[cid] = runtime
        _ACTIVE_RUNTIME[key] = cid
    _close_connection(old)
    return status(root)


def _runtime_is_alive(runtime: dict[str, Any]) -> bool:
    try:
        _ping_connection(runtime.get("connection"), runtime.get("profile", {}).get("db_type", "postgresql"))
        return True
    except Exception:
        return False


def status(root: str, *, verify: bool = False) -> dict[str, Any]:
    key = _project_key(root)
    with _LOCK:
        profiles = _load_profiles()
        entry = _saved_entry(key, profiles)
        active_id = str(_ACTIVE_RUNTIME.get(key) or entry.get("active_connection_id") or "")
        runtime = _runtime_bucket(key).get(active_id) if active_id else None

    # Only ping the selected connection. A project may intentionally keep many
    # database sessions open; verifying every server on each UI refresh would
    # make status checks scale with network timeout. Each connection is verified
    # when it becomes active instead.
    if verify and runtime and not _runtime_is_alive(runtime):
        with _LOCK:
            stale = _runtime_bucket(key).pop(active_id, None)
        _close_connection(stale)
        runtime = None

    with _LOCK:
        stored = (entry.get("connections") or {}).get(active_id) if active_id else None

    active_profile = _public_profile(runtime.get("profile")) if runtime else (_public_profile(stored) if stored else get_profile(root))
    storage = profile_storage_info(root)
    connections_payload = list_profiles(root)
    return {
        "ok": True,
        "connected": bool(runtime and runtime.get("connection") is not None),
        "connected_at": runtime.get("connected_at") if runtime else None,
        "password_in_memory": bool(runtime and runtime.get("password_in_memory")),
        "profile": active_profile,
        "project_root": os.path.abspath(str(root)),
        "profile_storage_path": storage["storage_path"],
        "saved_db_types": storage["saved_db_types"],
        "active_connection_id": active_id,
        "password_persisted": storage["password_persisted"],
        "credential_storage": storage["credential_storage"],
        "connections": connections_payload["connections"],
        "saved_connection_count": connections_payload["saved_connection_count"],
        "connected_connection_count": connections_payload["connected_connection_count"],
        "database_history": connections_payload.get("database_history", []),
    }


def _require_active_runtime(root: str) -> dict[str, Any]:
    _cid, runtime = _get_active_runtime(root)
    if not runtime or runtime.get("connection") is None:
        raise RuntimeError("현재 선택된 데이터베이스가 연결되어 있지 않습니다. 우측 DB 연결 탭에서 연결을 선택한 뒤 연결하세요.")
    return runtime



def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date, dt_time)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        raw = bytes(value)
        return "0x" + raw.hex()
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    return str(value)


def _split_sql_by_semicolon(statement: str) -> list[str]:
    """Split SQL on top-level semicolons while preserving quoted/comment blocks.

    This is intentionally lightweight rather than a full SQL parser, but it
    protects the common cases needed by the SQL Workspace: quoted strings,
    identifiers, line/block comments, and PostgreSQL dollar-quoted bodies.
    """
    text = str(statement or "")
    parts: list[str] = []
    buf: list[str] = []
    i = 0
    quote: str | None = None
    line_comment = False
    block_comment = False
    dollar_tag: str | None = None

    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if line_comment:
            buf.append(ch)
            if ch == "\n":
                line_comment = False
            i += 1
            continue

        if block_comment:
            buf.append(ch)
            if ch == "*" and nxt == "/":
                buf.append(nxt)
                i += 2
                block_comment = False
            else:
                i += 1
            continue

        if dollar_tag is not None:
            if text.startswith(dollar_tag, i):
                buf.append(dollar_tag)
                i += len(dollar_tag)
                dollar_tag = None
            else:
                buf.append(ch)
                i += 1
            continue

        if quote is not None:
            buf.append(ch)
            if ch == quote:
                # SQL escapes quote characters by doubling them.
                if nxt == quote:
                    buf.append(nxt)
                    i += 2
                    continue
                quote = None
            elif ch == "\\" and quote in {"'", '"'} and nxt:
                # Be tolerant of clients/dialects that use backslash escapes.
                buf.append(nxt)
                i += 2
                continue
            i += 1
            continue

        if ch == "-" and nxt == "-":
            buf.extend((ch, nxt))
            i += 2
            line_comment = True
            continue
        if ch == "/" and nxt == "*":
            buf.extend((ch, nxt))
            i += 2
            block_comment = True
            continue
        if ch in {"'", '"', "`"}:
            quote = ch
            buf.append(ch)
            i += 1
            continue
        if ch == "[":
            quote = "]"
            buf.append(ch)
            i += 1
            continue
        if ch == "$":
            # PostgreSQL dollar quotes: $$...$$ or $tag$...$tag$.
            j = i + 1
            while j < len(text) and (text[j].isalnum() or text[j] == "_"):
                j += 1
            if j < len(text) and text[j] == "$":
                tag = text[i:j + 1]
                dollar_tag = tag
                buf.append(tag)
                i = j + 1
                continue
        if ch == ";":
            piece = "".join(buf).strip()
            if piece:
                parts.append(piece)
            buf = []
            i += 1
            continue

        buf.append(ch)
        i += 1

    tail = "".join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _sqlite_line_dml_statements(statement: str) -> list[str]:
    """Recognize pasted/selected one-line SQLite DML without semicolons.

    Users frequently select several INSERT/UPDATE/DELETE/REPLACE lines in the
    editor. SQLite cursor.execute() cannot consume those as one statement. If
    every meaningful line is independently complete when terminated with a
    semicolon, we can safely execute the lines one-by-one without rewriting
    multi-line SELECT/CREATE statements.
    """
    candidates: list[str] = []
    allowed = ("INSERT ", "UPDATE ", "DELETE ", "REPLACE ")
    for raw in str(statement or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("--"):
            continue
        upper = line.upper()
        if not upper.startswith(allowed):
            return []
        try:
            if not sqlite3.complete_statement(line.rstrip(";") + ";"):
                return []
        except Exception:
            return []
        candidates.append(line.rstrip(";").strip())
    return candidates if len(candidates) > 1 else []


def _split_sql_statements(statement: str, db_type: str) -> list[str]:
    parts = _split_sql_by_semicolon(statement)
    if len(parts) > 1:
        return parts
    if str(db_type or "").lower() == "sqlite3":
        inferred = _sqlite_line_dml_statements(statement)
        if inferred:
            return inferred
    return parts or [str(statement or "").strip()]


def execute(root: str, sql: str, max_rows: int = 1000) -> dict[str, Any]:
    statement = str(sql or "")
    if not statement.strip():
        raise RuntimeError("실행할 SQL이 없습니다.")

    max_rows = max(1, min(int(max_rows or 1000), 10000))
    runtime = _require_active_runtime(root)
    conn = runtime["connection"]
    db_type = str(runtime.get("profile", {}).get("db_type", "") or "").lower()
    statements = [item for item in _split_sql_statements(statement, db_type) if item.strip()]
    if not statements:
        raise RuntimeError("실행할 SQL이 없습니다.")

    started = time.perf_counter()
    cursor = conn.cursor()
    execution_key = _project_key(root)
    with _LOCK:
        _ACTIVE_EXECUTIONS[execution_key] = {
            "connection": conn,
            "cursor": cursor,
            "db_type": db_type,
            "started_at": time.time(),
        }
    try:
        columns: list[str] = []
        rows: list[list[Any]] = []
        truncated = False
        total_affected = 0
        total_selected = 0
        statement_results: list[dict[str, Any]] = []

        for index, current in enumerate(statements, start=1):
            try:
                cursor.execute(current)
            except Exception as exc:
                snippet = " ".join(current.strip().split())[:180]
                raise RuntimeError(
                    f"{index}번째 SQL 실행 실패: {exc} | SQL: {snippet}"
                ) from exc

            affected = cursor.rowcount if getattr(cursor, "rowcount", None) is not None else -1
            item_columns: list[str] = []
            item_rows: list[list[Any]] = []
            item_truncated = False
            item_row_count = 0

            if cursor.description:
                item_columns = [str(col[0]) for col in cursor.description]
                fetched = cursor.fetchmany(max_rows + 1)
                if len(fetched) > max_rows:
                    item_truncated = True
                    fetched = fetched[:max_rows]
                item_rows = [[_json_safe(cell) for cell in row] for row in fetched]
                item_row_count = len(item_rows)
                total_selected += item_row_count
                # Data Output shows the most recent result set, like common DB tools.
                columns = item_columns
                rows = item_rows
                truncated = item_truncated
            else:
                item_affected = max(0, int(affected or 0))
                total_affected += item_affected

            statement_results.append({
                "index": index,
                "sql": " ".join(current.strip().split())[:500],
                "columns": item_columns,
                "row_count": item_row_count,
                "affected_rows": max(0, int(affected or 0)),
                "truncated": item_truncated,
            })

        try:
            conn.commit()
        except Exception:
            pass

        if len(statements) == 1 and columns:
            row_count = len(rows)
            message = f"{row_count:,}개 행을 조회했습니다."
            if truncated:
                message += f" 최대 {max_rows:,}행까지만 표시합니다."
        elif len(statements) == 1:
            row_count = total_affected
            message = f"SQL 실행 완료 · 영향받은 행 {total_affected:,}개"
        else:
            row_count = len(rows) if columns else total_affected
            message = f"SQL {len(statements):,}개 실행 완료"
            if total_affected:
                message += f" · 영향받은 행 {total_affected:,}개"
            if total_selected:
                message += f" · 조회 행 {total_selected:,}개"
            if columns:
                message += " · Data Output에는 마지막 조회 결과를 표시합니다."
            if truncated:
                message += f" 최대 {max_rows:,}행까지만 표시합니다."

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return {
            "ok": True,
            "columns": columns,
            "rows": rows,
            "row_count": row_count,
            "affected_rows": total_affected,
            "truncated": truncated,
            "elapsed_ms": elapsed_ms,
            "message": message,
            "db_type": db_type,
            "statement_count": len(statements),
            "statement_results": statement_results,
        }
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        with _LOCK:
            current = _ACTIVE_EXECUTIONS.get(execution_key)
            if current and current.get("cursor") is cursor:
                _ACTIVE_EXECUTIONS.pop(execution_key, None)
        try:
            cursor.close()
        except Exception:
            pass


def cancel_execution(root: str) -> dict[str, Any]:
    """Best-effort cancellation of the currently running SQL for a project."""
    key = _project_key(root)
    with _LOCK:
        active = _ACTIVE_EXECUTIONS.get(key)
    if not active:
        return {"ok": True, "cancelled": False, "message": "현재 실행 중인 SQL이 없습니다."}

    conn = active.get("connection")
    cursor = active.get("cursor")
    attempts: list[str] = []
    errors: list[str] = []

    # pyodbc and some DB-API cursors expose cancel().
    cancel_cursor = getattr(cursor, "cancel", None)
    if callable(cancel_cursor):
        try:
            cancel_cursor()
            attempts.append("cursor.cancel")
        except Exception as exc:
            errors.append(f"cursor.cancel: {exc}")

    # psycopg / oracledb connections may expose cancel().
    cancel_conn = getattr(conn, "cancel", None)
    if callable(cancel_conn):
        try:
            cancel_conn()
            attempts.append("connection.cancel")
        except Exception as exc:
            errors.append(f"connection.cancel: {exc}")

    # sqlite3 exposes interrupt() for a query running on another thread.
    interrupt_conn = getattr(conn, "interrupt", None)
    if callable(interrupt_conn):
        try:
            interrupt_conn()
            attempts.append("connection.interrupt")
        except Exception as exc:
            errors.append(f"connection.interrupt: {exc}")

    return {
        "ok": bool(attempts),
        "cancelled": bool(attempts),
        "methods": attempts,
        "errors": errors,
        "db_type": active.get("db_type") or "",
        "message": "SQL 실행 중지 요청을 보냈습니다." if attempts else "현재 DB 드라이버에서 실행 중지 기능을 호출하지 못했습니다.",
    }


def _metadata_rows(conn: Any, statement: str) -> list[tuple[Any, ...]]:
    cursor = conn.cursor()
    try:
        cursor.execute(statement)
        return list(cursor.fetchall() or [])
    finally:
        try:
            cursor.close()
        except Exception:
            pass


def _new_schema_bucket(name: str) -> dict[str, Any]:
    return {
        "name": str(name or "default"),
        "tables": [],
        "views": [],
        "procedures": [],
        "functions": [],
        "sequences": [],
        "triggers": [],
        "indexes": [],
        "packages": [],
    }


def _qualified_name(schema: str, name: str) -> str:
    schema = str(schema or "").strip()
    name = str(name or "").strip()
    return f"{schema}.{name}" if schema else name


def _append_object(
    schemas: dict[str, dict[str, Any]],
    schema: str,
    category: str,
    name: str,
    **extra: Any,
) -> dict[str, Any]:
    schema_name = str(schema or "default")
    bucket = schemas.setdefault(schema_name, _new_schema_bucket(schema_name))
    item = {
        "name": str(name or ""),
        "schema": schema_name,
        "qualified_name": _qualified_name(schema_name, str(name or "")),
        **{k: _json_safe(v) for k, v in extra.items() if v is not None},
    }
    bucket.setdefault(category, []).append(item)
    return item


def _postgresql_objects(conn: Any) -> dict[str, dict[str, Any]]:
    schemas: dict[str, dict[str, Any]] = {}

    for schema, name in _metadata_rows(conn, """
        SELECT table_schema, table_name
          FROM information_schema.tables
         WHERE table_type = 'BASE TABLE'
           AND table_schema NOT IN ('pg_catalog', 'information_schema')
         ORDER BY table_schema, table_name
    """):
        _append_object(schemas, schema, "tables", name, columns=[])

    for schema, name in _metadata_rows(conn, """
        SELECT table_schema, table_name
          FROM information_schema.views
         WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
         ORDER BY table_schema, table_name
    """):
        _append_object(schemas, schema, "views", name, columns=[])

    object_index: dict[tuple[str, str], dict[str, Any]] = {}
    for bucket in schemas.values():
        for category in ("tables", "views"):
            for item in bucket.get(category, []):
                object_index[(item["schema"], item["name"])] = item

    for schema, table_name, column_name, data_type, nullable, ordinal in _metadata_rows(conn, """
        SELECT table_schema, table_name, column_name, data_type, is_nullable, ordinal_position
          FROM information_schema.columns
         WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
         ORDER BY table_schema, table_name, ordinal_position
    """):
        item = object_index.get((str(schema), str(table_name)))
        if item is not None:
            item.setdefault("columns", []).append({
                "name": str(column_name),
                "data_type": str(data_type),
                "nullable": str(nullable).upper() == "YES",
                "ordinal": int(ordinal or 0),
            })

    try:
        routines = _metadata_rows(conn, """
            SELECT n.nspname,
                   p.proname,
                   CASE WHEN p.prokind = 'p' THEN 'procedure' ELSE 'function' END,
                   pg_get_function_identity_arguments(p.oid)
              FROM pg_proc p
              JOIN pg_namespace n ON n.oid = p.pronamespace
             WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
               AND p.prokind IN ('p', 'f')
             ORDER BY n.nspname, p.prokind, p.proname
        """)
    except Exception:
        # PostgreSQL 10 이하 호환 fallback (prokind가 없음)
        try:
            conn.rollback()
        except Exception:
            pass
        routines = [(*row, "function", "") for row in _metadata_rows(conn, """
            SELECT n.nspname, p.proname
              FROM pg_proc p
              JOIN pg_namespace n ON n.oid = p.pronamespace
             WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
             ORDER BY n.nspname, p.proname
        """)]

    for schema, name, kind, arguments in routines:
        category = "procedures" if str(kind) == "procedure" else "functions"
        _append_object(schemas, schema, category, name, arguments=str(arguments or ""))

    for schema, name in _metadata_rows(conn, """
        SELECT sequence_schema, sequence_name
          FROM information_schema.sequences
         WHERE sequence_schema NOT IN ('pg_catalog', 'information_schema')
         ORDER BY sequence_schema, sequence_name
    """):
        _append_object(schemas, schema, "sequences", name)

    for schema, table_name, trigger_name, event_name in _metadata_rows(conn, """
        SELECT trigger_schema, event_object_table, trigger_name, event_manipulation
          FROM information_schema.triggers
         WHERE trigger_schema NOT IN ('pg_catalog', 'information_schema')
         ORDER BY trigger_schema, event_object_table, trigger_name
    """):
        _append_object(schemas, schema, "triggers", trigger_name, table=str(table_name), event=str(event_name))

    return schemas


def _mssql_objects(conn: Any) -> dict[str, dict[str, Any]]:
    schemas: dict[str, dict[str, Any]] = {}

    for schema, name in _metadata_rows(conn, """
        SELECT s.name, t.name
          FROM sys.tables t
          JOIN sys.schemas s ON s.schema_id = t.schema_id
         WHERE t.is_ms_shipped = 0
         ORDER BY s.name, t.name
    """):
        _append_object(schemas, schema, "tables", name, columns=[])

    for schema, name in _metadata_rows(conn, """
        SELECT s.name, v.name
          FROM sys.views v
          JOIN sys.schemas s ON s.schema_id = v.schema_id
         WHERE v.is_ms_shipped = 0
         ORDER BY s.name, v.name
    """):
        _append_object(schemas, schema, "views", name, columns=[])

    object_index: dict[tuple[str, str], dict[str, Any]] = {}
    for bucket in schemas.values():
        for category in ("tables", "views"):
            for item in bucket.get(category, []):
                object_index[(item["schema"], item["name"])] = item

    for schema, obj_name, column_name, data_type, nullable, ordinal in _metadata_rows(conn, """
        SELECT s.name,
               o.name,
               c.name,
               ty.name,
               c.is_nullable,
               c.column_id
          FROM sys.objects o
          JOIN sys.schemas s ON s.schema_id = o.schema_id
          JOIN sys.columns c ON c.object_id = o.object_id
          JOIN sys.types ty ON ty.user_type_id = c.user_type_id
         WHERE o.type IN ('U', 'V')
           AND o.is_ms_shipped = 0
         ORDER BY s.name, o.name, c.column_id
    """):
        item = object_index.get((str(schema), str(obj_name)))
        if item is not None:
            item.setdefault("columns", []).append({
                "name": str(column_name),
                "data_type": str(data_type),
                "nullable": bool(nullable),
                "ordinal": int(ordinal or 0),
            })

    for schema, name in _metadata_rows(conn, """
        SELECT s.name, p.name
          FROM sys.procedures p
          JOIN sys.schemas s ON s.schema_id = p.schema_id
         WHERE p.is_ms_shipped = 0
         ORDER BY s.name, p.name
    """):
        _append_object(schemas, schema, "procedures", name)

    for schema, name, obj_type in _metadata_rows(conn, """
        SELECT s.name, o.name, o.type_desc
          FROM sys.objects o
          JOIN sys.schemas s ON s.schema_id = o.schema_id
         WHERE o.type IN ('FN', 'IF', 'TF', 'FS', 'FT')
           AND o.is_ms_shipped = 0
         ORDER BY s.name, o.name
    """):
        _append_object(schemas, schema, "functions", name, object_type=str(obj_type))

    for schema, name in _metadata_rows(conn, """
        SELECT s.name, seq.name
          FROM sys.sequences seq
          JOIN sys.schemas s ON s.schema_id = seq.schema_id
         ORDER BY s.name, seq.name
    """):
        _append_object(schemas, schema, "sequences", name)

    for schema, parent_name, trigger_name in _metadata_rows(conn, """
        SELECT s.name, COALESCE(o.name, ''), tr.name
          FROM sys.triggers tr
          LEFT JOIN sys.objects o ON o.object_id = tr.parent_id
          LEFT JOIN sys.schemas s ON s.schema_id = o.schema_id
         WHERE tr.is_ms_shipped = 0
         ORDER BY s.name, o.name, tr.name
    """):
        _append_object(schemas, schema or "database", "triggers", trigger_name, table=str(parent_name or ""))

    return schemas


def _oracle_objects(conn: Any, username: str) -> dict[str, dict[str, Any]]:
    schema_name = str(username or "USER").upper()
    schemas: dict[str, dict[str, Any]] = {schema_name: _new_schema_bucket(schema_name)}

    for (name,) in _metadata_rows(conn, "SELECT table_name FROM user_tables ORDER BY table_name"):
        _append_object(schemas, schema_name, "tables", name, columns=[])
    for (name,) in _metadata_rows(conn, "SELECT view_name FROM user_views ORDER BY view_name"):
        _append_object(schemas, schema_name, "views", name, columns=[])

    object_index: dict[str, dict[str, Any]] = {}
    for category in ("tables", "views"):
        for item in schemas[schema_name].get(category, []):
            object_index[item["name"]] = item

    for table_name, column_name, data_type, nullable, ordinal in _metadata_rows(conn, """
        SELECT table_name, column_name, data_type, nullable, column_id
          FROM user_tab_columns
         ORDER BY table_name, column_id
    """):
        item = object_index.get(str(table_name))
        if item is not None:
            item.setdefault("columns", []).append({
                "name": str(column_name),
                "data_type": str(data_type),
                "nullable": str(nullable).upper() == "Y",
                "ordinal": int(ordinal or 0),
            })

    for name, obj_type in _metadata_rows(conn, """
        SELECT object_name, object_type
          FROM user_objects
         WHERE object_type IN ('PROCEDURE', 'FUNCTION', 'PACKAGE', 'SEQUENCE')
         ORDER BY object_type, object_name
    """):
        kind = str(obj_type).upper()
        category = {
            "PROCEDURE": "procedures",
            "FUNCTION": "functions",
            "PACKAGE": "packages",
            "SEQUENCE": "sequences",
        }.get(kind)
        if category:
            _append_object(schemas, schema_name, category, name, object_type=kind)

    for trigger_name, table_name, trigger_type, event_name in _metadata_rows(conn, """
        SELECT trigger_name, table_name, trigger_type, triggering_event
          FROM user_triggers
         ORDER BY table_name, trigger_name
    """):
        _append_object(
            schemas,
            schema_name,
            "triggers",
            trigger_name,
            table=str(table_name or ""),
            trigger_type=str(trigger_type or ""),
            event=str(event_name or ""),
        )

    return schemas


def _sqlite_objects(conn: Any) -> dict[str, dict[str, Any]]:
    schema_name = "main"
    schemas: dict[str, dict[str, Any]] = {schema_name: _new_schema_bucket(schema_name)}
    object_index: dict[str, dict[str, Any]] = {}

    for name, obj_type in _metadata_rows(conn, """
        SELECT name, type
          FROM sqlite_master
         WHERE type IN ('table', 'view')
           AND name NOT LIKE 'sqlite_%'
         ORDER BY type, name
    """):
        category = "tables" if str(obj_type) == "table" else "views"
        item = _append_object(schemas, schema_name, category, name, columns=[])
        object_index[str(name)] = item

    for object_name, item in list(object_index.items()):
        escaped = object_name.replace('"', '""')
        try:
            rows = _metadata_rows(conn, f'PRAGMA table_info("{escaped}")')
        except Exception:
            rows = []
        for cid, column_name, data_type, not_null, default_value, primary_key in rows:
            item.setdefault("columns", []).append({
                "name": str(column_name),
                "data_type": str(data_type or ""),
                "nullable": not bool(not_null),
                "ordinal": int(cid or 0) + 1,
                "primary_key": bool(primary_key),
                "default": _json_safe(default_value),
            })

    for name, table_name in _metadata_rows(conn, """
        SELECT name, tbl_name
          FROM sqlite_master
         WHERE type = 'index'
           AND name NOT LIKE 'sqlite_%'
         ORDER BY tbl_name, name
    """):
        _append_object(schemas, schema_name, "indexes", name, table=str(table_name or ""))

    for name, table_name in _metadata_rows(conn, """
        SELECT name, tbl_name
          FROM sqlite_master
         WHERE type = 'trigger'
         ORDER BY tbl_name, name
    """):
        _append_object(schemas, schema_name, "triggers", name, table=str(table_name or ""))

    return schemas


def _project_sqlite_python_status(project_root: Path) -> dict[str, Any]:
    candidates = [
        project_root / ".venv" / "Scripts" / "python.exe",
        project_root / "venv" / "Scripts" / "python.exe",
        project_root / ".venv" / "bin" / "python",
        project_root / "venv" / "bin" / "python",
    ]
    for executable in candidates:
        if not executable.exists():
            continue
        try:
            result = subprocess.run(
                [str(executable), "-c", "import sqlite3; print(sqlite3.sqlite_version)"],
                capture_output=True,
                text=True,
                timeout=5,
                encoding="utf-8",
                errors="replace",
            )
            return {
                "found": True,
                "python": str(executable),
                "sqlite3_available": result.returncode == 0,
                "sqlite_version": (result.stdout or "").strip() if result.returncode == 0 else "",
                "error": (result.stderr or "").strip() if result.returncode != 0 else "",
            }
        except Exception as exc:
            return {"found": True, "python": str(executable), "sqlite3_available": False, "sqlite_version": "", "error": str(exc)}
    return {"found": False, "python": "", "sqlite3_available": None, "sqlite_version": "", "error": "프로젝트 가상환경 Python을 찾지 못했습니다."}


def _project_node_sqlite_packages(project_root: Path) -> list[dict[str, str]]:
    package_json = project_root / "package.json"
    if not package_json.exists():
        return []
    try:
        payload = json.loads(package_json.read_text(encoding="utf-8-sig"))
    except Exception:
        return []
    found: list[dict[str, str]] = []
    for section in ("dependencies", "devDependencies", "optionalDependencies"):
        deps = payload.get(section) or {}
        for package_name in ("sqlite3", "better-sqlite3", "@libsql/client"):
            if package_name in deps:
                found.append({"name": package_name, "version": str(deps[package_name]), "section": section})
    return found


def _find_project_sqlite_files(project_root: Path, limit: int = 100) -> list[str]:
    skip_dirs = {"node_modules", ".git", ".venv", "venv", "dist", "build", "coverage", ".next", "__pycache__"}
    suffixes = {".db", ".sqlite", ".sqlite3", ".db3"}
    results: list[str] = []
    try:
        for current_root, dirs, files in os.walk(project_root):
            dirs[:] = [name for name in dirs if name not in skip_dirs]
            base = Path(current_root)
            for filename in files:
                if Path(filename).suffix.lower() not in suffixes:
                    continue
                full_path = base / filename
                try:
                    results.append(full_path.relative_to(project_root).as_posix())
                except Exception:
                    continue
                if len(results) >= limit:
                    return sorted(results, key=str.lower)
    except Exception:
        pass
    return sorted(results, key=str.lower)


def sqlite_project_status(root: str) -> dict[str, Any]:
    project_root = Path(_project_key(root)).resolve()
    try:
        runtime_version = sqlite3.sqlite_version
        runtime_available = True
        runtime_error = ""
    except Exception as exc:
        runtime_version = ""
        runtime_available = False
        runtime_error = str(exc)
    project_python = _project_sqlite_python_status(project_root)
    node_packages = _project_node_sqlite_packages(project_root)
    db_files = _find_project_sqlite_files(project_root)
    return {
        "ok": True,
        "project_root": str(project_root),
        "agentstudio_python": {
            "available": runtime_available,
            "sqlite_version": runtime_version,
            "message": "Python sqlite3 표준 모듈 사용 가능" if runtime_available else runtime_error,
        },
        "project_python": project_python,
        "node_packages": node_packages,
        "sqlite_cli": shutil.which("sqlite3") or "",
        "database_files": db_files,
        "recommended_database": db_files[0] if db_files else "data/app.db",
        "note": "AgentStudio SQL Workspace의 SQLite3 연결은 Python 표준 sqlite3 모듈을 사용하므로 별도 pip 설치가 필요하지 않습니다.",
    }


def list_database_objects(root: str) -> dict[str, Any]:
    runtime = _require_active_runtime(root)
    conn = runtime["connection"]
    profile = _sanitized_profile(runtime.get("profile"))
    db_type = profile.get("db_type", "postgresql")

    if db_type == "sqlite3":
        schemas_map = _sqlite_objects(conn)
    elif db_type == "mssql":
        schemas_map = _mssql_objects(conn)
    elif db_type == "oracle":
        schemas_map = _oracle_objects(conn, str(profile.get("username") or ""))
    else:
        schemas_map = _postgresql_objects(conn)

    schemas = list(schemas_map.values())
    schemas.sort(key=lambda item: str(item.get("name") or "").lower())
    category_names = ("tables", "views", "procedures", "functions", "sequences", "triggers", "indexes", "packages")
    counts = {category: 0 for category in category_names}
    for schema in schemas:
        for category in category_names:
            items = schema.get(category, []) or []
            items.sort(key=lambda item: str(item.get("name") or "").lower())
            counts[category] += len(items)

    return {
        "ok": True,
        "db_type": db_type,
        "database": profile.get("database") or profile.get("service_name") or "",
        "schemas": schemas,
        "counts": counts,
        "refreshed_at": datetime.now().isoformat(timespec="seconds"),
    }




def _scratch_safe_name(value: str) -> str:
    text = ''.join(ch if ch.isalnum() or ch in ('-', '_') else '_' for ch in str(value or '').strip())
    return (text.strip('._') or 'object')[:80]


def _quoted_identifier(db_type: str, value: str) -> str:
    text = str(value or '')
    if db_type == 'mssql':
        return '[' + text.replace(']', ']]') + ']'
    return '"' + text.replace('"', '""') + '"'


def _qualified_object_name(db_type: str, schema: str, name: str) -> str:
    qname = _quoted_identifier(db_type, name)
    schema_text = str(schema or '').strip()
    return f'{_quoted_identifier(db_type, schema_text)}.{qname}' if schema_text else qname


def _find_database_object(root: str, schema: str, category: str, name: str) -> tuple[dict[str, Any], dict[str, Any], str]:
    objects = list_database_objects(root)
    wanted_schema = str(schema or '')
    wanted_category = str(category or '').strip().lower()
    wanted_name = str(name or '')
    allowed = {'tables', 'views', 'procedures', 'functions', 'sequences', 'triggers', 'indexes', 'packages'}
    if wanted_category not in allowed:
        raise ValueError(f'지원하지 않는 DB 객체 종류입니다: {wanted_category}')
    for schema_item in objects.get('schemas', []) or []:
        if str(schema_item.get('name') or '') != wanted_schema:
            continue
        for item in schema_item.get(wanted_category, []) or []:
            if str(item.get('name') or '') == wanted_name:
                return objects, item, wanted_category
    raise ValueError(f'DB 객체를 찾을 수 없습니다: {wanted_schema}.{wanted_name} ({wanted_category})')


def _postgresql_edit_script(conn: Any, schema: str, category: str, item: dict[str, Any]) -> str:
    name = str(item.get('name') or '')
    schema_lit = schema.replace("'", "''")
    name_lit = name.replace("'", "''")
    if category in {'procedures', 'functions'}:
        args = str(item.get('arguments') or '').replace("'", "''")
        rows = _metadata_rows(conn, f"""
            SELECT pg_get_functiondef(p.oid)
              FROM pg_proc p
              JOIN pg_namespace n ON n.oid = p.pronamespace
             WHERE n.nspname = '{schema_lit}'
               AND p.proname = '{name_lit}'
               AND pg_get_function_identity_arguments(p.oid) = '{args}'
             ORDER BY p.oid LIMIT 1
        """)
        return str(rows[0][0] or '') if rows else ''
    if category == 'views':
        rows = _metadata_rows(conn, f"""
            SELECT pg_get_viewdef(c.oid, true)
              FROM pg_class c
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE n.nspname = '{schema_lit}' AND c.relname = '{name_lit}'
             LIMIT 1
        """)
        body = str(rows[0][0] or '') if rows else ''
        return f'CREATE OR REPLACE VIEW {_qualified_object_name("postgresql", schema, name)} AS\n{body.rstrip(";")};\n' if body else ''
    if category == 'triggers':
        rows = _metadata_rows(conn, f"""
            SELECT pg_get_triggerdef(t.oid, true)
              FROM pg_trigger t
              JOIN pg_class c ON c.oid = t.tgrelid
              JOIN pg_namespace n ON n.oid = c.relnamespace
             WHERE NOT t.tgisinternal AND n.nspname = '{schema_lit}' AND t.tgname = '{name_lit}'
             LIMIT 1
        """)
        return str(rows[0][0] or '').rstrip(';') + ';\n' if rows else ''
    if category == 'indexes':
        rows = _metadata_rows(conn, f"""
            SELECT pg_get_indexdef(i.indexrelid)
              FROM pg_index i
              JOIN pg_class idx ON idx.oid = i.indexrelid
              JOIN pg_namespace n ON n.oid = idx.relnamespace
             WHERE n.nspname = '{schema_lit}' AND idx.relname = '{name_lit}'
             LIMIT 1
        """)
        return str(rows[0][0] or '').rstrip(';') + ';\n' if rows else ''
    if category == 'sequences':
        return f'-- 필요한 값으로 수정하세요.\nALTER SEQUENCE {_qualified_object_name("postgresql", schema, name)} RESTART WITH 1;\n'
    return ''


def _mssql_edit_script(conn: Any, schema: str, category: str, item: dict[str, Any]) -> str:
    name = str(item.get('name') or '')
    if category in {'procedures', 'functions', 'views', 'triggers'}:
        full_name = f'{_quoted_identifier("mssql", schema)}.{_quoted_identifier("mssql", name)}'
        literal = full_name.replace("'", "''")
        rows = _metadata_rows(conn, f"SELECT OBJECT_DEFINITION(OBJECT_ID(N'{literal}'))")
        if rows and rows[0][0]:
            definition = str(rows[0][0]).rstrip()
            # SQL Server 객체 편집은 CREATE OR ALTER가 가장 안전합니다.
            upper = definition.upper()
            if upper.startswith('CREATE PROCEDURE'):
                definition = 'CREATE OR ALTER' + definition[len('CREATE'):]
            elif upper.startswith('CREATE PROC'):
                definition = 'CREATE OR ALTER' + definition[len('CREATE'):]
            elif upper.startswith('CREATE FUNCTION'):
                definition = 'CREATE OR ALTER' + definition[len('CREATE'):]
            elif upper.startswith('CREATE VIEW'):
                definition = 'CREATE OR ALTER' + definition[len('CREATE'):]
            elif upper.startswith('CREATE TRIGGER'):
                definition = 'CREATE OR ALTER' + definition[len('CREATE'):]
            return definition + '\n'
    if category == 'sequences':
        return f'-- 필요한 값으로 수정하세요.\nALTER SEQUENCE {_qualified_object_name("mssql", schema, name)} RESTART WITH 1;\n'
    if category == 'indexes':
        table_name = str(item.get('table') or '')
        target = f'-- 대상 테이블: {_qualified_object_name("mssql", schema, table_name)}\n' if table_name else ''
        return (
            '-- 인덱스 수정은 DROP/CREATE 또는 ALTER INDEX를 사용합니다.\n'
            f'-- 대상 인덱스: {_qualified_object_name("mssql", schema, name)}\n'
            f'{target}'
            '-- 예: ALTER INDEX [index_name] ON [schema].[table] REBUILD;\n'
        )
    return ''


def _oracle_edit_script(conn: Any, schema: str, category: str, item: dict[str, Any]) -> str:
    name = str(item.get('name') or '')
    ddl_type = {
        'procedures': 'PROCEDURE', 'functions': 'FUNCTION', 'views': 'VIEW',
        'triggers': 'TRIGGER', 'sequences': 'SEQUENCE', 'packages': 'PACKAGE', 'indexes': 'INDEX',
    }.get(category)
    if not ddl_type:
        return ''
    name_lit = name.replace("'", "''")
    try:
        rows = _metadata_rows(conn, f"SELECT DBMS_METADATA.GET_DDL('{ddl_type}', '{name_lit}') FROM dual")
        if rows and rows[0][0]:
            value = rows[0][0]
            try:
                value = value.read()
            except Exception:
                pass
            return str(value).rstrip() + '\n/\n'
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    return f'-- {ddl_type} {schema}.{name} 정의를 자동으로 불러오지 못했습니다.\n-- DB 권한을 확인한 뒤 수정 SQL을 작성하세요.\n'


def _sqlite_edit_script(conn: Any, category: str, item: dict[str, Any]) -> str:
    name = str(item.get('name') or '')
    sqlite_type = {'views': 'view', 'triggers': 'trigger', 'indexes': 'index'}.get(category)
    if sqlite_type:
        name_lit = name.replace("'", "''")
        rows = _metadata_rows(conn, f"SELECT sql FROM sqlite_master WHERE type='{sqlite_type}' AND name='{name_lit}' LIMIT 1")
        if rows and rows[0][0]:
            definition = str(rows[0][0]).rstrip(';') + ';'
            quoted = _quoted_identifier('sqlite3', name)
            drop_keyword = {'view': 'VIEW', 'trigger': 'TRIGGER', 'index': 'INDEX'}[sqlite_type]
            return f'DROP {drop_keyword} IF EXISTS {quoted};\n\n{definition}\n'
    return f'-- SQLite3 {category} 객체 {name}의 수정 SQL을 작성하세요.\n'


def _build_object_edit_script(conn: Any, db_type: str, schema: str, category: str, item: dict[str, Any]) -> str:
    if db_type == 'sqlite3':
        return _sqlite_edit_script(conn, category, item)
    if db_type == 'mssql':
        return _mssql_edit_script(conn, schema, category, item)
    if db_type == 'oracle':
        return _oracle_edit_script(conn, schema, category, item)
    return _postgresql_edit_script(conn, schema, category, item)



def _postgresql_table_ddl(conn: Any, schema: str, name: str) -> str:
    schema_lit = str(schema or '').replace("'", "''")
    name_lit = str(name or '').replace("'", "''")
    qualified = _qualified_object_name('postgresql', schema, name)
    columns = _metadata_rows(conn, f"""
        SELECT a.attname,
               pg_catalog.format_type(a.atttypid, a.atttypmod),
               pg_get_expr(ad.adbin, ad.adrelid),
               a.attnotnull,
               COALESCE(a.attidentity, ''),
               COALESCE(a.attgenerated, '')
          FROM pg_attribute a
          JOIN pg_class c ON c.oid = a.attrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
          LEFT JOIN pg_attrdef ad ON ad.adrelid = a.attrelid AND ad.adnum = a.attnum
         WHERE n.nspname = '{schema_lit}'
           AND c.relname = '{name_lit}'
           AND c.relkind IN ('r','p')
           AND a.attnum > 0
           AND NOT a.attisdropped
         ORDER BY a.attnum
    """)
    if not columns:
        raise ValueError(f'PostgreSQL 테이블 컬럼 정보를 찾을 수 없습니다: {schema}.{name}')

    definitions: list[str] = []
    for column_name, data_type, default_expr, not_null, identity_kind, generated_kind in columns:
        parts = [f'    {_quoted_identifier("postgresql", str(column_name))} {data_type}']
        identity = str(identity_kind or '')
        generated = str(generated_kind or '')
        if identity:
            parts.append('GENERATED ALWAYS AS IDENTITY' if identity == 'a' else 'GENERATED BY DEFAULT AS IDENTITY')
        elif generated and default_expr:
            parts.append(f'GENERATED ALWAYS AS ({default_expr}) STORED')
        elif default_expr:
            parts.append(f'DEFAULT {default_expr}')
        if bool(not_null):
            parts.append('NOT NULL')
        definitions.append(' '.join(parts))

    constraints = _metadata_rows(conn, f"""
        SELECT con.conname, pg_get_constraintdef(con.oid, true)
          FROM pg_constraint con
          JOIN pg_class c ON c.oid = con.conrelid
          JOIN pg_namespace n ON n.oid = c.relnamespace
         WHERE n.nspname = '{schema_lit}'
           AND c.relname = '{name_lit}'
           AND con.contype IN ('p','u','f','c','x')
         ORDER BY CASE con.contype WHEN 'p' THEN 1 WHEN 'u' THEN 2 WHEN 'f' THEN 3 ELSE 4 END, con.conname
    """)
    for constraint_name, definition in constraints:
        definitions.append(
            f'    CONSTRAINT {_quoted_identifier("postgresql", str(constraint_name))} {definition}'
        )

    ddl = f'CREATE TABLE {qualified} (\n' + ',\n'.join(definitions) + '\n);\n'

    indexes = _metadata_rows(conn, f"""
        SELECT ic.relname, pg_get_indexdef(ic.oid)
          FROM pg_class tc
          JOIN pg_namespace n ON n.oid = tc.relnamespace
          JOIN pg_index ix ON ix.indrelid = tc.oid
          JOIN pg_class ic ON ic.oid = ix.indexrelid
         WHERE n.nspname = '{schema_lit}'
           AND tc.relname = '{name_lit}'
           AND NOT ix.indisprimary
           AND NOT EXISTS (SELECT 1 FROM pg_constraint con WHERE con.conindid = ic.oid)
         ORDER BY ic.relname
    """)
    if indexes:
        ddl += '\n' + '\n'.join(str(indexdef).rstrip(';') + ';' for _, indexdef in indexes if indexdef) + '\n'
    return ddl


def _mssql_type_sql(type_name: str, max_length: int, precision: int, scale: int) -> str:
    kind = str(type_name or '').lower()
    if kind in {'varchar', 'char', 'varbinary', 'binary'}:
        size = 'MAX' if int(max_length or 0) == -1 else str(int(max_length or 0))
        return f'{type_name}({size})'
    if kind in {'nvarchar', 'nchar'}:
        raw = int(max_length or 0)
        size = 'MAX' if raw == -1 else str(max(raw // 2, 1))
        return f'{type_name}({size})'
    if kind in {'decimal', 'numeric'}:
        return f'{type_name}({int(precision or 18)},{int(scale or 0)})'
    if kind in {'datetime2', 'datetimeoffset', 'time'}:
        return f'{type_name}({int(scale or 0)})'
    return str(type_name)


def _mssql_table_ddl(conn: Any, schema: str, name: str) -> str:
    schema_lit = str(schema or '').replace("'", "''")
    name_lit = str(name or '').replace("'", "''")
    qualified = _qualified_object_name('mssql', schema, name)
    columns = _metadata_rows(conn, f"""
        SELECT c.name, ty.name, c.max_length, c.precision, c.scale, c.is_nullable,
               ic.seed_value, ic.increment_value, dc.definition, cc.definition
          FROM sys.tables t
          JOIN sys.schemas s ON s.schema_id = t.schema_id
          JOIN sys.columns c ON c.object_id = t.object_id
          JOIN sys.types ty ON ty.user_type_id = c.user_type_id
          LEFT JOIN sys.identity_columns ic ON ic.object_id = c.object_id AND ic.column_id = c.column_id
          LEFT JOIN sys.default_constraints dc ON dc.parent_object_id = c.object_id AND dc.parent_column_id = c.column_id
          LEFT JOIN sys.computed_columns cc ON cc.object_id = c.object_id AND cc.column_id = c.column_id
         WHERE s.name = N'{schema_lit}' AND t.name = N'{name_lit}'
         ORDER BY c.column_id
    """)
    if not columns:
        raise ValueError(f'MSSQL 테이블 컬럼 정보를 찾을 수 없습니다: {schema}.{name}')

    definitions: list[str] = []
    for column_name, type_name, max_length, precision, scale, nullable, seed, increment, default_expr, computed_expr in columns:
        qcol = _quoted_identifier('mssql', str(column_name))
        if computed_expr:
            definitions.append(f'    {qcol} AS {computed_expr}')
            continue
        parts = [f'    {qcol} {_mssql_type_sql(str(type_name), int(max_length or 0), int(precision or 0), int(scale or 0))}']
        if seed is not None:
            parts.append(f'IDENTITY({seed},{increment})')
        if default_expr:
            parts.append(f'DEFAULT {default_expr}')
        parts.append('NULL' if bool(nullable) else 'NOT NULL')
        definitions.append(' '.join(parts))

    keys = _metadata_rows(conn, f"""
        SELECT kc.name, kc.type,
               STRING_AGG(QUOTENAME(c.name), ', ') WITHIN GROUP (ORDER BY ic.key_ordinal)
          FROM sys.tables t
          JOIN sys.schemas s ON s.schema_id = t.schema_id
          JOIN sys.key_constraints kc ON kc.parent_object_id = t.object_id
          JOIN sys.index_columns ic ON ic.object_id = t.object_id AND ic.index_id = kc.unique_index_id
          JOIN sys.columns c ON c.object_id = t.object_id AND c.column_id = ic.column_id
         WHERE s.name = N'{schema_lit}' AND t.name = N'{name_lit}'
         GROUP BY kc.name, kc.type
         ORDER BY CASE kc.type WHEN 'PK' THEN 1 ELSE 2 END, kc.name
    """)
    for constraint_name, key_type, columns_sql in keys:
        keyword = 'PRIMARY KEY' if str(key_type) == 'PK' else 'UNIQUE'
        definitions.append(f'    CONSTRAINT {_quoted_identifier("mssql", str(constraint_name))} {keyword} ({columns_sql})')

    checks = _metadata_rows(conn, f"""
        SELECT cc.name, cc.definition
          FROM sys.tables t
          JOIN sys.schemas s ON s.schema_id = t.schema_id
          JOIN sys.check_constraints cc ON cc.parent_object_id = t.object_id
         WHERE s.name = N'{schema_lit}' AND t.name = N'{name_lit}'
         ORDER BY cc.name
    """)
    for constraint_name, definition in checks:
        definitions.append(f'    CONSTRAINT {_quoted_identifier("mssql", str(constraint_name))} CHECK {definition}')

    ddl = f'CREATE TABLE {qualified} (\n' + ',\n'.join(definitions) + '\n);\n'

    fks = _metadata_rows(conn, f"""
        SELECT fk.name, ps.name, pt.name, rs.name, rt.name,
               STRING_AGG(QUOTENAME(pc.name), ', ') WITHIN GROUP (ORDER BY fkc.constraint_column_id),
               STRING_AGG(QUOTENAME(rc.name), ', ') WITHIN GROUP (ORDER BY fkc.constraint_column_id),
               fk.delete_referential_action_desc, fk.update_referential_action_desc
          FROM sys.foreign_keys fk
          JOIN sys.foreign_key_columns fkc ON fkc.constraint_object_id = fk.object_id
          JOIN sys.tables pt ON pt.object_id = fk.parent_object_id
          JOIN sys.schemas ps ON ps.schema_id = pt.schema_id
          JOIN sys.tables rt ON rt.object_id = fk.referenced_object_id
          JOIN sys.schemas rs ON rs.schema_id = rt.schema_id
          JOIN sys.columns pc ON pc.object_id = pt.object_id AND pc.column_id = fkc.parent_column_id
          JOIN sys.columns rc ON rc.object_id = rt.object_id AND rc.column_id = fkc.referenced_column_id
         WHERE ps.name = N'{schema_lit}' AND pt.name = N'{name_lit}'
         GROUP BY fk.name, ps.name, pt.name, rs.name, rt.name,
                  fk.delete_referential_action_desc, fk.update_referential_action_desc
         ORDER BY fk.name
    """)
    for fk_name, _, _, ref_schema, ref_table, parent_cols, ref_cols, delete_action, update_action in fks:
        line = (
            f'ALTER TABLE {qualified} ADD CONSTRAINT {_quoted_identifier("mssql", str(fk_name))} '
            f'FOREIGN KEY ({parent_cols}) REFERENCES {_qualified_object_name("mssql", str(ref_schema), str(ref_table))} ({ref_cols})'
        )
        if str(delete_action) != 'NO_ACTION':
            line += ' ON DELETE ' + str(delete_action).replace('_', ' ')
        if str(update_action) != 'NO_ACTION':
            line += ' ON UPDATE ' + str(update_action).replace('_', ' ')
        ddl += '\n' + line + ';\n'
    return ddl


def _oracle_table_ddl(conn: Any, schema: str, name: str) -> str:
    schema_lit = str(schema or '').replace("'", "''").upper()
    name_lit = str(name or '').replace("'", "''").upper()
    try:
        rows = _metadata_rows(conn, f"SELECT DBMS_METADATA.GET_DDL('TABLE', '{name_lit}', '{schema_lit}') FROM dual")
        if rows and rows[0][0]:
            value = rows[0][0]
            try:
                value = value.read()
            except Exception:
                pass
            return str(value).strip() + '\n/\n'
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    raise ValueError(f'Oracle 테이블 DDL을 가져오지 못했습니다: {schema}.{name}')


def _sqlite_table_ddl(conn: Any, name: str) -> str:
    name_lit = str(name or '').replace("'", "''")
    rows = _metadata_rows(conn, f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{name_lit}' LIMIT 1")
    if not rows or not rows[0][0]:
        raise ValueError(f'SQLite 테이블 DDL을 찾을 수 없습니다: {name}')
    ddl = str(rows[0][0]).rstrip(';') + ';\n'
    indexes = _metadata_rows(conn, f"SELECT sql FROM sqlite_master WHERE type='index' AND tbl_name='{name_lit}' AND sql IS NOT NULL ORDER BY name")
    if indexes:
        ddl += '\n' + '\n'.join(str(row[0]).rstrip(';') + ';' for row in indexes if row and row[0]) + '\n'
    return ddl


def _build_table_ddl_script(conn: Any, db_type: str, schema: str, name: str) -> str:
    if db_type == 'sqlite3':
        return _sqlite_table_ddl(conn, name)
    if db_type == 'mssql':
        return _mssql_table_ddl(conn, schema, name)
    if db_type == 'oracle':
        return _oracle_table_ddl(conn, schema, name)
    return _postgresql_table_ddl(conn, schema, name)


def create_table_script(root: str, schema: str, name: str) -> dict[str, Any]:
    runtime = _require_active_runtime(root)
    objects, item, category = _find_database_object(root, schema, 'tables', name)
    if category != 'tables':
        raise ValueError('테이블 객체만 스크립트를 생성할 수 있습니다.')
    db_type = str(objects.get('db_type') or 'postgresql').lower()
    conn = runtime['connection']
    qualified = _qualified_object_name(db_type, schema, name)
    ddl = _build_table_ddl_script(conn, db_type, schema, name)

    project_root = Path(_project_key(root)).resolve()
    scratch_dir = project_root / '.agentstudio' / 'sql_scratch'
    scratch_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
    scratch_name = f'ddl_table_{_scratch_safe_name(schema)}_{_scratch_safe_name(name)}_{timestamp}.sql'
    scratch_path = scratch_dir / scratch_name
    header = (
        '-- THEANOVA AgentStudio · 테이블 스크립트 보기\n'
        f'-- DB: {db_type.upper()} · 테이블: {qualified}\n'
        f'-- 생성 시각: {datetime.now().isoformat(timespec="seconds")}\n'
        '-- 이 파일은 임시 조회용입니다. 원본 DB 객체는 변경되지 않습니다.\n\n'
    )
    content = header + ddl
    scratch_path.write_text(content, encoding='utf-8', newline='\n')
    return {
        'ok': True,
        'action': 'ddl',
        'db_type': db_type,
        'schema': schema,
        'category': 'tables',
        'name': name,
        'qualified_name': qualified,
        'relative_path': scratch_path.relative_to(project_root).as_posix(),
        'content': content,
        'message': f'{qualified} 테이블 스크립트를 임시 SQL 파일로 생성했습니다.',
    }


def _table_column_reference_comments(item: dict[str, Any]) -> str:
    columns = item.get('columns') or []
    if not columns:
        return '-- 현재 컬럼 메타데이터를 읽지 못했습니다. DB 권한을 확인하세요.\n'
    lines = ['-- 현재 컬럼']
    for column in columns:
        if not isinstance(column, dict):
            continue
        column_name = str(column.get('name') or '')
        data_type = str(column.get('data_type') or '')
        nullable = 'NULL' if bool(column.get('nullable')) else 'NOT NULL'
        extra = []
        if column.get('primary_key'):
            extra.append('PK')
        if column.get('default') not in (None, ''):
            extra.append(f"DEFAULT {column.get('default')}")
        suffix = f" · {' · '.join(extra)}" if extra else ''
        lines.append(f'--   {column_name} : {data_type} · {nullable}{suffix}')
    return '\n'.join(lines) + '\n'


def _build_table_alter_template(db_type: str, schema: str, name: str, item: dict[str, Any]) -> str:
    qualified = _qualified_object_name(db_type, schema, name)
    qsample = _quoted_identifier(db_type, 'column_name')
    qnew = _quoted_identifier(db_type, 'new_column_name')

    if db_type == 'mssql':
        examples = (
            f'-- [컬럼 추가]\n-- ALTER TABLE {qualified} ADD {qsample} NVARCHAR(100) NULL;\n\n'
            f"-- [컬럼 이름 변경]\n-- EXEC sp_rename N'{qualified}.column_name', N'new_column_name', 'COLUMN';\n\n"
            f'-- [컬럼 형식/NULL 변경]\n-- ALTER TABLE {qualified} ALTER COLUMN {qsample} NVARCHAR(200) NOT NULL;\n\n'
            f'-- [DEFAULT 제약 추가]\n-- ALTER TABLE {qualified} ADD CONSTRAINT [DF_{_scratch_safe_name(name)}_column_name] DEFAULT (0) FOR {qsample};\n\n'
            f'-- [컬럼 삭제]\n-- ALTER TABLE {qualified} DROP COLUMN {qsample};\n'
        )
    elif db_type == 'oracle':
        examples = (
            f'-- [컬럼 추가]\n-- ALTER TABLE {qualified} ADD ({qsample} VARCHAR2(100));\n\n'
            f'-- [컬럼 이름 변경]\n-- ALTER TABLE {qualified} RENAME COLUMN {qsample} TO {qnew};\n\n'
            f'-- [컬럼 형식/NULL 변경]\n-- ALTER TABLE {qualified} MODIFY ({qsample} VARCHAR2(200) NOT NULL);\n\n'
            f'-- [DEFAULT 변경]\n-- ALTER TABLE {qualified} MODIFY ({qsample} DEFAULT 0);\n\n'
            f'-- [컬럼 삭제]\n-- ALTER TABLE {qualified} DROP COLUMN {qsample};\n'
        )
    elif db_type == 'sqlite3':
        renamed = _quoted_identifier(db_type, str(name) + '_new')
        qtable = _quoted_identifier(db_type, name)
        examples = (
            '-- SQLite는 ALTER TABLE 기능이 제한적입니다. 복잡한 형식/제약 변경은 새 테이블 생성 후 데이터 이관 방식이 안전합니다.\n\n'
            f'-- [컬럼 추가]\n-- ALTER TABLE {qualified} ADD COLUMN {qsample} TEXT;\n\n'
            f'-- [컬럼 이름 변경]\n-- ALTER TABLE {qualified} RENAME COLUMN {qsample} TO {qnew};\n\n'
            f'-- [컬럼 삭제 · SQLite 3.35+]\n-- ALTER TABLE {qualified} DROP COLUMN {qsample};\n\n'
            f'-- [테이블 이름 변경]\n-- ALTER TABLE {qualified} RENAME TO {renamed};\n\n'
            '-- [형식/PK/FK 등 복잡한 변경]\n'
            '-- 1) CREATE TABLE 새_테이블 (...);\n'
            f'-- 2) INSERT INTO 새_테이블 (...) SELECT ... FROM {qualified};\n'
            f'-- 3) DROP TABLE {qualified};\n'
            f'-- 4) ALTER TABLE 새_테이블 RENAME TO {qtable};\n'
        )
    else:
        examples = (
            f'-- [컬럼 추가]\n-- ALTER TABLE {qualified} ADD COLUMN {qsample} VARCHAR(100);\n\n'
            f'-- [컬럼 이름 변경]\n-- ALTER TABLE {qualified} RENAME COLUMN {qsample} TO {qnew};\n\n'
            f'-- [컬럼 형식 변경]\n-- ALTER TABLE {qualified} ALTER COLUMN {qsample} TYPE VARCHAR(200);\n\n'
            f'-- [NULL 허용/금지]\n-- ALTER TABLE {qualified} ALTER COLUMN {qsample} SET NOT NULL;\n-- ALTER TABLE {qualified} ALTER COLUMN {qsample} DROP NOT NULL;\n\n'
            f'-- [DEFAULT 변경]\n-- ALTER TABLE {qualified} ALTER COLUMN {qsample} SET DEFAULT 0;\n-- ALTER TABLE {qualified} ALTER COLUMN {qsample} DROP DEFAULT;\n\n'
            f'-- [컬럼 삭제]\n-- ALTER TABLE {qualified} DROP COLUMN {qsample};\n'
        )

    return _table_column_reference_comments(item) + '\n' + examples


def create_table_alter_script(root: str, schema: str, name: str) -> dict[str, Any]:
    _require_active_runtime(root)
    objects, item, category = _find_database_object(root, schema, 'tables', name)
    if category != 'tables':
        raise ValueError('테이블 객체만 수정 스크립트를 생성할 수 있습니다.')
    db_type = str(objects.get('db_type') or 'postgresql').lower()
    qualified = _qualified_object_name(db_type, schema, name)
    template = _build_table_alter_template(db_type, schema, name, item)

    project_root = Path(_project_key(root)).resolve()
    scratch_dir = project_root / '.agentstudio' / 'sql_scratch'
    scratch_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
    scratch_name = f'alter_table_{_scratch_safe_name(schema)}_{_scratch_safe_name(name)}_{timestamp}.sql'
    scratch_path = scratch_dir / scratch_name
    header = (
        '-- THEANOVA AgentStudio · 테이블 수정 스크립트 보기\n'
        f'-- DB: {db_type.upper()} · 테이블: {qualified}\n'
        f'-- 생성 시각: {datetime.now().isoformat(timespec="seconds")}\n'
        '-- 안전을 위해 모든 ALTER 예제는 주석 처리되어 있습니다. 필요한 구문만 수정 후 주석을 해제해 실행하세요.\n'
        '-- 이 임시 파일을 생성하는 것만으로 실제 DB 객체는 변경되지 않습니다.\n\n'
    )
    content = header + template
    scratch_path.write_text(content, encoding='utf-8', newline='\n')
    return {
        'ok': True,
        'action': 'alter_template',
        'db_type': db_type,
        'schema': schema,
        'category': 'tables',
        'name': name,
        'qualified_name': qualified,
        'relative_path': scratch_path.relative_to(project_root).as_posix(),
        'content': content,
        'message': f'{qualified} 테이블 수정 스크립트를 임시 SQL 파일로 생성했습니다.',
    }


def _primary_key_columns(conn: Any, db_type: str, schema: str, name: str, item: dict[str, Any]) -> list[str]:
    db_type = str(db_type or 'postgresql').lower()
    try:
        if db_type == 'sqlite3':
            return [
                str(column.get('name') or '')
                for column in (item.get('columns') or [])
                if isinstance(column, dict) and column.get('primary_key') and str(column.get('name') or '')
            ]
        schema_lit = str(schema or '').replace("'", "''")
        name_lit = str(name or '').replace("'", "''")
        if db_type == 'mssql':
            rows = _metadata_rows(conn, f"""
                SELECT c.name
                  FROM sys.indexes i
                  JOIN sys.index_columns ic ON ic.object_id=i.object_id AND ic.index_id=i.index_id
                  JOIN sys.columns c ON c.object_id=ic.object_id AND c.column_id=ic.column_id
                  JOIN sys.tables t ON t.object_id=i.object_id
                  JOIN sys.schemas s ON s.schema_id=t.schema_id
                 WHERE i.is_primary_key=1
                   AND s.name='{schema_lit}'
                   AND t.name='{name_lit}'
                 ORDER BY ic.key_ordinal
            """)
        elif db_type == 'oracle':
            rows = _metadata_rows(conn, f"""
                SELECT cc.column_name
                  FROM user_constraints c
                  JOIN user_cons_columns cc ON cc.constraint_name=c.constraint_name
                 WHERE c.constraint_type='P'
                   AND c.table_name=UPPER('{name_lit}')
                 ORDER BY cc.position
            """)
        else:
            rows = _metadata_rows(conn, f"""
                SELECT kcu.column_name
                  FROM information_schema.table_constraints tc
                  JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name=kcu.constraint_name
                   AND tc.table_schema=kcu.table_schema
                   AND tc.table_name=kcu.table_name
                 WHERE tc.constraint_type='PRIMARY KEY'
                   AND tc.table_schema='{schema_lit}'
                   AND tc.table_name='{name_lit}'
                 ORDER BY kcu.ordinal_position
            """)
        return [str(row[0]) for row in rows if row and row[0]]
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return []


def _sample_sql_value(db_type: str, column: dict[str, Any]) -> str:
    data_type = str(column.get('data_type') or '').lower()
    if any(token in data_type for token in ('int', 'numeric', 'decimal', 'real', 'double', 'float', 'money', 'number')):
        return '0'
    if 'bool' in data_type or data_type == 'bit':
        return 'FALSE' if db_type in {'postgresql', 'sqlite3'} else '0'
    if 'date' in data_type and 'time' not in data_type:
        return 'CURRENT_DATE' if db_type != 'mssql' else 'CAST(GETDATE() AS date)'
    if any(token in data_type for token in ('time', 'timestamp', 'datetime')):
        if db_type == 'mssql':
            return 'GETDATE()'
        if db_type == 'oracle':
            return 'SYSTIMESTAMP'
        return 'CURRENT_TIMESTAMP'
    if 'uuid' in data_type or 'uniqueidentifier' in data_type:
        return "'00000000-0000-0000-0000-000000000000'"
    if 'json' in data_type:
        return "'{}'"
    if 'bytea' in data_type or 'blob' in data_type or 'binary' in data_type:
        return 'NULL'
    return "'값'"


def _table_dml_template(conn: Any, db_type: str, schema: str, name: str, item: dict[str, Any], action: str) -> str:
    columns = [column for column in (item.get('columns') or []) if isinstance(column, dict) and str(column.get('name') or '').strip()]
    if not columns:
        raise ValueError('테이블 컬럼 메타데이터가 없어 DML 스크립트를 만들 수 없습니다.')
    qualified = _qualified_object_name(db_type, schema, name)
    pk_names = _primary_key_columns(conn, db_type, schema, name, item)
    if not pk_names:
        pk_names = [str(columns[0].get('name'))]
        pk_warning = '-- ⚠ PK 정보를 찾지 못해 첫 번째 컬럼을 WHERE 예제로 사용합니다. 실행 전에 조건을 확인하세요.\n'
    else:
        pk_warning = '-- PK 기반 WHERE 예제를 사용합니다. 실행 전에 조건값을 확인하세요.\n'

    qcols = [_quoted_identifier(db_type, str(column.get('name'))) for column in columns]
    column_map = {str(column.get('name')): column for column in columns}
    where_parts = []
    for pk in pk_names:
        column = column_map.get(pk) or {'name': pk, 'data_type': ''}
        where_parts.append(f'{_quoted_identifier(db_type, pk)} = {_sample_sql_value(db_type, column)}')
    where_clause = '\n  AND '.join(where_parts)

    action = str(action or '').strip().lower()
    if action == 'select':
        select_list = ',\n    '.join(qcols)
        if db_type == 'mssql':
            return f'SELECT TOP (100)\n    {select_list}\nFROM {qualified}\nORDER BY {_quoted_identifier(db_type, pk_names[0])};\n'
        if db_type == 'oracle':
            return f'SELECT\n    {select_list}\nFROM {qualified}\nORDER BY {_quoted_identifier(db_type, pk_names[0])}\nFETCH FIRST 100 ROWS ONLY;\n'
        return f'SELECT\n    {select_list}\nFROM {qualified}\nORDER BY {_quoted_identifier(db_type, pk_names[0])}\nLIMIT 100;\n'

    if action == 'insert':
        values = [_sample_sql_value(db_type, column) for column in columns]
        return (
            '-- ⚠ INSERT 실행 전 예제 값을 실제 값으로 변경하세요.\n'
            f'INSERT INTO {qualified} (\n    ' + ',\n    '.join(qcols) + '\n) VALUES (\n    ' + ',\n    '.join(values) + '\n);\n'
        )

    if action == 'update':
        # v5.261: UPDATE 임시 스크립트도 테이블의 전체 컬럼을 빠짐없이 표시합니다.
        # PK 컬럼은 WHERE 조건에도 사용되지만 사용자가 전체 구조를 확인할 수 있도록 SET에도 남깁니다.
        assignments = [
            f'{_quoted_identifier(db_type, str(column.get("name")))} = {_sample_sql_value(db_type, column)}'
            for column in columns
        ]
        pk_names_text = ', '.join(pk_names)
        return (
            '-- ⚠ UPDATE 실행 전 SET 값과 WHERE 조건을 반드시 확인하세요.\n'
            + pk_warning
            + (f'-- ⚠ 전체 컬럼 표시 정책: PK 컬럼({pk_names_text})도 SET 목록에 포함됩니다. PK를 변경하지 않을 경우 해당 줄을 제거하세요.\n' if pk_names_text else '')
            + f'UPDATE {qualified}\nSET\n    ' + ',\n    '.join(assignments)
            + f'\nWHERE {where_clause};\n'
        )

    if action == 'delete':
        return (
            '-- ⚠ DELETE 실행 전 WHERE 조건을 반드시 확인하세요.\n'
            + pk_warning
            + f'DELETE FROM {qualified}\nWHERE {where_clause};\n'
        )
    raise ValueError(f'지원하지 않는 DML 스크립트 종류입니다: {action}')


def create_table_dml_script(root: str, schema: str, name: str, action: str) -> dict[str, Any]:
    runtime = _require_active_runtime(root)
    objects, item, category = _find_database_object(root, schema, 'tables', name)
    if category != 'tables':
        raise ValueError('테이블 객체만 DML 스크립트를 생성할 수 있습니다.')
    db_type = str(objects.get('db_type') or 'postgresql').lower()
    conn = runtime['connection']
    qualified = _qualified_object_name(db_type, schema, name)
    action = str(action or '').strip().lower()
    labels = {'select':'SELECT', 'insert':'INSERT', 'update':'UPDATE', 'delete':'DELETE'}
    if action not in labels:
        raise ValueError('SELECT/INSERT/UPDATE/DELETE 중 하나를 선택하세요.')
    sql = _table_dml_template(conn, db_type, schema, name, item, action)

    project_root = Path(_project_key(root)).resolve()
    scratch_dir = project_root / '.agentstudio' / 'sql_scratch'
    scratch_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
    scratch_name = f'{action}_table_{_scratch_safe_name(schema)}_{_scratch_safe_name(name)}_{timestamp}.sql'
    scratch_path = scratch_dir / scratch_name
    header = (
        f'-- THEANOVA AgentStudio · {labels[action]} 스크립트 생성\n'
        f'-- DB: {db_type.upper()} · 테이블: {qualified}\n'
        f'-- 생성 시각: {datetime.now().isoformat(timespec="seconds")}\n'
        '-- 이 파일은 임시 SQL입니다. 자동 실행되지 않습니다. 실행 전에 조건과 값을 검토하세요.\n\n'
        + _table_column_reference_comments(item) + '\n'
    )
    content = header + sql
    scratch_path.write_text(content, encoding='utf-8', newline='\n')
    return {
        'ok': True,
        'action': action,
        'db_type': db_type,
        'schema': schema,
        'category': 'tables',
        'name': name,
        'qualified_name': qualified,
        'relative_path': scratch_path.relative_to(project_root).as_posix(),
        'content': content,
        'message': f'{qualified} {labels[action]} 스크립트를 임시 SQL 파일로 생성했습니다.',
    }


def _postgresql_admin_sql(database: str, action: str, value: str = '') -> tuple[str, str]:
    database = str(database or '').strip() or 'postgres'
    db_lit = database.replace("'", "''")
    action = str(action or '').strip().lower()
    value = str(value or '').strip()

    if action == 'sessions':
        return '현재 실행 중인 세션 보기', f"""-- 현재 실행 중인 세션 확인
-- pid : 세션 번호
-- state : 현재 상태
-- xact_start : 트랜잭션 시작 시간
-- wait_event_type : Lock 대기 여부
-- query : 해당 세션에서 실행한 SQL
SELECT
    pid,
    usename,
    datname,
    application_name,
    client_addr,
    state,
    xact_start,
    query_start,
    wait_event_type,
    wait_event,
    query
FROM pg_stat_activity
WHERE datname = '{db_lit}'
ORDER BY xact_start NULLS LAST;
"""
    if action == 'locks':
        return '실제 Lock 목록 보기', f"""-- 실제 Lock 목록 확인
-- granted = true  : Lock을 가지고 있는 세션
-- granted = false : 다른 세션의 Lock 때문에 기다리는 세션
SELECT
    l.pid,
    a.usename,
    a.application_name,
    a.state,
    l.locktype,
    l.mode,
    l.granted,
    c.relname AS table_name,
    a.query
FROM pg_locks l
LEFT JOIN pg_stat_activity a ON l.pid = a.pid
LEFT JOIN pg_class c ON l.relation = c.oid
WHERE a.datname = '{db_lit}'
ORDER BY l.pid, c.relname;
"""
    if action == 'blocking':
        return '누가 누구를 막고 있는지 보기', f"""-- 누가 누구를 막고 있는지 바로 확인
SELECT
    a.pid AS blocked_pid,
    a.usename AS blocked_user,
    a.query AS blocked_query,
    blocking.pid AS blocking_pid,
    blocking.usename AS blocking_user,
    blocking.application_name AS blocking_app,
    blocking.state AS blocking_state,
    blocking.query AS blocking_query
FROM pg_stat_activity a
JOIN LATERAL unnest(pg_blocking_pids(a.pid)) AS b(blocking_pid) ON true
JOIN pg_stat_activity blocking ON blocking.pid = b.blocking_pid
WHERE a.datname = '{db_lit}';
"""
    if action == 'table_locks':
        table = value or 'customers'
        table_lit = table.replace("'", "''")
        return f'특정 테이블 {table} Lock 보기', f"""-- 특정 테이블의 Lock만 보기
SELECT
    l.pid,
    a.usename,
    a.application_name,
    a.state,
    l.mode,
    l.granted,
    c.relname AS table_name,
    a.query
FROM pg_locks l
JOIN pg_class c ON l.relation = c.oid
LEFT JOIN pg_stat_activity a ON l.pid = a.pid
WHERE c.relname = '{table_lit}'
ORDER BY l.pid;
"""
    if action == 'backend_pid':
        return '현재 세션 PID 보기', """-- 현재 이 SQL을 실행하는 DB 세션의 PID
-- DBeaver에서 실행하면 현재 DBeaver 세션 PID가 반환됩니다.
SELECT pg_backend_pid();
"""
    if action in {'cancel_backend', 'terminate_backend'}:
        try:
            pid = int(value)
        except Exception as exc:
            raise ValueError('PID에는 숫자만 입력하세요.') from exc
        if pid <= 0:
            raise ValueError('PID는 1 이상의 숫자여야 합니다.')
        if action == 'cancel_backend':
            return f'쿼리 중지 PID {pid}', f"""-- 쿼리만 중지하고 DB 접속은 유지
-- 대상 PID: {pid}
SELECT pg_cancel_backend({pid});
"""
        return f'DB 연결 강제 종료 PID {pid}', f"""-- DB 연결 자체를 강제로 종료
-- 대상 PID: {pid}
SELECT pg_terminate_backend({pid});
"""
    if action == 'terminate_others':
        state = value or 'idle in transaction'
        state_lit = state.replace("'", "''")
        return '다른 세션만 종료', f"""-- 현재 연결을 제외하고 다른 세션만 종료
-- 상태 필터: {state}
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname = '{db_lit}'
  AND pid <> pg_backend_pid()
  AND state = '{state_lit}';
"""
    raise ValueError(f'지원하지 않는 PostgreSQL 관리 스크립트입니다: {action}')


def create_postgresql_admin_script(root: str, action: str, value: str = '') -> dict[str, Any]:
    runtime = _require_active_runtime(root)
    profile = runtime.get('profile') or {}
    db_type = str(profile.get('db_type') or 'postgresql').lower()
    if db_type != 'postgresql':
        raise ValueError('세션/Lock 관리 스크립트는 현재 PostgreSQL 연결에서만 지원합니다.')
    database = str(profile.get('database') or '').strip()
    try:
        rows = _metadata_rows(runtime['connection'], 'SELECT current_database()')
        if rows and rows[0] and rows[0][0]:
            database = str(rows[0][0])
    except Exception:
        try:
            runtime['connection'].rollback()
        except Exception:
            pass
    title, sql = _postgresql_admin_sql(database, action, value)

    project_root = Path(_project_key(root)).resolve()
    scratch_dir = project_root / '.agentstudio' / 'sql_scratch'
    scratch_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
    scratch_name = f'postgresql_admin_{_scratch_safe_name(action)}_{timestamp}.sql'
    scratch_path = scratch_dir / scratch_name
    destructive = str(action or '').lower() in {'cancel_backend', 'terminate_backend', 'terminate_others'}
    header = (
        '-- THEANOVA AgentStudio · PostgreSQL 세션 / Lock 관리\n'
        f'-- 메뉴: {title}\n'
        f'-- Database: {database}\n'
        f'-- 생성 시각: {datetime.now().isoformat(timespec="seconds")}\n'
        '-- 이 임시 파일은 자동 실행되지 않습니다.\n'
        + ('-- ⚠ 세션 종료/취소 SQL입니다. 대상 PID/조건을 다시 확인한 뒤 실행하세요.\n' if destructive else '')
        + '\n'
    )
    content = header + sql
    scratch_path.write_text(content, encoding='utf-8', newline='\n')
    return {
        'ok': True,
        'action': action,
        'db_type': db_type,
        'database': database,
        'relative_path': scratch_path.relative_to(project_root).as_posix(),
        'content': content,
        'message': f'{title} SQL을 임시 파일로 생성했습니다.',
    }


def _build_table_select_sql(db_type: str, qualified: str, item: dict[str, Any], limit: int = 1000) -> str:
    """DB Object Explorer 테이블 더블클릭용 SELECT를 실제 컬럼 목록으로 생성합니다."""
    column_names = [
        str(column.get('name') or '').strip()
        for column in (item.get('columns') or [])
        if isinstance(column, dict) and str(column.get('name') or '').strip()
    ]
    # 메타데이터 권한 문제 등으로 컬럼을 읽지 못한 경우에만 호환 fallback을 사용합니다.
    quoted_columns = [_quoted_identifier(db_type, name) for name in column_names]
    select_list = ',\n    '.join(quoted_columns) if quoted_columns else '*'

    if db_type == 'mssql':
        return f'SELECT TOP ({int(limit)})\n    {select_list}\nFROM {qualified};\n'
    if db_type == 'oracle':
        return f'SELECT\n    {select_list}\nFROM {qualified}\nFETCH FIRST {int(limit)} ROWS ONLY;\n'
    return f'SELECT\n    {select_list}\nFROM {qualified}\nLIMIT {int(limit)};\n'


def open_database_object(root: str, schema: str, category: str, name: str) -> dict[str, Any]:
    runtime = _require_active_runtime(root)
    objects, item, category = _find_database_object(root, schema, category, name)
    db_type = str(objects.get('db_type') or 'postgresql').lower()
    conn = runtime['connection']
    qualified = _qualified_object_name(db_type, schema, name)
    action = 'query' if category == 'tables' else 'edit'

    if action == 'query':
        sql = _build_table_select_sql(db_type, qualified, item, 1000)
        result = execute(root, sql, 1000)
    else:
        sql = _build_object_edit_script(conn, db_type, schema, category, item)
        if not sql.strip():
            sql = (
                f'-- {db_type.upper()} {category} 객체 수정 스크립트\n'
                f'-- 대상: {qualified}\n'
                '-- 객체 정의를 자동으로 가져오지 못했습니다. 필요한 ALTER/CREATE OR REPLACE 구문을 작성하세요.\n'
            )
        result = None

    project_root = Path(_project_key(root)).resolve()
    scratch_dir = project_root / '.agentstudio' / 'sql_scratch'
    scratch_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
    scratch_name = f'{action}_{_scratch_safe_name(category)}_{_scratch_safe_name(name)}_{timestamp}.sql'
    scratch_path = scratch_dir / scratch_name
    header = (
        f'-- AgentStudio 임시 SQL · {action.upper()}\n'
        f'-- DB: {db_type.upper()} · 객체: {schema}.{name} · 종류: {category}\n'
        f'-- 생성 시각: {datetime.now().isoformat(timespec="seconds")}\n\n'
    )
    content = header + sql
    scratch_path.write_text(content, encoding='utf-8', newline='\n')
    return {
        'ok': True,
        'action': action,
        'db_type': db_type,
        'schema': schema,
        'category': category,
        'name': name,
        'qualified_name': qualified,
        'relative_path': scratch_path.relative_to(project_root).as_posix(),
        'content': content,
        'result': result,
        'message': '테이블 조회 SQL을 생성하고 실행했습니다.' if action == 'query' else '객체 수정용 임시 SQL을 생성했습니다.',
    }
