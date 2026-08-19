from app.core.config import get_settings

async def web_search(query: str, max_results: int = 5) -> dict:
    s = get_settings()
    if not s.tavily_api_key:
        raise RuntimeError("TAVILY_API_KEY가 설정되지 않았습니다.")
    from tavily import AsyncTavilyClient
    client = AsyncTavilyClient(api_key=s.tavily_api_key)
    return await client.search(query=query, max_results=max_results, search_depth="advanced")
