from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
MAIN=(ROOT/'backend/app/main.py').read_text(encoding='utf-8')
ROUTES=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')

checks={
    'version': "AGENTSTUDIO_FRONTEND_VERSION='5.409'" in APP and 'version="5.409"' in MAIN and '"version": "5.409"' in ROUTES,
    'build badge': 'ResponsiveNotebookToolbarWrap' in ROUTES,
    'notebook inline container': 'container-type:inline-size' in CSS and 'container-name:notebook-editor' in CSS,
    'toolbar wrap': '.notebook-toolbar{' in CSS and 'flex-wrap:wrap' in CSS,
    'actions wrap': '.notebook-toolbar-actions{' in CSS and 'justify-content:flex-end' in CSS,
    'button no squash': 'white-space:nowrap' in CSS and 'flex:0 0 auto' in CSS,
    'bookmark min content': '.notebook-bookmark-navigation{' in CSS and 'min-width:max-content' in CSS,
    'pane responsive query': '@container notebook-editor (max-width:760px)' in CSS,
    'small pane bookmark query': '@container notebook-editor (max-width:520px)' in CSS,
    'two row responsive layout': 'flex:1 1 100%' in CSS and 'width:100%' in CSS,
}
failed=[name for name,ok in checks.items() if not ok]
if failed:
    raise SystemExit('v5.409 contract FAIL: '+', '.join(failed))
print(f'v5.409 Responsive Notebook Toolbar Wrap contract PASS {len(checks)}/{len(checks)}')
