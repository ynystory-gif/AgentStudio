from __future__ import annotations
import asyncio
from datetime import datetime
from sqlalchemy import select
from app.core.database import SessionLocal
from app.core.config import get_settings
from app.models.entities import MCPServer, ToolRecord
from app.services.mcp_manager import discover_streamable_http

class MCPRegistryMonitor:
    def __init__(self):
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def sync_server(self, server_id: int) -> dict:
        async with SessionLocal() as db:
            server = await db.get(MCPServer, server_id)
            if not server:
                raise ValueError("MCP 서버를 찾을 수 없습니다.")
            if not server.enabled:
                return {"server_id": server_id, "status": "DISABLED"}

            try:
                result = await discover_streamable_http(server.endpoint)
                server.last_status = "CONNECTED"
                server.protocol_version = result.get("protocol_version", "")
                server.supports_tool_list_changed = bool(result.get("supports_tool_list_changed"))
                server.discovered_at = datetime.utcnow()
                server.updated_at = datetime.utcnow()

                seen = set()
                for item in result.get("tools", []):
                    seen.add(item["name"])
                    row = (
                        await db.execute(
                            select(ToolRecord).where(
                                ToolRecord.mcp_server_id == server.id,
                                ToolRecord.name == item["name"]
                            )
                        )
                    ).scalar_one_or_none()
                    if row is None:
                        row = ToolRecord(
                            mcp_server_id=server.id,
                            provider=server.name,
                            name=item["name"],
                        )
                        db.add(row)

                    row.description = item.get("description", "")
                    row.category = item.get("category", "UNKNOWN")
                    row.subcategory = item.get("subcategory", "UNKNOWN")
                    row.capability = item.get("capability", "unknown")
                    row.risk_level = item.get("risk_level", 1)
                    row.requires_confirmation = item.get("requires_confirmation", False)
                    row.input_schema = item.get("input_schema", {})
                    row.annotations = item.get("annotations", {})
                    row.enabled = True
                    row.last_seen_at = datetime.utcnow()

                existing = (
                    await db.execute(select(ToolRecord).where(ToolRecord.mcp_server_id == server.id))
                ).scalars().all()
                for tool in existing:
                    if tool.name not in seen:
                        tool.enabled = False

                await db.commit()
                return {
                    "server_id": server.id,
                    "status": server.last_status,
                    "tool_count": len(seen),
                    "supports_tool_list_changed": server.supports_tool_list_changed,
                }
            except Exception as e:
                server.last_status = "ERROR"
                server.updated_at = datetime.utcnow()
                await db.commit()
                return {"server_id": server.id, "status": "ERROR", "error": str(e)}

    async def sync_all(self) -> list[dict]:
        async with SessionLocal() as db:
            ids = (
                await db.execute(select(MCPServer.id).where(MCPServer.enabled == True))  # noqa: E712
            ).scalars().all()
        results = []
        for server_id in ids:
            results.append(await self.sync_server(server_id))
        return results

    async def _loop(self):
        interval = max(5, get_settings().mcp_registry_refresh_seconds)
        while not self._stop.is_set():
            try:
                await self.sync_all()
            except Exception:
                pass
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    async def start(self):
        if not self._task or self._task.done():
            self._stop.clear()
            self._task = asyncio.create_task(self._loop())

    async def stop(self):
        self._stop.set()
        if self._task:
            await self._task

mcp_registry_monitor = MCPRegistryMonitor()
