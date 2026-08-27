from pathlib import Path
import ast
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
API = (ROOT / 'frontend/src/api.ts').read_text(encoding='utf-8')
MAIN = (BACKEND / 'app/main.py').read_text(encoding='utf-8')
ROUTES = (BACKEND / 'app/api/routes.py').read_text(encoding='utf-8')
DB = (BACKEND / 'app/core/database.py').read_text(encoding='utf-8')
DB_RUNTIME = (BACKEND / 'app/services/database_runtime_service.py').read_text(encoding='utf-8')
THEME = (BACKEND / 'app/services/ui_theme_service.py').read_text(encoding='utf-8')
REGISTRY_PATH = BACKEND / 'app/services/frontend_theme_registry.py'
REGISTRY = REGISTRY_PATH.read_text(encoding='utf-8')
SUPABASE_SQL = (BACKEND / 'sql/supabase_agentstudio_full_schema.sql').read_text(encoding='utf-8')

checks = {
    'version': "AGENTSTUDIO_FRONTEND_VERSION='5.388'" in APP and 'version="5.388"' in MAIN,
    'frontend list button': '지원 Frontend/스타일 목록 보기' in APP and '/ui-themes/frontend-targets' in ROUTES,
    'generic adapter': 'generic_web' in REGISTRY and '미등록 Frontend라도 generic adapter' in REGISTRY,
    'style combination': 'detect_frontend_style_adapters' in REGISTRY and 'style_adapters' in REGISTRY,
    'runtime metadata helper': 'async def ensure_runtime_metadata_tables()' in DB and 'Base.metadata.create_all' in DB,
    'supabase rebind self heal': 'await ensure_runtime_metadata_tables()' in DB_RUNTIME,
    'theme route self heal': 'async def _ensure_ui_theme_storage()' in ROUTES and ROUTES.count('await _ensure_ui_theme_storage()') >= 4,
    'api mismatch message': 'Theme API를 찾을 수 없습니다' in API,
    'url scheme normalization': 'raw = "https://" + raw.lstrip("/")' in THEME,
    'blocked site guidance': '화면 캡처 이미지로 Theme을 가져오세요' in THEME,
    'image safety': '25*1024*1024' in APP and 'Canvas를 사용할 수 없어' in APP,
    'fresh supabase theme table': 'CREATE TABLE IF NOT EXISTS theanova_agentstudio.ui_themes' in SUPABASE_SQL,
}

spec = importlib.util.spec_from_file_location('frontend_theme_registry', REGISTRY_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
targets = module.list_frontend_theme_targets()
checks['frontend target count'] = len(targets) >= 45
checks['react js ts both'] = {x['id'] for x in targets}.issuperset({'react_js','react_ts','next_js','next_ts'})
checks['non-react targets'] = {x['id'] for x in targets}.issuperset({'vue_ts','angular_ts','sveltekit','streamlit','blazor','flutter','aspnet_webforms','electron'})
checks['style targets'] = {x['id'] for x in targets}.issuperset({'tailwind','mui','shadcn','vuetify','prime_ui'})

for path in [
    BACKEND / 'app/main.py',
    BACKEND / 'app/api/routes.py',
    BACKEND / 'app/core/database.py',
    BACKEND / 'app/services/database_runtime_service.py',
    BACKEND / 'app/services/ui_theme_service.py',
    REGISTRY_PATH,
]:
    ast.parse(path.read_text(encoding='utf-8'), filename=str(path))

failed = [name for name, ok in checks.items() if not ok]
print(f"v5.388 contract: {sum(checks.values())}/{len(checks)} PASS")
print(f"frontend targets: {len(targets)}")
for name, ok in checks.items():
    print(('PASS' if ok else 'FAIL'), name)
if failed:
    raise SystemExit('failed: ' + ', '.join(failed))
