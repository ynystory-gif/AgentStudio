from __future__ import annotations

import re
from collections.abc import Iterable

_IDENTIFIER_RE = re.compile(r"^[a-z][a-z0-9_]{0,62}$")
DEFAULT_TECHNICAL_PREFIXES = ("rag_", "app_", "tbl_", "tb_")


def logical_table_name(table_name: str, *, prefixes: Iterable[str] | None = None) -> str:
    """Return the logical table name used for the default PK column.

    Technical namespace prefixes are not part of the business identity name.
    Examples: rag_chunks -> chunks, app_users -> users, users -> users.
    Additional project prefixes can be supplied by the DB design policy.
    """
    value = str(table_name or "").strip().lower()
    if not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"허용되지 않는 테이블명: {table_name}")
    candidates = list(prefixes or ()) + list(DEFAULT_TECHNICAL_PREFIXES)
    # Longest first prevents a shorter project prefix from stealing a longer one.
    normalized = sorted({str(x or "").strip().lower() for x in candidates if str(x or "").strip()}, key=len, reverse=True)
    for prefix in normalized:
        prefix_value = prefix if prefix.endswith("_") else prefix + "_"
        if value.startswith(prefix_value) and len(value) > len(prefix_value):
            return value[len(prefix_value):]
    return value


def primary_key_column_name(table_name: str, *, prefixes: Iterable[str] | None = None) -> str:
    logical = logical_table_name(table_name, prefixes=prefixes)
    return logical if logical.endswith("_id") else f"{logical}_id"
