from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
checks = {
    'frontend/src/app/App.tsx': ["AGENTSTUDIO_FRONTEND_VERSION='5.586'", 'projectRoot={String(newAgentProjectRoot||root||\'\')}'],
    'frontend/src/features/prompt-tool-studio/service.ts': ['project_root:payload.projectRoot', 'llm_usage?:'],
    'frontend/src/features/prompt-tool-studio/components/PromptToolStudio.tsx': [
        'schemaVersion:5', 'Studio 버전 저장', 'Studio Version / Diff', 'Full Test Report',
        "tools.filter(t=>t.type!=='Agent')", 'Runtime Source / SQL', 'Execution Trace',
    ],
    'backend/app/services/prompt_tool_studio_executor.py': [
        'async def execute_studio_tool', "tool_type in {'PYTHON', 'DATABASE'}", 'preview_database_sql',
        "verb in {'SELECT', 'WITH', 'EXPLAIN', 'SHOW'}", 'python_execution_manager.execute', 'httpx.AsyncClient',
    ],
    'backend/app/services/prompt_tool_studio_service.py': [
        'LANGGRAPH_RUNTIME', 'compiled_graph.ainvoke', 'execute_studio_tool(', 'DB_SQL_PREVIEW', 'llm_usage',
    ],
    'backend/app/api/routes.py': ['project_root: str = ""', 'project_root=req.project_root', '"version": "5.586"'],
}
for rel, needles in checks.items():
    text = (ROOT / rel).read_text(encoding='utf-8')
    for needle in needles:
        assert needle in text, f'{rel}: missing {needle}'

executor = (ROOT / 'backend/app/services/prompt_tool_studio_executor.py').read_text(encoding='utf-8')
assert 'INSERT' not in executor.split("read_only =", 1)[1].split('\n', 1)[0], 'read-only verb set should not allow INSERT'
print('[PASS] v5.586 Prompt & Tool Studio unified runtime contracts')
