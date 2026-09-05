from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
FRONTEND = ROOT / 'frontend'
sys.path.insert(0, str(BACKEND))

APP = (FRONTEND / 'src/app/App.tsx').read_text(encoding='utf-8')
MAIN = (BACKEND / 'app/main.py').read_text(encoding='utf-8')
API_ROUTES = (BACKEND / 'app/api/routes.py').read_text(encoding='utf-8')
RAG_ROUTES = (BACKEND / 'app/api/rag_routes.py').read_text(encoding='utf-8')
MODELS = (BACKEND / 'app/models/rag_entities.py').read_text(encoding='utf-8')
RETRIEVAL = (BACKEND / 'app/rag/retrieval_service.py').read_text(encoding='utf-8')
LOGIC = (BACKEND / 'app/rag/retrieval_logic.py').read_text(encoding='utf-8')
RAG_UI = (FRONTEND / 'src/features/rag/components/RagStudio.tsx').read_text(encoding='utf-8')
RAG_CSS = (FRONTEND / 'src/features/rag/ragStudio.css').read_text(encoding='utf-8')
RAG_API = (FRONTEND / 'src/features/rag/ragApi.ts').read_text(encoding='utf-8')
RAG_TYPES = (FRONTEND / 'src/features/rag/ragTypes.ts').read_text(encoding='utf-8')

assert "AGENTSTUDIO_FRONTEND_VERSION='5.590'" in APP
assert 'version="5.590"' in MAIN
assert '"version": "5.590"' in API_ROUTES
assert 'RagStudioPhase3Retrieval' in API_ROUTES

# Phase 1/2 persistence must remain, and phase 3 follows the mandatory auto-increment ID rule.
for class_name in (
    'RagStudioSetting', 'RagCollection', 'RagSource', 'RagCollectionSource',
    'RagDocument', 'RagChunk', 'RagEmbedding', 'RagIndexJob',
    'RagRetrievalSetting', 'RagSearchLog',
):
    match = re.search(rf'class {class_name}\(Base\):(?P<body>[\s\S]*?)(?=\nclass |\Z)', MODELS)
    assert match, class_name
    assert 'id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)' in match.group('body'), class_name

assert '__tablename__ = "rag_retrieval_settings"' in MODELS
assert '__tablename__ = "rag_search_logs"' in MODELS

# Required phase-3 endpoints.
for route in (
    "@router.get('/retrieval/settings')",
    "@router.put('/retrieval/settings')",
    "@router.get('/retrieval/options')",
    "@router.post('/retrieve')",
    "@router.get('/search-logs')",
):
    assert route in RAG_ROUTES, route

# Vector / Keyword / Hybrid engine contracts.
for token in (
    'cosine_distance(stored_vector)',
    'get_embedding_model().aembed_query(query)',
    'RagEmbedding.provider == provider',
    'RagEmbedding.model == model_name',
    'similarity < threshold',
    'RagChunk.content.icontains',
    'RagChunk.symbol_name.icontains',
    'RagDocument.path.icontains',
    'hybrid_fusion(vector_results, keyword_results, top_k)',
    'normalize_metadata_filter',
    'RagSearchLog(',
):
    assert token in RETRIEVAL, token

# Project/index state is always enforced before user metadata filters.
for token in (
    'RagSource.pc_name == pc_name',
    'RagSource.project_root == project_root',
    'RagSource.status == "INDEXED"',
    'RagSource.is_active.is_(True)',
    'RagSource.is_deleted.is_(False)',
    'RagDocument.status == "INDEXED"',
    'RagChunk.is_active.is_(True)',
):
    assert token in RETRIEVAL, token

# RRF / keyword scoring stays DB-neutral and unit-testable.
assert 'RRF_K = 60' in LOGIC
assert 'def keyword_score' in LOGIC
assert 'def hybrid_fusion' in LOGIC

# Frontend required UX: multiple search selection, settings, test, Retrieved Chunk, logs.
for token in (
    'Vector Search', 'Keyword Search', 'Hybrid Search', 'Top K', 'Similarity Threshold',
    'Metadata Filter · 기본형', 'Retrieval Test', 'Retrieved Chunk', '검색 로그',
    "type=\"checkbox\" checked={retrieval.search_mode!=='KEYWORD'}",
    "type=\"checkbox\" checked={retrieval.search_mode!=='VECTOR'}",
):
    assert token in RAG_UI, token
for endpoint in (
    '/api/rag/retrieval/settings', '/api/rag/retrieval/options', '/api/rag/retrieve', '/api/rag/search-logs',
):
    assert endpoint in RAG_API, endpoint
for type_name in ('RagRetrievalMetadataFilter', 'RagRetrievalSetting', 'RagRetrievalResult', 'RagSearchLog'):
    assert f'interface {type_name}' in RAG_TYPES, type_name

# RAG feature CSS must not reintroduce fixed text below the 13px readability floor.
for size in re.findall(r'font-size\s*:\s*(\d+(?:\.\d+)?)px', RAG_CSS):
    assert float(size) >= 13, f'font-size below 13px: {size}px'
for size in re.findall(r'font\s*:\s*(\d+(?:\.\d+)?)px', RAG_CSS):
    assert float(size) >= 13, f'font shorthand below 13px: {size}px'

# DB-free functional checks for exact-oriented scoring, filter normalization and RRF.
from app.rag.retrieval_logic import hybrid_fusion, keyword_score, keyword_tokens, normalize_metadata_filter

assert keyword_tokens('ERR-109 customer_id') == ['err-109', 'customer_id']
item = {
    'content': 'ERR-109 오류는 customer_id 검증에서 발생합니다.',
    'heading': '오류',
    'symbol_name': 'validate_customer',
    'document_path': 'backend/auth.py',
}
assert keyword_score(item, 'ERR-109', keyword_tokens('ERR-109')) > 0.5
vector = [
    {'chunk_id': 1, 'score': 0.91, 'vector_similarity': 0.91},
    {'chunk_id': 2, 'score': 0.82, 'vector_similarity': 0.82},
]
keyword = [
    {'chunk_id': 2, 'score': 0.95, 'keyword_score': 0.95},
    {'chunk_id': 3, 'score': 0.70, 'keyword_score': 0.70},
]
fused = hybrid_fusion(vector, keyword, 3)
assert fused[0]['chunk_id'] == 2, fused
assert fused[0]['vector_rank'] == 2 and fused[0]['keyword_rank'] == 1
filters = normalize_metadata_filter({
    'collection_ids': ['2', 2, 0, 'x'],
    'source_ids': [3, '3'],
    'document_types': ['MARKDOWN', '', 'MARKDOWN'],
    'languages': ['Python'],
    'path_contains': ' backend/auth ',
})
assert filters == {
    'collection_ids': [2],
    'source_ids': [3],
    'document_types': ['MARKDOWN'],
    'languages': ['Python'],
    'path_contains': 'backend/auth',
}

print('[PASS] v5.590 RAG Studio phase 3: Vector/Keyword/Hybrid + TopK/Threshold + Metadata Filter + Retrieval Test/Search Log contracts')
