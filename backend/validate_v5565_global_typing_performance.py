from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
app=(ROOT/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
composer=(ROOT/'frontend/src/features/editor/components/CodeLlmPromptComposer.tsx').read_text(encoding='utf-8')
assert 'React.memo' in composer
assert 'const [prompt,setPrompt]=useState' in composer
assert "const [codeEditPrompt,setCodeEditPrompt]=useState('')" not in app
assert 'useDeferredValue(projectFileSearch)' in app
assert 'const projectTree=useMemo(' in app
assert 'const projectTreeForDisplay=useMemo(' in app
assert "AGENTSTUDIO_FRONTEND_VERSION='5.565'" in app
print('v5.565 global typing performance: PASS')
