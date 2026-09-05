from pathlib import Path
import ast
import re

ROOT = Path(__file__).resolve().parents[1]

def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding='utf-8')

app = read('frontend/src/app/App.tsx')
main = read('backend/app/main.py')
routes = read('backend/app/api/routes.py')
rag_routes = read('backend/app/api/rag_routes.py')
rag_api = read('frontend/src/features/rag/ragApi.ts')
rag_ui = read('frontend/src/features/rag/components/RagStudio.tsx')
rag_css = read('frontend/src/features/rag/ragStudio.css')
rag_service = read('backend/app/services/rag_studio_service.py')
models = read('backend/app/models/rag_entities.py')
database = read('backend/app/core/database.py')

assert "AGENTSTUDIO_FRONTEND_VERSION='5.598'" in app
assert 'version="5.598"' in main
assert '"version": "5.598"' in routes
assert 'RagStudioApiBaseSourcePickerDarkUiFix' in routes

# runtime-config API_BASE_URL already includes /api; RAG client must NOT add /api again.
system_admin = read('SYSTEM_ADMIN.ps1')
assert "API_BASE_URL: window.location.protocol + '//'+ window.location.hostname + ':{0}/api'" in system_admin
assert '/api/rag/' not in rag_api
assert "'/rag/state'" in rag_api
assert "'/rag/index/config'" in rag_api
assert "'/rag/retrieve'" in rag_api
assert '`/rag/operation/sources?' in rag_api
assert '`/rag/security/access-rules?' in rag_api
assert '`/rag/evaluation/runs?' in rag_api

# Corresponding Backend routes must exist under rag_router + /api include prefix.
for marker in [
    "@router.get('/state')",
    "@router.get('/index/config')",
    "@router.post('/retrieve')",
    "@router.get('/operation/sources')",
    "@router.get('/security/access-rules')",
    "@router.get('/evaluation/runs')",
]:
    assert marker in rag_routes, marker
assert "app.include_router(rag_router, prefix=\"/api\")" in main

# Native File / Folder picker + pasted Source Code flow.
assert 'class FilePickerRequest(BaseModel):' in routes
assert '@router.post("/system/pick-file")' in routes
assert 'pickRagSourceFile' in rag_api and "'/system/pick-file'" in rag_api
assert 'pickRagSourceFolder' in rag_api and "'/system/pick-folder'" in rag_api
assert "source_text: str = Field(default='', max_length=2_000_000)" in rag_routes
assert '_materialize_pasted_source_code' in rag_service
assert "'.agentstudio' / 'rag_sources' / 'pasted'" in rag_service
assert "sourceDraft.source_type==='SOURCE_CODE'" in rag_ui
assert 'rag-source-code-box' in rag_ui
assert '파일 찾기' in rag_ui and '폴더 찾기' in rag_ui

# Phase numbers were development history, not current completion state; remove them from product UI.
for text in ['Knowledge <span>2차</span>', 'Retrieval <span>5차</span>', 'Test <span>5차</span>', 'Operation <span>6차</span>', '<strong>2차 Indexing 기본 설정</strong>', '<strong>5차 · Intelligence</strong>', '<strong>4차 · Agent 연결</strong>']:
    assert text not in rag_ui, text
assert '>Knowledge</button>' in rag_ui and '>Retrieval</button>' in rag_ui and '>Operation</button>' in rag_ui
assert '운영형 RAG · Security / Evaluation' in rag_ui

# Tab changes clear stale global errors so Operation does not duplicate an old banner.
assert "const changeTab=(next:RagTab)=>{setError('');setNotice('');setTab(next)}" in rag_ui

# Dark Operation / Test controls override old light fallback styles.
assert 'v5.598 RAG Studio integration / source picker / dark operation polish' in rag_css
assert '.rag-operation-layout input,.rag-operation-layout select,.rag-operation-layout textarea' in rag_css
assert 'background:#08151e!important' in rag_css
assert '.rag-test-security-context input,.rag-test-security-context select' in rag_css
assert '.rag-source-code-box textarea' in rag_css
assert 'min-height:190px' in rag_css

# Preserve table-specific PK naming policy from v5.595-v5.597.
assert 'mapped_column("sources_id", Integer, primary_key=True, autoincrement=True)' in models
assert 'mapped_column("evaluation_cases_id", Integer, primary_key=True, autoincrement=True)' in models
assert '"rag_sources": "sources_id"' in database
assert 'prepare_rag_primary_key_compatibility_for_create_all' in database
assert not re.search(r'ForeignKey\("rag_[a-z0-9_]+\.id"\)', models)

for rel in [
    'backend/app/api/routes.py',
    'backend/app/api/rag_routes.py',
    'backend/app/services/rag_studio_service.py',
    'backend/app/main.py',
]:
    ast.parse(read(rel), filename=rel)

print('[PASS] v5.598 RAG API-base alignment + source picker/paste + phase-label cleanup + dark Operation UI contracts')
