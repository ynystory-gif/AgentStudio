from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "THEANOVA AgentStudio"
    app_env: str = "development"
    agentstudio_pc_name: str = ""
    agentstudio_system_host_name: str = ""
    database_url: str = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/theanova_agentstudio"
    langgraph_database_url: str = "postgresql://postgres:postgres@127.0.0.1:5432/theanova_agentstudio"
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
    ollama_model: str = "qwen2.5:7b"
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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    @property
    def project_roots(self) -> list[str]:
        return [x.strip() for x in self.allowed_project_roots.split(";") if x.strip()]

def _read_backend_env_overrides() -> dict:
    """
    AgentStudio bootstrap 설정은 backend/.env를 최종 기준으로 사용합니다.

    Windows 부모 프로세스에 오래된 DATABASE_URL 등이 남아 있으면 Pydantic의
    기본 우선순위(OS 환경변수 > .env) 때문에 시스템 관리 화면에서 저장한 값이
    재시작 후에도 적용되지 않을 수 있습니다. DB 접속에 필요한 bootstrap 값만
    명시적 init 값으로 전달해 backend/.env가 확실히 우선하도록 합니다.
    """
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return {}

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
    }
    found = {}
    for raw_line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        key = key.strip()
        field = mapping.get(key)
        if field:
            found[field] = value.strip()
    return found


@lru_cache
def get_settings() -> Settings:
    return Settings(**_read_backend_env_overrides())
