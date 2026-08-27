from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTEBOOK = (ROOT / 'frontend' / 'src' / 'components' / 'notebook' / 'NotebookEditor.tsx').read_text(encoding='utf-8')
APP = (ROOT / 'frontend' / 'src' / 'App.jsx').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend' / 'app' / 'api' / 'routes.py').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend' / 'app' / 'main.py').read_text(encoding='utf-8')

checks = {
    'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.379'" in APP,
    'backend main version': 'version="5.379"' in MAIN,
    'backend health version': '"version": "5.379"' in ROUTES,
    'notebook code editor uncontrolled default': 'language="python"\n                  defaultValue={source}' in NOTEBOOK,
    'notebook source mirror ref': 'latestCellSourcesRef' in NOTEBOOK,
    'notebook bracket auto close disabled': "autoClosingBrackets: 'never'" in NOTEBOOK,
    'notebook quote auto close disabled': "autoClosingQuotes: 'never'" in NOTEBOOK,
    'notebook surround disabled': "autoSurround: 'never'" in NOTEBOOK,
    'notebook global refocus blocked': 'if(!isNotebookFile(selected))' in APP,
    'source editor bracket auto close disabled': "autoClosingBrackets:'never'" in APP,
    'source editor quote auto close disabled': "autoClosingQuotes:'never'" in APP,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('FAIL v5.379 contract: ' + ', '.join(failed))

print('PASS v5.379 Notebook Caret Persistence + Manual Pair Typing contract')
