from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend/src/styles.css').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
CODEX = (ROOT / 'backend/app/services/codex_app_server_service.py').read_text(encoding='utf-8')
MCP_MANAGER = (ROOT / 'backend/app/services/mcp_manager.py').read_text(encoding='utf-8')
MCP_REGISTRY = (ROOT / 'backend/app/services/mcp_registry.py').read_text(encoding='utf-8')
WORKFLOW = (ROOT / 'backend/app/services/agent_workflow.py').read_text(encoding='utf-8')
DESIGN_PATH = ROOT / 'backend/app/services/blender_3d_agent_design.py'
TOOL_PATH = ROOT / 'backend/app/services/tool_analyzer.py'

spec = importlib.util.spec_from_file_location('blender_3d_agent_design', DESIGN_PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

spec2 = importlib.util.spec_from_file_location('tool_analyzer', TOOL_PATH)
tool_mod = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(tool_mod)

design = mod.enforce_blender_3d_agent_design({}, 'Blender MCP를 이용한 3D 제작 Agent를 만들어줘')
sticky = mod.enforce_blender_3d_agent_design({'three_d_agent_plan': {'type': 'BLENDER_3D'}}, '추천 기능도 추가해줘')
plan = design.get('three_d_agent_plan') or {}
file_paths = {x.get('path') for x in (design.get('file_plan') or {}).get('new_files') or [] if isinstance(x, dict)}
tool = tool_mod.analyze_tool('execute_python_script', 'Blender scene bpy script executor')

checks = {
    'frontend version 5.437': "AGENTSTUDIO_FRONTEND_VERSION='5.437'" in APP,
    'backend version 5.437': 'version="5.437"' in MAIN,
    'health version 5.437': '"version": "5.437"' in ROUTES,
    'codex version 5.437': 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.437"' in CODEX,
    '3d specialization selector': "id:'BLENDER_3D'" in APP and '3D 제작 Agent · Blender MCP' in APP,
    'creator editor UI': '1. Agent Creator' in APP and '2. Agent Editor' in APP,
    'blender readiness route': '@router.get("/mcp/blender/readiness")' in ROUTES,
    'stdio create schema': 'transport: str = "streamable_http"' in ROUTES and 'command: str = ""' in ROUTES and 'args: list[str] = []' in ROUTES,
    'stdio discovery': 'async def discover_stdio' in MCP_MANAGER and 'StdioServerParameters' in MCP_MANAGER and 'stdio_client' in MCP_MANAGER,
    'stdio registry dispatch': 'discover_stdio(server.command, server.args or []' in MCP_REGISTRY,
    'stdio background no-auto-exec': "if auto_refresh and str(server.transport or '').casefold() == 'stdio':" in MCP_REGISTRY and 'continue' in MCP_REGISTRY,
    'frontend stdio form': "value=\"stdio\"" in APP and 'Arguments <small>한 줄에 인자 하나</small>' in APP,
    'blender generation instruction': '[Blender MCP 3D Agent 필수 계약]' in WORKFLOW,
    'editor incremental instruction': 'Agent Editor 증분 수정에서는 현재 Agent 소스/Architecture/Workflow를 먼저 기준으로' in WORKFLOW,
    '3d focus paths': '"three_d_agent_plan" in affected' in WORKFLOW,
    'design type': plan.get('type') == 'BLENDER_3D',
    'scene spec fields': {'object_type','materials','lighting','camera','animation','output_format','render_resolution'}.issubset(set(plan.get('scene_schema_fields') or [])),
    'scene state fields': {'scene_objects','materials','camera','lights','current_step','render_status','output_files'}.issubset(set(plan.get('scene_state_fields') or [])),
    'creator contract': (plan.get('creator_contract') or {}).get('mode') == 'AGENT_CREATOR',
    'editor contract': (plan.get('editor_contract') or {}).get('mode') == 'AGENT_EDITOR',
    'editor regression contract': 'backend/tests/test_blender_3d_regression.py' in file_paths,
    'sticky specialization': (sticky.get('three_d_agent_plan') or {}).get('type') == 'BLENDER_3D',
    'script risk classification': tool.category == '3D' and tool.risk_level == 4 and tool.requires_confirmation,
    'styles for creator editor': '.blender-agent-modes' in CSS and '.workflow-3d-editor-contract' in CSS,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('v5.437 contract failed: ' + ', '.join(failed))
print(f'v5.437 contract PASS {len(checks)}/{len(checks)}')
