from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "backend/app/main.py").read_text(encoding="utf-8-sig")
ROUTES = (ROOT / "backend/app/api/routes.py").read_text(encoding="utf-8-sig")
APP = (ROOT / "frontend/src/App.jsx").read_text(encoding="utf-8-sig")
CODEX = (ROOT / "backend/app/services/codex_app_server_service.py").read_text(encoding="utf-8-sig")

checks = {
    "health is public": '"/api/health",' in MAIN,
    "health middleware does not short-circuit cors": 'if path == "/api/health":' not in MAIN,
    "public api uses call_next": 'path in _PUBLIC_API_PATHS or path in _AUTH_BOOTSTRAP_PATHS:\n        return await call_next(request)' in MAIN,
    "cors localhost regex": 'allow_origin_regex=r"^https?://(127\\.0\\.0\\.1|localhost):\\d+$"' in MAIN,
    "backend version": 'version="5.432"' in MAIN,
    "route version": '"version": "5.432"' in ROUTES,
    "frontend version": "AGENTSTUDIO_FRONTEND_VERSION='5.432'" in APP,
    "codex version": 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.432"' in CODEX,
    "theme backend 5 minute timeout retained": 'HARD_JOB_TIMEOUT_SECONDS = 300' in (ROOT / "backend/app/services/ui_theme_job_hard_timeout_bridge.py").read_text(encoding="utf-8-sig"),
}
failed=[name for name,ok in checks.items() if not ok]
if failed:
    raise SystemExit("v5.430 contract FAIL: "+", ".join(failed))
print(f"v5.430 backend health CORS + 5-minute Theme timeout contract PASS {len(checks)}/{len(checks)}")
