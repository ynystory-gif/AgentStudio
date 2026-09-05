from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select, text

from app.core import database as database_core
from app.core.config import get_settings
from app.core.database import SessionLocal, quote_identifier
from app.core.machine_identity import current_pc_name
from app.models.rag_entities import (
    RAG_VECTOR_STORAGE_DIMENSION,
    RagChunk,
    RagDocument,
    RagEmbedding,
    RagIndexJob,
    RagSource,
)
from app.rag.chunking import DEFAULT_CHUNK_CHARS, DEFAULT_OVERLAP_CHARS, chunk_document, document_checksum
from app.rag.document_loader import LoadedDocument, load_source_documents
from app.rag.safety_scan import scan_knowledge_text
from app.services.embedding_service import get_embedding_model


HNSW_INDEX_NAME = 'ix_rag_embeddings_embedding_hnsw'
PREVIEW_MAX_DOCUMENTS = 20
PREVIEW_MAX_CHUNKS = 16
EMBEDDING_BATCH_SIZE = 32


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _embedding_identity() -> tuple[str, str]:
    settings = get_settings()
    provider = str(settings.memory_embedding_provider or 'ollama').lower()
    if not settings.openai_enabled:
        provider = 'ollama'
    if provider == 'openai':
        return provider, str(settings.openai_embedding_model or 'text-embedding-3-small')
    if provider == 'ollama':
        return provider, str(settings.ollama_embedding_model or 'nomic-embed-text')
    return provider, ''


def indexing_config() -> dict[str, Any]:
    provider, model = _embedding_identity()
    return {
        'embedding_provider': provider,
        'embedding_model': model,
        'storage_dimension': RAG_VECTOR_STORAGE_DIMENSION,
        'chunk_chars': DEFAULT_CHUNK_CHARS,
        'chunk_overlap_chars': DEFAULT_OVERLAP_CHARS,
        'hnsw_index_name': HNSW_INDEX_NAME,
        'hnsw_metric': 'cosine',
        'embedding_batch_size': EMBEDDING_BATCH_SIZE,
    }


def _serialize_job(row: RagIndexJob) -> dict[str, Any]:
    return {
        'id': row.id,
        'pc_name': row.pc_name,
        'project_root': row.project_root,
        'source_id': row.source_id,
        'status': row.status,
        'stage': row.stage,
        'progress': row.progress,
        'documents_total': row.documents_total,
        'documents_processed': row.documents_processed,
        'duplicates_skipped': row.duplicates_skipped,
        'safety_warnings': row.safety_warnings,
        'chunks_created': row.chunks_created,
        'embeddings_created': row.embeddings_created,
        'embedding_provider': row.embedding_provider,
        'embedding_model': row.embedding_model,
        'embedding_dimension': row.embedding_dimension,
        'index_name': row.index_name,
        'index_ready': row.index_ready,
        'error_message': row.error_message,
        'result_json': row.result_json or {},
        'started_at': _iso(row.started_at),
        'finished_at': _iso(row.finished_at),
        'created_at': _iso(row.created_at),
        'updated_at': _iso(row.updated_at),
    }


def _storage_vector(values: list[float]) -> tuple[list[float], int, str]:
    source_dimension = len(values)
    if source_dimension <= 0:
        raise ValueError('Embedding 모델이 빈 Vector를 반환했습니다.')
    if source_dimension == RAG_VECTOR_STORAGE_DIMENSION:
        return [float(value) for value in values], source_dimension, ''
    if source_dimension < RAG_VECTOR_STORAGE_DIMENSION:
        padded = [float(value) for value in values] + [0.0] * (RAG_VECTOR_STORAGE_DIMENSION - source_dimension)
        return padded, source_dimension, f'{source_dimension}차원 Embedding을 pgvector {RAG_VECTOR_STORAGE_DIMENSION}차원 저장 규격에 zero-padding 했습니다.'
    # Basic phase-2 guard. Do not silently truncate a higher-dimensional model because
    # doing so changes retrieval geometry. Users should choose a <=1536 model until a
    # per-model vector table strategy is introduced in a later phase.
    raise ValueError(
        f'현재 RAG HNSW 저장 규격은 {RAG_VECTOR_STORAGE_DIMENSION}차원까지 지원합니다. '
        f'선택한 Embedding은 {source_dimension}차원입니다. 1536차원 이하 모델을 사용하세요.'
    )


