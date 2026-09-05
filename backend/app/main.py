import asyncio
import sys

# v5.493: apply saved path roots before optional ML/browser imports.
from app.services.runtime_path_policy import bootstrap_runtime_paths_from_env_file, apply_runtime_path_policy
bootstrap_runtime_paths_from_env_file()

# Windows + psycopg async requires SelectorEventLoop.
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.database import init_db, migrate_agentstudio_schema, ensure_runtime_metadata_tables
# Must load before API routes so direct imports of read_usage_summary receive the DB-backed version.
import app.services.llm_usage_db_bridge  # noqa: F401
# Problem collection reuses AgentStudio's configured high-level model priority.
# v5.427 additionally repairs malformed Teacher JSON and falls through to the next Teacher.
import app.services.learning_teacher_bridge  # noqa: F401
# v5.602 keeps the cumulative learned model aligned with the configured latest Qwen runtime base.
# This bridge must load before learning API routes import the apply service.
import app.services.learning_base_model_auto_bridge  # noqa: F401
# Hide exact Dataset source cases already applied on the current PC before routes bind the function.
import app.services.learning_visibility_bridge  # noqa: F401
# Bind the static + Chrome CDP Theme analyzer before dynamic Theme routes import its function.
import app.services.ui_theme_hybrid_bridge  # noqa: F401
# v5.429: the frontend clock is UX only. Backend owns one 5-minute hard deadline and
# marks overdue Theme analysis FAILED while terminating AgentStudio-owned workers.
import app.services.ui_theme_job_hard_timeout_bridge  # noqa: F401
from app.api.routes import router
from app.api.learning_diagnostics_routes import router as learning_diagnostics_router
from app.api.learning_routes import router as learning_router
from app.api.learning_full_apply_routes import router as learning_full_apply_router
from app.api.ui_theme_dynamic_routes import router as ui_theme_dynamic_router
from app.api.scheduler_routes import router as scheduler_router
from app.api.media_workflow_routes import router as media_workflow_router
from app.api.auth_routes import router as auth_router
from app.api.account_settings_routes import router as account_settings_router
from app.api.rag_routes import router as rag_router
from app.services.langgraph_runtime import agent_graph_runtime
from app.services.mcp_registry import mcp_registry_monitor
from app.services.settings_service import migrate_env_settings_to_db, load_db_settings_into_runtime, register_current_machine, resolve_pending_machine_name
from app.core.machine_identity import ensure_pc_name_env, current_pc_name
from app.services.project_root_registry import restore_registered_project_roots
from app.services.llm_usage_service import prune_llm_history
from app.services.active_ollama_model_service import sync_active_ollama_model
from app.services.llm_learning_service import sync_misjudgment_candidates
from app.services.learning_visibility_bridge import backfill_current_pc_learning_group_mappings
from app.services.learning_relational_schema_service import ensure_learning_relational_schema
from app.services.auth_service import authenticate_token
from app.services.database_runtime_service import apply_saved_database_provider
from app.services.chromium_browser_service import chromium_browser_manager
from app.services.codex_app_server_service import codex_app_server_manager

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        machine_env = ensure_pc_name_env()
        print(f"[완료되었습니다] AgentStudio PC 이름: {machine_env.get('pc_name', '')}")
        await init_db()
        schema_migration = await migrate_agentstudio_schema()
        pending_result = await resolve_pending_machine_name()
        if pending_result.get("pending"):
            print(f"[안내] PC 이름 유니크 검증 대기: {pending_result.get('pending_pc_name', '')} - {pending_result.get('message', '')}")
        machine_db = await register_current_machine()
        print(f"[완료되었습니다] PC 프로필 DB 등록: {machine_db.get('pc_name', '')}")
        print(f"[완료되었습니다] DB 스키마 보정: {schema_migration.get('count', 0)}개")
        migration = await migrate_env_settings_to_db()
        runtime = await load_db_settings_into_runtime()
        runtime_paths = apply_runtime_path_policy()
        print(f"[완료되었습니다] Runtime 경로 적용: Temp={runtime_paths.get('temp_root', '')} · Cache={runtime_paths.get('cache_root', '')} · Output={runtime_paths.get('output_root', '')}")
        runtime_db = await apply_saved_database_provider()
        runtime_metadata = await ensure_runtime_metadata_tables()
        runtime_pk_renames = list(runtime_metadata.get("precreate_pk_renames") or [])
        if runtime_pk_renames:
            print(
                "[완료되었습니다] Runtime RAG PK 사전 보정: "
                f"{len(runtime_pk_renames)}개 · create_all 이전 적용"
            )
        active_ollama = await sync_active_ollama_model()
        print(
            "[완료되었습니다] Active Ollama 모델 동기화: "
            f"{active_ollama.get('active_model', '')} · reason={active_ollama.get('reason', '')}"
        )
        print("[완료되었습니다] PostgreSQL/pgvector 초기화")
        print(f"[완료되었습니다] Runtime ORM 테이블 확인: {runtime_metadata.get('table_count', 0)}개 · schema={runtime_metadata.get('schema', '')}")
        print(f"[완료되었습니다] Runtime DB: {runtime_db.get('active_provider', 'local')} · {runtime_db.get('target', '')}")
        if not runtime_db.get("ok", True):
            print(f"[경고] Runtime DB 전환: {runtime_db.get('message', '')}")
        if migration.get("migrated"):
            print(f"[완료되었습니다] 설정 DB 이관: {migration['migrated']}개")
        print(f"[완료되었습니다] DB 설정 런타임 적용: {runtime.get('loaded', 0)}개")

        project_roots = await restore_registered_project_roots()
        print(f"[완료되었습니다] 등록 프로젝트 허용 경로 복원: {project_roots.get('restored_count', 0)}개")
        legacy_adoption = dict(project_roots.get("legacy_adoption") or {})
        if legacy_adoption.get("claimed_count"):
            print(f"[완료되었습니다] 레거시 프로젝트 현재 PC 귀속: {legacy_adoption.get('claimed_count', 0)}개 · PC={project_roots.get('pc_name', '')}")
        if project_roots.get("missing_count"):
            print(f"[안내] 현재 PC에 존재하지 않는 등록 프로젝트 경로: {project_roots.get('missing_count', 0)}개")

        try:
            history_prune = prune_llm_history(force=True)
            print(f"[완료되었습니다] LLM 요청/응답 10일 보관 정리: 삭제 {history_prune.get('removed', 0)}개")
            learning_schema = await ensure_learning_relational_schema()
            print(
                "[완료되었습니다] LLM 학습 관계형 스키마/문제 행 보정: "
                f"문제 {learning_schema.get('created_problem_row_count', 0)}개 · "
                f"Dataset 연결 {learning_schema.get('linked_dataset_count', 0)}개"
            )
            learning_sync = await sync_misjudgment_candidates()
            print(f"[완료되었습니다] LLM 오판 학습 후보 공용 DB 동기화: 신규 {learning_sync.get('added', 0)}개 · 전체 {learning_sync.get('total', 0)}개")
            mapping_backfill = await backfill_current_pc_learning_group_mappings()
            print(
                "[완료되었습니다] 기존 학습 Dataset 그룹 키 보정: "
                f"Dataset {mapping_backfill.get('backfilled_dataset_count', 0)}개 · "
                f"학습 Case {mapping_backfill.get('learned_case_count', 0)}개 · "
                f"그룹 {mapping_backfill.get('learned_family_count', 0)}개"
            )
        except Exception as history_error:
            print(f"[경고] LLM 요청/응답/학습 후보/그룹 키 정리 실패: {history_error}")
    except Exception as e:
        orig = getattr(e, "orig", None)
        sqlstate = str(getattr(orig, "sqlstate", "") or getattr(orig, "pgcode", "") or "")
        if sqlstate == "28P01":
            print("[경고] PostgreSQL 초기화 실패: 데이터베이스 사용자 비밀번호 인증에 실패했습니다. 시스템 관리의 DATABASE URL을 확인하세요.")
        elif sqlstate.startswith("08"):
            print("[경고] PostgreSQL 초기화 실패: PostgreSQL 서버 연결이 끊겼습니다. 서버/포트/서비스 상태를 확인하세요.")
        else:
            print(f"[경고] PostgreSQL 초기화 실패: {e}")

    await agent_graph_runtime.start()
    await mcp_registry_monitor.start()

    async def _background_browser_cleanup():
        try:
            browser_cleanup = await chromium_browser_manager.cleanup_stale_processes()
            if browser_cleanup.get("killed") or browser_cleanup.get("remaining"):
                print(f"[완료되었습니다] 이전 BrowserRuntime 백그라운드 정리: kill {browser_cleanup.get('killed', 0)} · remaining {browser_cleanup.get('remaining', 0)}")
        except Exception as browser_cleanup_error:
            print(f"[경고] 이전 BrowserRuntime 백그라운드 정리 실패: {browser_cleanup_error}")

    browser_cleanup_task = asyncio.create_task(_background_browser_cleanup())
    try:
        yield
    finally:
        if not browser_cleanup_task.done():
            browser_cleanup_task.cancel()
        await mcp_registry_monitor.stop()
        await agent_graph_runtime.stop()
        await chromium_browser_manager.shutdown()
        await codex_app_server_manager.shutdown()

