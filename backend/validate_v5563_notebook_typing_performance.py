from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
nb=(ROOT/'frontend/src/features/notebook/components/NotebookEditor.tsx').read_text(encoding='utf-8')
types=(ROOT/'frontend/src/types/notebook.ts').read_text(encoding='utf-8')
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
assert 'sourceCommitTimerRef' in nb
assert 'scheduleSourceCommit()' in nb
assert '}, 420)' in nb
assert "patchCell(index, { source: textToNotebookSource(text) })" not in nb
assert 'flushPendingChanges: () => flushPendingSourceChanges()' in nb
assert 'getLiveContent: () => string' in types
assert 'flushPendingChanges: () => string' in types
assert 'notebookEditorControllerRef.current?.flushPendingChanges?.()' in app
assert "AGENTSTUDIO_FRONTEND_VERSION='5.563'" in app
print('v5.563 Notebook typing performance: PASS')
