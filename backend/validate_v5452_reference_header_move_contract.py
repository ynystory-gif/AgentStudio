from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend/src/App.jsx").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/src/styles.css").read_text(encoding="utf-8")
MAIN = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
ROUTES = (ROOT / "backend/app/api/routes.py").read_text(encoding="utf-8")
CODEX = (ROOT / "backend/app/services/codex_app_server_service.py").read_text(encoding="utf-8")

checks = {
    "frontend version": "AGENTSTUDIO_FRONTEND_VERSION='5.452'" in APP,
    "backend version": 'version="5.452"' in MAIN and '"version": "5.452"' in ROUTES,
    "codex version": 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.452"' in CODEX,
    "header summary moved": 'className="code-edit-reference-summary"' in APP and 'LLM 참조 문구 {codeEditReferences.length}개' in APP,
    "selected filename removed from llm panel header": "<span>{selected ? selected.split(/[\\/]/).pop() : '파일 선택 필요'}</span>" not in APP,
    "reference head removed": '<div className="code-edit-reference-head">' not in APP[19000:19650],
    "summary style added": '.ux-pane-title .code-edit-reference-summary{' in CSS,
}
failed=[name for name,ok in checks.items() if not ok]
if failed:
    raise SystemExit('v5.452 contract failed: ' + ', '.join(failed))
print(f"v5.452 contracts: {len(checks)}/{len(checks)} PASS")
