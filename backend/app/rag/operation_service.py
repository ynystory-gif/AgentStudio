from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from sqlalchemy import func, select, update

from app.core.database import SessionLocal
from app.core.machine_identity import current_pc_name
from app.models.rag_entities import (
    RAG_VECTOR_STORAGE_DIMENSION,
    RagChunk,
    RagDocument,
    RagDocumentSecurity,
    RagDocumentVersion,
    RagEmbedding,
    RagSource,
    RagSourceOperationSetting,
    RagSyncJob,
)
from app.rag.chunking import chunk_document, document_checksum
from app.rag.document_loader import LoadedDocument, load_source_documents
from app.rag.indexing_service import (
    HNSW_INDEX_NAME,
    _clear_document_index,
    _embed_texts,
    _ensure_hnsw_index,
    _find_duplicate,
    _upsert_document,
    _embedding_identity,
)
from app.rag.safety_scan import scan_knowledge_text

_SYNC_MODES = {"MANUAL", "ON_PROJECT_OPEN", "DAILY", "CHANGE_DETECT"}


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _serialize_sync_job(row: RagSyncJob) -> dict[str, Any]:
    return {
        "id": row.id,
        "pc_name": row.pc_name,
        "project_root": row.project_root,
        "source_id": row.source_id,
        "status": row.status,
        "stage": row.stage,
        "progress": row.progress,
        "added_count": row.added_count,
        "changed_count": row.changed_count,
        "removed_count": row.removed_count,
        "unchanged_count": row.unchanged_count,
        "chunks_updated": row.chunks_updated,
        "embeddings_updated": row.embeddings_updated,
        "error_message": row.error_message,
        "result_json": row.result_json or {},
        "started_at": _iso(row.started_at),
        "finished_at": _iso(row.finished_at),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


async def _source_setting(session, source_id: int) -> RagSourceOperationSetting:
    row = (await session.execute(select(RagSourceOperationSetting).where(
        RagSourceOperationSetting.source_id == source_id,
    ))).scalar_one_or_none()
    if row is None:
        row = RagSourceOperationSetting(source_id=source_id, sync_mode="MANUAL")
        session.add(row)
        await session.flush()
    return row


async def set_source_sync_mode(source_id: int, sync_mode: str) -> dict[str, Any]:
    pc_name = current_pc_name()
    mode = str(sync_mode or "MANUAL").upper()
    if mode not in _SYNC_MODES:
        raise ValueError("지원 Sync Mode: MANUAL / ON_PROJECT_OPEN / DAILY / CHANGE_DETECT")
    async with SessionLocal() as session:
        source = await session.get(RagSource, int(source_id))
        if source is None or source.pc_name != pc_name or source.is_deleted:
            raise LookupError("RAG Source를 찾을 수 없습니다.")
        row = await _source_setting(session, source.id)
        row.sync_mode = mode
        row.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(row)
        return {
            "id": row.id,
            "project_root": source.project_root,
            "source_id": row.source_id,
            "sync_mode": row.sync_mode,
            "last_checked_at": _iso(row.last_checked_at),
            "last_synced_at": _iso(row.last_synced_at),
            "last_change_count": row.last_change_count,
        }


async def _load_source_snapshot(source_id: int) -> dict[str, Any]:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        source = await session.get(RagSource, int(source_id))
        if source is None or source.pc_name != pc_name or source.is_deleted:
            raise LookupError("RAG Source를 찾을 수 없습니다.")
        return {
            "id": source.id,
            "pc_name": source.pc_name,
            "project_root": source.project_root,
            "source_type": source.source_type,
            "source_uri": source.source_uri,
            "display_name": source.display_name,
        }


async def detect_source_changes(source_id: int) -> dict[str, Any]:
    snapshot = await _load_source_snapshot(source_id)
    documents, skipped = await asyncio.to_thread(
        load_source_documents,
        snapshot["project_root"],
        snapshot["source_type"],
        snapshot["source_uri"],
    )
    incoming = {doc.display_path: (doc, document_checksum(doc.text)) for doc in documents}
    async with SessionLocal() as session:
        rows = (await session.execute(select(RagDocument).where(
            RagDocument.source_id == source_id,
            RagDocument.is_deleted.is_(False),
        ))).scalars().all()
        existing = {row.path: row for row in rows}
        added = []
        changed = []
        unchanged = []
        removed = []
        for path, (document, checksum) in incoming.items():
            row = existing.get(path)
            item = {"path": path, "filename": document.filename, "document_type": document.document_type, "checksum": checksum}
            if row is None:
                added.append(item)
            elif row.checksum != checksum or row.status not in {"INDEXED", "DUPLICATE_SKIPPED"}:
                changed.append({**item, "document_id": row.id, "previous_checksum": row.checksum, "previous_status": row.status})
            else:
                unchanged.append({**item, "document_id": row.id})
        for path, row in existing.items():
            if path not in incoming and row.is_active:
                removed.append({"path": path, "document_id": row.id, "checksum": row.checksum})
        setting = await _source_setting(session, source_id)
        setting.last_checked_at = datetime.utcnow()
        setting.last_change_count = len(added) + len(changed) + len(removed)
        await session.commit()
    return {
        "source_id": source_id,
        "source_name": snapshot["display_name"] or snapshot["source_uri"],
        "added": added,
        "changed": changed,
        "removed": removed,
        "unchanged": unchanged,
        "change_count": len(added) + len(changed) + len(removed),
        "skipped_files": skipped,
        "checked_at": datetime.utcnow().isoformat(),
    }


async def create_sync_job(source_id: int) -> dict[str, Any]:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        source = await session.get(RagSource, int(source_id))
        if source is None or source.pc_name != pc_name or source.is_deleted:
            raise LookupError("RAG Source를 찾을 수 없습니다.")
        if source.status not in {"APPROVED", "INDEXED"}:
            raise ValueError("승인된 Source만 Sync / 증분 Re-index할 수 있습니다.")
        active = (await session.execute(select(RagSyncJob).where(
            RagSyncJob.source_id == source.id,
            RagSyncJob.status.in_(["PENDING", "RUNNING"]),
        ).order_by(RagSyncJob.id.desc()))).scalars().first()
        if active is not None:
            result = _serialize_sync_job(active)
            result["should_start"] = False
            return result
        row = RagSyncJob(
            pc_name=pc_name,
            project_root=source.project_root,
            source_id=source.id,
            status="PENDING",
            stage="QUEUED",
            progress=0,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        result = _serialize_sync_job(row)
        result["should_start"] = True
        return result


async def _set_sync_job(job_id: int, **patch: Any) -> None:
    async with SessionLocal() as session:
        row = await session.get(RagSyncJob, int(job_id))
        if row is None:
            return
        for key, value in patch.items():
            if hasattr(row, key):
                setattr(row, key, value)
        row.updated_at = datetime.utcnow()
        await session.commit()


async def _snapshot_document(session, document: RagDocument, *, created_by: str = "SYNC", force: bool = False) -> RagDocumentVersion | None:
    chunks = (await session.execute(select(RagChunk).where(
        RagChunk.document_id == document.id,
        RagChunk.is_active.is_(True),
    ).order_by(RagChunk.chunk_index.asc()))).scalars().all()
    if not chunks and not force:
        return None
    current = (await session.execute(select(RagDocumentVersion).where(
        RagDocumentVersion.document_id == document.id,
        RagDocumentVersion.is_current.is_(True),
    ).order_by(RagDocumentVersion.version_no.desc()))).scalars().first()
    if current is not None and current.checksum == document.checksum and not force:
        return current
    max_version = (await session.execute(select(func.max(RagDocumentVersion.version_no)).where(
        RagDocumentVersion.document_id == document.id,
    ))).scalar() or 0
    await session.execute(update(RagDocumentVersion).where(
        RagDocumentVersion.document_id == document.id,
        RagDocumentVersion.is_current.is_(True),
    ).values(is_current=False))
    snapshot = [{
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "content_hash": chunk.content_hash,
        "char_count": chunk.char_count,
        "token_estimate": chunk.token_estimate,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "heading": chunk.heading,
        "symbol_name": chunk.symbol_name,
        "metadata_json": chunk.metadata_json or {},
    } for chunk in chunks]
    row = RagDocumentVersion(
        document_id=document.id,
        version_no=int(max_version) + 1,
        checksum=document.checksum,
        document_type=document.document_type,
        language=document.language,
        safety_level=document.safety_level,
        safety_result=document.safety_result or {},
        chunk_snapshot=snapshot,
        source_revision=document.checksum[:16],
        is_current=True,
        created_by=created_by,
    )
    session.add(row)
    await session.flush()
    return row


async def _index_loaded_document(session, source: RagSource, document: LoadedDocument, *, created_by: str) -> tuple[int, int, str, list[str]]:
    safety = scan_knowledge_text(document.path, document.text)
    checksum = document_checksum(document.text)
    existing = (await session.execute(select(RagDocument).where(
        RagDocument.source_id == source.id,
        RagDocument.path == document.display_path,
    ))).scalar_one_or_none()
    if existing is not None and existing.status == "INDEXED" and existing.chunk_count:
        await _snapshot_document(session, existing, created_by=f"{created_by}_PREVIOUS")
    row = await _upsert_document(
        session,
        source=source,
        document=document,
        checksum=checksum,
        safety_level=safety.level,
        safety_result={
            "warnings": safety.warnings,
            "redaction_count": safety.redaction_count,
            "prompt_injection_count": safety.prompt_injection_count,
            "instruction_like_count": getattr(safety, "instruction_like_count", 0),
            "exfiltration_count": getattr(safety, "exfiltration_count", 0),
            "risk_score": getattr(safety, "risk_score", 0),
            "risk_categories": getattr(safety, "risk_categories", []),
            "quarantined": getattr(safety, "quarantined", False),
        },
    )
    await _clear_document_index(session, row.id)
    if getattr(safety, "quarantined", False):
        row.status = "SECURITY_QUARANTINED"
        row.chunk_count = 0
        row.is_active = False
        await session.flush()
        return 0, 0, "SECURITY_QUARANTINED", list(safety.warnings)

    duplicate = await _find_duplicate(
        session,
        project_root=source.project_root,
        checksum=checksum,
        source_id=source.id,
        path=document.display_path,
        current_document_id=row.id,
    )
    if duplicate is not None:
        row.status = "DUPLICATE_SKIPPED"
        row.duplicate_of_document_id = duplicate.id
        row.chunk_count = 0
        await session.flush()
        return 0, 0, "DUPLICATE_SKIPPED", list(safety.warnings)

    chunks = chunk_document(safety.redacted_text, document.document_type, document.language)
    if not chunks:
        row.status = "EMPTY"
        row.chunk_count = 0
        await session.flush()
        return 0, 0, "EMPTY", list(safety.warnings)
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
            metadata_json={**chunk.metadata, "document_type": document.document_type, "language": document.language, "path": document.display_path},
        )
        session.add(chunk_row)
        chunk_rows.append(chunk_row)
    await session.flush()
    vectors, dimension, _ = await _embed_texts([chunk.content for chunk in chunks])
    provider, model = _embedding_identity()
    for chunk_row, vector in zip(chunk_rows, vectors, strict=True):
        session.add(RagEmbedding(
            chunk_id=chunk_row.id,
            provider=provider,
            model=model,
            source_dimension=dimension,
            storage_dimension=RAG_VECTOR_STORAGE_DIMENSION,
            embedding=vector,
        ))
    row.chunk_count = len(chunk_rows)
    row.status = "INDEXED"
    row.is_active = True
    row.duplicate_of_document_id = None
    row.updated_at = datetime.utcnow()
    await session.flush()
    await _snapshot_document(session, row, created_by=created_by, force=True)
    return len(chunk_rows), len(vectors), "INDEXED", list(safety.warnings)


async def run_sync_job(job_id: int) -> None:
    try:
        await _set_sync_job(job_id, status="RUNNING", stage="CHANGE_DETECT", progress=5, started_at=datetime.utcnow(), error_message="")
        async with SessionLocal() as session:
            job = await session.get(RagSyncJob, int(job_id))
            if job is None:
                raise LookupError("RAG Sync Job을 찾을 수 없습니다.")
            source = await session.get(RagSource, job.source_id)
            if source is None:
                raise LookupError("RAG Source를 찾을 수 없습니다.")
            source_id = source.id
        changes = await detect_source_changes(source_id)
        total_changes = int(changes["change_count"])
        await _set_sync_job(
            job_id,
            stage="INCREMENTAL_REINDEX",
            progress=15,
            added_count=len(changes["added"]),
            changed_count=len(changes["changed"]),
            removed_count=len(changes["removed"]),
            unchanged_count=len(changes["unchanged"]),
        )
        if total_changes == 0:
            async with SessionLocal() as session:
                setting = await _source_setting(session, source_id)
                setting.last_synced_at = datetime.utcnow()
                await session.commit()
            await _set_sync_job(job_id, status="COMPLETED", stage="NO_CHANGES", progress=100, result_json=changes, finished_at=datetime.utcnow())
            return

        snapshot = await _load_source_snapshot(source_id)
        loaded, skipped = await asyncio.to_thread(load_source_documents, snapshot["project_root"], snapshot["source_type"], snapshot["source_uri"])
        loaded_map = {item.display_path: item for item in loaded}
        target_paths = [item["path"] for item in changes["added"] + changes["changed"]]
        processed = 0
        chunk_count = 0
        embedding_count = 0
        results: list[dict[str, Any]] = []

        async with SessionLocal() as session:
            source = await session.get(RagSource, source_id)
            if source is None:
                raise LookupError("RAG Source를 찾을 수 없습니다.")
            for removed in changes["removed"]:
                document = await session.get(RagDocument, int(removed["document_id"]))
                if document is not None:
                    await _snapshot_document(session, document, created_by="SYNC_REMOVED")
                    document.is_active = False
                    document.status = "DISABLED"
                    document.updated_at = datetime.utcnow()
                processed += 1
            await session.commit()

        for path in target_paths:
            document = loaded_map.get(path)
            if document is None:
                continue
            async with SessionLocal() as session:
                source = await session.get(RagSource, source_id)
                if source is None:
                    raise LookupError("RAG Source를 찾을 수 없습니다.")
                chunks, embeddings, status, warnings = await _index_loaded_document(session, source, document, created_by="SYNC_INCREMENTAL")
                await session.commit()
                chunk_count += chunks
                embedding_count += embeddings
                results.append({"path": path, "status": status, "chunks": chunks, "embeddings": embeddings, "warnings": warnings})
            processed += 1
            await _set_sync_job(job_id, progress=min(88, 15 + int(70 * processed / max(1, total_changes))), chunks_updated=chunk_count, embeddings_updated=embedding_count)

        if embedding_count:
            await _set_sync_job(job_id, stage="HNSW_VERIFY", progress=92)
            ready, schema, index_name = await _ensure_hnsw_index()
            if not ready:
                raise RuntimeError("증분 Re-index 후 HNSW Index 검증에 실패했습니다.")
        else:
            schema, index_name = "", HNSW_INDEX_NAME

        async with SessionLocal() as session:
            source = await session.get(RagSource, source_id)
            if source is not None:
                source.status = "INDEXED"
                source.updated_at = datetime.utcnow()
            setting = await _source_setting(session, source_id)
            setting.last_synced_at = datetime.utcnow()
            setting.last_change_count = total_changes
            await session.commit()
        await _set_sync_job(
            job_id,
            status="COMPLETED",
            stage="COMPLETED",
            progress=100,
            chunks_updated=chunk_count,
            embeddings_updated=embedding_count,
            result_json={**changes, "documents": results, "skipped_files": skipped, "schema": schema, "hnsw_index_name": index_name},
            finished_at=datetime.utcnow(),
        )
    except Exception as exc:
        await _set_sync_job(job_id, status="FAILED", stage="FAILED", error_message=str(exc), finished_at=datetime.utcnow())


async def list_sync_jobs(project_root: str, limit: int = 30) -> list[dict[str, Any]]:
    pc_name = current_pc_name()
    root = str(project_root or "").strip()
    async with SessionLocal() as session:
        rows = (await session.execute(select(RagSyncJob).where(
            RagSyncJob.pc_name == pc_name,
            RagSyncJob.project_root == root,
        ).order_by(RagSyncJob.id.desc()).limit(max(1, min(int(limit), 100))))).scalars().all()
        return [_serialize_sync_job(row) for row in rows]


async def get_sync_job(job_id: int) -> dict[str, Any]:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        row = await session.get(RagSyncJob, int(job_id))
        if row is None or row.pc_name != pc_name:
            raise LookupError("RAG Sync Job을 찾을 수 없습니다.")
        return _serialize_sync_job(row)


async def list_operation_sources(project_root: str) -> list[dict[str, Any]]:
    pc_name = current_pc_name()
    root = str(project_root or "").strip()
    async with SessionLocal() as session:
        sources = (await session.execute(select(RagSource).where(
            RagSource.pc_name == pc_name,
            RagSource.project_root == root,
            RagSource.is_deleted.is_(False),
        ).order_by(RagSource.id.asc()))).scalars().all()
        result: list[dict[str, Any]] = []
        for source in sources:
            setting = await _source_setting(session, source.id)
            document_count = int((await session.execute(select(func.count(RagDocument.id)).where(
                RagDocument.source_id == source.id,
                RagDocument.is_deleted.is_(False),
            ))).scalar() or 0)
            result.append({
                "id": source.id,
                "display_name": source.display_name,
                "source_uri": source.source_uri,
                "source_type": source.source_type,
                "status": source.status,
                "is_active": bool(source.is_active),
                "sync_mode": setting.sync_mode,
                "last_checked_at": _iso(setting.last_checked_at),
                "last_synced_at": _iso(setting.last_synced_at),
                "last_change_count": setting.last_change_count,
                "document_count": document_count,
            })
        await session.commit()
        return result


async def list_operation_documents(project_root: str, source_id: int | None = None) -> list[dict[str, Any]]:
    pc_name = current_pc_name()
    root = str(project_root or "").strip()
    async with SessionLocal() as session:
        stmt = select(RagDocument).where(
            RagDocument.pc_name == pc_name,
            RagDocument.project_root == root,
            RagDocument.is_deleted.is_(False),
        )
        if source_id:
            stmt = stmt.where(RagDocument.source_id == int(source_id))
        rows = (await session.execute(stmt.order_by(RagDocument.path.asc()))).scalars().all()
        result: list[dict[str, Any]] = []
        for row in rows:
            security = (await session.execute(select(RagDocumentSecurity).where(RagDocumentSecurity.document_id == row.id))).scalar_one_or_none()
            version_count = int((await session.execute(select(func.count(RagDocumentVersion.id)).where(RagDocumentVersion.document_id == row.id))).scalar() or 0)
            current_version = (await session.execute(select(RagDocumentVersion).where(
                RagDocumentVersion.document_id == row.id,
                RagDocumentVersion.is_current.is_(True),
            ).order_by(RagDocumentVersion.version_no.desc()))).scalars().first()
            result.append({
                "id": row.id,
                "source_id": row.source_id,
                "path": row.path,
                "filename": row.filename,
                "document_type": row.document_type,
                "language": row.language,
                "checksum": row.checksum,
                "status": row.status,
                "chunk_count": row.chunk_count,
                "safety_level": row.safety_level,
                "security_level": security.security_level if security else "INTERNAL",
                "security_note": security.note if security else "",
                "is_active": bool(row.is_active),
                "version_count": version_count,
                "current_version_id": current_version.id if current_version else None,
                "current_version_no": current_version.version_no if current_version else None,
                "updated_at": _iso(row.updated_at),
            })
        return result


async def list_document_versions(document_id: int) -> list[dict[str, Any]]:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        document = await session.get(RagDocument, int(document_id))
        if document is None or document.pc_name != pc_name:
            raise LookupError("RAG Document를 찾을 수 없습니다.")
        if not (await session.execute(select(RagDocumentVersion.id).where(RagDocumentVersion.document_id == document.id))).scalars().first() and document.status == "INDEXED":
            await _snapshot_document(session, document, created_by="VERSION_BOOTSTRAP", force=True)
            await session.commit()
        rows = (await session.execute(select(RagDocumentVersion).where(
            RagDocumentVersion.document_id == document.id,
        ).order_by(RagDocumentVersion.version_no.desc()))).scalars().all()
        return [{
            "id": row.id,
            "document_id": row.document_id,
            "version_no": row.version_no,
            "checksum": row.checksum,
            "document_type": row.document_type,
            "language": row.language,
            "safety_level": row.safety_level,
            "chunk_count": len(row.chunk_snapshot or []),
            "source_revision": row.source_revision,
            "is_current": bool(row.is_current),
            "created_by": row.created_by,
            "created_at": _iso(row.created_at),
        } for row in rows]


async def rollback_document_version(version_id: int) -> dict[str, Any]:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        version = await session.get(RagDocumentVersion, int(version_id))
        if version is None:
            raise LookupError("RAG Document Version을 찾을 수 없습니다.")
        document = await session.get(RagDocument, version.document_id)
        if document is None or document.pc_name != pc_name:
            raise LookupError("RAG Document를 찾을 수 없습니다.")
        if document.status == "INDEXED" and document.chunk_count:
            await _snapshot_document(session, document, created_by="ROLLBACK_BACKUP")
        await _clear_document_index(session, document.id)
        chunk_rows: list[RagChunk] = []
        for item in version.chunk_snapshot or []:
            row = RagChunk(
                document_id=document.id,
                source_id=document.source_id,
                chunk_index=int(item.get("chunk_index") or 0),
                content=str(item.get("content") or ""),
                content_hash=str(item.get("content_hash") or ""),
                char_count=int(item.get("char_count") or len(str(item.get("content") or ""))),
                token_estimate=int(item.get("token_estimate") or 0),
                start_line=item.get("start_line"),
                end_line=item.get("end_line"),
                heading=str(item.get("heading") or ""),
                symbol_name=str(item.get("symbol_name") or ""),
                metadata_json=item.get("metadata_json") or {},
            )
            session.add(row)
            chunk_rows.append(row)
        await session.flush()
        vectors: list[list[float]] = []
        dimension = 0
        if chunk_rows:
            vectors, dimension, _ = await _embed_texts([row.content for row in chunk_rows])
            provider, model = _embedding_identity()
            for chunk, vector in zip(chunk_rows, vectors, strict=True):
                session.add(RagEmbedding(chunk_id=chunk.id, provider=provider, model=model, source_dimension=dimension, storage_dimension=RAG_VECTOR_STORAGE_DIMENSION, embedding=vector))
        document.checksum = version.checksum
        document.document_type = version.document_type
        document.language = version.language
        document.safety_level = version.safety_level
        document.safety_result = version.safety_result or {}
        document.chunk_count = len(chunk_rows)
        document.status = "INDEXED"
        document.is_active = True
        document.updated_at = datetime.utcnow()
        await session.execute(update(RagDocumentVersion).where(RagDocumentVersion.document_id == document.id).values(is_current=False))
        version.is_current = True
        await session.commit()
    if vectors:
        ready, _, _ = await _ensure_hnsw_index()
        if not ready:
            raise RuntimeError("Rollback 후 HNSW Index 검증에 실패했습니다.")
    return {"ok": True, "project_root": document.project_root, "document_id": document.id, "version_id": int(version_id), "version_no": version.version_no, "chunk_count": len(chunk_rows), "embedding_count": len(vectors)}


async def set_source_active(source_id: int, active: bool) -> dict[str, Any]:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        source = await session.get(RagSource, int(source_id))
        if source is None or source.pc_name != pc_name or source.is_deleted:
            raise LookupError("RAG Source를 찾을 수 없습니다.")
        source.is_active = bool(active)
        source.updated_at = datetime.utcnow()
        await session.commit()
        return {"ok": True, "project_root": source.project_root, "id": source.id, "is_active": bool(source.is_active)}


async def set_document_active(document_id: int, active: bool) -> dict[str, Any]:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        document = await session.get(RagDocument, int(document_id))
        if document is None or document.pc_name != pc_name or document.is_deleted:
            raise LookupError("RAG Document를 찾을 수 없습니다.")
        document.is_active = bool(active)
        document.status = "INDEXED" if active and document.chunk_count > 0 else "DISABLED"
        document.updated_at = datetime.utcnow()
        await session.commit()
        return {"ok": True, "project_root": document.project_root, "id": document.id, "is_active": bool(document.is_active), "status": document.status}
