from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN = (ROOT / "backend/app/services/agent_factory_workflow_design.py").read_text(encoding="utf-8")
WORKFLOW = (ROOT / "backend/app/services/agent_workflow.py").read_text(encoding="utf-8")
PLANNER = (ROOT / "backend/app/services/agent_factory_policy_planner.py").read_text(encoding="utf-8")
POLICY = (ROOT / "backend/app/data/agent_factory/generated_agent_test_environment_policy.json").read_text(encoding="utf-8")
APP = (ROOT / "frontend/src/App.jsx").read_text(encoding="utf-8")
MAIN = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
ROUTES = (ROOT / "backend/app/api/routes.py").read_text(encoding="utf-8")

checks = {
    "frontend version": "AGENTSTUDIO_FRONTEND_VERSION='5.384'" in APP,
    "backend version": 'version="5.384"' in MAIN,
    "health version": '"version": "5.384"' in ROUTES,
    "build marker": "GeneratedAgentTestEnvironmentRoleSeed" in ROUTES,
    "policy registered": "generated_agent_test_environment_policy.json" in PLANNER,
    "policy id": "GENERATED_AGENT_TEST_ENVIRONMENT_POLICY" in POLICY,
    "test environment plan": '"test_environment_plan"' in DESIGN,
    "role accounts": '"role_test_accounts"' in DESIGN,
    "default user 10": '"count": 10' in DESIGN and '"users"' in DESIGN,
    "product 50": '_seed_default("products", 50' in DESIGN,
    "super admin 1": '("SUPER_ADMIN"' in DESIGN and ', 1),' in DESIGN,
    "data isolation": '"test_batch_id"' in DESIGN and '"is_test"' in DESIGN,
    "production guard": '"deny_production": True' in DESIGN,
    "impersonation": '"short_lived": True' in DESIGN and '"audit": True' in DESIGN,
    "backend seed files": 'backend/app/services/test_data_service.py' in DESIGN and 'backend/app/routers/admin_test_environment.py' in DESIGN,
    "frontend test page": 'TestEnvironmentPage' in DESIGN,
    "file plan integration": 'Generated Agent Test Environment' in WORKFLOW,
    "code generation rule": 'plan.role_test_accounts' in WORKFLOW and 'production에서는 seed/reset/delete/impersonation' in WORKFLOW,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("FAIL v5.384 contract: " + ", ".join(failed))
print("PASS v5.384 Generated Agent Test Environment Role Seed contract")
