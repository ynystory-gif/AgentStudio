from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = (ROOT / 'backend/app/services/model_router.py').read_text(encoding='utf-8')
WORKFLOW = (ROOT / 'backend/app/services/agent_factory_workflow_design.py').read_text(encoding='utf-8')
PATCH = (ROOT / 'backend/app/services/patch_service.py').read_text(encoding='utf-8')
DEBUG = (ROOT / 'backend/app/services/debug_service.py').read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
RUNTIME = (ROOT / 'backend/app/services/llm_runtime_status_service.py').read_text(encoding='utf-8')
CATALOG = (ROOT / 'backend/app/services/llm_catalog_service.py').read_text(encoding='utf-8')
APP = (ROOT / 'frontend/src/App.jsx').read_text(encoding='utf-8')

for name, text in {
    'model_router': MODEL,
    'workflow_design': WORKFLOW,
    'patch_service': PATCH,
    'debug_service': DEBUG,
    'routes': ROUTES,
    'runtime_status': RUNTIME,
    'catalog': CATALOG,
}.items():
    ast.parse(text, filename=name)

checks = {
    'frontend version 5.341': "AGENTSTUDIO_FRONTEND_VERSION='5.368'" in APP,
    'high performance task enum': all(x in MODEL for x in (
        'WORKFLOW_DESIGN = "workflow_design"',
        'DATABASE_SCHEMA_DESIGN = "database_schema_design"',
        'MULTI_FILE_CODE_CHANGE = "multi_file_code_change"',
        'EXECUTION_DEBUG_REPAIR = "execution_debug_repair"',
    )),
    'automatic high-performance Codex first': (
        'elif task in HIGH_PERFORMANCE_TASKS:' in MODEL
        and 'if s.codex_enabled:' in MODEL
        and 'candidates.append("codex")' in MODEL
        and 'if s.openai_enabled:' in MODEL
        and 'candidates.append("openai")' in MODEL
        and 'candidates.append("ollama")' in MODEL
    ),
    'manual/explicit provider preserved': (
        'explicit in {"ollama", "openai", "codex"}' in MODEL
        and 'strategy == "manual"' in MODEL
    ),
    'workflow and LangGraph use high performance task': (
        'model_for_task(LLMTask.WORKFLOW_DESIGN, provider)' in WORKFLOW
        and 'langgraph_branch_provider' in WORKFLOW
    ),
    'DB Entity relationship refinement uses high performance task': (
        'model_for_task(LLMTask.DATABASE_SCHEMA_DESIGN, provider)' in WORKFLOW
        and 'build_database_plan(request, parsed)' in WORKFLOW
        and 'database_provider' in WORKFLOW
    ),
    'complex project edit uses high performance task': (
        'async def ai_project_edit' in ROUTES
        and 'model_for_task(LLMTask.MULTI_FILE_CODE_CHANGE)' in ROUTES
    ),
    'single file edit remains standard task': (
        'async def ai_edit_code' in ROUTES
        and 'model_for_task(LLMTask.CODE_GENERATION)' in ROUTES
    ),
    'patch auto complexity classification': all(x in PATCH for x in (
        'def _patch_task_for_request',
        'len(files or {}) >= 2',
        'LLMTask.MULTI_FILE_CODE_CHANGE',
        'LLMTask.EXECUTION_DEBUG_REPAIR',
    )),
    'execution debug uses high performance task': 'model_for_task(LLMTask.EXECUTION_DEBUG_REPAIR, provider)' in DEBUG,
    'runtime exposes high performance routes': all(x in RUNTIME for x in (
        '"workflow_design": LLMTask.WORKFLOW_DESIGN',
        '"database_design": LLMTask.DATABASE_SCHEMA_DESIGN',
        '"multi_file_change": LLMTask.MULTI_FILE_CODE_CHANGE',
        '"debugging": LLMTask.EXECUTION_DEBUG_REPAIR',
    )),
    'catalog labels high performance tasks': all(x in CATALOG for x in (
        'Workflow 전체 / LangGraph 분기 설계',
        'DB Entity / 관계 설계',
        '복잡한 다중파일 코드 변경',
        '코드 실행·디버깅·대규모 수정',
    )),
    'settings explains Codex OpenAI Ollama priority': (
        'Codex → OpenAI → Ollama' in APP
        and '일반 작업 Ollama 우선' in APP
    ),
    'workflow UI exposes actual design provider': (
        'workflow-provider-routing-note' in APP
        and 'workflow_provider' in APP
        and 'database_provider' in APP
    ),
}

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(f"[v5.341-provider-contract] {name}: {'OK' if ok else 'FAIL'}")
if failed:
    raise SystemExit('FAILED: ' + ', '.join(failed))
print('[v5.341-provider-contract] PASS')