async def _set_job(job_id: int, **patch: Any) -> dict[str, Any]:
    async with SessionLocal() as session:
        row = (await session.execute(select(RagIndexJob).where(RagIndexJob.id == job_id))).scalar_one_or_none()
        if row is None:
            raise LookupError('RAG Index Job을 찾을 수 없습니다.')
        for key, value in patch.items():
            if hasattr(row, key):
                setattr(row, key, value)
        row.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(row)
        return _serialize_job(row)


async def create_index_job(source_id: int) -> dict[str, Any]:
    pc_name = current_pc_name()
    provider, model = _embedding_identity()
    async with SessionLocal() as session:
        source = (await session.execute(select(RagSource).where(
            RagSource.id == source_id,
            RagSource.pc_name == pc_name,
            RagSource.is_deleted.is_(False),
        ))).scalar_one_or_none()
        if source is None:
            raise LookupError('RAG Source를 찾을 수 없습니다.')
        if source.status not in {'APPROVED', 'INDEXED'}:
            raise ValueError('Analyse → Review → Approve 완료한 Source만 Indexing할 수 있습니다.')
        active = (await session.execute(select(RagIndexJob).where(
            RagIndexJob.source_id == source.id,
            RagIndexJob.status.in_(['PENDING', 'RUNNING']),
        ).order_by(RagIndexJob.id.desc()))).scalars().first()
        if active is not None:
            result = _serialize_job(active)
            result['should_start'] = False
            return result
        job = RagIndexJob(
            pc_name=pc_name,
            project_root=source.project_root,
            source_id=source.id,
            status='PENDING',
            stage='QUEUED',
            progress=0,
            embedding_provider=provider,
            embedding_model=model,
            index_name=HNSW_INDEX_NAME,
        )
        session.add(job)
        await session.commit()
        await session.refresh(job)
        result = _serialize_job(job)
        result['should_start'] = True
        return result


async def get_index_job(job_id: int) -> dict[str, Any]:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        row = (await session.execute(select(RagIndexJob).where(
            RagIndexJob.id == job_id,
            RagIndexJob.pc_name == pc_name,
        ))).scalar_one_or_none()
        if row is None:
            raise LookupError('RAG Index Job을 찾을 수 없습니다.')
        return _serialize_job(row)


async def list_index_jobs(project_root: str = '', limit: int = 30) -> list[dict[str, Any]]:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        stmt = select(RagIndexJob).where(RagIndexJob.pc_name == pc_name)
        if str(project_root or '').strip():
            stmt = stmt.where(RagIndexJob.project_root == str(project_root).strip())
        rows = (await session.execute(stmt.order_by(RagIndexJob.id.desc()).limit(max(1, min(int(limit), 100))))).scalars().all()
        return [_serialize_job(row) for row in rows]


async def _find_duplicate(session, *, project_root: str, checksum: str, source_id: int, path: str, current_document_id: int | None) -> RagDocument | None:
    stmt = select(RagDocument).where(
        RagDocument.project_root == project_root,
        RagDocument.checksum == checksum,
        RagDocument.is_deleted.is_(False),
        RagDocument.is_active.is_(True),
        RagDocument.status == 'INDEXED',
    )
    if current_document_id is not None:
        stmt = stmt.where(RagDocument.id != current_document_id)
    # Same source/path is the current logical document and must not classify itself as duplicate.
    stmt = stmt.where(~((RagDocument.source_id == source_id) & (RagDocument.path == path)))
    return (await session.execute(stmt.order_by(RagDocument.id.asc()))).scalars().first()


async def _clear_document_index(session, document_id: int) -> None:
    chunk_ids = (await session.execute(select(RagChunk.id).where(RagChunk.document_id == document_id))).scalars().all()
    if chunk_ids:
        await session.execute(delete(RagEmbedding).where(RagEmbedding.chunk_id.in_(list(chunk_ids))))
    await session.execute(delete(RagChunk).where(RagChunk.document_id == document_id))


