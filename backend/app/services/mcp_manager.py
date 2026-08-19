import asyncio
from dataclasses import asdict
from app.services.tool_analyzer import analyze_tool
from app.core.config import get_settings

async def discover_streamable_http(endpoint: str) -> dict:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamable_http_client

    timeout = get_settings().mcp_default_timeout_seconds

    async def _run():
        async with streamable_http_client(endpoint) as (read, write, _):
            async with ClientSession(read, write) as session:
                init = await session.initialize()
                tools = await session.list_tools()

                capabilities = getattr(init, "capabilities", None)
                tools_cap = getattr(capabilities, "tools", None) if capabilities else None
                list_changed = bool(getattr(tools_cap, "listChanged", False)) if tools_cap else False

                rows = []
                for tool in tools.tools:
                    analysis = analyze_tool(tool.name, tool.description or "")
                    rows.append({
                        "name": tool.name,
                        "description": tool.description or "",
                        "input_schema": getattr(tool, "inputSchema", {}) or {},
                        "annotations": (
                            tool.annotations.model_dump()
                            if getattr(tool, "annotations", None) and hasattr(tool.annotations, "model_dump")
                            else {}
                        ),
                        **asdict(analysis),
                    })

                return {
                    "server_info": (
                        init.serverInfo.model_dump()
                        if getattr(init, "serverInfo", None) and hasattr(init.serverInfo, "model_dump")
                        else {}
                    ),
                    "protocol_version": str(getattr(init, "protocolVersion", "") or ""),
                    "supports_tool_list_changed": list_changed,
                    "tools": rows,
                }

    return await asyncio.wait_for(_run(), timeout=timeout)
