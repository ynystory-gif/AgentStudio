from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


agent_workflow = read(BACKEND / "app/services/agent_workflow.py")
design = read(BACKEND / "app/services/agent_factory_workflow_design.py")
routes = read(BACKEND / "app/api/routes.py")
jobs = read(BACKEND / "app/services/job_manager.py")
as_built = read(BACKEND / "app/services/as_built_architecture.py")
app = read(FRONTEND / "src/App.jsx")
main = read(BACKEND / "app/main.py")

# Version / build marker.
require("5.345" in app, "Frontend version must be 5.345")
require('version="5.345"' in main or "version='5.345'" in main, "FastAPI version must be 5.345")
require('"version": "5.345"' in routes, "Health version must be 5.345")
require("GeneratedAgentSetupIncrementalBuildTrace" in routes, "Health build marker missing")

# Generated Agent setup-first runtime gate.
require("[SETUP_REQUIRED] Initial settings are not complete." in agent_workflow, "Generated CMD setup-required state missing")
require('if "%EXITCODE%"=="2"' in agent_workflow, "Generated CMD must distinguish setup-required ExitCode=2")
require('$SetupManifest = Join-Path $RuntimeRoot "setup_requirements.json"' in agent_workflow, "Setup manifest path missing")
require("function Test-InitialConfiguration" in agent_workflow, "Initial configuration gate missing")
require("FastAPI/Frontend를 시작하거나 app.main을 import하지 않습니다." in agent_workflow, "Setup gate must explicitly avoid runtime/import")
require("_build_generated_setup_manifest" in agent_workflow, "Generated setup manifest builder missing")
require('root / ".agentstudio" / "setup_requirements.json"' in agent_workflow, "Setup manifest write missing")
require("settings_plan=settings_plan" in agent_workflow, "Generated launcher must receive settings plan")
require("database_plan=database_plan" in agent_workflow, "Generated launcher must receive database plan")
require("environment_plan=environment_plan" in agent_workflow, "Generated launcher must receive environment plan")
require("requirement_spec=requirement_spec" in agent_workflow, "Generated setup gate must inspect target requirements")
require("DATABASE_URL" in agent_workflow and "REDIS_URL" in agent_workflow, "DB/Redis fallback setup keys missing")

# Check actual main try block call ordering, not just function declaration ordering.
try_pos = agent_workflow.index('try {\n    Write-Host ""\n    Write-Host "============================================================"', agent_workflow.index("function Start-Frontend"))
gate_call = agent_workflow.index("if (-not (Test-InitialConfiguration))", try_pos)
python_call = agent_workflow.index("Ensure-Python312", gate_call)
pip_call = agent_workflow.index("Ensure-BackendDependencies", gate_call)
npm_call = agent_workflow.index("Ensure-FrontendDependencies", gate_call)
import_call = agent_workflow.index("Test-BackendImport", gate_call)
backend_start = agent_workflow.index("Start-Backend", gate_call)
require(gate_call < min(python_call, pip_call, npm_call, import_call, backend_start), "Setup gate must execute before dependency install/import/runtime")
require("exit 2" in agent_workflow[gate_call:python_call], "Setup-required path must exit before dependencies/runtime")

# Lightweight real build trace.
require("events: list[dict] = field(default_factory=list)" in jobs, "Job event list missing")
require('last_node: str = ""' in jobs, "Job last_node missing")
require("event_detail" in jobs, "Job event detail support missing")
require("job.events.append" in jobs, "Job node events are not recorded")
require("_AGENT_BUILD_NODE_PROGRESS" in routes, "Agent build node progress map missing")
require('stream_mode="updates"' in routes, "LangGraph build must stream node updates")
require("_run_agent_graph_with_progress" in routes, "Agent graph progress runner missing")
require("생성 진행 로그" in app, "Frontend live build log panel missing")
require("LLM 추가 호출 없음" in app, "Frontend must clarify logs do not add LLM calls")
require("jobState.last_node" in app and "jobState.events" in app, "Frontend must consume actual node/event state")

# Incremental workflow/design revision.
require("previous_design: dict = {}" in routes, "Workflow preview previous_design field missing")
require("design_agent_factory_incremental" in routes, "Workflow preview must call incremental designer")
for mode in ("FULL_INITIAL", "FULL_REUSE", "PARTIAL_REVISE", "FULL_REDESIGN"):
    require(mode in design, f"Incremental design mode missing: {mode}")
require("updated_sections" in design, "Partial design must request section-only updates")
require("affected_sections" in design and "reused_sections" in design, "Incremental design impact/reuse metadata missing")
require("LLMTask.DATABASE_SCHEMA_DESIGN" in design, "DB delta must retain high-performance schema design")
require("previous_design:targetWorkflowPreview||previousTargetWorkflowPreview||{}" in app, "Frontend must send previous design for incremental preview")
require("previousTargetWorkflowPreview" in app, "Frontend previous design cache missing")

# Incremental code generation / re-use.
require('revision_mode == "FULL_REUSE"' in agent_workflow, "Code full reuse path missing")
require('revision_mode == "PARTIAL_REVISE"' in agent_workflow, "Code partial revise path missing")
require("_incremental_focus_paths" in agent_workflow, "Incremental code focus path selection missing")
require('"incremental_mode": "FULL_REUSE", "llm_called": False' in agent_workflow, "Full reuse must skip code LLM")
require('code_plan_validation["incremental_mode"] = "PARTIAL_REVISE"' in agent_workflow, "Partial code revision marker missing")
require("Do not rewrite the whole project" in agent_workflow or "전체 프로젝트" in agent_workflow, "Partial revision prompt must discourage full rewrite")

# Incremental As-Built reuse based on actual source fingerprint.
require("source_fingerprint" in as_built and "hashlib.sha256" in as_built, "As-Built source fingerprint missing")
require('analysis_mode"] = "incremental_static_scan_no_llm"' in agent_workflow, "Non-structural As-Built no-LLM path missing")
require("incremental_full_reuse_no_llm" in agent_workflow, "As-Built full reuse no-LLM path missing")

print("PASS v5.345 Generated Agent Setup + Incremental Build Trace contract")
