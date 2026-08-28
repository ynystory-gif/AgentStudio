from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROUTES = (ROOT / "backend/app/api/routes.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / "backend/app/services/agent_factory_workflow_design.py").read_text(encoding="utf-8")
APP = (ROOT / "frontend/src/App.jsx").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/src/styles.css").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")

checks = {
    "version": "AGENTSTUDIO_FRONTEND_VERSION='5.393'" in APP and 'version="5.393"' in (ROOT / "backend/app/main.py").read_text(encoding="utf-8"),
    "runtime truth endpoint": '@router.get("/workflow/runtime-status")' in ROUTES and 'execution_active' in ROUTES,
    "terminal reconcile": "Backend Job의 terminal event" in APP and "setActiveWorkflowJobId('')" in APP,
    "requirement supersession": "_normalize_latest_confirmed_requirement_conflicts" in ROUTES and "Headless UI와 충돌" in ROUTES,
    "safe request flag": "safe_mode: bool = False" in ROUTES,
    "safe deterministic builder": "def build_safe_agent_factory_design" in WORKFLOW and "DETERMINISTIC_SAFE_DESIGN" in WORKFLOW,
    "route recovery fallback": "preview_recovery" in ROUTES and "build_safe_agent_factory_design" in ROUTES,
    "retry AI action": "AI 설계 다시 시도" in APP,
    "safe continue action": "안전 설계로 계속" in APP,
    "database-only recovery": "DB 초안만 다시 계산" in APP and "retryDatabaseDesignPreview" in APP,
    "provider diagnostic": "AI Provider 상태 확인" in APP and "/llm/runtime-status" in APP,
    "back to interview": "설계 인터뷰로 돌아가기" in APP,
    "db validator recovery": "안전 규칙으로 재설계" in APP and "database-design-recovery-actions" in APP,
    "db enrichment warning": "AI DB 보강은 실패했지만" in APP,
    "recovery styles": ".workflow-recovery-card'" not in CSS and ".workflow-recovery-card{" in CSS,
    "readme": "v5.393 ExecutionStateRequirementDbDesignRecovery" in README,
}

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(f"{'PASS' if ok else 'FAIL'} - {name}")
if failed:
    raise SystemExit(f"Contract failed: {failed}")
print(f"PASS {sum(checks.values())}/{len(checks)}")
