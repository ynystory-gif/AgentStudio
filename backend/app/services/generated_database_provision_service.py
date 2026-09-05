from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from urllib.parse import quote
from pathlib import Path
from typing import Any
from dataclasses import dataclass, field
from app.services.database_schema_design import apply_common_table_policy, apply_common_table_policy_overrides, finalize_database_plan


def _bool(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "on"}


def _text(value: Any, default: str = "") -> str:
    value = str(value or "").strip()
    return value or default


def _enabled(setup: dict, key: str) -> bool:
    item = setup.get(key) or {}
    return isinstance(item, dict) and _bool(item.get("use_in_agent", item.get("enabled")))


def _auto_provision(setup: dict, key: str) -> bool:
    item = setup.get(key) or {}
    return isinstance(item, dict) and _enabled(setup, key) and _bool(item.get("auto_provision"))


def sanitize_agent_database_setup(setup: dict | None) -> dict:
    """Return a safe, non-secret description suitable for generated project files."""
    src = setup if isinstance(setup, dict) else {}
    mode = _text(src.get("mode"), "PENDING").upper()
    pg = src.get("postgresql") if isinstance(src.get("postgresql"), dict) else {}
    fs = src.get("firestore") if isinstance(src.get("firestore"), dict) else {}
    rd = src.get("redis") if isinstance(src.get("redis"), dict) else {}
    return {
        "mode": mode,
        "postgresql": {
            "enabled": _enabled(src, "postgresql"),
            "use_in_agent": _enabled(src, "postgresql"),
            "auto_provision": _auto_provision(src, "postgresql"),
            "use_existing": _bool(pg.get("use_existing")),
            "analyze_existing": _bool(pg.get("analyze_existing")),
            "host": _text(pg.get("host"), "127.0.0.1"),
            "port": int(pg.get("port") or 5432),
            "database": _text(pg.get("database")),
            "schema": _text(pg.get("schema"), "public"),
            "user": _text(pg.get("user"), "postgres"),
            "ssl": _bool(pg.get("ssl", True)),
            "sslmode": _text(pg.get("sslmode"), "prefer"),
            "pgvector": _bool(pg.get("pgvector")),
            "role": _text(pg.get("role")),
            "password_env": "POSTGRES_PASSWORD",
        },
        "firestore": {
            "enabled": _enabled(src, "firestore"),
            "use_in_agent": _enabled(src, "firestore"),
            "auto_provision": _auto_provision(src, "firestore"),
            "use_existing": _bool(fs.get("use_existing")),
            "analyze_existing": _bool(fs.get("analyze_existing")),
            "project_id": _text(fs.get("project_id")),
            "database_id": _text(fs.get("database_id"), "(default)"),
            "region": _text(fs.get("region")),
            "emulator": _bool(fs.get("emulator")),
            "collection_prefix": _text(fs.get("collection_prefix")),
            "initial_collections": _normalize_name_list(fs.get("initial_collections")),
            "map_design_entities": fs.get("map_design_entities") is not False,
            "role": _text(fs.get("role")),
            "credentials_env": "GOOGLE_APPLICATION_CREDENTIALS",
        },
        "redis": {
            "enabled": _enabled(src, "redis"),
            "use_in_agent": _enabled(src, "redis"),
            "auto_provision": _auto_provision(src, "redis"),
            "use_existing": _bool(rd.get("use_existing")),
            "host": _text(rd.get("host"), "127.0.0.1"),
            "port": int(rd.get("port") or 6379),
            "db": int(rd.get("db") or 0),
            "username": _text(rd.get("username")),
            "tls": _bool(rd.get("tls", rd.get("ssl"))),
            "ssl": _bool(rd.get("tls", rd.get("ssl"))),
            "key_prefix": _text(rd.get("key_prefix")),
            "role": _text(rd.get("role")),
            "password_env": "REDIS_PASSWORD",
        },
    }

