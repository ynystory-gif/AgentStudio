from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend/src/App.jsx").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/src/styles.css").read_text(encoding="utf-8")
MAIN = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
ROUTES = (ROOT / "backend/app/api/routes.py").read_text(encoding="utf-8")
CODEX = (ROOT / "backend/app/services/codex_app_server_service.py").read_text(encoding="utf-8")

checks = [
    ("frontend version", "AGENTSTUDIO_FRONTEND_VERSION='5.464'" in APP),
    ("backend version", 'version="5.464"' in MAIN and '"version": "5.464"' in ROUTES),
    ("codex version", 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.464"' in CODEX),
    ("toggle helper exists", "function CodeDocumentationToggle" in APP),
    ("title action contains toggle", 'title="Agent 제작 진행"' in APP and 'action={<CodeDocumentationToggle' in APP),
    ("two title placements", APP.count('action={<CodeDocumentationToggle') == 2),
    ("toggle removed from development start wrapper", 'className="development-start-control"' not in APP),
    ("old option class removed from jsx", 'code-documentation-option' not in APP),
    ("develop start remains", '▶ 개발 시작' in APP),
    ("toggle state remains wired", 'enabled={codeDocumentationEnabled}' in APP and 'onChange={setCodeDocumentationEnabled}' in APP),
    ("title toggle css", '.agent-build-title-doc-option{' in CSS),
    ("old development control css removed", '.development-start-control{' not in CSS),
    ("old option css removed", '.code-documentation-option{' not in CSS),
]
failed=[name for name,ok in checks if not ok]
for name,ok in checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
if failed:
    raise SystemExit("FAIL v5.464 contract: " + ", ".join(failed))
print(f"PASS v5.464 Code Documentation Title Relocation contract {len(checks)}/{len(checks)}")
