from __future__ import annotations

import ast
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ROUTE_PATH=ROOT/'backend/app/api/ui_theme_dynamic_routes.py'
HYBRID_PATH=ROOT/'backend/app/services/ui_theme_hybrid_analysis_service.py'
FETCH_PATH=ROOT/'backend/app/services/ui_theme_fetch_context_service.py'
HARD_PATH=ROOT/'backend/app/services/ui_theme_job_hard_timeout_bridge.py'
BRIDGE_PATH=ROOT/'backend/app/services/ui_theme_hybrid_bridge.py'
FRONT_V2_PATH=ROOT/'frontend/src/components/layout/LayoutThemeDynamicSourceV2.jsx'
FRONT_LEGACY_PATH=ROOT/'frontend/src/components/layout/LayoutThemeDynamicSourceEnhancer.jsx'
WATCHDOG_PATH=ROOT/'frontend/src/components/layout/ThemeImportWatchdogEnhancer.jsx'
MAIN_PATH=ROOT/'backend/app/main.py'
ROUTES_PATH=ROOT/'backend/app/api/routes.py'
CODEX_PATH=ROOT/'backend/app/services/codex_app_server_service.py'
APP_PATH=ROOT/'frontend/src/App.jsx'

ROUTE=ROUTE_PATH.read_text(encoding='utf-8')
HYBRID=HYBRID_PATH.read_text(encoding='utf-8')
FETCH=FETCH_PATH.read_text(encoding='utf-8')
HARD=HARD_PATH.read_text(encoding='utf-8')
BRIDGE=BRIDGE_PATH.read_text(encoding='utf-8')
FRONT_V2=FRONT_V2_PATH.read_text(encoding='utf-8')
FRONT_LEGACY=FRONT_LEGACY_PATH.read_text(encoding='utf-8')
WATCHDOG=WATCHDOG_PATH.read_text(encoding='utf-8')
MAIN=MAIN_PATH.read_text(encoding='utf-8')
ROUTES=ROUTES_PATH.read_text(encoding='utf-8')
CODEX=CODEX_PATH.read_text(encoding='utf-8')
APP=APP_PATH.read_text(encoding='utf-8')

checks={
    'version sync': 'version="5.432"' in MAIN and '"version": "5.432"' in ROUTES and "AGENTSTUDIO_FRONTEND_VERSION='5.432'" in APP and 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.432"' in CODEX,
    'route hard limit 300': '_JOB_TIMEOUT_SECONDS = 300' in ROUTE and '_URL_ANALYSIS_TIMEOUT_SECONDS = _JOB_TIMEOUT_SECONDS' in ROUTE,
    'no shorter per-url wait_for': 'analysis = await analyze_theme_with_layout_contract(url)' in ROUTE and 'timeout=_URL_ANALYSIS_TIMEOUT_SECONDS' not in ROUTE,
    'static fatal ceiling 300': '_ANALYSIS_HARD_TIMEOUT_SECONDS = 300' in HYBRID and '_STATIC_TIMEOUT_SECONDS = _ANALYSIS_HARD_TIMEOUT_SECONDS' in HYBRID and '_FETCH_TIMEOUT_SECONDS = _ANALYSIS_HARD_TIMEOUT_SECONDS' in HYBRID,
    'static token worker ceiling 300': '_STATIC_WORKER_TIMEOUT_SECONDS = 300' in FETCH,
    'parallel static enrichment': 'asyncio.gather(' in HYBRID and 'parallel_static_layout_workers' in HYBRID and 'Theme 토큰 분석 결과를 유지하고 Chrome CDP 보강 분석을 계속합니다.' in HYBRID,
    'backend watchdog 300': 'HARD_JOB_TIMEOUT_SECONDS = 300' in HARD and 'await asyncio.sleep(HARD_JOB_TIMEOUT_SECONDS)' in HARD,
    'backend timeout terminal failed': 'status="failed"' in HARD and '5분(300초)' in HARD and 'task.cancel()' in HARD and 'shutdown_theme_workers()' in HARD,
    'startup bridge does not shorten': 'dynamic_routes._JOB_TIMEOUT_SECONDS = 300' in BRIDGE and 'dynamic_routes._URL_ANALYSIS_TIMEOUT_SECONDS = dynamic_routes._JOB_TIMEOUT_SECONDS' in BRIDGE,
    'frontend v2 five minutes': 'FRONTEND_HARD_TIMEOUT_MS = 300000' in FRONT_V2 and '최대 분석 5분' in FRONT_V2 and 'job_age_seconds' in FRONT_V2 and 'backend_hard_timeout_seconds' in FRONT_V2,
    'frontend timeout is not user cancel': 'Never call the user-cancel endpoint because' in FRONT_V2 and 'Frontend 전체 제한 3분' not in FRONT_V2,
    'legacy frontend five minutes': 'jobTimeout=300' in FRONT_LEGACY and '전체 분석 제한 5분' in FRONT_LEGACY,
    'legacy watchdog five minutes no autocancel': 'const MAX_SECONDS=300' in WATCHDOG and 'cancel.click()' not in WATCHDOG and 'Backend 실패 종료 상태' in WATCHDOG,
    'no stale three-minute policy': '3분' not in HARD and '3분' not in FRONT_V2 and '3분' not in FRONT_LEGACY and '3분' not in WATCHDOG and '3-minute' not in MAIN,
}

for path in [ROUTE_PATH, HYBRID_PATH, FETCH_PATH, HARD_PATH, BRIDGE_PATH, MAIN_PATH]:
    ast.parse(path.read_text(encoding='utf-8'), filename=str(path))

failed=[name for name,ok in checks.items() if not ok]
for name,ok in checks.items():
    print(('PASS' if ok else 'FAIL'), name)
if failed:
    raise SystemExit('v5.429 contract FAIL: '+', '.join(failed))
print(f'v5.429 5-minute Theme hard-timeout contract PASS {len(checks)}/{len(checks)}')
