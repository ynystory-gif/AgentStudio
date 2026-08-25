import os
from app.core.config import get_settings

def configure_langsmith():
    s = get_settings()
    os.environ["LANGSMITH_TRACING"] = s.langsmith_tracing
    if s.langsmith_api_key:
        os.environ["LANGSMITH_API_KEY"] = s.langsmith_api_key
    os.environ["LANGSMITH_PROJECT"] = s.langsmith_project

def get_chat_model(provider: str | None = None):
    s = get_settings()
    configure_langsmith()
    provider = (provider or s.llm_provider).lower()

    # v5.315: explicit provider="openai" from older UI/API callers is also
    # forced to Ollama while OpenAI is disabled. There is no paid-provider fallback.
    if not s.openai_enabled:
        provider = "ollama"

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model=s.openai_model, api_key=s.openai_api_key or None, temperature=0)

    if provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=s.ollama_model, base_url=s.ollama_base_url, temperature=0)

    raise ValueError(f"지원하지 않는 LLM Provider입니다: {provider}")
