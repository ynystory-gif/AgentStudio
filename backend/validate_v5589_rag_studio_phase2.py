from __future__ import annotations

import re
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'backend'
FRONTEND = ROOT / 'frontend'
sys.path.insert(0, str(BACKEND))

APP = (FRONTEND / 'src/app/App.tsx').read_text(encoding='utf-8')
MAIN = (BACKEND / 'app/main.py').read_text(encoding='utf-8')
API_ROUTES = (BACKEND / 'app/api/routes.py').read_text(encoding='utf-8')
RAG_ROUTES = (BACKEND / 'app/api/rag_routes.py').read_text(encoding='utf-8')
MODELS = (BACKEND / 'app/models/rag_entities.py').read_text(encoding='utf-8')
INDEXING = (BACKEND / 'app/rag/indexing_service.py').read_text(encoding='utf-8')
RAG_UI = (FRONTEND / 'src/features/rag/components/RagStudio.tsx').read_text(encoding='utf-8')
RAG_CSS = (FRONTEND / 'src/features/rag/ragStudio.css').read_text(encoding='utf-8')
RAG_API = (FRONTEND / 'src/features/rag/ragApi.ts').read_text(encoding='utf-8')

assert "AGENTSTUDIO_FRONTEND_VERSION='5.589'" in APP
assert 'version="5.589"' in MAIN
assert '"version": "5.589"' in API_ROUTES
assert 'RagStudioPhase2Indexing' in API_ROUTES

# Phase-1 foundation must remain present.
for token in ('RagStudioSetting', 'RagCollection', 'RagSource', 'RagCollectionSource'):
    assert f'class {token}' in MODELS

# Phase-2 persistence tables. Every new DB table must keep the mandatory numeric ID.
for class_name in ('RagDocument', 'RagChunk', 'RagEmbedding', 'RagIndexJob'):
    match = re.search(rf'class {class_name}\(Base\):(?P<body>[\s\S]*?)(?=\nclass |\Z)', MODELS)
    assert match, class_name
    assert 'id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)' in match.group('body'), class_name

assert 'Vector(RAG_VECTOR_STORAGE_DIMENSION)' in MODELS
assert 'RAG_VECTOR_STORAGE_DIMENSION = 1536' in MODELS
assert '__tablename__ = "rag_documents"' in MODELS
assert '__tablename__ = "rag_chunks"' in MODELS
assert '__tablename__ = "rag_embeddings"' in MODELS
assert '__tablename__ = "rag_index_jobs"' in MODELS

# Backend Phase-2 endpoints and actual HNSW creation.
for route in ("@router.post('/chunk-preview')", "@router.post('/index')", "@router.get('/index/jobs')", "@router.get('/index/jobs/{job_id}')", "@router.get('/index/config')"):
    assert route in RAG_ROUTES, route
assert 'USING hnsw (embedding vector_cosine_ops)' in INDEXING
assert "stage='HNSW_INDEX'" in INDEXING
assert "status='COMPLETED'" in INDEXING
assert 'get_embedding_model()' in INDEXING
assert 'load_source_documents' in INDEXING
assert 'scan_knowledge_text' in INDEXING
assert 'chunk_document' in INDEXING
assert 'duplicates_skipped' in INDEXING

# Frontend: preview + Index Job + Embedding/HNSW state must be user-visible.
for token in ('Chunk Preview', 'Index 생성', 'Index Job 상태', 'Embedding', 'HNSW', '2차 · Indexing'):
    assert token in RAG_UI, token
for endpoint in ('/api/rag/chunk-preview', '/api/rag/index', '/api/rag/index/jobs', '/api/rag/index/config'):
    assert endpoint in RAG_API, endpoint
assert 'font-size:13px' in RAG_CSS
assert 'font:13px/1.55' in RAG_CSS

# Functional, DB-free checks for automatic type detection, Safety Scan and Chunking.
from app.rag.chunking import chunk_document, document_checksum
from app.rag.document_loader import detect_document_type, load_source_documents
from app.rag.safety_scan import scan_knowledge_text

with TemporaryDirectory() as td:
    root = Path(td)
    py_file = root / 'auth_service.py'
    py_file.write_text(
        'class AuthService:\n'
        '    def login(self, user):\n'
        '        password = "super-secret-password"\n'
        '        return user\n\n'
        'def helper(value):\n'
        '    return value * 2\n',
        encoding='utf-8',
    )
    md_file = root / 'guide.md'
    md_file.write_text('# 인증\nOAuth2를 사용합니다.\n\n## 오류\nERR-109를 확인합니다.\n', encoding='utf-8')
    sql_file = root / 'schema.sql'
    sql_file.write_text('CREATE TABLE users (id BIGSERIAL PRIMARY KEY, name TEXT);\nSELECT * FROM users;\n', encoding='utf-8')

    docs, skipped = load_source_documents(str(root), 'FOLDER', '.')
    assert not skipped, skipped
    by_name = {doc.filename: doc for doc in docs}
    assert by_name['auth_service.py'].document_type == 'SOURCE_CODE'
    assert by_name['guide.md'].document_type == 'MARKDOWN'
    assert by_name['schema.sql'].document_type == 'SQL'

    safety = scan_knowledge_text(py_file, by_name['auth_service.py'].text)
    assert safety.level == 'HIGH'
    assert safety.redaction_count >= 1
    assert '[RAG_REDACTED:' in safety.redacted_text

    py_chunks = chunk_document(safety.redacted_text, 'SOURCE_CODE', 'Python')
    md_chunks = chunk_document(by_name['guide.md'].text, 'MARKDOWN', 'Markdown')
    sql_chunks = chunk_document(by_name['schema.sql'].text, 'SQL', 'SQL')
    assert py_chunks and md_chunks and sql_chunks
    assert all(chunk.chunk_index == index for index, chunk in enumerate(py_chunks))
    assert any(chunk.heading for chunk in md_chunks)
    assert document_checksum(by_name['guide.md'].text)

print('[PASS] v5.589 RAG Studio phase 2: document detection + duplicate/safety pipeline + chunk preview + embedding/pgvector/HNSW job contracts')
