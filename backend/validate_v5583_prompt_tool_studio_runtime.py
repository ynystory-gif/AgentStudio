from pathlib import Path
root=Path(__file__).resolve().parents[1]
app=(root/'frontend/src/app/App.tsx').read_text(encoding='utf-8')
comp=(root/'frontend/src/features/prompt-tool-studio/components/PromptToolStudio.tsx').read_text(encoding='utf-8')
svc=(root/'frontend/src/features/prompt-tool-studio/service.ts').read_text(encoding='utf-8')
routes=(root/'backend/app/api/routes.py').read_text(encoding='utf-8')
backend=(root/'backend/app/services/prompt_tool_studio_service.py').read_text(encoding='utf-8')
main=(root/'backend/app/main.py').read_text(encoding='utf-8')
assert "AGENTSTUDIO_FRONTEND_VERSION='5.583'" in app
assert app.count('prompt_tool_studio:promptToolStudioState') >= 2
assert 'setPromptToolStudioState(snapshot?.prompt_tool_studio' in app
assert 'onProjectStateChange={setPromptToolStudioState}' in app
assert 'onApplyState=' in app
assert 'Agent 설계에 적용' in comp
assert "['INPUT','EXTRACTION','VALIDATION','ROUTING','TOOL','PROMPT','FULL']" in comp
assert 'runStudioRuntimeTest' in comp and '/prompt-tool-studio/test' in svc
assert '@router.post("/prompt-tool-studio/test")' in routes
assert 'run_prompt_tool_studio_test' in backend and 'runtime_llm=invoked' in backend
assert 'version="5.583"' in main
print('v5.583 Prompt & Tool Studio project/runtime integration validation: PASS')
