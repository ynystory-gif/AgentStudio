from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = (ROOT / 'frontend/src/utils/codeIntelligence.ts').read_text(encoding='utf-8')
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
CODEX = (ROOT / 'backend/app/services/codex_app_server_service.py').read_text(encoding='utf-8')
SERVICE = (ROOT / 'backend/app/services/code_intelligence_service.py').read_text(encoding='utf-8')

checks = []
def check(name, condition):
    checks.append((name, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {name}")

check('frontend version 5.472', "AGENTSTUDIO_FRONTEND_VERSION='5.472'" in APP)
check('backend version 5.472', 'version="5.472"' in MAIN)
check('health version 5.472', '"version": "5.472"' in ROUTES)
check('codex client version 5.472', 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.472"' in CODEX)
check('Ctrl+Space intercepted on editor keydown', 'editor.onKeyDown?.' in CODE)
check('Ctrl+Space detects Space key', "monaco.KeyCode.Space" in CODE and "browserEvent?.code === 'Space'" in CODE)
check('Ctrl+Space prevents default browser/editor behavior', 'event?.preventDefault?.()' in CODE and 'browserEvent?.preventDefault?.()' in CODE)
check('Ctrl+Space triggers suggestion widget only', "'editor.action.triggerSuggest'" in CODE)
check('old addCommand Ctrl+Space binding removed', "editor.addCommand?.(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Space" not in CODE)
check('completion-navigation interaction guard exists', 'completionGuardUntil' in CODE and 'Date.now() < completionGuardUntil' in CODE)
check('suggestion widget click excluded from definition navigation', ".suggest-widget, .monaco-list, .monaco-editor-hover" in CODE)
check('definition click limited to editor content text', 'MouseTargetType?.CONTENT_TEXT' in CODE)
check('definition navigation requires Ctrl mouse click', 'if (!ctrlKey || !leftButton || !position) return' in CODE)
check('completion provider uses completion action only', "resolveAt(model, position, 'completion')" in CODE)
check('call arguments remain highest-priority completion context', 'completion_context": "call_arguments"' in SERVICE)
check('code-defined symbol completion remains available', 'completion_context": "symbols"' in SERVICE and 'priority = {"variable": 0' in SERVICE)
check('builtins remain lower priority than code-defined symbols', '"builtin": 8' in SERVICE)
check('keydown disposable cleaned up', 'keyDisposable?.dispose?.()' in CODE)
check('build marker updated', 'CtrlSpaceCompletionNavigationSeparation' in ROUTES)


# Functional completion contract: Ctrl+Space data source must return menu items, never a definition jump.
import importlib.util
import sys
import tempfile

spec = importlib.util.spec_from_file_location('agentstudio_code_intelligence_v5472', ROOT / 'backend/app/services/code_intelligence_service.py')
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
assert spec.loader is not None
spec.loader.exec_module(module)

with tempfile.TemporaryDirectory() as td:
    project_root = Path(td)
    package = project_root / '.venv/Lib/site-packages/langchain_openai'
    (package / 'chat_models').mkdir(parents=True)
    (package / '__init__.py').write_text('from .chat_models import ChatOpenAI\n', encoding='utf-8')
    (package / 'chat_models/__init__.py').write_text('from .base import ChatOpenAI\n', encoding='utf-8')
    (package / 'chat_models/base.py').write_text(
        'class BaseChatOpenAI:\n    model_name: str = Field(default="gpt-4o-mini", alias="model")\n    temperature: float | None = None\n\nclass ChatOpenAI(BaseChatOpenAI):\n    pass\n',
        encoding='utf-8',
    )
    source = 'from langchain_openai import ChatOpenAI\nMODEL_NAME = "gpt-4o-mini"\nTEMPERATURE = 0.1\n\nllm = ChatOpenAI(\n'
    result = module.resolve_code_intelligence({
        'root': str(project_root), 'relative_path': 'cell.py', 'language': 'python',
        'content': source, 'line': 5, 'column': 18, 'action': 'completion',
    })
    labels = [item.get('label') for item in result.get('completions', [])]
    check('functional Ctrl+Space call menu context', result.get('completion_context') == 'call_arguments')
    check('functional parameter candidate model=MODEL_NAME', 'model=MODEL_NAME' in labels)
    check('functional parameter candidate temperature=TEMPERATURE', 'temperature=TEMPERATURE' in labels)
    check('completion response does not request navigation', not result.get('definition'))

    outside = 'intro_documents = []\nother_value = 1\nprint(\n'
    outside_result = module.resolve_code_intelligence({
        'root': str(project_root), 'relative_path': 'plain.py', 'language': 'python',
        'content': outside, 'line': 3, 'column': 7, 'action': 'completion',
    })
    outside_labels = [item.get('label') for item in outside_result.get('completions', [])]
    check('code-defined object appears in Ctrl+Space menu', 'intro_documents' in outside_labels)
    check('code-defined object ranks before builtin', outside_labels.index('intro_documents') < outside_labels.index('print'))

failed = [name for name, ok in checks if not ok]
if failed:
    raise SystemExit(f'v5.472 contract failed: {len(failed)}/{len(checks)} -> {failed}')
print(f'v5.472 CtrlSpace completion/navigation separation contract: ALL PASS ({len(checks)}/{len(checks)})')
