from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"{label}: missing {needle!r}")


app = (ROOT / "frontend/src/App.jsx").read_text(encoding="utf-8")
api_ts = (ROOT / "frontend/src/api.ts").read_text(encoding="utf-8")
memo = (ROOT / "frontend/src/components/memo/ProjectMemoPanel.tsx").read_text(encoding="utf-8")
diagram = (ROOT / "frontend/src/components/database/DatabaseDiagramViewer.tsx").read_text(encoding="utf-8")
learning = (ROOT / "frontend/src/components/learning/LlmLearningCenter.tsx").read_text(encoding="utf-8")
routes = (ROOT / "backend/app/api/routes.py").read_text(encoding="utf-8")
main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
settings = (ROOT / "backend/app/services/settings_service.py").read_text(encoding="utf-8")
browser = (ROOT / "backend/app/services/chromium_browser_service.py").read_text(encoding="utf-8")
system_admin = (ROOT / "SYSTEM_ADMIN.ps1").read_text(encoding="utf-8-sig")

require(app, "AGENTSTUDIO_FRONTEND_VERSION='5.493'", "frontend version")
require(main, 'version="5.493"', "backend version")
require(routes, '"version": "5.493"', "health version")
require(routes, '@router.post("/output/save")', "output API")
require(routes, "save_output_text", "transcript output")
require(api_ts, "saveBlobToOutput", "frontend output helper")
for source, label in ((app, "App downloads"), (memo, "recording"), (diagram, "diagram"), (learning, "learning SQL")):
    require(source, "saveBlobToOutput", label)
require(settings, "apply_runtime_path_policy()", "settings runtime apply")
require(main, "bootstrap_runtime_paths_from_env_file()", "early path bootstrap")
require(browser, 'resolve_cache_root() / "browser" / "profile"', "browser cache")
require(browser, 'resolve_temp_root() / "browser" / "runtime"', "browser temp")
require(browser, 'resolve_output_root() / "browser-downloads"', "browser output")
for key in ("DEFAULT_TEMP_ROOT", "DEFAULT_CACHE_ROOT", "DEFAULT_OUTPUT_ROOT", "PIP_CACHE_DIR", "NPM_CONFIG_CACHE"):
    require(system_admin, key, f"SYSTEM_ADMIN {key}")

for path in [
    ROOT / "frontend/src/App.jsx",
    ROOT / "frontend/src/components/memo/ProjectMemoPanel.tsx",
    ROOT / "frontend/src/components/database/DatabaseDiagramViewer.tsx",
    ROOT / "frontend/src/components/learning/LlmLearningCenter.tsx",
]:
    text = path.read_text(encoding="utf-8")
    if "anchor.download=" in text or "link.download=" in text or ' download="agentstudio-recording.webm"' in text:
        raise AssertionError(f"legacy browser download remains: {path}")

print("v5.493 RuntimePathPolicy contract PASS")
