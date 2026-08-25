from __future__ import annotations

import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "backend/app/services/agent_workflow.py"
DESIGN = ROOT / "backend/app/services/agent_factory_workflow_design.py"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


source = read(SOURCE)
design = read(DESIGN)

# Static policy checks.
for token in (
    '"react_typescript"',
    'frontend/src/App.tsx',
    'frontend/src/layouts/AppLayout',
    'frontend/src/components/layout/TopHeader',
    'frontend/src/components/layout/Sidebar',
    'frontend/src/components/layout/Footer',
    'frontend/src/pages/HomePage',
    'frontend/src/types/index.ts',
    'app_max_lines',
    'App.tsx에는 화면 전체 구현을 몰아넣지 말고',
    'React + TypeScript 확정 요구에서 .jsx/.js Frontend entry가 생성되었습니다.',
):
    require(token in source, f"generated TypeScript modular policy missing: {token}")

require("React + TypeScript가 확정되면 Frontend src 파일은 .tsx/.ts" in design,
        "Agent design prompt must preserve React TypeScript language contract")
require("App.tsx는 Route/Page/Layout 조립만 담당" in design,
        "Agent design prompt must prohibit App.tsx monolith")
require("components/layout/TopHeader" in design and "Sidebar" in design and "Footer" in design,
        "Agent design prompt must require layout component split")

# Execute the small deterministic file-plan helpers without importing LangGraph/App dependencies.
module = ast.parse(source)
needed = {
    "_append_planned_file",
    "_map_component_file",
    "_normalize_react_frontend_plan_extensions",
    "_react_frontend_minimum_files",
    "_ensure_minimum_agent_file_plan",
}
nodes = [node for node in module.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in needed]
require({node.name for node in nodes} == needed, "could not locate all file-plan helper functions")
mini = ast.Module(body=nodes, type_ignores=[])
ns = {"json": json}
exec(compile(mini, str(SOURCE), "exec"), ns)

plan = {
    "new_files": [
        {"path": "frontend/src/App.jsx", "purpose": "legacy LLM proposal", "required": True, "component": "frontend"},
        {"path": "frontend/src/main.jsx", "purpose": "legacy LLM proposal", "required": True, "component": "frontend"},
        {"path": "frontend/src/services/api.js", "purpose": "legacy LLM proposal", "required": True, "component": "frontend"},
    ],
    "component_file_map": [
        {"component": "React Frontend", "files": ["frontend/src/App.jsx"], "status": "planned"}
    ],
}
request = "React 타입스크립트로 AI 상품 검색 추천 주문 Agent를 만들어줘"
bundle = {"full_request": request, "settings_plan": {"enabled": False}, "database_plan": {"enabled": False}}
result = ns["_ensure_minimum_agent_file_plan"](plan, request, bundle)
paths = {
    (item if isinstance(item, str) else item.get("path", "")).replace("\\", "/")
    for item in result.get("new_files", [])
}

required_ts = {
    "frontend/src/main.tsx",
    "frontend/src/App.tsx",
    "frontend/src/layouts/AppLayout.tsx",
    "frontend/src/components/layout/TopHeader.tsx",
    "frontend/src/components/layout/Sidebar.tsx",
    "frontend/src/components/layout/Footer.tsx",
    "frontend/src/pages/HomePage.tsx",
    "frontend/src/services/api.ts",
    "frontend/src/types/index.ts",
    "frontend/src/styles/global.css",
    "frontend/tsconfig.json",
    "frontend/vite.config.ts",
}
require(required_ts.issubset(paths), f"missing TypeScript modular files: {sorted(required_ts - paths)}")
require("frontend/src/App.jsx" not in paths, "App.jsx must be removed for React TypeScript")
require("frontend/src/main.jsx" not in paths, "main.jsx must be removed for React TypeScript")
require("frontend/src/services/api.js" not in paths, "api.js must be removed for React TypeScript")

contract = result.get("frontend_contract") or {}
require(contract.get("language") == "TypeScript", "frontend contract must be TypeScript")
require(contract.get("app_entry") == "frontend/src/App.tsx", "frontend contract entry must be App.tsx")
require(contract.get("modular_layout_required") is True, "modular layout must be required")

mapping = next((x for x in result.get("component_file_map", []) if x.get("component") == "React Frontend"), {})
map_files = set(mapping.get("files") or [])
require("frontend/src/App.tsx" in map_files, "component map must normalize App.jsx -> App.tsx")
require("frontend/src/layouts/AppLayout.tsx" in map_files, "component map must include modular layout files")

print("PASS v5.345 Generated React TypeScript modular frontend contract")
