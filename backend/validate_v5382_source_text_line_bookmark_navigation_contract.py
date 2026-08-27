from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
NOTEBOOK = (ROOT / "frontend" / "src" / "components" / "notebook" / "NotebookEditor.tsx").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "src" / "styles.css").read_text(encoding="utf-8")
MAIN = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
ROUTES = (ROOT / "backend" / "app" / "api" / "routes.py").read_text(encoding="utf-8")
SERVICE = (ROOT / "backend" / "app" / "services" / "codex_app_server_service.py").read_text(encoding="utf-8")

checks = {
    "frontend version": "AGENTSTUDIO_FRONTEND_VERSION='5.382'" in APP,
    "backend main version": 'version="5.382"' in MAIN,
    "backend health version": '"version": "5.382"' in ROUTES,
    "codex client version": 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.382"' in SERVICE,
    "build marker": "SourceTextLineBookmarkNavigation" in ROUTES,
    "text bookmark storage": "TEXT_EDITOR_BOOKMARK_STORAGE_PREFIX" in APP and "localStorage.setItem" in APP,
    "text bookmark toolbar": "editor-bookmark-toolbar" in APP and "🔖 현재 줄" in APP,
    "text previous next navigation": "moveToEditorBookmark(-1)" in APP and "moveToEditorBookmark(1)" in APP,
    "text glyph margin": "glyphMargin:true" in APP and "editor-line-bookmark-glyph" in APP,
    "text gutter click": "[2,3,4].includes(targetType)" in APP,
    "notebook explicit current line button": "toggleActiveLineBookmark" in NOTEBOOK and "🔖 현재 줄" in NOTEBOOK,
    "notebook widened click target": "[2, 3, 4].includes(Number(event?.target?.type))" in NOTEBOOK,
    "bookmark css": ".editor-line-bookmark-glyph::before" in CSS and ".editor-bookmark-toolbar" in CSS,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("FAIL v5.382 contract: " + ", ".join(failed))
print("PASS v5.382 Source/Text Line Bookmark Navigation contract")
