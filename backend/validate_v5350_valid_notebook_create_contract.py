from __future__ import annotations

import asyncio
import hashlib
import json
import tempfile
from pathlib import Path

from app.services.local_control import create_file, register_runtime_project_root

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend/src/App.jsx").read_text(encoding="utf-8")
SERVICE = (ROOT / "backend/app/services/local_control.py").read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


require("AGENTSTUDIO_FRONTEND_VERSION='5.369'" in APP, "frontend version must be 5.369")
require("def _new_notebook_payload() -> bytes:" in SERVICE, "Notebook initializer missing")
require('target.suffix.casefold() == ".ipynb"' in SERVICE, "ipynb create branch missing")
require("repaired_empty_notebook" in SERVICE, "legacy zero-byte Notebook repair missing")


async def run() -> None:
    with tempfile.TemporaryDirectory(prefix="agentstudio-v5350-") as tmp:
        root = Path(tmp)
        register_runtime_project_root(str(root))

        created = await create_file(str(root), "new_notebook.ipynb")
        path = root / "new_notebook.ipynb"
        require(created.get("ok") is True, f"create failed: {created}")
        require(created.get("created") is True, f"must report created: {created}")
        require(path.stat().st_size > 0, "new Notebook must not be zero bytes")
        raw = path.read_bytes()
        notebook = json.loads(raw.decode("utf-8"))
        require(notebook.get("nbformat") == 4, f"unexpected nbformat: {notebook}")
        require(notebook.get("nbformat_minor") == 4, f"unexpected nbformat minor: {notebook}")
        require(len(notebook.get("cells") or []) == 1, "new Notebook must contain one empty cell")
        cell = notebook["cells"][0]
        require(cell.get("cell_type") == "code", f"initial cell must be code: {cell}")
        require(cell.get("source") == [], f"initial code cell must be empty: {cell}")
        require(cell.get("outputs") == [], f"initial outputs must be empty: {cell}")
        require(created.get("sha256") == hashlib.sha256(raw).hexdigest(), "create sha256 mismatch")

        plain = await create_file(str(root), "plain.py")
        require((root / "plain.py").stat().st_size == 0, f"plain file should stay empty: {plain}")

        legacy = root / "legacy.ipynb"
        legacy.write_bytes(b"")
        repaired = await create_file(str(root), "legacy.ipynb")
        require(repaired.get("created") is False, f"legacy file already existed: {repaired}")
        require(repaired.get("repaired_empty_notebook") is True, f"legacy Notebook was not repaired: {repaired}")
        require(json.loads(legacy.read_text(encoding="utf-8")).get("cells") is not None, "repaired Notebook invalid")

        existing = root / "existing.ipynb"
        existing_text = json.dumps({"cells": [], "metadata": {"owner": "user"}, "nbformat": 4, "nbformat_minor": 4})
        existing.write_text(existing_text, encoding="utf-8")
        second = await create_file(str(root), "existing.ipynb")
        require(second.get("created") is False, f"existing file should be idempotent: {second}")
        require(second.get("repaired_empty_notebook") is False, f"non-empty Notebook must not be repaired: {second}")
        require(existing.read_text(encoding="utf-8") == existing_text, "existing Notebook was overwritten")


asyncio.run(run())
print("PASS v5.369 Valid Notebook Create contract")