def validate_agent_database_setup(setup: dict | None) -> dict:
    src = setup if isinstance(setup, dict) else {}
    mode = _text(src.get("mode"), "PENDING").upper()
    errors: list[str] = []
    warnings: list[str] = []
    enabled = [key for key in ("postgresql", "firestore", "redis") if _enabled(src, key)]
    provision = [key for key in enabled if _auto_provision(src, key)]

    passive_modes = {"SKIP", "NO_DB", "LATER_EDITOR"}
    if mode in passive_modes:
        return {"valid": True, "mode": mode, "providers": [], "provision_providers": [], "errors": [], "warnings": []}
    if mode not in {"CONFIGURE", "CONNECTION_ONLY", "PENDING", *passive_modes}:
        errors.append("DB 설정 mode가 올바르지 않습니다.")
    if mode in {"CONFIGURE", "CONNECTION_ONLY"} and not enabled:
        errors.append("DB 설정을 사용하는 경우 PostgreSQL, Firestore, Redis 중 하나 이상을 선택하세요.")
    if mode == "CONNECTION_ONLY" and provision:
        warnings.append("연결 정보만 저장 모드에서는 DB 구조 자동 생성을 수행하지 않습니다.")
        provision = []

    pg = src.get("postgresql") if isinstance(src.get("postgresql"), dict) else {}
    if _enabled(src, "postgresql"):
        if not _text(pg.get("host")): errors.append("PostgreSQL Host를 입력하세요.")
        if not _text(pg.get("database")): errors.append("PostgreSQL Database를 입력하세요.")
        if not _text(pg.get("user")): errors.append("PostgreSQL User를 입력하세요.")
        try:
            port = int(pg.get("port") or 0)
            if not 1 <= port <= 65535: raise ValueError
        except Exception:
            errors.append("PostgreSQL Port는 1~65535 사이 숫자여야 합니다.")

    fs = src.get("firestore") if isinstance(src.get("firestore"), dict) else {}
    if _enabled(src, "firestore"):
        if not _text(fs.get("project_id")): errors.append("Firestore Project ID를 입력하세요.")
        if not _text(fs.get("service_account_path")) and not _bool(fs.get("emulator")):
            warnings.append("Firestore Credential 경로가 비어 있어 Application Default Credentials를 사용합니다.")

    rd = src.get("redis") if isinstance(src.get("redis"), dict) else {}
    if _enabled(src, "redis"):
        if not _text(rd.get("host")): errors.append("Redis Host를 입력하세요.")
        try:
            port = int(rd.get("port") or 0)
            if not 1 <= port <= 65535: raise ValueError
        except Exception:
            errors.append("Redis Port는 1~65535 사이 숫자여야 합니다.")
        try:
            db = int(rd.get("db") or 0)
            if db < 0: raise ValueError
        except Exception:
            errors.append("Redis DB Number는 0 이상의 숫자여야 합니다.")

    return {
        "valid": not errors,
        "mode": mode,
        "providers": enabled,
        "provision_providers": provision,
        "errors": errors,
        "warnings": warnings,
    }

def _normalize_name_list(value: Any) -> list[str]:
    if isinstance(value, str):
        rows = value.replace("\n", ",").replace(";", ",").split(",")
    elif isinstance(value, (list, tuple, set)):
        rows = list(value)
    else:
        rows = []
    result: list[str] = []
    for row in rows:
        name = str(row or "").strip()
        if name and name not in result:
            result.append(name)
    return result


def _test_postgresql(cfg: dict) -> dict:
    import psycopg

    with psycopg.connect(
        host=_text(cfg.get("host"), "127.0.0.1"),
        port=int(cfg.get("port") or 5432),
        dbname=_text(cfg.get("database")),
        user=_text(cfg.get("user"), "postgres"),
        password=str(cfg.get("password") or ""),
        sslmode=_text(cfg.get("sslmode"), "prefer"),
        connect_timeout=5,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), current_user")
            database, user = cur.fetchone()
    return {"ok": True, "provider": "postgresql", "message": f"PostgreSQL 연결 성공 · {user}@{database}"}


