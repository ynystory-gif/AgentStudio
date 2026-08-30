from datetime import datetime
from urllib.parse import quote
from pathlib import Path
from app.services.db_gateway import DatabaseGateway
from app.services.folder_picker import pick_folder, pick_file, pick_files
from app.services.ollama_installer import install_ollama_windows
from app.services.ollama_runtime_manager import get_ollama_runtime_status, start_ollama_server, stop_ollama_server, restart_managed_ollama_for_gpu_mode
from app.services.gpu_runtime_manager import get_gpu_runtime_status, set_gpu_runtime_enabled, gpu_recommendation
import asyncio
import json
from app.models.entities import Project, ProjectAnalysis, AgentDesignProject, AgentDesignProjectVersion, UITheme
from app.services.project_paths import resolve_project_paths
from app.services.ui_theme_service import analyze_theme_from_url, build_rules, merge_theme_analyses
from app.services.frontend_theme_registry import list_frontend_theme_targets
from app.services.database_provisioning import provision_agentstudio_database
from app.services.database_schema_design import build_database_plan, finalize_database_plan, materialize_database_plan
from app.services.db_erd_service import build_project_db_erd, build_agentstudio_db_erd
from app.core.config import get_settings
from app.services.pgvector_installer import install_pgvector_windows18, latest_pg18_windows_release, detect_postgresql18_root, validate_postgresql18_root
from app.services.settings_service import get_editable_settings, update_settings, migrate_env_settings_to_db, rename_current_machine, save_database_env_settings
from app.services.connection_test_service import (
    test_postgresql, test_postgresql_admin, test_pgvector, test_ollama, test_openai, test_tavily, test_langsmith, test_all
)
from app.services.llm_runtime_status_service import get_llm_runtime_status
from app.services.connection_import_service import analyze_connection_file
from app.services.database_runtime_service import (
    runtime_status as get_database_runtime_status,
    activate_database_provider,
    save_supabase_runtime_settings,
    initialize_supabase_schema,
    schema_script_path as get_supabase_schema_script_path,
)
from app.services.weather_service import build_weather_dashboard, weather_config
from app.services.llm_catalog_service import build_llm_catalog
from app.services.project_root_registry import adopt_legacy_projects_for_current_pc, ensure_persisted_project_root
from app.services.terminal_completion_service import complete_terminal_input
from app.services.managed_process_service import managed_process_service
from app.services.python_execution_service import python_execution_manager
from app.services.source_debug_service import source_debug_capability, run_source_code
from app.services.presentation_preview_service import (
    PresentationPreviewError,
    prepare_presentation_preview,
)
from app.services.presentation_export_service import (
    PPTX_MIME,
    build_agentstudio_presentation,
)
from app.services.sql_workspace_service import (
    get_profile as get_sql_workspace_profile,
    list_profiles as list_sql_workspace_profiles,
    save_profile as save_sql_workspace_profile,
    rename_profile as rename_sql_workspace_profile,
    delete_profile as delete_sql_workspace_profile,
    activate_profile as activate_sql_workspace_profile,
    profile_storage_info as get_sql_workspace_profile_storage_info,
    connect as connect_sql_workspace,
    disconnect as disconnect_sql_workspace,
    release_sqlite_file_locks as release_sql_workspace_file_locks,
    status as get_sql_workspace_status,
    execute as execute_sql_workspace,
    cancel_execution as cancel_sql_workspace_execution,
    list_database_objects as list_sql_workspace_objects,
    list_redis_keys as list_sql_workspace_redis_keys,
    get_redis_key as get_sql_workspace_redis_key,
    list_firestore_collections as list_sql_workspace_firestore_collections,
    list_firestore_documents as list_sql_workspace_firestore_documents,
    get_firestore_document as get_sql_workspace_firestore_document,
    create_redis_python_script as create_sql_workspace_redis_python_script,
    create_firestore_python_script as create_sql_workspace_firestore_python_script,
    redis_python_script_runtime_env as get_redis_python_script_runtime_env,
    sqlite_project_status as get_sqlite_project_status,
    open_database_object as open_sql_workspace_object,
    create_table_script as create_sql_workspace_table_script,
    create_table_diagram as create_sql_workspace_table_diagram,
    create_schema_diagram as create_sql_workspace_schema_diagram,
    create_table_alter_script as create_sql_workspace_table_alter_script,
    create_table_dml_script as create_sql_workspace_table_dml_script,
    create_postgresql_admin_script as create_sql_workspace_postgresql_admin_script,
)
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Request, Query
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel
from langgraph.types import Command
from sqlalchemy import select, func
from app.core.database import SessionLocal, ensure_runtime_metadata_tables, migrate_agentstudio_schema, verify_project_schema, current_event_loop_name
from app.core.machine_identity import current_pc_name
from app.models.entities import MCPServer, ToolRecord
from app.services.ws_hub import hub
from app.services.job_manager import job_manager
from app.services.system_status import get_status
from app.services.port_service import recommend_agentstudio_ports
from app.services.browser_proxy_service import (
    BrowserProxyError,
    fetch_external_page,
    proxy_error_html,
    reconstruct_proxy_target,
)
from app.services.chromium_browser_service import (
    ChromiumBrowserError,
    chromium_browser_manager,
)
from app.services.codex_app_server_service import codex_app_server_manager
from app.services.ai_attachment_service import (
    register_selected_files,
    release_attachments,
    attachment_metadata,
    build_attachment_context,
    build_requirements_attachment_context,
    prepare_attachment,
    redact_sensitive_text,
)
from app.services.local_control import list_files, list_directories, read_file, write_file, run_command, register_runtime_project_root, get_runtime_project_roots, create_folder, rename_path, create_file, delete_files, project_file_snapshot, get_file_meta, get_file_hash_states, validate_project_root, watch_project_changes, search_project_text, active_command_processes, ExternalFileChangedError, InvalidNotebookContentError
from app.services.tavily_service import web_search
from app.services.requirements_agent import next_interview_message, summarize_attachment_requirements, build_attachment_requirements_display_summary
from app.services.attachment_requirement_mining import extract_attachment_requirement_registry, format_requirement_registry_memory
from app.services.llm_usage_service import usage_context, read_usage_summary, read_llm_history
from app.services.agent_builder import build_plan
from app.services.tool_analyzer import analyze_tool
from app.services.mcp_manager import discover_streamable_http
from app.services.mcp_registry import mcp_registry_monitor
from app.services.langgraph_runtime import agent_graph_runtime
from app.services.git_service import git_status, git_diff, checkpoint
from app.services.project_analyzer import scan_project, find_related_files, local_project_summary
from app.services.high_speed_analysis import high_speed_analysis_status
from app.services.project_adaptive_report import build_project_adaptive_report
from app.services.memory_service import add_memory, search_memory
from app.services.simple_question import answer_simple_question
from app.services.tool_analyzer import analyze_tool_with_llm
from app.services.coding_style_registry import list_rules, load_template_registry
from app.services.coding_style_analyzer import analyze_coding_style_text
from app.services.coding_rule_selector import coding_rules_for_request
from app.services.agent_factory_policy import format_agent_factory_policy_for_prompt
from app.services.coding_rule_validator import validate_code_style
from app.services.context_budget_service import (
    MAX_FILE_EDIT_PROMPT_CHARS,
    approximate_tokens,
    build_notebook_edit_context,
    merge_notebook_cell,
    trim_style_prompt,
)
from app.services.agent_factory_policy_planner import (
    format_factory_policies_for_prompt,
    infer_fastapi_factory_plan,
    load_agent_factory_policies,
)
from app.services.agent_factory_workflow_design import build_safe_agent_factory_design, design_agent_factory, design_agent_factory_incremental
from app.services.failure_artifact_service import (
    begin_workflow_diagnostic_run,
    normalize_workflow_result,
)
from app.services.coding_rule_governance import classify_candidates
from app.services.coding_rule_priority import load_rule_policy


def _as_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def _instruction_allows_comment_replacement(instruction: str) -> bool:
    """
    사용자가 명시적으로 주석 삭제/수정 또는 파일 전체 교체를 요청한 경우에만
    기존 주석 보존 보호를 해제합니다.
    """
    compact = "".join(str(instruction or "").casefold().split())
    markers = (
        "주석삭제", "주석제거", "주석수정", "주석변경",
        "힌트삭제", "힌트제거", "힌트수정", "힌트변경",
        "전체교체", "전체내용교체", "파일전체교체",
        "기존코드전부삭제", "기존내용전부삭제",
        "removecomment", "deletecomment", "editcomment",
        "changecomment", "replacewholefile", "replaceentirefile",
    )
    return any(marker in compact for marker in markers)


def _is_preservable_comment_line(path: str, line: str) -> bool:
    stripped = str(line or "").lstrip()
    if not stripped:
        return False

    ext = Path(path or "").suffix.casefold()

    hash_comment_exts = {
        ".py", ".pyw", ".ps1", ".psm1", ".psd1",
        ".sh", ".bash", ".zsh", ".yaml", ".yml",
        ".toml", ".ini", ".cfg", ".conf", ".r",
    }
    slash_comment_exts = {
        ".js", ".jsx", ".ts", ".tsx", ".java",
        ".c", ".h", ".cpp", ".hpp", ".cs", ".go",
        ".rs", ".swift", ".kt", ".kts",
    }

    if ext in hash_comment_exts:
        return stripped.startswith("#")
    if ext in slash_comment_exts:
        return (
            stripped.startswith("//")
            or stripped.startswith("/*")
            or stripped.startswith("*")
            or stripped.startswith("*/")
        )
    if ext == ".sql":
        return (
            stripped.startswith("--")
            or stripped.startswith("/*")
            or stripped.startswith("*")
            or stripped.startswith("*/")
        )
    if ext in {".cmd", ".bat"}:
        upper = stripped.upper()
        return stripped.startswith("::") or upper == "REM" or upper.startswith("REM ")

    return False


def _preserve_existing_comments(
    original: str,
    proposed: str,
    path: str,
    instruction: str,
) -> tuple[str, int]:
    """
    LLM이 코드 추가 과정에서 기존 학습용 힌트/설명 주석을 통째로 치환하는
    문제를 방지합니다. 사용자가 주석 변경 또는 파일 전체 교체를 명시하지
    않았다면, diff에서 사라진 기존 full-line comment를 원래 변경 위치 앞에
    결정적으로 복원합니다.
    """
    if not original or not proposed:
        return proposed, 0
    if _instruction_allows_comment_replacement(instruction):
        return proposed, 0

    import difflib
    from collections import Counter

    original_lines = str(original).splitlines()
    proposed_lines = str(proposed).splitlines()

    original_comments = [
        line for line in original_lines
        if _is_preservable_comment_line(path, line)
    ]
    if not original_comments:
        return proposed, 0

    original_counts = Counter(original_comments)
    proposed_counts = Counter(
        line for line in proposed_lines
        if _is_preservable_comment_line(path, line)
    )
    deficits = Counter({
        line: count - proposed_counts.get(line, 0)
        for line, count in original_counts.items()
        if count > proposed_counts.get(line, 0)
    })
    if not deficits:
        return proposed, 0

    matcher = difflib.SequenceMatcher(
        a=original_lines,
        b=proposed_lines,
        autojunk=False,
    )
    repaired: list[str] = []
    restored = 0

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in {"replace", "delete"}:
            missing_here: list[str] = []
            for line in original_lines[i1:i2]:
                if deficits.get(line, 0) <= 0:
                    continue
                if not _is_preservable_comment_line(path, line):
                    continue
                missing_here.append(line)
                deficits[line] -= 1
                restored += 1

            if missing_here:
                repaired.extend(missing_here)
                # 기존 힌트/설명 블록을 코드로 치환한 경우, 주석 바로 아래에
                # 새 코드가 오도록 한 줄만 분리해 가독성을 유지합니다.
                if j1 < j2 and proposed_lines[j1].strip():
                    repaired.append("")

        if tag in {"equal", "replace", "insert"}:
            repaired.extend(proposed_lines[j1:j2])

    # 정상적인 diff에서는 모든 deficit이 위에서 복원됩니다. 방어적으로 남은
    # 주석이 있으면 파일 끝에 유실시키지 않고 보존합니다.
    leftovers: list[str] = []
    for line, count in deficits.items():
        if count > 0:
            leftovers.extend([line] * count)
            restored += count
    if leftovers:
        if repaired and repaired[-1].strip():
            repaired.append("")
        repaired.extend(leftovers)

    newline = "\r\n" if "\r\n" in proposed or "\r\n" in original else "\n"
    result = newline.join(repaired)
    if proposed.endswith(("\n", "\r")):
        result += newline
    return result, restored


def _normalize_project_analysis(project_root: str, summary, scan) -> dict:
    project_name = ""
    if isinstance(summary, dict):
        project_name = str(
            summary.get("project_name")
            or summary.get("name")
            or ""
        )

    if not project_name:
        project_name = Path(project_root).name

    scan_dict = scan if isinstance(scan, dict) else {"result": scan}
    summary_dict = summary if isinstance(summary, dict) else {"summary": summary}

    summary_text = ""
    for source in (scan_dict, summary_dict):
        for key in ("summary", "description", "overview"):
            value = source.get(key)
            if isinstance(value, str) and value.strip():
                summary_text = value.strip()
                break
        if summary_text:
            break

    tech_stack = (
        scan_dict.get("tech_stack")
        or scan_dict.get("technologies")
        or summary_dict.get("tech_stack")
        or []
    )

    entry_points = (
        scan_dict.get("entry_points")
        or scan_dict.get("entrypoints")
        or scan_dict.get("entry_files")
        or []
    )

    major_files = (
        scan_dict.get("major_files")
        or scan_dict.get("important_files")
        or scan_dict.get("files")
        or []
    )

    mcp_tools = (
        scan_dict.get("mcp_tools")
        or scan_dict.get("tools")
        or scan_dict.get("mcp")
        or []
    )

    structure = (
        scan_dict.get("structure")
        or scan_dict.get("tree")
        or {}
    )

    return {
        "project_name": project_name,
        "summary": summary_text,
        "tech_stack": _as_list(tech_stack),
        "entry_points": _as_list(entry_points),
        "major_files": _as_list(major_files)[:100],
        "mcp_tools": _as_list(mcp_tools),
        "structure": structure if isinstance(structure, dict) else {"value": structure},
        "raw_analysis": {
            "analysis_mode": "SOURCE_ONLY",
            "llm_called": False,
            "model_references": _as_list(summary_dict.get("model_references") or []),
            "summary": summary,
            "scan": scan,
        },
    }


router = APIRouter()

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []
    provider: str | None = None
    project_root: str = ""
    attachment_ids: list[str] = []
    attachment_memory: str = ""

class AttachmentRequirementsSummaryRequest(BaseModel):
    attachment_ids: list[str] = []
    attachment_memory: str = ""
    provider: str | None = None
    project_root: str = ""

class CodexStartRequest(BaseModel):
    root: str = ""


class CodexThreadRequest(BaseModel):
    root: str
    model: str = ""
    effort: str = ""


class CodexResumeThreadRequest(BaseModel):
    thread_id: str
    root: str = ""


class CodexTurnRequest(BaseModel):
    thread_id: str
    root: str
    text: str
    model: str = ""
    effort: str = ""
    attachment_ids: list[str] = []


class CodexInterruptRequest(BaseModel):
    thread_id: str
    turn_id: str


class CodexApprovalRequest(BaseModel):
    request_id: str
    decision: str
    payload: dict = {}


class FileRequest(BaseModel):
    path: str

class FileWriteRequest(BaseModel):
    path: str
    content: str
    expected_mtime_ns: int | None = None
    expected_sha256: str | None = None
    force: bool = False

class FileHashStateRequest(BaseModel):
    root: str
    relative_paths: list[str] = []

class CommandRequest(BaseModel):
    command: str
    cwd: str

class SearchRequest(BaseModel):
    query: str

class ToolAnalyzeRequest(BaseModel):
    name: str
    description: str = ""

class PlanRequest(BaseModel):
    requirements: str
    provider: str | None = None

class MCPDiscoverRequest(BaseModel):
    endpoint: str

class MCPServerCreate(BaseModel):
    name: str
    endpoint: str
    trust_level: str = "UNTRUSTED"
    allow_read_without_prompt: bool = False
    allow_write_without_prompt: bool = False

class WorkflowStartRequest(BaseModel):
    project_root: str
    request: str
    target_files: list[str] = []
    test_command: str = "python -m compileall ."
    provider: str | None = None
    thread_id: str | None = None
    design_bundle: dict = {}
    # v5.371: failed Agent builds can restart from a persisted checkpoint
    # instead of replaying requirement/design nodes from START.
    resume_mode: bool = False
    resume_from_node: str = ""
    resume_run_id: str = ""


class WorkflowRedevelopRequest(BaseModel):
    project_root: str
    request: str = ""
    test_command: str = "python -m compileall ."
    provider: str | None = None
    agent_name: str = ""

class WorkflowResumeRequest(BaseModel):
    thread_id: str
    decision: str


class AgentDesignCheckpointRequest(BaseModel):
    project_root: str
    snapshot: dict = {}


class PresentationExportRequest(BaseModel):
    scope: str = "ALL"
    deck_type: str = "AGENT"
    project_name: str = "AgentStudio Project"
    project_root: str = ""
    generated_at: str = ""
    workflow_request: str = ""
    workflow_definition: dict = {}
    report: dict = {}
    coding_style_report: dict = {}
    llm_usage_summary: dict = {}
    db_erd: dict = {}
    ui_layout: dict = {}

class FolderCreateRequest(BaseModel):
    root: str
    relative_path: str


class PathRenameRequest(BaseModel):
    root: str
    relative_path: str
    new_name: str


class FilesDeleteRequest(BaseModel):
    root: str
    relative_paths: list[str]


class CodeEditRequest(BaseModel):
    root: str
    path: str
    instruction: str
    content: str = ""
    active_cell_index: int | None = None
    attachment_ids: list[str] = []


class ProjectCodeEditRequest(BaseModel):
    root: str
    instruction: str
    max_context_files: int = 10
    attachment_ids: list[str] = []


class CodingStyleAnalyzeRequest(BaseModel):
    text: str


class CodingStyleValidateRequest(BaseModel):
    code: str
    request: str = ""
    path: str = ""
    project_scope: bool = False


class CodingRuleGovernanceRequest(BaseModel):
    candidates: list[dict]


class AgentFactoryPlanRequest(BaseModel):
    request: str


class WorkflowPreviewRequest(BaseModel):
    request: str
    project_root: str = ""
    provider: str | None = None
    interview_messages: list[dict] = []
    confirmed_requirements: dict = {}
    attachment_ids: list[str] = []
    attachment_memory: str = ""
    previous_design: dict = {}
    # v5.393: user-selectable recovery path. When True, do not call an AI
    # Provider; build a deterministic Workflow + DB Module Registry plan.
    safe_mode: bool = False







class DatabaseDesignPreviewRequest(BaseModel):
    request: str
    confirmed_requirements: dict = {}

class GpuRecommendationRequest(BaseModel):
    request: str = ""
    confirmed_requirements: dict = {}
    ai_mode: str = ""
    phase: str = ""


class DatabaseDesignFinalizeRequest(BaseModel):
    database_plan: dict = {}


class DatabaseErdRequest(BaseModel):
    project_root: str = ""
    database_plan: dict = {}
    project_profile: dict = {}
    workflow_request: str = ""
    deck_type: str = "AGENT"


class ProjectAnalyzeRequest(BaseModel):
    project_root: str
    request: str = ""

class MemoryAddRequest(BaseModel):
    content: str
    memory_type: str = "PROJECT"
    key: str = ""
    project_id: int | None = None
    metadata: dict = {}

class MemorySearchRequest(BaseModel):
    query: str
    project_id: int | None = None
    memory_type: str | None = None
    limit: int = 8


class FolderPickerRequest(BaseModel):
    title: str = "폴더를 선택하세요."
    initial_path: str = ""


class AiAttachmentPickRequest(BaseModel):
    title: str = "AI가 분석할 파일을 선택하세요."
    initial_path: str = ""
    project_root: str = ""
    max_files: int = 12


class AiAttachmentReleaseRequest(BaseModel):
    attachment_ids: list[str] = []


class AiAttachmentAnalyzeRequest(BaseModel):
    attachment_ids: list[str] = []
    purpose: str = "AI 참고 파일 분석 준비"

class OllamaInstallRequest(BaseModel):
    common_models_root: str = ""

class SettingsUpdateRequest(BaseModel):
    values: dict

class MachineNameUpdateRequest(BaseModel):
    pc_name: str


class PgvectorInstallRequest(BaseModel):
    postgresql_root: str = ""
    admin_user: str = ""
    admin_password: str = ""

class PostgreSqlAdminConnectionTestRequest(BaseModel):
    admin_user: str = "postgres"
    admin_password: str = ""

class DatabaseUrlConnectionTestRequest(BaseModel):
    database_url: str = ""

class DatabaseEnvSettingsRequest(BaseModel):
    database_url: str = ""
    langgraph_database_url: str = ""
    postgresql_root: str = ""

class DatabaseProvisionRequest(BaseModel):
    postgresql_root: str = ""
    admin_user: str = "postgres"
    admin_password: str = ""
    app_user: str = "theanova_agentstudio_app"
    app_password: str = ""
    database_name: str = "theanova_agentstudio"

class DatabaseRuntimeActivateRequest(BaseModel):
    provider: str = "local"
    supabase_database_url: str = ""
    supabase_langgraph_database_url: str = ""
    supabase_db_schema: str = "theanova_agentstudio"
    initialize_schema: bool = True


class SupabaseRuntimeSettingsSaveRequest(BaseModel):
    database_url: str = ""
    langgraph_database_url: str = ""
    schema: str = "theanova_agentstudio"


class SupabaseSchemaInitializeRequest(BaseModel):
    database_url: str = ""
    langgraph_database_url: str = ""
    schema: str = "theanova_agentstudio"

class AgentDesignProjectSaveRequest(BaseModel):
    id: int | None = None
    name: str = ""
    project_root: str = ""
    status: str = "INTERVIEWING"
    progress: int = 0
    current_stage: str = "REQUIREMENTS"
    current_question: str = ""
    langgraph_thread_id: str = ""
    snapshot: dict = {}
    feature_registry: list = []
    create_version: bool = False
    version_label: str = ""


class AgentDesignProjectVersionRequest(BaseModel):
    label: str = ""
    snapshot: dict = {}
    feature_registry: list = []


class UIThemeImportUrlRequest(BaseModel):
    name: str = ""
    url: str = ""
    scope: str = "GLOBAL"


class UIThemeImportImageRequest(BaseModel):
    name: str = ""
    file_name: str = ""
    tokens: dict = {}
    component_rules: dict = {}
    layout_rules: dict = {}
    preview_colors: list[str] = []
    scope: str = "GLOBAL"


class UIThemeImportImageReference(BaseModel):
    file_name: str = ""
    reference_role: str = "default"
    tokens: dict = {}
    component_rules: dict = {}
    layout_rules: dict = {}
    preview_colors: list[str] = []


class UIThemeImportCombinedRequest(BaseModel):
    name: str = ""
    url: str = ""
    images: list[UIThemeImportImageReference] = []
    scope: str = "GLOBAL"


class RequirementSaveRequest(BaseModel):
    project_id: int | None = None
    key: str
    value: str
    confirmed: bool = True


class ConversationSaveRequest(BaseModel):
    project_id: int | None = None
    thread_id: str = "default"
    role: str
    content: str


class SqlWorkspaceProfileRequest(BaseModel):
    root: str
    connection_id: str = ""
    name: str = ""
    db_type: str = "postgresql"
    host: str = "127.0.0.1"
    port: int = 5432
    database: str = ""
    schema_name: str = ""
    username: str = ""
    password: str = ""
    driver: str = "ODBC Driver 18 for SQL Server"
    service_name: str = ""
    project_id: str = ""
    service_account_json: str = ""
    dashboard_url: str = ""
    ssl_mode: str = ""
    trust_server_certificate: bool = True




class SqlWorkspaceConnectionFileImportRequest(BaseModel):
    root: str = ""
    db_type: str
    initial_path: str = ""

class SqlWorkspaceConnectionRequest(BaseModel):
    root: str
    connection_id: str = ""


class ChromiumBrowserNavigateRequest(BaseModel):
    url: str
    viewport_width: int = 1280
    viewport_height: int = 720
    force_restart: bool = False


class ChromiumBrowserActionRequest(BaseModel):
    action: str
    x: float = 0
    y: float = 0
    delta_x: float = 0
    delta_y: float = 0
    button: str = "left"
    click_count: int = 1
    key: str = ""
    text: str = ""
    viewport_width: int = 1280
    viewport_height: int = 720


class SqlWorkspaceRenameRequest(BaseModel):
    root: str
    connection_id: str
    name: str


class SqlWorkspaceExecuteRequest(BaseModel):
    root: str
    sql: str
    max_rows: int = 1000


class SqlWorkspaceObjectOpenRequest(BaseModel):
    root: str
    schema: str
    category: str
    name: str


class SqlWorkspaceSchemaDiagramRequest(BaseModel):
    root: str
    schema: str


class SqlWorkspaceTableDmlScriptRequest(BaseModel):
    root: str
    schema: str
    name: str
    action: str


class SqlWorkspaceDatabaseAdminScriptRequest(BaseModel):
    root: str
    action: str
    value: str = ""


class SqlWorkspaceRedisScriptRequest(BaseModel):
    root: str
    action: str
    key: str = ""
    key_type: str = ""
    prefix: str = ""
    node_kind: str = "key"


class SqlWorkspaceFirestoreScriptRequest(BaseModel):
    root: str
    action: str
    path: str = ""
    node_kind: str = "collection"


class UsageSaveRequest(BaseModel):
    project_id: int | None = None
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float = 0.0


class ExternalProjectAnalyzeRequest(BaseModel):
    project_root: str
    request: str = "프로젝트 구조와 주요 파일을 분석해주세요."


class ProjectFavoriteRequest(BaseModel):
    is_favorite: bool


class AgentProjectCreateRequest(BaseModel):
    name: str
    project_root: str
    cache_path: str = ""
    temp_path: str = ""
    output_path: str = ""
    venv_path: str = ""
    models_path: str = ""
    force_recreate: bool = False
    database_plan: dict = {}




_TERMINAL_RUNTIME_SESSIONS: dict[str, dict] = {}


def _terminal_runtime_key(root: str, terminal_id: str | None = None) -> str:
    return f"{root.lower()}::{terminal_id or 'default'}"


def _terminal_runtime_env(project_root):
    import os
    from pathlib import Path

    env = os.environ.copy()
    venv_dir = Path(project_root) / ".venv"
    scripts_dir = venv_dir / "Scripts"

    if scripts_dir.exists():
        env["VIRTUAL_ENV"] = str(venv_dir)
        env["PATH"] = str(scripts_dir) + os.pathsep + env.get("PATH", "")
        env.pop("PYTHONHOME", None)

    return env


@router.get("/system/db-write-policy")
async def db_write_policy():
    return {
        "ok": True,
        "policy": "FASTAPI_ONLY",
        "flow": [
            "Frontend / Agent / Tool",
            "FastAPI endpoint",
            "Service",
            "DatabaseGateway",
            "SQLAlchemy AsyncSession",
            "PostgreSQL",
        ],
        "direct_client_db_access": False,
    }


@router.post("/system/pick-folder")
async def system_pick_folder(req: FolderPickerRequest):
    return await pick_folder(
        title=req.title,
        initial_path=req.initial_path,
    )

@router.post("/ai/attachments/pick")
async def ai_attachments_pick(req: AiAttachmentPickRequest):
    selection = await pick_files(
        title=req.title,
        initial_path=req.initial_path,
        max_files=req.max_files,
    )
    if not selection.get("ok") or selection.get("cancelled"):
        return {**selection, "attachments": []}

    attachments = register_selected_files(
        selection.get("paths") or [],
        project_root=req.project_root,
    )
    accepted = [row for row in attachments if row.get("ok") is not False]
    rejected = [row for row in attachments if row.get("ok") is False]
    return {
        "ok": True,
        "cancelled": False,
        "attachments": accepted,
        "rejected": rejected,
        "message": f"AI 분석 파일 {len(accepted)}개를 등록했습니다." + (f" 제한으로 {len(rejected)}개 제외." if rejected else ""),
    }


