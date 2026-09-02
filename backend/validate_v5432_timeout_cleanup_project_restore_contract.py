from pathlib import Path
import ast

ROOT=Path(__file__).resolve().parents[1]
APP=(ROOT/'frontend/src/App.jsx').read_text(encoding='utf-8')
THEME_V2=(ROOT/'frontend/src/components/layout/LayoutThemeDynamicSourceV2.jsx').read_text(encoding='utf-8')
SCHED_PANEL=(ROOT/'frontend/src/components/system/SchedulerPanel.tsx').read_text(encoding='utf-8')
SCHED=(ROOT/'backend/app/api/scheduler_routes.py').read_text(encoding='utf-8')
HARD=(ROOT/'backend/app/services/ui_theme_job_hard_timeout_bridge.py').read_text(encoding='utf-8')
ROUTES=(ROOT/'backend/app/api/routes.py').read_text(encoding='utf-8')
MAIN=(ROOT/'backend/app/main.py').read_text(encoding='utf-8')
CODEX=(ROOT/'backend/app/services/codex_app_server_service.py').read_text(encoding='utf-8')

checks={
    'version sync': 'version="5.432"' in MAIN and '"version": "5.432"' in ROUTES and "AGENTSTUDIO_FRONTEND_VERSION='5.432'" in APP and 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.432"' in CODEX,
    'five minute backend deadline retained': 'HARD_JOB_TIMEOUT_SECONDS = 300' in HARD,
    'timeout failure exposes cleanup lifecycle': 'backend_cleanup_state="running"' in HARD and 'backend_execution_active=True' in HARD and 'backend_analysis_ended=False' in HARD,
    'cleanup completion is explicit': 'backend_cleanup_state="complete"' in HARD and 'backend_execution_active=False' in HARD and 'backend_analysis_ended=True' in HARD and 'backend_terminated_at=ended_at' in HARD,
    'worker process verification': 'active_theme_worker_pids()' in HARD and 'backend_worker_process_count' in HARD and 'shutdown_theme_workers()' in HARD,
    'wait_for timeout race normalized': 'source="executor_wait_for"' in HARD and 'HARD_JOB_TIMEOUT_SECONDS - 1' in HARD,
    'frontend waits for backend cleanup': 'timeoutCleanupPending' in THEME_V2 and 'backend_analysis_ended !== true' in THEME_V2 and 'backend_cleanup_completed !== true' in THEME_V2,
    'frontend shows backend ended': 'Backend 작업 종료 확인됨' in THEME_V2 and 'data-v2-backend' in THEME_V2,
    'frontend timeout never becomes user cancel': 'Never call the user-cancel endpoint because' in THEME_V2,
    'scheduler carries backend cleanup fields': 'backend_execution_active = bool(snapshot.get("backend_execution_active"))' in SCHED and 'backend_cleanup_completed' in SCHED and 'backend_worker_process_count' in SCHED,
    'scheduler shows backend termination state': 'Backend 종료 확인됨' in SCHED_PANEL and 'Backend 종료 처리 중' in SCHED_PANEL,
    'project load blocks autosave before restore': 'requirementDraftDecisionPendingRef.current=true' in APP and '이전 설계 검토 · Workflow · DB SQL 상태를 복원하는 중...' in APP,
    'project load auto restore helper': 'restoreExistingProjectDesignState' in APP and 'restoreRequirementDraft(key,snapshot,buildResume)' in APP,
    'project load opens restored workflow': "setWorkspaceTab(restoredDesign.restored?'WORKFLOW':'CODE')" in APP,
    'project load reports restored DB SQL': "restoredDesign.hasDatabaseSql?' · DB SQL':''" in APP,
    'restore uses persisted workflow preview': 'const restoredPreview=' in APP and 'setTargetWorkflowPreview(restoredPreview)' in APP,
    'restore populates live DB SQL': 'ddl_preview:String(restoredDatabasePlan.ddl_preview||restoredDatabasePlan.ddl||\'\')' in APP,
    'backend hydrates stale checkpoint SQL': 'def _hydrate_saved_database_sql' in ROUTES and 'backend/migrations/001_initial_schema.sql' in ROUTES,
    'hydrated DB plan finalized': 'plan["finalized"] = True' in ROUTES and 'plan["confirmed"] = True' in ROUTES,
    'generic restore prompt suppressed during direct project load': 'projectAutoRestoreRootRef' in APP and 'loadProject() performs an authoritative server/local checkpoint restore itself' in APP,
}

for path in [
    ROOT/'backend/app/services/ui_theme_job_hard_timeout_bridge.py',
    ROOT/'backend/app/api/scheduler_routes.py',
    ROOT/'backend/app/api/routes.py',
    ROOT/'backend/app/main.py',
]:
    ast.parse(path.read_text(encoding='utf-8'),filename=str(path))

failed=[name for name,ok in checks.items() if not ok]
for name,ok in checks.items():
    print(('PASS' if ok else 'FAIL'),name)
if failed:
    raise SystemExit('v5.432 contract FAIL: '+', '.join(failed))
print(f'v5.432 timeout cleanup + project restore contract PASS {len(checks)}/{len(checks)}')
