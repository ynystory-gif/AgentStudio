from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend' / 'src' / 'App.jsx').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend' / 'app' / 'api' / 'routes.py').read_text(encoding='utf-8')
WORKFLOW = (ROOT / 'backend' / 'app' / 'services' / 'agent_workflow.py').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend' / 'app' / 'main.py').read_text(encoding='utf-8')
PS1 = (ROOT / 'SYSTEM_ADMIN.ps1').read_text(encoding='utf-8')

checks = {
    'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.369'" in APP,
    'backend version': 'version="5.369"' in MAIN,
    'launcher version': '$FallbackAgentStudioVersion = "5.369"' in PS1,
    'redevelopment endpoint': '@router.post("/workflow/redevelop-start-job")' in ROUTES,
    'redevelopment descriptor': 'def _redevelopment_descriptor(' in ROUTES,
    'failure status detector': 'def _is_failed_agent_build_status(' in ROUTES,
    'failure previous-node mapping': '_FAILURE_RESUME_PREVIOUS_NODE' in ROUTES,
    'request resume mode': 'resume_mode: bool = False' in ROUTES,
    'initial state reuse': 'previous_build_state' in ROUTES and 'merged["resume_from_node"]' in ROUTES,
    'dynamic graph entry': 'resume_entry_router' in WORKFLOW and 'route_workflow_entry' in WORKFLOW,
    'frontend button': '↻ 재개발 시작' in APP,
    'frontend activation': 'redevelopmentEnabled={Boolean(redevelopmentInfo?.available)}' in APP,
    'frontend resume API': "api('/workflow/redevelop-start-job'" in APP,
    'normal build blocked on failure': "stage!=='PROJECT_CREATED'||redevelopmentEnabled" in APP,
    'resume prior stage shown': 'resume_from_node' in APP,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit('FAIL v5.369: ' + ', '.join(failed))
print('PASS v5.369 Failed Build Redevelopment Checkpoint contract')