@router.post("/ai/attachments/analyze")
async def ai_attachments_analyze(req: AiAttachmentAnalyzeRequest):
    requested = [str(value).strip() for value in req.attachment_ids if str(value or '').strip()]
    if not requested:
        raise HTTPException(status_code=400, detail="분석할 첨부 파일이 없습니다.")

    metadata_by_id = {
        str(row.get("attachment_id") or ""): row
        for row in attachment_metadata(requested)
    }

    async def runner(job):
        rows = []
        for attachment_id in requested:
            meta = metadata_by_id.get(attachment_id) or {}
            rows.append({
                "attachment_id": attachment_id,
                "name": str(meta.get("name") or f"첨부 {attachment_id[:8]}"),
                "size": int(meta.get("size") or 0),
                "status": "QUEUED",
                "progress": 0,
                "stage": "대기",
                "message": "분석 대기 중",
            })

        async def publish(index: int, *, progress: int, status: str, stage: str, message: str):
            row = rows[index]
            row.update({
                "progress": max(0, min(100, int(progress))),
                "status": status,
                "stage": stage,
                "message": message,
            })
            overall = int(round(sum(int(item.get("progress") or 0) for item in rows) / max(1, len(rows))))
            completed = sum(1 for item in rows if item.get("status") in {"SUCCESS", "FAILED"})
            await job_manager.update(
                job,
                status="RUNNING",
                progress=overall,
                message=f"{row['name']}: {message}",
                result={
                    "analysis": {
                        "purpose": req.purpose,
                        "files": [dict(item) for item in rows],
                        "overall_progress": overall,
                        "completed_files": completed,
                        "total_files": len(rows),
                    }
                },
            )

        warnings = []
        for index, attachment_id in enumerate(requested):
            row = rows[index]
            if attachment_id not in metadata_by_id:
                await publish(
                    index,
                    progress=100,
                    status="FAILED",
                    stage="실패",
                    message="첨부 ID가 만료되었거나 존재하지 않습니다.",
                )
                warnings.append(f"{row['name']}: 첨부 ID가 만료되었거나 존재하지 않습니다.")
                continue

            await publish(index, progress=15, status="RUNNING", stage="파일 확인", message="파일 상태를 확인하고 있습니다.")
            await asyncio.sleep(0)
            await publish(index, progress=45, status="RUNNING", stage="텍스트 추출", message="분석 가능한 텍스트를 추출하고 있습니다.")

            try:
                prepared = await asyncio.to_thread(prepare_attachment, attachment_id)
                row["content_type"] = str(prepared.get("content_type") or "")
                row["content_chars"] = int(prepared.get("content_chars") or 0)
                row["cached"] = bool(prepared.get("cached"))
                await publish(index, progress=85, status="RUNNING", stage="Context 준비", message="AI Context를 준비하고 있습니다.")
                await asyncio.sleep(0)
                await publish(index, progress=100, status="SUCCESS", stage="준비 완료", message="AI 분석 준비가 완료되었습니다.")
            except Exception as exc:
                message = str(exc) or type(exc).__name__
                await publish(index, progress=100, status="FAILED", stage="실패", message=message)
                warnings.append(f"{row['name']}: {message}")

        successful = sum(1 for item in rows if item.get("status") == "SUCCESS")
        failed = sum(1 for item in rows if item.get("status") == "FAILED")
        return {
            "ok": successful > 0 and failed == 0,
            "message": (
                f"참고 파일 {successful}개 분석 준비를 완료했습니다."
                if not failed
                else f"참고 파일 {successful}개 준비 완료, {failed}개 실패했습니다."
            ),
            "analysis": {
                "purpose": req.purpose,
                "files": rows,
                "overall_progress": 100,
                "completed_files": len(rows),
                "total_files": len(rows),
                "successful_files": successful,
                "failed_files": failed,
            },
            "warnings": warnings,
        }

    job = job_manager.create("AI_ATTACHMENT_ANALYSIS", runner)
    return vars(job)


@router.post("/ai/attachments/release")
async def ai_attachments_release(req: AiAttachmentReleaseRequest):
    return {"ok": True, "removed": release_attachments(req.attachment_ids)}


@router.get("/ai/attachments")
async def ai_attachments(attachment_ids: str = Query(default="")):
    ids = [value.strip() for value in attachment_ids.split(",") if value.strip()]
    return {"attachments": attachment_metadata(ids)}


@router.get("/system/ports/recommend")
async def system_port_recommendations(
    request: Request,
    backend_port: int = Query(default=8000, ge=1024, le=65535),
    frontend_port: int = Query(default=5173, ge=1024, le=65535),
    current_frontend_port: int | None = Query(default=None, ge=1024, le=65535),
):
    current_backend_port = request.url.port or 8000
    return recommend_agentstudio_ports(
        backend_port,
        frontend_port,
        current_backend_port=current_backend_port,
        current_frontend_port=current_frontend_port,
    )

@router.get("/settings/default-paths")
async def get_default_paths():
    s = get_settings()
    return {
        "project_root": s.default_project_root,
        "cache_root": s.default_cache_root,
        "temp_root": s.default_temp_root,
        "output_root": s.default_output_root,
        "common_models_root": s.common_models_root,
    }

@router.get("/settings")
async def get_settings_form():
    return await get_editable_settings()

@router.post("/settings")
async def save_settings_form(req: SettingsUpdateRequest):
    try:
        result = await update_settings(req.values)
        # v5.330: Codex master switch is operational, not cosmetic. Turning it
        # off immediately terminates a running app-server process and clears the
        # right-panel runtime without touching the official Codex OAuth store.
        if "CODEX_ENABLED" in req.values:
            raw = str(req.values.get("CODEX_ENABLED") or "").strip().lower()
            if raw in {"0", "false", "no", "off"}:
                await asyncio.to_thread(codex_app_server_manager.shutdown_sync)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

@router.post("/settings/machine-name")
async def save_machine_name(req: MachineNameUpdateRequest):
    try:
        return await rename_current_machine(req.pc_name)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

@router.post("/settings/migrate-to-db")
async def settings_migrate_to_db():
    try:
        result = await migrate_env_settings_to_db()
        result["message"] = (
            f"공용 DB 동기화 완료: 신규 {result.get('migrated', 0)}개 / "
            f"오프라인 수정 반영 {result.get('updated', 0)}개"
        )
        return result
    except Exception as exc:
        return {
            "ok": False,
            "database_connected": False,
            "migrated": 0,
            "updated": 0,
            "message": f"공용 DB에 연결할 수 없어 동기화를 보류했습니다: {exc}",
        }

@router.post("/settings/database-env")
async def save_database_environment(req: DatabaseEnvSettingsRequest):
    """DB 연결 bootstrap 값은 PostgreSQL이 아니라 backend/.env에만 저장합니다."""
    try:
        return await save_database_env_settings({
            "DATABASE_URL": req.database_url,
            "LANGGRAPH_DATABASE_URL": req.langgraph_database_url,
            "POSTGRESQL18_ROOT": req.postgresql_root,
        })
    except (ValueError, OSError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/settings/database-runtime")
async def settings_database_runtime_status():
    return await get_database_runtime_status()


@router.post("/settings/database-runtime/activate")
async def settings_database_runtime_activate(req: DatabaseRuntimeActivateRequest):
    try:
        return await activate_database_provider(
            req.provider,
            supabase_database_url=req.supabase_database_url,
            supabase_langgraph_database_url=req.supabase_langgraph_database_url,
            supabase_db_schema=req.supabase_db_schema,
            initialize_schema=req.initialize_schema,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Runtime DB 전환 실패: {exc}") from exc


@router.post("/settings/database-runtime/supabase/save")
async def settings_supabase_runtime_save(req: SupabaseRuntimeSettingsSaveRequest):
    try:
        return await save_supabase_runtime_settings(
            req.database_url,
            req.langgraph_database_url,
            req.schema,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"Supabase 정보 저장 실패: {exc}") from exc


@router.post("/settings/database-runtime/supabase/initialize-schema")
async def settings_supabase_initialize_schema(req: SupabaseSchemaInitializeRequest):
    try:
        return await initialize_supabase_schema(req.database_url, req.langgraph_database_url, req.schema)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Supabase 스키마 생성 실패: {exc}") from exc


@router.get("/settings/database-runtime/supabase/schema-script")
async def settings_supabase_schema_script():
    path = get_supabase_schema_script_path()
    if not path.exists():
        raise HTTPException(status_code=404, detail="Supabase 전체 스키마 SQL 파일을 찾을 수 없습니다.")
    return FileResponse(path, media_type="application/sql", filename=path.name)


@router.post("/settings/test/postgresql")
async def settings_test_postgresql(req: DatabaseUrlConnectionTestRequest | None = None):
    return await test_postgresql(req.database_url if req else None)

@router.post("/settings/test/postgresql-admin")
async def settings_test_postgresql_admin(req: PostgreSqlAdminConnectionTestRequest):
    return await test_postgresql_admin(
        admin_user=req.admin_user,
        admin_password=req.admin_password,
    )

@router.post("/settings/test/pgvector")
async def settings_test_pgvector(req: DatabaseUrlConnectionTestRequest | None = None):
    return await test_pgvector(req.database_url if req else None)

@router.post("/settings/test/ollama")
async def settings_test_ollama():
    return await test_ollama()

@router.post("/settings/test/openai")
async def settings_test_openai():
    return await test_openai()


@router.get("/llm/runtime-status")
async def llm_runtime_status():
    return await get_llm_runtime_status()

@router.get("/llm/catalog")
async def llm_catalog():
    return build_llm_catalog()

@router.get("/weather/config")
async def weather_configuration():
    return weather_config()

@router.get("/weather/dashboard")
async def weather_dashboard(
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    force_refresh: bool = Query(default=False),
):
    return await build_weather_dashboard(
        latitude=latitude,
        longitude=longitude,
        force_refresh=force_refresh,
    )


@router.get("/llm/history")
async def llm_history(
    days: int = Query(default=10, ge=1, le=10),
    project_root: str = Query(default=""),
    task: str = Query(default=""),
    limit: int = Query(default=300, ge=1, le=1000),
):
    return read_llm_history(
        days=days,
        project_root=project_root,
        task=task,
        limit=limit,
    )

@router.post("/settings/test/tavily")
async def settings_test_tavily():
    return await test_tavily()

@router.post("/settings/test/langsmith")
async def settings_test_langsmith():
    return await test_langsmith()

@router.post("/settings/test-all")
async def settings_test_all():
    return await test_all()


@router.get("/settings/pgvector/windows18/info")
async def pgvector_windows18_info(postgresql_root: str = ''):
    root = detect_postgresql18_root(postgresql_root)
    try:
        release = await latest_pg18_windows_release()
        error = ""
    except Exception as e:
        release = None
        error = str(e)
    return {
        "postgresql_root": str(root) if root else "",
        "release": release,
        "error": error,
    }


@router.post("/settings/pgvector/windows18/validate-path")
async def pgvector_validate_postgresql_path(req: PgvectorInstallRequest):
    return validate_postgresql18_root(req.postgresql_root)

@router.post("/settings/pgvector/windows18/install")
async def pgvector_windows18_install(req: PgvectorInstallRequest):
    existing = job_manager.active_job("PGVECTOR_INSTALL")
    if existing:
        return vars(existing)

    async def runner(job):
        async def progress(value: int, message: str):
            await job_manager.update(
                job,
                status="RUNNING",
                progress=value,
                message=message,
            )

        return await install_pgvector_windows18(
            progress_cb=progress,
            postgresql_root=req.postgresql_root or None,
            admin_user=req.admin_user,
            admin_password=req.admin_password,
            database_url=get_settings().database_url,
        )

    job = job_manager.create("PGVECTOR_INSTALL", runner)
    return vars(job)

@router.get("/settings/gpu/runtime/status")
async def gpu_runtime_status():
    return await asyncio.to_thread(get_gpu_runtime_status)


@router.post("/settings/gpu/runtime/start")
async def gpu_runtime_start():
    result = await asyncio.to_thread(set_gpu_runtime_enabled, True)
    if not result.get("ok"):
        return result
    ollama = await restart_managed_ollama_for_gpu_mode()
    return {**result, "ollama": ollama}


@router.post("/settings/gpu/runtime/stop")
async def gpu_runtime_stop():
    result = await asyncio.to_thread(set_gpu_runtime_enabled, False)
    ollama = await restart_managed_ollama_for_gpu_mode()
    return {**result, "ollama": ollama}


@router.post("/settings/gpu/recommendation")
async def gpu_runtime_recommendation(req: GpuRecommendationRequest):
    return await asyncio.to_thread(
        gpu_recommendation,
        request=req.request,
        confirmed_requirements=req.confirmed_requirements,
        ai_mode=req.ai_mode,
        phase=req.phase,
    )


@router.get("/settings/ollama/runtime/status")
async def ollama_runtime_status():
    return await get_ollama_runtime_status()


@router.post("/settings/ollama/runtime/start")
async def ollama_runtime_start():
    return await start_ollama_server()


@router.post("/settings/ollama/runtime/stop")
async def ollama_runtime_stop():
    return await stop_ollama_server()


@router.post("/settings/ollama/windows/install")
async def ollama_windows_install(req: OllamaInstallRequest):
    existing = job_manager.active_job("OLLAMA_INSTALL")
    if existing:
        return vars(existing)

    async def runner(job):
        async def progress(value: int, message: str):
            await job_manager.update(
                job,
                status="RUNNING",
                progress=value,
                message=message,
            )

        return await install_ollama_windows(
            progress_cb=progress,
            common_models_root=req.common_models_root or get_settings().common_models_root,
        )

    job = job_manager.create("OLLAMA_INSTALL", runner)
    return vars(job)

@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    job = job_manager.jobs.get(job_id)
    if not job:
        return {"ok": False, "error": "Job not found"}
    return vars(job)


@router.get("/workflow/runtime-status")
async def workflow_runtime_status(project_root: str = "", job_id: str = ""):
    """Return backend truth for Agent Factory execution lifecycle.

    v5.393 keeps UI stop controls tied to the actual Background Job/task and
    validation subprocesses instead of a stale browser-side boolean.
    """
    job = job_manager.jobs.get(str(job_id or "")) if job_id else None
    task = job_manager.tasks.get(str(job_id or "")) if job_id else None
    command_processes = await asyncio.to_thread(active_command_processes, project_root)
    job_status = str(job.status if job else "NOT_FOUND").upper()
    job_active = bool(job and job_status in {"QUEUED", "RUNNING", "WAITING_USER"})
    task_alive = bool(task and not task.done())
    process_active = any(bool(item.get("running")) for item in command_processes)
    return {
        "ok": True,
        "job_id": str(job_id or ""),
        "job_status": job_status,
        "job_active": job_active,
        "task_alive": task_alive,
        "validation_process_count": sum(1 for item in command_processes if item.get("running")),
        "validation_processes": command_processes,
        "execution_active": bool(job_active or task_alive or process_active),
    }


@router.post("/settings/database/provision-agentstudio")
async def provision_agentstudio_db(req: DatabaseProvisionRequest):
    try:
        result = await provision_agentstudio_database(
            postgresql_root=req.postgresql_root,
            admin_user=req.admin_user,
            admin_password=req.admin_password,
            app_user=req.app_user,
            app_password=req.app_password,
            database_name=req.database_name,
        )

        await save_database_env_settings({
            "DATABASE_URL": result["database_url"],
            "LANGGRAPH_DATABASE_URL": result["langgraph_database_url"],
            "POSTGRESQL18_ROOT": req.postgresql_root,
        })

        return result

    except Exception as e:
        return {
            "ok": False,
            "message": str(e),
        }



def _design_project_payload(row: AgentDesignProject, *, include_snapshot: bool = False) -> dict:
    payload = {
        "id": row.id,
        "name": row.name,
        "project_root": row.project_root,
        "status": row.status,
        "progress": row.progress,
        "current_stage": row.current_stage,
        "current_question": row.current_question,
        "langgraph_thread_id": row.langgraph_thread_id,
        "feature_registry": row.feature_registry or [],
        "version_no": row.version_no,
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
        "last_opened_at": row.last_opened_at.isoformat() if row.last_opened_at else "",
    }
    if include_snapshot:
        payload["snapshot"] = row.snapshot or {}
    return payload



async def _ensure_ui_theme_storage() -> None:
    """Self-heal Theme storage on the currently active runtime DB.

    This also fixes installations that switched from the local bootstrap DB to an
    older Supabase schema before the ui_themes table was introduced.
    """
    try:
        await ensure_runtime_metadata_tables()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Theme 저장 테이블을 준비하지 못했습니다. SYSTEM_ADMIN에서 현재 DB 연결/스키마를 확인한 뒤 "
                f"Backend를 재시작하세요. 상세: {exc}"
            ),
        ) from exc


def _ui_theme_payload(row: UITheme) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "theme_type": row.theme_type,
        "source_type": row.source_type,
        "source_url": row.source_url,
        "source_label": row.source_label,
        "scope": row.scope,
        "tokens": row.tokens or {},
        "component_rules": row.component_rules or {},
        "layout_rules": row.layout_rules or {},
        "preview_colors": row.preview_colors or [],
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "updated_at": row.updated_at.isoformat() if row.updated_at else "",
    }


@router.get("/ui-themes/frontend-targets")
async def list_ui_theme_frontend_targets():
    targets = list_frontend_theme_targets()
    groups: dict[str, list[dict]] = {}
    for item in targets:
        groups.setdefault(str(item.get("group") or "기타"), []).append(item)
    return {"ok": True, "targets": targets, "groups": groups, "count": len(targets)}


@router.get("/ui-themes")
async def list_ui_themes():
    await _ensure_ui_theme_storage()
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(UITheme)
                .where(UITheme.pc_name == current_pc_name())
                .order_by(UITheme.updated_at.desc(), UITheme.id.desc())
            )
        ).scalars().all()
    return {"ok": True, "themes": [_ui_theme_payload(row) for row in rows]}


@router.post("/ui-themes/import")
async def import_ui_theme_from_sources(req: UIThemeImportCombinedRequest):
    """Import one Theme from an optional public URL and up to three screenshot analyses.

    Either source is sufficient. When both are provided, URL CSS semantics (including
    menu hover/active/submenu/user-menu states) and screenshot state references are merged before persistence.
    """
    await _ensure_ui_theme_storage()
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Theme 이름을 입력하세요.")
    url = (req.url or "").strip()
    images = list(req.images or [])
    if len(images) > 3:
        raise HTTPException(status_code=400, detail="화면 캡처 이미지는 최대 3개까지 사용할 수 있습니다.")
    if not url and not images:
        raise HTTPException(status_code=400, detail="웹사이트 URL 또는 화면 캡처 이미지를 하나 이상 입력하세요.")

    analyses: list[dict] = []
    source_url = ""
    warnings: list[str] = []
    url_applied = False
    source_meta: dict = {"images": [], "url": bool(url), "content_copied": False}
    if url:
        try:
            url_analysis = await analyze_theme_from_url(url)
            analyses.append(url_analysis)
            url_applied = True
            source_url = str(url_analysis.get("source_url") or url).strip()
            source_meta["url_meta"] = url_analysis.get("source_meta") or {}
        except ValueError as exc:
            if not images:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            warnings.append(f"URL 분석 제외: {exc}")
        except Exception as exc:
            if not images:
                raise HTTPException(status_code=502, detail=f"웹사이트 Theme 분석 실패: {exc}") from exc
            warnings.append(f"URL 분석 제외: {exc}")

    for image in images:
        tokens = image.tokens or {}
        colors = tokens.get("colors") if isinstance(tokens, dict) else None
        if not isinstance(colors, dict) or not colors.get("primary") or not colors.get("background"):
            raise HTTPException(status_code=400, detail=f"'{image.file_name or '화면 캡처'}' 이미지의 Theme 색상 정보가 없습니다.")
        component_rules = image.component_rules or {}
        layout_rules = image.layout_rules or {}
        if not component_rules or not layout_rules:
            default_components, default_layout = build_rules(tokens)
            component_rules = component_rules or default_components
            layout_rules = layout_rules or default_layout
        analyses.append({
            "analysis_source": "IMAGE",
            "file_name": (image.file_name or "화면 캡처 이미지").strip(),
            "reference_role": (image.reference_role or "default").strip().lower(),
            "tokens": tokens,
            "component_rules": component_rules,
            "layout_rules": layout_rules,
            "preview_colors": image.preview_colors or [],
        })
        source_meta["images"].append({
            "file_name": (image.file_name or "화면 캡처 이미지").strip(),
            "reference_role": (image.reference_role or "default").strip().lower(),
        })

    if not analyses:
        raise HTTPException(status_code=400, detail="Theme으로 사용할 수 있는 참고 소스를 분석하지 못했습니다.")
    merged = merge_theme_analyses(analyses)
    source_type = "COMBINED" if url_applied and images else ("URL" if url_applied else "IMAGE")
    source_meta["warnings"] = warnings
    source_meta["analysis"] = (
        "URL HTML/CSS + screenshot design-token merge"
        if source_type == "COMBINED"
        else "HTML/CSS design-token extraction"
        if source_type == "URL"
        else "Screenshot design-token extraction"
    )
    now = datetime.utcnow()
    async with SessionLocal() as session:
        row = UITheme(
            pc_name=current_pc_name(),
            name=name,
            theme_type="IMPORTED",
            source_type=source_type,
            source_url=source_url,
            source_label=json.dumps(source_meta, ensure_ascii=False)[:1000],
            scope=(req.scope or "GLOBAL").strip().upper(),
            tokens=merged.get("tokens") or {},
            component_rules=merged.get("component_rules") or {},
            layout_rules=merged.get("layout_rules") or {},
            preview_colors=merged.get("preview_colors") or [],
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return {"ok": True, "theme": _ui_theme_payload(row), "sources": source_meta, "warnings": warnings}


@router.post("/ui-themes/import-url")
async def import_ui_theme_from_url(req: UIThemeImportUrlRequest):
    await _ensure_ui_theme_storage()
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Theme 이름을 입력하세요.")
    try:
        analysis = await analyze_theme_from_url(req.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"웹사이트 Theme 분석 실패: {exc}") from exc

    now = datetime.utcnow()
    async with SessionLocal() as session:
        row = UITheme(
            pc_name=current_pc_name(),
            name=name,
            theme_type="IMPORTED",
            source_type="URL",
            source_url=str(analysis.get("source_url") or req.url).strip(),
            source_label=json.dumps(analysis.get("source_meta") or {}, ensure_ascii=False),
            scope=(req.scope or "GLOBAL").strip().upper(),
            tokens=analysis.get("tokens") or {},
            component_rules=analysis.get("component_rules") or {},
            layout_rules=analysis.get("layout_rules") or {},
            preview_colors=analysis.get("preview_colors") or [],
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return {"ok": True, "theme": _ui_theme_payload(row)}


@router.post("/ui-themes/import-image")
async def import_ui_theme_from_image(req: UIThemeImportImageRequest):
    await _ensure_ui_theme_storage()
    name = (req.name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Theme 이름을 입력하세요.")
    tokens = req.tokens or {}
    colors = tokens.get("colors") if isinstance(tokens, dict) else None
    if not isinstance(colors, dict) or not colors.get("primary") or not colors.get("background"):
        raise HTTPException(status_code=400, detail="이미지에서 추출된 Theme 색상 정보가 없습니다.")
    component_rules = req.component_rules or {}
    layout_rules = req.layout_rules or {}
    if not component_rules or not layout_rules:
        default_components, default_layout = build_rules(tokens)
        component_rules = component_rules or default_components
        layout_rules = layout_rules or default_layout
    now = datetime.utcnow()
    async with SessionLocal() as session:
        row = UITheme(
            pc_name=current_pc_name(),
            name=name,
            theme_type="IMPORTED",
            source_type="IMAGE",
            source_url="",
            source_label=(req.file_name or "화면 캡처 이미지").strip(),
            scope=(req.scope or "GLOBAL").strip().upper(),
            tokens=tokens,
            component_rules=component_rules,
            layout_rules=layout_rules,
            preview_colors=req.preview_colors or [],
            created_at=now,
            updated_at=now,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return {"ok": True, "theme": _ui_theme_payload(row)}


@router.delete("/ui-themes/{theme_id}")
async def delete_ui_theme(theme_id: int):
    await _ensure_ui_theme_storage()
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(UITheme).where(
                    UITheme.id == theme_id,
                    UITheme.pc_name == current_pc_name(),
                )
            )
        ).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Theme을 찾을 수 없습니다.")
        await session.delete(row)
        await session.commit()
    return {"ok": True, "theme_id": theme_id}


@router.get("/agent-design-projects")
async def list_agent_design_projects():
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(AgentDesignProject)
                .where(
                    AgentDesignProject.pc_name == current_pc_name(),
                    AgentDesignProject.status != "ARCHIVED",
                )
                .order_by(AgentDesignProject.updated_at.desc(), AgentDesignProject.id.desc())
            )
        ).scalars().all()
    return {"ok": True, "projects": [_design_project_payload(row) for row in rows]}


@router.get("/agent-design-projects/{design_project_id}")
async def get_agent_design_project(design_project_id: int):
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(AgentDesignProject).where(
                    AgentDesignProject.id == design_project_id,
                    AgentDesignProject.pc_name == current_pc_name(),
                )
            )
        ).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Agent 설계 프로젝트를 찾을 수 없습니다.")
        row.last_opened_at = datetime.utcnow()
        row.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(row)
        versions = (
            await session.execute(
                select(AgentDesignProjectVersion)
                .where(AgentDesignProjectVersion.design_project_id == row.id)
                .order_by(AgentDesignProjectVersion.version_no.desc())
                .limit(20)
            )
        ).scalars().all()
    payload = _design_project_payload(row, include_snapshot=True)
    payload["versions"] = [
        {
            "id": version.id,
            "version_no": version.version_no,
            "label": version.label,
            "created_at": version.created_at.isoformat() if version.created_at else "",
        }
        for version in versions
    ]
    return {"ok": True, "project": payload}


@router.post("/agent-design-projects/save")
async def save_agent_design_project(req: AgentDesignProjectSaveRequest):
    now = datetime.utcnow()
    async with SessionLocal() as session:
        row = None
        if req.id is not None:
            row = (
                await session.execute(
                    select(AgentDesignProject).where(
                        AgentDesignProject.id == req.id,
                        AgentDesignProject.pc_name == current_pc_name(),
                    )
                )
            ).scalar_one_or_none()
        if row is None:
            row = AgentDesignProject(
                pc_name=current_pc_name(),
                name=(req.name or "새 Agent 설계").strip(),
                created_at=now,
                updated_at=now,
            )
            session.add(row)
            await session.flush()

        if req.create_version and (row.snapshot or row.feature_registry):
            next_version = int(row.version_no or 1) + 1
            session.add(AgentDesignProjectVersion(
                design_project_id=row.id,
                version_no=int(row.version_no or 1),
                label=(req.version_label or f"v{int(row.version_no or 1)} Snapshot").strip(),
                snapshot=row.snapshot or {},
                feature_registry=row.feature_registry or [],
                created_at=now,
            ))
            row.version_no = next_version

        row.name = (req.name or row.name or "새 Agent 설계").strip()
        row.project_root = (req.project_root or "").strip()
        row.status = (req.status or "INTERVIEWING").strip().upper()
        row.progress = max(0, min(100, int(req.progress or 0)))
        row.current_stage = (req.current_stage or "REQUIREMENTS").strip()
        row.current_question = req.current_question or ""
        row.langgraph_thread_id = req.langgraph_thread_id or row.langgraph_thread_id or f"agent_design_{row.id}"
        row.snapshot = req.snapshot or {}
        row.feature_registry = req.feature_registry or []
        row.updated_at = now
        row.last_opened_at = now
        await session.commit()
        await session.refresh(row)

    return {"ok": True, "project": _design_project_payload(row, include_snapshot=True)}


@router.post("/agent-design-projects/{design_project_id}/version")
async def snapshot_agent_design_project(design_project_id: int, req: AgentDesignProjectVersionRequest):
    now = datetime.utcnow()
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(AgentDesignProject).where(
                    AgentDesignProject.id == design_project_id,
                    AgentDesignProject.pc_name == current_pc_name(),
                )
            )
        ).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Agent 설계 프로젝트를 찾을 수 없습니다.")
        version_no = int(row.version_no or 1)
        version = AgentDesignProjectVersion(
            design_project_id=row.id,
            version_no=version_no,
            label=(req.label or f"v{version_no} Snapshot").strip(),
            snapshot=req.snapshot or row.snapshot or {},
            feature_registry=req.feature_registry or row.feature_registry or [],
            created_at=now,
        )
        session.add(version)
        row.version_no = version_no + 1
        row.updated_at = now
        await session.commit()
    return {"ok": True, "version_no": version_no, "label": version.label}


@router.post("/agent-design-projects/{design_project_id}/archive")
async def archive_agent_design_project(design_project_id: int):
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(AgentDesignProject).where(
                    AgentDesignProject.id == design_project_id,
                    AgentDesignProject.pc_name == current_pc_name(),
                )
            )
        ).scalar_one_or_none()
        if not row:
            raise HTTPException(status_code=404, detail="Agent 설계 프로젝트를 찾을 수 없습니다.")
        row.status = "ARCHIVED"
        row.updated_at = datetime.utcnow()
        await session.commit()
    return {"ok": True}


@router.post("/persistence/requirements")
async def save_requirement(req: RequirementSaveRequest):
    async with SessionLocal() as session:
        row = await DatabaseGateway.add_requirement(
            session,
            project_id=req.project_id,
            key=req.key,
            value=req.value,
            confirmed=req.confirmed,
        )
        await session.commit()
        await session.refresh(row)

    return {
        "ok": True,
        "id": row.id,
        "message": "요구사항이 FastAPI를 통해 DB에 저장되었습니다.",
    }


@router.post("/persistence/conversations")
async def save_conversation(req: ConversationSaveRequest):
    async with SessionLocal() as session:
        row = await DatabaseGateway.add_conversation(
            session,
            project_id=req.project_id,
            thread_id=req.thread_id,
            role=req.role,
            content=req.content,
        )
        await session.commit()
        await session.refresh(row)

    return {
        "ok": True,
        "id": row.id,
        "message": "대화 기록이 FastAPI를 통해 DB에 저장되었습니다.",
    }


@router.post("/persistence/usage")
async def save_usage(req: UsageSaveRequest):
    async with SessionLocal() as session:
        row = await DatabaseGateway.add_usage(
            session,
            project_id=req.project_id,
            provider=req.provider,
            model=req.model,
            input_tokens=req.input_tokens,
            output_tokens=req.output_tokens,
            estimated_cost_usd=req.estimated_cost_usd,
        )
        await session.commit()
        await session.refresh(row)

    return {
        "ok": True,
        "id": row.id,
        "message": "사용량 정보가 FastAPI를 통해 DB에 저장되었습니다.",
    }



