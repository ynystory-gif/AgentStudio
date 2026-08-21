from __future__ import annotations

import re
from contextlib import asynccontextmanager
from typing import AsyncIterator
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.core.database import normalize_schema_name, postgres_search_path, quote_identifier


_SEARCH_PATH_OPTION_RE = re.compile(r"(?:^|\s)-c(?:\s*)search_path=([^\s]+)")


def _psycopg_conn_string(value: str) -> str:
    """Normalize SQLAlchemy-style PostgreSQL URLs for psycopg and strip our startup search_path option.

    v5.295 encoded ``options=-csearch_path=...`` into the URL. Supabase's PgBouncer
    session endpoint can accept the connection while not reliably preserving that startup option
    for the checkpointer migration path. v5.296 therefore extracts the desired schema and applies
    ``SET search_path`` on the exact psycopg connection used by LangGraph.
    """
    raw = str(value or "").strip()
    for prefix in (
        "postgresql+asyncpg://",
        "postgresql+psycopg://",
        "postgresql+psycopg_async://",
    ):
        if raw.startswith(prefix):
            raw = "postgresql://" + raw[len(prefix) :]
            break

    parts = urlsplit(raw)
    query_pairs = parse_qsl(parts.query, keep_blank_values=True)
    filtered: list[tuple[str, str]] = []
    for key, val in query_pairs:
        if key.lower() == "options" and _SEARCH_PATH_OPTION_RE.search(val or ""):
            # The search_path is re-applied explicitly on the opened psycopg connection.
            continue
        filtered.append((key, val))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(filtered), parts.fragment))


def schema_from_conn_string(value: str) -> str:
    """Read the first schema from the v5.295+ search_path URL option, if present."""
    parts = urlsplit(str(value or "").strip())
    for key, val in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower() != "options":
            continue
        match = _SEARCH_PATH_OPTION_RE.search(val or "")
        if not match:
            continue
        first = (match.group(1).split(",", 1)[0] or "").strip().strip('"')
        return normalize_schema_name(first)
    return ""


@asynccontextmanager
async def open_schema_pinned_checkpointer(
    database_url: str,
    *,
    schema: str = "",
) -> AsyncIterator[object]:
    """Open LangGraph AsyncPostgresSaver on one schema-pinned psycopg session.

    Python ``langgraph-checkpoint-postgres`` currently uses unqualified table names.
    For Supabase custom schemas we must therefore set ``search_path`` on the SAME
    connection that runs ``setup()`` and all runtime checkpoint SQL.
    """
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from psycopg import AsyncConnection
    from psycopg.rows import dict_row

    target_schema = normalize_schema_name(schema or schema_from_conn_string(database_url))
    conn_string = _psycopg_conn_string(database_url)

    async with await AsyncConnection.connect(
        conn_string,
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
    ) as conn:
        if target_schema:
            qschema = quote_identifier(target_schema)
            await conn.execute(
                f'SET search_path TO {qschema}, "extensions", "public"'
            )
            result = await conn.execute(
                "SELECT current_schema() AS current_schema, "
                "current_setting('search_path') AS search_path"
            )
            row = await result.fetchone()
            actual_schema = str((row or {}).get("current_schema") or "")
            if actual_schema != target_schema:
                actual_path = str((row or {}).get("search_path") or "")
                raise RuntimeError(
                    "LangGraph PostgreSQL search_path 고정 실패: "
                    f"기대={target_schema}, 실제={actual_schema or '-'}, "
                    f"search_path={actual_path or '-'}"
                )

        yield AsyncPostgresSaver(conn)
