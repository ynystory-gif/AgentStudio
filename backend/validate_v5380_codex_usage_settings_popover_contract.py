from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend' / 'src' / 'App.jsx').read_text(encoding='utf-8')
PANEL = (ROOT / 'frontend' / 'src' / 'components' / 'codex' / 'CodexPanel.tsx').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend' / 'src' / 'styles.css').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend' / 'app' / 'main.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend' / 'app' / 'api' / 'routes.py').read_text(encoding='utf-8')
SERVICE = (ROOT / 'backend' / 'app' / 'services' / 'codex_app_server_service.py').read_text(encoding='utf-8')

checks = {
    'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.380'" in APP,
    'backend main version': 'version="5.380"' in MAIN,
    'backend health version': '"version": "5.380"' in ROUTES,
    'codex client version': 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.380"' in SERVICE,
    'usage popover': 'codex-usage-popover' in PANEL and '.codex-usage-popover' in CSS,
    'settings title': 'Codex 설정 및 남은 사용량' in PANEL,
    'remaining usage title': '남은 사용량' in PANEL,
    '5 hour label': "minutes === 300) return '5시간'" in PANEL,
    '1 week label': "minutes === 10080) return '1주'" in PANEL,
    'remaining percent': '100 - Number(window.usedPercent)' in PANEL,
    'reset display': "toLocaleTimeString('ko-KR'" in PANEL and "toLocaleDateString('ko-KR'" in PANEL,
    'force usage refresh': "/codex/rate-limits?force=${force ? 'true' : 'false'}" in PANEL,
    'reset credit display': '재설정 {status.rate_limits.rateLimitResetCredits.availableCount}회 가능' in PANEL,
    'technical details preserved': 'Codex 상세 정보' in PANEL and '프로세스' in PANEL and '현재 파일' in PANEL,
    'system settings link': 'Codex 설정' in PANEL and "window.location.href = '/system'" in PANEL,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('FAIL v5.380 contract: ' + ', '.join(failed))
print('PASS v5.380 Codex Usage Settings Popover contract')
