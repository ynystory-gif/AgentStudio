from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend/src/App.jsx").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/src/styles.css").read_text(encoding="utf-8")
MAIN = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
ROUTES = (ROOT / "backend/app/api/routes.py").read_text(encoding="utf-8")
CODEX = (ROOT / "backend/app/services/codex_app_server_service.py").read_text(encoding="utf-8")

checks = {
    "frontend version": "AGENTSTUDIO_FRONTEND_VERSION='5.451'" in APP,
    "backend version": 'version="5.451"' in MAIN and '"version": "5.451"' in ROUTES,
    "codex version": 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.451"' in CODEX,
    "scroll region added": 'className="code-llm-scroll-region" ref={codeEditChatRef}' in APP,
    "chat moved inside scroll region": 'className="code-llm-scroll-region" ref={codeEditChatRef}' in APP and '<div className="code-llm-chat">' in APP,
    "global scroll styling": '.code-llm-side.chat-only>.code-llm-scroll-region{' in CSS and 'overflow-y:auto;' in CSS,
    "chat no self-scroll": '.code-llm-side.chat-only>.code-llm-scroll-region>.code-llm-chat{' in CSS and 'overflow:visible;' in CSS,
    "reference list no inner scroll": '.llm-code-chat-panel .code-edit-reference-list{' in CSS and 'max-height:none;' in CSS and 'overflow:visible;' in CSS,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('v5.451 contract failed: ' + ', '.join(failed))
print(f"v5.451 contracts: {len(checks)}/{len(checks)} PASS")
