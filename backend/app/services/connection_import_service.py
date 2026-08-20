from __future__ import annotations

import ast
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

_MAX_IMPORT_BYTES = 2 * 1024 * 1024


def _read_text(path: Path) -> str:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(str(path))
    if path.stat().st_size > _MAX_IMPORT_BYTES:
        raise ValueError("연결 설정 파일은 2MB 이하만 불러올 수 있습니다.")
    raw = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "cp949"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("파일 문자 인코딩을 읽을 수 없습니다. UTF-8 형식을 권장합니다.")


def _norm_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def _flatten_json(value: Any, prefix: str = "") -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            rows.append((path, item))
            rows.extend(_flatten_json(item, path))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            rows.extend(_flatten_json(item, f"{prefix}[{index}]"))
    return rows


def _first_json_value(payload: Any, aliases: set[str]) -> Any:
    normalized = {_norm_key(item) for item in aliases}
    for path, value in _flatten_json(payload):
        leaf = re.split(r"\.|\[", path)[-1].rstrip("]")
        if _norm_key(leaf) in normalized and not isinstance(value, (dict, list)):
            if value is not None and str(value).strip() != "":
                return value
    return None


def _parse_postgres_url(raw: str) -> dict[str, Any]:
    value = str(raw or "").strip()
    if not value:
        return {}
    normalized = re.sub(r"^postgresql\+[^:]+:", "postgresql:", value, flags=re.I)
    normalized = re.sub(r"^postgres:", "postgresql:", normalized, flags=re.I)
    parsed = urlparse(normalized)
    if parsed.scheme.lower() != "postgresql" or not parsed.hostname:
        return {}
    query = parsed.query.lower()
    ssl_mode = "require" if "sslmode=require" in query or "ssl=true" in query else ""
    return {
        "host": parsed.hostname or "",
        "port": int(parsed.port or 5432),
        "database": unquote((parsed.path or "/postgres").lstrip("/") or "postgres"),
        "username": unquote(parsed.username or "postgres"),
        "password": unquote(parsed.password or ""),
        "ssl_mode": ssl_mode,
    }


def _parse_redis_url(raw: str) -> dict[str, Any]:
    value = str(raw or "").strip()
    if not value:
        return {}
    parsed = urlparse(value)
    if parsed.scheme.lower() not in {"redis", "rediss"} or not parsed.hostname:
        return {}
    database = (parsed.path or "/0").lstrip("/") or "0"
    try:
        int(database)
    except ValueError:
        database = "0"
    return {
        "host": parsed.hostname or "",
        "port": int(parsed.port or 6379),
        "database": str(database),
        "username": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "ssl": parsed.scheme.lower() == "rediss",
    }


def _firebase_service_account(payload: Any) -> bool:
    return (
        isinstance(payload, dict)
        and str(payload.get("type") or "").strip() == "service_account"
        and bool(payload.get("private_key"))
        and bool(payload.get("client_email"))
    )


def _analyze_firestore_service_account(path: Path, payload: Any) -> dict[str, Any]:
    if not _firebase_service_account(payload):
        raise ValueError(
            "Google Cloud/Firebase Service Account JSON 형식이 아닙니다. "
            "type=service_account, project_id, client_email, private_key 항목을 확인하세요."
        )

    project_id = str(payload.get("project_id") or "").strip()
    if not project_id:
        raise ValueError("Service Account JSON에서 project_id를 찾지 못했습니다.")

    return {
        "ok": True,
        "db_type": "firestore",
        "format": "google-service-account-json",
        "source_path": str(path),
        "source_name": path.name,
        "profile": {
            "db_type": "firestore",
            "project_id": project_id,
            "database": "(default)",
            "service_account_json": str(path),
            "driver": "google-cloud-firestore",
            "dashboard_url": "https://console.cloud.google.com/firestore/databases",
        },
        "detected_fields": ["project_id", "service_account_json"],
        "message": (
            "Firebase/Google Service Account JSON을 감지했습니다. "
            "DB 종류를 Google Cloud Firestore로 자동 전환하고 Project ID와 JSON 경로를 등록했습니다."
        ),
    }


