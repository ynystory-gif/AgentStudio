from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent
PROJECT_ENV_PATH = PROJECT_ROOT / ".env"
BACKEND_ENV_PATH = BACKEND_ROOT / ".env"

class Settings(BaseSettings):
    app_name: str = "THEANOVA AgentStudio"
    app_env: str = "development"
    agentstudio_pc_name: str = ""
    agentstudio_system_host_name: str = ""
    agentstudio_backend_port: int = 0
    agentstudio_frontend_port: int = 0
    # DB credentials must come from user-managed .env files. Never fall back to a hard-coded account/password.
    database_url: str = ""
    langgraph_database_url: str = ""
    # v5.284: local PostgreSQL remains the bootstrap/control DB. Supabase is optional after schema verification.
    local_database_url: str = ""
    local_langgraph_database_url: str = ""
    agentstudio_database_provider: str = "local"
    supabase_database_url: str = ""
    supabase_langgraph_database_url: str = ""
    # v5.295: Supabase AgentStudio/LangGraph objects are isolated from public.
    supabase_db_schema: str = "theanova_agentstudio"

    # OpenAI API master switch. OFF filters OpenAI from the adaptive provider chain.
    openai_enabled: bool = True
    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3.5:4b"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_auto_start: bool = True

    # v5.330: unified AI routing. ``ollama_first`` makes local Ollama the default
    # for every compatible text task, then falls back to OpenAI API and (for
    # higher-value coding/requirements tasks) ChatGPT Codex when enabled.
    ai_provider_strategy: str = "ollama_first"
    llm_provider: str = "ollama"
    local_llm_provider: str = "auto"
    coding_llm_provider: str = "auto"
    requirements_llm_provider: str = "auto"
    memory_embedding_provider: str = "ollama"

    # Codex OAuth credentials are owned by the official Codex CLI. AgentStudio
    # stores only whether Codex integration may be used.
    codex_enabled: bool = False

    tavily_api_key: str = ""
    langsmith_tracing: str = "true"
    langsmith_api_key: str = ""
    langsmith_project: str = "THEANOVA-AgentStudio"

    allowed_project_roots: str = ""
    max_command_seconds: int = 300

    auto_approve_risk_level: int = 1
    max_debug_iterations: int = 3
    project_analyzer_max_files: int = 80

    mcp_default_timeout_seconds: int = 30
    mcp_registry_refresh_seconds: int = 15

    sandbox_root: str = ""
    postgresql18_root: str = ""
    default_project_root: str = ""
    default_cache_root: str = ""
    default_temp_root: str = ""
    default_output_root: str = ""
    common_models_root: str = ""

    weather_auto_location: bool = True
    weather_location: str = ""
    weather_extra_locations: str = ""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ENV_PATH),
        extra="ignore",
        case_sensitive=False,
    )

    @property
    def project_roots(self) -> list[str]:
        return [x.strip() for x in self.allowed_project_roots.split(";") if x.strip()]

def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    found: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        found[key.strip()] = value.strip()
    return found


def _read_agentstudio_env_overrides() -> dict:
    """
    Read AgentStudio bootstrap settings from user-managed .env files.

    Priority:
    1. project-root/.env for all database connection settings (authoritative)
    2. backend/.env only as a legacy fallback for non-database bootstrap settings

    Explicit init values are used so stale Windows parent-process environment variables
    cannot override the .env values selected by the user. No database credential is
    synthesized in code.
    """
    mapping = {
        "AGENTSTUDIO_PC_NAME": "agentstudio_pc_name",
        "AGENTSTUDIO_SYSTEM_HOST_NAME": "agentstudio_system_host_name",
        "DATABASE_URL": "database_url",
        "LANGGRAPH_DATABASE_URL": "langgraph_database_url",
        "AGENTSTUDIO_LOCAL_DATABASE_URL": "local_database_url",
        "AGENTSTUDIO_LOCAL_LANGGRAPH_DATABASE_URL": "local_langgraph_database_url",
        "AGENTSTUDIO_DATABASE_PROVIDER": "agentstudio_database_provider",
        "SUPABASE_DATABASE_URL": "supabase_database_url",
        "SUPABASE_LANGGRAPH_DATABASE_URL": "supabase_langgraph_database_url",
        "SUPABASE_DB_SCHEMA": "supabase_db_schema",
        "POSTGRESQL18_ROOT": "postgresql18_root",
        "AGENTSTUDIO_BACKEND_PORT": "agentstudio_backend_port",
        "AGENTSTUDIO_FRONTEND_PORT": "agentstudio_frontend_port",
    }
    project_values = _parse_env_file(PROJECT_ENV_PATH)
    legacy_values = _parse_env_file(BACKEND_ENV_PATH)

    # Database credentials are root-.env-only. A stale backend/.env must never
    # resurrect historical postgres/postgres (or any other) connection settings.
    root_only_database_keys = {
        "DATABASE_URL",
        "LANGGRAPH_DATABASE_URL",
        "AGENTSTUDIO_LOCAL_DATABASE_URL",
        "AGENTSTUDIO_LOCAL_LANGGRAPH_DATABASE_URL",
        "SUPABASE_DATABASE_URL",
        "SUPABASE_LANGGRAPH_DATABASE_URL",
    }

    merged: dict[str, str] = {}
    for key, value in legacy_values.items():
        if key not in root_only_database_keys:
            merged[key] = value
    merged.update(project_values)
    return {field: merged[key] for key, field in mapping.items() if key in merged}


@lru_cache
def get_settings() -> Settings:
    return Settings(**_read_agentstudio_env_overrides())
