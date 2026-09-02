from __future__ import annotations

import json
import tempfile
from pathlib import Path

from app.services.code_intelligence_service import resolve_code_intelligence

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
UTILITY = (ROOT / 'frontend/src/utils/codeIntelligence.ts').read_text(encoding='utf-8')
SERVICE = (ROOT / 'backend/app/services/code_intelligence_service.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
CODEX = (ROOT / 'backend/app/services/codex_app_server_service.py').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend/src/styles.css').read_text(encoding='utf-8')

checks: list[tuple[str, bool]] = []

def check(label: str, condition: bool) -> None:
    checks.append((label, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {label}")

check('frontend version 5.468', "AGENTSTUDIO_FRONTEND_VERSION='5.468'" in APP)
check('backend version 5.468', 'version="5.468"' in MAIN)
check('health route version 5.468', '"version": "5.468"' in ROUTES)
check('Codex client version 5.468', 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.468"' in CODEX)
check('build marker completion', 'CtrlSpaceSymbolCompletion' in ROUTES)
check('Monaco completion provider', 'registerCompletionItemProvider' in UTILITY)
check('completion action request', "resolveAt(model, position, 'completion')" in UTILITY)
check('Ctrl+Space command', 'KeyMod.CtrlCmd | monaco.KeyCode.Space' in UTILITY and 'editor.action.triggerSuggest' in UTILITY)
check('Python completion backend', 'def _python_completions(' in SERVICE and 'action == "completion"' in SERVICE)
check('Notebook completion uses prior cells', '_parse_notebook_code_cells(notebook_content)' in SERVICE and 'target_index > cell_index' in SERVICE)
check('manual reference add function', 'const addManualCodeEditReference=()=>{' in APP)
check('manual reference button', '>+ 참조 문구</button>' in APP and 'onClick={addManualCodeEditReference}' in APP)
check('manual reference source marker', "source:'manual-entry'" in APP)
check('manual reference textarea focus id', 'data-llm-reference-id={reference.id}' in APP)
check('manual reference label', "'직접 입력 참조'" in APP and "'사용자 입력'" in APP)
check('save dot no file status badge class', 'className="editor-save-button-dot"' in APP and 'file-save-status dirty editor-save-button-dot' not in APP)
check('save dot unified style', '.editor-save-toolbar-button .editor-save-button-dot' in CSS and 'background:transparent' in CSS)

with tempfile.TemporaryDirectory() as temp_dir:
    notebook = {
        'cells': [
            {'cell_type': 'code', 'source': [
                'from langchain_core.documents import Document\n',
                "intro_documents = [Document(page_content='RAG')]\n",
            ]},
            {'cell_type': 'code', 'source': ["print('문서 수:', len())\n"]},
        ],
        'metadata': {}, 'nbformat': 4, 'nbformat_minor': 5,
    }
    result = resolve_code_intelligence({
        'root': temp_dir,
        'relative_path': 'demo.ipynb',
        'language': 'python',
        'content': "print('문서 수:', len())\n",
        'line': 1,
        'column': 21,
        'action': 'completion',
        'notebook_content': json.dumps(notebook),
        'cell_index': 1,
    })
    labels = [str(item.get('label') or '') for item in result.get('completions') or []]
    check('intro_documents offered by Ctrl+Space backend', 'intro_documents' in labels)
    check('local variable ranks before builtin len', labels.index('intro_documents') < labels.index('len'))

    prefixed = resolve_code_intelligence({
        'root': temp_dir,
        'relative_path': 'demo.py',
        'language': 'python',
        'content': "intro_documents = []\nprint(intro)\n",
        'line': 2,
        'column': 12,
        'action': 'completion',
    })
    prefix_labels = [str(item.get('label') or '') for item in prefixed.get('completions') or []]
    check('typed prefix filters completion', prefixed.get('prefix') == 'intro' and 'intro_documents' in prefix_labels)

failed = [label for label, ok in checks if not ok]
if failed:
    raise SystemExit(f'v5.468 contract failed: {len(failed)}/{len(checks)} -> {failed}')
print(f'v5.468 completion/manual-reference/save contract: ALL PASS ({len(checks)}/{len(checks)})')
