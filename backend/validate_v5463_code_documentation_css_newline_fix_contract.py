from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend/src/App.jsx").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/src/styles.css").read_text(encoding="utf-8")
MAIN = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
ROUTES = (ROOT / "backend/app/api/routes.py").read_text(encoding="utf-8")
CODEX = (ROOT / "backend/app/services/codex_app_server_service.py").read_text(encoding="utf-8")

marker = "/* ===== v5.461 Agent Factory code documentation option ===== */"
assert marker in CSS, "code documentation CSS marker missing"
block = CSS[CSS.index(marker):]

checks = [
    ("frontend version", "AGENTSTUDIO_FRONTEND_VERSION='5.463'" in APP),
    ("backend version", 'version="5.463"' in MAIN and '"version": "5.463"' in ROUTES),
    ("codex version", 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.463"' in CODEX),
    ("no literal newline escape in documentation css", r"\n" not in block),
    ("development start selector", ".development-start-control{" in block),
    ("documentation option selector", ".code-documentation-option{" in block),
    ("responsive media rule", "@media(max-width:760px){" in block),
    ("build marker", "CodeDocumentationCssLiteralNewlineFix" in ROUTES),
]
failed = [name for name, ok in checks if not ok]
if failed:
    raise SystemExit("FAIL v5.463 contract: " + ", ".join(failed))
print(f"PASS v5.463 Code Documentation CSS Newline Fix contract {len(checks)}/{len(checks)}")