async def _upsert_document(
    session,
    *,
    source: RagSource,
    document: LoadedDocument,
    checksum: str,
    safety_level: str,
    safety_result: dict[str, Any],
) -> RagDocument:
    row = (await session.execute(select(RagDocument).where(
        RagDocument.source_id == source.id,
        RagDocument.path == document.display_path,
    ))).scalar_one_or_none()
    if row is None:
        row = RagDocument(
            pc_name=source.pc_name,
            project_root=source.project_root,
            source_id=source.id,
            path=document.display_path,
            filename=document.filename,
        )
        session.add(row)
        await session.flush()
    row.filename = document.filename
    row.document_type = document.document_type
    row.language = document.language
    row.checksum = checksum
    row.size_bytes = document.size_bytes
    row.safety_level = safety_level
    row.safety_result = safety_result
    row.is_active = True
    row.is_deleted = False
    row.updated_at = datetime.utcnow()
    return row


async def _embed_texts(texts: list[str]) -> tuple[list[list[float]], int, list[str]]:
    model = get_embedding_model()
    all_vectors: list[list[float]] = []
    source_dimension = 0
    notes: list[str] = []
    for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[start:start + EMBEDDING_BATCH_SIZE]
        vectors = await model.aembed_documents(batch)
        if len(vectors) != len(batch):
            raise RuntimeError('Embedding 응답 개수와 Chunk 개수가 일치하지 않습니다.')
        for vector in vectors:
            stored, dim, note = _storage_vector(list(vector))
            source_dimension = source_dimension or dim
            if source_dimension != dim:
                raise RuntimeError(f'한 Index Job 안에서 Embedding 차원이 변경되었습니다: {source_dimension} → {dim}')
            if note and note not in notes:
                notes.append(note)
            all_vectors.append(stored)
    return all_vectors, source_dimension, notes


async def _ensure_hnsw_index() -> tuple[bool, str, str]:
    """Create and verify the default cosine HNSW index on the active runtime DB."""
    async with database_core.engine.begin() as conn:
        schema = str((await conn.execute(text('SELECT current_schema()'))).scalar() or 'public')
        qschema = quote_identifier(schema)
        qindex = '"' + HNSW_INDEX_NAME.replace('"', '""') + '"'
        await conn.execute(text(
            f'CREATE INDEX IF NOT EXISTS {qindex} '
            f'ON {qschema}."rag_embeddings" USING hnsw (embedding vector_cosine_ops) '
            f'WITH (m = 16, ef_construction = 64)'
        ))
        exists = bool((await conn.execute(text(
            'SELECT EXISTS ('
            'SELECT 1 FROM pg_indexes WHERE schemaname=:schema AND indexname=:index_name'
            ')'
        ), {'schema': schema, 'index_name': HNSW_INDEX_NAME})).scalar())
    return exists, schema, HNSW_INDEX_NAME


