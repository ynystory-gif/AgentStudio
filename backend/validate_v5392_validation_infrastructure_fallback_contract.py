from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
CSS=(ROOT/'frontend/src/styles.css').read_text(encoding='utf-8')
MAIN=(ROOT/'backend/app/main.py').read_text(encoding='utf-8')
ROUTES=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
WORKFLOW=(ROOT/'backend/app/services/agent_workflow.py').read_text(encoding='utf-8')
CODEX=(ROOT/'backend/app/services/codex_app_server_service.py').read_text(encoding='utf-8')
ROUTER=(ROOT/'backend/app/services/model_router.py').read_text(encoding='utf-8')
FAILURE=(ROOT/'backend/app/services/failure_artifact_service.py').read_text(encoding='utf-8')

checks={
    'frontend version': "AGENTSTUDIO_FRONTEND_VERSION='5.392'" in APP,
    'backend version': 'version="5.392"' in MAIN,
    'codex client version': 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.392"' in CODEX,
    'codex sandbox failure detector': '_looks_like_sandbox_infrastructure_failure' in CODEX and 'codex-windows-sandbox-setup' in CODEX,
    'codex runtime diagnostics': '_record_runtime_error' in CODEX and 'last_runtime_error' in CODEX and 'last_command' in CODEX and 'stderr_tail' in CODEX,
    'sandbox helper raw details': '_sandbox_helper_details' in CODEX and 'winerror' in CODEX and 'exit_code' in CODEX and 'raw_error' in CODEX,
    'codex answer infrastructure rejection': 'Codex Windows sandbox helper를 사용할 수 없어 Codex 결과를 채택하지 않았습니다.' in CODEX,
    'explicit codex repair fallback': 'LLMTask.EXECUTION_DEBUG_REPAIR' in ROUTER and 'candidates.append("ollama")' in ROUTER and 'candidates.append("openai")' in ROUTER,
    'local validation fallback': 'async def _collect_validation_fallback' in WORKFLOW and 'python -m compileall .' in WORKFLOW and 'npm run build --if-present' in WORKFLOW,
    'git evidence': 'git status --short' in WORKFLOW,
    'blocked status separated': WORKFLOW.count('VALIDATION_BLOCKED') >= 3 and '프로젝트 코드 결함과 검증 인프라 문제를 분리' in WORKFLOW,
    'fallback persisted in diagnostics': 'validation_fallback.json' in FAILURE and '검증 Fallback 진단' in FAILURE and 'Windows WinError' in FAILURE,
    'blocked is resumable': '"BLOCKED"' in ROUTES and '_is_failed_agent_build_status' in ROUTES,
    'frontend blocked UX': "status==='VALIDATION_BLOCKED'" in APP and 'Agent 생성 후 검증이 중단되었습니다.' in APP,
    'frontend revalidation action': '↻ 검증 다시 실행' in APP and 'startAgentDevelopment({redevelopment:true})' in APP,
    'frontend action style': '.development-final-status-actions' in CSS,
    'build marker': 'ValidationInfrastructureFallback' in ROUTES,
}

failed=[name for name,ok in checks.items() if not ok]
print(f"v5.392 contract: {sum(checks.values())}/{len(checks)} PASS")
if failed:
    print('FAILED:', ', '.join(failed))
    raise SystemExit(1)
