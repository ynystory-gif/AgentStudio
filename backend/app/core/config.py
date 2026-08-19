from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "THEANOVA AgentStudio"
    app_env: str = "development"
    agentstudio_pc_name: str = ""
    agentstudio_system_host_name: str = ""
    database_url: str = "postgresql+psycopg://postgres:postgres@127.0.0.1:5432/theanova_agentstudio"
    langgraph_database_url: str = "postgresql://postgres:postgres@127.0.0.1:5432/theanova_agentstudio"

    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen2.5:7b"
    ollama_embedding_model: str = "nomic-embed-text"
    ollama_auto_start: bool = True
    llm_provider: str = "ollama"
    local_llm_provider: str = "ollama"
    coding_llm_provider: str = "openai"
    requirements_llm_provider: str = "openai"
    memory_embedding_provider: str = "ollama"

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

@lru_cache
def get_settings() -> Settings:
    return Settings()
