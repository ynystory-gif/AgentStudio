import shutil, socket
from app.core.config import get_settings
from app.core.machine_identity import current_pc_name, detect_system_pc_name
from app.services.langgraph_runtime import agent_graph_runtime
from app.services.model_router import routing_table
from app.services.connection_test_service import test_postgresql
from app.services.database_runtime_service import current_runtime_database_url, runtime_status as get_database_runtime_status

def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.4):
            return True
    except OSError:
        return False

async def get_status():
    s = get_settings()
    # DB URL이 실행 중 변경되었거나 시작 시 영속화 연결이 실패했으면 자동 복구를 시도합니다.
    await agent_graph_runtime.ensure_current()
    postgres_port_open = _port_open("127.0.0.1", 5432)
    postgres_test = await test_postgresql(current_runtime_database_url())
    database_runtime = await get_database_runtime_status()
    llm_routes = routing_table()
    return {
        "pc_name": current_pc_name(),
        "system_host_name": detect_system_pc_name(),
        "python": shutil.which("python") is not None,
        "node": shutil.which("node") is not None,
        "npm": shutil.which("npm") is not None,
        "git": shutil.which("git") is not None,
        "postgres": bool(postgres_test.get("ok")),
        "postgres_port_open": postgres_port_open,
        "postgres_message": postgres_test.get("message", ""),
        "database_runtime_provider": database_runtime.get("active_provider", "local"),
        "database_runtime_target": database_runtime.get("supabase_target") if database_runtime.get("active_provider")=="supabase" else database_runtime.get("local_target"),
        "fastapi": True,
        "ollama": _port_open("127.0.0.1", 11434),
        "openai_enabled": bool(s.openai_enabled),
        "openai_key": bool(s.openai_api_key),
        "tavily_key": bool(s.tavily_api_key),
        "langsmith_key": bool(s.langsmith_api_key),
        "llm_provider": llm_routes[0]["provider"] if llm_routes else "ollama",
        "codex_enabled": bool(s.codex_enabled),
        "local_only": not bool(s.openai_enabled) and not bool(s.codex_enabled),
        "project_roots": s.project_roots,
        "auto_approve_risk_level": s.auto_approve_risk_level,
        "langgraph": True,
        "langgraph_persistent": agent_graph_runtime.persistent,
        "langgraph_persistent_message": (
            "PostgreSQL Checkpointer 연결 및 setup 완료"
            if agent_graph_runtime.persistent
            else (agent_graph_runtime.last_error or "LangGraph PostgreSQL Checkpointer 연결 확인이 필요합니다.")
        ),
        "pgvector": True,
        "max_debug_iterations": s.max_debug_iterations,
        "mcp_registry_refresh_seconds": s.mcp_registry_refresh_seconds,
        "mcp_spec_target": "2026-07-28",
        "llm_routing": llm_routes,
    }
