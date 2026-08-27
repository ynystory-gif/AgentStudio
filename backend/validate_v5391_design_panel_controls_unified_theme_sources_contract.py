from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend/src/styles.css').read_text(encoding='utf-8')
MANAGER = (ROOT / 'frontend/src/components/ai/AgentDesignProjectManager.jsx').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
THEME = (ROOT / 'backend/app/services/ui_theme_service.py').read_text(encoding='utf-8')
REGISTRY = (ROOT / 'backend/app/services/frontend_theme_registry.py').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')

checks = {
    'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.391'" in APP,
    'backend version': 'version="5.391"' in MAIN,
    'top unified toolbar removed': '<section className="unified-design-chat">\n            <AgentDesignProjectToolbar' not in APP,
    'project toolbar under build progress': 'className="agent-build-secondary-tools"' in APP and 'showNew={false}' in APP,
    'project save load kept': '💾 프로젝트 저장' in MANAGER and '📂 프로젝트 로드' in MANAGER,
    'new project conditionally hidden': '{showNew&&<button' in MANAGER,
    'feature manager under build': 'className="agent-build-feature-tools"' in APP and 'panelMode' in APP,
    'feature delete available': "changeStatus(item,'REMOVE')" in MANAGER,
    'project config no nested scroll': '.unified-project-config{' in CSS and 'max-height:none!important' in CSS and 'overflow:visible!important' in CSS,
    'design visible scrollbar hidden': 'scrollbar-width:none!important' in CSS,
    'unified url and image inputs': '웹사이트 URL' in APP and 'multiple onChange={e=>chooseThemeImages(e.target.files)}' in APP,
    'max three image guard': APP.count('최대 3개') >= 2,
    'combined theme endpoint': '@router.post("/ui-themes/import")' in ROUTES and 'UIThemeImportCombinedRequest' in ROUTES,
    'combined source type': 'source_type = "COMBINED" if url_applied and images' in ROUTES,
    'menu css states': 'extract_menu_rules' in THEME and '"hover"' in THEME and '"active"' in THEME,
    'theme analysis merge': 'def merge_theme_analyses' in THEME,
    'all frontend native adapter instruction': 'component_rules.menu에 normal/hover/active' in REGISTRY and '미등록 Frontend라도 generic adapter' in REGISTRY,
    'unified theme panel styles': '.ui-layout-theme-import-panel.unified-source' in CSS and '.ui-layout-theme-file-list' in CSS,
}

failed = [name for name, ok in checks.items() if not ok]
print(f"v5.391 contract: {sum(checks.values())}/{len(checks)} PASS")
if failed:
    print('FAILED:', ', '.join(failed))
    raise SystemExit(1)
