from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
renderer = (ROOT / "frontend/src/components/notebook/NotebookRenderers.tsx").read_text(encoding="utf-8")
status_css = (ROOT / "frontend/src/components/notebook/NotebookOutputStatus.css").read_text(encoding="utf-8")
service = (ROOT / "backend/app/services/python_execution_service.py").read_text(encoding="utf-8")
main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
routes = (ROOT / "backend/app/api/routes.py").read_text(encoding="utf-8")
app = (ROOT / "frontend/src/App.jsx").read_text(encoding="utf-8")

checks = {
    "frontend version": "AGENTSTUDIO_FRONTEND_VERSION='5.490'" in app,
    "backend version": 'version="5.490"' in main,
    "health version": '"version": "5.490"' in routes,
    "external worker runtime preserved": '_WORKER_RUNTIME_PATH = Path(__file__).with_name("python_worker_runtime.py")' in service,
    "warning classifier": "NOTEBOOK_WARNING_TYPE_PATTERN" in renderer,
    "warning disclosure": "NotebookWarningOutput" in renderer and "자세히 보기" in renderer,
    "stderr no longer auto error": "output.name === 'stderr' ? 'notebook-output-stream error'" not in renderer,
    "actual errors stay red": "outputType === 'error'" in renderer and 'notebook-output-stream error' in renderer,
    "warning css": ".notebook-output-warning" in status_css and ".notebook-output-stream.stderr" in status_css,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("v5.490 Notebook warning output contract failed: " + ", ".join(failed))
print("v5.490 Notebook warning output contract: PASS")
