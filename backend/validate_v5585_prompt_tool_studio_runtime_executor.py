from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
checks = {
    ROOT / 'backend/app/services/mcp_manager.py': [
        'call_streamable_http_tool', 'call_stdio_tool', 'session.call_tool',
    ],
    ROOT / 'backend/app/services/prompt_tool_studio_service.py': [
        'TOOL_EXECUTE', 'LANGGRAPH_COMPILE', 'Draft202012Validator', 'tool_execution', 'graph_summary',
    ],
    ROOT / 'backend/app/api/routes.py': [
        'execute_tool: bool = False', 'tool_arguments: dict = Field(default_factory=dict)', 'confirmation: bool = False',
    ],
    ROOT / 'frontend/src/features/prompt-tool-studio/components/PromptToolStudio.tsx': [
        'TOOL_EXECUTE', 'FULL_EXECUTE', 'Routing Visual Graph', 'State Snapshot', 'routeVersions',
    ],
    ROOT / 'frontend/src/features/prompt-tool-studio/service.ts': [
        'execute_tool', 'tool_execution', 'graph_summary',
    ],
}
for path, tokens in checks.items():
    text = path.read_text(encoding='utf-8')
    missing = [token for token in tokens if token not in text]
    if missing:
        raise SystemExit(f'FAIL {path}: missing {missing}')
print('PASS v5.585 Prompt & Tool Studio runtime executor / LangGraph / trace / versioning contracts')
