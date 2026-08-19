from __future__ import annotations

from pathlib import Path

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.entities import Project
from app.services.local_control import (
    get_runtime_project_roots,
    register_runtime_project_root,
)


def _path_key(value: str) -> str:
    """Return a stable comparison key for local project roots.

    Windows project paths are case-insensitive, while AgentStudio also runs in
    development/test environments on other platforms. Path.resolve() handles
    separators and relative segments; casefold keeps Windows DB rows robust to
    casing differences without granting arbitrary parent folders.
    """
    try:
        resolved = Path(str(value or "")).expanduser().resolve()
        return str(resolved).casefold()
    except Exception:
        return str(value or "").strip().replace("/", "\\").casefold()


async def restore_registered_project_roots() -> dict:
    """Restore persisted AgentStudio projects into the runtime allow-list.

    The runtime allow-list intentionally resets whenever the Backend process
    restarts. Persisted Project rows are trusted because the user explicitly
    registered/imported them through AgentStudio earlier. Only paths that
    currently exist as directories are restored; missing/offline paths are
    reported but never broadened to their parent directories.
    """
    restored: list[str] = []
    missing: list[str] = []
    failed: list[dict] = []

    async with SessionLocal() as session:
        rows = (await session.execute(select(Project.root_path))).scalars().all()

    seen: set[str] = set()
    for raw in rows:
        value = str(raw or "").strip()
        if not value:
            continue
        key = _path_key(value)
        if key in seen:
            continue
        seen.add(key)

        path = Path(value).expanduser()
        if not path.exists() or not path.is_dir():
            missing.append(value)
            continue

        try:
            restored.append(register_runtime_project_root(value))
        except Exception as exc:
            failed.append({
                "project_root": value,
                "error": str(exc),
                "exception": type(exc).__name__,
            })

    return {
        "ok": not failed,
        "restored": restored,
        "restored_count": len(restored),
        "missing": missing,
        "missing_count": len(missing),
        "failed": failed,
        "failed_count": len(failed),
        "runtime_project_roots": get_runtime_project_roots(),
    }


async def ensure_persisted_project_root(root: str) -> dict:
    """Register *root* only when it exactly matches a persisted Project row.

    This is a self-healing fallback for requests that race with Frontend state
    restoration immediately after Backend restart. It deliberately does not
    permit arbitrary filesystem paths or parent-directory widening.
    """
    requested = str(root or "").strip()
    if not requested:
        return {"ok": False, "registered": False, "reason": "EMPTY_ROOT"}

    target_key = _path_key(requested)

    async with SessionLocal() as session:
        rows = (await session.execute(select(Project.id, Project.root_path))).all()

    for project_id, stored_root in rows:
        value = str(stored_root or "").strip()
        if not value or _path_key(value) != target_key:
            continue

        path = Path(value).expanduser()
        if not path.exists() or not path.is_dir():
            return {
                "ok": False,
                "registered": False,
                "reason": "PROJECT_PATH_MISSING",
                "project_id": project_id,
                "project_root": value,
            }

        normalized = register_runtime_project_root(value)
        return {
            "ok": True,
            "registered": True,
            "reason": "PERSISTED_PROJECT_RESTORED",
            "project_id": project_id,
            "project_root": normalized,
        }

    return {
        "ok": False,
        "registered": False,
        "reason": "PROJECT_NOT_REGISTERED",
        "project_root": requested,
    }
