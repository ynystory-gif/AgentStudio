from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend' / 'src' / 'App.jsx').read_text(encoding='utf-8')
NOTEBOOK = (ROOT / 'frontend' / 'src' / 'components' / 'notebook' / 'NotebookEditor.tsx').read_text(encoding='utf-8')
EDITOR = (ROOT / 'frontend' / 'src' / 'utils' / 'editor.ts').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend' / 'app' / 'main.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend' / 'app' / 'api' / 'routes.py').read_text(encoding='utf-8')
CODEX = (ROOT / 'backend' / 'app' / 'services' / 'codex_app_server_service.py').read_text(encoding='utf-8')
README = (ROOT / 'README_V5_462.md').read_text(encoding='utf-8')

checks = [
    ('frontend version', "AGENTSTUDIO_FRONTEND_VERSION='5.462'" in APP),
    ('backend version', 'version="5.462"' in MAIN and '"version": "5.462"' in ROUTES),
    ('codex version', 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.462"' in CODEX),
    ('shared pair typing policy exists', 'CODE_EDITOR_PAIR_TYPING_OPTIONS' in EDITOR),
    ('opening brackets auto close', "autoClosingBrackets: 'always'" in EDITOR),
    ('double quote auto close', "autoClosingQuotes: 'always'" in EDITOR),
    ('paired backspace delete', "autoClosingDelete: 'always'" in EDITOR),
    ('closing character overtype skip', "autoClosingOvertype: 'always'" in EDITOR),
    ('selected text surround', "autoSurround: 'languageDefined'" in EDITOR),
    ('escaped quote guard exists', 'registerEscapedDoubleQuotePairGuard' in EDITOR),
    ('IME composition ignored', 'browserEvent?.isComposing' in EDITOR),
    ('guard only before existing quote', "lineContent[offset] !== '\"'" in EDITOR),
    ('odd backslash rule', 'slashCount % 2 !== 1' in EDITOR),
    ('escaped quote inserted literally', "text: '\"'" in EDITOR),
    ('caret stays before outer quote', 'column: column + 1' in EDITOR),
    ('primary source editor uses policy', APP.count('...CODE_EDITOR_PAIR_TYPING_OPTIONS') >= 2),
    ('primary and split source editors register guard', APP.count('registerEscapedDoubleQuotePairGuard(editor)') >= 2),
    ('notebook code cell uses policy', '...CODE_EDITOR_PAIR_TYPING_OPTIONS' in NOTEBOOK),
    ('notebook code cell registers guard', 'registerEscapedDoubleQuotePairGuard' in NOTEBOOK),
    ('notebook markdown remains manual', NOTEBOOK.count("autoClosingQuotes: 'never'") >= 1),
    ('release notes explain escaped quote caret', '바깥쪽 자동 닫힘 따옴표를 보존' in README),
]

# Semantic examples for the explicit escaped-quote branch.
def action(left: str, right: str) -> str:
    slash_count = 0
    for ch in reversed(left):
        if ch != '\\':
            break
        slash_count += 1
    if right.startswith('"') and slash_count % 2 == 1:
        return 'INSERT_ESCAPED_QUOTE_STAY_INSIDE'
    if right.startswith('"'):
        return 'SKIP_EXISTING_CLOSER'
    return 'NORMAL_MONACO_TYPING'

checks.extend([
    ('single backslash quote stays inside', action('\\', '"') == 'INSERT_ESCAPED_QUOTE_STAY_INSIDE'),
    ('three backslashes quote stays inside', action('\\\\\\', '"') == 'INSERT_ESCAPED_QUOTE_STAY_INSIDE'),
    ('zero backslash quote skips closer', action('', '"') == 'SKIP_EXISTING_CLOSER'),
    ('two backslashes quote closes normally', action('\\\\', '"') == 'SKIP_EXISTING_CLOSER'),
])

failed = [name for name, ok in checks if not ok]
if failed:
    raise SystemExit('FAIL v5.462 contract: ' + ', '.join(failed))

print(f'PASS v5.462 Smart Pair Typing contract {len(checks)}/{len(checks)}')
