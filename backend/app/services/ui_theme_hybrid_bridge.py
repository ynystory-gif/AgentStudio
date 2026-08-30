"""Bind the hybrid Theme analyzer and its process lifecycle before API routes load."""
from __future__ import annotations

from app.services import ui_theme_layout_contract_service as layout_service
from app.services.chromium_browser_service import chromium_browser_manager
from app.services.ui_theme_hybrid_analysis_service import analyze_theme_with_layout_contract
from app.services.ui_theme_killable_process_service import shutdown_theme_workers

# ui_theme_dynamic_routes imports this symbol directly, so patch the module before the
# route module is imported by app.main.
layout_service.analyze_theme_with_layout_contract = analyze_theme_with_layout_contract

from app.api import ui_theme_dynamic_routes as dynamic_routes  # noqa: E402

dynamic_routes._JOB_TIMEOUT_SECONDS = 300
dynamic_routes._URL_ANALYSIS_TIMEOUT_SECONDS = dynamic_routes._JOB_TIMEOUT_SECONDS

# FastAPI lifespan already calls chromium_browser_manager.shutdown(). Extend that single
# shutdown path so AgentStudio-owned Theme Python/Playwright process trees are terminated
# first. This prevents a cancelled Theme job from keeping Backend shutdown/CTRL+C alive.
if not getattr(chromium_browser_manager, "_theme_worker_shutdown_wrapped", False):
    _original_browser_shutdown = chromium_browser_manager.shutdown

    async def _shutdown_browser_with_theme_workers():
        try:
            killed = await shutdown_theme_workers()
            if killed:
                print(f"[완료되었습니다] Theme 분석 Worker Process 종료: {killed}개")
        finally:
            await _original_browser_shutdown()

    chromium_browser_manager.shutdown = _shutdown_browser_with_theme_workers
    chromium_browser_manager._theme_worker_shutdown_wrapped = True
