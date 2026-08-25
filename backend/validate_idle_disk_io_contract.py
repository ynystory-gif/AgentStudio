from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
ROUTES = (ROOT / "backend" / "app" / "api" / "routes.py").read_text(encoding="utf-8")
LOCAL = (ROOT / "backend" / "app" / "services" / "local_control.py").read_text(encoding="utf-8")
REQ = (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def source_contract() -> None:
    require('/files/watch?root=' in APP, "Frontend native watcher WebSocket wiring missing")
    require('setInterval(pollProjectFiles,1500)' not in APP, "Legacy 1.5s project polling still present")
    require("await api(`/files/snapshot?root=" not in APP, "Frontend still performs project snapshot polling")
    require('@router.websocket("/files/watch")' in ROUTES, "Backend file watch WebSocket missing")
    require("awatch(" in LOCAL, "watchfiles native watcher missing")
    require("watchfiles>=1.2" in REQ, "watchfiles dependency is not explicit")
    print("[idle-io-contract] no 1.5s project polling + native watcher wiring: OK")


async def watcher_smoke() -> None:
    from app.services.local_control import register_runtime_project_root, watch_project_changes

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        register_runtime_project_root(str(root))

        async def mutate() -> None:
            await asyncio.sleep(0.35)
            (root / "idle_io_test.py").write_text("print('ok')\n", encoding="utf-8")

        mutator = asyncio.create_task(mutate())
        try:
            async with asyncio.timeout(5):
                async for rows in watch_project_changes(str(root)):
                    require(
                        any(row.get("path") == "idle_io_test.py" for row in rows),
                        f"Unexpected watcher rows: {rows!r}",
                    )
                    break
        finally:
            await mutator

    print("[idle-io-contract] native filesystem event smoke: OK")


if __name__ == "__main__":
    source_contract()
    asyncio.run(watcher_smoke())
