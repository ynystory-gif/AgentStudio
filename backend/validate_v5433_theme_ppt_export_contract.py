from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
API = (ROOT / "frontend" / "src" / "api.ts").read_text(encoding="utf-8")
MAIN = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
HYBRID = (ROOT / "backend" / "app" / "services" / "ui_theme_hybrid_analysis_service.py").read_text(encoding="utf-8")
BROWSER = (ROOT / "backend" / "app" / "services" / "ui_theme_browser_analysis_service.py").read_text(encoding="utf-8")
BROWSER_PROCESS = (ROOT / "backend" / "app" / "services" / "ui_theme_browser_process_service.py").read_text(encoding="utf-8")
ROUTES = (ROOT / "backend" / "app" / "api" / "ui_theme_dynamic_routes.py").read_text(encoding="utf-8")

checks = {
    "frontend version 5.433": "AGENTSTUDIO_FRONTEND_VERSION='5.433'" in APP,
    "authenticated raw fetch helper": "export async function apiFetch" in API and "Authorization:`Bearer ${token}`" in API,
    "ppt export uses authenticated fetch": "apiFetch('/presentation/export'" in APP,
    "notebook stream uses authenticated fetch": "apiFetch('/python/execute/stream'" in APP,
    "cors registered after auth guard": MAIN.index("app.add_middleware(\n    CORSMiddleware") > MAIN.index("async def _agentstudio_auth_guard"),
    "backend version 5.433": 'version="5.433"' in MAIN,
    "parallel static browser tasks": "static_task=asyncio.create_task(_analyze_static_theme(url))" in HYBRID and "browser_task=asyncio.create_task(analyze_rendered_theme_layout(url))" in HYBRID,
    "static failure is non fatal": "렌더링 분석 결과로 계속합니다" in HYBRID,
    "rendered computed style analysis": "_derive_rendered_theme_analysis" in BROWSER and "rootVars" in BROWSER,
    "browser process returns theme analysis": "'analysis':analysis" in BROWSER_PROCESS,
    "both branches required to fail": "if not usable:" in HYBRID,
    "hard timeout remains 300": "_JOB_TIMEOUT_SECONDS = 300" in ROUTES,
}

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
if failed:
    raise SystemExit(f"v5.433 contract failed: {', '.join(failed)}")
print(f"v5.433 contract PASS {len(checks)}/{len(checks)}")