@router.post("/projects/analyze-external")
async def analyze_external_project(req: ExternalProjectAnalyzeRequest):
    """
    DB 미등록 프로젝트 분석을 Background Job으로 실행합니다.
    Frontend는 /jobs/{job_id}를 polling하여 진행률을 표시합니다.
    """
    root = req.project_root.strip()
    if not root:
        return {
            "ok": False,
            "message": "프로젝트 경로를 입력하세요.",
        }

    # 사용자가 명시적으로 선택/입력한 프로젝트 폴더를
    # 현재 Backend 세션의 허용 루트로 등록합니다.
    try:
        root = register_runtime_project_root(root)
    except Exception as e:
        return {
            "ok": False,
            "message": f"프로젝트 경로 등록 실패: {e}",
        }

    async def runner(job):
        await job_manager.update(
            job,
            status="RUNNING",
            progress=5,
            message="프로젝트 경로를 확인하고 있습니다.",
        )

        await job_manager.update(
            job,
            status="RUNNING",
            progress=15,
            message="프로젝트 소스 파일을 스캔하고 있습니다.",
        )

        summary = await local_project_summary(
            root,
            req.request,
        )

        await job_manager.update(
            job,
            status="RUNNING",
            progress=40,
            message="소스 구조, 기술 스택, 실행 진입점을 분석하고 있습니다.",
        )

        scan = await scan_project(
            root,
        )

        await job_manager.update(
            job,
            status="RUNNING",
            progress=70,
            message="관련 소스와 모델 참고 정보를 정리하고 있습니다.",
        )

        normalized = _normalize_project_analysis(
            project_root=root,
            summary=summary,
            scan=scan,
        )

        await job_manager.update(
            job,
            status="RUNNING",
            progress=82,
            message="프로젝트 정보를 PostgreSQL에 저장하고 있습니다.",
        )

        await adopt_legacy_projects_for_current_pc()
        async with SessionLocal() as session:
            project = (
                await session.execute(
                    select(Project).where(Project.pc_name == current_pc_name(), Project.root_path == root)
                )
            ).scalar_one_or_none()

            created = False

            if not project:
                paths = resolve_project_paths(
                    project_root=root,
                    create=False,
                )

                project = await DatabaseGateway.create_project(
                    session,
                    name=normalized["project_name"],
                    root_path=paths["project_root"],
                    cache_path=paths["cache_path"],
                    temp_path=paths["temp_path"],
                    output_path=paths["output_path"],
                    venv_path=paths["venv_path"],
                    models_path=paths["models_path"],
                    description=normalized["summary"],
                )
                await session.flush()
                created = True

            await job_manager.update(
                job,
                status="RUNNING",
                progress=90,
                message="프로젝트 분석 정보를 DB에 저장하고 있습니다.",
            )

            await DatabaseGateway.touch_project_opened(session, project)

            analysis_row = await DatabaseGateway.upsert_project_analysis(
                session,
                project_id=project.id,
                project_root=root,
                project_name=normalized["project_name"],
                summary=normalized["summary"],
                tech_stack=normalized["tech_stack"],
                entry_points=normalized["entry_points"],
                major_files=normalized["major_files"],
                mcp_tools=normalized["mcp_tools"],
                structure=normalized["structure"],
                raw_analysis=normalized["raw_analysis"],
            )

            await session.commit()
            await session.refresh(project)
            await session.refresh(analysis_row)

        await job_manager.update(
            job,
            status="RUNNING",
            progress=98,
            message="저장 결과를 확인하고 작업공간을 준비하고 있습니다.",
        )

        return {
            "ok": True,
            "registered": True,
            "created": created,
            "project_id": project.id,
            "analysis_id": analysis_row.id,
            "project_root": project.root_path,
            "project_name": project.name,
            "cache_path": project.cache_path,
            "temp_path": project.temp_path,
            "output_path": project.output_path,
            "venv_path": project.venv_path,
            "models_path": project.models_path,
            "summary": normalized["summary"],
            "tech_stack": normalized["tech_stack"],
            "entry_points": normalized["entry_points"],
            "major_files": normalized["major_files"],
            "mcp_tools": normalized["mcp_tools"],
            "structure": normalized["structure"],
            "message": "프로젝트 분석 및 DB 저장이 완료되었습니다.",
        }

    job = job_manager.create("EXTERNAL_PROJECT_ANALYSIS", runner)
    return {
        "ok": True,
        "job_id": job.id,
        "status": job.status,
        "progress": job.progress,
        "message": "프로젝트 분석 작업을 시작했습니다.",
    }



@router.post("/projects/{project_id}/favorite")
async def set_project_favorite(project_id: int, req: ProjectFavoriteRequest):
    async with SessionLocal() as session:
        project = (
            await session.execute(
                select(Project).where(
                    Project.id == project_id,
                    Project.pc_name == current_pc_name(),
                )
            )
        ).scalar_one_or_none()
        if not project:
            return {
                "ok": False,
                "message": "프로젝트를 찾을 수 없습니다.",
            }

        await DatabaseGateway.set_project_favorite(
            session,
            project,
            req.is_favorite,
        )
        await session.commit()
        await session.refresh(project)

    return {
        "ok": True,
        "project_id": project.id,
        "is_favorite": bool(project.is_favorite),
        "message": "즐겨찾기 설정을 저장했습니다.",
    }


@router.post("/projects/create-agent")
async def create_agent_project(req: AgentProjectCreateRequest):
    paths = resolve_project_paths(
        project_root=req.project_root,
        cache_path=req.cache_path,
        temp_path=req.temp_path,
        output_path=req.output_path,
        venv_path=req.venv_path,
        models_path=req.models_path,
        create=True,
    )

    # 신규 생성 프로젝트도 현재 실행 세션의 허용 루트로 등록
    register_runtime_project_root(paths["project_root"])

    # v5.308 이전의 미귀속 row가 이 PC의 실제 경로와 일치하면 먼저
    # 현재 PC 소유로 승격해 중복 Project row를 만들지 않습니다.
    await adopt_legacy_projects_for_current_pc()

    async with SessionLocal() as session:
        # 같은 프로젝트 경로가 이미 등록되어 있으면 중복 생성하지 않음
        existing = (
            await session.execute(
                select(Project).where(Project.pc_name == current_pc_name(), Project.root_path == paths["project_root"])
            )
        ).scalar_one_or_none()

        if existing and not req.force_recreate:
            return {
                "ok": False,
                "conflict": True,
                "conflict_type": "PROJECT_PATH_ALREADY_REGISTERED",
                "can_recreate": True,
                "message": "이미 등록된 프로젝트 경로입니다.",
                "project_id": existing.id,
                "name": existing.name,
                "project_root": existing.root_path,
                "cache_path": getattr(existing, "cache_path", ""),
                "temp_path": getattr(existing, "temp_path", ""),
                "output_path": getattr(existing, "output_path", ""),
                "venv_path": getattr(existing, "venv_path", ""),
                "models_path": getattr(existing, "models_path", ""),
            }

        if existing and req.force_recreate:
            # 같은 경로를 새 DB Row로 중복 생성하지 않고 기존 Row를 재사용합니다.
            # 사용자가 현재 설계 화면에서 지정한 프로젝트 정보로 갱신한 뒤
            # Agent Factory가 해당 경로에 코드를 다시 생성/수정할 수 있게 합니다.
            existing.name = req.name.strip()
            existing.cache_path = paths["cache_path"]
            existing.temp_path = paths["temp_path"]
            existing.output_path = paths["output_path"]
            existing.venv_path = paths["venv_path"]
            existing.models_path = paths["models_path"]

            await DatabaseGateway.touch_project_opened(session, existing)
            await session.commit()
            await session.refresh(existing)

            database_files = materialize_database_plan(paths["project_root"], req.database_plan or {})

            return {
                "ok": True,
                "recreated": True,
                "database_files": database_files,
                "message": "기존 등록 프로젝트를 재사용하여 재생성 준비가 완료되었습니다.",
                "project_id": existing.id,
                "name": existing.name,
                "project_root": existing.root_path,
                "cache_path": getattr(existing, "cache_path", ""),
                "temp_path": getattr(existing, "temp_path", ""),
                "output_path": getattr(existing, "output_path", ""),
                "venv_path": getattr(existing, "venv_path", ""),
                "models_path": getattr(existing, "models_path", ""),
            }

        project = await DatabaseGateway.create_project(
            session,
            name=req.name.strip(),
            root_path=paths["project_root"],
            cache_path=paths["cache_path"],
            temp_path=paths["temp_path"],
            output_path=paths["output_path"],
            venv_path=paths["venv_path"],
            models_path=paths["models_path"],
        )

        await DatabaseGateway.touch_project_opened(session, project)
        await session.commit()
        await session.refresh(project)

    database_files = materialize_database_plan(paths["project_root"], req.database_plan or {})

    return {
        "ok": True,
        "message": "신규 Agent 프로젝트 생성 및 DB 저장 완료",
        "database_files": database_files,
        "project_id": project.id,
        "name": project.name,
        "project_root": project.root_path,
        "cache_path": project.cache_path,
        "temp_path": project.temp_path,
        "output_path": project.output_path,
        "venv_path": project.venv_path,
        "models_path": project.models_path,
    }




@router.get("/projects/diagnostics")
async def project_list_diagnostics():
    """
    Frontend -> FastAPI -> PostgreSQL 프로젝트 목록 경로를 진단합니다.
    실패 시 Backend 로그 전체 경로를 함께 반환합니다.
    """
    import os
    from pathlib import Path

    backend_root = Path(__file__).resolve().parents[3]
    log_dir = backend_root.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    backend_log = log_dir / "system_manager.log"
    api_log = log_dir / "api_projects.log"

    schema_status = {"ok": False, "message": "DB 연결 확인 전"}
    try:
        schema_status = await verify_project_schema()
        legacy = await adopt_legacy_projects_for_current_pc()
        pc_name = current_pc_name()
        async with SessionLocal() as session:
            count = (
                await session.execute(
                    select(func.count(Project.id)).where(Project.pc_name == pc_name)
                )
            ).scalar_one()

            sample = (
                await session.execute(
                    select(Project)
                    .where(Project.pc_name == pc_name)
                    .order_by(Project.id.desc())
                    .limit(5)
                )
            ).scalars().all()

        return {
            "ok": True,
            "path": "Frontend -> FastAPI -> PostgreSQL",
            "database_connected": True,
            "pc_name": pc_name,
            "legacy_adoption": legacy,
            "project_count": int(count or 0),
            "sample_projects": [
                {
                    "id": p.id,
                    "name": p.name,
                    "root_path": p.root_path,
                }
                for p in sample
            ],
            "backend_log_path": str(backend_log),
            "api_log_path": str(api_log),
        }
    except Exception as e:
        import traceback
        detail = traceback.format_exc()

        try:
            api_log.write_text(
                detail,
                encoding="utf-8",
            )
        except Exception:
            pass

        return {
            "project_schema": schema_status,
            "ok": False,
            "path": "Frontend -> FastAPI -> PostgreSQL",
            "database_connected": False,
            "message": str(e),
            "traceback": detail,
            "backend_log_path": str(backend_log),
            "api_log_path": str(api_log),
        }

@router.get("/projects/{project_id}")
async def get_agent_project(project_id: int):
    await adopt_legacy_projects_for_current_pc()
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        project = (
            await session.execute(
                select(Project).where(
                    Project.id == project_id,
                    Project.pc_name == pc_name,
                )
            )
        ).scalar_one_or_none()

        if not project:
            return {
                "ok": False,
                "message": "프로젝트를 찾을 수 없습니다.",
            }

        # DB에서 불러온 프로젝트도 작업공간 접근 전에 허용 루트 등록
        register_runtime_project_root(project.root_path)

        await DatabaseGateway.touch_project_opened(session, project)
        await session.commit()
        await session.refresh(project)

        analysis = (
            await session.execute(
                select(ProjectAnalysis).where(
                    ProjectAnalysis.project_id == project_id
                )
            )
        ).scalar_one_or_none()

    return {
        "ok": True,
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "project_root": project.root_path,
        "cache_path": getattr(project, "cache_path", ""),
        "temp_path": getattr(project, "temp_path", ""),
        "output_path": getattr(project, "output_path", ""),
        "venv_path": getattr(project, "venv_path", ""),
        "models_path": getattr(project, "models_path", ""),
        "last_opened_at": project.last_opened_at.isoformat() if getattr(project, "last_opened_at", None) else None,
        "is_favorite": bool(getattr(project, "is_favorite", False)),
        "analysis": (
            {
                "id": analysis.id,
                "summary": analysis.summary,
                "tech_stack": analysis.tech_stack,
                "entry_points": analysis.entry_points,
                "major_files": analysis.major_files,
                "mcp_tools": analysis.mcp_tools,
                "structure": analysis.structure,
            }
            if analysis else None
        ),
    }





@router.get("/health/runtime")
async def runtime_health():
    import asyncio
    import sys

    loop = asyncio.get_running_loop()
    loop_name = type(loop).__name__

    return {
        "ok": True,
        "platform": sys.platform,
        "event_loop": loop_name,
        "is_selector": "Selector" in loop_name,
        "is_proactor": "Proactor" in loop_name,
    }



@router.get("/health/database")
async def database_health():
    import traceback
    from pathlib import Path

    backend_root = Path(__file__).resolve().parents[3]
    log_dir = backend_root.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "database_health.log"

    try:
        async with SessionLocal() as session:
            pc_name = current_pc_name()
            count = (
                await session.execute(
                    select(func.count(Project.id)).where(Project.pc_name == pc_name)
                )
            ).scalar_one()

        return {
            "ok": True,
            "database_connected": True,
            "pc_name": pc_name,
            "project_count": int(count or 0),
            "log_path": str(log_path),
        }
    except Exception as e:
        detail = traceback.format_exc()
        try:
            log_path.write_text(detail, encoding="utf-8")
        except Exception:
            pass

        return {
            "ok": False,
            "database_connected": False,
            "message": str(e),
            "traceback": detail,
            "log_path": str(log_path),
        }


@router.get("/projects")
async def list_agent_projects():
    try:
        await adopt_legacy_projects_for_current_pc()
        pc_name = current_pc_name()
        async with SessionLocal() as session:
            rows = (
                await session.execute(
                    select(Project)
                    .where(Project.pc_name == pc_name)
                    .order_by(
                        Project.last_opened_at.desc().nullslast(),
                        Project.id.desc(),
                    )
                )
            ).scalars().all()
    except Exception:
        # 공용 DB가 오프라인/인증 실패여도 Frontend 전체가 500으로 무너지지 않게
        # 빈 목록을 반환합니다. 상세 원인은 /health/database와 /projects/diagnostics에서 확인합니다.
        return []

    for project in rows:
        try:
            register_runtime_project_root(project.root_path)
        except (FileNotFoundError, NotADirectoryError):
            pass

    return [
        {
            "id": p.id,
            "pc_name": getattr(p, "pc_name", ""),
            "name": p.name,
            "description": p.description,
            "project_root": p.root_path,
            "cache_path": getattr(p, "cache_path", ""),
            "temp_path": getattr(p, "temp_path", ""),
            "output_path": getattr(p, "output_path", ""),
            "venv_path": getattr(p, "venv_path", ""),
            "models_path": getattr(p, "models_path", ""),
            "created_at": p.created_at.isoformat() if getattr(p, "created_at", None) else None,
            "updated_at": p.updated_at.isoformat() if getattr(p, "updated_at", None) else None,
            "last_opened_at": p.last_opened_at.isoformat() if getattr(p, "last_opened_at", None) else None,
            "is_favorite": bool(getattr(p, "is_favorite", False)),
        }
        for p in rows
    ]


@router.get("/system/db-runtime")
async def db_runtime_info():
    loop = asyncio.get_running_loop()
    settings = get_settings()

    database_url = settings.database_url or ""
    if database_url.startswith("postgresql+asyncpg://"):
        driver = "asyncpg"
    elif database_url.startswith("postgresql+psycopg://"):
        driver = "psycopg"
    else:
        driver = "other"

    return {
        "ok": True,
        "event_loop": type(loop).__name__,
        "database_driver": driver,
        "database_url_scheme": database_url.split("://", 1)[0] if "://" in database_url else "",
        "windows_psycopg_ready": (
            driver == "psycopg"
            and "Proactor" not in type(loop).__name__
        ),
    }

@router.get("/sql/status")
async def sql_workspace_status(root: str = Query(...)):
    try:
        return await asyncio.to_thread(get_sql_workspace_status, root, verify=True)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sql/connections")
async def sql_workspace_connections(root: str = Query(...)):
    try:
        return await asyncio.to_thread(list_sql_workspace_profiles, root)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sql/profile")
async def sql_workspace_profile_get(
    root: str = Query(...),
    db_type: str = Query(""),
    connection_id: str = Query(""),
):
    try:
        profile = await asyncio.to_thread(
            get_sql_workspace_profile, root, db_type or None, connection_id or None
        )
        storage = await asyncio.to_thread(get_sql_workspace_profile_storage_info, root)
        return {"ok": True, "profile": profile, **storage}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc




@router.post("/sql/import-connection-file")
async def sql_workspace_import_connection_file(req: SqlWorkspaceConnectionFileImportRequest):
    kind = str(req.db_type or "").strip().lower()
    if kind not in {"supabase", "firestore", "redis"}:
        raise HTTPException(status_code=400, detail="파일 자동 분석은 Supabase, Google Cloud Firestore, Redis 연결에서 지원합니다.")

    if kind == "supabase":
        title = "Supabase PostgreSQL 연결 JSON 선택"
        file_filter = "JSON 파일 (*.json)|*.json|모든 파일 (*.*)|*.*"
    elif kind == "firestore":
        title = "Google Cloud / Firebase Service Account JSON 선택"
        file_filter = "Service Account JSON (*.json)|*.json|모든 파일 (*.*)|*.*"
    else:
        title = "Redis 연결 설정 파일 선택"
        file_filter = "Redis 설정 (*.py;*.json;*.env;*.txt)|*.py;*.json;*.env;*.txt|Python (*.py)|*.py|JSON (*.json)|*.json|모든 파일 (*.*)|*.*"

    initial = str(req.initial_path or req.root or "").strip()
    picked = await pick_file(title=title, initial_path=initial, file_filter=file_filter)
    if not picked.get("ok") or picked.get("cancelled"):
        return picked

    try:
        analyzed = await asyncio.to_thread(analyze_connection_file, str(picked.get("path") or ""), kind)
        return {**analyzed, "cancelled": False}
    except Exception as exc:
        raise HTTPException(status_code=400, detail={
            "message": f"연결 설정 파일 분석 실패: {exc}",
            "exception": type(exc).__name__,
        }) from exc


@router.post("/sql/profile")
async def sql_workspace_profile(req: SqlWorkspaceProfileRequest):
    try:
        profile = req.model_dump(exclude={"password"})
        profile.pop("root", None)
        saved = await asyncio.to_thread(
            save_sql_workspace_profile, req.root, profile, req.password or None
        )
        connections = await asyncio.to_thread(list_sql_workspace_profiles, req.root)
        return {"ok": True, "profile": saved, **connections}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sql/profile/rename")
async def sql_workspace_profile_rename(req: SqlWorkspaceRenameRequest):
    try:
        return await asyncio.to_thread(rename_sql_workspace_profile, req.root, req.connection_id, req.name)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sql/profile/delete")
async def sql_workspace_profile_delete(req: SqlWorkspaceConnectionRequest):
    try:
        return await asyncio.to_thread(delete_sql_workspace_profile, req.root, req.connection_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sql/activate")
async def sql_workspace_activate(req: SqlWorkspaceConnectionRequest):
    try:
        return await asyncio.to_thread(activate_sql_workspace_profile, req.root, req.connection_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sql/connect")
async def sql_workspace_connect(req: SqlWorkspaceProfileRequest):
    try:
        profile = req.model_dump(exclude={"password"})
        profile.pop("root", None)
        return await asyncio.to_thread(connect_sql_workspace, req.root, profile, req.password)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={
            "message": f"DB 연결 실패: {exc}",
            "exception": type(exc).__name__,
        }) from exc


@router.post("/sql/disconnect")
async def sql_workspace_disconnect(req: SqlWorkspaceConnectionRequest):
    try:
        return await asyncio.to_thread(disconnect_sql_workspace, req.root, req.connection_id or None)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sql/execute")
async def sql_workspace_execute(req: SqlWorkspaceExecuteRequest):
    try:
        return await asyncio.to_thread(execute_sql_workspace, req.root, req.sql, req.max_rows)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={
            "message": f"SQL 실행 실패: {exc}",
            "exception": type(exc).__name__,
        }) from exc

@router.post("/sql/cancel")
async def sql_workspace_cancel(req: SqlWorkspaceConnectionRequest):
    try:
        return await asyncio.to_thread(cancel_sql_workspace_execution, req.root)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={
            "message": f"SQL 실행 중지 실패: {exc}",
            "exception": type(exc).__name__,
        }) from exc


@router.get("/sql/objects")
async def sql_workspace_objects(root: str = Query(...)):
    try:
        return await asyncio.to_thread(list_sql_workspace_objects, root)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={
            "message": f"DB Object Explorer 조회 실패: {exc}",
            "exception": type(exc).__name__,
        }) from exc


@router.get("/sql/firestore/collections")
async def sql_workspace_firestore_collections(
    root: str = Query(...),
    limit: int = Query(500, ge=1, le=2000),
):
    try:
        return await asyncio.to_thread(list_sql_workspace_firestore_collections, root, limit)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={
            "message": f"Firestore Collection 목록 조회 실패: {exc}",
            "exception": type(exc).__name__,
        }) from exc


@router.get("/sql/firestore/documents")
async def sql_workspace_firestore_documents(
    root: str = Query(...),
    collection: str = Query(...),
    limit: int = Query(200, ge=1, le=1000),
):
    try:
        return await asyncio.to_thread(list_sql_workspace_firestore_documents, root, collection, limit)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={
            "message": f"Firestore Document 목록 조회 실패: {exc}",
            "exception": type(exc).__name__,
        }) from exc


@router.get("/sql/firestore/document")
async def sql_workspace_firestore_document(
    root: str = Query(...),
    path: str = Query(...),
):
    try:
        return await asyncio.to_thread(get_sql_workspace_firestore_document, root, path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={
            "message": f"Firestore Document 상세 조회 실패: {exc}",
            "exception": type(exc).__name__,
        }) from exc


@router.get("/sql/redis/keys")
async def sql_workspace_redis_keys(
    root: str = Query(...),
    pattern: str = Query("*"),
    limit: int = Query(1000, ge=1, le=5000),
):
    try:
        return await asyncio.to_thread(list_sql_workspace_redis_keys, root, pattern, limit)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={
            "message": f"Redis Key 목록 조회 실패: {exc}",
            "exception": type(exc).__name__,
        }) from exc


@router.get("/sql/redis/key")
async def sql_workspace_redis_key(
    root: str = Query(...),
    key: str = Query(...),
    max_items: int = Query(500, ge=1, le=2000),
):
    try:
        return await asyncio.to_thread(get_sql_workspace_redis_key, root, key, max_items)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={
            "message": f"Redis Key 상세 조회 실패: {exc}",
            "exception": type(exc).__name__,
        }) from exc


@router.post("/sql/redis/script")
async def sql_workspace_redis_script(req: SqlWorkspaceRedisScriptRequest):
    try:
        return await asyncio.to_thread(
            create_sql_workspace_redis_python_script,
            req.root,
            req.action,
            req.key,
            req.key_type,
            req.prefix,
            req.node_kind,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail={
            "message": f"Redis 임시 Python 코드 생성 실패: {exc}",
            "exception": type(exc).__name__,
        }) from exc


@router.post("/sql/firestore/script")
async def sql_workspace_firestore_script(req: SqlWorkspaceFirestoreScriptRequest):
    try:
        return await asyncio.to_thread(
            create_sql_workspace_firestore_python_script,
            req.root,
            req.action,
            req.path,
            req.node_kind,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail={
            "message": f"Firestore 임시 Python 코드 생성 실패: {exc}",
            "exception": type(exc).__name__,
        }) from exc


@router.get("/sql/sqlite-status")
async def sql_workspace_sqlite_status(root: str = Query(...)):
    try:
        return await asyncio.to_thread(get_sqlite_project_status, root)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={
            "message": f"SQLite3 프로젝트 상태 확인 실패: {exc}",
            "exception": type(exc).__name__,
        }) from exc


@router.post("/sql/object-open")
async def sql_workspace_object_open(req: SqlWorkspaceObjectOpenRequest):
    try:
        return await asyncio.to_thread(
            open_sql_workspace_object,
            req.root,
            req.schema,
            req.category,
            req.name,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail={
            "message": f"DB 객체 열기 실패: {exc}",
            "exception": type(exc).__name__,
        }) from exc




@router.post("/sql/table-diagram")
async def sql_workspace_table_diagram(req: SqlWorkspaceObjectOpenRequest):
    try:
        return await asyncio.to_thread(
            create_sql_workspace_table_diagram,
            req.root,
            req.schema,
            req.name,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail={
            "message": f"테이블 다이어그램 생성 실패: {exc}",
            "exception": type(exc).__name__,
        }) from exc


@router.post("/sql/schema-diagram")
async def sql_workspace_schema_diagram(req: SqlWorkspaceSchemaDiagramRequest):
    try:
        return await asyncio.to_thread(
            create_sql_workspace_schema_diagram,
            req.root,
            req.schema,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail={
            "message": f"스키마 전체 다이어그램 생성 실패: {exc}",
            "exception": type(exc).__name__,
        }) from exc


@router.post("/sql/table-script")
async def sql_workspace_table_script(req: SqlWorkspaceObjectOpenRequest):
    try:
        return await asyncio.to_thread(
            create_sql_workspace_table_script,
            req.root,
            req.schema,
            req.name,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail={
            "message": f"테이블 스크립트 생성 실패: {exc}",
            "exception": type(exc).__name__,
        }) from exc

@router.post("/sql/table-alter-script")
async def sql_workspace_table_alter_script(req: SqlWorkspaceObjectOpenRequest):
    try:
        return await asyncio.to_thread(
            create_sql_workspace_table_alter_script,
            req.root,
            req.schema,
            req.name,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail={
            "message": f"테이블 수정 스크립트 생성 실패: {exc}",
            "exception": type(exc).__name__,
        }) from exc

@router.post("/sql/table-dml-script")
async def sql_workspace_table_dml_script(req: SqlWorkspaceTableDmlScriptRequest):
    try:
        return await asyncio.to_thread(
            create_sql_workspace_table_dml_script,
            req.root,
            req.schema,
            req.name,
            req.action,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail={
            "message": f"테이블 DML 스크립트 생성 실패: {exc}",
            "exception": type(exc).__name__,
        }) from exc


@router.post("/sql/postgresql-admin-script")
async def sql_workspace_postgresql_admin_script(req: SqlWorkspaceDatabaseAdminScriptRequest):
    try:
        return await asyncio.to_thread(
            create_sql_workspace_postgresql_admin_script,
            req.root,
            req.action,
            req.value,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail={
            "message": f"PostgreSQL 세션/Lock 스크립트 생성 실패: {exc}",
            "exception": type(exc).__name__,
        }) from exc


@router.get("/codex/status")
async def codex_status(root: str = Query(default="")):
    status = codex_app_server_manager.status()
    if not status.get("enabled"):
        return status
    if status.get("initialized"):
        await asyncio.to_thread(codex_app_server_manager.refresh_account)
        refreshed = codex_app_server_manager.status()
        if refreshed.get("account"):
            await asyncio.to_thread(codex_app_server_manager.refresh_rate_limits, False)
    return codex_app_server_manager.status()


@router.post("/codex/start")
async def codex_start(req: CodexStartRequest):
    return await asyncio.to_thread(codex_app_server_manager.ensure_started, req.root)


@router.post("/codex/login/chatgpt")
async def codex_login_chatgpt(req: CodexStartRequest):
    status = await asyncio.to_thread(codex_app_server_manager.ensure_started, req.root)
    if not status.get("initialized"):
        raise HTTPException(status_code=400, detail={"message": status.get("last_error") or "Codex app-server 초기화 실패"})
    try:
        return await asyncio.to_thread(codex_app_server_manager.start_chatgpt_login)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"message": f"ChatGPT 로그인 시작 실패: {exc}"}) from exc


@router.post("/codex/logout")
async def codex_logout():
    try:
        return await asyncio.to_thread(codex_app_server_manager.logout)
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"message": f"Codex 계정 연결 해제 실패: {exc}"}) from exc


@router.get("/codex/rate-limits")
async def codex_rate_limits(force: bool = Query(default=False)):
    status = codex_app_server_manager.status()
    if not status.get("enabled"):
        return {"ok": False, "rate_limits": {}, "message": "Codex 사용 설정이 꺼져 있습니다."}
    if not status.get("initialized"):
        return {"ok": False, "rate_limits": {}, "message": status.get("last_error") or "Codex가 실행 중이 아닙니다."}
    await asyncio.to_thread(codex_app_server_manager.refresh_account)
    if not codex_app_server_manager.status().get("account"):
        return {"ok": False, "rate_limits": {}, "message": "Codex ChatGPT 계정이 연결되어 있지 않습니다."}
    data = await asyncio.to_thread(codex_app_server_manager.refresh_rate_limits, force)
    status = codex_app_server_manager.status()
    return {
        "ok": bool(data),
        "rate_limits": data,
        "error": status.get("rate_limits_error") or "",
        "refreshed_at": status.get("rate_limits_refreshed_at") or 0,
    }


@router.get("/codex/models")
async def codex_models():
    try:
        return {"data": await asyncio.to_thread(codex_app_server_manager.refresh_models)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"message": f"Codex 모델 목록 조회 실패: {exc}"}) from exc


