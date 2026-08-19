import asyncio, shutil, uuid
from pathlib import Path
from app.core.config import get_settings
from app.services.local_control import _allowed

async def create_sandbox(project_root: str) -> str:
    source = _allowed(project_root)
    base = Path(get_settings().sandbox_root)
    base.mkdir(parents=True, exist_ok=True)
    target = base / uuid.uuid4().hex
    ignore = shutil.ignore_patterns(".git", ".venv", "node_modules", "__pycache__", "dist")
    await asyncio.to_thread(shutil.copytree, source, target, ignore=ignore)
    return str(target)

async def remove_sandbox(path: str):
    p = Path(path)
    base = Path(get_settings().sandbox_root).resolve()
    if not str(p.resolve()).lower().startswith(str(base).lower()):
        raise PermissionError("Sandbox 경로가 아닙니다.")
    if p.exists():
        await asyncio.to_thread(shutil.rmtree, p, True)
