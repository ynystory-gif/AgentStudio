from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
sys.path.insert(0, str(BACKEND))

from app.services.frontend_theme_registry import (  # noqa: E402
    list_frontend_theme_targets,
    detect_frontend_theme_target,
    frontend_test_environment_files,
)

APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
WORKFLOW = (ROOT / 'backend/app/services/agent_workflow.py').read_text(encoding='utf-8')
DESIGN = (ROOT / 'backend/app/services/agent_factory_workflow_design.py').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend/src/styles.css').read_text(encoding='utf-8')


def require(condition, message):
    if not condition:
        raise AssertionError(message)


targets = list_frontend_theme_targets()
ids = {item['id'] for item in targets}
require(len(targets) >= 30, 'frontend Theme registry must expose broad target list')
for expected in ('react_ts','next_ts','vue_ts','nuxt_ts','angular_ts','sveltekit','astro','streamlit','gradio','nicegui','blazor','react_native','flutter','generic_web'):
    require(expected in ids, f'missing target: {expected}')

require(detect_frontend_theme_target('React + TypeScript')['id'] == 'react_ts', 'React TS detection')
require(detect_frontend_theme_target('Vue + TypeScript')['id'] == 'vue_ts', 'Vue TS detection')
require(detect_frontend_theme_target('Streamlit dashboard')['id'] == 'streamlit', 'Streamlit detection')
require(detect_frontend_theme_target('Flutter mobile app')['id'] == 'flutter', 'Flutter detection')
require(detect_frontend_theme_target('unlisted framework')['id'] == 'generic_web', 'generic fallback')
require(frontend_test_environment_files('streamlit')['page'].endswith('.py'), 'Streamlit admin test page must be Python')
require(frontend_test_environment_files('vue_ts')['page'].endswith('.vue'), 'Vue admin page must be .vue')

checks = {
    'version': "AGENTSTUDIO_FRONTEND_VERSION='5.388'" in APP or "AGENTSTUDIO_FRONTEND_VERSION='5.387'" in APP,
    'frontend target endpoint': '@router.get("/ui-themes/frontend-targets")' in ROUTES,
    'frontend list button': ('적용 Frontend 목록' in APP or '지원 Frontend/스타일 목록 보기' in APP),
    'frontend target summary': 'Frontend Theme 적용' in APP,
    'generic adapter note': 'Generic Theme Adapter' in APP,
    'target list css': '.ui-layout-theme-target-list' in CSS,
    'framework native generation': '확정된 Frontend Framework의 native Theme 방식' in WORKFLOW,
    'not react only': 'React 전용 Theme Provider나 CSS 변수 방식으로 고정하지 마십시오.' in WORKFLOW,
    'test environment generic frontend': 'frontend_present' in DESIGN and 'frontend_test_environment_files' in DESIGN,
    'vue source recognized': '".vue"' in WORKFLOW,
    'svelte source recognized': '".svelte"' in WORKFLOW,
    'astro source recognized': '".astro"' in WORKFLOW,
    'flutter source recognized': '".dart"' in WORKFLOW,
    'razor source recognized': '".razor"' in WORKFLOW and '".cshtml"' in WORKFLOW,
}
for name, ok in checks.items():
    require(ok, name)

print('v5.387 frontend agnostic theme adapters contract PASS')
print('frontend targets:', len(targets))