async def run_index_job(job_id: int) -> None:
    provider, model_name = _embedding_identity()
    notes: list[str] = []
    skipped_files: list[dict[str, Any]] = []
    try:
        await _set_job(job_id, status='RUNNING', stage='DOCUMENT_SCAN', progress=3, started_at=datetime.utcnow(), error_message='')
        async with SessionLocal() as session:
            job = (await session.execute(select(RagIndexJob).where(RagIndexJob.id == job_id))).scalar_one()
            source = (await session.execute(select(RagSource).where(RagSource.id == job.source_id))).scalar_one()
            source_snapshot = {
                'id': source.id,
                'pc_name': source.pc_name,
                'project_root': source.project_root,
                'source_type': source.source_type,
                'source_uri': source.source_uri,
            }

        documents, skipped_files = await asyncio.to_thread(
            load_source_documents,
            source_snapshot['project_root'],
            source_snapshot['source_type'],
            source_snapshot['source_uri'],
        )
        if not documents:
            reason = skipped_files[0]['reason'] if skipped_files else '지원되는 문서가 없습니다.'
            raise ValueError(f'Indexing할 문서를 찾지 못했습니다. {reason}')

        total = len(documents)
        await _set_job(job_id, stage='DUPLICATE_SAFETY_CHUNK', progress=8, documents_total=total)

        processed = 0
        duplicate_count = 0
        warning_count = 0
        total_chunks = 0
        total_embeddings = 0
        embedding_dimension = 0
        document_results: list[dict[str, Any]] = []

        for document in documents:
            safety = scan_knowledge_text(document.path, document.text)
            checksum = document_checksum(document.text)
            warning_count += len(safety.warnings)
            chunks = [] if safety.quarantined else chunk_document(safety.redacted_text, document.document_type, document.language)
            if not chunks:
                document_results.append({'path': document.display_path, 'status': 'SKIPPED_EMPTY_CHUNK'})
                processed += 1
                continue

            async with SessionLocal() as session:
                source = (await session.execute(select(RagSource).where(RagSource.id == source_snapshot['id']))).scalar_one()
                existing = (await session.execute(select(RagDocument).where(
                    RagDocument.source_id == source.id,
                    RagDocument.path == document.display_path,
                ))).scalar_one_or_none()
                duplicate = await _find_duplicate(
                    session,
                    project_root=source.project_root,
                    checksum=checksum,
                    source_id=source.id,
                    path=document.display_path,
                    current_document_id=existing.id if existing else None,
                )
                row = await _upsert_document(
                    session,
                    source=source,
                    document=document,
                    checksum=checksum,
                    safety_level=safety.level,
                    safety_result={
                        'warnings': safety.warnings,
                        'redaction_count': safety.redaction_count,
                        'prompt_injection_count': safety.prompt_injection_count,
                        'instruction_like_count': safety.instruction_like_count,
                        'exfiltration_count': safety.exfiltration_count,
                        'risk_score': safety.risk_score,
                        'risk_categories': safety.risk_categories,
                        'quarantined': safety.quarantined,
                    },
                )
                await _clear_document_index(session, row.id)
                if safety.quarantined:
                    row.status = 'SECURITY_QUARANTINED'
                    row.is_active = False
                    row.duplicate_of_document_id = None
                    row.chunk_count = 0
                    await session.commit()
                    processed += 1
                    document_results.append({
                        'document_id': row.id,
                        'path': document.display_path,
                        'document_type': document.document_type,
                        'status': row.status,
                        'safety_level': safety.level,
                        'risk_score': safety.risk_score,
                        'warnings': safety.warnings,
                    })
                    await _set_job(
                        job_id,
                        stage='DUPLICATE_SAFETY_CHUNK',
                        progress=min(82, 8 + int(72 * processed / total)),
                        documents_processed=processed,
                        duplicates_skipped=duplicate_count,
                        safety_warnings=warning_count,
                        chunks_created=total_chunks,
                        embeddings_created=total_embeddings,
                    )
                    continue
                if duplicate is not None:
                    row.status = 'DUPLICATE_SKIPPED'
                    row.duplicate_of_document_id = duplicate.id
                    row.chunk_count = 0
                    await session.commit()
                    duplicate_count += 1
                    processed += 1
                    document_results.append({
                        'document_id': row.id,
                        'path': document.display_path,
                        'document_type': document.document_type,
                        'status': row.status,
                        'duplicate_of_document_id': duplicate.id,
                        'safety_level': safety.level,
                        'warnings': safety.warnings,
                    })
                    await _set_job(
                        job_id,
                        stage='DUPLICATE_SAFETY_CHUNK',
                        progress=min(82, 8 + int(72 * processed / total)),
                        documents_processed=processed,
                        duplicates_skipped=duplicate_count,
                        safety_warnings=warning_count,
                        chunks_created=total_chunks,
                        embeddings_created=total_embeddings,
                    )
                    continue

                row.duplicate_of_document_id = None
                row.status = 'CHUNKED'
                chunk_rows: list[RagChunk] = []
                for chunk in chunks:
                    chunk_row = RagChunk(
                        document_id=row.id,
                        source_id=source.id,
                        chunk_index=chunk.chunk_index,
                        content=chunk.content,
                        content_hash=chunk.content_hash,
                        char_count=len(chunk.content),
                        token_estimate=chunk.token_estimate,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        heading=chunk.heading,
                        symbol_name=chunk.symbol_name,
                        metadata_json={**chunk.metadata, 'document_type': document.document_type, 'language': document.language, 'path': document.display_path},
                    )
                    session.add(chunk_row)
                    chunk_rows.append(chunk_row)
                await session.flush()
                row.chunk_count = len(chunk_rows)
                row.status = 'EMBEDDING'
                await session.commit()
                chunk_ids = [chunk_row.id for chunk_row in chunk_rows]

            vectors, dim, resize_notes = await _embed_texts([chunk.content for chunk in chunks])
            embedding_dimension = embedding_dimension or dim
            for note in resize_notes:
                if note not in notes:
                    notes.append(note)

            async with SessionLocal() as session:
                for chunk_id, vector in zip(chunk_ids, vectors, strict=True):
                    session.add(RagEmbedding(
                        chunk_id=chunk_id,
                        provider=provider,
                        model=model_name,
                        source_dimension=dim,
                        storage_dimension=RAG_VECTOR_STORAGE_DIMENSION,
                        embedding=vector,
                    ))
                row = (await session.execute(select(RagDocument).where(
                    RagDocument.source_id == source_snapshot['id'],
                    RagDocument.path == document.display_path,
                ))).scalar_one()
                row.status = 'INDEXED'
                row.updated_at = datetime.utcnow()
                await session.commit()

            processed += 1
            total_chunks += len(chunks)
            total_embeddings += len(vectors)
            document_results.append({
                'path': document.display_path,
                'document_type': document.document_type,
                'language': document.language,
                'status': 'INDEXED',
                'chunk_count': len(chunks),
                'safety_level': safety.level,
                'warnings': safety.warnings,
            })
            await _set_job(
                job_id,
                stage='CHUNK_EMBEDDING',
                progress=min(84, 10 + int(74 * processed / total)),
                documents_processed=processed,
                duplicates_skipped=duplicate_count,
                safety_warnings=warning_count,
                chunks_created=total_chunks,
                embeddings_created=total_embeddings,
                embedding_dimension=embedding_dimension,
            )

        if total_embeddings <= 0:
            raise ValueError('Embedding 가능한 Chunk가 생성되지 않았습니다. Duplicate/문서 추출 결과를 확인하세요.')

        await _set_job(job_id, stage='HNSW_INDEX', progress=90)
        index_ready, schema, index_name = await _ensure_hnsw_index()
        if not index_ready:
            raise RuntimeError('pgvector HNSW Index 생성 후 존재 여부를 확인하지 못했습니다.')

        async with SessionLocal() as session:
            source = (await session.execute(select(RagSource).where(RagSource.id == source_snapshot['id']))).scalar_one()
            source.status = 'INDEXED'
            source.updated_at = datetime.utcnow()
            await session.commit()

        await _set_job(
            job_id,
            status='COMPLETED',
            stage='COMPLETED',
            progress=100,
            documents_processed=processed,
            duplicates_skipped=duplicate_count,
            safety_warnings=warning_count,
            chunks_created=total_chunks,
            embeddings_created=total_embeddings,
            embedding_provider=provider,
            embedding_model=model_name,
            embedding_dimension=embedding_dimension,
            index_name=index_name,
            index_ready=True,
            result_json={
                'schema': schema,
                'documents': document_results,
                'skipped_files': skipped_files,
                'notes': notes,
                'storage_dimension': RAG_VECTOR_STORAGE_DIMENSION,
                'hnsw_metric': 'cosine',
            },
            finished_at=datetime.utcnow(),
        )
    except Exception as exc:
        try:
            await _set_job(
                job_id,
                status='FAILED',
                stage='FAILED',
                error_message=str(exc),
                result_json={'skipped_files': skipped_files, 'notes': notes},
                finished_at=datetime.utcnow(),
            )
        except Exception:
            pass


