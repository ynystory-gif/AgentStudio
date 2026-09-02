from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
PANEL = (ROOT / "frontend" / "src" / "components" / "system" / "SchedulerPanel.tsx").read_text(encoding="utf-8")
STYLES = (ROOT / "frontend" / "src" / "styles.css").read_text(encoding="utf-8")
MAIN = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
ROUTES = (ROOT / "backend" / "app" / "api" / "routes.py").read_text(encoding="utf-8")
SCHEDULER = (ROOT / "backend" / "app" / "api" / "scheduler_routes.py").read_text(encoding="utf-8")
THEME = (ROOT / "backend" / "app" / "api" / "ui_theme_dynamic_routes.py").read_text(encoding="utf-8")
JOBS = (ROOT / "backend" / "app" / "services" / "job_manager.py").read_text(encoding="utf-8")
CODEX = (ROOT / "backend" / "app" / "services" / "codex_app_server_service.py").read_text(encoding="utf-8")

checks = {
    "frontend version": "AGENTSTUDIO_FRONTEND_VERSION='5.432'" in APP,
    "backend app version": 'version="5.432"' in MAIN,
    "backend health version": '"version": "5.432"' in ROUTES,
    "codex version": 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.432"' in CODEX,
    "scheduler tab immediately after DB ERD": "['DB_ERD','DB ERD'],\n            ['SCHEDULER','스케줄러']" in APP,
    "scheduler panel render": "workspaceTab==='SCHEDULER'&&<SchedulerPanel" in APP,
    "scheduler poll endpoint": "/scheduler/jobs?include_terminal=" in APP,
    "scheduler cancel action": "/scheduler/jobs/${encodeURIComponent(source)}/${encodeURIComponent(jobId)}/cancel" in APP,
    "scheduler panel cancel label": "실행취소" in PANEL,
    "active default list": "현재 실행 중인 Scheduler 목록" in PANEL,
    "terminal history toggle": "종료된 작업 포함" in PANEL,
    "scheduler responsive styles": ".scheduler-dashboard" in STYLES and ".scheduler-cancel-button" in STYLES,
    "scheduler router included": "app.include_router(scheduler_router, prefix=\"/api\")" in MAIN,
    "scheduler list API": '@router.get("/jobs")' in SCHEDULER,
    "scheduler cancel API": '@router.post("/jobs/{source}/{job_id}/cancel")' in SCHEDULER,
    "job manager aggregation": "job_manager.jobs.values()" in SCHEDULER,
    "theme analyzer aggregation": "list_dynamic_import_job_snapshots" in SCHEDULER and "def list_dynamic_import_job_snapshots" in THEME,
    "job timestamps": "created_at: str = field(default_factory=_now_iso)" in JOBS and "updated_at: str = field(default_factory=_now_iso)" in JOBS,
    "backend cancellability": "await job_manager.cancel(job_key)" in SCHEDULER and "cancel_ui_theme_dynamic_import_job(job_key)" in SCHEDULER,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("v5.432 Scheduler workspace contract FAIL: " + ", ".join(failed))
print(f"v5.432 Scheduler workspace contract PASS {len(checks)}/{len(checks)}")
