from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend/src/App.jsx").read_text(encoding="utf-8")
VIEWER = (ROOT / "frontend/src/components/viewers/DocumentViewers.tsx").read_text(encoding="utf-8")
MAIN = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
ROUTES = (ROOT / "backend/app/api/routes.py").read_text(encoding="utf-8")
CODEX = (ROOT / "backend/app/services/codex_app_server_service.py").read_text(encoding="utf-8")

checks = {
    "frontend version": "AGENTSTUDIO_FRONTEND_VERSION='5.455'" in APP,
    "backend version": 'version="5.455"' in MAIN and '"version": "5.455"' in ROUTES,
    "codex version": 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.455"' in CODEX,
    "visible pdf preview heading removed": '<strong>PDF 미리보기</strong>' not in VIEWER,
    "pdf file path kept": '<span>{filePath}</span>' in VIEWER,
    "pdf viewer iframe kept": 'className="pdf-viewer-frame"' in VIEWER,
}
failed=[name for name,ok in checks.items() if not ok]
if failed:
    raise SystemExit('v5.455 contract failed: ' + ', '.join(failed))
print(f"v5.455 contracts: {len(checks)}/{len(checks)} PASS")
