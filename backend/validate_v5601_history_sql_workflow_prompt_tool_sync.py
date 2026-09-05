from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


main_py = text(BACKEND / "app" / "main.py")
routes_py = text(BACKEND / "app" / "api" / "routes.py")
account_routes = text(BACKEND / "app" / "api" / "account_settings_routes.py")
account_service = text(BACKEND / "app" / "services" / "account_setting_service.py")
adaptive_service = text(BACKEND / "app" / "services" / "project_adaptive_report.py")
app_tsx = text(FRONTEND / "src" / "app" / "App.tsx")
history_tsx = text(FRONTEND / "src" / "features" / "history" / "ProjectHistoryPanel.tsx")
prompt_tool_tsx = text(FRONTEND / "src" / "features" / "prompt-tool-studio" / "components" / "PromptToolStudio.tsx")
prompt_tool_model = text(FRONTEND / "src" / "features" / "prompt-tool-studio" / "model.ts")
styles = text(FRONTEND / "src" / "styles.css") + "\n" + text(FRONTEND / "src" / "features" / "history" / "projectHistory.css")

# Version markers.
require('version="5.601"' in main_py, "Backend FastAPI version is not 5.601")
require("AGENTSTUDIO_FRONTEND_VERSION='5.601'" in app_tsx, "Frontend version is not 5.601")
require('"version": "5.601"' in routes_py, "Health version is not 5.601")
require("HistorySqlWorkflowSaveExistingPromptToolSyncNoopSave" in routes_py, "v5.601 build marker missing")

# History SQL scratch.
require("@router.post('/history/{history_id}/sql')" in account_routes, "History SQL API missing")
require("create_project_history_sql_scratch" in account_service, "History SQL scratch service missing")
require(".agentstudio' / 'sql_scratch" in account_service, "Project-local SQL scratch path missing")
require("project_setting_histories_id" in account_service and "[변경 전 JSON]" in account_service, "History SQL content missing")
require("/account-settings/history/${historyId}/sql" in history_tsx, "History SQL UI API call missing")
require("SQL 임시 파일" in history_tsx and "project-history-sql-button" in history_tsx, "History SQL list/detail buttons missing")

# Explicit Workflow save/restore and dirty state.
require("workspace-workflow-save-button" in app_tsx, "Workflow save button missing")
require("setting_group:'WORKFLOW'" in app_tsx and "setting_key:'default'" in app_tsx, "Workflow project DB save missing")
require("workflowSavedSignature" in app_tsx and "workflowSaveDirty" in app_tsx, "Workflow dirty signature guard missing")
require("PROJECT_SETTING_WORKFLOW" in app_tsx, "Saved Workflow restore missing")

# No-op save semantics.
require("변경사항이 없어 저장하지 않았습니다." in account_service, "Project/account setting no-op message missing")
require("Repeated clicks on the same save/apply button" in account_service, "Project history duplicate guard missing")
require("_design_values_equal" in routes_py and "unchanged" in routes_py, "Agent design no-op save guard missing")
for marker in ("saveStudioVersion", "savePromptVersion", "saveToolVersion", "saveRouteVersion", "saveStateSnapshot", "saveTestReport"):
    require(marker in prompt_tool_tsx, f"Prompt & Tool no-op save path missing: {marker}")
require("comparable(stripVersionMeta" in prompt_tool_tsx, "Prompt/Tool version duplicate comparison missing")

# Existing project Prompt/Tool load and source-state badge.
require("prompt_tool_discovery" in adaptive_service, "Source Prompt/Tool discovery payload missing")
require("discovery_budget = 8_000_000" in adaptive_service, "Bounded source discovery guard missing")
require("mergeExistingProjectPromptToolDiscovery" in app_tsx, "Project Prompt/Tool merge missing")
require("setting_group=PROMPT_TOOL_STUDIO" in app_tsx, "Saved project Prompt/Tool setting restore missing")
require("sourceSyncInitialized" in app_tsx and "sourceFingerprint" in app_tsx, "Source baseline/fingerprint comparison missing")
require("syncStatus?:'NEW'|'CHANGED'|'SYNCED'|'MANUAL'" in prompt_tool_model, "Tool sync status model missing")
for label in ("신규", "변경", "동일"):
    require(label in prompt_tool_tsx, f"Prompt/Tool status badge label missing: {label}")
require("pts-sync-badge" in styles, "Prompt/Tool status badge styles missing")

# Preserve v5.600 strict first-item fix.
require("next[0].id" not in history_tsx, "Unsafe next[0].id access regressed")
require("const firstItem=next[0]" in history_tsx and "if(firstItem&&!selectedId)setSelectedId(firstItem.id)" in history_tsx, "Strict-safe first item guard missing")

print("[PASS] v5.601 History SQL / Workflow Save / Existing Prompt-Tool Sync / No-op Save contracts")
