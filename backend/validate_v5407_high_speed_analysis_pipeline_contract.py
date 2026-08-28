from __future__ import annotations

import asyncio
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend/src/App.jsx").read_text(encoding="utf-8")
MAIN = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
ROUTES = (ROOT / "backend/app/api/routes.py").read_text(encoding="utf-8")
PROJECT_ANALYZER = (ROOT / "backend/app/services/project_analyzer.py").read_text(encoding="utf-8")
HIGH_SPEED = (ROOT / "backend/app/services/high_speed_analysis.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / "backend/app/services/agent_workflow.py").read_text(encoding="utf-8")

checks = {
    "version": "AGENTSTUDIO_FRONTEND_VERSION='5.407'" in APP and 'version="5.407"' in MAIN and '"version": "5.407"' in ROUTES,
    "high_speed_module": "def analyze_project_candidates(" in HIGH_SPEED and "def high_speed_analysis_status(" in HIGH_SPEED,
    "bm25": "def _bm25_scores(" in HIGH_SPEED,
    "ast": "ast.parse" in HIGH_SPEED and "python_ast" in HIGH_SPEED,
    "dependency_graph": "def _build_dependency_graph(" in HIGH_SPEED and "dependency_graph_expansion" in HIGH_SPEED,
    "torch_fallback": "torch_tensor_fusion" in HIGH_SPEED and "python_fallback" in HIGH_SPEED,
    "incremental_cache": "incremental_mtime_size_parallel" in PROJECT_ANALYZER and "_SCAN_CACHE" in PROJECT_ANALYZER,
    "parallel_index": "ThreadPoolExecutor" in PROJECT_ANALYZER and "parallel_workers" in PROJECT_ANALYZER,
    "single_scan": "scan_data=data" in PROJECT_ANALYZER,
    "workflow_integration": "local_project_summary" in WORKFLOW and "project_analysis" in WORKFLOW,
    "status_endpoint": '/project/high-speed-analysis/status' in ROUTES,
    "analysis_endpoint": '/project/high-speed-analysis' in ROUTES,
    "no_embedding_first_pass": '"embedding_called": False' in HIGH_SPEED and '"llm_called": False' in HIGH_SPEED,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("v5.407 static contract FAIL: " + ", ".join(failed))


async def runtime_contract() -> None:
    import sys
    sys.path.insert(0, str(ROOT / "backend"))

    from app.services.local_control import register_runtime_project_root
    from app.services.project_analyzer import local_project_summary

    project = Path(tempfile.mkdtemp(prefix="agentstudio_v5407_"))
    (project / "app").mkdir()
    (project / "app" / "order_service.py").write_text(
        "from app.order_repo import save_order\n\ndef create_order(customer_id):\n    return save_order(customer_id)\n",
        encoding="utf-8",
    )
    (project / "app" / "order_repo.py").write_text(
        "def save_order(customer_id):\n    return {'id': 1, 'customer_id': customer_id}\n",
        encoding="utf-8",
    )
    (project / "app" / "product_service.py").write_text(
        "def find_product(query):\n    return []\n",
        encoding="utf-8",
    )
    (project / "README.md").write_text("Order Agent sample", encoding="utf-8")
    register_runtime_project_root(str(project))

    first = await local_project_summary(str(project), "주문 생성 create_order 오류 수정")
    second = await local_project_summary(str(project), "주문 생성 create_order 오류 수정")

    related = [item.get("relative") for item in first.get("related_files") or []]
    assert related and related[0] == str(Path("app/order_service.py")), related
    assert first.get("analysis_mode") == "HIGH_SPEED_LOCAL"
    assert first.get("llm_called") is False
    assert first.get("embedding_called") is False
    assert int(second.get("scan_cache", {}).get("reused_files") or 0) >= 4
    assert int(second.get("scan_cache", {}).get("reindexed_files") or 0) == 0
    assert first.get("high_speed_pipeline", {}).get("candidate_count", 0) > 0


asyncio.run(runtime_contract())
print(f"v5.407 High-Speed Analysis Pipeline contract PASS {len(checks)}/{len(checks)} + runtime")