def _firestore_client(cfg: dict):
    from google.cloud import firestore

    project_id = _text(cfg.get("project_id"))
    database_id = _text(cfg.get("database_id"), "(default)")
    service_account_path = _text(cfg.get("service_account_path"))
    credentials = None
    if service_account_path:
        from google.oauth2 import service_account

        path = Path(service_account_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Firestore Service Account JSON을 찾을 수 없습니다: {path}")
        credentials = service_account.Credentials.from_service_account_file(str(path))
    return firestore.Client(project=project_id, database=database_id, credentials=credentials)


def _test_firestore(cfg: dict) -> dict:
    client = _firestore_client(cfg)
    # Firestore reserves resource IDs matching __.*__.  The old probe document
    # ID "__probe__" therefore returned HTTP 400 even when credentials/project
    # were valid.  Use a normal non-existent document ID and perform read-only
    # GET so connection testing never writes user data.
    probe_collection = "_agentstudio_connection_probe"
    probe_document = "connection_probe"
    snapshot = client.collection(probe_collection).document(probe_document).get()
    return {
        "ok": True,
        "provider": "firestore",
        "message": (
            f"Firestore 연결 성공 · project={_text(cfg.get('project_id'))} · "
            f"database={_text(cfg.get('database_id'), '(default)')} · "
            f"read-only probe={'existing' if snapshot.exists else 'not-found-ok'}"
        ),
    }


def _redis_client(cfg: dict, *, tls_override: bool | None = None, connect_timeout: float = 5):
    import redis

    tls_enabled = _bool(cfg.get("tls", cfg.get("ssl"))) if tls_override is None else bool(tls_override)
    return redis.Redis(
        host=_text(cfg.get("host"), "127.0.0.1"),
        port=int(cfg.get("port") or 6379),
        db=int(cfg.get("db") or 0),
        username=_text(cfg.get("username")) or None,
        password=str(cfg.get("password") or "") or None,
        ssl=tls_enabled,
        socket_connect_timeout=connect_timeout,
        socket_timeout=connect_timeout,
        decode_responses=True,
    )


def _test_redis(cfg: dict) -> dict:
    host = _text(cfg.get("host"), "127.0.0.1")
    port = int(cfg.get("port") or 6379)
    db_index = int(cfg.get("db") or 0)
    tls_enabled = _bool(cfg.get("tls", cfg.get("ssl")))
    loopback = host.strip().lower() in {"127.0.0.1", "localhost", "::1"}

    if tls_enabled and loopback:
        try:
            client = _redis_client(cfg, tls_override=True, connect_timeout=2)
            client.ping()
            return {"ok": True, "provider": "redis", "message": f"Redis TLS 연결 성공 · {host}:{port} / DB {db_index}"}
        except Exception as tls_exc:
            try:
                plain = _redis_client(cfg, tls_override=False, connect_timeout=2)
                plain.ping()
                return {
                    "ok": True,
                    "provider": "redis",
                    "fallback_applied": True,
                    "suggested_config": {"tls": False},
                    "message": (
                        f"Redis 연결 성공 · {host}:{port} / DB {db_index} · "
                        "로컬 TLS 연결이 실패하여 비TLS로 자동 재시도했습니다. TLS 설정을 자동 해제합니다."
                    ),
                    "diagnostic": f"TLS probe failed: {type(tls_exc).__name__}",
                }
            except Exception:
                raise tls_exc

    client = _redis_client(cfg)
    client.ping()
    return {
        "ok": True,
        "provider": "redis",
        "message": f"Redis 연결 성공 · {host}:{port} / DB {db_index}{' · TLS' if tls_enabled else ''}",
    }


def test_agent_database_setup(setup: dict | None, provider: str = "") -> dict:
    src = setup if isinstance(setup, dict) else {}
    requested = _text(provider).lower()
    validation_source = src
    if requested in {"postgresql", "firestore", "redis"}:
        validation_source = {**src, "mode": "CONFIGURE"}
        for key in ("postgresql", "firestore", "redis"):
            cfg = dict(src.get(key) or {})
            cfg["enabled"] = key == requested and _enabled(src, key)
            cfg["use_in_agent"] = cfg["enabled"]
            validation_source[key] = cfg
    validation = validate_agent_database_setup(validation_source)
    if not validation["valid"]:
        return {"ok": False, "validation": validation, "providers": []}
    if validation["mode"] == "SKIP":
        return {"ok": True, "validation": validation, "providers": [], "message": "DB 연결 설정을 건너뛰도록 선택했습니다."}
    providers: list[dict] = []
    for key, fn in (("postgresql", _test_postgresql), ("firestore", _test_firestore), ("redis", _test_redis)):
        if requested and key != requested:
            continue
        if not _enabled(src, key):
            continue
        try:
            providers.append(fn(src.get(key) or {}))
        except Exception as exc:
            providers.append({"ok": False, "provider": key, "message": str(exc)})
    return {
        "ok": bool(providers) and all(item.get("ok") for item in providers),
        "validation": validation,
        "providers": providers,
        "message": "선택한 DB 연결 테스트를 완료했습니다.",
    }


@dataclass
class DatabaseProvisionPlan:
    provider: str
    use_in_agent: bool
    auto_provision: bool
    include_in_provision: bool
    role: str = ""
    resources: dict = field(default_factory=dict)
    approved: bool = False

    def as_dict(self) -> dict:
        return {
            "provider": self.provider,
            "use_in_agent": self.use_in_agent,
            "auto_provision": self.auto_provision,
            "include_in_provision": self.include_in_provision,
            "role": self.role,
            "resources": self.resources,
            "approved": self.approved,
        }


class PostgreSQLProvision:
    provider = "postgresql"

    @staticmethod
    def provision(plan: dict, cfg: dict) -> dict:
        return _provision_postgresql(plan, cfg)

    @staticmethod
    def build(plan: dict, cfg: dict) -> DatabaseProvisionPlan:
        policy_plan = apply_common_table_policy(plan)
        tables = [str(x.get("name") or "") for x in policy_plan.get("tables") or [] if isinstance(x, dict) and x.get("name")]
        table_details = []
        indexes = []
        for table in policy_plan.get("tables") or []:
            if isinstance(table, dict):
                table_details.append({
                    "name": _text(table.get("name")),
                    "purpose": _text(table.get("purpose")),
                    "crud": table.get("crud") or [],
                    "columns": [dict(x) for x in table.get("columns") or [] if isinstance(x, dict)],
                    "common_policy": table.get("common_policy") or {},
                })
            if not isinstance(table, dict): continue
            tname = _text(table.get("name"))
            for cols in table.get("indexes") or []:
                if isinstance(cols, (list, tuple)) and cols:
                    indexes.append(f"idx_{tname}_{'_'.join(str(v) for v in cols)}")
        role = _text(cfg.get("role")) or ("영구/관계형 데이터 · pgvector Vector Search" if _bool(cfg.get("pgvector")) else "영구 데이터 · 관계형 데이터 · Agent Memory")
        return DatabaseProvisionPlan(
            provider="postgresql", use_in_agent=True, auto_provision=_bool(cfg.get("auto_provision")),
            include_in_provision=_bool(cfg.get("auto_provision")), role=role,
            resources={
                "database": _text(cfg.get("database")), "schema": _text(cfg.get("schema"), _text(plan.get("schema_name"), "public")),
                "tables": tables, "table_details": table_details, "table_policy_overrides": {}, "indexes": indexes, "primary_keys": True, "foreign_keys": True,
                "unique_constraints": True, "common_table_policy": "CRUD 기반 ID / Audit / Soft Delete 자동 판단", "pgvector_extension": _bool(cfg.get("pgvector")),
                "vector_columns": ["embedding"] if _bool(cfg.get("pgvector")) else [],
                "vector_indexes": ["vector_index"] if _bool(cfg.get("pgvector")) else [],
                "triggers": [], "seed_data": [],
                "existing_structure": (plan.get("existing_analysis") or {}).get("postgresql"),
            }
        )


class FirestoreProvision:
    provider = "firestore"

    @staticmethod
    def provision(plan: dict, cfg: dict) -> dict:
        return _provision_firestore(plan, cfg)

    @staticmethod
    def build(plan: dict, cfg: dict) -> DatabaseProvisionPlan:
        explicit = _normalize_name_list(cfg.get("initial_collections"))
        collections = explicit or [str(x.get("name") or "") for x in plan.get("tables") or [] if isinstance(x, dict) and x.get("name")]
        if not collections:
            collections = ["user_sessions", "agent_events", "agent_settings"]
        prefix = _text(cfg.get("collection_prefix"))
        collections = [f"{prefix}{x}" if prefix else x for x in collections]
        role = _text(cfg.get("role")) or "Document 기반 데이터 · Agent Event · 사용자 설정 · 실시간 상태"
        return DatabaseProvisionPlan(
            provider="firestore", use_in_agent=True, auto_provision=_bool(cfg.get("auto_provision")),
            include_in_provision=_bool(cfg.get("auto_provision")), role=role,
            resources={
                "database": _text(cfg.get("database_id"), "(default)"), "region": _text(cfg.get("region")),
                "collections": collections, "document_schema": {}, "fields": [],
                "composite_indexes": [], "security_rules": [], "initial_documents": [],
                "existing_structure": (plan.get("existing_analysis") or {}).get("firestore"),
            }
        )


class RedisProvision:
    provider = "redis"

    @staticmethod
    def provision(plan: dict, cfg: dict) -> dict:
        return _provision_redis(plan, cfg)

    @staticmethod
    def build(plan: dict, cfg: dict) -> DatabaseProvisionPlan:
        prefix = _text(cfg.get("key_prefix")) or "AGENT_"
        keys = []
        redis_plan = plan.get("redis_plan") if isinstance(plan.get("redis_plan"), dict) else {}
        for row in redis_plan.get("keys") or []:
            if isinstance(row, dict) and _text(row.get("key")):
                keys.append({"pattern": _text(row.get("key")), "type": _text(row.get("type"), "STRING"), "ttl": _text(row.get("ttl")), "purpose": _text(row.get("purpose"))})
        if not keys:
            keys = [
                {"pattern": f"{prefix}SESSION:{{session_id}}", "type": "HASH", "ttl": "session policy", "purpose": "Session"},
                {"pattern": f"{prefix}CACHE:{{hash}}", "type": "STRING", "ttl": "cache policy", "purpose": "Cache"},
                {"pattern": f"{prefix}LOCK:{{resource}}", "type": "STRING", "ttl": "lock timeout", "purpose": "Lock"},
                {"pattern": f"{prefix}QUEUE:{{name}}", "type": "LIST", "ttl": "", "purpose": "Queue"},
            ]
        role = _text(cfg.get("role")) or "Session · Cache · TTL 데이터 · Queue · Lock · 작업 상태"
        return DatabaseProvisionPlan(
            provider="redis", use_in_agent=True, auto_provision=_bool(cfg.get("auto_provision")),
            include_in_provision=_bool(cfg.get("auto_provision")), role=role,
            resources={"prefix": prefix, "key_patterns": keys, "ttl_policy": True, "data_structures": ["Hash", "List", "Set", "Sorted Set", "Stream"], "existing_structure": (plan.get("existing_analysis") or {}).get("redis")}
        )


def build_database_resource_plan(database_plan: dict | None, setup: dict | None) -> dict:
    plan = database_plan if isinstance(database_plan, dict) else {}
    src = setup if isinstance(setup, dict) else {}
    validation = validate_agent_database_setup(src)
    rows: list[dict] = []
    adapters = {"postgresql": PostgreSQLProvision, "firestore": FirestoreProvision, "redis": RedisProvision}
    for key in validation.get("providers") or []:
        adapter = adapters[key]
        row = adapter.build(plan, src.get(key) or {}).as_dict()
        rows.append(row)
    requires_approval = any(bool(row.get("auto_provision") and row.get("include_in_provision")) for row in rows)
    return {
        "ok": validation.get("valid", False), "approved": False, "requires_approval": requires_approval,
        "mode": validation.get("mode"), "providers": rows, "validation": validation,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "message": "DB Resource Plan을 생성했습니다. 실제 DB 변경은 사용자 승인 후에만 실행합니다.",
    }


def analyze_existing_database(setup: dict | None, provider: str) -> dict:
    src = setup if isinstance(setup, dict) else {}
    key = _text(provider).lower()
    if key == "postgresql":
        import psycopg
        cfg = src.get("postgresql") or {}
        schema = _text(cfg.get("schema"), "public")
        with psycopg.connect(host=_text(cfg.get("host"), "127.0.0.1"), port=int(cfg.get("port") or 5432), dbname=_text(cfg.get("database")), user=_text(cfg.get("user"), "postgres"), password=str(cfg.get("password") or ""), sslmode=_text(cfg.get("sslmode"), "prefer"), connect_timeout=6) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema=%s AND table_type='BASE TABLE' ORDER BY table_name", (schema,))
                tables=[row[0] for row in cur.fetchall()]
        return {"ok": True, "provider": key, "schema": schema, "tables": tables, "message": f"기존 PostgreSQL Schema 분석 완료 · {len(tables)} Table"}
    if key == "firestore":
        client = _firestore_client(src.get("firestore") or {})
        collections=[item.id for item in client.collections()]
        return {"ok": True, "provider": key, "collections": collections, "message": f"기존 Firestore Collection 분석 완료 · {len(collections)}개"}
    if key == "redis":
        client = _redis_client(src.get("redis") or {})
        sample=[]
        for item in client.scan_iter(match="*", count=50):
            sample.append(str(item))
            if len(sample)>=50: break
        return {"ok": True, "provider": key, "sample_keys": sample, "message": f"기존 Redis Key 분석 완료 · Sample {len(sample)}개"}
    return {"ok": False, "provider": key, "message": "지원하지 않는 DB Provider입니다."}



def create_postgresql_schema_resource(setup: dict | None) -> dict:
    """Create only the configured PostgreSQL schema. No tables or seed data are changed."""
    import psycopg
    from psycopg import sql

    src = setup if isinstance(setup, dict) else {}
    cfg = src.get("postgresql") if isinstance(src.get("postgresql"), dict) else {}
    host = _text(cfg.get("host"), "127.0.0.1")
    port = int(cfg.get("port") or 5432)
    database = _text(cfg.get("database"))
    schema = _text(cfg.get("schema"), "public")
    user = _text(cfg.get("user"), "postgres")
    if not database:
        return {"ok": False, "provider": "postgresql", "message": "PostgreSQL Database Name을 입력하세요."}
    if not schema:
        return {"ok": False, "provider": "postgresql", "message": "PostgreSQL Schema 이름을 입력하세요."}

    with psycopg.connect(
        host=host,
        port=port,
        dbname=database,
        user=user,
        password=str(cfg.get("password") or ""),
        sslmode=_text(cfg.get("sslmode"), "prefer"),
        connect_timeout=8,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name=%s", (schema,))
            existed = cur.fetchone() is not None
            cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
        conn.commit()
    return {
        "ok": True,
        "provider": "postgresql",
        "created": not existed,
        "already_exists": existed,
        "database": database,
        "schema": schema,
        "message": (
            f"PostgreSQL 스키마가 이미 존재합니다 · {database}.{schema}"
            if existed
            else f"PostgreSQL 스키마 생성 완료 · {database}.{schema}"
        ),
    }


def _firestore_authorized_session(cfg: dict):
    import google.auth
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account

    scopes = ["https://www.googleapis.com/auth/cloud-platform"]
    credentials_path = _text(cfg.get("service_account_path"))
    if credentials_path:
        path = Path(credentials_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Firestore Service Account JSON을 찾을 수 없습니다: {path}")
        credentials = service_account.Credentials.from_service_account_file(str(path), scopes=scopes)
    else:
        credentials, _ = google.auth.default(scopes=scopes)
    return AuthorizedSession(credentials)


def _google_error_message(response) -> str:
    try:
        payload = response.json()
        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict) and error.get("message"):
                return str(error.get("message"))
            if payload.get("message"):
                return str(payload.get("message"))
    except Exception:
        pass
    return str(getattr(response, "text", "") or f"HTTP {getattr(response, 'status_code', '?')}").strip()


def create_firestore_database_resource(setup: dict | None) -> dict:
    """Create the configured Firestore database through the official Firestore Admin REST API."""
    src = setup if isinstance(setup, dict) else {}
    cfg = src.get("firestore") if isinstance(src.get("firestore"), dict) else {}
    if _bool(cfg.get("emulator")):
        return {"ok": False, "provider": "firestore", "message": "Firestore Emulator에서는 Google Cloud Database 생성이 필요하지 않습니다."}

    project_id = _text(cfg.get("project_id"))
    database_id = _text(cfg.get("database_id"), "(default)")
    location_id = _text(cfg.get("region"))
    if not project_id:
        return {"ok": False, "provider": "firestore", "message": "Google Cloud Project ID를 입력하세요."}
    if not database_id:
        return {"ok": False, "provider": "firestore", "message": "Firestore Database ID를 입력하세요."}
    if not location_id:
        return {"ok": False, "provider": "firestore", "message": "Firestore Database 생성 전에 Region / Location을 입력하세요. 위치는 생성 후 변경할 수 없습니다."}

    session = _firestore_authorized_session(cfg)
    encoded_project = quote(project_id, safe="")
    encoded_database = quote(database_id, safe="")
    database_url = f"https://firestore.googleapis.com/v1/projects/{encoded_project}/databases/{encoded_database}"
    existing = session.get(database_url, timeout=20)
    if existing.status_code == 200:
        return {
            "ok": True, "provider": "firestore", "created": False, "already_exists": True,
            "project_id": project_id, "database_id": database_id,
            "message": f"Firestore Database가 이미 존재합니다 · {project_id}/{database_id}",
        }
    if existing.status_code not in {404}:
        return {"ok": False, "provider": "firestore", "message": f"Firestore Database 확인 실패: {_google_error_message(existing)}"}

    create_url = f"https://firestore.googleapis.com/v1/projects/{encoded_project}/databases?databaseId={encoded_database}"
    response = session.post(
        create_url,
        json={"locationId": location_id, "type": "FIRESTORE_NATIVE"},
        timeout=30,
    )
    if response.status_code == 409:
        return {
            "ok": True, "provider": "firestore", "created": False, "already_exists": True,
            "project_id": project_id, "database_id": database_id,
            "message": f"Firestore Database가 이미 존재합니다 · {project_id}/{database_id}",
        }
    if response.status_code not in {200, 201, 202}:
        return {"ok": False, "provider": "firestore", "message": f"Firestore Database 생성 실패: {_google_error_message(response)}"}

    operation = {}
    try:
        operation = response.json() if response.content else {}
    except Exception:
        operation = {}
    operation_name = str(operation.get("name") or "").strip() if isinstance(operation, dict) else ""
    if operation_name:
        operation_url = f"https://firestore.googleapis.com/v1/{operation_name.lstrip('/')}"
        for _ in range(45):
            poll = session.get(operation_url, timeout=20)
            if poll.status_code != 200:
                return {"ok": False, "provider": "firestore", "message": f"Firestore Database 생성 상태 확인 실패: {_google_error_message(poll)}"}
            payload = poll.json() if poll.content else {}
            if payload.get("done"):
                if payload.get("error"):
                    error = payload.get("error") or {}
                    return {"ok": False, "provider": "firestore", "message": f"Firestore Database 생성 실패: {error.get('message') or error}"}
                break
            time.sleep(2)
        else:
            return {"ok": False, "provider": "firestore", "message": "Firestore Database 생성 요청은 접수되었지만 완료 확인 시간이 초과되었습니다. Google Cloud Console에서 상태를 확인하세요."}

    verify = None
    for _ in range(10):
        verify = session.get(database_url, timeout=20)
        if verify.status_code == 200:
            break
        if verify.status_code != 404:
            return {"ok": False, "provider": "firestore", "message": f"Firestore Database 생성 후 확인 실패: {_google_error_message(verify)}"}
        time.sleep(2)
    if verify is None or verify.status_code != 200:
        return {"ok": False, "provider": "firestore", "message": "Firestore Database 생성 요청은 완료되었지만 Database 조회 반영을 확인하지 못했습니다. Google Cloud Console에서 상태를 확인하세요."}
    return {
        "ok": True,
        "provider": "firestore",
        "created": True,
        "already_exists": False,
        "project_id": project_id,
        "database_id": database_id,
        "location_id": location_id,
        "message": f"Firestore Database 생성 완료 · {project_id}/{database_id} · {location_id}",
    }

def _provision_postgresql(plan: dict, cfg: dict) -> dict:
    import psycopg
    from psycopg import sql

    ddl = str(plan.get("ddl") or "").strip()
    if not ddl:
        raise ValueError("확정된 PostgreSQL DDL이 없습니다. 먼저 DB 설계를 확정하세요.")
    schema = _text(cfg.get("schema"), "public")
    target_database = _text(cfg.get("database"))
    connection_kwargs = dict(
        host=_text(cfg.get("host"), "127.0.0.1"), port=int(cfg.get("port") or 5432),
        user=_text(cfg.get("user"), "postgres"), password=str(cfg.get("password") or ""),
        sslmode=_text(cfg.get("sslmode"), "prefer"), connect_timeout=8,
    )
    database_created = False
    try:
        conn = psycopg.connect(dbname=target_database, **connection_kwargs)
    except psycopg.errors.InvalidCatalogName:
        # 사용자 권한이 허용하는 경우에만 Database까지 생성합니다. 실패하면 원인을 그대로 반환합니다.
        with psycopg.connect(dbname="postgres", autocommit=True, **connection_kwargs) as admin_conn:
            with admin_conn.cursor() as cur:
                cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target_database)))
        database_created = True
        conn = psycopg.connect(dbname=target_database, **connection_kwargs)

    with conn:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema)))
            cur.execute(sql.SQL("SET search_path TO {}, public").format(sql.Identifier(schema)))
            if _bool(cfg.get("pgvector")):
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(ddl)
            cur.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema=%s AND table_type='BASE TABLE'", (schema,))
            count = int(cur.fetchone()[0])
        conn.commit()
    return {
        "ok": True, "provider": "postgresql", "database_created": database_created,
        "created_structure_count": count,
        "steps": {"connection": "SUCCESS", "database": "SUCCESS", "schema": "SUCCESS", "table": "SUCCESS", "index": "SUCCESS"},
        "message": f"PostgreSQL DB 구조 구성 완료 · database={target_database} · schema={schema} · table={count}",
    }

