from app.core.config import get_settings

def get_embedding_model():
    s = get_settings()
    provider = s.memory_embedding_provider.lower()

    if provider == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model=s.openai_embedding_model,
            api_key=s.openai_api_key or None
        )

    if provider == "ollama":
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(
            model=s.ollama_embedding_model,
            base_url=s.ollama_base_url
        )

    raise ValueError(f"지원하지 않는 Embedding Provider입니다: {provider}")
