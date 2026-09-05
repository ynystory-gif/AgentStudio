from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = (ROOT / 'frontend/src/app/App.tsx').read_text(encoding='utf-8')
RAG_UI = (ROOT / 'frontend/src/features/rag/components/RagStudio.tsx').read_text(encoding='utf-8')
RAG_API = (ROOT / 'frontend/src/features/rag/ragApi.ts').read_text(encoding='utf-8')
RAG_CSS = (ROOT / 'frontend/src/features/rag/ragStudio.css').read_text(encoding='utf-8')
HELP_CSS = (ROOT / 'frontend/src/components/common/option-help.css').read_text(encoding='utf-8')
MODELS_PATH = ROOT / 'backend/app/models/rag_entities.py'
MODELS = MODELS_PATH.read_text(encoding='utf-8')
ROUTES = (ROOT / 'backend/app/api/rag_routes.py').read_text(encoding='utf-8')
SERVICE = (ROOT / 'backend/app/services/rag_studio_service.py').read_text(encoding='utf-8')
MAIN = (ROOT / 'backend/app/main.py').read_text(encoding='utf-8')
API_ROUTES = (ROOT / 'backend/app/api/routes.py').read_text(encoding='utf-8')
DATABASE_CORE = (ROOT / 'backend/app/core/database.py').read_text(encoding='utf-8')

assert "AGENTSTUDIO_FRONTEND_VERSION='5.588'" in APP
assert 'Prompt &amp; Tool Studio</button>' in APP and '>RAG Studio</button>' in APP
assert "designCenterTab==='RAG'&&<RagStudio" in APP
assert 'RAG Studio' in RAG_UI
assert 'Knowledge Collections' in RAG_UI
assert 'DB / Vector Store' in RAG_UI
assert 'Source 등록' in RAG_UI
assert 'Analyse' in RAG_UI and 'Review 완료' in RAG_UI and 'Approve' in RAG_UI
assert 'AI 적합성 분석 · 1차 규칙 기반' in RAG_UI
assert '/api/rag/collections' in RAG_API
assert '/api/rag/sources/analyze' in RAG_API
assert '/api/rag/sources/review' in RAG_API
assert '/api/rag/sources/approve' in RAG_API
assert '/api/rag/database/test' in RAG_API
assert 'font-size:13px' in RAG_CSS
assert 'font-size:13px' in HELP_CSS
assert "router = APIRouter(prefix='/rag'" in ROUTES
assert 'app.include_router(rag_router, prefix="/api")' in MAIN
assert 'version="5.588"' in MAIN
assert DATABASE_CORE.count('import app.models.rag_entities  # noqa: F401') >= 2
assert '"version": "5.588"' in API_ROUTES
assert "source_type not in {'FILE', 'FOLDER', 'SOURCE_CODE'}" in SERVICE
assert "row.status = 'REVIEW_REQUIRED'" in SERVICE
assert "row.status = 'REVIEWED'" in SERVICE
assert "row.status = 'APPROVED'" in SERVICE

# Project rule: every RAG table created now or later must have an explicit ID primary key.
tree = ast.parse(MODELS, filename=str(MODELS_PATH))
rag_classes = []
for node in tree.body:
    if not isinstance(node, ast.ClassDef):
        continue
    table_name = None
    field_names = set()
    for stmt in node.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name) and target.id == '__tablename__':
                    table_name = ast.literal_eval(stmt.value)
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            field_names.add(stmt.target.id)
    if table_name and str(table_name).startswith('rag_'):
        rag_classes.append((node.name, table_name, field_names))
assert rag_classes, 'RAG ORM tables not found'
for class_name, table_name, field_names in rag_classes:
    assert 'id' in field_names, f'{class_name} ({table_name}) must define id'

for marker in (
    'id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)',
    'class RagStudioSetting', 'class RagCollection', 'class RagSource', 'class RagCollectionSource',
):
    assert marker in MODELS

print('[PASS] v5.588 RAG Studio phase 1 contracts + mandatory table ID rule')
