"""Bind the hybrid static + rendered-CDP Theme analyzer before API routes are imported."""
from __future__ import annotations

from app.services import ui_theme_layout_contract_service as layout_service
from app.services.ui_theme_hybrid_analysis_service import analyze_theme_with_layout_contract

# ui_theme_dynamic_routes imports this symbol directly, so patch the module before the
# route module is imported by app.main.
layout_service.analyze_theme_with_layout_contract = analyze_theme_with_layout_contract
