from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
MAIN=(ROOT/'backend/app/main.py').read_text(encoding='utf-8')
ROUTES=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
SERVICE=(ROOT/'backend/app/services/ui_theme_service.py').read_text(encoding='utf-8')
checks={
    'version': "AGENTSTUDIO_FRONTEND_VERSION='5.402'" in APP and 'version="5.402"' in MAIN and '"version": "5.402"' in ROUTES,
    'interactive preview menu': 'setSubmenuOpen' in APP and 'ui-theme-preview-submenu' in APP and 'ui-theme-preview-user-menu' in APP,
    'native hover preview css': '.ui-theme-preview-nav-dropdown>button:hover' in CSS and '.ui-theme-preview-form input:focus' in CSS,
    'button card interactions': '.ui-theme-preview-primary:hover' in CSS and '.ui-theme-preview-card:hover' in CSS,
    'evidence panel': '외부 스타일 재현 근거' in APP and 'uiThemeEvidenceRows' in APP and 'URL CSS 확인' in APP,
    'transparent inferred status': '추정/기본값' in APP and '근거가 없는 상태' in APP,
    'screenshot roles state': "useState(['default','menu_hover','user_menu_open'])" in APP,
    'screenshot role selector': '하위 메뉴 Open' in APP and '사용자 메뉴 Open' in APP and '입력 Focus' in APP,
    'request sends roles': 'reference_role:themeImportRoles' in APP,
    'backend role schema': 'reference_role: str = "default"' in ROUTES,
    'backend interaction extraction': 'extract_interaction_rules' in SERVICE and 'URL_CSS_SELECTOR' in SERVICE,
    'backend dropdown user selectors': '"submenu"' in SERVICE and '"user_menu"' in SERVICE and 'profile-dropdown' in SERVICE,
    'backend css states': '"boxShadow"' in SERVICE and '"transition"' in SERVICE and '"transform"' in SERVICE,
    'evidence persistence': 'components["_evidence"] = evidence' in SERVICE and 'components["_source_summary"]' in SERVICE,
}
failed=[name for name,ok in checks.items() if not ok]
if failed:
    raise SystemExit('FAIL: '+', '.join(failed))
print(f'v5.402 interactive theme behavior verification contract PASS {len(checks)}/{len(checks)}')
