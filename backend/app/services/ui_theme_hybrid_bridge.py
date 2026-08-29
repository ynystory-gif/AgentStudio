"""Bind the hybrid static + rendered-CDP Theme analyzer before API routes are imported."""
from __future__ import annotations

from app.services import ui_theme_layout_contract_service as layout_service
from app.services.ui_theme_hybrid_analysis_service import analyze_theme_with_layout_contract

# ui_theme_dynamic_routes imports this symbol directly, so patch the module before the
# route module is imported by app.main.
layout_service.analyze_theme_with_layout_contract = analyze_theme_with_layout_contract

# Import the route only after the analyzer symbol has been replaced. Hybrid analysis has
# its own bounded static/browser stages, so the outer URL/job limits should accommodate
# both passes without returning to the old five-minute monolithic wait.
from app.api import ui_theme_dynamic_routes as dynamic_routes  # noqa: E402

dynamic_routes._URL_ANALYSIS_TIMEOUT_SECONDS = 100
dynamic_routes._JOB_TIMEOUT_SECONDS = 180