app = FastAPI(title="THEANOVA AgentStudio", version="5.602", lifespan=lifespan)

_PUBLIC_API_PATHS = {
    "/api/health",
    "/api/health/database",
    "/api/auth/login",
    "/api/auth/register",
}

_AUTH_BOOTSTRAP_PATHS = {
    "/api/auth/me",
    "/api/auth/logout",
    "/api/auth/current-pc",
    "/api/auth/current-pc/register",
}

@app.middleware("http")
async def _agentstudio_auth_guard(request: Request, call_next):
    path = request.url.path

    # v5.430: Public health requests must continue through the inner CORS middleware.
    # Returning JSONResponse directly from this outer auth middleware bypassed CORS,
    # so Frontend (5173) -> Backend (800x) /api/health fetches appeared as
    # BackendFetchError even while the Backend itself was alive and reachable in a tab.
    if request.method == "OPTIONS" or not path.startswith("/api/") or path in _PUBLIC_API_PATHS or path in _AUTH_BOOTSTRAP_PATHS:
        return await call_next(request)
    auth = request.headers.get("Authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    member = await authenticate_token(token)
    if not member:
        return JSONResponse(status_code=401, content={"detail": "로그인이 필요합니다."})
    pc_name = current_pc_name()
    if pc_name not in set(member.get("pcs") or []):
        return JSONResponse(status_code=403, content={"detail": f"현재 PC '{pc_name}'가 이 사용자 계정에 등록되어 있지 않습니다. 우측 사용자 메뉴에서 '현재 PC 등록'을 먼저 실행하세요."})
    request.state.member = member
    return await call_next(request)

# v5.434: CORS must be the outermost HTTP middleware so even authentication
# rejections (401/403) are visible to the browser as normal HTTP responses instead
# of opaque "Failed to fetch" network errors. add_middleware inserts at the front
# of Starlette's middleware list, so register CORS after the auth guard.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_origin_regex=r"^https?://(127\.0\.0\.1|localhost):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def _agentstudio_startup_probe():
    from pathlib import Path
    from datetime import datetime
    project_root = Path(__file__).resolve().parents[2]
    log_dir = project_root.parent / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "backend_startup.log"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] AgentStudio Backend startup completed\n")

app.include_router(auth_router, prefix="/api")
app.include_router(account_settings_router, prefix="/api")
app.include_router(router, prefix="/api")
app.include_router(learning_diagnostics_router, prefix="/api")
app.include_router(learning_router, prefix="/api")
app.include_router(learning_full_apply_router, prefix="/api")
app.include_router(ui_theme_dynamic_router, prefix="/api")
app.include_router(scheduler_router, prefix="/api")
app.include_router(media_workflow_router, prefix="/api")
app.include_router(rag_router, prefix="/api")

from app.api.terminal_ws import router as terminal_ws_router
app.include_router(terminal_ws_router)
