from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.python_execution_service import (  # noqa: E402
    PythonExecutionManager,
    _split_notebook_package_cell,
)

service = (ROOT / "backend/app/services/python_execution_service.py").read_text(encoding="utf-8")
runtime = ROOT / "backend/app/services/python_worker_runtime.py"
routes = (ROOT / "backend/app/api/routes.py").read_text(encoding="utf-8")
app = (ROOT / "frontend/src/App.jsx").read_text(encoding="utf-8")
main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")

checks = {
    "worker runtime file": runtime.exists() and runtime.stat().st_size > 10000,
    "no inline worker code": "_WORKER_CODE = r'''" not in service,
    "no python -c worker bootstrap": '[interpreter, "-u", "-c", _WORKER_CODE]' not in service,
    "runtime path bootstrap": '[interpreter, "-u", str(worker_runtime)]' in service,
    "package backend method": "def execute_package_cell(" in service,
    "package backend route": '@router.post("/python/packages/execute")' in routes,
    "frontend package route": "api('/python/packages/execute'" in app,
    "frontend version": "AGENTSTUDIO_FRONTEND_VERSION='5.489'" in app,
    "backend version": 'version="5.489"' in main,
    "health version": '"version": "5.489"' in routes,
}
failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(f"[{'OK' if ok else 'FAIL'}] {name}")
if failed:
    raise SystemExit("v5.489 static contract failed: " + ", ".join(failed))

commands, remaining = _split_notebook_package_cell('%pip --version\nprint("after-pip")')
assert commands == [["--version"]], commands
assert 'print("after-pip")' in remaining

manager = PythonExecutionManager()
with tempfile.TemporaryDirectory(prefix="에이전트_스튜디오_회귀_") as td:
    project = Path(td) / ("긴프로젝트_" + "가" * 32)
    project.mkdir(parents=True)
    notebook = project / "한글_긴_노트북_테스트.ipynb"
    notebook.write_text("{}", encoding="utf-8")

    first = manager.execute(
        root=str(project), code="a=10\nprint(a)", relative_path=notebook.name,
        session_id="regression", notebook_mode=True, cell_index=0,
    )
    assert first.get("ok") and "10" in str(first.get("stdout") or ""), first

    second = manager.execute(
        root=str(project), code="print(a+20)", relative_path=notebook.name,
        session_id="regression", notebook_mode=True, cell_index=1,
    )
    assert second.get("ok") and "30" in str(second.get("stdout") or ""), second

    awaited = manager.execute(
        root=str(project), code='import asyncio\nawait asyncio.sleep(0)\nprint("await-ok")',
        relative_path=notebook.name, session_id="regression", notebook_mode=True, cell_index=2,
    )
    assert awaited.get("ok") and "await-ok" in str(awaited.get("stdout") or ""), awaited

    package = manager.execute_package_cell(
        root=str(project), code='%pip --version\nprint("after-pip")', relative_path=notebook.name,
        session_id="regression", notebook_mode=True, cell_index=3, timeout=120,
    )
    assert package.get("ok"), package
    assert package.get("package_environment_refreshed") is True, package
    assert "after-pip" in str(package.get("stdout") or ""), package

    after_reset = manager.execute(
        root=str(project), code='print("fresh-worker-ok")', relative_path=notebook.name,
        session_id="regression", notebook_mode=True, cell_index=4,
    )
    assert after_reset.get("ok") and "fresh-worker-ok" in str(after_reset.get("stdout") or ""), after_reset
    manager.reset(str(project), "regression")

print("v5.489 Windows Python Worker Runtime regression: PASS")
