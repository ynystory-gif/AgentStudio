from __future__ import annotations

import tempfile
from pathlib import Path

from app.services.database_schema_design import (
    build_database_plan,
    finalize_database_plan,
    materialize_database_plan,
    validate_database_plan,
)

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
ROUTES = (ROOT / "backend" / "app" / "api" / "routes.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / "backend" / "app" / "services" / "agent_workflow.py").read_text(encoding="utf-8")
DESIGNER = (ROOT / "backend" / "app" / "services" / "agent_factory_workflow_design.py").read_text(encoding="utf-8")

checks: dict[str, bool] = {}

no_db = build_database_plan(
    "PDF 파일을 선택해서 요약하고 React 화면에 보여준다. 데이터베이스는 사용하지 않는다.",
    {},
)
checks["explicit no-db stays disabled"] = (
    no_db.get("enabled") is False
    and no_db.get("tables") == []
    and no_db.get("finalized") is True
)

order = build_database_plan(
    "고객이 상품을 자연어로 검색하고 주문하며 PostgreSQL과 pgvector RAG를 사용하는 Agent",
    {},
)
module_ids = {x.get("id") for x in order.get("modules") or []}
checks["module selector core dependencies"] = {
    "CORE", "OBSERVABILITY", "RAG", "FILE", "CUSTOMER", "PRODUCT", "ORDER"
}.issubset(module_ids)
checks["database plan validator"] = bool((order.get("validation") or {}).get("valid"))

finalized = finalize_database_plan(order)
ddl = finalized.get("ddl") or ""
checks["finalize creates ddl"] = (
    finalized.get("finalized") is True
    and "CREATE EXTENSION IF NOT EXISTS vector" in ddl
    and "CREATE TABLE IF NOT EXISTS agents" in ddl
    and "CREATE TABLE IF NOT EXISTS orders" in ddl
    and "REFERENCES customers(id)" in ddl
)

custom = build_database_plan(
    "PostgreSQL을 사용하는 예약 Agent",
    {
        "database_plan": {
            "custom_tables": [
                {
                    "name": "reservations",
                    "purpose": "예약 업무",
                    "columns": [
                        {"name": "id", "type": "BIGSERIAL", "primary_key": True, "nullable": False},
                        {"name": "agent_id", "type": "BIGINT", "references": "agents.id", "nullable": False},
                        {"name": "reserved_at", "type": "TIMESTAMPTZ", "nullable": False},
                    ],
                }
            ]
        }
    },
)
checks["custom business entity merged"] = any(x.get("name") == "reservations" for x in custom.get("tables") or [])
checks["custom business entity validated"] = validate_database_plan(custom).get("valid") is True

unsafe = dict(custom)
unsafe["tables"] = list(custom.get("tables") or []) + [{
    "name": "bad-table;drop",
    "columns": [{"name": "id", "type": "BIGINT", "primary_key": True}],
}]
checks["unsafe identifier rejected"] = validate_database_plan(unsafe).get("valid") is False

with tempfile.TemporaryDirectory() as tmp:
    files = materialize_database_plan(tmp, finalized)
    ddl_path = Path(tmp) / "backend" / "migrations" / "001_initial_schema.sql"
    readme_path = Path(tmp) / "backend" / "migrations" / "README.md"
    checks["migration materialization"] = (
        len(files) == 2
        and ddl_path.exists()
        and readme_path.exists()
        and "CREATE TABLE IF NOT EXISTS orders" in ddl_path.read_text(encoding="utf-8")
    )

checks.update({
    "frontend version 5.341": "AGENTSTUDIO_FRONTEND_VERSION='5.369'" in APP,
    "workflow DB design card": "DB 자동 설계" in APP and "finalizeDatabaseDesign" in APP,
    "project create carries database plan": "database_plan:targetWorkflowPreview?.database_plan||{}" in APP,
    "database confirmation gate": "databasePlan?.enabled&&!databasePlan?.finalized" in APP,
    "finalize API": '@router.post("/database-design/finalize")' in ROUTES,
    "project materializes migration": "materialize_database_plan" in ROUTES,
    "workflow database node": '"database_design"' in WORKFLOW and "database_design_node" in WORKFLOW,
    "code generation receives database plan": '"database_plan": state.get("database_plan", {})' in WORKFLOW,
    "design bundle requests database plan": '"database_plan": {' in DESIGNER,
})

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(f"[v5.341-db-contract] {name}: {'OK' if ok else 'FAIL'}")
if failed:
    raise SystemExit("FAILED: " + ", ".join(failed))
print("[v5.341-db-contract] PASS")
