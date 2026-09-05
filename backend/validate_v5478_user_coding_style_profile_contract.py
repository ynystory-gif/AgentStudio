from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS = (ROOT / 'frontend/src/styles.css').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
WORKFLOW = (ROOT / 'backend/app/services/agent_workflow.py').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
CODEX = (ROOT / 'backend/app/services/codex_app_server_service.py').read_text(encoding='utf-8')

checks = []
def check(name, ok):
    checks.append((name, bool(ok)))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")

check('frontend version 5.478', "AGENTSTUDIO_FRONTEND_VERSION='5.478'" in APP)
check('backend version 5.478', 'version="5.478"' in MAIN)
check('health version 5.478', '"version": "5.478"' in ROUTES)
check('codex version 5.478', 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.478"' in CODEX)
check('coding style defaults', 'DEFAULT_AGENT_CODING_STYLE' in APP and 'meaningful_names:true' in APP and 'avoid_magic_numbers:true' in APP)
check('coding style settings menu', 'function CodingStyleSettingsMenu' in APP and '기본 코딩 스타일' in APP)
check('style controls beside build title', 'function AgentBuildStyleControls' in APP and 'codingStyle={agentCodingStyle}' in APP)
check('all ten style options', all(token in APP for token in [
    'meaningful_names','uppercase_constants','snake_case_functions','pascal_case_classes','type_hints',
    'function_docstrings','notebook_single_responsibility','refactor_repetition','labeled_outputs','avoid_magic_numbers'
]))
check('coding style persisted in snapshot', 'user_coding_style:normalizeAgentCodingStyle(agentCodingStyle)' in APP)
check('coding style autosave dependency', 'codeDocumentationEnabled,\n    agentCodingStyle,\n    uiLayoutConfig' in APP)
check('coding style restored', 'setAgentCodingStyle(normalizeAgentCodingStyle(snapshot?.user_coding_style||DEFAULT_AGENT_CODING_STYLE))' in APP)
check('coding style sent to new build', 'user_coding_style:userCodingStyle' in APP and 'design_bundle:{' in APP)
check('coding style sent to redevelopment', 'code_documentation:codeDocumentation,\n              user_coding_style:userCodingStyle' in APP)
check('redevelopment api accepts style', 'user_coding_style: dict = {}' in ROUTES)
check('redevelopment preserves style', 'previous_bundle.get("user_coding_style")' in ROUTES and 'checkpoint.get("user_coding_style")' in ROUTES)
check('backend style policy', 'def _user_coding_style_policy' in WORKFLOW and 'USER_CODING_STYLE_DEFAULTS' in WORKFLOW)
check('backend style instruction', 'def _user_coding_style_instruction' in WORKFLOW and '[사용자 선택: 기본 코딩 스타일 - 반드시 적용]' in WORKFLOW)
check('notebook one-cell rule', '한 Cell에 한 역할' in WORKFLOW)
check('output label rule', '[PDF 로딩]' in WORKFLOW and '[Chunking]' in WORKFLOW and '[LLM]' in WORKFLOW)
check('magic number rule', 'Magic Number/String' in WORKFLOW)
check('style instruction applied to repair/generation', WORKFLOW.count('user_coding_style_instruction') >= 5 and '_user_coding_style_instruction(state)' in WORKFLOW)
check('style profile included in build context', '"user_coding_style": _user_coding_style_policy(state)' in WORKFLOW)
check('style profile included in validation result', '"user_coding_style_policy": user_coding_style_policy' in WORKFLOW)
check('style profile included in package result', '"user_preferences": _user_coding_style_policy(state)' in WORKFLOW)
check('coding style popover css', '.agent-coding-style-popover' in CSS and '.agent-coding-style-options' in CSS)

failed = [name for name, ok in checks if not ok]
if failed:
    raise SystemExit(f'v5.478 contract failed: {len(failed)}/{len(checks)} -> {failed}')
print(f'v5.478 user coding style profile contract: ALL PASS ({len(checks)}/{len(checks)})')
