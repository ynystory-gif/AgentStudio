from __future__ import annotations

import tempfile
from pathlib import Path

from app.services.python_execution_service import PythonExecutionManager

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend/src/App.jsx").read_text(encoding="utf-8")
SERVICE = (ROOT / "backend/app/services/python_execution_service.py").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require("AGENTSTUDIO_FRONTEND_VERSION='5.371'" in APP, "frontend version must be 5.371")
require("ast.PyCF_ALLOW_TOP_LEVEL_AWAIT if notebook_mode else 0" in SERVICE, "Notebook compile flag missing")
require("_agentstudio_run_awaitable" in SERVICE, "awaitable runner missing")
require("loop.run_until_complete(value)" in SERVICE, "persistent asyncio execution missing")

with tempfile.TemporaryDirectory(prefix="agentstudio-v5349-") as tmp:
    project = Path(tmp)
    notebook = project / "lesson.ipynb"
    notebook.write_text("{}", encoding="utf-8")
    manager = PythonExecutionManager()
    session_id = "v5349-contract"
    try:
        first = manager.execute(
            root=str(project),
            relative_path="lesson.ipynb",
            session_id=session_id,
            code=(
                "import asyncio\n"
                "async def double(value):\n"
                "    await asyncio.sleep(0)\n"
                "    return value * 2\n"
                "result = await double(21)\n"
                "print(result)\n"
            ),
            notebook_mode=True,
            cell_index=0,
        )
        require(first.get("ok") is True, f"Notebook top-level await failed: {first}")
        require(first.get("stdout") == "42\n", f"unexpected await stdout: {first.get('stdout')!r}")

        second = manager.execute(
            root=str(project),
            relative_path="lesson.ipynb",
            session_id=session_id,
            code="await double(result)",
            notebook_mode=True,
            cell_index=1,
            capture_last_expression=True,
        )
        require(second.get("ok") is True, f"last-expression await failed: {second}")
        require(second.get("stdout") == "84\n", f"unexpected captured result: {second.get('stdout')!r}")

        script = manager.execute(
            root=str(project),
            relative_path="plain.py",
            session_id="plain-script-contract",
            code="await double(1)",
            notebook_mode=False,
        )
        require(script.get("ok") is False, "plain .py top-level await must stay invalid")
        require(script.get("error_type") == "SyntaxError", f"plain mode must raise SyntaxError: {script}")
    finally:
        manager.stop(str(project), session_id)
        manager.stop(str(project), "plain-script-contract")

print("PASS v5.371 Notebook Top-Level Await contract")
