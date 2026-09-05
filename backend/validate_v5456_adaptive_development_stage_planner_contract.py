from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.services.development_stage_planner import (  # noqa: E402
    apply_development_stage_plan_to_design,
    approve_development_stage_plan,
    recommend_development_stage_plan,
)

APP = (ROOT / "frontend/src/App.jsx").read_text(encoding="utf-8")
CSS = (ROOT / "frontend/src/styles.css").read_text(encoding="utf-8")
ROUTES = (ROOT / "backend/app/api/routes.py").read_text(encoding="utf-8")
MAIN = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
CODEX = (ROOT / "backend/app/services/codex_app_server_service.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / "backend/app/services/agent_workflow.py").read_text(encoding="utf-8")

rag_requirement = """
개발팀 문서 기반 RAG Agent. PDF/DOCX/PPTX/XLSX와 소스코드를 Parser Registry로 수집한다.
Vector Search + BM25 + Metadata Filter + Reranker Hybrid Search를 사용하고 pgvector와 Redis를 사용한다.
파일 Hash 기반 증분 색인, INDEX/SKIP/REINDEX/REMOVE를 지원한다.
PUBLIC/INTERNAL/RESTRICTED/NO_INDEX, ACL, Sensitive Data Scanner, Redaction, BLOCKED, 완전 제거가 필요하다.
Benchmark P50/P95, 1GB/10GB, Golden Dataset, Hallucination 품질 평가가 필요하다.
React TypeScript + FastAPI + LangGraph를 사용한다.
"""
plan = recommend_development_stage_plan(rag_requirement, [], {}, "")
approved = approve_development_stage_plan(plan)
design = apply_development_stage_plan_to_design({
    "file_plan": {
        "new_files": [
            {"path": "backend/services/retrieval.py", "purpose": "RAG hybrid search"},
            {"path": "backend/services/indexer.py", "purpose": "document parser and reindex"},
            {"path": "backend/services/security.py", "purpose": "ACL redaction security"},
            {"path": "backend/services/benchmark.py", "purpose": "benchmark quality metrics"},
        ]
    }
}, approved)

checks = {
    "version sync": (
        "AGENTSTUDIO_FRONTEND_VERSION='5.456'" in APP
        and 'version="5.456"' in MAIN
        and '"version": "5.456"' in ROUTES
        and 'AGENTSTUDIO_CODEX_CLIENT_VERSION = "5.456"' in CODEX
    ),
    "rag requirement recommends four stages": plan.get("recommended_stage_count") == 4,
    "rag stage ids": [s.get("id") for s in plan.get("stages", [])] == [
        "STAGE_1_CORE_RAG",
        "STAGE_2_DOCUMENT_INDEX",
        "STAGE_3_SECURITY",
        "STAGE_4_PERFORMANCE_QUALITY",
    ],
    "recommendation requires approval": plan.get("approval_required") is True and plan.get("approved") is False,
    "approval creates approved plan": approved.get("approved") is True and approved.get("status") == "APPROVED",
    "approved plan creates development workflow": design.get("development_workflow", {}).get("stage_count") == 4,
    "planned files receive stage ids": all(
        isinstance(row, dict) and row.get("development_stage_id")
        for row in design.get("file_plan", {}).get("new_files", [])
    ),
    "recommend endpoint": '/workflow/development-stage-plan/recommend' in ROUTES,
    "approve endpoint": '/workflow/development-stage-plan/approve' in ROUTES,
    "workflow approval gate": 'DEVELOPMENT_STAGE_APPROVAL_REQUIRED' in ROUTES,
    "workflow applies approved stages": 'apply_development_stage_plan_to_design(design, development_stage_plan)' in ROUTES,
    "frontend recommendation panel": 'function DevelopmentStageRecommendationPanel' in APP,
    "frontend approve action": '이 단계로 승인하고 Workflow 구성' in APP and 'approveDevelopmentStages' in APP,
    "frontend auto workflow after approval": "previewTargetWorkflow('',{stageApprovalBypass:true,approvedStagePlan:approved})" in APP,
    "workflow visual": 'function DevelopmentStageWorkflowDiagram' in APP and '<DevelopmentStageWorkflowDiagram' in APP,
    "agent factory receives development workflow": 'development_stage_instruction' in WORKFLOW and 'development_stage_id' in WORKFLOW,
    "stage css": 'Adaptive Development Stage Planner' in CSS,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("v5.456 contract failed: " + ", ".join(failed))
print(f"v5.456 contracts: {len(checks)}/{len(checks)} PASS")