@router.get("/codex/threads")
async def codex_threads(root: str = Query(default=""), limit: int = Query(default=20, ge=1, le=50)):
    try:
        return {"data": await asyncio.to_thread(codex_app_server_manager.list_threads, root, limit)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"message": f"Codex 대화 목록 조회 실패: {exc}"}) from exc


@router.post("/codex/thread/start")
async def codex_thread_start(req: CodexThreadRequest):
    try:
        return {"thread": await asyncio.to_thread(codex_app_server_manager.start_thread, req.root, req.model, req.effort)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"message": f"Codex 새 대화 시작 실패: {exc}"}) from exc


@router.post("/codex/thread/resume")
async def codex_thread_resume(req: CodexResumeThreadRequest):
    try:
        return {"thread": await asyncio.to_thread(codex_app_server_manager.resume_thread, req.thread_id, req.root)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"message": f"Codex 대화 재개 실패: {exc}"}) from exc


@router.post("/codex/turn/start")
async def codex_turn_start(req: CodexTurnRequest):
    if not req.text.strip():
        raise HTTPException(status_code=400, detail={"message": "Codex에 전달할 메시지를 입력하세요."})
    try:
        attachment_context = build_attachment_context(
            req.attachment_ids,
            purpose="Codex 참고 파일 분석",
            total_char_limit=90000,
        )
        turn = await asyncio.to_thread(
            codex_app_server_manager.start_turn,
            req.thread_id, req.text, req.root, req.model, req.effort,
            attachment_context.get("text") or "",
        )
        return {
            "turn": turn,
            "attachments": attachment_context.get("files") or [],
            "attachment_warnings": attachment_context.get("warnings") or [],
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"message": f"Codex 작업 시작 실패: {exc}"}) from exc


@router.post("/codex/turn/interrupt")
async def codex_turn_interrupt(req: CodexInterruptRequest):
    try:
        await asyncio.to_thread(codex_app_server_manager.interrupt_turn, req.thread_id, req.turn_id)
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"message": f"Codex 작업 중지 실패: {exc}"}) from exc


@router.post("/codex/approval")
async def codex_approval(req: CodexApprovalRequest):
    try:
        await asyncio.to_thread(
            codex_app_server_manager.resolve_server_request,
            req.request_id, req.decision, req.payload or None,
        )
        return {"ok": True}
    except Exception as exc:
        raise HTTPException(status_code=400, detail={"message": f"Codex 승인 처리 실패: {exc}"}) from exc


@router.websocket("/codex/events")
async def codex_events(ws: WebSocket):
    await ws.accept()
    subscriber_id, event_queue = codex_app_server_manager.subscribe()
    try:
        await ws.send_json({"type": "codex/state", "status": codex_app_server_manager.status()})
        while True:
            try:
                event = event_queue.get_nowait()
            except Exception:
                await asyncio.sleep(0.05)
                continue
            await ws.send_json(event)
    except WebSocketDisconnect:
        return
    finally:
        codex_app_server_manager.unsubscribe(subscriber_id)


@router.post("/web-browser/chromium/{session_id}/navigate")
async def chromium_browser_navigate(session_id: str, req: ChromiumBrowserNavigateRequest):
    """v5.319: Render a public Internet page in a real headless Chrome/Chromium session."""
    try:
        return await chromium_browser_manager.navigate(
            session_id=session_id,
            url=req.url,
            width=req.viewport_width,
            height=req.viewport_height,
            force_restart=req.force_restart,
        )
    except ChromiumBrowserError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"message": str(exc), "diagnostics": exc.diagnostics}) from exc


@router.get("/web-browser/chromium/diagnostics")
async def chromium_browser_diagnostics():
    """v5.326: return the latest Chrome/CDP diagnostics without starting a browser."""
    return await chromium_browser_manager.diagnostics()


@router.get("/web-browser/chromium/{session_id}/state")
async def chromium_browser_state(session_id: str):
    try:
        return await chromium_browser_manager.state(session_id, consume_popups=True)
    except ChromiumBrowserError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"message": str(exc), "diagnostics": exc.diagnostics}) from exc


@router.get("/web-browser/chromium/{session_id}/screenshot")
async def chromium_browser_screenshot(session_id: str):
    try:
        content = await chromium_browser_manager.screenshot(session_id)
    except ChromiumBrowserError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"message": str(exc), "diagnostics": exc.diagnostics}) from exc
    return Response(
        content=content,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@router.post("/web-browser/chromium/{session_id}/action")
async def chromium_browser_action(session_id: str, req: ChromiumBrowserActionRequest):
    try:
        return await chromium_browser_manager.action(session_id, req.action, req.model_dump())
    except ChromiumBrowserError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"message": str(exc), "diagnostics": exc.diagnostics}) from exc


@router.websocket("/web-browser/cdp/{session_id}/stream")
async def chromium_browser_cdp_stream(ws: WebSocket, session_id: str):
    """v5.326: stream frames only from an already-running CDP session; never auto-start Chrome."""
    await ws.accept()
    revision = -1
    try:
        while True:
            frame = await chromium_browser_manager.next_frame(session_id, revision)
            next_revision = int(frame.get("revision") or 0)
            data = str(frame.get("data") or "")
            if data and next_revision != revision:
                revision = next_revision
                await ws.send_json({
                    "type": "frame",
                    "revision": revision,
                    "data": data,
                    "url": frame.get("url", ""),
                    "loading": bool(frame.get("loading", False)),
                })
            else:
                await asyncio.sleep(0.02)
    except WebSocketDisconnect:
        return
    except ChromiumBrowserError as exc:
        try:
            await ws.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
    except Exception as exc:
        try:
            await ws.send_json({"type": "error", "message": f"CDP stream failed: {exc}"})
        except Exception:
            pass


@router.delete("/web-browser/chromium/{session_id}")
async def chromium_browser_close(session_id: str):
    return await chromium_browser_manager.close(session_id)


@router.api_route("/web-proxy/{session_id}/{scheme}/{netloc}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
@router.api_route("/web-proxy/{session_id}/{scheme}/{netloc}/{target_path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"])
async def web_browser_proxy(
    request: Request,
    session_id: str,
    scheme: str,
    netloc: str,
    target_path: str = "",
):
    """
    v5.318: public Internet page proxy for the Workspace browser.

    Local/private IP URLs intentionally never pass through this endpoint. The
    browser keeps using the existing direct iframe path for those destinations.
    """
    target_url = reconstruct_proxy_target(
        scheme,
        netloc,
        target_path,
        request.url.query,
    )
    try:
        result = await fetch_external_page(
            target_url=target_url,
            session_id=session_id,
            method=request.method,
            request_headers=dict(request.headers),
            body=await request.body(),
        )
    except BrowserProxyError as exc:
        return Response(
            content=proxy_error_html(str(exc), target_url),
            status_code=exc.status_code,
            headers={
                "Content-Type": "text/html; charset=utf-8",
                "Cache-Control": "no-store",
                "Access-Control-Allow-Origin": "*",
            },
        )

    headers = dict(result.headers)
    if result.redirect_url:
        headers["Location"] = result.redirect_url
    headers["Content-Type"] = result.content_type
    if result.content_type.lower().startswith("text/html"):
        # External JavaScript runs in a sandboxed iframe. Restrict its network/form/resource
        # access to the proxy path only so it cannot call AgentStudio's local API directly.
        proxy_prefix = f"{str(request.base_url).rstrip('/')}/api/web-proxy/"
        headers["Content-Security-Policy"] = "; ".join([
            "default-src 'none'",
            f"script-src 'unsafe-inline' 'unsafe-eval' blob: {proxy_prefix}",
            f"style-src 'unsafe-inline' {proxy_prefix}",
            f"img-src data: blob: {proxy_prefix}",
            f"font-src data: {proxy_prefix}",
            f"media-src data: blob: {proxy_prefix}",
            f"frame-src {proxy_prefix}",
            f"connect-src {proxy_prefix}",
            f"form-action {proxy_prefix}",
            f"worker-src blob: {proxy_prefix}",
            "object-src 'none'",
            "base-uri 'none'",
        ])
    content = b"" if request.method == "HEAD" else result.content
    return Response(
        content=content,
        status_code=result.status_code,
        headers=headers,
    )


@router.get("/health")
async def health():
    return {"ok": True, "name": "THEANOVA AgentStudio", "version": "5.435", "build": "GeneratedAgentSetupIncrementalBuildTraceTsFrontend+ProjectSearchAndTextFind+SearchTreeToggleUnifiedFind+NotebookTopLevelAwait+ValidNotebookCreate+EditablePresentationExport+LargeArchitectureVisualAssets+ProjectAdaptiveWorkflowReportArchitecture+SeparatedAgentStudioPptExport+DatabaseErdWorkspacePpt+AgentProgressHeartbeatUX+FastInterviewStateDedupRepairRecovery+AttachmentAnalysisSummaryVisibility+DeepAttachmentRequirementMining+RootSourceFenceRepair+NewAgentProjectContextIsolation+ErdKeyBadgeRelationRouting+GeneratedDatabaseUrlGuide+ResizableAttachmentAnalysisPanel+AgentUILayoutTemplateGallery+DatabaseSummaryDedupFix+FrontendInputMemoryLayoutVisibilityFix+ReactTypeScriptLegacySourceCleanupFix+FailedBuildResumeCheckpoint+FailedBuildRedevelopmentCheckpoint+GlobalCommandPalette+AgentWorkCenter+HelpCenter+NotebookWorkspaceRootResolver+CtrlSNotebookSaveRootFix+PdfUnifiedFindSupport+PdfSearchDedupPageNavigationFix+PdfWhitespaceInsensitiveSearchFix+GpuAccelerationRecommendationControl+ExecutionStopLifecycle+ErdObstacleRouting+EnvExampleOnlySetupGuide+PdfMultiExtractorSearch+NotebookRuntimeContextIsolation+NotebookCaretPersistence+ManualPairTyping+CodexUsageSettingsPopover+NotebookLineBookmarkNavigation+SourceTextLineBookmarkNavigation+AgentUILayoutRuntimePersistenceControls+GeneratedAgentTestEnvironmentRoleSeed+AgentDesignProjectFeatureLifecycle+ImportedThemeLibrary+FrontendAgnosticThemeAdapters+UnifiedDesignProjectControlsAndThemeRegistryUX+DesignPanelControlRelocation+UnifiedThemeSourceMerge+MenuStateThemeExtraction+ValidationInfrastructureFallback+ExecutionTerminalStateReconcile+RequirementSupersession+WorkflowDatabaseDesignRecoveryUX+NotebookRawHtmlImageRenderingFix+NotebookCellDebugger+UnifiedSourceDebuggerAndNotebookDebugUXFix+EducationalCodeProposalExplanation+CodeEditorPathBarRemoval+CodeToolbarRightPanelFit+ThemeLivePreview+TripleScreenshotSlots+InteractiveThemeBehaviorVerification+CodeToolbarRightAlignment+MobileInteractiveThemeMenuPreview+CsvSpreadsheetGridViewer+ResizableCodeToolbarSplit+HighSpeedAnalysisPipeline+DualEditorSplitView+ResponsiveNotebookToolbarWrap+NotebookInlineDataImageRenderingFix+NotebookLiveRichOutputStreaming+NotebookSmoothLiveOutputRendering+SchedulerWorkspace+ParallelRenderedThemeFallback+AuthenticatedPptExportCors+InteractiveThemePagePreview+RenderedMenuMotionProbe"}

@router.get("/system/project-roots")
async def system_project_roots():
    return {
        "ok": True,
        "runtime_project_roots": get_runtime_project_roots(),
        "message": "현재 Backend 실행 세션에서 허용된 프로젝트 루트입니다.",
    }


@router.post("/system/database/migrate")
async def migrate_database_schema():
    """
    기존 DB 데이터를 유지한 상태로 AgentStudio 필수 스키마를 보정합니다.
    """
    return await migrate_agentstudio_schema()


@router.get("/system/status")
async def system_status():
    return await get_status()

def _merge_interview_attachment_memory(previous: str, current: str, limit: int = 18_000) -> str:
    parts = [
        redact_sensitive_text(str(previous or '')).strip(),
        redact_sensitive_text(str(current or '')).strip(),
    ]
    merged = "\n\n".join(part for part in parts if part)
    if not merged:
        return ""
    # Keep the most recent evidence if a long-running interview exceeds the
    # bounded memory budget. Raw attachment bodies remain Backend-only.
    return merged[-max(2_000, int(limit)):]


@router.post("/chat/interview/attachments/summary")
async def interview_attachment_summary(req: AttachmentRequirementsSummaryRequest):
    attachment_context = build_requirements_attachment_context(
        req.attachment_ids,
        purpose="Agent 설계 인터뷰 첨부 파일 통합 요구사항 분석",
    )
    context_text = str(attachment_context.get("text") or "").strip()
    if not context_text:
        return {
            "ok": False,
            "summary": "",
            "attachment_memory": redact_sensitive_text(req.attachment_memory or ""),
            "attachments": attachment_context.get("files") or [],
            "attachment_warnings": attachment_context.get("warnings") or ["분석할 첨부 텍스트가 없습니다."],
        }

    requirement_registry = extract_attachment_requirement_registry(context_text)
    registry_memory = format_requirement_registry_memory(requirement_registry)

    with usage_context(
        project_root=req.project_root,
        operation="requirements_attachment_summary",
    ):
        summary = await summarize_attachment_requirements(
            context_text,
            previous_summary=redact_sensitive_text(req.attachment_memory or ""),
            provider=req.provider,
        )

    summary = redact_sensitive_text(summary).strip()
    current_memory_parts = []
    if registry_memory:
        current_memory_parts.append(registry_memory)
    if summary:
        current_memory_parts.append("[첨부 파일에서 파악한 사용자 요구사항 요약]\n" + summary)
    current_memory = "\n\n".join(current_memory_parts)
    memory = _merge_interview_attachment_memory(req.attachment_memory, current_memory, limit=18_000)
    return {
        "ok": bool(summary or requirement_registry.get("requirements")),
        "summary": summary,
        "attachment_memory": memory,
        "attachments": attachment_context.get("files") or [],
        "attachment_warnings": attachment_context.get("warnings") or [],
        "attachments_consumed": bool(req.attachment_ids),
        "attachment_requirements": requirement_registry.get("requirements") or [],
        "attachment_requirement_coverage": requirement_registry.get("coverage") or {},
    }


@router.post("/chat/interview")
async def interview(req: ChatRequest):
    with usage_context(
        project_root=req.project_root,
        operation="requirements_interview",
    ):
        attachment_context = build_requirements_attachment_context(
            req.attachment_ids,
            purpose="Agent 설계 인터뷰 요구사항/참고자료 분석",
        )
        fresh_attachment_text = str(attachment_context.get("text") or "").strip()
        requirement_registry = extract_attachment_requirement_registry(fresh_attachment_text) if fresh_attachment_text else {"requirements": [], "coverage": {}}
        registry_memory = format_requirement_registry_memory(requirement_registry)
        attachment_memory = _merge_interview_attachment_memory(
            req.attachment_memory,
            registry_memory or fresh_attachment_text,
        )
        # v5.363: normal interview-with-files exposes the requirement registry
        # immediately without a second LLM call. The richer summary action can
        # still call the model explicitly.
        attachment_summary = build_attachment_requirements_display_summary(
            fresh_attachment_text
        ) if fresh_attachment_text else ""
        answer = await next_interview_message(
            req.message,
            req.history,
            req.provider,
            attachment_context=fresh_attachment_text,
            attachment_memory=attachment_memory,
        )

    return {
        "answer": answer,
        "attachments": attachment_context.get("files") or [],
        "attachment_warnings": attachment_context.get("warnings") or [],
        "attachment_memory": attachment_memory,
        "attachment_summary": attachment_summary,
        "attachment_requirements": requirement_registry.get("requirements") or [],
        "attachment_requirement_coverage": requirement_registry.get("coverage") or {},
        "attachments_consumed": bool(req.attachment_ids),
    }

@router.post("/agent/plan")
async def agent_plan(req: PlanRequest):
    return {"plan": await build_plan(req.requirements, req.provider)}

@router.websocket("/files/watch")
async def project_files_watch(ws: WebSocket):
    """Stream project changes using native filesystem notifications.

    This endpoint intentionally stays silent while the project is idle. It
    replaces the previous browser-side 1.5 second `/files/snapshot` polling
    loop that repeatedly traversed the source tree and generated access-log
    writes even when the user was doing nothing.
    """
    await ws.accept()
    root = str(ws.query_params.get("root") or "").strip()
    if not root:
        await ws.send_json({"type": "error", "message": "root가 필요합니다."})
        await ws.close(code=1008)
        return

    try:
        try:
            validate_project_root(root)
        except PermissionError as exc:
            restored = await ensure_persisted_project_root(root)
            if not restored.get("registered"):
                await ws.send_json({
                    "type": "error",
                    "message": str(exc),
                    "code": "PROJECT_ROOT_NOT_ALLOWED",
                })
                await ws.close(code=1008)
                return
            validate_project_root(root)

        await ws.send_json({"type": "ready", "root": root})

        async def _send_changes():
            async for changes in watch_project_changes(root):
                await ws.send_json({
                    "type": "changes",
                    "root": root,
                    "changes": changes,
                })

        async def _wait_for_disconnect():
            try:
                while True:
                    await ws.receive()
            except WebSocketDisconnect:
                return

        change_task = asyncio.create_task(_send_changes())
        disconnect_task = asyncio.create_task(_wait_for_disconnect())
        done, pending = await asyncio.wait(
            {change_task, disconnect_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            try:
                task.result()
            except WebSocketDisconnect:
                pass
    except WebSocketDisconnect:
        pass
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        try:
            await ws.send_json({
                "type": "error",
                "message": f"프로젝트 파일 감시 오류: {exc}",
            })
        except Exception:
            pass
        try:
            await ws.close(code=1011)
        except Exception:
            pass


@router.get("/files/snapshot")
async def project_files_snapshot(root: str = Query(...)):
    try:
        return await project_file_snapshot(root)
    except PermissionError as exc:
        # Backend 재시작 직후 Frontend가 이전 프로젝트 root를 먼저 복원하면
        # in-memory allow-list가 아직 비어 있을 수 있습니다. DB에 정확히
        # 등록된 프로젝트인지 확인한 경우에만 해당 root를 자가 복구합니다.
        restored = await ensure_persisted_project_root(root)
        if restored.get("registered"):
            return await project_file_snapshot(root)

        raise HTTPException(
            status_code=403,
            detail={
                "code": "PROJECT_ROOT_NOT_ALLOWED",
                "message": str(exc),
                "project_root": root,
                "recovery": restored,
            },
        ) from exc


@router.get("/files/meta")
async def project_file_meta(root: str = Query(...), relative_path: str = Query(...)):
    return await get_file_meta(root, relative_path)

@router.post("/files/hash-state")
async def project_file_hash_state(req: FileHashStateRequest):
    return await get_file_hash_states(req.root, req.relative_paths)


@router.post("/files/folder")
async def create_project_folder(req: FolderCreateRequest):
    return await create_folder(
        req.root,
        req.relative_path,
    )


@router.post("/files/create")
async def create_project_file(payload: dict):
    root = str(payload.get("root") or "").strip()
    relative_path = str(payload.get("relative_path") or "").strip()

    if not root:
        raise HTTPException(status_code=400, detail="root가 필요합니다.")

    if not relative_path:
        raise HTTPException(
            status_code=400,
            detail="relative_path가 필요합니다.",
        )

    try:
        return await create_file(root, relative_path)
    except FileExistsError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except (ValueError, FileNotFoundError, PermissionError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/files/rename")
async def rename_project_path(req: PathRenameRequest):
    return await rename_path(
        req.root,
        req.relative_path,
        req.new_name,
    )


def _windows_file_in_use_error(exc: BaseException) -> bool:
    winerror = getattr(exc, "winerror", None)
    if winerror in {32, 33}:
        return True
    message = str(exc or "")
    return "WinError 32" in message or "WinError 33" in message


@router.post("/files/delete")
async def delete_project_files(req: FilesDeleteRequest):
    try:
        return await delete_files(req.root, req.relative_paths)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except PermissionError as first_error:
        if not _windows_file_in_use_error(first_error):
            raise HTTPException(status_code=400, detail=str(first_error)) from first_error

        # v5.238: Windows sharing violation. First release only AgentStudio-owned
        # handles that can legitimately keep a project SQLite DB open. We never
        # terminate arbitrary external processes.
        released_sqlite = await asyncio.to_thread(
            release_sql_workspace_file_locks,
            req.root,
            req.relative_paths,
        )
        reset_python_sessions = await asyncio.to_thread(
            python_execution_manager.reset_all_for_root,
            req.root,
        )
        if released_sqlite or reset_python_sessions:
            await asyncio.sleep(0.15)

        try:
            result = await delete_files(req.root, req.relative_paths)
            result["lock_recovered"] = True
            result["released_sqlite_connections"] = released_sqlite
            result["reset_python_sessions"] = reset_python_sessions
            return result
        except PermissionError as retry_error:
            if _windows_file_in_use_error(retry_error):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "code": "FILE_IN_USE",
                        "message": (
                            "파일을 사용 중인 연결을 해제한 뒤 다시 시도했지만 아직 다른 프로세스가 파일을 열고 있습니다. "
                            "SQLite/DB 도구, Python 프로그램 또는 외부 편집기에서 해당 DB 연결을 닫은 뒤 다시 삭제하세요."
                        ),
                        "paths": req.relative_paths,
                        "released_sqlite_connections": released_sqlite,
                        "reset_python_sessions": reset_python_sessions,
                        "original_error": str(retry_error),
                    },
                ) from retry_error
            raise HTTPException(status_code=400, detail=str(retry_error)) from retry_error


@router.post("/files/execute-cmd")
async def execute_project_cmd_file(payload: dict):
    """Run a project CMD as a tracked process so it can be stopped from the UI."""
    root = str(payload.get("root") or "").strip()
    relative_path = str(payload.get("relative_path") or "").strip()
    if not root:
        raise HTTPException(status_code=400, detail="root가 필요합니다.")
    if not relative_path:
        raise HTTPException(status_code=400, detail="relative_path가 필요합니다.")
    try:
        return await asyncio.to_thread(managed_process_service.start_cmd, root, relative_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"CMD 파일이 없습니다: {exc}") from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"CMD 실행 실패: {exc}") from exc


@router.get("/files/execute-cmd/{execution_id}/status")
async def execute_project_cmd_status(execution_id: str):
    return await asyncio.to_thread(managed_process_service.status, execution_id)


@router.post("/files/execute-cmd/{execution_id}/stop")
async def stop_project_cmd(execution_id: str):
    return await asyncio.to_thread(managed_process_service.stop, execution_id)


@router.get("/folders")
async def folders(root: str):
    return await list_directories(root)


@router.get("/files")
async def files(root: str):
    return {"root": root, "files": await list_files(root)}

@router.get("/files/raw")
async def project_file_raw(root: str = Query(...), relative_path: str = Query(...)):
    """등록된 프로젝트 안의 원본 파일 바이트를 Save As 용도로 전송합니다.

    편집 가능한 텍스트는 Frontend의 현재 buffer를 저장하고, PDF/PPT/PPTX처럼
    읽기 전용 binary preview 탭은 이 endpoint에서 원본 bytes를 읽습니다.
    프로젝트 root allow-list와 경로 이탈 검증은 기존 file viewer와 동일합니다.
    """
    project_root = Path(str(root or "")).expanduser().resolve()
    relative = str(relative_path or "").strip()
    if not relative:
        raise HTTPException(status_code=400, detail="relative_path가 필요합니다.")

    try:
        await get_file_meta(str(project_root), relative)
    except PermissionError as exc:
        restored = await ensure_persisted_project_root(str(project_root))
        if not restored.get("registered"):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "PROJECT_ROOT_NOT_ALLOWED",
                    "message": str(exc),
                    "project_root": str(project_root),
                    "recovery": restored,
                },
            ) from exc
        await get_file_meta(str(project_root), relative)

    target = (project_root / Path(relative.replace("\\", "/"))).resolve()
    try:
        target.relative_to(project_root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="프로젝트 밖의 파일은 읽을 수 없습니다.") from exc

    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"파일을 찾을 수 없습니다: {target}")

    return FileResponse(
        path=str(target),
        filename=target.name,
        media_type="application/octet-stream",
        content_disposition_type="inline",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.get("/files/pdf")
async def project_pdf_view(root: str = Query(...), relative_path: str = Query(...)):
    """등록 프로젝트 안의 PDF를 브라우저 내장 PDF Viewer용으로 inline 전송합니다.

    PDF는 UTF-8 텍스트가 아니라 바이너리 형식이므로 `/files/read`를 거치지
    않습니다. 프로젝트 root는 기존 runtime allow-list 또는 DB에 저장된 정확한
    프로젝트 경로일 때만 허용합니다.
    """
    project_root = Path(str(root or "")).expanduser().resolve()
    relative = str(relative_path or "").strip()
    if not relative:
        raise HTTPException(status_code=400, detail="relative_path가 필요합니다.")

    try:
        await get_file_meta(str(project_root), relative)
    except PermissionError as exc:
        restored = await ensure_persisted_project_root(str(project_root))
        if not restored.get("registered"):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "PROJECT_ROOT_NOT_ALLOWED",
                    "message": str(exc),
                    "project_root": str(project_root),
                    "recovery": restored,
                },
            ) from exc
        await get_file_meta(str(project_root), relative)

    target = (project_root / Path(relative.replace("\\", "/"))).resolve()
    try:
        target.relative_to(project_root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="프로젝트 밖의 PDF는 열 수 없습니다.") from exc

    if target.suffix.casefold() != ".pdf":
        raise HTTPException(status_code=415, detail="PDF 파일만 이 Viewer로 열 수 있습니다.")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"PDF 파일을 찾을 수 없습니다: {target}")

    def _read_pdf_header() -> bytes:
        with target.open("rb") as stream:
            return stream.read(5)

    try:
        header = await asyncio.to_thread(_read_pdf_header)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=f"PDF 접근 권한이 없습니다: {target}") from exc
    if header != b"%PDF-":
        raise HTTPException(status_code=415, detail="유효한 PDF 헤더(%PDF-)를 찾을 수 없습니다.")

    return FileResponse(
        path=str(target),
        media_type="application/pdf",
        filename=target.name,
        content_disposition_type="inline",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@router.post("/db-erd/analyze")
async def analyze_database_erd(payload: DatabaseErdRequest):
    """현재 Agent/프로젝트 또는 AgentStudio 자체의 DB별 ERD 모델을 생성합니다."""
    deck_type = str(payload.deck_type or "AGENT").strip().upper()
    if deck_type == "STUDIO":
        studio_root = str(Path(__file__).resolve().parents[3])
        return await asyncio.to_thread(build_agentstudio_db_erd, studio_root)
    project_root = str(payload.project_root or "").strip()
    if project_root:
        try:
            project_root = register_runtime_project_root(project_root)
        except Exception:
            pass
    return await asyncio.to_thread(
        build_project_db_erd,
        project_root,
        database_plan=payload.database_plan or {},
        project_profile=payload.project_profile or {},
        workflow_request=str(payload.workflow_request or ""),
    )


@router.post("/presentation/export")
async def export_agentstudio_presentation(payload: PresentationExportRequest):
    """워크플로우/실행결과/분석리포트/아키텍처/DB ERD를 편집 가능한 PPTX로 내보냅니다.

    화면 캡처를 그대로 넣는 방식이 아니라 python-pptx로 텍스트, 카드, 레이어,
    연결 화살표 등을 PowerPoint 네이티브 객체로 생성합니다. 따라서 사용자는
    다운로드한 PPTX에서 제목, 박스, 구조와 설명을 직접 수정할 수 있습니다.
    """
    scope = str(payload.scope or "ALL").strip().upper()
    deck_type = str(payload.deck_type or "AGENT").strip().upper()
    if scope not in {"ALL", "WORKFLOW", "RUN", "REPORT", "ARCHITECTURE", "DB_ERD"}:
        raise HTTPException(status_code=400, detail="지원하지 않는 PPT 내보내기 범위입니다.")
    if deck_type not in {"AGENT", "STUDIO"}:
        raise HTTPException(status_code=400, detail="지원하지 않는 PPT 문서 유형입니다.")
    if deck_type == "STUDIO" and scope != "ALL":
        raise HTTPException(status_code=400, detail="Studio PPT는 상단 Studio PPT 버튼에서 전체 문서로만 다운로드할 수 있습니다.")

    data = payload.model_dump()
    data["scope"] = scope
    data["deck_type"] = deck_type
    if not data.get("generated_at"):
        data["generated_at"] = datetime.now().isoformat(timespec="seconds")

    # v5.363: Agent PPT만 현재 프로젝트를 재분석합니다. Studio PPT는 현재 프로젝트와 완전히 분리합니다.
    # Agent PPT는 UI의 오래된 Snapshot만 신뢰하지 않습니다. 프로젝트 루트가 있으면
    # 내보내기 직전에 실제 소스를 다시 분석하고, Agent Factory의 실제 실행/설계 결과가
    # 없는 항목만 Project Adaptive Snapshot으로 채웁니다. 따라서 감지되지 않은 DB/LLM/MCP를
    # 고정 템플릿 때문에 PPT에 표시하지 않습니다.
    project_root = str(data.get("project_root") or "").strip()
    if deck_type == "AGENT" and project_root:
        try:
            adaptive = await build_project_adaptive_report(
                register_runtime_project_root(project_root),
                str(data.get("workflow_request") or ""),
            )
            report = dict(data.get("report") or {})
            fallback_map = {
                "targetWorkflow": adaptive.get("workflow") or {},
                "requirementSpec": adaptive.get("requirement_spec") or {},
                "capabilityPlan": adaptive.get("capability_plan") or {},
                "toolMcpPlan": adaptive.get("tool_mcp_plan") or {},
                "architecture": adaptive.get("architecture") or {},
            }
            for key, value in fallback_map.items():
                current = report.get(key)
                if not current or (isinstance(current, dict) and not any(current.values())):
                    report[key] = value
            report["projectProfile"] = adaptive
            report["analysisReport"] = adaptive.get("analysis_report") or {}
            baseline = adaptive.get("execution_baseline") or {}
            if not report.get("status") or report.get("status") == "NOT_STARTED":
                report["status"] = baseline.get("status") or report.get("status") or "PROJECT_LOADED"
            if not report.get("testCommand"):
                report["testCommand"] = baseline.get("test_command") or ""
            data["report"] = report
        except Exception:
            # Adaptive 분석 실패가 PPT 다운로드 자체를 막지는 않습니다. 기존 Snapshot으로 계속 생성합니다.
            pass

    # v5.363: DB ERD는 PPT 생성 직전 서버에서 다시 구성해 UI Snapshot과 분리합니다.
    try:
        if deck_type == "STUDIO":
            studio_root = str(Path(__file__).resolve().parents[3])
            data["db_erd"] = await asyncio.to_thread(build_agentstudio_db_erd, studio_root)
        else:
            report = data.get("report") or {}
            data["db_erd"] = await asyncio.to_thread(
                build_project_db_erd,
                project_root,
                database_plan=report.get("databasePlan") or data.get("db_erd", {}).get("database_plan") or {},
                project_profile=report.get("projectProfile") or {},
                workflow_request=str(data.get("workflow_request") or ""),
            )
    except Exception:
        # ERD 분석 실패는 PPT 전체 다운로드를 막지 않고 전달된 Snapshot을 사용합니다.
        pass

    try:
        content, filename = await asyncio.to_thread(
            build_agentstudio_presentation,
            data,
            "5.435",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "code": "PRESENTATION_EXPORT_FAILED",
                "message": f"PPT 문서를 생성하지 못했습니다: {exc}",
            },
        ) from exc

    ascii_filename = "AgentStudio_Report.pptx"
    encoded = quote(filename)
    return Response(
        content=content,
        media_type=PPTX_MIME,
        headers={
            "Content-Disposition": f"attachment; filename=\"{ascii_filename}\"; filename*=UTF-8''{encoded}",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "X-AgentStudio-Export-Scope": scope,
            "X-AgentStudio-Export-Deck-Type": deck_type,
            "X-AgentStudio-Export-Editable": "native-powerpoint-shapes",
        },
    )


