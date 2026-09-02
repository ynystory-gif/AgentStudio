from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CENTER = (ROOT / 'frontend/src/components/learning/LlmLearningCenter.tsx').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend/src/components/learning/learning-case-list-cleanup.css').read_text(encoding='utf-8')
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')

checks = {
    'frontend version 5.441': "AGENTSTUDIO_FRONTEND_VERSION='5.441'" in APP,
    'backend version 5.441': 'version="5.441"' in MAIN,
    'health version 5.441': '"version": "5.441"' in ROUTES,
    'dataset table has scroll wrapper': 'className="llm-dataset-table-scroll"' in CENTER,
    'trace column is native and marked': 'data-learning-trace="1"' in CENTER,
    'learning topic cell is explicit': 'className="learning-topic-cell"' in CENTER,
    'learning topic inner scroll exists': 'className="learning-topic-scroll"' in CENTER,
    'table wrapper horizontal scroll': 'overflow-x: auto;' in CSS and '.llm-dataset-table-scroll' in CSS,
    'table wrapper vertical scroll': 'overflow-y: auto;' in CSS and '.llm-dataset-table-scroll' in CSS,
    'learning topic width reserved': 'width: 360px !important;' in CSS,
    'learning topic has independent scroll': '.learning-topic-scroll {' in CSS and 'max-height: 132px;' in CSS,
    'learning topic auto wraps': 'white-space: normal !important;' in CSS and 'overflow-wrap: anywhere !important;' in CSS,
    'sticky table header in scroll container': '.llm-dataset-table-scroll .llm-dataset-table thead th' in CSS and 'top: 0 !important;' in CSS,
}
failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(('PASS' if ok else 'FAIL') + ': ' + name)
if failed:
    raise SystemExit(f'{len(failed)} checks failed: {failed}')
print(f'PASS {len(checks)}/{len(checks)}')
