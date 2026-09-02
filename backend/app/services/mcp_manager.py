import asyncio
from dataclasses import asdict
from app.services.tool_analyzer import analyze_tool
from app.core.config import get_settings


def _tool_rows(tools, *, server_hint: str = "") -> list[dict]:
    rows = []
    for tool in tools.tools:
        description = tool.description or ""
        analysis_text = description + (f"\nMCP Server: {server_hint}" if server_hint else "")
        analysis = analyze_tool(tool.name, analysis_text)
        rows.append({
            "name": tool.name,
            "description": description,
            "input_schema": getattr(tool, "inputSchema", {}) or {},
            "annotations": (
                tool.annotations.model_dump()
                if getattr(tool, "annotations", None) and hasattr(tool.annotations, "model_dump")
                else {}
            ),
            **asdict(analysis),
        })
    return rows


def _discovery_payload(init, tools, *, server_hint: str = "") -> dict:
    capabilities = getattr(init, "capabilities", None)
    tools_cap = getattr(capabilities, "tools", None) if capabilities else None
    list_changed = bool(getattr(tools_cap, "listChanged", False)) if tools_cap else False
    return {
        "server_info": (
            init.serverInfo.model_dump()
            if getattr(init, "serverInfo", None) and hasattr(init.serverInfo, "model_dump")
            else {}
        ),
        "protocol_version": str(getattr(init, "protocolVersion", "") or ""),
        "supports_tool_list_changed": list_changed,
        "tools": _tool_rows(tools, server_hint=server_hint),
    }


async def discover_streamable_http(endpoint: str, *, server_hint: str = "") -> dict:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    timeout = get_settings().mcp_default_timeout_seconds

    async def _run():
        async with streamable_http_client(endpoint) as (read, write, _):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                tools = await session.list_tools()
                return _discovery_payload(init, tools, server_hint=server_hint)

    return await asyncio.wait_for(_run(), timeout=timeout)


async def discover_stdio(command: str, args: list[str] | None = None, *, server_hint: str = "") -> dict:
    """Discover an MCP stdio server without assuming an HTTP endpoint.

    The process is scoped to the discovery session and is closed when list_tools
    completes. This is important for Blender MCP variants that are distributed as
    local stdio commands rather than long-running HTTP servers.
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    timeout = get_settings().mcp_default_timeout_seconds
    params = StdioServerParameters(command=str(command or '').strip(), args=list(args or []))
    if not params.command:
        raise ValueError('stdio MCP command가 비어 있습니다.')

    async def _run():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                tools = await session.list_tools()
                return _discovery_payload(init, tools, server_hint=server_hint)

    return await asyncio.wait_for(_run(), timeout=timeout)
