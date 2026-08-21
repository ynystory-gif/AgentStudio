from datetime import datetime
from pathlib import Path
from app.services.db_gateway import DatabaseGateway
from app.services.folder_picker import pick_folder, pick_file
from app.services.ollama_installer import install_ollama_windows
from app.services.ollama_runtime_manager import get_ollama_runtime_status, start_ollama_server, stop_ollama_server
import asyncio
import json
from app.models.entities import Project, ProjectAnalysis
from app.services.project_paths import resolve_project_paths
from app.services.database_provisioning import provision_agentstudio_database
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
    initialize_supabase_schema,
    schema_script_path as get_supabase_schema_script_path,
)
from app.services.weather_service import build_weather_dashboard, weather_config
from app.services.llm_catalog_service import build_llm_catalog
from app.services.project_root_registry import ensure_persisted_project_root
from app.services.terminal_completion_service import complete_terminal_input
from app.services.managed_process_service import managed_process_service
from app.services.python_execution_service import python_execution_manager
from app.services.sql_workspace_service import (
    get_profile as get_sql_workspace_profile,
    list_profiles as list_sql_workspace_profiles,
    save_profile as save_sql_workspace_profile,
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
    create_redis_python_script as create_sql_workspace_redis_python_script,
    redis_python_script_runtime_env as get_redis_python_script_runtime_env,
    sqlite_project_status as get_sqlite_project_status,
    open_database_object as open_sql_workspace_object,
    create_table_script as create_sql_workspace_table_script,
    create_table_alter_script as create_sql_workspace_table_alter_script,
    create_table_dml_script as create_sql_workspace_table_dml_script,
    create_postgresql_admin_script as create_sql_workspace_postgresql_admin_script,
)
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Request, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from langgraph.types import Command
from sqlalchemy import select, func
from app.core.database import SessionLocal, migrate_agentstudio_schema, verify_project_schema, current_event_loop_name
from app.models.entities import MCPServer, ToolRecord
from app.services.ws_hub import hub
from app.services.job_manager import job_manager
from app.services.system_status import get_status
from app.services.port_service import recommend_agentstudio_ports
from app.services.local_control import list_files, list_directories, read_file, write_file, run_command, register_runtime_project_root, get_runtime_project_roots, create_folder, rename_path, create_file, delete_files, project_file_snapshot, get_file_meta, get_file_hash_states, ExternalFileChangedError, InvalidNotebookContentError
from app.services.tavily_service import web_search
from app.services.requirements_agent import next_interview_message
from app.services.llm_usage_service import usage_context, read_usage_summary, read_llm_history
from app.services.agent_builder import build_plan
from app.services.tool_analyzer import analyze_tool
from app.services.mcp_manager import discover_streamable_http
from app.services.mcp_registry import mcp_registry_monitor
from app.services.langgraph_runtime import agent_graph_runtime
from app.services.git_service import git_status, git_diff, checkpoint
from app.services.project_analyzer import scan_project, find_related_files, local_project_summary
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
from app.services.agent_factory_workflow_design import design_agent_factory
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

class WorkflowResumeRequest(BaseModel):
    thread_id: str
    decision: str

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


class ProjectCodeEditRequest(BaseModel):
    root: str
    instruction: str
    max_context_files: int = 10


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
    initialize_schema: bool = True


class SupabaseSchemaInitializeRequest(BaseModel):
    database_url: str = ""
    langgraph_database_url: str = ""

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


class SqlWorkspaceExecuteRequest(BaseModel):
    root: str
    sql: str
    max_rows: int = 1000


class SqlWorkspaceObjectOpenRequest(BaseModel):
    root: str
    schema: str
    category: str
    name: str


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
        return await update_settings(req.values)
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
            initialize_schema=req.initialize_schema,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Runtime DB 전환 실패: {exc}") from exc


