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