def _analyze_supabase_json(path: Path, text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Supabase JSON 파싱 실패: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Supabase 연결 JSON의 최상위 값은 객체여야 합니다.")
    if _firebase_service_account(payload):
        return _analyze_firestore_service_account(path, payload)

    url_value = _first_json_value(payload, {
        "connection_url", "connectionString", "database_url", "db_url",
        "postgres_url", "postgresql_url", "supabase_db_url", "supabase_database_url",
        "DATABASE_URL", "SUPABASE_DB_URL",
    })
    profile = _parse_postgres_url(str(url_value or ""))

    aliases = {
        "host": {"host", "db_host", "database_host", "postgres_host", "pg_host"},
        "port": {"port", "db_port", "database_port", "postgres_port", "pg_port"},
        "database": {"database", "db", "db_name", "database_name", "dbname"},
        "username": {"username", "user", "db_user", "database_user", "postgres_user"},
        "password": {"password", "db_password", "database_password", "postgres_password"},
        "ssl_mode": {"ssl_mode", "sslmode"},
    }
    for field, keys in aliases.items():
        value = _first_json_value(payload, keys)
        if value is not None:
            profile[field] = value

    project_ref = _first_json_value(payload, {"project_ref", "projectRef", "supabase_project_ref"})
    if not profile.get("host") and project_ref:
        profile["host"] = f"db.{str(project_ref).strip()}.supabase.co"
    if profile.get("host"):
        profile["port"] = int(profile.get("port") or 5432)
        profile["database"] = str(profile.get("database") or "postgres")
        profile["username"] = str(profile.get("username") or "postgres")
        profile["password"] = str(profile.get("password") or "")
        profile["ssl_mode"] = str(profile.get("ssl_mode") or "require")
    else:
        raise ValueError(
            "Supabase PostgreSQL Host 또는 Connection URL을 찾지 못했습니다. "
            "JSON에 database_url/connection_url 또는 host 정보가 필요합니다."
        )

    detected = [key for key in ("host", "port", "database", "username", "password", "ssl_mode") if profile.get(key) not in (None, "")]
    return {
        "ok": True,
        "db_type": "supabase",
        "format": "json",
        "source_path": str(path),
        "source_name": path.name,
        "profile": {
            "db_type": "supabase",
            "host": str(profile["host"]),
            "port": int(profile["port"]),
            "database": str(profile["database"]),
            "username": str(profile["username"]),
            "password": str(profile.get("password") or ""),
            "driver": "psycopg",
            "ssl_mode": str(profile.get("ssl_mode") or "require"),
            "dashboard_url": "https://supabase.com/dashboard",
        },
        "detected_fields": detected,
        "message": "Supabase 연결 JSON을 분석해 연결 입력란에 자동 등록했습니다.",
    }


def _literal(node: ast.AST | None) -> Any:
    if node is None:
        return None
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _redis_from_python(text: str) -> dict[str, Any]:
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise ValueError(f"Redis Python 파일 구문 분석 실패: {exc}") from exc

    candidates: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = ""
        if isinstance(node.func, ast.Attribute):
            parts: list[str] = []
            cur: ast.AST | None = node.func
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
            name = ".".join(reversed(parts))
        elif isinstance(node.func, ast.Name):
            name = node.func.id
        lower = name.lower()

        if lower.endswith("redis.from_url") or lower.endswith("strictredis.from_url") or lower == "from_url":
            raw = _literal(node.args[0]) if node.args else None
            parsed = _parse_redis_url(str(raw or ""))
            if parsed:
                candidates.append(parsed)
            continue

        if not (lower.endswith("redis.redis") or lower.endswith("redis.strictredis") or lower in {"redis", "strictredis"}):
            continue
        data: dict[str, Any] = {}
        positionals = ["host", "port", "db", "password"]
        for index, arg in enumerate(node.args[:len(positionals)]):
            value = _literal(arg)
            if value is not None:
                data[positionals[index]] = value
        for keyword in node.keywords:
            if keyword.arg in {"host", "port", "db", "database", "username", "user", "password"}:
                value = _literal(keyword.value)
                if value is not None:
                    data[keyword.arg] = value
        if data:
            candidates.append(data)

    if not candidates:
        raise ValueError("Python 파일에서 redis.Redis(...) 또는 Redis.from_url(...) 연결 설정을 찾지 못했습니다.")
    return candidates[0]


def _parse_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            values[key] = value
    return values


def _redis_from_mapping(payload: Any) -> dict[str, Any]:
    url_value = _first_json_value(payload, {"redis_url", "REDIS_URL", "url", "connection_url"})
    profile = _parse_redis_url(str(url_value or ""))
    aliases = {
        "host": {"host", "redis_host"},
        "port": {"port", "redis_port"},
        "db": {"db", "database", "database_index", "redis_db"},
        "username": {"username", "user", "redis_username", "redis_user"},
        "password": {"password", "redis_password"},
    }
    for field, keys in aliases.items():
        value = _first_json_value(payload, keys)
        if value is not None:
            profile[field] = value
    return profile


def _redis_from_env(text: str) -> dict[str, Any]:
    env = _parse_env(text)
    for key in ("REDIS_URL", "CACHE_REDIS_URL"):
        parsed = _parse_redis_url(env.get(key, ""))
        if parsed:
            return parsed
    return {
        "host": env.get("REDIS_HOST", ""),
        "port": env.get("REDIS_PORT", ""),
        "db": env.get("REDIS_DB", env.get("REDIS_DATABASE", "0")),
        "username": env.get("REDIS_USERNAME", env.get("REDIS_USER", "")),
        "password": env.get("REDIS_PASSWORD", ""),
    }


def _analyze_redis(path: Path, text: str) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".py":
        raw = _redis_from_python(text)
        fmt = "python-ast"
    elif suffix == ".json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Redis JSON 파싱 실패: {exc}") from exc
        raw = _redis_from_mapping(payload)
        fmt = "json"
    else:
        raw = _redis_from_env(text)
        fmt = "env"

    host = str(raw.get("host") or "").strip()
    if not host:
        raise ValueError("Redis Host를 찾지 못했습니다.")
    try:
        port = int(raw.get("port") or 6379)
    except Exception as exc:
        raise ValueError("Redis Port 값이 올바르지 않습니다.") from exc
    db_value = raw.get("db", raw.get("database", "0"))
    try:
        database = str(max(0, int(db_value or 0)))
    except Exception:
        database = "0"
    username = str(raw.get("username", raw.get("user", "")) or "")
    password = str(raw.get("password") or "")

    detected = ["host", "port", "database"]
    if username:
        detected.append("username")
    if password:
        detected.append("password")
    return {
        "ok": True,
        "db_type": "redis",
        "format": fmt,
        "source_path": str(path),
        "source_name": path.name,
        "profile": {
            "db_type": "redis",
            "host": host,
            "port": port,
            "database": database,
            "username": username,
            "password": password,
            "driver": "redis-py",
        },
        "detected_fields": detected,
        "message": "Redis 연결 파일을 안전하게 분석해 연결 입력란에 자동 등록했습니다.",
    }


def analyze_connection_file(path: str, db_type: str) -> dict[str, Any]:
    source = Path(str(path or "")).expanduser().resolve()
    kind = str(db_type or "").strip().lower()
    if kind not in {"supabase", "firestore", "redis"}:
        raise ValueError("파일 자동 분석은 Supabase, Google Cloud Firestore, Redis 연결에서 지원합니다.")
    text = _read_text(source)
    if kind in {"supabase", "firestore"}:
        if source.suffix.lower() != ".json":
            raise ValueError("Supabase/Firestore 연결 가져오기는 JSON 파일만 지원합니다.")
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            label = "Firestore Service Account" if kind == "firestore" else "Supabase"
            raise ValueError(f"{label} JSON 파싱 실패: {exc}") from exc
        if kind == "firestore":
            return _analyze_firestore_service_account(source, payload)
        return _analyze_supabase_json(source, text)
    return _analyze_redis(source, text)
