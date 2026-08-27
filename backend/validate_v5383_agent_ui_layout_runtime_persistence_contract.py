from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
CSS = (ROOT / "frontend" / "src" / "styles.css").read_text(encoding="utf-8")
MAIN = (ROOT / "backend" / "app" / "main.py").read_text(encoding="utf-8")
ROUTES = (ROOT / "backend" / "app" / "api" / "routes.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / "backend" / "app" / "services" / "agent_workflow.py").read_text(encoding="utf-8")
SERVICE = (ROOT / "backend" / "app" / "services" / "codex_app_server_service.py").read_text(encoding="utf-8")

checks = {
    "frontend version": "AGENTSTUDIO_FRONTEND_VERSION='5.383'" in APP,
    "backend main version": 'version="5.383"' in MAIN,
    "backend health version": '"version": "5.383"' in ROUTES,
    "codex client version": 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.383"' in SERVICE,
    "build marker": "AgentUILayoutRuntimePersistenceControls" in ROUTES,
    "runtime always persistent": "agent_runtime_persistent:true" in APP and "메뉴 이동 시 Agent 실행 유지" in APP and "항상 ON" in APP,
    "screen restore controls": all(token in APP for token in ("restore_screen_state", "restore_scroll_position", "restore_draft_input", "restore_selection_state", "screen_restore_mode")),
    "running task controls": all(token in APP for token in ("show_running_tasks", "runtime_status_position", "top_statusbar", "floating_button")),
    "notification controls": all(token in APP for token in ("notify_agent_complete", "notify_agent_failure", "run_item_navigate")),
    "event reconnect fixed": "event_stream_auto_reconnect:true" in APP and "event_stream_resync:true" in APP,
    "section css": ".ui-layout-config-section" in CSS and ".ui-layout-runtime-lock" in CSS,
    "workflow design rule": "session_id/run_id 기반 Backend Runtime" in ROUTES and "누락 이벤트 재동기화" in ROUTES,
    "code generation rule": "Agent run의 cancel/stop" in WORKFLOW and "WebSocket/SSE가 끊겼다가 다시 연결되면" in WORKFLOW,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("FAIL v5.383 contract: " + ", ".join(failed))
print("PASS v5.383 Agent UI Layout Runtime Persistence Controls contract")