async def preview_source_chunks(source_id: int, limit: int = PREVIEW_MAX_CHUNKS) -> dict[str, Any]:
    pc_name = current_pc_name()
    limit = max(1, min(int(limit), 50))
    async with SessionLocal() as session:
        source = (await session.execute(select(RagSource).where(
            RagSource.id == source_id,
            RagSource.pc_name == pc_name,
            RagSource.is_deleted.is_(False),
        ))).scalar_one_or_none()
        if source is None:
            raise LookupError('RAG Source를 찾을 수 없습니다.')
        if source.status not in {'APPROVED', 'INDEXED'}:
            raise ValueError('Chunk Preview는 Analyse → Review → Approve 완료 후 실행할 수 있습니다.')
        snapshot = {
            'id': source.id,
            'project_root': source.project_root,
            'source_type': source.source_type,
            'source_uri': source.source_uri,
        }

    documents, skipped = await asyncio.to_thread(
        load_source_documents,
        snapshot['project_root'], snapshot['source_type'], snapshot['source_uri'],
    )
    preview_documents: list[dict[str, Any]] = []
    preview_chunks: list[dict[str, Any]] = []
    total_chunk_count = 0
    duplicate_count = 0
    safety_warning_count = 0

    for document in documents[:PREVIEW_MAX_DOCUMENTS]:
        safety = scan_knowledge_text(document.path, document.text)
        checksum = document_checksum(document.text)
        chunks = [] if safety.quarantined else chunk_document(safety.redacted_text, document.document_type, document.language)
        total_chunk_count += len(chunks)
        safety_warning_count += len(safety.warnings)
        async with SessionLocal() as session:
            existing = (await session.execute(select(RagDocument).where(
                RagDocument.source_id == snapshot['id'],
                RagDocument.path == document.display_path,
            ))).scalar_one_or_none()
            duplicate = await _find_duplicate(
                session,
                project_root=snapshot['project_root'],
                checksum=checksum,
                source_id=snapshot['id'],
                path=document.display_path,
                current_document_id=existing.id if existing else None,
            )
        if duplicate is not None:
            duplicate_count += 1
        preview_documents.append({
            'path': document.display_path,
            'filename': document.filename,
            'document_type': document.document_type,
            'language': document.language,
            'size_bytes': document.size_bytes,
            'checksum': checksum,
            'chunk_count': len(chunks),
            'safety_level': safety.level,
            'safety_warnings': safety.warnings,
            'redaction_count': safety.redaction_count,
            'prompt_injection_count': safety.prompt_injection_count,
            'instruction_like_count': safety.instruction_like_count,
            'exfiltration_count': safety.exfiltration_count,
            'risk_score': safety.risk_score,
            'risk_categories': safety.risk_categories,
            'quarantined': safety.quarantined,
            'is_duplicate': duplicate is not None,
            'duplicate_of_document_id': duplicate.id if duplicate else None,
        })
        if duplicate is None:
            for chunk in chunks:
                if len(preview_chunks) >= limit:
                    break
                preview_chunks.append({
                    'document_path': document.display_path,
                    'document_type': document.document_type,
                    'language': document.language,
                    'chunk_index': chunk.chunk_index,
                    'content': chunk.content,
                    'char_count': len(chunk.content),
                    'token_estimate': chunk.token_estimate,
                    'start_line': chunk.start_line,
                    'end_line': chunk.end_line,
                    'heading': chunk.heading,
                    'symbol_name': chunk.symbol_name,
                    'metadata': chunk.metadata,
                })
        if len(preview_chunks) >= limit:
            # Continue document summaries only until preview document cap, but no more chunk bodies.
            continue

    return {
        'source_id': source_id,
        'documents_total': len(documents),
        'documents_previewed': min(len(documents), PREVIEW_MAX_DOCUMENTS),
        'document_preview_truncated': len(documents) > PREVIEW_MAX_DOCUMENTS,
        'duplicate_count': duplicate_count,
        'safety_warning_count': safety_warning_count,
        'total_chunk_count': total_chunk_count,
        'chunks': preview_chunks,
        'documents': preview_documents,
        'skipped_files': skipped,
        'config': indexing_config(),
    }