def _firestore_collection_names(plan: dict, cfg: dict) -> list[str]:
    explicit = _normalize_name_list(cfg.get("initial_collections"))
    prefix = _text(cfg.get("collection_prefix"))
    if explicit:
        names = explicit
    else:
        firestore_plan = plan.get("firestore_plan") if isinstance(plan.get("firestore_plan"), dict) else {}
        names = []
        for row in firestore_plan.get("collections") or []:
            if isinstance(row, dict):
                value = _text(row.get("name"))
            else:
                value = _text(row)
            if value:
                names.append(value)
        if not names and cfg.get("map_design_entities") is not False:
            names = [_text(row.get("name")) for row in plan.get("tables") or [] if isinstance(row, dict) and _text(row.get("name"))]
    result: list[str] = []
    for name in names:
        full = f"{prefix}{name}" if prefix else name
        if full and full not in result:
            result.append(full)
    return result


def _provision_firestore(plan: dict, cfg: dict) -> dict:
    from google.cloud import firestore

    client = _firestore_client(cfg)
    collections = _firestore_collection_names(plan, cfg)
    if not collections:
        collections = [f"{_text(cfg.get('collection_prefix'))}_agentstudio_meta".lstrip("_") or "agentstudio_meta"]

    batch = client.batch()
    now = datetime.now(timezone.utc).isoformat()
    for name in collections:
        doc = client.collection(name).document("__agentstudio_schema__")
        batch.set(
            doc,
            {
                "_agentstudio_schema": True,
                "created_at": now,
                "source": "THEANOVA AgentStudio",
                "note": "Firestore collections are schemaless; this document records the generated collection bootstrap.",
            },
            merge=True,
        )
    batch.commit()
    return {
        "ok": True,
        "provider": "firestore",
        "created_structure_count": len(collections),
        "collections": collections,
        "steps": {"connection": "SUCCESS", "database": "SUCCESS", "collection": "SUCCESS", "initial_document": "SUCCESS"},
        "message": f"Firestore DB 구조 구성 완료 · Collection {len(collections)}개",
    }


