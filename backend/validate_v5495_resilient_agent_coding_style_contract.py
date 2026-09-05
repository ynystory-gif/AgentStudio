from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")

def require(path: str, token: str) -> None:
    if token not in read(path):
        raise AssertionError(f"{path}: missing {token}")

def main() -> None:
    app = read("frontend/src/App.jsx")
    workflow = read("backend/app/services/agent_workflow.py")
    selector = read("backend/app/services/coding_rule_selector.py")
    registry = json.loads(read("backend/app/data/coding_style/rules.json"))

    keys = [
        "preflight_validation",
        "non_destructive_environment",
        "quality_gated_fallback",
        "typed_result_contract",
        "external_artifact_guard",
        "controlled_benchmark",
        "actionable_error_messages",
    ]
    for key in keys:
        if f"{key}:true" not in app:
            raise AssertionError(f"frontend default missing: {key}")
        if f'"{key}": True' not in workflow:
            raise AssertionError(f"backend default missing: {key}")
        if f'policy.get("{key}")' not in workflow:
            raise AssertionError(f"prompt instruction missing: {key}")

    assert registry.get("version") == "2.0"
    by_id = {row.get("id"): row for row in registry.get("rules") or []}
    for rule_id in [f"CS-{number}" for number in range(163, 170)]:
        if rule_id not in by_id:
            raise AssertionError(f"registry missing {rule_id}")
        if by_id[rule_id].get("source") != "document_loading_ocr_notebook":
            raise AssertionError(f"wrong source for {rule_id}")

    for token in ("paddleocr", "nvidia-smi", "quality_fallback", "benchmark", "artifact"):
        if token not in selector:
            raise AssertionError(f"selector tag missing: {token}")

    require("backend/app/data/coding_style/sources/document_loading_ocr_notebook.md", "44개 (Code 22 / Markdown 22)")
    require("backend/app/data/coding_style/sources/document_loading_ocr_notebook.md", "OpenCV 배포판")
    require("backend/app/data/coding_style/sources/document_loading_ocr_notebook.md", "Quality-gated fallback")
    require("backend/app/main.py", 'version="5.495"')
    require("backend/app/api/routes.py", '"version": "5.495"')
    require("frontend/src/App.jsx", "AGENTSTUDIO_FRONTEND_VERSION='5.495'")
    require("README_V5_495_ResilientAgentCodingStyle.md", "총 25개")
    print("v5.495 resilient Agent coding style contract PASS")

if __name__ == "__main__":
    main()