@router.post("/files/presentation/prepare")
async def project_presentation_prepare(payload: dict):
    """PPT/PPTX 원본은 수정하지 않고 임시 PDF 미리보기를 준비합니다.

    Windows에서는 Microsoft PowerPoint COM Export를 우선 사용하고, 사용할 수
    없거나 변환에 실패하면 LibreOffice headless를 fallback으로 사용합니다.
    결과 PDF는 프로젝트의 `.agentstudio/preview/presentations` 아래에만 캐시됩니다.
    """
    project_root = Path(str(payload.get("root") or "")).expanduser().resolve()
    relative = str(payload.get("relative_path") or "").strip()
    force = bool(payload.get("force"))
    if not relative:
        raise HTTPException(status_code=400, detail="relative_path가 필요합니다.")

    try:
        await get_file_meta(str(project_root), relative)
    except PermissionError as exc:
        restored = await ensure_persisted_project_root(str(project_root))
        if not restored.get("registered"):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "PROJECT_ROOT_NOT_ALLOWED",
                    "message": str(exc),
                    "project_root": str(project_root),
                    "recovery": restored,
                },
            ) from exc
        await get_file_meta(str(project_root), relative)

    target = (project_root / Path(relative.replace("\\", "/"))).resolve()
    try:
        target.relative_to(project_root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="프로젝트 밖의 PowerPoint 파일은 열 수 없습니다.") from exc

    if target.suffix.casefold() not in {".ppt", ".pptx"}:
        raise HTTPException(status_code=415, detail="PPT/PPTX 파일만 PowerPoint 미리보기를 사용할 수 있습니다.")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"PowerPoint 파일을 찾을 수 없습니다: {target}")

    try:
        result = await asyncio.to_thread(
            prepare_presentation_preview,
            project_root,
            target,
            force=force,
        )
    except PresentationPreviewError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "PRESENTATION_PREVIEW_CONVERSION_FAILED",
                "message": str(exc),
                "attempts": exc.attempts,
                "recovery": [
                    "Windows에서는 Microsoft PowerPoint가 설치되어 있는지 확인하세요.",
                    "PowerPoint가 없으면 LibreOffice를 설치하면 자동 fallback 변환을 사용합니다.",
                    "원본 PPT/PPTX 파일은 수정되지 않습니다.",
                ],
            },
        ) from exc

    return {
        "ok": True,
        "relative_path": result.source_relative_path,
        "source_sha256": result.source_sha256,
        "source_mtime_ns": result.source_mtime_ns,
        "source_size": result.source_size,
        "preview_size": result.preview_size,
        "converter": result.converter,
        "cache_hit": result.cache_hit,
        "generated_at": result.generated_at,
        "original_modified": False,
    }


@router.get("/files/presentation/pdf")
async def project_presentation_pdf_view(
    root: str = Query(...),
    relative_path: str = Query(...),
):
    """준비된 PPT/PPTX PDF 미리보기를 기존 브라우저 PDF Viewer에 inline 전송합니다."""
    project_root = Path(str(root or "")).expanduser().resolve()
    relative = str(relative_path or "").strip()
    if not relative:
        raise HTTPException(status_code=400, detail="relative_path가 필요합니다.")

    try:
        await get_file_meta(str(project_root), relative)
    except PermissionError as exc:
        restored = await ensure_persisted_project_root(str(project_root))
        if not restored.get("registered"):
            raise HTTPException(status_code=403, detail="프로젝트 root가 등록되어 있지 않습니다.") from exc
        await get_file_meta(str(project_root), relative)

    target = (project_root / Path(relative.replace("\\", "/"))).resolve()
    try:
        target.relative_to(project_root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="프로젝트 밖의 PowerPoint 파일은 열 수 없습니다.") from exc

    try:
        result = await asyncio.to_thread(prepare_presentation_preview, project_root, target)
    except PresentationPreviewError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "PRESENTATION_PREVIEW_CONVERSION_FAILED",
                "message": str(exc),
                "attempts": exc.attempts,
            },
        ) from exc

    preview = Path(result.preview_path)
    if not preview.exists() or not preview.is_file():
        raise HTTPException(status_code=404, detail="PowerPoint 미리보기 PDF를 찾을 수 없습니다.")

    return FileResponse(
        path=str(preview),
        media_type="application/pdf",
        filename=f"{target.stem}.preview.pdf",
        content_disposition_type="inline",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-AgentStudio-Presentation-Converter": result.converter,
        },
    )




@router.post("/files/search-text")
async def project_text_search(payload: dict):
    root = str(payload.get("root") or "").strip()
    query = str(payload.get("query") or "").strip()
    relative_path = str(payload.get("relative_path") or "").strip()
    if not root:
        raise HTTPException(status_code=400, detail="root가 필요합니다.")
    if not query:
        return {"query": "", "results": [], "files_scanned": 0, "truncated": False}
    try:
        return await search_project_text(
            root,
            query,
            relative_path=relative_path,
            case_sensitive=bool(payload.get("case_sensitive", False)),
            max_results=int(payload.get("max_results") or 300),
            max_files=int(payload.get("max_files") or 5000),
        )
    except PermissionError as exc:
        restored = await ensure_persisted_project_root(root)
        if restored.get("registered"):
            return await search_project_text(
                root,
                query,
                relative_path=relative_path,
                case_sensitive=bool(payload.get("case_sensitive", False)),
                max_results=int(payload.get("max_results") or 300),
                max_files=int(payload.get("max_files") or 5000),
            )
        raise HTTPException(status_code=403, detail=str(exc)) from exc


@router.post("/files/read")
async def project_file_read(payload: dict):
    """프로젝트 root + relative_path 기반 파일 읽기 API."""
    from pathlib import Path
    import asyncio
    import traceback

    root = str(payload.get("root") or "").strip()
    relative_path = str(payload.get("relative_path") or "").strip()

    if not root:
        raise HTTPException(status_code=400, detail="root가 필요합니다.")
    if not relative_path:
        raise HTTPException(status_code=400, detail="relative_path가 필요합니다.")

    project_root = Path(root).expanduser().resolve()
    target = (project_root / Path(relative_path.replace("\\", "/"))).resolve()

    if target.suffix.casefold() == ".pdf":
        raise HTTPException(
            status_code=415,
            detail={
                "code": "PDF_BINARY_VIEWER_REQUIRED",
                "message": "PDF는 텍스트 파일이 아닙니다. /api/files/pdf Viewer를 사용하세요.",
            },
        )
    if target.suffix.casefold() in {".ppt", ".pptx"}:
        raise HTTPException(
            status_code=415,
            detail={
                "code": "PRESENTATION_BINARY_VIEWER_REQUIRED",
                "message": "PPT/PPTX는 바이너리 문서입니다. /api/files/presentation/prepare 미리보기를 사용하세요.",
            },
        )

    try:
        target.relative_to(project_root)
    except ValueError as e:
        raise HTTPException(
            status_code=403,
            detail=f"프로젝트 밖의 파일은 읽을 수 없습니다: {target}",
        ) from e

    try:
        if not target.exists():
            raise FileNotFoundError(str(target))
        if target.is_dir():
            raise IsADirectoryError(str(target))

        content = await asyncio.to_thread(
            target.read_text,
            encoding="utf-8",
            errors="replace",
        )
        stat = target.stat()
        raw = await asyncio.to_thread(target.read_bytes)
        import hashlib
        return {
            "ok": True,
            "root": str(project_root),
            "relative_path": target.relative_to(project_root).as_posix(),
            "path": str(target),
            "content": content,
            "mtime_ns": int(stat.st_mtime_ns),
            "size": int(stat.st_size),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"파일을 찾을 수 없습니다: {target}") from e
    except IsADirectoryError as e:
        raise HTTPException(status_code=400, detail=f"파일이 아니라 폴더입니다: {target}") from e
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=f"파일 접근 권한이 없습니다: {target}") from e
    except Exception as e:
        backend_root = Path(__file__).resolve().parents[3]
        log_dir = backend_root.parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "file_read.log"
        detail = traceback.format_exc()
        try:
            log_path.write_text(detail, encoding="utf-8")
        except Exception:
            pass
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"파일 읽기 실패: {target} / {e}",
                "log_path": str(log_path),
            },
        ) from e



@router.get("/files/content")
async def project_file_content(root: str, relative_path: str):
    """
    기존 Frontend 호환용 파일 읽기 GET API.
    내부 동작은 /files/read와 동일한 UTF-8 파일 읽기 규칙을 사용합니다.
    """
    from pathlib import Path
    import asyncio

    project_root = Path(root).expanduser().resolve()
    target = (
        project_root
        / Path(relative_path.replace("\\", "/"))
    ).resolve()

    if target.suffix.casefold() == ".pdf":
        raise HTTPException(
            status_code=415,
            detail={
                "code": "PDF_BINARY_VIEWER_REQUIRED",
                "message": "PDF는 텍스트 파일이 아닙니다. /api/files/pdf Viewer를 사용하세요.",
            },
        )
    if target.suffix.casefold() in {".ppt", ".pptx"}:
        raise HTTPException(
            status_code=415,
            detail={
                "code": "PRESENTATION_BINARY_VIEWER_REQUIRED",
                "message": "PPT/PPTX는 바이너리 문서입니다. /api/files/presentation/prepare 미리보기를 사용하세요.",
            },
        )

    try:
        target.relative_to(project_root)
    except ValueError as e:
        raise HTTPException(
            status_code=403,
            detail=f"프로젝트 밖의 파일은 읽을 수 없습니다: {target}",
        ) from e

    if not target.exists():
        raise HTTPException(
            status_code=404,
            detail=f"파일을 찾을 수 없습니다: {target}",
        )

    if target.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"파일이 아니라 폴더입니다: {target}",
        )

    try:
        content = await asyncio.to_thread(
            target.read_text,
            encoding="utf-8",
            errors="replace",
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=403,
            detail=f"파일 접근 권한이 없습니다: {target}",
        ) from e

    return {
        "ok": True,
        "root": str(project_root),
        "relative_path": relative_path,
        "path": str(target),
        "content": content,
    }

@router.post("/file/read")
async def file_read(req: FileRequest):
    try:
        content = await read_file(req.path)
        return {
            "ok": True,
            "path": req.path,
            "content": content,
        }
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"파일을 찾을 수 없습니다: {req.path}",
        ) from e
    except PermissionError as e:
        raise HTTPException(
            status_code=403,
            detail=f"파일 접근 권한이 없습니다: {req.path}",
        ) from e
    except IsADirectoryError as e:
        raise HTTPException(
            status_code=400,
            detail=f"파일이 아니라 폴더입니다: {req.path}",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"파일 읽기 실패: {req.path} / {e}",
        ) from e

@router.post("/file/write")
async def file_write(req: FileWriteRequest):
    try:
        return await write_file(
            req.path,
            req.content,
            expected_mtime_ns=req.expected_mtime_ns,
            expected_sha256=req.expected_sha256,
            force=req.force,
        )
    except InvalidNotebookContentError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "NOTEBOOK_INVALID_SAVE_BLOCKED",
                "message": "유효하지 않은 Notebook 내용이므로 저장을 차단했습니다. 원본 .ipynb 파일은 변경하지 않았습니다.",
                "path": str(e.path),
                "validation_error": e.validation_message,
            },
        ) from e
    except ExternalFileChangedError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "EXTERNAL_FILE_CHANGED",
                "message": str(e),
                "path": str(e.path),
                "expected_mtime_ns": e.expected_mtime_ns,
                "actual_mtime_ns": e.actual_mtime_ns,
                "expected_sha256": e.expected_sha256,
                "actual_sha256": e.actual_sha256,
            },
        ) from e





@router.post("/agent-factory/plan")
async def agent_factory_plan(req: AgentFactoryPlanRequest):
    plan = infer_fastapi_factory_plan(
        request=req.request,
        project_scope=True,
    )

    return {
        "ok": True,
        "plan": plan,
        "policies": (
            load_agent_factory_policies()
            if plan.get("fastapi_candidate")
            else {}
        ),
    }


@router.get("/coding-style/policy")
async def coding_style_policy():
    return {
        "ok": True,
        "policy": load_rule_policy(),
    }


@router.post("/coding-style/governance")
async def coding_style_governance(
    req: CodingRuleGovernanceRequest,
):
    return {
        "ok": True,
        "results": classify_candidates(
            req.candidates
        ),
    }


@router.get("/coding-style/rules")
async def coding_style_rules():
    return {
        "ok": True,
        "rules": list_rules(),
        "templates": list(
            (load_template_registry().get("templates") or [])
        ),
    }


@router.post("/coding-style/analyze")
async def coding_style_analyze(req: CodingStyleAnalyzeRequest):
    try:
        result = await analyze_coding_style_text(req.text)
        return {
            "ok": True,
            "analysis": result,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"코딩 스타일 분석 실패: {e}",
        ) from e


@router.post("/coding-style/validate")
async def coding_style_validate(req: CodingStyleValidateRequest):
    return validate_code_style(
        code=req.code,
        request=req.request,
        path=req.path,
        project_scope=req.project_scope,
    )


@router.post("/ai/edit")
async def ai_edit_code(req: CodeEditRequest):
    """
    현재 열린 파일 + 자연어 수정 요청을 코드 생성 모델에 전달합니다.

    일반 텍스트 파일은 전체 파일 수정 제안을 반환하고, Jupyter Notebook은
    전체 JSON/outputs를 LLM에 보내지 않고 현재 Code 셀 중심으로 Context를
    압축한 뒤 해당 셀만 다시 원본 Notebook JSON에 병합합니다.
    """
    from app.services.model_router import model_for_task, LLMTask
    import traceback

    if not req.path.strip():
        raise HTTPException(
            status_code=400,
            detail="수정할 파일 경로가 필요합니다.",
        )

    if not req.instruction.strip():
        raise HTTPException(
            status_code=400,
            detail="코드 수정 요청을 입력하세요.",
        )

    def _strip_code_fence(value: str) -> str:
        content = str(value or "").strip()
        if content.startswith("```"):
            lines = content.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines).strip()
        return content

    def _fallback_edit_explanation(original: str, proposed: str) -> dict:
        import difflib

        diff_lines = list(difflib.unified_diff(
            str(original or "").splitlines(),
            str(proposed or "").splitlines(),
            lineterm="",
        ))
        added = [line[1:].strip() for line in diff_lines if line.startswith("+") and not line.startswith("+++")]
        removed = [line[1:].strip() for line in diff_lines if line.startswith("-") and not line.startswith("---")]
        if added or removed:
            summary = f"요청을 반영해 코드 {len(added)}줄을 추가/변경했습니다."
        else:
            summary = "사용자 요청을 반영한 코드 제안입니다."
        walkthrough = []
        for line in added[:6]:
            if line:
                walkthrough.append({
                    "code": line[:220],
                    "explanation": "이 줄은 사용자 요청을 실제 코드 동작으로 반영하기 위해 추가되거나 변경된 부분입니다.",
                })
        return {
            "summary": summary,
            "value_reasons": [],
            "code_walkthrough": walkthrough,
            "notes": ["AI 설명 생성이 실패한 경우에도 코드 제안은 그대로 검토하고 적용할 수 있습니다."],
            "source": "fallback",
        }

    async def _build_edit_explanation(
        *,
        llm,
        original: str,
        proposed: str,
        instruction: str,
        path: str,
        project_root: str,
    ) -> dict:
        """Explain the proposed change without blocking the code proposal.

        Code generation remains a code-only call so malformed explanatory JSON can
        never corrupt the proposed source.  A second compact call explains only the
        actual diff, including why literal values/expressions were selected.
        """
        import difflib

        fallback = _fallback_edit_explanation(original, proposed)
        try:
            diff_text = "\n".join(difflib.unified_diff(
                str(original or "").splitlines(),
                str(proposed or "").splitlines(),
                fromfile="before",
                tofile="after",
                lineterm="",
                n=3,
            ))
            if not diff_text.strip():
                diff_text = str(proposed or "")[:8000]
            diff_text = diff_text[:14000]

            explanation_prompt = f"""
당신은 프로그래밍 학습을 돕는 코드 리뷰 설명 AI입니다.
코드를 다시 작성하지 말고, 아래 실제 변경 내용을 한국어로 설명하세요.

[파일]
{path}

[사용자 요청]
{instruction}

[변경 Diff]
```diff
{diff_text}
```

반드시 JSON 객체 하나만 반환하세요. Markdown 코드펜스는 사용하지 마세요.
스키마:
{{
  "summary": "무엇을 왜 변경했는지 2~4문장",
  "value_reasons": [
    {{"value": "코드에 들어간 값/식/함수/shape 등", "reason": "왜 이 값이나 표현이어야 하는지"}}
  ],
  "code_walkthrough": [
    {{"code": "설명 대상 코드 조각", "explanation": "이 코드가 하는 일과 실행 흐름"}}
  ],
  "notes": ["주의점, 전제조건 또는 대안이 있으면 작성"]
}}

규칙:
1. 사용자가 학습 중이라고 가정하고 용어를 쉽게 풀어 설명합니다.
2. 숫자, dtype, shape, index, 함수 인자, 조건식처럼 선택 이유가 있는 값은 value_reasons에 우선 설명합니다.
3. 이유가 없는 관례적 값은 억지로 의미를 만들지 말고 생략합니다.
4. code_walkthrough는 변경된 코드 중심으로 최대 8개만 작성합니다.
5. value_reasons도 최대 8개만 작성합니다.
6. 원본 코드와 변경 Diff로 확인할 수 없는 사실은 단정하지 않습니다.
"""

            with usage_context(
                project_root=project_root,
                operation="code_edit_explanation",
            ):
                explained = await llm.ainvoke(explanation_prompt)

            raw = explained.content if hasattr(explained, "content") else str(explained)
            raw = _strip_code_fence(raw)
            try:
                data = json.loads(raw)
            except Exception:
                start = raw.find("{")
                end = raw.rfind("}")
                if start < 0 or end <= start:
                    return fallback
                data = json.loads(raw[start:end + 1])

            if not isinstance(data, dict):
                return fallback

            def _items(name: str, keys: tuple[str, ...], limit: int) -> list[dict]:
                output = []
                for item in data.get(name) or []:
                    if not isinstance(item, dict):
                        continue
                    normalized = {key: str(item.get(key) or "").strip()[:1200] for key in keys}
                    if any(normalized.values()):
                        output.append(normalized)
                    if len(output) >= limit:
                        break
                return output

            notes = [str(item).strip()[:1200] for item in (data.get("notes") or []) if str(item).strip()][:6]
            return {
                "summary": str(data.get("summary") or fallback["summary"]).strip()[:3000],
                "value_reasons": _items("value_reasons", ("value", "reason"), 8),
                "code_walkthrough": _items("code_walkthrough", ("code", "explanation"), 8),
                "notes": notes,
                "source": "llm",
            }
        except Exception:
            return fallback

    try:
        llm = model_for_task(LLMTask.CODE_GENERATION)
        is_notebook = req.path.casefold().endswith(".ipynb")
        attachment_context = build_attachment_context(
            req.attachment_ids,
            purpose="LLM 대화형 코드 편집 참고자료",
            total_char_limit=70000,
            per_file_char_limit=28000,
        )
        attachment_prompt = attachment_context.get("text") or "(추가 참고 파일 없음)"

        coding_style = coding_rules_for_request(
            request=req.instruction,
            path=(req.path + ".py") if is_notebook else req.path,
            project_scope=False,
        )
        style_prompt = trim_style_prompt(
            coding_style.get("prompt") or "(적용 규칙 없음)"
        )

        if is_notebook:
            notebook_ctx = build_notebook_edit_context(
                req.content,
                req.active_cell_index,
            )
            target_number = notebook_ctx.active_cell_index + 1

            prompt = f"""
당신은 Jupyter Notebook Code 셀 편집 전용 AI입니다.

[AgentStudio 코딩 스타일 규칙]
{style_prompt}

[Notebook 파일 경로]
{req.path}

[사용자 수정 요청]
{req.instruction}

[Notebook Context]
아래 Context는 입력 예산 보호를 위해 outputs, execution result, metadata를 제거했습니다.
[TARGET]로 표시된 Code 셀 {target_number}만 수정 대상입니다.
{notebook_ctx.context_text}

[사용자 등록 참고 파일]
{attachment_prompt}

절대 규칙:
1. [TARGET] Code 셀 {target_number}에 들어갈 코드만 반환합니다.
2. Notebook 전체 JSON을 반환하지 않습니다.
3. 설명, Markdown, 코드펜스 없이 Code 셀 본문만 반환합니다.
4. [CONTEXT] 셀은 이해용이며 수정하거나 다시 출력하지 않습니다.
5. 현재 셀이 비어 있다면 사용자 요청과 주변 Markdown/힌트에 맞는 코드를 작성합니다.
6. 기존 동작을 불필요하게 변경하지 않습니다.
7. 사용자가 명시적으로 주석 삭제/수정 또는 셀 전체 교체를 요청하지 않았다면 TARGET 셀의 기존 주석, 학습용 힌트, TODO를 삭제하거나 치환하지 않습니다.
8. 기존 주석 아래에 코드를 작성하라는 요청이면 주석을 그대로 남기고 바로 아래에 코드를 추가합니다.
9. Python/Jupyter Notebook 문법으로 실행 가능한 코드를 작성합니다.
10. `%%writefile` 같은 Cell Magic을 사용할 경우 반드시 셀의 물리적 첫 줄에 배치하고, 그 앞에 빈 줄/주석/설명을 추가하지 않습니다.
"""

            if len(prompt) > MAX_FILE_EDIT_PROMPT_CHARS:
                raise HTTPException(
                    status_code=413,
                    detail={
                        "code": "CONTEXT_BUDGET_EXCEEDED",
                        "message": "Notebook 편집 Context가 안전 입력 예산을 초과했습니다. 현재 셀 주변 Context를 더 줄여야 합니다.",
                        "path": req.path,
                        "prompt_chars": len(prompt),
                        "estimated_tokens": approximate_tokens(prompt),
                        "active_cell_index": notebook_ctx.active_cell_index,
                        "included_cells": notebook_ctx.included_cells,
                    },
                )

            with usage_context(
                project_root=req.root,
                operation="notebook_cell_code_edit",
            ):
                result = await llm.ainvoke(prompt)

            cell_content = _strip_code_fence(
                result.content if hasattr(result, "content") else str(result)
            )
            if not cell_content:
                raise ValueError("코드 생성 모델이 빈 Notebook 셀 결과를 반환했습니다.")

            cell_content, preserved_comment_lines = _preserve_existing_comments(
                original=notebook_ctx.active_cell_source,
                proposed=cell_content,
                path=req.path + ".py",
                instruction=req.instruction,
            )

            merged_notebook = merge_notebook_cell(notebook_ctx, cell_content)
            proposal_explanation = await _build_edit_explanation(
                llm=llm,
                original=notebook_ctx.active_cell_source,
                proposed=cell_content,
                instruction=req.instruction,
                path=req.path,
                project_root=req.root,
            )
            reduced = max(notebook_ctx.original_chars - notebook_ctx.compact_chars, 0)
            message = (
                f"Notebook Cell {target_number} 코드 수정 제안을 만들었습니다. "
                f"LLM Context에서 outputs/metadata를 제외하고 {len(notebook_ctx.included_cells)}개 셀만 사용했습니다."
            )
            if preserved_comment_lines:
                message += f" 기존 주석 {preserved_comment_lines}줄을 보존했습니다."

            return {
                "ok": True,
                "code": merged_notebook,
                "cell_code": cell_content,
                "message": message,
                "proposal_explanation": proposal_explanation,
                "path": req.path,
                "saved": False,
                "preserved_comment_lines": preserved_comment_lines,
                "edit_scope": "notebook_cell",
                "active_cell_index": notebook_ctx.active_cell_index,
                "attachments": attachment_context.get("files") or [],
                "attachment_warnings": attachment_context.get("warnings") or [],
                "context_budget": {
                    "original_file_chars": notebook_ctx.original_chars,
                    "llm_context_chars": notebook_ctx.compact_chars,
                    "removed_chars": reduced,
                    "included_cells": notebook_ctx.included_cells,
                    "total_cells": notebook_ctx.total_cells,
                    "prompt_chars": len(prompt),
                    "estimated_tokens": approximate_tokens(prompt),
                },
            }

        prompt = f"""
당신은 코드 편집 전용 AI입니다.

[AgentStudio 코딩 스타일 규칙]
{style_prompt}

[파일 경로]
{req.path}

[사용자 수정 요청]
{req.instruction}

[현재 코드]
```text
{req.content}
```

[사용자 등록 참고 파일]
{attachment_prompt}

절대 규칙:
1. 사용자가 요청한 내용을 실제 코드에 반영합니다.
2. 기존 코드가 비어 있다면 요청에 필요한 코드를 새로 작성합니다.
3. 기존 동작을 불필요하게 변경하지 않습니다.
4. 전체 수정된 파일 내용을 반환합니다.
5. 설명, Markdown, 코드펜스 없이 코드 본문만 반환합니다.
6. Python 파일이면 실행 가능한 Python 문법을 사용합니다.
7. 사용자가 명시적으로 주석 삭제/수정 또는 파일 전체 교체를 요청하지 않았다면 기존 주석, 학습용 힌트, 설명 주석, TODO를 한 줄도 삭제하거나 다른 문장으로 치환하지 않습니다.
8. 사용자가 기존 주석 아래에 코드를 작성하라고 요청한 경우 주석 블록은 원문 그대로 남기고 그 바로 아래에 새 코드를 추가합니다.
9. 코드 추가를 위해 기존 주석 블록을 코드로 교체하지 않습니다.
"""

        # A raw 128k provider error is too late and too opaque.  Fail before
        # calling the model with a clear context-budget diagnostic.
        if len(prompt) > MAX_FILE_EDIT_PROMPT_CHARS:
            raise HTTPException(
                status_code=413,
                detail={
                    "code": "CONTEXT_BUDGET_EXCEEDED",
                    "message": "현재 파일의 LLM 입력 Context가 안전 예산을 초과했습니다. 파일을 나누거나 필요한 범위만 수정하세요.",
                    "path": req.path,
                    "prompt_chars": len(prompt),
                    "estimated_tokens": approximate_tokens(prompt),
                    "max_prompt_chars": MAX_FILE_EDIT_PROMPT_CHARS,
                },
            )

        with usage_context(
            project_root=req.root,
            operation="file_code_edit",
        ):
            result = await llm.ainvoke(prompt)

        content = _strip_code_fence(
            result.content if hasattr(result, "content") else str(result)
        )

        if not content:
            raise ValueError("코드 생성 모델이 빈 결과를 반환했습니다.")

        content, preserved_comment_lines = _preserve_existing_comments(
            original=req.content,
            proposed=content,
            path=req.path,
            instruction=req.instruction,
        )

        proposal_explanation = await _build_edit_explanation(
            llm=llm,
            original=req.content,
            proposed=content,
            instruction=req.instruction,
            path=req.path,
            project_root=req.root,
        )

        message = "코드 수정 제안을 만들었습니다."
        if preserved_comment_lines:
            message += f" 기존 주석 {preserved_comment_lines}줄을 보존했습니다."

        return {
            "ok": True,
            "code": content,
            "message": message,
            "proposal_explanation": proposal_explanation,
            "path": req.path,
            "saved": False,
            "preserved_comment_lines": preserved_comment_lines,
            "edit_scope": "file",
            "attachments": attachment_context.get("files") or [],
            "attachment_warnings": attachment_context.get("warnings") or [],
            "context_budget": {
                "prompt_chars": len(prompt),
                "estimated_tokens": approximate_tokens(prompt),
            },
        }

    except HTTPException:
        raise

    except Exception as e:
        detail = traceback.format_exc()
        message_text = str(e)
        lowered = message_text.casefold()
        if "context_length_exceeded" in lowered or "maximum context length" in lowered:
            raise HTTPException(
                status_code=413,
                detail={
                    "code": "MODEL_CONTEXT_OVERFLOW",
                    "message": "LLM 모델의 최대 Context 길이를 초과했습니다. AgentStudio가 요청을 축소해야 합니다.",
                    "exception": type(e).__name__,
                    "path": req.path,
                    "provider_message": message_text[-1600:],
                },
            ) from e

        raise HTTPException(
            status_code=500,
            detail={
                "message": f"코드 수정 모델 호출 실패: {e}",
                "exception": type(e).__name__,
                "path": req.path,
                "traceback": detail[-4000:],
            },
        ) from e




