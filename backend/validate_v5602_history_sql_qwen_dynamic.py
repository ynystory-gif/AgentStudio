from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"[PASS] {message}")


main_py = read("backend/app/main.py")
routes_py = read("backend/app/api/routes.py")
account_service = read("backend/app/services/account_setting_service.py")
account_routes = read("backend/app/api/account_settings_routes.py")
history_ui = read("frontend/src/features/history/ProjectHistoryPanel.tsx")
db_setup = read("frontend/src/features/database/AgentDatabaseSetup.tsx")
learning_sql = read("backend/app/services/learning_sql_export_service.py")
model_manager = read("backend/app/services/ollama_model_manager_service.py")
active_model = read("backend/app/services/active_ollama_model_service.py")
learning_service = read("backend/app/services/llm_learning_service.py")
learning_routes = read("backend/app/api/learning_routes.py")
learning_ui = read("frontend/src/components/learning/LlmLearningCenter.tsx")
ai_service = read("backend/app/services/ai_trends/service.py")
ai_ui = read("frontend/src/features/ai-trends/components/AITrendsDashboard.tsx")
ai_hook = read("frontend/src/features/ai-trends/hooks/useAITrends.ts")
app_tsx = read("frontend/src/app/App.tsx")

# Version
require('version="5.602"' in main_py, "Backend version is v5.602")
require("AGENTSTUDIO_FRONTEND_VERSION='5.602'" in app_tsx, "Frontend version is v5.602")
require('"version": "5.602"' in routes_py, "Health version is v5.602")
require("HistoryListSqlSchemaQualifiedDbBindingSemanticQwenDynamicModel" in routes_py, "v5.602 build marker exists")

# History SQL placement / schema
require("/account-settings/history/sql-list" in history_ui, "History list-query SQL endpoint is wired")
require("project-history-list-sql-button" in history_ui, "History list toolbar SQL button exists")
require("project-history-sql-button" not in history_ui, "Per-history-row SQL button is removed")
require("/account-settings/history/${historyId}/sql" in history_ui, "History detail SQL button remains")
require("@router.post('/history/sql-list')" in account_routes, "History list SQL API exists")
require("current_runtime_schema_name()" in account_service, "History SQL resolves current runtime schema")
require("history_table = f'{quote_identifier(schema_name)}.\"project_setting_histories\"'" in account_service, "History SQL uses schema-qualified table")
require("'    created_at',\n        f'FROM {history_table}'," in account_service, "History detail SELECT keeps valid newline-separated FROM")

# DB provider binding semantics
require("const bindingKey=kind==='supabase'?'postgresql':kind" in db_setup, "Agent DB bindings use provider-specific setting keys")
require("setting_key:bindingKey" in db_setup, "Project DB binding no longer overwrites one default key")
require("history_action: str = 'AUTO'" in account_service, "Project setting history action is auto-semantic")
require("resolved_history_action = 'CREATE' if created else 'UPDATE'" in account_service, "New provider is CREATE; existing provider change is UPDATE")
require("_history_display_action" in account_service and "DATABASE_PROFILE_BINDING" in account_service, "Legacy cross-provider UPDATE is displayed as semantic CREATE without rewriting audit rows")

# SQL export schema qualification
require("current_runtime_schema_name()" in learning_sql, "Learning SQL resolves current runtime schema")
for table in ("llm_misjudgment_cases", "llm_learning_datasets", "llm_learning_problems", "llm_learning_pc_applications"):
    require(f'\"{table}\"' in learning_sql, f"Learning SQL table {table} is qualified through schema table map")
require(not re.search(r"(?m)^(?:FROM|JOIN|LEFT JOIN|RIGHT JOIN|UPDATE|INSERT INTO|DELETE FROM)\s+llm_", learning_sql), "Learning generated SQL contains no bare llm_* table reference")

# Qwen recommendation / compatibility / dynamic resolution
require('LATEST_RECOMMENDED_MODEL = "qwen3.8:27b-mtp-q4_K_M"' in model_manager, "Latest recommended Qwen is qwen3.8:27b-mtp-q4_K_M")
require("def qwen_model_metadata" in model_manager, "Qwen model metadata is structured")
require('WEIGHT_TRAINING_OLLAMA_BASE_MODEL = "qwen3.5:4b"' in learning_service, "Existing Qwen3.5 QLoRA compatibility is preserved")
require('WEIGHT_TRAINING_HF_BASE_MODEL = "Qwen/Qwen3.5-4B"' in learning_service, "Existing Qwen3.5 HF weight-training base is preserved")
require("async def resolve_qwen_model_context" in active_model, "Shared project-aware Qwen resolver exists")
require("project_model" in active_model and "account_model" in active_model and "installed_qwen" in active_model, "Qwen resolver supports project/account/default/installed sources")
require("current_qwen_model" in learning_routes and "current_qwen_context" in learning_routes, "Learning summary exposes shared current Qwen context")
require("project_root" in learning_routes, "Learning summary accepts project root")
require("currentQwenModel" in learning_ui and "recommendedModel" in learning_ui, "Learning Center separates current and latest recommended Qwen")
require("qwen3.8:27b-mtp-q4_K_M" not in learning_ui, "Learning Center does not hardcode current/latest qwen3.8 in UI")
require("resolve_qwen_model_context" in ai_service, "AI Trends uses shared Qwen resolver")
require("model_context" in ai_service, "AI Trends returns Qwen model context")
require("currentQwenModel" in ai_ui and "data?.model_context?.model" in ai_ui, "Main AI Trends dataset card displays dynamic full Qwen model")
require("qwen3.5" not in ai_ui.casefold(), "Main AI Trends UI has no qwen3.5 hardcoded display")
require("projectRoot" in ai_hook and "loadAITrends(projectRoot)" in ai_hook, "AI Trends refreshes when project root changes")
require("useAITrends(screen==='HOME',String(activeWorkspaceRoot||''))" in app_tsx, "Main page passes active project root to AI Trends")

print("[PASS] v5.602 History SQL / DB binding semantics / Dynamic Qwen contracts")
