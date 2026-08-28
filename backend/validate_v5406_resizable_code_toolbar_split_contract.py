from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
MAIN=(ROOT/'backend/app/main.py').read_text(encoding='utf-8')
ROUTES=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')

checks={
    'version': "AGENTSTUDIO_FRONTEND_VERSION='5.406'" in APP and 'version="5.406"' in MAIN and '"version": "5.406"' in ROUTES,
    'persisted width': "agentstudio.codeToolbar.actionWidth" in APP,
    'resize state': 'codeToolbarResizing' in APP and 'codeToolbarActionWidth' in APP,
    'split handler': 'beginCodeToolbarSplitResize' in APP,
    'reset handler': 'resetCodeToolbarSplit' in APP,
    'separator': 'code-toolbar-horizontal-splitter' in APP and 'role="separator"' in APP,
    'width binding': 'flexBasis:`${Math.round(codeToolbarActionWidth)}px`' in APP,
    'split css': '.code-toolbar-horizontal-splitter' in CSS and 'cursor:col-resize' in CSS,
    'tab flex remainder': '.code-file-tabs-shell .code-file-tabs{flex:1 1 auto !important}' in CSS,
    'action min width': 'min-width:220px' in CSS,
}
failed=[name for name,ok in checks.items() if not ok]
if failed:
    raise SystemExit('v5.406 contract FAIL: '+', '.join(failed))
print(f'v5.406 resizable code toolbar split contract PASS {len(checks)}/{len(checks)}')