@router.post("/ai/project-edit")
async def ai_project_edit(req: ProjectCodeEditRequest):
    """
    프로젝트 전체 단위 자연어 코드 생성/수정.

    - 현재 프로젝트 구조를 분석
    - 관련 기존 파일 내용을 LLM Context로 제공
    - 필요한 신규 파일 생성
    - 필요한 기존 파일 전체 내용 갱신
    - 생성/수정 결과를 Frontend에 반환
    """
    from app.services.model_router import model_for_task, LLMTask
    import traceback

    project_root = Path(req.root).expanduser().resolve()

    if not project_root.exists() or not project_root.is_dir():
        raise HTTPException(
            status_code=404,
            detail=f"프로젝트 경로가 없습니다: {project_root}",
        )

    instruction = (req.instruction or "").strip()
    if not instruction:
        raise HTTPException(
            status_code=400,
            detail="프로젝트 작업 요청을 입력하세요.",
        )

    try:
        attachment_context = build_attachment_context(
            req.attachment_ids,
            purpose="프로젝트 단위 LLM 코드 편집 참고자료",
            total_char_limit=70000,
            per_file_char_limit=28000,
        )
        attachment_prompt = attachment_context.get("text") or "(추가 참고 파일 없음)"

        # 프로젝트 구조/관련 파일을 로컬 분석으로 먼저 좁힙니다.
        summary = await local_project_summary(
            str(project_root),
            instruction,
        )

        related = list(summary.get("related_files") or [])
        max_files = max(1, min(int(req.max_context_files or 10), 16))

        context_files = []
        seen = set()

        for item in related:
            relative = str(item.get("relative") or item.get("path") or "").strip()
            if not relative:
                continue

            normalized = relative.replace("\\", "/")
            if normalized in seen:
                continue
            seen.add(normalized)

            target = (project_root / normalized).resolve()

            try:
                target.relative_to(project_root)
            except ValueError:
                continue

            if not target.exists() or not target.is_file():
                continue

            # 바이너리/거대 파일은 코드 생성 Context에서 제외
            try:
                content = await read_file(str(target))
            except Exception:
                continue

            context_files.append({
                "path": normalized,
                "content": content[:14000],
            })

            if len(context_files) >= max_files:
                break

        scanned = await scan_project(str(project_root))
        structure = [
            str(x.get("relative") or "")
            for x in list(scanned.get("files") or [])[:300]
            if x.get("relative")
        ]

        llm = model_for_task(LLMTask.MULTI_FILE_CODE_CHANGE)

        coding_style = coding_rules_for_request(
            request=instruction,
            path="",
            project_scope=True,
        )
        agent_factory_policy = format_agent_factory_policy_for_prompt()

        # v5.218: 프로젝트 코딩 Prompt에서 참조하는 Agent Factory 설계
        # 변수를 반드시 이 요청 범위에서 먼저 구성합니다. 이전 구현은
        # factory_plan/factory_policies를 정의하지 않은 채 f-string에서
        # 참조하여 LLM 호출 전에 NameError가 발생했습니다.
        factory_plan = infer_fastapi_factory_plan(
            request=instruction,
            project_scope=True,
        )
        factory_policies = (
            format_factory_policies_for_prompt()
            if factory_plan.get("fastapi_candidate")
            else ""
        )
        factory_plan_prompt = json.dumps(
            factory_plan,
            ensure_ascii=False,
            indent=2,
        )

        context_text = "\n\n".join(
            f"### {item['path']}\n```text\n{item['content']}\n```"
            for item in context_files
        )

        prompt = f"""
당신은 THEANOVA AgentStudio의 프로젝트 단위 코딩 에이전트입니다.

[프로젝트 루트]
{project_root}

[AgentStudio Agent Factory 제작 기본 방향]
{agent_factory_policy}

[AgentStudio 코딩 스타일 규칙]
{coding_style.get("prompt") or "(적용 규칙 없음)"}

[Agent Factory 설계 정책]
적용 계획:
{factory_plan_prompt}

{factory_policies or "(FastAPI 설계 정책 비적용)"}

[프로젝트 요약]
{summary.get("summary", "")}

[기술 스택]
{json.dumps(summary.get("tech_stack", []), ensure_ascii=False)}

[현재 프로젝트 파일 구조]
{json.dumps(structure, ensure_ascii=False)}

[관련 기존 파일 내용]
{context_text or "(관련 기존 파일 없음 - 신규 프로젝트 파일 생성 가능)"}

[사용자 등록 참고 파일]
{attachment_prompt}

[사용자 프로젝트 요청]
{instruction}

반드시 아래 JSON 형식 하나만 반환하십시오.
Markdown 코드펜스나 설명문은 JSON 밖에 작성하지 마십시오.

{{
  "summary": "수행한 작업 요약",
  "primary_file": "완료 후 편집기에서 먼저 열 상대경로",
  "files": [
    {{
      "path": "프로젝트 루트 기준 상대경로",
      "action": "create 또는 update",
      "content": "파일의 전체 최종 내용"
    }}
  ]
}}

절대 규칙:
1. 요청을 실제 실행 가능한 프로젝트 코드로 구현합니다.
2. 필요한 신규 파일은 반드시 files에 create로 추가합니다.
3. 기존 파일 수정이 필요하면 update로 전체 최종 내용을 반환합니다.
4. path는 절대경로가 아니라 프로젝트 기준 상대경로만 사용합니다.
5. .venv, node_modules, .git 내부 파일은 만들거나 수정하지 않습니다.
6. 환경변수 비밀값/API Key를 코드에 하드코딩하지 않습니다.
7. Python 프로젝트라면 requirements.txt 또는 기존 의존성 파일도 필요 시 갱신합니다.
8. 에이전트 요청이면 실행 진입점, 설정, 핵심 서비스 코드가 빠지지 않도록 구성합니다.
9. 기존 프로젝트 구조를 가능한 존중합니다.
10. 파일 하나당 content는 일부 Patch가 아니라 저장할 전체 파일 내용입니다.
11. 사용자가 명시적으로 주석 삭제/수정 또는 파일 전체 교체를 요청하지 않았다면 기존 파일의 주석, 학습용 힌트, 설명 주석, TODO를 삭제하거나 치환하지 않습니다.
12. 기존 힌트/설명 아래에 구현 코드를 추가하는 요청이면 기존 주석 블록을 그대로 유지하고 그 아래에 코드를 삽입합니다.
"""

        with usage_context(
            project_root=str(project_root),
            operation="project_code_edit",
        ):
            result = await llm.ainvoke(prompt)
        raw = result.content if hasattr(result, "content") else str(result)
        raw = str(raw or "").strip()

        # JSON fenced response도 방어적으로 정리
        if raw.startswith("```"):
            lines = raw.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw = "\n".join(lines).strip()
            if raw.lower().startswith("json"):
                raw = raw[4:].lstrip()

        plan = json.loads(raw)

        file_plan = plan.get("files")
        if not isinstance(file_plan, list) or not file_plan:
            raise ValueError(
                "프로젝트 코딩 모델이 생성/수정할 파일 목록을 반환하지 않았습니다."
            )

        written = []

        for item in file_plan:
            relative = str(item.get("path") or "").strip()
            content = item.get("content")
            requested_action = str(item.get("action") or "").strip().lower()

            if not relative:
                continue
            if content is None:
                continue

            normalized = relative.replace("\\", "/").lstrip("/")
            parts = Path(normalized).parts

            if any(
                part in {".git", ".venv", "node_modules", "__pycache__"}
                for part in parts
            ):
                raise ValueError(
                    f"보호된 경로는 프로젝트 AI가 수정할 수 없습니다: {normalized}"
                )

            target = (project_root / normalized).resolve()

            try:
                target.relative_to(project_root)
            except ValueError as e:
                raise ValueError(
                    f"프로젝트 밖의 경로는 생성할 수 없습니다: {normalized}"
                ) from e

            existed = target.exists()
            actual_action = "update" if existed else "create"
            final_content = str(content)
            preserved_comment_lines = 0

            if existed:
                try:
                    original_content = await read_file(str(target))
                except Exception:
                    original_content = ""

                final_content, preserved_comment_lines = _preserve_existing_comments(
                    original=original_content,
                    proposed=final_content,
                    path=normalized,
                    instruction=instruction,
                )

            await write_file(
                str(target),
                final_content,
            )

            written.append({
                "path": normalized,
                "action": actual_action,
                "requested_action": requested_action or actual_action,
                "content": final_content,
                "bytes": len(final_content.encode("utf-8")),
                "preserved_comment_lines": preserved_comment_lines,
            })

        if not written:
            raise ValueError(
                "유효한 생성/수정 파일이 없습니다."
            )

        primary = str(plan.get("primary_file") or "").replace("\\", "/").strip()
        written_paths = [x["path"] for x in written]

        if primary not in written_paths:
            primary = written_paths[0]

        created = sum(1 for x in written if x["action"] == "create")
        updated = sum(1 for x in written if x["action"] == "update")

        return {
            "ok": True,
            "summary": str(plan.get("summary") or "프로젝트 코딩 작업을 완료했습니다."),
            "primary_file": primary,
            "files": written,
            "created_count": created,
            "updated_count": updated,
            "saved": True,
            "provider": getattr(llm, "last_provider", ""),
            "provider_task": LLMTask.MULTI_FILE_CODE_CHANGE.value,
            "attachments": attachment_context.get("files") or [],
            "attachment_warnings": attachment_context.get("warnings") or [],
        }

    except HTTPException:
        raise

    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "프로젝트 코딩 모델의 JSON 응답을 해석하지 못했습니다.",
                "exception": type(e).__name__,
                "raw_preview": raw[:3000] if "raw" in locals() else "",
            },
        ) from e

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"프로젝트 코딩 실패: {e}",
                "exception": type(e).__name__,
                "traceback": traceback.format_exc()[-5000:],
            },
        ) from e


@router.post("/command")
async def execute_terminal_command(payload: dict):
    """
    실제 프로젝트 PowerShell 명령 실행 API.

    프로젝트/터미널별로 다음 상태를 유지합니다.
    - 현재 작업 디렉터리(cwd)
    - .venv 기반 환경 변수
    - PowerShell 프롬프트
    """
    from pathlib import Path
    import asyncio
    import subprocess
    import traceback

    root = str(payload.get("root") or "").strip()
    command = str(payload.get("command") or "")
    terminal_id = str(payload.get("terminal_id") or "default").strip()

    if not root:
        raise HTTPException(status_code=400, detail="root가 필요합니다.")

    project_root = Path(root).expanduser().resolve()
    if not project_root.exists() or not project_root.is_dir():
        raise HTTPException(
            status_code=404,
            detail=f"프로젝트 경로가 없습니다: {project_root}",
        )

    key = _terminal_runtime_key(str(project_root), terminal_id)
    session = _TERMINAL_RUNTIME_SESSIONS.get(key)

    if not session:
        env = _terminal_runtime_env(project_root)
        session = {
            "root": str(project_root),
            "cwd": str(project_root),
            "env": env,
            "has_venv": bool(env.get("VIRTUAL_ENV")),
        }
        _TERMINAL_RUNTIME_SESSIONS[key] = session

    current_cwd = Path(session.get("cwd") or project_root).resolve()
    env = dict(session.get("env") or _terminal_runtime_env(project_root))

    has_venv = bool(env.get("VIRTUAL_ENV"))
    prefix = "(.venv) " if has_venv else ""

    if not command.strip():
        return {
            "ok": True,
            "output": "",
            "stdout": "",
            "stderr": "",
            "returncode": 0,
            "cwd": str(current_cwd),
            "prompt": f"{prefix}PS {current_cwd}>",
            "terminal_id": terminal_id,
        }

    # 명령 실행 뒤 Get-Location으로 최종 cwd를 반환해
    # cd / Set-Location을 다음 명령에도 유지한다.
    cwd_marker = "__THEANOVA_CWD__="
    ps_command = (
        "$ErrorActionPreference='Continue'; "
        + command
        + "; "
        + f'Write-Output ("{cwd_marker}" + (Get-Location).Path)'
    )

    log_dir = project_root / ".agentstudio" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "terminal.log"

    def _run():
        return subprocess.run(
            [
                "powershell.exe",
                "-NoLogo",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                ps_command,
            ],
            cwd=str(current_cwd),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )

    try:
        result = await asyncio.to_thread(_run)

        clean_stdout = []
        new_cwd = str(current_cwd)

        for line in result.stdout.splitlines():
            if line.startswith(cwd_marker):
                candidate = line[len(cwd_marker):].strip()
                if candidate:
                    new_cwd = candidate
            else:
                clean_stdout.append(line)

        session["cwd"] = new_cwd
        session["env"] = env

        stdout = "\n".join(clean_stdout)
        stderr = result.stderr or ""
        output_parts = []
        if stdout:
            output_parts.append(stdout)
        if stderr:
            output_parts.append(stderr)

        prompt = f"{prefix}PS {new_cwd}>"

        return {
            "ok": result.returncode == 0,
            "output": "\n".join(output_parts),
            "stdout": stdout,
            "stderr": stderr,
            "returncode": result.returncode,
            "cwd": new_cwd,
            "prompt": prompt,
            "terminal_id": terminal_id,
            "log_path": str(log_path),
        }

    except subprocess.TimeoutExpired as e:
        detail = f"터미널 명령 시간 초과: {command}\n{e}"
        log_path.write_text(detail, encoding="utf-8")
        raise HTTPException(
            status_code=504,
            detail={
                "message": detail,
                "log_path": str(log_path),
            },
        ) from e

    except Exception as e:
        detail = traceback.format_exc()
        try:
            log_path.write_text(detail, encoding="utf-8")
        except Exception:
            pass

        raise HTTPException(
            status_code=500,
            detail={
                "message": f"터미널 명령 실행 실패: {e}",
                "log_path": str(log_path),
            },
        ) from e



@router.post("/python/execute")
async def execute_python_editor_code(payload: dict):
    root = str(payload.get("root") or "").strip()
    code = str(payload.get("code") or "")
    relative_path = str(payload.get("relative_path") or "").strip()
    session_id = str(payload.get("session_id") or "default").strip() or "default"
    mode = str(payload.get("mode") or "selection").strip().lower()
    capture_last_expression = bool(payload.get("capture_last_expression"))
    notebook_mode = bool(payload.get("notebook_mode"))
    raw_cell_index = payload.get("cell_index")
    try:
        cell_index = int(raw_cell_index) if raw_cell_index is not None else None
    except (TypeError, ValueError):
        cell_index = None

    if not root:
        raise HTTPException(status_code=400, detail="root가 필요합니다.")
    if not code.strip():
        raise HTTPException(status_code=400, detail="실행할 Python 코드가 없습니다.")
    if relative_path and not relative_path.lower().endswith((".py", ".pyw", ".ipynb")):
        raise HTTPException(status_code=400, detail="Python(.py) 또는 Jupyter Notebook(.ipynb) 파일만 실행할 수 있습니다.")

    try:
        execution_env = await asyncio.to_thread(
            get_redis_python_script_runtime_env,
            root,
            relative_path,
        )
        result = await asyncio.to_thread(
            python_execution_manager.execute,
            root=root,
            code=code,
            relative_path=relative_path,
            session_id=session_id,
            reset=(mode == "full"),
            capture_last_expression=capture_last_expression,
            notebook_mode=notebook_mode,
            cell_index=cell_index,
            env_overrides=execution_env,
        )
        return result
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "message": f"Python 코드 실행 실패: {exc}",
                "exception": type(exc).__name__,
            },
        ) from exc




@router.post("/python/execute/stream")
async def execute_python_editor_code_stream(payload: dict):
    """Stream Jupyter-style rich display events while a Notebook cell runs."""
    root = str(payload.get("root") or "").strip()
    code = str(payload.get("code") or "")
    relative_path = str(payload.get("relative_path") or "").strip()
    session_id = str(payload.get("session_id") or "default").strip() or "default"
    mode = str(payload.get("mode") or "selection").strip().lower()
    capture_last_expression = bool(payload.get("capture_last_expression"))
    notebook_mode = bool(payload.get("notebook_mode"))
    raw_cell_index = payload.get("cell_index")
    try:
        cell_index = int(raw_cell_index) if raw_cell_index is not None else None
    except (TypeError, ValueError):
        cell_index = None

    if not root:
        raise HTTPException(status_code=400, detail="root가 필요합니다.")
    if not code.strip():
        raise HTTPException(status_code=400, detail="실행할 Python 코드가 없습니다.")
    if relative_path and not relative_path.lower().endswith((".py", ".pyw", ".ipynb")):
        raise HTTPException(status_code=400, detail="Python(.py) 또는 Jupyter Notebook(.ipynb) 파일만 실행할 수 있습니다.")

    execution_env = await asyncio.to_thread(
        get_redis_python_script_runtime_env,
        root,
        relative_path,
    )

    def packet_stream():
        try:
            for packet in python_execution_manager.execute_stream(
                root=root,
                code=code,
                relative_path=relative_path,
                session_id=session_id,
                reset=(mode == "full"),
                capture_last_expression=capture_last_expression,
                notebook_mode=notebook_mode,
                cell_index=cell_index,
                env_overrides=execution_env,
            ):
                yield json.dumps(packet, ensure_ascii=False) + "\n"
        except Exception as exc:
            packet = {
                "type": "result",
                "result": {
                    "ok": False,
                    "stdout": "",
                    "stderr": "",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                    "traceback": traceback.format_exc(),
                    "streaming": True,
                },
            }
            yield json.dumps(packet, ensure_ascii=False) + "\n"

    return StreamingResponse(
        packet_stream(),
        media_type="application/x-ndjson; charset=utf-8",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/source/debug/capability")
async def source_debug_capability_route(relative_path: str = Query(...)):
    return source_debug_capability(relative_path)


@router.post("/source/debug/run")
async def source_debug_run(payload: dict):
    root = str(payload.get("root") or "").strip()
    relative_path = str(payload.get("relative_path") or "").strip()
    code = str(payload.get("code") or "")
    if not root:
        raise HTTPException(status_code=400, detail="root가 필요합니다.")
    if not relative_path:
        raise HTTPException(status_code=400, detail="relative_path가 필요합니다.")
    if not code.strip():
        raise HTTPException(status_code=400, detail="실행할 소스 코드가 없습니다.")
    try:
        return await asyncio.to_thread(run_source_code, root=root, relative_path=relative_path, code=code, timeout=int(payload.get("timeout") or 120))
    except (ValueError, FileNotFoundError, PermissionError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"message": f"소스 실행 Adapter 실패: {exc}", "exception": type(exc).__name__}) from exc


@router.post("/python/debug/start")
async def start_python_source_debug(payload: dict):
    root = str(payload.get("root") or "").strip()
    code = str(payload.get("code") or "")
    relative_path = str(payload.get("relative_path") or "").strip()
    session_id = str(payload.get("session_id") or "default").strip() or "default"
    raw_cell_index = payload.get("cell_index")
    raw_breakpoints = payload.get("breakpoints") or []
    try:
        cell_index = max(0, int(raw_cell_index or 0))
    except (TypeError, ValueError):
        cell_index = 0
    if not root:
        raise HTTPException(status_code=400, detail="root가 필요합니다.")
    if not code.strip():
        raise HTTPException(status_code=400, detail="디버깅할 Python 코드가 없습니다.")
    if relative_path and not relative_path.lower().endswith((".py", ".ipynb")):
        raise HTTPException(status_code=400, detail="Python 디버깅은 .py/.pyw 또는 .ipynb 파일에서 사용할 수 있습니다.")
    breakpoints = []
    if isinstance(raw_breakpoints, list):
        for value in raw_breakpoints:
            try:
                line = int(value)
            except (TypeError, ValueError):
                continue
            if line > 0 and line not in breakpoints:
                breakpoints.append(line)
    try:
        execution_env = await asyncio.to_thread(get_redis_python_script_runtime_env, root, relative_path)
        return await asyncio.to_thread(
            python_execution_manager.debug_start,
            root=root,
            code=code,
            relative_path=relative_path,
            session_id=session_id,
            cell_index=cell_index,
            breakpoints=breakpoints,
            reset=False,
            env_overrides=execution_env,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"message": f"Python 소스 디버그 시작 실패: {exc}", "exception": type(exc).__name__}) from exc


@router.post("/python/debug/command")
async def command_notebook_cell_debug(payload: dict):
    root = str(payload.get("root") or "").strip()
    session_id = str(payload.get("session_id") or "default").strip() or "default"
    command = str(payload.get("command") or "").strip().lower()
    expression = str(payload.get("expression") or "")
    if not root:
        raise HTTPException(status_code=400, detail="root가 필요합니다.")
    if command not in {"continue", "step_over", "step_into", "step_out", "stop", "evaluate"}:
        raise HTTPException(status_code=400, detail="지원하지 않는 디버그 명령입니다.")
    try:
        return await asyncio.to_thread(
            python_execution_manager.debug_command,
            root=root,
            session_id=session_id,
            command=command,
            expression=expression,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"message": f"Notebook 디버그 명령 실패: {exc}", "exception": type(exc).__name__}) from exc