def _provision_redis(plan: dict, cfg: dict) -> dict:
    client = _redis_client(cfg)
    client.ping()
    prefix = _text(cfg.get("key_prefix"))
    prefix = prefix if not prefix or prefix.endswith(":") else prefix + ":"
    schema_key = f"{prefix}agentstudio:schema"
    redis_plan = plan.get("redis_plan") if isinstance(plan.get("redis_plan"), dict) else {}
    key_patterns = []
    for row in redis_plan.get("keys") or []:
        if isinstance(row, dict):
            key_patterns.append({
                "key": _text(row.get("key")),
                "purpose": _text(row.get("purpose")),
                "ttl": _text(row.get("ttl")),
            })
    payload = {
        "source": "THEANOVA AgentStudio",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "key_prefix": prefix,
        "key_patterns": json.dumps(key_patterns, ensure_ascii=False),
    }
    client.hset(schema_key, mapping=payload)
    return {
        "ok": True,
        "provider": "redis",
        "created_structure_count": 1,
        "schema_key": schema_key,
        "steps": {"connection": "SUCCESS", "prefix": "SUCCESS", "key_policy": "SUCCESS", "ttl_policy": "SUCCESS"},
        "message": f"Redis 초기 구조 구성 완료 · {schema_key}",
    }


def _write_safe_runtime_config(project_root: str, setup: dict) -> str:
    root = Path(project_root).expanduser().resolve()
    config_dir = (root / "backend" / "config").resolve()
    config_dir.relative_to(root)
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "database_runtime.generated.json"
    payload = sanitize_agent_database_setup(setup)
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    payload["secret_policy"] = (
        "Passwords and Firestore credential file contents are not stored by AgentStudio. "
        "Use POSTGRES_PASSWORD, REDIS_PASSWORD and GOOGLE_APPLICATION_CREDENTIALS at runtime."
    )
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


