from __future__ import annotations

import socket
from typing import Any


MIN_USER_PORT = 1024
MAX_PORT = 65535
SEARCH_WINDOW = 200


def normalize_port(value: Any, default: int) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return default
    if port < MIN_USER_PORT or port > MAX_PORT:
        return default
    return port


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    """Return True only when a local TCP listener can bind to the port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        sock.bind((host, int(port)))
        return True
    except OSError:
        return False
    finally:
        sock.close()


def _port_state(port: int, current_ports: set[int]) -> str:
    if port in current_ports:
        return "current"
    return "available" if is_port_available(port) else "in_use"


def _find_free_ports(
    start_port: int,
    *,
    current_ports: set[int],
    excluded: set[int] | None = None,
    count: int = 5,
) -> list[int]:
    excluded = set(excluded or set())
    result: list[int] = []
    start = normalize_port(start_port, MIN_USER_PORT)

    for offset in range(SEARCH_WINDOW):
        port = start + offset
        if port > MAX_PORT:
            break
        if port in excluded:
            continue
        state = _port_state(port, current_ports)
        if state in {"available", "current"}:
            result.append(port)
            if len(result) >= count:
                break
    return result


def recommend_agentstudio_ports(
    backend_port: Any = 8000,
    frontend_port: Any = 5173,
    *,
    current_backend_port: Any = None,
    current_frontend_port: Any = None,
) -> dict[str, Any]:
    backend = normalize_port(backend_port, 8000)
    frontend = normalize_port(frontend_port, 5173)

    current_backend = normalize_port(current_backend_port, 0) if current_backend_port else 0
    current_frontend = normalize_port(current_frontend_port, 0) if current_frontend_port else 0
    current_ports = {p for p in (current_backend, current_frontend) if p}

    backend_state = _port_state(backend, current_ports)
    backend_options = _find_free_ports(
        backend if backend_state != "in_use" else min(backend + 1, MAX_PORT),
        current_ports=current_ports,
        count=5,
    )
    backend_recommended = (
        backend
        if backend_state in {"available", "current"}
        else (backend_options[0] if backend_options else backend)
    )

    frontend_excluded = {backend_recommended}
    frontend_state = (
        "conflict_with_backend"
        if frontend == backend_recommended
        else _port_state(frontend, current_ports)
    )
    frontend_options = _find_free_ports(
        frontend if frontend_state not in {"in_use", "conflict_with_backend"}
        else min(frontend + 1, MAX_PORT),
        current_ports=current_ports,
        excluded=frontend_excluded,
        count=5,
    )
    frontend_recommended = (
        frontend
        if frontend_state in {"available", "current"} and frontend != backend_recommended
        else (frontend_options[0] if frontend_options else frontend)
    )

    return {
        "ok": True,
        "backend": {
            "requested": backend,
            "state": backend_state,
            "recommended": backend_recommended,
            "suggestions": backend_options,
            "current": backend == current_backend,
        },
        "frontend": {
            "requested": frontend,
            "state": frontend_state,
            "recommended": frontend_recommended,
            "suggestions": frontend_options,
            "current": frontend == current_frontend,
        },
        "current_runtime": {
            "backend_port": current_backend or None,
            "frontend_port": current_frontend or None,
        },
        "note": (
            "현재 AgentStudio가 사용 중인 포트는 재시작 시 다시 사용할 수 있는 정상 포트로 표시합니다. "
            "다른 프로그램이 사용 중인 포트는 종료하지 않고 다음 사용 가능한 포트를 추천합니다."
        ),
    }



def _technology_default_port(kind: str, technology: str) -> int:
    tech = str(technology or "").strip().lower()
    if kind == "frontend":
        if "next" in tech:
            return 3000
        if "streamlit" in tech:
            return 8501
        return 5173
    if kind == "backend":
        if "spring" in tech:
            return 8080
        if "express" in tech or "node" in tech:
            return 3000
        if "asp.net" in tech or "aspnet" in tech:
            return 5000
        return 8000
    return 8000


def _generated_port_state(port: int, reserved_ports: set[int], excluded: set[int] | None = None) -> str:
    excluded = set(excluded or set())
    if port in excluded:
        return "agent_internal_conflict"
    if port in reserved_ports:
        return "agentstudio_project_in_use"
    return "available" if is_port_available(port) else "os_in_use"


def _find_generated_free_ports(start_port: int, *, reserved_ports: set[int], excluded: set[int] | None = None, count: int = 5) -> list[int]:
    excluded = set(excluded or set())
    result: list[int] = []
    start = normalize_port(start_port, MIN_USER_PORT)
    for offset in range(SEARCH_WINDOW):
        port = start + offset
        if port > MAX_PORT:
            break
        if _generated_port_state(port, reserved_ports, excluded) == "available":
            result.append(port)
            if len(result) >= count:
                break
    return result


def recommend_generated_agent_ports(
    *,
    frontend_technology: str = "React + Vite",
    backend_technology: str = "FastAPI",
    frontend_port: Any = None,
    backend_port: Any = None,
    api_port: Any = None,
    api_share_backend: bool = True,
    frontend_user_fixed: bool = False,
    backend_user_fixed: bool = False,
    api_user_fixed: bool = False,
    reserved_ports: list[int] | set[int] | tuple[int, ...] | None = None,
) -> dict[str, Any]:
    """Recommend ports for a generated Agent, excluding OS listeners and AgentStudio project reservations."""
    reserved = {normalize_port(v, 0) for v in (reserved_ports or [])}
    reserved.discard(0)

    front_default = _technology_default_port("frontend", frontend_technology)
    back_default = _technology_default_port("backend", backend_technology)
    front_requested = normalize_port(frontend_port, front_default)
    back_requested = normalize_port(backend_port, back_default)
    api_requested = normalize_port(api_port, max(8000, back_default + 1))

    def choose(kind: str, requested: int, default: int, tech: str, user_fixed: bool, excluded: set[int]) -> dict[str, Any]:
        state = _generated_port_state(requested, reserved, excluded)
        scan_start = requested if state == "available" else default
        options = _find_generated_free_ports(scan_start, reserved_ports=reserved, excluded=excluded, count=5)
        if not options:
            options = _find_generated_free_ports(default, reserved_ports=reserved, excluded=excluded, count=5)
        recommended = requested if state == "available" else (options[0] if options else requested)
        reasons = [f"{tech or kind} 기술 스택 기준 기본 PORT {default}"]
        if requested != default:
            reasons.append(f"현재 입력 PORT {requested} 확인")
        if state == "agentstudio_project_in_use":
            reasons.append(f"{requested}는 다른 AgentStudio 프로젝트에서 사용 중")
        elif state == "os_in_use":
            reasons.append(f"{requested}는 현재 OS Process에서 사용 중")
        elif state == "agent_internal_conflict":
            reasons.append(f"{requested}는 동일 Agent의 다른 서비스와 충돌")
        else:
            reasons.append(f"{requested} 사용 가능")
        if recommended != requested:
            reasons.append(f"가장 가까운 사용 가능 PORT {recommended} 추천")
        if user_fixed:
            reasons.append("사용자 직접 지정(USER_FIXED) 값은 자동 변경하지 않음")
        return {
            "kind": kind,
            "technology": tech,
            "requested": requested,
            "default": default,
            "state": state,
            "recommended": recommended,
            "suggestions": options,
            "user_fixed": bool(user_fixed),
            "reason": reasons,
        }

    backend = choose("backend", back_requested, back_default, backend_technology, backend_user_fixed, set())
    frontend = choose("frontend", front_requested, front_default, frontend_technology, frontend_user_fixed, {backend["recommended"]})

    if api_share_backend:
        api = {
            "kind": "api", "technology": "Backend API 공유", "requested": backend["recommended"],
            "default": backend["recommended"], "state": backend["state"], "recommended": backend["recommended"],
            "suggestions": [backend["recommended"]], "user_fixed": False,
            "reason": [f"Backend PORT {backend['recommended']} 공유"], "share_backend": True,
        }
    else:
        api = choose("api", api_requested, 8000, "별도 API Server", api_user_fixed, {backend["recommended"], frontend["recommended"]})
        api["share_backend"] = False

    return {
        "ok": True,
        "frontend": frontend,
        "backend": backend,
        "api": api,
        "reserved_ports": sorted(reserved),
        "policy": "기술 스택 → OS 사용 여부 → AgentStudio 프로젝트 예약 → 동일 Agent 충돌 → 사용 가능 PORT 추천",
    }


def sanitize_generated_agent_runtime_setup(setup: dict | None) -> dict[str, Any]:
    src = setup if isinstance(setup, dict) else {}
    mode = str(src.get("mode") or "PENDING").strip().upper()
    front = src.get("frontend") if isinstance(src.get("frontend"), dict) else {}
    back = src.get("backend") if isinstance(src.get("backend"), dict) else {}
    api = src.get("api") if isinstance(src.get("api"), dict) else {}
    return {
        "mode": mode,
        "auto_allocate": bool(src.get("auto_allocate", True)),
        "approved": bool(src.get("approved", False)),
        "frontend": {
            "technology": str(front.get("technology") or "React + Vite"),
            "host": str(front.get("host") or "localhost"),
            "port": normalize_port(front.get("port"), 5173),
            "user_fixed": bool(front.get("user_fixed", False)),
        },
        "backend": {
            "technology": str(back.get("technology") or "FastAPI"),
            "host": str(back.get("host") or "localhost"),
            "port": normalize_port(back.get("port"), 8000),
            "user_fixed": bool(back.get("user_fixed", False)),
        },
        "api": {
            "share_backend": bool(api.get("share_backend", True)),
            "host": str(api.get("host") or "localhost"),
            "port": normalize_port(api.get("port"), 8001),
            "base_path": str(api.get("base_path") or "/api/v1"),
            "user_fixed": bool(api.get("user_fixed", False)),
        },
    }


def resolve_generated_agent_runtime_setup(setup: dict | None, *, reserved_ports: list[int] | None = None) -> dict[str, Any]:
    safe = sanitize_generated_agent_runtime_setup(setup)
    if safe["mode"] == "PENDING":
        return {"ok": True, "skipped": True, "runtime_setup": safe, "message": "실행 환경 설정이 아직 지정되지 않았습니다."}
    result = recommend_generated_agent_ports(
        frontend_technology=safe["frontend"]["technology"],
        backend_technology=safe["backend"]["technology"],
        frontend_port=safe["frontend"]["port"],
        backend_port=safe["backend"]["port"],
        api_port=safe["api"]["port"],
        api_share_backend=safe["api"]["share_backend"],
        frontend_user_fixed=safe["frontend"]["user_fixed"],
        backend_user_fixed=safe["backend"]["user_fixed"],
        api_user_fixed=safe["api"]["user_fixed"],
        reserved_ports=reserved_ports or [],
    )
    conflicts = []
    for key in ("frontend", "backend", "api"):
        row = result[key]
        if row.get("share_backend"):
            continue
        if row.get("user_fixed") and row.get("state") != "available":
            conflicts.append(f"{key} USER_FIXED PORT {row.get('requested')} 충돌: {row.get('state')}")
    if conflicts:
        return {"ok": False, "skipped": False, "runtime_setup": safe, "recommendation": result, "errors": conflicts, "message": "사용자 고정 PORT가 현재 사용 중입니다. PORT를 수정하거나 자동 할당으로 변경하세요."}

    resolved = {**safe, "approved": bool(safe.get("approved"))}
    if safe.get("auto_allocate", True) or safe.get("mode") in {"AUTO", "SKIP"}:
        resolved["frontend"] = {**safe["frontend"], "port": result["frontend"]["recommended"]}
        resolved["backend"] = {**safe["backend"], "port": result["backend"]["recommended"]}
        resolved["api"] = {**safe["api"], "port": result["api"]["recommended"]}
    return {"ok": True, "skipped": False, "runtime_setup": resolved, "recommendation": result, "message": "실행 직전 PORT 재검사를 완료했습니다."}


def write_generated_agent_runtime_config(project_root: str, setup: dict | None) -> str:
    import json
    from datetime import datetime, timezone
    from pathlib import Path

    root = Path(project_root).expanduser().resolve()
    config_dir = (root / "backend" / "config").resolve()
    config_dir.relative_to(root)
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / "runtime_ports.generated.json"
    payload = sanitize_generated_agent_runtime_setup(setup)
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    payload["policy"] = "Frontend/Backend/API/CORS/.env/run scripts/Docker must use this common runtime configuration. Recheck ports immediately before launch."
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)