@router.get("/python/debug/status")
async def notebook_cell_debug_status(root: str = Query(...), session_id: str = Query("default")):
    try:
        return await asyncio.to_thread(python_execution_manager.debug_status, root, session_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/python/status")
async def python_editor_status(root: str = Query(...), session_id: str = Query("default")):
    try:
        return await asyncio.to_thread(
            python_execution_manager.status,
            root,
            session_id,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/python/reset")
async def reset_python_editor_session(payload: dict):
    root = str(payload.get("root") or "").strip()
    session_id = str(payload.get("session_id") or "default").strip() or "default"
    if not root:
        raise HTTPException(status_code=400, detail="root가 필요합니다.")
    reset = await asyncio.to_thread(
        python_execution_manager.reset,
        root,
        session_id,
    )
    return {"ok": True, "reset": reset, "session_id": session_id}

@router.post("/python/stop")
async def stop_python_editor_session(payload: dict):
    root = str(payload.get("root") or "").strip()
    session_id = str(payload.get("session_id") or "default").strip() or "default"
    if not root:
        raise HTTPException(status_code=400, detail="root가 필요합니다.")
    stopped = await asyncio.to_thread(
        python_execution_manager.stop,
        root,
        session_id,
    )
    return {
        "ok": True,
        "stopped": stopped,
        "cancelled": stopped,
        "session_id": session_id,
        "message": "Python 실행을 중지했습니다." if stopped else "현재 실행 중인 Python 세션이 없습니다.",
    }


@router.post("/terminal/completions")
async def terminal_completions(payload: dict):
    root = str(payload.get("root") or "").strip()
    cwd = str(payload.get("cwd") or "").strip() or None
    buffer = str(payload.get("buffer") or "")
    try:
        cursor = int(payload.get("cursor", len(buffer)))
    except Exception:
        cursor = len(buffer)

    if not root:
        raise HTTPException(status_code=400, detail="root가 필요합니다.")

    try:
        return await asyncio.to_thread(
            complete_terminal_input,
            root=root,
            cwd=cwd,
            buffer=buffer,
            cursor=cursor,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"터미널 경로가 없습니다: {e}") from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"터미널 자동완성 조회 실패: {e}") from e


@router.post("/terminal/project-bootstrap")
async def terminal_project_bootstrap(payload: dict):
    """
    선택한 프로젝트의 기본 PowerShell 터미널 초기 상태를 반환합니다.
    프로젝트 root로 이동하고 .venv가 있으면 활성화 명령을 함께 구성합니다.
    """
    from pathlib import Path

    root = str(payload.get("root") or "").strip()
    project_name = str(payload.get("project_name") or "").strip()

    if not root:
        raise HTTPException(status_code=400, detail="root가 필요합니다.")

    project_root = Path(root).expanduser().resolve()

    if not project_root.exists() or not project_root.is_dir():
        raise HTTPException(
            status_code=404,
            detail=f"프로젝트 경로가 없습니다: {project_root}",
        )

    venv_activate = project_root / ".venv" / "Scripts" / "Activate.ps1"
    has_venv = venv_activate.exists()

    # UI 표시용 프롬프트
    prompt_before = f"PS {project_root}>"
    prompt_after = (
        f"(.venv) PS {project_root}>"
        if has_venv
        else prompt_before
    )

    # 실제 PowerShell 초기화 명령
    safe_project_root = str(project_root).replace("'", "''")
    safe_venv_activate = str(venv_activate).replace("'", "''")

    commands = [
        f"Set-Location -LiteralPath '{safe_project_root}'"
    ]

    if has_venv:
        commands.append(
            "Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned"
        )
        commands.append(
            f"& '{safe_venv_activate}'"
        )

    return {
        "ok": True,
        "project_name": project_name or project_root.name,
        "root": str(project_root),
        "shell": "PowerShell",
        "has_venv": has_venv,
        "venv_activate": str(venv_activate) if has_venv else "",
        "commands": commands,
        "prompt_before": prompt_before,
        "prompt_after": prompt_after,
        "display": "\n".join([
            prompt_before,
            *(
                [
                    "(Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned) ; "
                    f"(& {venv_activate})",
                    prompt_after,
                ]
                if has_venv
                else []
            ),
        ]),
    }


@router.get("/project/git-info")
async def project_git_info(root: str):
    """선택 프로젝트의 Git 상태를 조회합니다."""
    from pathlib import Path
    import asyncio
    import subprocess

    project_root = Path(root).expanduser().resolve()
    if not project_root.exists() or not project_root.is_dir():
        raise HTTPException(status_code=404, detail=f"프로젝트 경로가 없습니다: {project_root}")

    async def git(*args: str):
        def _run():
            return subprocess.run(
                ["git", "-C", str(project_root), *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
            )
        return await asyncio.to_thread(_run)

    try:
        inside = await git("rev-parse", "--is-inside-work-tree")
    except FileNotFoundError:
        return {
            "ok": False,
            "is_git": False,
            "git_installed": False,
            "message": "Git 실행 파일을 찾을 수 없습니다.",
        }

    if inside.returncode != 0 or inside.stdout.strip().lower() != "true":
        return {
            "ok": True,
            "is_git": False,
            "git_installed": True,
            "message": "Git 저장소가 아닙니다.",
        }

    branch_r = await git("branch", "--show-current")
    origin_r = await git("remote", "get-url", "origin")
    head_r = await git("rev-parse", "--short", "HEAD")
    status_r = await git("status", "--porcelain")
    upstream_r = await git("rev-list", "--left-right", "--count", "@{upstream}...HEAD")

    branch = branch_r.stdout.strip()
    origin = origin_r.stdout.strip() if origin_r.returncode == 0 else ""
    head = head_r.stdout.strip() if head_r.returncode == 0 else ""
    changed_files = [line for line in status_r.stdout.splitlines() if line.strip()] if status_r.returncode == 0 else []

    behind = 0
    ahead = 0
    if upstream_r.returncode == 0:
        parts = upstream_r.stdout.strip().split()
        if len(parts) >= 2:
            try:
                behind = int(parts[0])
                ahead = int(parts[1])
            except ValueError:
                pass

    if ahead == 0 and behind == 0:
        sync_status = "up-to-date"
    elif ahead > 0 and behind == 0:
        sync_status = "ahead"
    elif behind > 0 and ahead == 0:
        sync_status = "behind"
    else:
        sync_status = "diverged"

    return {
        "ok": True,
        "is_git": True,
        "git_installed": True,
        "root": str(project_root),
        "branch": branch,
        "origin": origin,
        "head": head,
        "changed_count": len(changed_files),
        "ahead": ahead,
        "behind": behind,
        "sync_status": sync_status,
        "clean": len(changed_files) == 0,
    }



@router.post("/project/git-action")
async def project_git_action(payload: dict):
    from pathlib import Path
    import asyncio
    import subprocess
    import traceback

    root = str(payload.get("root") or "").strip()
    action = str(payload.get("action") or "").strip().lower()
    message = str(payload.get("message") or "").strip()

    if not root:
        raise HTTPException(status_code=400, detail="root가 필요합니다.")

    project_root = Path(root).expanduser().resolve()
    if not project_root.exists() or not project_root.is_dir():
        raise HTTPException(status_code=404, detail=f"프로젝트 경로가 없습니다: {project_root}")

    allowed = {"status","fetch","pull","add","commit","push","sync","log","diff"}
    if action not in allowed:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 Git 작업입니다: {action}")

    async def git(*args: str, timeout: int = 60):
        def _run():
            return subprocess.run(
                ["git", "-C", str(project_root), *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
        return await asyncio.to_thread(_run)

    check = await git("rev-parse", "--is-inside-work-tree")
    if check.returncode != 0 or check.stdout.strip().lower() != "true":
        raise HTTPException(status_code=400, detail="Git 저장소가 아닙니다.")

    def pack(name, result):
        return {
            "ok": result.returncode == 0,
            "action": name,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    log_dir = project_root / ".agentstudio" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "git_action.log"

    try:
        if action == "status":
            return pack(action, await git("status", "--short", "--branch"))
        if action == "fetch":
            return pack(action, await git("fetch", "--all", "--prune", timeout=120))
        if action == "pull":
            return pack(action, await git("pull", "--ff-only", timeout=120))
        if action == "add":
            return pack(action, await git("add", "-A"))
        if action == "commit":
            if not message:
                raise HTTPException(status_code=400, detail="커밋 메시지를 입력하세요.")
            return pack(action, await git("commit", "-m", message, timeout=120))
        if action == "push":
            return pack(action, await git("push", timeout=120))
        if action == "log":
            return pack(action, await git("log", "--oneline", "--decorate", "--graph", "-20"))
        if action == "diff":
            return pack(action, await git("diff", "--stat"))
        if action == "sync":
            if not message:
                raise HTTPException(status_code=400, detail="커밋 메시지를 입력하세요.")

            add_r = await git("add", "-A")
            if add_r.returncode != 0:
                return {"ok":False,"action":"sync","step":"add","stdout":add_r.stdout,"stderr":add_r.stderr}

            status_r = await git("status", "--porcelain")
            if status_r.returncode != 0:
                return {"ok":False,"action":"sync","step":"status","stdout":status_r.stdout,"stderr":status_r.stderr}

            pieces_out = []
            pieces_err = []

            if status_r.stdout.strip():
                commit_r = await git("commit", "-m", message, timeout=120)
                if commit_r.stdout.strip():
                    pieces_out.append("[commit]\n"+commit_r.stdout.strip())
                if commit_r.stderr.strip():
                    pieces_err.append("[commit]\n"+commit_r.stderr.strip())
                if commit_r.returncode != 0:
                    return {
                        "ok":False,"action":"sync","step":"commit",
                        "stdout":"\n".join(pieces_out),"stderr":"\n".join(pieces_err)
                    }

            push_r = await git("push", timeout=120)
            if push_r.stdout.strip():
                pieces_out.append("[push]\n"+push_r.stdout.strip())
            if push_r.stderr.strip():
                pieces_err.append("[push]\n"+push_r.stderr.strip())

            return {
                "ok": push_r.returncode == 0,
                "action":"sync",
                "step":"push",
                "stdout":"\n".join(pieces_out),
                "stderr":"\n".join(pieces_err),
            }

    except subprocess.TimeoutExpired as e:
        detail = f"Git 작업 시간 초과: {action}\n{e}"
        log_path.write_text(detail, encoding="utf-8")
        raise HTTPException(status_code=504, detail={"message":detail,"log_path":str(log_path)}) from e
    except HTTPException:
        raise
    except Exception as e:
        detail = traceback.format_exc()
        try:
            log_path.write_text(detail, encoding="utf-8")
        except Exception:
            pass
        raise HTTPException(
            status_code=500,
            detail={"message":f"Git 작업 실패: {action} / {e}","log_path":str(log_path)},
        ) from e


@router.post("/project/scan")
async def project_scan(req: ProjectAnalyzeRequest):
    root = register_runtime_project_root(req.project_root)
    return await scan_project(root)

@router.post("/project/analyze")
async def project_analyze(req: ProjectAnalyzeRequest):
    root = register_runtime_project_root(req.project_root)
    return await local_project_summary(root, req.request)


@router.get("/project/high-speed-analysis/status")
async def project_high_speed_analysis_status():
    """Return the local analysis acceleration capabilities without invoking an LLM."""
    return high_speed_analysis_status()


@router.post("/project/high-speed-analysis")
async def project_high_speed_analysis(req: ProjectAnalyzeRequest):
    """Run the same accelerated candidate-compression path used by design/build workflows."""
    root = register_runtime_project_root(req.project_root)
    return await local_project_summary(root, req.request)


@router.post("/project/adaptive-report")
async def project_adaptive_report(req: ProjectAnalyzeRequest):
    """프로젝트 소스에서 Workflow/Report/Architecture/PPT용 동적 Snapshot을 생성합니다.

    LLM 추측이 아니라 현재 프로젝트 파일에서 실제로 감지한 Framework/DB/Agent/MCP/Infra만
    사용합니다. 프로젝트 로드 직후와 PPT Export 전에 같은 Snapshot을 재사용할 수 있습니다.
    """
    root = register_runtime_project_root(req.project_root)
    return await build_project_adaptive_report(root, req.request)

@router.post("/tool/analyze")
async def tool_analyze(req: ToolAnalyzeRequest):
    return analyze_tool(req.name, req.description).__dict__

@router.post("/mcp/discover")
async def mcp_discover(req: MCPDiscoverRequest):
    return await discover_streamable_http(req.endpoint)

@router.post("/mcp/servers")
async def create_mcp_server(req: MCPServerCreate):
    async with SessionLocal() as db:
        row = MCPServer(
            name=req.name,
            endpoint=req.endpoint,
            trust_level=req.trust_level.upper(),
            allow_read_without_prompt=req.allow_read_without_prompt,
            allow_write_without_prompt=req.allow_write_without_prompt,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        return {"id": row.id, "name": row.name, "endpoint": row.endpoint}

@router.get("/mcp/servers")
async def list_mcp_servers():
    async with SessionLocal() as db:
        rows = (await db.execute(select(MCPServer))).scalars().all()
        return [{
            "id": x.id, "name": x.name, "endpoint": x.endpoint,
            "status": x.last_status, "trust_level": x.trust_level,
            "supports_tool_list_changed": x.supports_tool_list_changed
        } for x in rows]

@router.post("/mcp/servers/{server_id}/sync")
async def sync_mcp_server(server_id: int):
    return await mcp_registry_monitor.sync_server(server_id)

@router.get("/mcp/tools")
async def list_mcp_tools(server_id: int | None = None):
    async with SessionLocal() as db:
        stmt = select(ToolRecord)
        if server_id is not None:
            stmt = stmt.where(ToolRecord.mcp_server_id == server_id)
        rows = (await db.execute(stmt)).scalars().all()
        return [{
            "id": x.id, "server_id": x.mcp_server_id, "name": x.name,
            "category": x.category, "capability": x.capability,
            "risk_level": x.risk_level, "enabled": x.enabled,
            "requires_confirmation": x.requires_confirmation,
        } for x in rows]

@router.post("/memory")
async def memory_add(req: MemoryAddRequest):
    memory_id = await add_memory(
        req.content, req.memory_type, req.key, req.project_id, req.metadata
    )
    return {"id": memory_id}

@router.post("/memory/search")
async def memory_search(req: MemorySearchRequest):
    return await search_memory(req.query, req.project_id, req.memory_type, req.limit)


@router.post("/chat/simple")
async def simple_chat(req: ChatRequest):
    return {"answer": await answer_simple_question(req.message)}

@router.post("/tool/analyze-semantic")
async def tool_analyze_semantic(req: ToolAnalyzeRequest):
    return await analyze_tool_with_llm(req.name, req.description)

@router.post("/search")
async def search(req: SearchRequest):
    return await web_search(req.query)

@router.post("/git/status")
async def get_git_status(req: FileRequest):
    return await git_status(req.path)

@router.post("/git/diff")
async def get_git_diff(req: FileRequest):
    return await git_diff(req.path)

@router.post("/git/checkpoint")
async def create_git_checkpoint(req: FileRequest):
    return await checkpoint(req.path)


def _build_interview_requirement_context(
    request: str,
    interview_messages: list[dict],
    confirmed_requirements: dict,
) -> str:
    rows = [
        "[현재 사용자의 개발 요청]",
        request.strip(),
        "",
        "[인터뷰에서 확정된 요구사항]",
        json.dumps(
            confirmed_requirements or {},
            ensure_ascii=False,
            indent=2,
        ),
        "",
        "[인터뷰 전체 대화]",
    ]

    for item in interview_messages or []:
        role = str(item.get("role") or "").strip()
        content = str(item.get("content") or "").strip()

        if not content:
            continue

        rows.append(
            f"{role.upper()}: {content}"
        )

    rows.extend([
        "",
        "[Workflow 설계 절대 규칙]",
        "1. 위에서 확정된 요구사항을 누락하지 않습니다.",
        "2. 보안/검증 단계는 일반 처리 단계에 합쳐서 생략하지 않습니다.",
        "3. MCP Client, Transport, MCP Server, Tool 호출이 요구되면 각각 설계에 드러나게 합니다.",
        "4. LLM Provider 전환 요구가 있으면 Provider 선택/설정 단계를 반영합니다.",
        "5. UI 표시와 파일 저장처럼 결과 경로가 둘 이상이면 분기 단계로 표현합니다.",
        "6. 재시도와 실패 처리를 별도 정책/분기로 설계합니다.",
        "7. 단순히 3~4단계로 축약하지 말고 실제 실행 가능한 업무 Workflow를 설계합니다.",
        "8. confirmed_requirements.ui_layout이 있으면 선택한 Header/Sidebar/Footer/User Menu/Main Layout/Theme/Components를 UI 파일 구조와 코드 생성 계획에 반드시 반영합니다.",
        "9. UI Layout을 사용하는 Agent는 메뉴/탭/페이지 이동으로 실행 중 Agent 작업을 중단하지 않습니다. Agent Runtime은 UI component lifecycle과 분리하고 session_id/run_id 기반 Backend Runtime으로 유지합니다.",
        "10. ui_layout의 restore_screen_state/restore_scroll_position/restore_draft_input/restore_selection_state/screen_restore_mode 설정을 Frontend 상태 저장·복원 설계에 반영합니다.",
        "11. ui_layout의 show_running_tasks/runtime_status_position/notify_agent_complete/notify_agent_failure/run_item_navigate를 실행 상태 UI와 알림 설계에 반영합니다. WebSocket/SSE는 자동 재연결, 현재 run 재조회, 누락 이벤트 재동기화를 기본 정책으로 설계합니다.",
        "12. ui_layout.theme가 custom이면 theme_id/theme_name/theme_tokens/component_rules/layout_rules를 Design Token의 단일 기준으로 사용하고 React/TypeScript CSS 변수 또는 Theme Provider에 반영합니다. 참조 사이트의 로고·문구·이미지·고유 콘텐츠를 복제하지 말고 색상·타이포그래피·간격·Radius·Shadow·Component 스타일 특성만 적용합니다.",
    ])

    return "\n".join(rows)


def _normalize_latest_confirmed_requirement_conflicts(value: dict | None) -> dict:
    """Resolve deterministic requirement conflicts before workflow design.

    v5.393: later explicit Frontend requirements must supersede an older
    Headless layout selection.  Keeping both values made the right-side
    requirements card continue to show Headless and allowed code generation to
    reuse a stale no-UI design even after the user asked for React/TypeScript.
    """
    source = value if isinstance(value, dict) else {}
    try:
        normalized = json.loads(json.dumps(source, ensure_ascii=False, default=str))
    except Exception:
        normalized = dict(source)

    frontend = normalized.get("frontend") if isinstance(normalized.get("frontend"), dict) else {}
    ui_text = str(normalized.get("ui") or "").strip()
    framework = str(frontend.get("framework") or "").strip()
    headless = frontend.get("headless") is True
    explicit_frontend = bool(framework or ui_text)
    non_headless_frontend = bool(
        explicit_frontend
        and not headless
        and "headless" not in ui_text.casefold()
        and "ui 없음" not in ui_text.casefold()
        and "화면 없음" not in ui_text.casefold()
    )

    layout = normalized.get("ui_layout") if isinstance(normalized.get("ui_layout"), dict) else {}
    layout_headless = bool(layout.get("enabled") is False or str(layout.get("template_id") or "") == "headless_agent")
    if non_headless_frontend and layout_headless:
        previous = str(layout.get("name") or layout.get("template_name") or "UI 없음 / Headless Agent")
        normalized["ui_layout"] = None
        history = normalized.get("superseded_requirements")
        if not isinstance(history, list):
            history = []
        history.append({
            "key": "ui_layout",
            "previous": previous,
            "replacement": ui_text or framework,
            "reason": "최신 사용자 Frontend 요구사항이 이전 Headless UI와 충돌하여 대체되었습니다.",
            "source": "SERVER_CONFLICT_VALIDATOR",
        })
        normalized["superseded_requirements"] = history[-20:]

    return normalized


@router.post("/workflow/preview")
async def workflow_preview(req: WorkflowPreviewRequest):
    if not req.request.strip():
        return {
            "ok": False,
            "message": "에이전트 개발 요청 내용을 입력하세요.",
        }

    project_context = {}

    if req.project_root.strip():
        try:
            project_context = await local_project_summary(
                req.project_root,
                req.request,
            )
        except Exception:
            project_context = {
                "project_root": req.project_root,
                "analysis_error": "프로젝트 분석 없이 Workflow 설계를 계속합니다.",
            }

    confirmed_requirements = _normalize_latest_confirmed_requirement_conflicts(req.confirmed_requirements)
    full_request = _build_interview_requirement_context(
        request=req.request,
        interview_messages=req.interview_messages,
        confirmed_requirements=confirmed_requirements,
    )
    attachment_context = build_requirements_attachment_context(
        req.attachment_ids,
        purpose="Agent Workflow 설계 참고자료",
    )
    attachment_memory = _merge_interview_attachment_memory(
        req.attachment_memory,
        attachment_context.get("text") or "",
    )
    if attachment_memory:
        full_request += (
            "\n\n[인터뷰 참고자료 세션 메모리]\n"
            + attachment_memory
            + "\n\n중요: 위 참고자료는 내부 분석 근거이며 원문/비밀값을 사용자 출력에 복사하지 않습니다."
        )

    previous_design = req.previous_design if isinstance(req.previous_design, dict) else {}
    previous_confirmed = previous_design.get("confirmed_requirements") or {}

    preview_recovery = None
    if req.safe_mode:
        design = build_safe_agent_factory_design(
            full_request,
            reason="사용자가 AI Provider 오류 복구를 위해 안전 설계를 선택했습니다.",
        )
        preview_recovery = dict(design.get("recovery") or {})
    else:
        try:
            with usage_context(
                project_root=req.project_root,
                operation="workflow_preview",
            ):
                design = await design_agent_factory_incremental(
                    request=full_request,
                    project_context=project_context,
                    provider=req.provider,
                    previous_design=previous_design,
                    previous_confirmed_requirements=previous_confirmed,
                    current_confirmed_requirements=confirmed_requirements,
                    interview_messages=req.interview_messages,
                )
        except Exception as preview_exc:
            # v5.393: Workflow/DB 설계 화면을 dead-end 오류로 끝내지 않습니다.
            # Provider/네트워크 오류가 나도 검증된 deterministic 설계와 DB Module
            # Registry를 반환해 사용자가 DB를 확인하고 계속 진행할 수 있습니다.
            design = build_safe_agent_factory_design(
                full_request,
                reason=f"{type(preview_exc).__name__}: {preview_exc}",
            )
            preview_recovery = dict(design.get("recovery") or {})

    design["confirmed_requirements"] = confirmed_requirements
    design["interview_messages"] = list(req.interview_messages or [])

    selected_ui_layout = (confirmed_requirements or {}).get("ui_layout") or {}
    if isinstance(selected_ui_layout, dict) and selected_ui_layout.get("template_id"):
        requirement_spec = design.setdefault("requirement_spec", {})
        if isinstance(requirement_spec, dict):
            requirement_spec["ui_layout"] = selected_ui_layout
        design.setdefault("design_runtime", {})["selected_ui_layout"] = selected_ui_layout

    target = design.get("target_agent_workflow") or {}

    # Workflow가 지나치게 축약됐을 때 UI에서 확인할 수 있도록 품질 정보 제공
    steps = list(target.get("steps") or [])
    quality = {
        "step_count": len(steps),
        "has_branch": bool(target.get("branches")),
        "has_retry": bool(target.get("retry_policy")),
        "has_failure_policy": bool(target.get("failure_policy")),
        "uses_full_interview_context": True,
        "warning": (
            "Workflow 단계가 너무 적습니다. 인터뷰 요구사항 누락 여부를 확인하세요."
            if len(steps) < 6
            else ""
        ),
    }

    return {
        "ok": True,
        "request": req.request,
        "full_request": full_request,
        "interview_context": full_request,
        "interview_messages": req.interview_messages,
        "confirmed_requirements": req.confirmed_requirements,
        "attachments": attachment_context.get("files") or [],
        "attachment_warnings": attachment_context.get("warnings") or [],
        "attachment_memory": attachment_memory,
        "attachments_consumed": bool(req.attachment_ids),
        "target_agent_workflow": target,
        "requirement_spec": design.get("requirement_spec") or {},
        "capability_plan": design.get("capability_plan") or {},
        "tool_mcp_plan": design.get("tool_mcp_plan") or {},
        "agent_architecture": design.get("agent_architecture") or {},
        "database_plan": design.get("database_plan") or {},
        "file_plan": design.get("file_plan") or {},
        "environment_plan": design.get("environment_plan") or {},
        "settings_plan": design.get("settings_plan") or {},
        "design_runtime": design.get("design_runtime") or {},
        "workflow_quality": quality,
        "recovery": preview_recovery or design.get("recovery") or {},
    }


@router.post("/database-design/preview")
async def database_design_preview(req: DatabaseDesignPreviewRequest):
    request_text = str(req.request or "").strip()
    if not request_text:
        return {
            "ok": True,
            "database_plan": {
                "enabled": False,
                "engine": "none",
                "strategy": "요구사항을 입력하면 DB 초안을 실시간으로 표시합니다.",
                "modules": [],
                "tables": [],
                "relationships": [],
                "validation": {"valid": True, "errors": [], "warnings": []},
                "confirmed": False,
                "finalized": False,
            },
            "ddl_preview": "",
        }

    # 실시간 Preview는 LLM을 호출하지 않습니다. 대화가 바뀔 때만 검증된
    # Module Registry를 결정적으로 재조립하여 빠르게 보여 줍니다.
    design_context = {
        "requirement_spec": {
            "goal": str((req.confirmed_requirements or {}).get("original_request") or "")
        },
        "capability_plan": {},
        "agent_architecture": {},
    }
    plan = build_database_plan(request_text, design_context)

    lower = request_text.casefold()
    technologies: list[str] = []
    if plan.get("enabled"):
        technologies.append("PostgreSQL")
    if "pgvector" in lower or "vector" in lower or "벡터" in lower or "embedding" in lower or "임베딩" in lower:
        technologies.append("pgvector")
    redis_enabled = "redis" in lower
    if redis_enabled:
        technologies.append("Redis")

    redis_keys: list[dict] = []
    if redis_enabled:
        redis_keys.append({"key": "session:{session_id}", "purpose": "사용자 세션", "ttl": "세션 정책"})
        if any(token in lower for token in ("검색", "search")):
            redis_keys.extend([
                {"key": "search:{query_hash}", "purpose": "검색 결과 캐시", "ttl": "5분 권장"},
                {"key": "recent_search:{customer_id}", "purpose": "최근 검색", "ttl": "업무 정책"},
            ])
        if any(token in lower for token in ("장바구니", "cart")):
            redis_keys.append({"key": "cart:{customer_id}", "purpose": "임시 장바구니", "ttl": "사용자 정책"})
        if any(token in lower for token in ("주문 draft", "order draft", "주문 임시", "주문")):
            redis_keys.append({"key": "order_draft:{session_id}", "purpose": "주문 확인 전 Draft", "ttl": "30분 권장"})

    plan["technologies"] = list(dict.fromkeys(technologies))
    plan["redis_plan"] = {
        "enabled": redis_enabled,
        "keys": redis_keys,
        "policy": "Redis는 PostgreSQL 업무 원장과 분리하여 세션/캐시/임시 상태에 사용합니다." if redis_enabled else "",
    }

    finalized_copy = finalize_database_plan(plan)
    return {
        "ok": True,
        "database_plan": plan,
        "ddl_preview": str(finalized_copy.get("ddl") or ""),
        "preview": True,
        "message": "요구사항 기준 실시간 DB 초안을 갱신했습니다.",
    }


@router.post("/database-design/finalize")
async def database_design_finalize(req: DatabaseDesignFinalizeRequest):
    plan = finalize_database_plan(req.database_plan or {})
    validation = plan.get("validation") or {}
    return {
        "ok": bool(validation.get("valid", True)),
        "database_plan": plan,
        "validation": validation,
        "message": (
            "DB 설계 검증 및 PostgreSQL DDL 확정이 완료되었습니다."
            if validation.get("valid", True)
            else "DB 설계 검증에 실패했습니다. 오류를 수정한 뒤 다시 확정해 주세요."
        ),
    }


@router.get("/workflow/definition")
async def workflow_definition():
    phases = [
        {
            "id": "DISCOVER",
            "title": "요구 이해",
            "subtitle": "무엇을 왜 만들지 정리합니다.",
            "icon": "◎",
            "nodes": [
                {
                    "name": "requirement_analysis",
                    "label": "요구사항 분석",
                    "description": "사용자 목표·입력·출력·제약을 구조화",
                    "icon": "✦",
                },
                {
                    "name": "analyze_project",
                    "label": "프로젝트 분석",
                    "description": "기존 구조와 관련 파일을 파악",
                    "icon": "⌕",
                },
            ],
        },
        {
            "id": "DESIGN",
            "title": "Agent 설계",
            "subtitle": "기능·도구·구조·업무 흐름을 결정합니다.",
            "icon": "◇",
            "nodes": [
                {
                    "name": "capability_design",
                    "label": "기능 설계",
                    "description": "Agent가 가져야 할 핵심 능력을 정의",
                    "icon": "✣",
                },
                {
                    "name": "tool_mcp_decision",
                    "label": "Tool / MCP 판단",
                    "description": "외부 기능을 어떤 방식으로 연결할지 결정",
                    "icon": "⚙",
                },
                {
                    "name": "agent_architecture",
                    "label": "Agent 아키텍처",
                    "description": "컴포넌트·상태·인터페이스를 설계",
                    "icon": "⬡",
                },
                {
                    "name": "database_design",
                    "label": "DB Module 설계",
                    "description": "Core + 기능별 Module + Custom Entity를 조립하고 PK/FK를 검증",
                    "icon": "▦",
                    "accent": "target",
                },
                {
                    "name": "target_workflow_design",
                    "label": "대상 Agent Workflow",
                    "description": "생성될 Agent의 실제 업무 흐름을 설계",
                    "icon": "⇢",
                    "accent": "target",
                },
                {
                    "name": "project_file_plan",
                    "label": "파일 계획",
                    "description": "수정/생성할 파일과 책임을 배치",
                    "icon": "▤",
                },
                {
                    "name": "settings_requirement_analysis",
                    "label": "설정 요구 분석",
                    "description": "런타임에서 변경할 설정과 Secret을 추출",
                    "icon": "⚙",
                    "accent": "target",
                },
                {
                    "name": "settings_schema_design",
                    "label": "설정 Schema",
                    "description": "타입·기본값·검증·Secret 계약 설계",
                    "icon": "▦",
                    "accent": "target",
                },
                {
                    "name": "settings_ui_design",
                    "label": "설정 UI 설계",
                    "description": "Agent에 필요한 설정 화면만 구성",
                    "icon": "▣",
                    "accent": "target",
                },
            ],
        },
        {
            "id": "BUILD",
            "title": "제작",
            "subtitle": "안전하게 코드를 만들고 실행 환경을 구성합니다.",
            "icon": "⌘",
            "nodes": [
                {
                    "name": "checkpoint",
                    "label": "체크포인트",
                    "description": "변경 전 복구 지점을 준비",
                    "icon": "◈",
                },
                {
                    "name": "approval",
                    "label": "실행 승인",
                    "description": "실제 파일 변경 전에 실행 여부 확인",
                    "icon": "✓",
                },
                {
                    "name": "code_generation",
                    "label": "코드 생성 / 수정",
                    "description": "기존 파일 수정과 신규 파일 생성",
                    "icon": "</>",
                },
                {
                    "name": "settings_generator",
                    "label": "Settings Generator",
                    "description": "Backend Settings API와 React 설정 화면 자동 생성",
                    "icon": "⚙",
                    "accent": "target",
                },
                {
                    "name": "settings_validation",
                    "label": "설정 검증",
                    "description": "파일 생성·Secret 마스킹·설정 계약 검증",
                    "icon": "✓",
                    "accent": "target",
                },
                {
                    "name": "build_artifact_validation",
                    "label": "산출물 / 코딩 스타일 검증",
                    "description": "계획 파일 누락·Placeholder·등록 Coding Style 위반을 검사",
                    "icon": "✓",
                    "accent": "target",
                },
                {
                    "name": "as_built_architecture",
                    "label": "As-Built 아키텍처",
                    "description": "생성된 실제 파일·클래스·함수·Framework 증거로 구현 구조를 역분석",
                    "icon": "◎",
                    "accent": "target",
                },
                {
                    "name": "architecture_conformance",
                    "label": "Architecture Conformance",
                    "description": "Design ↔ As-Built 일치도를 검증하고 차이가 있으면 자동 보정",
                    "icon": "≍",
                    "accent": "target",
                },
                {
                    "name": "environment_configuration",
                    "label": "환경 구성",
                    "description": "패키지·환경변수·서비스 설정을 구성",
                    "icon": "⚡",
                },
            ],
        },
        {
            "id": "VERIFY",
            "title": "검증 & 완성",
            "subtitle": "실행하고 실패하면 수정한 뒤 완성 상태를 확인합니다.",
            "icon": "✓",
            "nodes": [
                {
                    "name": "test",
                    "label": "테스트",
                    "description": "실행·문법·기능 검증",
                    "icon": "▶",
                },
                {
                    "name": "debug/repair",
                    "label": "디버그 / 복구",
                    "description": "실패 원인을 분석하고 재수정",
                    "icon": "↻",
                    "accent": "warning",
                },
                {
                    "name": "package_completion",
                    "label": "완성 패키지",
                    "description": "생성·수정 결과와 실행 상태 정리",
                    "icon": "▣",
                },
                {
                    "name": "review",
                    "label": "최종 검토",
                    "description": "완료 조건 충족 여부 확인",
                    "icon": "★",
                },
            ],
        },
    ]

    return {
        "ok": True,
        "factory_workflow": [
            node["name"]
            for phase in phases
            for node in phase["nodes"]
        ],
        "factory_phases": phases,
        "repair_loop": [
            "test",
            "debug/repair",
            "code_generation",
            "environment_configuration",
            "test",
        ],
        "target_agent_workflow": (
            "각 Workflow 실행 State의 target_agent_workflow 필드에 "
            "별도 설계 결과로 저장됩니다."
        ),
    }


def _agent_design_checkpoint_path(root: Path) -> Path:
    return root / "reports" / "agentstudio_design_checkpoint.json"


def _safe_resume_value(value):
    """Persist only resumable design/build context and redact secret-looking text."""
    secret_keys = {
        "password", "passwd", "pwd", "api_key", "apikey", "access_token",
        "refresh_token", "token", "secret", "authorization", "private_key",
    }
    if isinstance(value, dict):
        clean = {}
        for key, item in value.items():
            name = str(key or "")
            if name.lower() in secret_keys:
                clean[name] = "***"
            else:
                clean[name] = _safe_resume_value(item)
        return clean
    if isinstance(value, list):
        return [_safe_resume_value(item) for item in value]
    if isinstance(value, str):
        return redact_sensitive_text(value)
    return value


def _compact_resume_workflow_state(state: dict) -> dict:
    if not isinstance(state, dict):
        return {}
    keep = (
        "thread_id", "project_root", "request", "status", "error",
        "requirement_spec", "capability_plan", "tool_mcp_plan",
        "agent_architecture", "database_plan", "target_agent_workflow",
        "file_plan", "environment_plan", "settings_plan", "settings_schema",
        "settings_ui_plan", "as_built_architecture", "architecture_conformance",
        "build_artifact_validation", "code_plan_validation", "settings_validation_result",
        "debug_iteration", "debug_history", "patch_result", "test_result",
        "diagnostic_run_id", "diagnostic_status", "diagnostic_failure_stage",
        "diagnostic_failure_reason", "diagnostic_generated_at", "run_started_at",
    )
    compact = {key: state.get(key) for key in keep if key in state}
    if isinstance(compact.get("debug_history"), list):
        compact["debug_history"] = compact["debug_history"][-8:]
    if isinstance(compact.get("patch_result"), list):
        compact["patch_result"] = compact["patch_result"][-80:]
    return _safe_resume_value(compact)


def _read_json_dict(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _hydrate_saved_database_sql(root: Path, snapshot: dict, workflow_state: dict) -> dict:
    """Restore finalized DB DDL from the generated migration when checkpoint JSON is stale.

    A DB design can be finalized moments after the design checkpoint autosave. If the
    browser is closed during that narrow window, the migration SQL is authoritative and
    must be reattached when the project is opened again. Only files inside project root
    are eligible.
    """
    safe_snapshot = dict(snapshot or {})
    preview = dict(safe_snapshot.get("workflow_preview") or {})
    state = dict(workflow_state or {})

    # Legacy workflow_state can contain the design even when the UI checkpoint does not.
    for key in ("target_agent_workflow", "agent_architecture", "file_plan"):
        if not preview.get(key) and state.get(key):
            preview[key] = _safe_resume_value(state.get(key))

    plan = dict(preview.get("database_plan") or state.get("database_plan") or {})

    # Even very old projects can have a finalized migration without a serialized
    # database_plan. Treat the generated migration as the durable DB artifact and
    # rebuild a minimal plan so the Workflow/DB SQL panes are not blank after load.
    ddl = str(plan.get("ddl") or plan.get("ddl_preview") or "").strip()
    if not ddl:
        candidates: list[str] = []
        for item in list(plan.get("migration_files") or []):
            if isinstance(item, dict):
                value = str(item.get("path") or "").strip()
            else:
                value = str(item or "").strip()
            if value and value not in candidates:
                candidates.append(value)
        for default_path in (
            "backend/migrations/001_initial_schema.sql",
        ):
            if default_path not in candidates:
                candidates.append(default_path)

        root_resolved = root.resolve()
        for relative in candidates:
            try:
                candidate = (root_resolved / relative).resolve()
                if candidate != root_resolved and root_resolved not in candidate.parents:
                    continue
                if not candidate.is_file():
                    continue
                text = candidate.read_text(encoding="utf-8", errors="replace").strip()
                if not text:
                    continue
                ddl = text
                plan["ddl"] = text
                plan["ddl_preview"] = text
                plan["confirmed"] = True
                plan["finalized"] = True
                if not plan.get("migration_files"):
                    plan["migration_files"] = [{
                        "path": str(candidate.relative_to(root_resolved)).replace("\\", "/"),
                        "purpose": "복원된 PostgreSQL DB Migration",
                    }]
                break
            except Exception:
                continue

    if ddl:
        plan.setdefault("enabled", True)
        plan.setdefault("engine", "postgresql")
        plan.setdefault("database", "PostgreSQL")
        plan["confirmed"] = True
        plan["finalized"] = True
        plan.setdefault("ddl", ddl)
        plan.setdefault("ddl_preview", ddl)
    if plan:
        preview["database_plan"] = _safe_resume_value(plan)
    safe_snapshot["workflow_preview"] = preview
    return _safe_resume_value(safe_snapshot)


# v5.371 Failed Build Redevelopment
_FAILURE_RESUME_PREVIOUS_NODE = {
    "requirement_analysis": "requirement_analysis",
    "analyze_project": "requirement_analysis",
    "capability_design": "analyze_project",
    "tool_mcp_decision": "capability_design",
    "agent_architecture": "tool_mcp_decision",
    "database_design": "agent_architecture",
    "target_workflow_design": "database_design",
    "project_file_plan": "target_workflow_design",
    "requirement_coverage_gate": "project_file_plan",
    "settings_requirement_analysis": "requirement_coverage_gate",
    "settings_schema_design": "settings_requirement_analysis",
    "settings_ui_design": "settings_schema_design",
    "checkpoint": "settings_ui_design",
    "approval": "checkpoint",
    # A code-generation failure must not re-run approval/requirements.
    "code_generation": "code_generation",
    "settings_generator": "code_generation",
    "settings_validation": "settings_generator",
    "build_artifact_validation": "settings_validation",
    "as_built_architecture": "build_artifact_validation",
    "architecture_conformance": "as_built_architecture",
    "environment_configuration": "architecture_conformance",
    "test": "environment_configuration",
    "debug": "test",
    "package_completion": "test",
    "review": "package_completion",
}


def _is_failed_agent_build_status(status: str) -> bool:
    value = str(status or "").strip().upper()
    if not value:
        return False
    if value in {"SUCCESS", "COMPLETED", "TEST_PASSED"}:
        return False
    return any(token in value for token in ("FAILED", "INCOMPLETE", "EXCEPTION", "ERROR", "BLOCKED"))


def _normalize_failure_stage_to_node(stage: str, state: dict | None = None) -> str:
    raw = str(stage or "").strip().lower().replace("-", "_").replace("/", "_")
    aliases = {
        "build_artifact": "build_artifact_validation",
        "artifact_validation": "build_artifact_validation",
        "architecture": "architecture_conformance",
        "conformance": "architecture_conformance",
        "environment": "environment_configuration",
        "tests": "test",
        "testing": "test",
        "repair": "debug",
        "debug_repair": "debug",
        "settings": "settings_validation",
        "coverage": "requirement_coverage_gate",
    }
    raw = aliases.get(raw, raw)
    if raw in _FAILURE_RESUME_PREVIOUS_NODE:
        return raw

    # Older diagnostics sometimes only persisted a status, not a node name.
    current = state or {}
    status = str(current.get("diagnostic_status") or current.get("status") or "").upper()
    status_map = (
        ("BUILD_ARTIFACT", "build_artifact_validation"),
        ("ARCHITECTURE_CONFORMANCE", "architecture_conformance"),
        ("AS_BUILT", "as_built_architecture"),
        ("SETTINGS_VALIDATION", "settings_validation"),
        ("SETTINGS_GENERATION", "settings_generator"),
        ("TEST_", "test"),
        ("TEST", "test"),
        ("CODE_PLAN", "project_file_plan"),
        ("COVERAGE", "requirement_coverage_gate"),
        ("CODE_GENERATION", "code_generation"),
    )
    for token, node in status_map:
        if token in status:
            return node
    return "build_artifact_validation"


def _redevelopment_descriptor(root: Path, workflow_state: dict, current_run: dict, checkpoint: dict | None = None) -> dict:
    checkpoint = checkpoint or {}
    build_resume = checkpoint.get("build_resume") if isinstance(checkpoint, dict) else {}
    if not isinstance(build_resume, dict):
        build_resume = {}
    status = str(
        current_run.get("status")
        or workflow_state.get("diagnostic_status")
        or workflow_state.get("status")
        or build_resume.get("status")
        or ""
    )
    failure_stage = str(
        workflow_state.get("diagnostic_failure_stage")
        or build_resume.get("failure_stage")
        or ""
    )
    failure_node = _normalize_failure_stage_to_node(failure_stage, workflow_state)
    resume_from = _FAILURE_RESUME_PREVIOUS_NODE.get(failure_node, failure_node)
    run_id = str(
        current_run.get("run_id")
        or workflow_state.get("diagnostic_run_id")
        or workflow_state.get("thread_id")
        or build_resume.get("run_id")
        or ""
    )
    available = bool(root.exists() and workflow_state and _is_failed_agent_build_status(status))
    return {
        "available": available,
        "status": status,
        "run_id": run_id,
        "failure_stage": failure_stage or failure_node,
        "failure_node": failure_node,
        "resume_from_node": resume_from,
        "failure_reason": str(
            workflow_state.get("diagnostic_failure_reason")
            or workflow_state.get("error")
            or build_resume.get("failure_reason")
            or ""
        ),
    }


@router.post("/workflow/design-checkpoint")
async def save_workflow_design_checkpoint(req: AgentDesignCheckpointRequest):
    root = Path(req.project_root).expanduser().resolve()
    # Do not create a not-yet-generated Agent project merely because the
    # interview autosave fired. Browser localStorage remains the pre-create
    # draft store; project-folder persistence starts after the folder exists.
    if not root.exists() or not root.is_dir():
        return {"ok": False, "reason": "PROJECT_NOT_CREATED", "project_root": str(root)}
    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    allowed = {
        "version", "saved_at", "agent_name", "project_root", "workflow_request",
        "chat", "confirmed_requirements", "workflow_preview", "workflow_quality",
        "agent_build_stage", "attachment_memory", "attachment_summary",
        "attachment_summary_files", "attachment_requirements",
        "attachment_requirement_coverage", "manual_requirement_overrides",
        "feature_registry", "design_project_id", "design_project_version",
        "ui_layout", "build_resume",
    }
    snapshot = {
        key: value for key, value in (req.snapshot or {}).items()
        if key in allowed
    }
    snapshot["version"] = 3
    snapshot["project_root"] = str(root)
    snapshot["saved_at"] = str(snapshot.get("saved_at") or datetime.now().astimezone().isoformat())
    snapshot["server_saved_at"] = datetime.now().astimezone().isoformat()
    safe = _safe_resume_value(snapshot)
    path = _agent_design_checkpoint_path(root)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
    return {"ok": True, "path": str(path), "saved_at": safe.get("saved_at", "")}


@router.get("/workflow/design-checkpoint")
async def load_workflow_design_checkpoint(project_root: str):
    root = Path(project_root).expanduser().resolve()
    reports = root / "reports"
    checkpoint = _read_json_dict(_agent_design_checkpoint_path(root))
    current_run = _read_json_dict(reports / "current_run.json")
    workflow_state = _read_json_dict(reports / "workflow_state.json")
    requirements_snapshot = _read_json_dict(reports / "requirements_snapshot.json")

    runtime = {
        "current_run": _safe_resume_value(current_run),
        "workflow_state": _compact_resume_workflow_state(workflow_state),
        "requirements_snapshot": _safe_resume_value(requirements_snapshot),
    }

    # Legacy v5.371-and-earlier projects may have failure diagnostics but no
    # persisted UI checkpoint. Build a conservative fallback so the user can
    # still continue from the failed project's design instead of starting over.
    legacy_snapshot = {}
    if not checkpoint and (requirements_snapshot or workflow_state):
        req = requirements_snapshot or {}
        workflow_preview = {
            "target_agent_workflow": req.get("target_agent_workflow") or workflow_state.get("target_agent_workflow") or {},
            "agent_architecture": req.get("agent_architecture") or workflow_state.get("agent_architecture") or {},
            "database_plan": workflow_state.get("database_plan") or {},
            "file_plan": req.get("file_plan") or workflow_state.get("file_plan") or {},
        }
        legacy_snapshot = {
            "version": 3,
            "saved_at": str(
                workflow_state.get("diagnostic_generated_at")
                or current_run.get("updated_at")
                or requirements_snapshot.get("diagnostic_generated_at")
                or ""
            ),
            "project_root": str(root),
            "workflow_request": str(req.get("request") or workflow_state.get("request") or ""),
            "confirmed_requirements": {
                "original_request": str(req.get("request") or workflow_state.get("request") or ""),
                "restored_requirement_spec": req.get("requirement_spec") or workflow_state.get("requirement_spec") or {},
            },
            "workflow_preview": workflow_preview,
            "workflow_quality": None,
            "agent_build_stage": "PROJECT_CREATED",
            "build_resume": {
                "source": "PROJECT_DIAGNOSTICS",
                "run_id": str(current_run.get("run_id") or workflow_state.get("diagnostic_run_id") or workflow_state.get("thread_id") or ""),
                "status": str(current_run.get("status") or workflow_state.get("diagnostic_status") or workflow_state.get("status") or ""),
                "failure_stage": str(workflow_state.get("diagnostic_failure_stage") or ""),
                "failure_reason": str(workflow_state.get("diagnostic_failure_reason") or workflow_state.get("error") or ""),
            },
        }
        legacy_snapshot = _safe_resume_value(legacy_snapshot)

    chosen = checkpoint or legacy_snapshot
    if chosen:
        chosen = _hydrate_saved_database_sql(root, chosen, workflow_state)
    redevelopment = _redevelopment_descriptor(
        root,
        workflow_state,
        current_run,
        checkpoint or legacy_snapshot,
    )
    return {
        "ok": True,
        "available": bool(chosen or workflow_state or requirements_snapshot),
        "project_root": str(root),
        "checkpoint": chosen,
        "checkpoint_source": "SAVED_CHECKPOINT" if checkpoint else ("PROJECT_DIAGNOSTICS" if legacy_snapshot else ""),
        "runtime": runtime,
        "redevelopment": redevelopment,
    }


@router.get("/workflow/diagnostics")
async def workflow_diagnostics(project_root: str, run_id: str = ""):
    """
    프로젝트 폴더의 최신 진단 자료를 조회합니다.

    v5.165부터 current_run.json의 실행 ID와 각 진단 파일의 실행 ID/수정 시각을
    함께 비교합니다. 따라서 이전 실행의 failure_report가 남아 있더라도 이번 실행의
    자료로 오인하지 않습니다.
    """
    from pathlib import Path
    import json

    root = Path(project_root).expanduser().resolve()
    reports = root / "reports"

    files = {
        "current_run": reports / "current_run.json",
        "failure_report": reports / "failure_report.md",
        "workflow_state": reports / "workflow_state.json",
        "requirements_snapshot": reports / "requirements_snapshot.json",
        "generated_artifacts": reports / "generated_artifacts.json",
        "debug_patch": root / "debug/debug_patch.json",
        "recovery_plan": root / "debug/recovery_plan.md",
        "agent_factory_log": root / "logs/agent_factory.log",
        "workflow_execution_log": root / "logs/workflow_execution.log",
        "test_log": root / "logs/test.log",
        "debug_log": root / "logs/debug.log",
    }

    def read_json(path: Path) -> dict:
        if not path.is_file():
            return {}
        try:
            value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    current_run = read_json(files["current_run"])
    state = read_json(files["workflow_state"])
    artifact = read_json(files["generated_artifacts"])

    current_run_id = str(current_run.get("run_id") or current_run.get("thread_id") or "")
    state_run_id = str(state.get("diagnostic_run_id") or state.get("thread_id") or "")
    requested_run_id = str(run_id or "")

    # 호출자가 run_id를 주면 그 실행을 가장 우선합니다. 없으면 current_run marker 기준입니다.
    expected_run_id = requested_run_id or current_run_id
    diagnostics_fresh = bool(
        expected_run_id
        and state_run_id
        and expected_run_id == state_run_id
    )

    # run marker가 없는 예전 프로젝트도 조회할 수 있도록 fallback을 둡니다.
    if not expected_run_id:
        diagnostics_fresh = bool(state)

    result_files = {}
    for key, path in files.items():
        exists = path.is_file()
        stat = path.stat() if exists else None
        result_files[key] = {
            "path": str(path),
            "exists": exists,
            "size": stat.st_size if stat else 0,
            "modified_at": (
                datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat()
                if stat else ""
            ),
            "modified_epoch": stat.st_mtime if stat else 0,
        }

    patch_result = state.get("patch_result") or []
    test_result = state.get("test_result") or {}
    debug_history = state.get("debug_history") or []

    current_status = str(current_run.get("status") or "")
    stored_status = str(
        state.get("diagnostic_status")
        or state.get("status")
        or "UNKNOWN"
    )

    if expected_run_id and not diagnostics_fresh:
        visible_status = "DIAGNOSTICS_STALE"
        failure_reason = (
            "현재 실행의 진단 자료가 아직 생성되지 않았습니다. "
            "화면에 남아 있는 이전 실행 파일을 현재 실패 원인으로 사용하지 않습니다."
        )
        failure_stage = "diagnostics/freshness"
    elif current_status == "RUNNING" and stored_status == "RUNNING":
        visible_status = "RUNNING"
        failure_reason = "현재 Agent 개발 Workflow가 실행 중입니다."
        failure_stage = "agent_factory"
    else:
        visible_status = stored_status
        failure_reason = str(
            state.get("diagnostic_failure_reason")
            or state.get("error")
            or ""
        )
        failure_stage = str(state.get("diagnostic_failure_stage") or "")

    return {
        "ok": True,
        "project_root": str(root),
        "requested_run_id": requested_run_id,
        "run_id": expected_run_id or state_run_id,
        "current_run": current_run,
        "current_run_id": current_run_id,
        "state_run_id": state_run_id,
        "run_started_at": str(current_run.get("started_at") or state.get("run_started_at") or ""),
        "diagnostic_generated_at": str(
            state.get("diagnostic_generated_at")
            or current_run.get("diagnostics_generated_at")
            or ""
        ),
        "diagnostics_fresh": diagnostics_fresh,
        "status": visible_status,
        "stored_status": stored_status,
        "failure_stage": failure_stage,
        "failure_reason": failure_reason,
        "actual_file_count": (
            state.get("diagnostic_actual_file_count")
            or artifact.get("actual_project_file_count")
            or 0
        ),
        "planned_file_count": artifact.get("planned_file_count") or 0,
        "file_apply": {
            "executed": bool(patch_result),
            "count": len(patch_result),
        },
        "file_apply_validation": state.get("file_apply_validation") or {},
        "test": {
            "executed": bool(test_result),
            "returncode": test_result.get("returncode"),
        },
        "debug": {
            "executed": bool(debug_history),
            "count": len(debug_history),
        },
        "missing_planned_files": artifact.get("missing_planned_files") or [],
        "build_artifact_validation": (
            state.get("build_artifact_validation")
            or artifact.get("build_artifact_validation")
            or {}
        ),
        "code_plan_validation": (
            state.get("code_plan_validation")
            or artifact.get("code_plan_validation")
            or {}
        ),
        "missing_required_paths": (
            (
                state.get("code_plan_validation")
                or artifact.get("code_plan_validation")
                or {}
            ).get("missing_required_paths")
            or []
        ),
        "files": result_files,
    }


def _workflow_initial_state(req: WorkflowStartRequest, thread_id: str) -> dict:
    base = {
        "thread_id": thread_id,
        "project_root": req.project_root,
        "request": req.request,
        "target_files": req.target_files,
        "test_command": req.test_command,
        "provider": req.provider,
        "design_bundle": req.design_bundle,
        "debug_iteration": 0,
        "debug_history": [],
    }

    # v5.371: for redevelopment, carry forward the last persisted build state
    # and jump into the node immediately before the recorded failure. Completed
    # requirement/design/code-plan work is reused; only the failure suffix runs.
    if req.resume_mode:
        previous = (req.design_bundle or {}).get("previous_build_state") or {}
        if isinstance(previous, dict) and previous:
            merged = dict(previous)
            merged.update(base)
            merged["debug_iteration"] = int(previous.get("debug_iteration") or 0)
            merged["debug_history"] = list(previous.get("debug_history") or [])
            merged["patch_result"] = list(previous.get("patch_result") or [])
            merged["resume_mode"] = True
            merged["resume_from_node"] = str(req.resume_from_node or "")
            merged["resume_run_id"] = str(req.resume_run_id or "")
            merged["resume_previous_status"] = str(previous.get("diagnostic_status") or previous.get("status") or "")
            merged.pop("error", None)
            return merged

    return base


# v5.349: Actual LangGraph node-boundary progress. This replaces synthetic-only
# progress with a small observable trace without any additional LLM request.
_AGENT_BUILD_NODE_PROGRESS = {
    "requirement_analysis": (6, "요구사항 설계 상태 확인"),
    "analyze_project": (10, "프로젝트 영향 범위 분석"),
    "capability_design": (14, "Capability 설계 반영"),
    "tool_mcp_decision": (18, "Tool / MCP 설계 반영"),
    "agent_architecture": (22, "Design Architecture 반영"),
    "database_design": (26, "DB 설계 반영"),
    "target_workflow_design": (30, "Workflow / LangGraph 설계 반영"),
    "project_file_plan": (34, "파일 변경 계획 계산"),
    "requirement_coverage_gate": (38, "요구사항 Coverage 검증"),
    "settings_requirement_analysis": (41, "초기 설정 요구사항 분석"),
    "settings_schema_design": (44, "설정 Schema 설계"),
    "settings_ui_design": (47, "설정 UI 설계"),
    "checkpoint": (49, "변경 전 Checkpoint 생성"),
    "approval": (51, "코드 변경 승인 확인"),
    "code_generation": (62, "코드 생성 / 증분 수정"),
    "settings_generator": (68, "설정 기능 생성"),
    "settings_validation": (72, "설정 기능 검증"),
    "build_artifact_validation": (76, "생성 산출물 검증"),
    "as_built_architecture": (80, "As-Built Architecture 분석"),
    "architecture_conformance": (84, "Design ↔ As-Built 일치 검증"),
    "environment_configuration": (87, "실행 환경 구성"),
    "test": (91, "테스트 실행"),
    "debug": (88, "실패 원인 분석 / 수정 준비"),
    "package_completion": (96, "실행 관리자 / 패키지 정리"),
    "review": (98, "최종 검토"),
}


async def _run_agent_graph_with_progress(state: dict, config: dict, job) -> dict:
    if job is None:
        return await agent_graph_runtime.graph.ainvoke(state, config=config)

    saw_update = False
    async for chunk in agent_graph_runtime.graph.astream(
        state,
        config=config,
        stream_mode="updates",
    ):
        if not isinstance(chunk, dict):
            continue
        for node_name, update in chunk.items():
            if str(node_name).startswith("__"):
                continue
            saw_update = True
            progress, label = _AGENT_BUILD_NODE_PROGRESS.get(
                str(node_name),
                (max(job.progress, 8), f"{node_name} 처리"),
            )
            status = ""
            detail = ""
            if isinstance(update, dict):
                status = str(update.get("status") or "")
                detail = str(update.get("error") or update.get("review") or "")
            message = label + (f" · {status}" if status else "")
            await job_manager.update(
                job,
                status="RUNNING",
                progress=max(job.progress, progress),
                message=message,
                node=str(node_name),
                event_detail=detail,
            )

    try:
        snapshot = await agent_graph_runtime.graph.aget_state(config)
        values = getattr(snapshot, "values", None)
        if isinstance(values, dict):
            return dict(values)
    except Exception:
        pass

    # A graph without a checkpointer should be rare here. Fall back only when the
    # stream emitted nothing; do not execute the graph twice after real updates.
    if not saw_update:
        return await agent_graph_runtime.graph.ainvoke(state, config=config)
    return dict(state)


async def _execute_workflow_with_diagnostics(
    req: WorkflowStartRequest,
    thread_id: str,
    job=None,
) -> dict:
    """
    Agent Workflow 실행과 진단 생성을 하나의 Backend 작업으로 묶습니다.
    Frontend HTTP 연결이 끊겨도 Background Job 안에서 최종 진단 파일 생성까지 계속됩니다.
    """
    config = {"configurable": {"thread_id": thread_id}}
    state = _workflow_initial_state(req, thread_id)
    begin_workflow_diagnostic_run(req.project_root, thread_id, req.request)

    if job is not None:
        await job_manager.update(
            job,
            status="RUNNING",
            progress=8,
            message="Agent Factory Workflow를 시작했습니다. 현재 실행 ID의 진단 파일도 초기화했습니다.",
        )

    try:
        with usage_context(
            project_root=req.project_root,
            thread_id=thread_id,
            operation="agent_build",
        ):
            result = await _run_agent_graph_with_progress(
                state,
                config,
                job,
            )
    except asyncio.CancelledError:
        raise
    except BaseException as exc:
        # LangGraph 내부 예외가 HTTP 500/연결 리셋으로만 끝나지 않게 실패 자료를 반드시 남깁니다.
        partial_state = dict(state)
        try:
            snapshot = await agent_graph_runtime.graph.aget_state(config)
            values = getattr(snapshot, "values", None)
            if isinstance(values, dict):
                partial_state.update(values)
        except Exception:
            pass

        partial_state.update({
            "thread_id": thread_id,
            "project_root": req.project_root,
            "request": req.request,
            "status": "WORKFLOW_EXCEPTION",
            "error": f"{type(exc).__name__}: {exc}",
        })
        result, failure_diagnostics = normalize_workflow_result(
            project_root=req.project_root,
            state=partial_state,
            request=req.request,
            thread_id=thread_id,
        )
        return {
            "ok": False,
            "thread_id": thread_id,
            "state": result,
            "failure_diagnostics": failure_diagnostics,
            "usage": read_usage_summary(project_root=req.project_root),
        }

    if job is not None:
        await job_manager.update(
            job,
            status="RUNNING",
            progress=92,
            message="Agent Factory 실행이 종료되어 최종 상태와 진단 파일을 저장하고 있습니다.",
        )

    result, failure_diagnostics = normalize_workflow_result(
        project_root=req.project_root,
        state=result,
        request=req.request,
        thread_id=thread_id,
    )

    return {
        "ok": True,
        "thread_id": thread_id,
        "state": result,
        "failure_diagnostics": failure_diagnostics,
        "usage": read_usage_summary(project_root=req.project_root),
    }


@router.post("/workflow/start-job")
async def workflow_start_job(req: WorkflowStartRequest):
    """긴 Agent 개발을 HTTP 장기 연결 대신 Background Job으로 실행합니다."""
    thread_id = req.thread_id or uuid.uuid4().hex

    async def runner(job):
        return await _execute_workflow_with_diagnostics(
            req=req,
            thread_id=thread_id,
            job=job,
        )

    job = job_manager.create("AGENT_BUILD", runner)
    payload = vars(job).copy()
    payload["thread_id"] = thread_id
    payload["project_root"] = req.project_root
    return payload


@router.post("/workflow/redevelop-start-job")
async def workflow_redevelop_start_job(req: WorkflowRedevelopRequest):
    """Resume a failed generated-Agent build from the checkpoint before failure.

    The project source may have been edited after the failure. We therefore reuse
    completed requirement/design/code-plan state, but start a fresh LangGraph run
    from the node immediately before the recorded failing node. This avoids
    replaying the interview/design pipeline while still re-validating the edited
    source before moving forward.
    """
    root = Path(req.project_root).expanduser().resolve()
    reports = root / "reports"
    workflow_state = _read_json_dict(reports / "workflow_state.json")
    current_run = _read_json_dict(reports / "current_run.json")
    checkpoint = _read_json_dict(_agent_design_checkpoint_path(root))
    requirements_snapshot = _read_json_dict(reports / "requirements_snapshot.json")

    redevelopment = _redevelopment_descriptor(root, workflow_state, current_run, checkpoint)
    if not redevelopment.get("available"):
        raise HTTPException(
            status_code=409,
            detail="재개발 가능한 이전 실패 기록을 찾지 못했습니다.",
        )

    prior_request = str(
        req.request
        or workflow_state.get("request")
        or requirements_snapshot.get("request")
        or checkpoint.get("workflow_request")
        or ""
    )
    if not prior_request:
        raise HTTPException(status_code=422, detail="이전 개발 요청 내용을 복원할 수 없습니다.")

    previous_bundle = workflow_state.get("design_bundle")
    if not isinstance(previous_bundle, dict):
        previous_bundle = {}
    confirmed_requirements = checkpoint.get("confirmed_requirements")
    if not isinstance(confirmed_requirements, dict):
        confirmed_requirements = previous_bundle.get("confirmed_requirements") or {}

    design_bundle = {
        **previous_bundle,
        "confirmed_requirements": confirmed_requirements,
        "previous_build_state": workflow_state,
        "resume_context": {
            "run_id": redevelopment.get("run_id") or "",
            "status": redevelopment.get("status") or "",
            "failure_stage": redevelopment.get("failure_stage") or "",
            "failure_reason": redevelopment.get("failure_reason") or "",
            "continue_failed_build": True,
            "redevelopment": True,
            "resume_from_node": redevelopment.get("resume_from_node") or "",
        },
    }

    thread_id = f"redevelop-{uuid.uuid4().hex}"
    start_req = WorkflowStartRequest(
        project_root=str(root),
        request=prior_request,
        target_files=[],
        test_command=req.test_command or str(workflow_state.get("test_command") or "python -m compileall ."),
        provider=req.provider or workflow_state.get("provider"),
        thread_id=thread_id,
        design_bundle=design_bundle,
        resume_mode=True,
        resume_from_node=str(redevelopment.get("resume_from_node") or "build_artifact_validation"),
        resume_run_id=str(redevelopment.get("run_id") or ""),
    )

    async def runner(job):
        return await _execute_workflow_with_diagnostics(
            req=start_req,
            thread_id=thread_id,
            job=job,
        )

    job = job_manager.create("AGENT_REDEVELOP", runner)
    payload = vars(job).copy()
    payload.update({
        "thread_id": thread_id,
        "project_root": str(root),
        "redevelopment": True,
        "previous_run_id": redevelopment.get("run_id") or "",
        "failure_stage": redevelopment.get("failure_stage") or "",
        "resume_from_node": redevelopment.get("resume_from_node") or "",
    })
    return payload


@router.post("/workflow/start")
async def workflow_start(req: WorkflowStartRequest):
    """호환용 동기 Endpoint. Frontend v5.297는 /workflow/start-job을 사용하며 시작 전 Backend 버전을 검증합니다."""
    thread_id = req.thread_id or uuid.uuid4().hex
    return await _execute_workflow_with_diagnostics(
        req=req,
        thread_id=thread_id,
    )

@router.post("/workflow/resume")
async def workflow_resume(req: WorkflowResumeRequest):
    config = {"configurable": {"thread_id": req.thread_id}}
    result = await agent_graph_runtime.graph.ainvoke(
        Command(resume={"decision": req.decision}),
        config=config
    )

    project_root = str(result.get("project_root") or "")
    failure_diagnostics = None

    if project_root:
        result, failure_diagnostics = normalize_workflow_result(
            project_root=project_root,
            state=result,
            request=str(result.get("request") or ""),
            thread_id=req.thread_id,
        )

    return {
        "thread_id": req.thread_id,
        "state": result,
        "failure_diagnostics": failure_diagnostics,
    }

@router.get("/usage/summary")
async def usage_summary(
    project_root: str = "",
    date: str = "",
    scope: str = "today",
    month: str = "",
):
    return read_usage_summary(
        project_root=project_root,
        date=date,
        scope=scope,
        month=month,
    )


@router.post("/jobs/command")
async def command_job(req: CommandRequest):
    async def runner(job):
        await job_manager.update(job, progress=20, message="명령을 실행하고 있습니다.")
        result = await run_command(req.command, req.cwd)
        await job_manager.update(job, progress=90, message="실행 결과를 확인하고 있습니다.")
        return result
    job = job_manager.create("COMMAND", runner)
    return vars(job)

@router.get("/jobs")
async def jobs():
    return [vars(x) for x in job_manager.jobs.values()]

@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str):
    await job_manager.cancel(job_id)
    return {"ok": True}

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await hub.connect(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.disconnect(ws)
