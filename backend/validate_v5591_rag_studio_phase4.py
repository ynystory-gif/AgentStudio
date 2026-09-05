from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
FRONTEND = ROOT / 'frontend'

APP = (FRONTEND / 'src/app/App.tsx').read_text(encoding='utf-8')
MAIN = (BACKEND / 'app/main.py').read_text(encoding='utf-8')
API_ROUTES = (BACKEND / 'app/api/routes.py').read_text(encoding='utf-8')
RAG_ROUTES = (BACKEND / 'app/api/rag_routes.py').read_text(encoding='utf-8')
MODELS = (BACKEND / 'app/models/rag_entities.py').read_text(encoding='utf-8')
INTEGRATION = (BACKEND / 'app/rag/agent_integration_service.py').read_text(encoding='utf-8')
EXECUTOR = (BACKEND / 'app/services/prompt_tool_studio_executor.py').read_text(encoding='utf-8')
RAG_UI = (FRONTEND / 'src/features/rag/components/RagStudio.tsx').read_text(encoding='utf-8')
RAG_CSS = (FRONTEND / 'src/features/rag/ragStudio.css').read_text(encoding='utf-8')
RAG_API = (FRONTEND / 'src/features/rag/ragApi.ts').read_text(encoding='utf-8')
RAG_TYPES = (FRONTEND / 'src/features/rag/ragTypes.ts').read_text(encoding='utf-8')

assert "AGENTSTUDIO_FRONTEND_VERSION='5.591'" in APP
assert 'version="5.591"' in MAIN
assert '"version": "5.591"' in API_ROUTES
assert 'RagStudioPhase4AgentIntegration' in API_ROUTES

# Mandatory DB table rule: every RAG table, including phase-4 tables, has auto-increment id.
for class_name in (
    'RagStudioSetting', 'RagCollection', 'RagSource', 'RagCollectionSource',
    'RagDocument', 'RagChunk', 'RagEmbedding', 'RagIndexJob',
    'RagRetrievalSetting', 'RagSearchLog', 'RagAgentTool',
    'RagWorkflowBinding', 'RagAgentTestLog',
):
    match = re.search(rf'class {class_name}\(Base\):(?P<body>[\s\S]*?)(?=\nclass |\Z)', MODELS)
    assert match, class_name
    assert 'id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)' in match.group('body'), class_name

for table in ('rag_agent_tools', 'rag_workflow_bindings', 'rag_agent_test_logs'):
    assert f'__tablename__ = "{table}"' in MODELS, table

# Required phase-4 API contracts.
for route in (
    "@router.get('/tools')",
    "@router.post('/tools/generate')",
    "@router.put('/tools/{tool_id}/prompt-context')",
    "@router.post('/tools/{tool_id}/register')",
    "@router.post('/tools/{tool_id}/workflow-bind')",
    "@router.post('/tools/{tool_id}/execute')",
    "@router.post('/tools/{tool_id}/agent-test/prepare')",
    "@router.get('/agent-test-logs')",
):
    assert route in RAG_ROUTES, route

# Tool generation freezes Retrieval config and creates Prompt/Tool Studio contract.
for token in (
    'def _safe_tool_name',
    "'studio_tool': {",
    "'studio_route': {",
    "'agentstudio_internal': True",
    "'path': f'/api/rag/tools/{row.id}/execute'",
    'async def generate_agent_tool',
    'async def update_prompt_context',
    'async def bind_workflow',
    'async def execute_rag_tool',
    'async def prepare_agent_test',
    "'trace': ['Knowledge', 'RAG Tool', 'Prompt & Tool Studio', 'Workflow', 'Agent Test']",
):
    assert token in INTEGRATION, token

# Prompt & Tool Studio executes the generated RAG Tool internally without port hardcoding.
for token in (
    "bool(cfg.get('agentstudio_internal'))",
    "re.fullmatch(r'/api/rag/tools/(\\d+)/execute', internal_path)",
    'from app.rag.agent_integration_service import execute_rag_tool',
    "test_mode='PROMPT_TOOL_STUDIO'",
):
    assert token in EXECUTOR, token
assert "internal_path.startswith('/api/rag/tools/')" in EXECUTOR

# Frontend phase-4 UX and real state handoff.
for token in (
    '4차 · Agent 연결',
    '+ RAG Tool 생성',
    'Prompt Context 연결',
    'Prompt & Tool Studio 열기',
    'Workflow 연결',
    'RAG Tool Test',
    'Agent Test 연결',
    'Knowledge</span><i>→</i><span>RAG Tool',
    'generateRagAgentTool',
    'prepareRagAgentTest',
    'onSyncPromptTool',
    'onBindWorkflow',
    'onOpenAgentTest',
):
    assert token in RAG_UI, token

for endpoint in (
    '/api/rag/tools?project_root=',
    '/api/rag/tools/generate',
    '/register',
    '/prompt-context',
    '/workflow-bind',
    '/execute',
    '/agent-test/prepare',
    '/api/rag/agent-test-logs',
):
    assert endpoint in RAG_API, endpoint

for type_name in ('RagAgentTool', 'RagWorkflowBindingResult', 'RagToolTestResult', 'RagAgentTestPreparation', 'RagAgentTestLog'):
    assert f'interface {type_name}' in RAG_TYPES, type_name

for token in (
    'syncRagAgentToolToPromptStudio',
    'bindRagToolToTargetWorkflow',
    'openRagAgentTestInPromptStudio',
    "tab:'TEST'",
    'rag_integration',
    'onSyncPromptTool={syncRagAgentToolToPromptStudio}',
):
    assert token in APP, token

# RAG feature CSS must keep the 13px readability floor.
for size in re.findall(r'font-size\s*:\s*(\d+(?:\.\d+)?)px', RAG_CSS):
    assert float(size) >= 13, f'font-size below 13px: {size}px'
for size in re.findall(r'font\s*:\s*(\d+(?:\.\d+)?)px', RAG_CSS):
    assert float(size) >= 13, f'font shorthand below 13px: {size}px'

print('[PASS] v5.591 RAG Studio phase 4: Knowledge -> RAG Tool -> Prompt & Tool Studio -> Workflow -> Agent Test contracts')
