from __future__ import annotations
from app.core.config import get_settings
from app.services.agent_workflow import build_workflow

class AgentGraphRuntime:
    """
    FastAPI lifespan 동안 PostgreSQL Checkpointer와 compiled graph를 유지합니다.
    요청마다 checkpointer를 새로 만들지 않습니다.
    """
    def __init__(self):
        self._cm = None
        self.checkpointer = None
        self.graph = None
        self.persistent = False

    async def start(self):
        if self.graph is not None:
            return

        try:
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
            self._cm = AsyncPostgresSaver.from_conn_string(
                get_settings().langgraph_database_url
            )
            self.checkpointer = await self._cm.__aenter__()
            await self.checkpointer.setup()
            self.graph = build_workflow(checkpointer=self.checkpointer)
            self.persistent = True
        except Exception:
            # PostgreSQL checkpoint가 준비되지 않아도 IDE 자체는 기동
            self.graph = build_workflow(checkpointer=None)
            self.persistent = False

    async def stop(self):
        if self._cm is not None:
            try:
                await self._cm.__aexit__(None, None, None)
            finally:
                self._cm = None
        self.checkpointer = None
        self.graph = None

agent_graph_runtime = AgentGraphRuntime()
