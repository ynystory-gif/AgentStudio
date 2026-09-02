from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EDITOR = (ROOT / 'frontend/src/utils/editor.ts').read_text(encoding='utf-8')
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
NOTEBOOK = (ROOT / 'frontend/src/components/notebook/NotebookEditor.tsx').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
CODEX = (ROOT / 'backend/app/services/codex_app_server_service.py').read_text(encoding='utf-8')

checks = []

def check(label, condition):
    checks.append((label, bool(condition)))
    print(f"[{'PASS' if condition else 'FAIL'}] {label}")

check('frontend version 5.469', "AGENTSTUDIO_FRONTEND_VERSION='5.469'" in APP)
check('backend version 5.469', 'version="5.469"' in MAIN)
check('health route version 5.469', '"version": "5.469"' in ROUTES)
check('Codex client version 5.469', 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.469"' in CODEX)
check('build marker selected text exact replace', 'SelectedTextExactReplacePairTyping' in ROUTES)
check('selection auto surround disabled', "autoSurround: 'never'" in EDITOR)
check('selected opening characters guarded', "['(', '{', '[', '\"'].includes(key)" in EDITOR)
check('selected text replaced by exact key', "text: key" in EDITOR and "theanova.selection-exact-character-replace" in EDITOR)
check('selection event prevents Monaco pair creation', 'event.preventDefault?.()' in EDITOR and 'event.stopPropagation?.()' in EDITOR)
check('caret moves after exact replacement character', 'column: startColumn + key.length' in EDITOR)
check('IME composition remains protected', 'if (browserEvent?.isComposing) return' in EDITOR)
check('Ctrl/Alt/Meta modifiers are not intercepted', 'browserEvent?.ctrlKey || browserEvent?.altKey || browserEvent?.metaKey' in EDITOR)
check('empty selection pair typing still enabled', "autoClosingBrackets: 'always'" in EDITOR and "autoClosingQuotes: 'always'" in EDITOR)
check('escaped quote guard retained', 'theanova.escaped-double-quote-pair-guard' in EDITOR and 'slashCount % 2 !== 1' in EDITOR)
check('main editor registers pair guard', 'registerEscapedDoubleQuotePairGuard(editor)' in APP)
check('notebook code cell registers pair guard', 'registerEscapedDoubleQuotePairGuard(editor as unknown as any)' in NOTEBOOK)

failed = [label for label, ok in checks if not ok]
if failed:
    raise SystemExit(f'v5.469 contract failed: {len(failed)}/{len(checks)} -> {failed}')
print(f'v5.469 selected-text exact replacement pair typing contract: ALL PASS ({len(checks)}/{len(checks)})')
