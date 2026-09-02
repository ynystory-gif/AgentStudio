from pathlib import Path
import importlib.util
import json
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
CODEX = (ROOT / 'backend/app/services/codex_app_server_service.py').read_text(encoding='utf-8')
FRONT = (ROOT / 'frontend/src/utils/codeIntelligence.ts').read_text(encoding='utf-8')
SERVICE_PATH = ROOT / 'backend/app/services/code_intelligence_service.py'
SERVICE = SERVICE_PATH.read_text(encoding='utf-8')
EDITOR = (ROOT / 'frontend/src/utils/editor.ts').read_text(encoding='utf-8')

checks = []

def check(label, condition):
    checks.append((label, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {label}")

check('frontend version 5.470', "AGENTSTUDIO_FRONTEND_VERSION='5.470'" in APP)
check('backend version 5.470', 'version="5.470"' in MAIN)
check('health route version 5.470', '"version": "5.470"' in ROUTES)
check('Codex client version 5.470', 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.470"' in CODEX)
check('build marker context aware call argument completion', 'ContextAwareCallArgumentCompletion' in ROUTES)
check('frontend knows keyword completion kind', 'keyword: monaco.languages.CompletionItemKind.Property' in FRONT)
check('Ctrl+Space command retained', "monaco.KeyMod.CtrlCmd | monaco.KeyCode.Space" in FRONT)
check('call context parser exists', 'def _call_context_before_position' in SERVICE)
check('keyword argument completion builder exists', 'def _keyword_argument_completions' in SERVICE)
check('Pydantic Field alias extraction exists', 'def _field_alias' in SERVICE and '{"alias", "validation_alias"}' in SERVICE)
check('class hierarchy parameter collector exists', 'def _collect_class_parameters_from_file' in SERVICE)
check('site-package module root precedence fix exists', 'Prefer virtualenv/site-package roots before the project root' in SERVICE)
check('incomplete import fallback exists', 'an editor buffer is often intentionally incomplete' in SERVICE)
check('used keyword argument exclusion exists', 'def _used_keyword_arguments' in SERVICE)
check('visible variable matching exists', 'def _best_value_symbol' in SERVICE)
check('selected-text exact replacement retained', "theanova.selection-exact-character-replace" in EDITOR)

# Functional static-analysis contract with a synthetic langchain_openai package.
spec = importlib.util.spec_from_file_location('agentstudio_code_intelligence_v5470', SERVICE_PATH)
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
        '''\ndef Field(*args, **kwargs):\n    pass\n\nclass BaseChatOpenAI:\n    model_name: str = Field(default="gpt-4o-mini", alias="model")\n    temperature: float | None = None\n    api_key: str | None = None\n\nclass ChatOpenAI(BaseChatOpenAI):\n    pass\n''',
        encoding='utf-8',
    )

    source = '''from langchain_openai import ChatOpenAI\nMODEL_NAME = "gpt-4o-mini"\nTEMPERATURE = 0.1\n\nllm = ChatOpenAI(\n'''
    result = module.resolve_code_intelligence({
        'root': str(project_root),
        'relative_path': 'notebook_cell.py',
        'language': 'python',
        'content': source,
        'line': 5,
        'column': 18,
        'action': 'completion',
    })
    labels = [item.get('label') for item in result.get('completions', [])]
    check('call context returns callable-argument mode', result.get('completion_context') == 'call_arguments')
    check('ChatOpenAI model maps to MODEL_NAME', 'model=MODEL_NAME' in labels)
    check('ChatOpenAI temperature maps to TEMPERATURE', 'temperature=TEMPERATURE' in labels)
    check('global symbol dump suppressed in call argument mode', 'MODEL_NAME' not in labels and 'print' not in labels)

    source_after_model = '''from langchain_openai import ChatOpenAI\nMODEL_NAME = "gpt-4o-mini"\nTEMPERATURE = 0.1\n\nllm = ChatOpenAI(\n    model=MODEL_NAME,\n    \n'''
    result_after_model = module.resolve_code_intelligence({
        'root': str(project_root),
        'relative_path': 'notebook_cell.py',
        'language': 'python',
        'content': source_after_model,
        'line': 7,
        'column': 5,
        'action': 'completion',
    })
    labels_after_model = [item.get('label') for item in result_after_model.get('completions', [])]
    check('already-used model keyword is excluded', 'model=MODEL_NAME' not in labels_after_model)
    check('next temperature keyword remains available', 'temperature=TEMPERATURE' in labels_after_model)

    outside = '''intro_documents = []\nprint(\n'''
    outside_result = module.resolve_code_intelligence({
        'root': str(project_root),
        'relative_path': 'plain.py',
        'language': 'python',
        'content': outside,
        'line': 2,
        'column': 7,
        'action': 'completion',
    })
    # print is a builtin with no static signature in this service, so normal symbol
    # fallback should remain usable rather than returning an empty menu.
    outside_labels = [item.get('label') for item in outside_result.get('completions', [])]
    check('symbol completion fallback still includes intro_documents', 'intro_documents' in outside_labels)

failed = [label for label, ok in checks if not ok]
if failed:
    raise SystemExit(f'v5.470 contract failed: {len(failed)}/{len(checks)} -> {failed}')
print(f'v5.470 context-aware call argument completion contract: ALL PASS ({len(checks)}/{len(checks)})')
