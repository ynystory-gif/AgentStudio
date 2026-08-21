from __future__ import annotations

import asyncio
import time

from app.core.config import get_settings
from app.services.agent_workflow import build_workflow
from app.services.langgraph_postgres_connection import open_schema_pinned_checkpointer


class AgentGraphRuntime:
    """
    FastAPI lifespan 동안 PostgreSQL Checkpointer와 compiled graph를 유지합니다.

    v5.273:
    - Backend 시작 당시 DB 연결이 실패했더라도 시스템 관리에서 DB URL을 고친 뒤
      Backend를 재시작하지 않고 LangGraph PostgreSQL Checkpointer를 다시 연결합니다.
    - LANGGRAPH_DATABASE_URL이 변경되면 이전 checkpointer를 닫고 새 URL로 재구성합니다.
    - 상태 조회가 반복될 때 실패한 DB에 과도하게 재접속하지 않도록 짧은 재시도 간격을 둡니다.
    """

    def __init__(self):
        self._cm = None
        self.checkpointer = None
        self.graph = None
        self.persistent = False
        self._active_url = ""
        self._override_url = ""
        self._lock = asyncio.Lock()
        self._last_attempt_monotonic = 0.0
        self.last_error = ""

    def _current_url(self) -> str:
        return str(self._override_url or get_settings().langgraph_database_url or "").strip()

    async def set_database_url(self, url: str, *, restart: bool = False) -> bool:
        """Set a runtime-only LangGraph PostgreSQL URL without overwriting the local bootstrap URL."""
        self._override_url = str(url or "").strip()
        if restart:
            return await self.start(force=True)
        return True

    async def _close_checkpointer_locked(self) -> None:
        if self._cm is not None:
            try:
                await self._cm.__aexit__(None, None, None)
            except Exception:
                pass
        self._cm = None
        self.checkpointer = None

    async def _start_locked(self, url: str) -> bool:
        self._last_attempt_monotonic = time.monotonic()
        await self._close_checkpointer_locked()

        cm = None
        try:
            if not url:
                raise RuntimeError("LANGGRAPH_DATABASE_URL이 비어 있습니다.")

            # v5.296: the helper explicitly applies search_path on the exact
            # psycopg session used by LangGraph. This avoids Supabase PgBouncer
            # silently losing the startup search_path URL option.
            cm = open_schema_pinned_checkpointer(url)
            checkpointer = await cm.__aenter__()
            try:
                # 실제 PostgreSQL 연결 + LangGraph checkpoint 테이블 준비까지 성공해야
                # 영속화 정상으로 판정합니다.
                await checkpointer.setup()
            except Exception:
                try:
                    await cm.__aexit__(None, None, None)
                except Exception:
                    pass
                raise

            self._cm = cm
            self.checkpointer = checkpointer
            self.graph = build_workflow(checkpointer=checkpointer)
            self.persistent = True
            self._active_url = url
            self.last_error = ""
            return True
        except Exception as exc:
            # graph 구성 단계에서 실패한 경우에도 이미 연 PostgreSQL connection을 닫습니다.
            if cm is not None and self._cm is None:
                try:
                    await cm.__aexit__(None, None, None)
                except Exception:
                    pass
            # PostgreSQL checkpoint가 준비되지 않아도 IDE 자체는 기동합니다.
            self._cm = None
            self.checkpointer = None
            self.graph = build_workflow(checkpointer=None)
            self.persistent = False
            self._active_url = url
            self.last_error = str(exc)
            return False

    async def start(self, *, force: bool = False) -> bool:
        url = self._current_url()
        async with self._lock:
            if (
                not force
                and self.graph is not None
                and self.persistent
                and self._active_url == url
            ):
                return True
            return await self._start_locked(url)

    async def restart(self) -> bool:
        """현재 backend/.env의 LANGGRAPH_DATABASE_URL로 즉시 다시 연결합니다."""
        return await self.start(force=True)

    async def ensure_current(self, *, retry_interval_seconds: float = 10.0) -> bool:
        """
        상태 화면 조회 시 현재 .env URL과 런타임 checkpointer 상태를 동기화합니다.

        정상 연결 상태에서는 DB 재접속을 하지 않습니다. 실패 상태일 때만 일정 간격으로
        자동 재시도하여, 설정 화면에서 DB 정보를 고친 뒤 재시작 없이 녹색 상태로 복구됩니다.
        """
        url = self._current_url()
        if self.persistent and self.graph is not None and self._active_url == url:
            return True

        now = time.monotonic()
        if (
            self._active_url == url
            and self._last_attempt_monotonic
            and (now - self._last_attempt_monotonic) < retry_interval_seconds
        ):
            return False

        return await self.start(force=True)

    async def stop(self):
        async with self._lock:
            await self._close_checkpointer_locked()
            self.graph = None
            self.persistent = False
            self._active_url = ""
            self._override_url = ""
            self.last_error = ""


agent_graph_runtime = AgentGraphRuntime()