@router.post("/settings/database-runtime/supabase/initialize-schema")
async def settings_supabase_initialize_schema(req: SupabaseSchemaInitializeRequest):
    try:
        return await initialize_supabase_schema(req.database_url, req.langgraph_database_url)
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

        async with SessionLocal() as session:
            project = (
                await session.execute(
                    select(Project).where(Project.root_path == root)
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
        project = await session.get(Project, project_id)
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

    async with SessionLocal() as session:
        # 같은 프로젝트 경로가 이미 등록되어 있으면 중복 생성하지 않음
        existing = (
            await session.execute(
                select(Project).where(Project.root_path == paths["project_root"])
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

            return {
                "ok": True,
                "recreated": True,
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

    return {
        "ok": True,
        "message": "신규 Agent 프로젝트 생성 및 DB 저장 완료",
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
        async with SessionLocal() as session:
            count = (
                await session.execute(
                    select(func.count(Project.id))
                )
            ).scalar_one()

            sample = (
                await session.execute(
                    select(Project)
                    .order_by(Project.id.desc())
                    .limit(5)
                )
            ).scalars().all()

        return {
            "ok": True,
            "path": "Frontend -> FastAPI -> PostgreSQL",
            "database_connected": True,
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
    async with SessionLocal() as session:
        project = await session.get(Project, project_id)

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
            count = (
                await session.execute(
                    select(func.count(Project.id))
                )
            ).scalar_one()

        return {
            "ok": True,
            "database_connected": True,
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
        async with SessionLocal() as session:
            rows = (
                await session.execute(
                    select(Project).order_by(
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


@router.get("/health")
async def health():
    return {"ok": True, "name": "THEANOVA AgentStudio", "version": "5.284", "build": "SupabaseIdempotentSchemaProvisioningFix"}

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

@router.post("/chat/interview")
async def interview(req: ChatRequest):
    with usage_context(
        project_root=req.project_root,
        operation="requirements_interview",
    ):
        answer = await next_interview_message(
            req.message,
            req.history,
            req.provider,
        )

    return {"answer": answer}

@router.post("/agent/plan")
async def agent_plan(req: PlanRequest):
    return {"plan": await build_plan(req.requirements, req.provider)}

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

    try:
        llm = model_for_task(LLMTask.CODE_GENERATION)
        is_notebook = req.path.casefold().endswith(".ipynb")

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

절대 규칙:
1. [TARGET] Code 셀 {target_number}에 들어갈 코드만 반환합니다.
2. Notebook 전체 JSON을 반환하지 않습니다.
3. 설명, Markdown, 코드펜스 없이 Code 셀 본문만 반환합니다.
4. [CONTEXT] 셀은 이해용이며 수정하거나 다시 출력하지 않습니다.
5. 현재 셀이 비어 있다면 사용자 요청과 주변 Markdown/힌트에 맞는 코드를 작성합니다.
6. 기존 동작을 불필요하게 변경하지 않습니다.
7. 사용자가 명시적으로 주석 삭제/수정 또는 셀 전체 교체를 요청하지 않았다면 TARGET 셀의 기존 주석, 학습용 힌트, TODO를 삭제하거나 치환하지 않습니다.
8. 기존 주석 아래에 코드를 작성하라는 요청이면 주석을 그대로 남기고 바로 아래에 코드를 추가합니다.
9. Python Notebook 문법으로 실행 가능한 코드를 작성합니다.
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
                "path": req.path,
                "saved": False,
                "preserved_comment_lines": preserved_comment_lines,
                "edit_scope": "notebook_cell",
                "active_cell_index": notebook_ctx.active_cell_index,
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

        message = "코드 수정 제안을 만들었습니다."
        if preserved_comment_lines:
            message += f" 기존 주석 {preserved_comment_lines}줄을 보존했습니다."

        return {
            "ok": True,
            "code": content,
            "message": message,
            "path": req.path,
            "saved": False,
            "preserved_comment_lines": preserved_comment_lines,
            "edit_scope": "file",
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

        llm = model_for_task(LLMTask.CODE_GENERATION)

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
    if relative_path and not relative_path.lower().endswith((".py", ".ipynb")):
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
    ])

    return "\\n".join(rows)


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

    full_request = _build_interview_requirement_context(
        request=req.request,
        interview_messages=req.interview_messages,
        confirmed_requirements=req.confirmed_requirements,
    )

    with usage_context(
        project_root=req.project_root,
        operation="workflow_preview",
    ):
        design = await design_agent_factory(
            request=full_request,
            project_context=project_context,
            provider=req.provider,
        )

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
        "target_agent_workflow": target,
        "requirement_spec": design.get("requirement_spec") or {},
        "capability_plan": design.get("capability_plan") or {},
        "tool_mcp_plan": design.get("tool_mcp_plan") or {},
        "agent_architecture": design.get("agent_architecture") or {},
        "file_plan": design.get("file_plan") or {},
        "environment_plan": design.get("environment_plan") or {},
        "settings_plan": design.get("settings_plan") or {},
        "workflow_quality": quality,
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
    return {
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
            result = await agent_graph_runtime.graph.ainvoke(
                state,
                config=config,
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


@router.post("/workflow/start")
async def workflow_start(req: WorkflowStartRequest):
    """호환용 동기 Endpoint. Frontend v5.284는 /workflow/start-job을 사용하며 시작 전 Backend 버전을 검증합니다."""
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
