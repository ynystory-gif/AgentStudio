import asyncio
import sys

# Windows + psycopg async requires SelectorEventLoop.
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except Exception:
        pass

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import init_db, migrate_agentstudio_schema
from app.api.routes import router
from app.services.langgraph_runtime import agent_graph_runtime
from app.services.mcp_registry import mcp_registry_monitor
from app.services.settings_service import migrate_env_settings_to_db, load_db_settings_into_runtime, register_current_machine, resolve_pending_machine_name
from app.core.machine_identity import ensure_pc_name_env
from app.services.project_root_registry import restore_registered_project_roots
from app.services.llm_usage_service import prune_llm_history
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
        print(
            f"[완료되었습니다] DB 스키마 보정: "
            f"{schema_migration.get('count', 0)}개"
        )
        migration = await migrate_env_settings_to_db()
        runtime = await load_db_settings_into_runtime()

        # v5.284: local PostgreSQL remains the bootstrap/control DB; Supabase activation is verified before switch.
        # If Supabase was selected on this PC, switch the runtime DB only after
        # local settings have been restored safely.
        runtime_db = await apply_saved_database_provider()

        print("[완료되었습니다] PostgreSQL/pgvector 초기화")
        print(
            f"[완료되었습니다] Runtime DB: {runtime_db.get('active_provider', 'local')} "
            f"· {runtime_db.get('target', '')}"
        )
        if not runtime_db.get("ok", True):
            print(f"[경고] Runtime DB 전환: {runtime_db.get('message', '')}")

        if migration.get("migrated"):
            print(f"[완료되었습니다] 설정 DB 이관: {migration['migrated']}개")

        print(
            f"[완료되었습니다] DB 설정 런타임 적용: "
            f"{runtime.get('loaded', 0)}개"
        )

        project_roots = await restore_registered_project_roots()
        print(
            f"[완료되었습니다] 등록 프로젝트 허용 경로 복원: "
            f"{project_roots.get('restored_count', 0)}개"
        )
        legacy_adoption = dict(project_roots.get("legacy_adoption") or {})
        if legacy_adoption.get("claimed_count"):
            print(
                f"[완료되었습니다] 레거시 프로젝트 현재 PC 귀속: "
                f"{legacy_adoption.get('claimed_count', 0)}개 · PC={project_roots.get('pc_name', '')}"
            )
        if project_roots.get("missing_count"):
            print(
                f"[안내] 현재 PC에 존재하지 않는 등록 프로젝트 경로: "
                f"{project_roots.get('missing_count', 0)}개"
            )

        try:
            history_prune = prune_llm_history(force=True)
            print(
                f"[완료되었습니다] LLM 요청/응답 10일 보관 정리: "
                f"삭제 {history_prune.get('removed', 0)}개"
            )
        except Exception as history_error:
            print(f"[경고] LLM 요청/응답 보관 정리 실패: {history_error}")
    except Exception as e:
        orig = getattr(e, "orig", None)
        sqlstate = str(getattr(orig, "sqlstate", "") or getattr(orig, "pgcode", "") or "")
        if sqlstate == "28P01":
            print("[경고] PostgreSQL 초기화 실패: 데이터베이스 사용자 비밀번호 인증에 실패했습니다. 시스템 관리의 DATABASE URL을 확인하세요.")
        elif sqlstate.startswith("08"):
            print("[경고] PostgreSQL 초기화 실패: PostgreSQL 서버 연결이 끊겼습니다. 서버/포트/서비스 상태를 확인하세요.")
        else:
            print(f"[경고] PostgreSQL 초기화 실패: {e}")

    # v5.326: BrowserRuntime stale cleanup must never hold FastAPI startup at
    # "Waiting for application startup". SYSTEM_ADMIN already performs a bounded
    # bulk cleanup; direct backend launches get the same cleanup in background.
    await agent_graph_runtime.start()
    await mcp_registry_monitor.start()

    async def _background_browser_cleanup():
        try:
            browser_cleanup = await chromium_browser_manager.cleanup_stale_processes()
            if browser_cleanup.get("killed") or browser_cleanup.get("remaining"):
                print(
                    f"[완료되었습니다] 이전 BrowserRuntime 백그라운드 정리: "
                    f"kill {browser_cleanup.get('killed', 0)} · remaining {browser_cleanup.get('remaining', 0)}"
                )
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

app = FastAPI(title="THEANOVA AgentStudio", version="5.369", lifespan=lifespan)

# Frontend 개발 서버(Vite)와 Backend API 간 CORS 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
    ],
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
        f.write(
            f"[{datetime.now().isoformat()}] "
            "AgentStudio Backend startup completed\n"
        )

app.include_router(router, prefix="/api")

from app.api.terminal_ws import router as terminal_ws_router
app.include_router(terminal_ws_router)