def _write_safe_resource_plan(project_root: str, resource_plan: dict | None) -> str:
    root = Path(project_root).expanduser().resolve()
    config_dir = (root / "backend" / "config").resolve()
    config_dir.relative_to(root)
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "database_resource_plan.generated.json"
    payload = resource_plan if isinstance(resource_plan, dict) else {}
    safe = {
        "approved": bool(payload.get("approved")),
        "approved_at": _text(payload.get("approved_at")),
        "generated_at": _text(payload.get("generated_at")),
        "providers": payload.get("providers") or [],
        "policy": "Actual database changes are allowed only for an approved DB Resource Plan.",
    }
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


def provision_agent_databases(project_root: str, database_plan: dict | None, setup: dict | None, resource_plan: dict | None = None) -> dict:
    src = setup if isinstance(setup, dict) else {}
    validation = validate_agent_database_setup(src)
    mode = validation.get("mode")
    if not validation.get("valid"):
        return {"ok": False, "skipped": False, "providers": [], "validation": validation, "message": "DB 설정 검증에 실패했습니다."}

    # DB 미사용/Skip/나중에 설정은 실제 외부 DB를 절대 변경하지 않습니다.
    if mode in {"PENDING", "SKIP", "NO_DB", "LATER_EDITOR"} or not validation.get("providers"):
        return {"ok": True, "skipped": True, "mode": mode, "providers": [], "validation": validation, "message": "DB 구조 구성은 건너뛰었습니다."}

    plan = database_plan if isinstance(database_plan, dict) else {}
    rp = resource_plan if isinstance(resource_plan, dict) else {}
    rp_rows = {str(x.get("provider") or ""): x for x in rp.get("providers") or [] if isinstance(x, dict)}
    provision_keys = list(validation.get("provision_providers") or [])
    if mode == "CONNECTION_ONLY":
        provision_keys = []

    if provision_keys and not bool(rp.get("approved")):
        return {
            "ok": False, "skipped": False, "approval_required": True, "providers": [], "validation": validation,
            "message": "DB 구조 자동 생성 전에 DB Resource Plan 사용자 승인이 필요합니다.",
        }

    results: list[dict] = []
    provisioners = {"postgresql": PostgreSQLProvision.provision, "firestore": FirestoreProvision.provision, "redis": RedisProvision.provision}
    for key in validation.get("providers") or []:
        cfg = src.get(key) or {}
        rp_row = rp_rows.get(key, {})
        include = key in provision_keys and rp_row.get("include_in_provision", True) is not False
        if not include:
            results.append({"ok": True, "provider": key, "skipped": True, "message": f"{key} 연결 사용 · DB 구조 자동 생성 제외"})
            continue
        try:
            # Preview에서 수정한 provider resource 일부를 provisioning input에 반영합니다.
            provider_plan = dict(plan)
            resources = rp_row.get("resources") if isinstance(rp_row.get("resources"), dict) else {}
            if key == "postgresql":
                provider_plan = apply_common_table_policy_overrides(provider_plan, resources.get("table_policy_overrides") or {})
                provider_plan = finalize_database_plan(provider_plan)
                if resources.get("schema"):
                    cfg = {**cfg, "schema": resources.get("schema")}
            if key == "firestore" and resources.get("collections"):
                cfg = {**cfg, "initial_collections": resources.get("collections")}
            if key == "redis" and resources.get("prefix"):
                cfg = {**cfg, "key_prefix": resources.get("prefix")}
            results.append(provisioners[key](provider_plan, cfg))
        except Exception as exc:
            rollback = {
                "postgresql": "DDL transaction 범위는 자동 rollback 가능 · CREATE DATABASE는 별도 확인 필요",
                "firestore": "실패 전 commit되지 않은 Batch는 반영 안 됨 · 생성 완료 Document는 제거 계획 필요",
                "redis": "AgentStudio schema registry Key는 삭제 가능 · 기존 사용자 Key는 변경하지 않음",
            }.get(key, "확인 필요")
            results.append({"ok": False, "provider": key, "message": str(exc), "retryable": True, "rollback": rollback})

    config_file = ""
    resource_plan_file = ""
    try:
        config_file = _write_safe_runtime_config(project_root, src)
        resource_plan_file = _write_safe_resource_plan(project_root, rp)
    except Exception as exc:
        results.append({"ok": False, "provider": "runtime_config", "message": f"안전한 DB Runtime/Plan 설정 파일 생성 실패: {exc}"})

    ok = all(item.get("ok") for item in results) if results else True
    return {
        "ok": ok, "skipped": not bool(provision_keys), "mode": mode, "providers": results, "validation": validation,
        "config_file": config_file, "resource_plan_file": resource_plan_file,
        "message": "승인된 DB Resource Plan 적용을 완료했습니다." if ok and provision_keys else "DB 연결 정보만 Runtime 설정에 반영했습니다." if ok else "일부 DB 구조 구성에 실패했습니다.",
    }

