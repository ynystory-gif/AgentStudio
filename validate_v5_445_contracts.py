from pathlib import Path

ROOT = Path(__file__).resolve().parent
checks = []

def require(path: str, needle: str, label: str):
    text = (ROOT / path).read_text(encoding="utf-8")
    ok = needle in text
    checks.append((label, ok))
    if not ok:
        raise AssertionError(f"{label}: missing {needle!r} in {path}")

require("frontend/src/components/learning/LlmLearningCenter.tsx", "/learning/sql-export", "frontend dynamic SQL export endpoint")
require("frontend/src/components/learning/LlmLearningCenter.tsx", "case_ids:kind==='cases'?cases.map", "case SQL uses visible IDs")
require("frontend/src/components/learning/LlmLearningCenter.tsx", "dataset_ids:kind==='cases'?[]:datasets.map", "dataset/training SQL uses visible IDs")
require("backend/app/api/learning_routes.py", '@router.post("/sql-export")', "backend SQL export route")
require("backend/app/services/learning_sql_export_service.py", "a.pc_name =", "current PC application condition")
require("backend/app/services/learning_sql_export_service.py", "Dataset은 모든 PC의 공용 학습 데이터", "shared Dataset policy")
require("backend/app/services/learning_sql_export_service.py", "visible_cases", "misjudgment visible snapshot")
require("backend/app/services/learning_sql_export_service.py", "visible_datasets", "dataset visible snapshot")
require("backend/app/services/llm_learning_service.py", '"read_mode": "bulk_read_only"', "bulk read-only Dataset list")
require("backend/app/services/learning_collection_service.py", '"reason": "read_only_list"', "misjudgment GET skips history sync")
require("backend/app/services/learning_visibility_bridge.py", "repair_mappings=False", "list GET skips mapping repair writes")
require("backend/app/services/ollama_model_manager_service.py", "_MODEL_STATUS_TTL_SECONDS = 600.0", "Ollama status cache")
require("frontend/src/App.jsx", "AGENTSTUDIO_FRONTEND_VERSION='5.445'", "frontend version")
require("backend/app/main.py", 'version="5.445"', "backend version")

print(f"v5.445 contracts: {sum(ok for _, ok in checks)}/{len(checks)} PASS")
for label, ok in checks:
    print(f"{'PASS' if ok else 'FAIL'} - {label}")
