from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend' / 'src' / 'App.jsx').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend' / 'src' / 'styles.css').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend' / 'app' / 'main.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend' / 'app' / 'api' / 'routes.py').read_text(encoding='utf-8')
WORKFLOW = (ROOT / 'backend' / 'app' / 'services' / 'agent_workflow.py').read_text(encoding='utf-8')
PPT = (ROOT / 'backend' / 'app' / 'services' / 'presentation_export_service.py').read_text(encoding='utf-8')
CODEX = (ROOT / 'backend' / 'app' / 'services' / 'codex_app_server_service.py').read_text(encoding='utf-8')

checks = {
    'frontend version 5.436': "AGENTSTUDIO_FRONTEND_VERSION='5.436'" in APP,
    'backend version 5.436': 'version="5.436"' in MAIN,
    'health version 5.436': '"version": "5.436"' in ROUTES,
    'codex client version 5.436': 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.436"' in CODEX,
    'sidebar icon config normalized': 'sidebar_menu_icons:Boolean(' in APP,
    'header icon config normalized': 'header_icons:Boolean(' in APP,
    'sidebar icon toggle visible': '좌측 메뉴 아이콘' in APP,
    'header icon toggle visible': '상단 Header 아이콘' in APP,
    'sidebar toggle disabled without sidebar': 'disabled={!draft.sidebar}' in APP and 'sidebar_menu_icons:e.target.checked' in APP,
    'header toggle disabled without header': 'disabled={!draft.header}' in APP and 'header_icons:e.target.checked' in APP,
    'wireframe sidebar icon preview': "ui-layout-wf-sidebar ${sidebarMenuIcons?'with-icons':''}" in APP,
    'wireframe header icon preview': "ui-layout-wf-nav ${headerIcons?'with-icons':''}" in APP,
    'theme sidebar icon preview': 'renderMenuLabel(item,index,sidebarMenuIcons)' in APP,
    'theme header nav icon preview': 'renderMenuLabel(item,index,headerIcons)' in APP,
    'theme header action icons preview': 'ui-theme-preview-header-icons' in APP,
    'sidebar icon css': '.ui-layout-wf-sidebar.with-icons' in CSS,
    'header icon css': '.ui-theme-preview-header-icons>button' in CSS,
    'incremental generation sidebar instruction': 'ui_layout.sidebar_menu_icons=true' in WORKFLOW,
    'generation header instruction': 'ui_layout.header_icons=true' in WORKFLOW,
    'ppt sidebar icon summary': 'sidebar_menu_icons = bool(layout.get("sidebar_menu_icons", False))' in PPT,
    'ppt header icon summary': 'header_icons = bool(layout.get("header_icons", False))' in PPT,
    'build capability': 'UILayoutSidebarHeaderIconOptions' in ROUTES,
}
failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(('PASS' if ok else 'FAIL') + ' - ' + name)
if failed:
    raise SystemExit(f"v5.436 contract failed: {', '.join(failed)}")
print(f"v5.436 contract PASS {len(checks)}/{len(checks)}")
