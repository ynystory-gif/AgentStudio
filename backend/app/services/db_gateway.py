from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.machine_identity import current_pc_name

from app.models.entities import (
    AppSetting,
    Project,
    ConversationMessage,
    Requirement,
    MCPServer,
    ToolRecord,
    MemoryRecord,
    UsageRecord,
    JobRecord,
    ProjectAnalysis,
)


class DatabaseGateway:
    """
    AgentStudio의 모든 영속화 쓰기 작업을 한 곳으로 모읍니다.

    외부(React/Agent/Tool)는 DB에 직접 연결하지 않고 FastAPI endpoint를 호출합니다.
    FastAPI endpoint -> service -> DatabaseGateway -> PostgreSQL 순서로 저장합니다.
    """

    @staticmethod
    async def upsert_setting(
        session: AsyncSession,
        *,
        key: str,
        value: str,
        is_secret: bool = False,
    ) -> AppSetting:
        pc_name = current_pc_name()
        row = (
            await session.execute(
                select(AppSetting).where(
                    AppSetting.pc_name == pc_name,
                    AppSetting.key == key,
                )
            )
        ).scalar_one_or_none()

        if row:
            row.value = value
            row.is_secret = is_secret
        else:
            row = AppSetting(
                pc_name=pc_name,
                key=key,
                value=value,
                is_secret=is_secret,
            )
            session.add(row)

        return row

    @staticmethod
    async def create_project(
        session: AsyncSession,
        **values: Any,
    ) -> Project:
        row = Project(**values)
        session.add(row)
        return row

    @staticmethod
    async def add_conversation(
        session: AsyncSession,
        **values: Any,
    ) -> ConversationMessage:
        row = ConversationMessage(**values)
        session.add(row)
        return row

    @staticmethod
    async def add_requirement(
        session: AsyncSession,
        **values: Any,
    ) -> Requirement:
        row = Requirement(**values)
        session.add(row)
        return row

    @staticmethod
    async def add_mcp_server(
        session: AsyncSession,
        **values: Any,
    ) -> MCPServer:
        row = MCPServer(**values)
        session.add(row)
        return row

    @staticmethod
    async def add_tool_record(
        session: AsyncSession,
        **values: Any,
    ) -> ToolRecord:
        row = ToolRecord(**values)
        session.add(row)
        return row

    @staticmethod
    async def add_memory(
        session: AsyncSession,
        **values: Any,
    ) -> MemoryRecord:
        row = MemoryRecord(**values)
        session.add(row)
        return row

    @staticmethod
    async def add_usage(
        session: AsyncSession,
        **values: Any,
    ) -> UsageRecord:
        row = UsageRecord(**values)
        session.add(row)
        return row

    @staticmethod
    async def add_job(
        session: AsyncSession,
        **values: Any,
    ) -> JobRecord:
        row = JobRecord(**values)
        session.add(row)
        return row

    @staticmethod
    async def upsert_project_analysis(
        session: AsyncSession,
        *,
        project_id: int,
        project_root: str,
        project_name: str = "",
        summary: str = "",
        tech_stack: list | None = None,
        entry_points: list | None = None,
        major_files: list | None = None,
        mcp_tools: list | None = None,
        structure: dict | None = None,
        raw_analysis: dict | None = None,
    ) -> ProjectAnalysis:
        row = (
            await session.execute(
                select(ProjectAnalysis).where(
                    ProjectAnalysis.project_id == project_id
                )
            )
        ).scalar_one_or_none()

        values = {
            "project_root": project_root,
            "project_name": project_name,
            "summary": summary,
            "tech_stack": tech_stack or [],
            "entry_points": entry_points or [],
            "major_files": major_files or [],
            "mcp_tools": mcp_tools or [],
            "structure": structure or {},
            "raw_analysis": raw_analysis or {},
        }

        if row:
            for key, value in values.items():
                setattr(row, key, value)
        else:
            row = ProjectAnalysis(
                project_id=project_id,
                **values,
            )
            session.add(row)

        return row

    @staticmethod
    async def touch_project_opened(
        session: AsyncSession,
        project: Project,
    ) -> Project:
        from datetime import datetime
        project.last_opened_at = datetime.utcnow()
        return project

    @staticmethod
    async def set_project_favorite(
        session: AsyncSession,
        project: Project,
        is_favorite: bool,
    ) -> Project:
        project.is_favorite = bool(is_favorite)
        return project
