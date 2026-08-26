from pathlib import Path

from app.services.database_schema_design import build_database_plan, finalize_database_plan

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
ARCH = (ROOT / "frontend" / "src" / "components" / "architecture" / "ArchitecturePanels.tsx").read_text(encoding="utf-8")
ROUTES = (ROOT / "backend" / "app" / "api" / "routes.py").read_text(encoding="utf-8")
DESIGN = (ROOT / "backend" / "app" / "services" / "agent_factory_workflow_design.py").read_text(encoding="utf-8")

checks: dict[str, bool] = {
    "frontend version 5.345": "AGENTSTUDIO_FRONTEND_VERSION='5.356'" in APP,
    "right action renamed design review": "◇ 설계 검토" in APP,
    "project create simplified": "＋ 프로젝트 생성" in APP and "프로젝트 생성 (Workflow/DB 자동)" not in APP,
    "workspace duplicate workflow button removed": APP.count('className="requirement-collection-actions"') == 0,
    "live database preview endpoint": '@router.post("/database-design/preview")' in ROUTES,
    "live db preview UI": "DB 실시간 설계 · 초안" in APP and "liveDatabasePreviewTab" in APP,
    "live db tabs": all(token in APP for token in ("['MODULES','Module']", "['ENTITIES','Entity']", "['RELATIONS','관계']", "['DDL','DDL']")),
    "redis preview": "Redis Cache / Session" in APP and 'plan["redis_plan"]' in ROUTES,
    "interview context uses real newline": 'return "\\n".join(rows)' in ROUTES and 'return "\\\\n".join(rows)' not in ROUTES,
    "architecture raw state guard": "safeArchitectureText" in ARCH and "original_request" in ARCH and "JSON.stringify(item)" not in ARCH,
    "architecture lifecycle empty": "DESIGN ARCHITECTURE · NOT STARTED" in APP and "AS-BUILT ARCHITECTURE · PENDING" in APP,
    "fallback goal sanitized": "def _primary_user_goal" in DESIGN and '"goal": _primary_user_goal(request)' in DESIGN,
}

plan = build_database_plan(
    "PostgreSQL, Redis, pgvector를 사용하는 AI 상품 검색 추천 주문 Agent. 고객, 상품, 주문, 장바구니를 관리한다.",
    {},
)
modules = {item.get("id") for item in plan.get("modules") or []}
checks["live preview module source supports retail"] = {
    "CORE", "OBSERVABILITY", "RAG", "FILE", "CUSTOMER", "PRODUCT", "ORDER"
}.issubset(modules)
checks["preview ddl can be produced without mutating draft"] = bool(finalize_database_plan(plan).get("ddl")) and not plan.get("finalized")

failed = []
for name, ok in checks.items():
    print(f"[v5.345-contract] {name}: {'OK' if ok else 'FAIL'}")
    if not ok:
        failed.append(name)
if failed:
    raise SystemExit("FAILED: " + ", ".join(failed))
print("[v5.345-contract] PASS")
