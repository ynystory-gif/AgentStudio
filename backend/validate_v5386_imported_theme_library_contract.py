from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
ROUTES=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
ENTITIES=(ROOT/'backend/app/models/entities.py').read_text(encoding='utf-8')
SERVICE=(ROOT/'backend/app/services/ui_theme_service.py').read_text(encoding='utf-8')
PROVISION=(ROOT/'backend/app/services/database_provisioning.py').read_text(encoding='utf-8')
WORKFLOW=(ROOT/'backend/app/services/agent_workflow.py').read_text(encoding='utf-8')

checks={
    'version': any(v in APP for v in ["AGENTSTUDIO_FRONTEND_VERSION='5.386'","AGENTSTUDIO_FRONTEND_VERSION='5.387'","AGENTSTUDIO_FRONTEND_VERSION='5.388'"]),
    'theme table': 'class UITheme(Base):' in ENTITIES and '__tablename__ = "ui_themes"' in ENTITIES and '"ui_themes"' in PROVISION,
    'theme API': all(x in ROUTES for x in ['/ui-themes/import-url','/ui-themes/import-image','/ui-themes/{theme_id}']),
    'URL analyzer': 'analyze_theme_from_url' in SERVICE and 'validate_public_theme_url' in SERVICE and 'is_private' in SERVICE,
    'screenshot analyzer': 'extractThemeTokensFromImage' in APP and "getImageData" in APP,
    'theme selector': '사용자 Theme' in APP and '+ 스타일 가져오기' in APP and 'uiThemeSelectValue' in APP,
    'preview': 'ui-layout-wireframe.custom' in CSS and '--ui-theme-primary' in CSS,
    'generation contract': 'theme_tokens' in ROUTES and 'Theme Provider' in ROUTES and 'theme_tokens' in WORKFLOW,
    'no content clone': '로고·문구·이미지·고유 콘텐츠를 복제하지' in ROUTES,
}
failed=[name for name,ok in checks.items() if not ok]
for name,ok in checks.items(): print(('PASS' if ok else 'FAIL'),name)
if failed: raise SystemExit('FAILED: '+', '.join(failed))
print('v5.386 imported theme library contract PASS')
