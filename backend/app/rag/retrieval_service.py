from __future__ import annotations

import time
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select

from app.core.database import SessionLocal
from app.core.machine_identity import current_pc_name
from app.models.rag_entities import (
    RAG_VECTOR_STORAGE_DIMENSION,
    RagChunk,
    RagCollection,
    RagCollectionSource,
    RagDocument,
    RagDocumentSecurity,
    RagEmbedding,
    RagIntelligenceSetting,
    RagRetrievalSetting,
    RagSearchLog,
    RagSource,
)
from app.rag.indexing_service import HNSW_INDEX_NAME, _embedding_identity, _storage_vector
from app.rag.retrieval_logic import RRF_K, hybrid_fusion, keyword_score, keyword_tokens, normalize_metadata_filter, rerank_results, route_retrieval_mode
from app.rag.security_service import normalize_security_context, resolve_security_scope, write_search_audit
from app.services.embedding_service import get_embedding_model


SEARCH_MODES = {"VECTOR", "KEYWORD", "HYBRID"}
DEFAULT_SEARCH_MODE = "HYBRID"
DEFAULT_TOP_K = 5
DEFAULT_SIMILARITY_THRESHOLD = 0.20
MAX_TOP_K = 50


def _root(value: str | None) -> str:
    return str(value or "").strip()


def _clamp_top_k(value: Any) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = DEFAULT_TOP_K
    return max(1, min(parsed, MAX_TOP_K))


def _clamp_threshold(value: Any) -> float:
    try:
        parsed = float(value)
    except Exception:
        parsed = DEFAULT_SIMILARITY_THRESHOLD
    return max(0.0, min(parsed, 1.0))


def _normalize_mode(value: Any) -> str:
    mode = str(value or DEFAULT_SEARCH_MODE).strip().upper()
    if mode not in SEARCH_MODES:
        raise ValueError("검색 방식은 VECTOR / KEYWORD / HYBRID 중 하나여야 합니다.")
    return mode


def _clamp_rerank_top_n(value: Any, top_k: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = max(12, top_k * 2)
    return max(top_k, min(parsed, 50))


async def _resolve_intelligence_config(project_root: str, payload: dict[str, Any], top_k: int) -> dict[str, Any]:
    pc_name = current_pc_name()
    router_enabled = payload.get("router_enabled")
    reranking_enabled = payload.get("reranking_enabled")
    rerank_top_n = payload.get("rerank_top_n")
    async with SessionLocal() as session:
        row = (await session.execute(select(RagIntelligenceSetting).where(
            RagIntelligenceSetting.pc_name == pc_name,
            RagIntelligenceSetting.project_root == project_root,
        ))).scalar_one_or_none()
        if row is None:
            row = RagIntelligenceSetting(
                pc_name=pc_name,
                project_root=project_root,
                router_enabled=True,
                reranking_enabled=True,
                rerank_top_n=max(12, top_k * 2),
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
    return {
        "router_enabled": bool(row.router_enabled if router_enabled is None else router_enabled),
        "reranking_enabled": bool(row.reranking_enabled if reranking_enabled is None else reranking_enabled),
        "rerank_top_n": _clamp_rerank_top_n(row.rerank_top_n if rerank_top_n is None else rerank_top_n, top_k),
    }


def _serialize_setting(row: RagRetrievalSetting) -> dict[str, Any]:
    return {
        "id": row.id,
        "pc_name": row.pc_name,
        "project_root": row.project_root,
        "search_mode": row.search_mode,
        "top_k": row.top_k,
        "similarity_threshold": row.similarity_threshold,
        "metadata_filter": normalize_metadata_filter(row.metadata_filter),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_log(row: RagSearchLog) -> dict[str, Any]:
    return {
        "id": row.id,
        "pc_name": row.pc_name,
        "project_root": row.project_root,
        "query_text": row.query_text,
        "search_mode": row.search_mode,
        "top_k": row.top_k,
        "similarity_threshold": row.similarity_threshold,
        "metadata_filter": row.metadata_filter or {},
        "result_count": row.result_count,
        "vector_candidate_count": row.vector_candidate_count,
        "keyword_candidate_count": row.keyword_candidate_count,
        "duration_ms": row.duration_ms,
        "embedding_provider": row.embedding_provider,
        "embedding_model": row.embedding_model,
        "result_summary": row.result_summary or {},
        "error_message": row.error_message,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def get_or_create_retrieval_setting(project_root: str = "") -> dict[str, Any]:
    pc_name = current_pc_name()
    root = _root(project_root)
    async with SessionLocal() as session:
        row = (await session.execute(select(RagRetrievalSetting).where(
            RagRetrievalSetting.pc_name == pc_name,
            RagRetrievalSetting.project_root == root,
        ))).scalar_one_or_none()
        if row is None:
            row = RagRetrievalSetting(
                pc_name=pc_name,
                project_root=root,
                search_mode=DEFAULT_SEARCH_MODE,
                top_k=DEFAULT_TOP_K,
                similarity_threshold=DEFAULT_SIMILARITY_THRESHOLD,
                metadata_filter=normalize_metadata_filter({}),
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return _serialize_setting(row)


async def update_retrieval_setting(project_root: str, patch: dict[str, Any]) -> dict[str, Any]:
    pc_name = current_pc_name()
    root = _root(project_root)
    async with SessionLocal() as session:
        row = (await session.execute(select(RagRetrievalSetting).where(
            RagRetrievalSetting.pc_name == pc_name,
            RagRetrievalSetting.project_root == root,
        ))).scalar_one_or_none()
        if row is None:
            row = RagRetrievalSetting(pc_name=pc_name, project_root=root)
            session.add(row)
        if "search_mode" in patch:
            row.search_mode = _normalize_mode(patch.get("search_mode"))
        if "top_k" in patch:
            row.top_k = _clamp_top_k(patch.get("top_k"))
        if "similarity_threshold" in patch:
            row.similarity_threshold = _clamp_threshold(patch.get("similarity_threshold"))
        if "metadata_filter" in patch:
            row.metadata_filter = normalize_metadata_filter(patch.get("metadata_filter"))
        row.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(row)
        return _serialize_setting(row)


async def retrieval_options(project_root: str = "") -> dict[str, Any]:
    pc_name = current_pc_name()
    root = _root(project_root)
    async with SessionLocal() as session:
        source_rows = (await session.execute(select(RagSource).where(
            RagSource.pc_name == pc_name,
            RagSource.project_root == root,
            RagSource.status == "INDEXED",
            RagSource.is_active.is_(True),
            RagSource.is_deleted.is_(False),
        ).order_by(RagSource.display_name.asc()))).scalars().all()
        document_types = list((await session.execute(select(RagDocument.document_type).where(
            RagDocument.pc_name == pc_name,
            RagDocument.project_root == root,
            RagDocument.status == "INDEXED",
            RagDocument.is_active.is_(True),
            RagDocument.is_deleted.is_(False),
        ).distinct().order_by(RagDocument.document_type.asc()))).scalars().all())
        languages = list((await session.execute(select(RagDocument.language).where(
            RagDocument.pc_name == pc_name,
            RagDocument.project_root == root,
            RagDocument.status == "INDEXED",
            RagDocument.is_active.is_(True),
            RagDocument.is_deleted.is_(False),
            RagDocument.language != "",
        ).distinct().order_by(RagDocument.language.asc()))).scalars().all())
        chunk_count = int((await session.execute(select(func.count(RagChunk.id)).join(
            RagDocument, RagDocument.id == RagChunk.document_id
        ).where(
            RagDocument.pc_name == pc_name,
            RagDocument.project_root == root,
            RagDocument.status == "INDEXED",
            RagDocument.is_active.is_(True),
            RagDocument.is_deleted.is_(False),
            RagChunk.is_active.is_(True),
        ))).scalar() or 0)
        embedding_count = int((await session.execute(select(func.count(RagEmbedding.id)).join(
            RagChunk, RagChunk.id == RagEmbedding.chunk_id
        ).join(RagDocument, RagDocument.id == RagChunk.document_id).where(
            RagDocument.pc_name == pc_name,
            RagDocument.project_root == root,
            RagDocument.status == "INDEXED",
            RagDocument.is_active.is_(True),
            RagDocument.is_deleted.is_(False),
            RagChunk.is_active.is_(True),
        ))).scalar() or 0)
    provider, model = _embedding_identity()
    return {
        "search_modes": ["VECTOR", "KEYWORD", "HYBRID"],
        "default_mode": DEFAULT_SEARCH_MODE,
        "default_top_k": DEFAULT_TOP_K,
        "default_similarity_threshold": DEFAULT_SIMILARITY_THRESHOLD,
        "max_top_k": MAX_TOP_K,
        "rrf_k": RRF_K,
        "hnsw_index_name": HNSW_INDEX_NAME,
        "embedding_provider": provider,
        "embedding_model": model,
        "indexed_source_count": len(source_rows),
        "indexed_chunk_count": chunk_count,
        "embedding_count": embedding_count,
        "sources": [
            {"id": row.id, "display_name": row.display_name, "source_type": row.source_type, "source_uri": row.source_uri}
            for row in source_rows
        ],
        "document_types": [str(value) for value in document_types if str(value or "").strip()],
        "languages": [str(value) for value in languages if str(value or "").strip()],
    }


async def _resolve_source_ids(session, *, pc_name: str, project_root: str, filters: dict[str, Any], security_scope: dict[str, Any]) -> list[int]:
    stmt = select(RagSource.id).where(
        RagSource.pc_name == pc_name,
        RagSource.project_root == project_root,
        RagSource.status == "INDEXED",
        RagSource.is_active.is_(True),
        RagSource.is_deleted.is_(False),
    )
    requested_sources = [int(value) for value in (filters.get("source_ids") or []) if int(value) > 0]
    if requested_sources:
        stmt = stmt.where(RagSource.id.in_(requested_sources))
    requested_collections = [int(value) for value in (filters.get("collection_ids") or []) if int(value) > 0]
    allowed_collections = {int(value) for value in (security_scope.get("allowed_collection_ids") or [])}
    all_linked_sources = select(RagCollectionSource.source_id).join(
        RagCollection, RagCollection.id == RagCollectionSource.collection_id
    ).where(
        RagCollection.pc_name == pc_name,
        RagCollection.project_root == project_root,
        RagCollection.is_active.is_(True),
        RagCollection.is_deleted.is_(False),
    )
    if requested_collections:
        effective = [value for value in requested_collections if value in allowed_collections]
        if not effective:
            return []
        allowed_sources = select(RagCollectionSource.source_id).where(RagCollectionSource.collection_id.in_(effective))
        stmt = stmt.where(RagSource.id.in_(allowed_sources))
    else:
        allowed_sources = select(RagCollectionSource.source_id).where(RagCollectionSource.collection_id.in_(list(allowed_collections))) if allowed_collections else None
        if allowed_sources is None:
            stmt = stmt.where(~RagSource.id.in_(all_linked_sources))
        else:
            # Unassigned Sources remain visible; Collection-linked Sources must have at least one allowed Collection.
            stmt = stmt.where(or_(~RagSource.id.in_(all_linked_sources), RagSource.id.in_(allowed_sources)))
    return list((await session.execute(stmt.order_by(RagSource.id.asc()))).scalars().all())


def _base_conditions(*, pc_name: str, project_root: str, source_ids: list[int], filters: dict[str, Any], security_scope: dict[str, Any]) -> list[Any]:
    secured_document_ids = select(RagDocumentSecurity.document_id)
    allowed_document_ids = select(RagDocumentSecurity.document_id).where(
        RagDocumentSecurity.security_level.in_(list(security_scope.get("allowed_document_security_levels") or ["PUBLIC", "INTERNAL"]))
    )
    conditions: list[Any] = [
        RagSource.pc_name == pc_name,
        RagSource.project_root == project_root,
        RagSource.id.in_(source_ids),
        RagSource.status == "INDEXED",
        RagSource.is_active.is_(True),
        RagSource.is_deleted.is_(False),
        RagDocument.pc_name == pc_name,
        RagDocument.project_root == project_root,
        RagDocument.status == "INDEXED",
        RagDocument.is_active.is_(True),
        RagDocument.is_deleted.is_(False),
        or_(~RagDocument.id.in_(secured_document_ids), RagDocument.id.in_(allowed_document_ids)),
        RagChunk.is_active.is_(True),
    ]
    document_types = filters.get("document_types") or []
    if document_types:
        conditions.append(RagDocument.document_type.in_(document_types))
    languages = filters.get("languages") or []
    if languages:
        conditions.append(RagDocument.language.in_(languages))
    path_contains = str(filters.get("path_contains") or "").strip()
    if path_contains:
        conditions.append(RagDocument.path.icontains(path_contains, autoescape=True))
    return conditions


def _base_result(chunk: RagChunk, document: RagDocument, source: RagSource) -> dict[str, Any]:
    return {
        "chunk_id": chunk.id,
        "document_id": document.id,
        "source_id": source.id,
        "source_name": source.display_name or source.source_uri,
        "source_type": source.source_type,
        "document_path": document.path,
        "filename": document.filename,
        "document_type": document.document_type,
        "language": document.language,
        "chunk_index": chunk.chunk_index,
        "content": chunk.content,
        "start_line": chunk.start_line,
        "end_line": chunk.end_line,
        "heading": chunk.heading,
        "symbol_name": chunk.symbol_name,
        "metadata": chunk.metadata_json or {},
        "score": 0.0,
        "vector_similarity": None,
        "keyword_score": None,
        "fusion_score": None,
    }


async def _vector_search(
    session,
    *,
    pc_name: str,
    project_root: str,
    source_ids: list[int],
    filters: dict[str, Any],
    security_scope: dict[str, Any],
    query: str,
    threshold: float,
    candidate_limit: int,
) -> tuple[list[dict[str, Any]], str, str, int]:
    provider, model_name = _embedding_identity()
    vector = await get_embedding_model().aembed_query(query)
    stored_vector, source_dimension, _ = _storage_vector(list(vector))
    distance = RagEmbedding.embedding.cosine_distance(stored_vector)
    stmt = select(RagChunk, RagDocument, RagSource, distance.label("distance")).join(
        RagDocument, RagDocument.id == RagChunk.document_id
    ).join(RagSource, RagSource.id == RagChunk.source_id).join(
        RagEmbedding, RagEmbedding.chunk_id == RagChunk.id
    ).where(
        *_base_conditions(pc_name=pc_name, project_root=project_root, source_ids=source_ids, filters=filters, security_scope=security_scope),
        RagEmbedding.embedding.is_not(None),
        RagEmbedding.provider == provider,
        RagEmbedding.model == model_name,
        RagEmbedding.source_dimension == source_dimension,
        RagEmbedding.storage_dimension == RAG_VECTOR_STORAGE_DIMENSION,
    ).order_by(distance.asc()).limit(candidate_limit)
    rows = (await session.execute(stmt)).all()
    results: list[dict[str, Any]] = []
    for chunk, document, source, raw_distance in rows:
        if raw_distance is None:
            continue
        similarity = 1.0 - float(raw_distance)
        if similarity < threshold:
            continue
        item = _base_result(chunk, document, source)
        item["vector_similarity"] = round(similarity, 6)
        item["score"] = round(similarity, 6)
        results.append(item)
    return results, provider, model_name, source_dimension


async def _keyword_search(
    session,
    *,
    pc_name: str,
    project_root: str,
    source_ids: list[int],
    filters: dict[str, Any],
    security_scope: dict[str, Any],
    query: str,
    candidate_limit: int,
) -> list[dict[str, Any]]:
    tokens = keyword_tokens(query)
    if not tokens:
        return []
    token_conditions: list[Any] = []
    for token in tokens:
        token_conditions.extend([
            RagChunk.content.icontains(token, autoescape=True),
            RagChunk.heading.icontains(token, autoescape=True),
            RagChunk.symbol_name.icontains(token, autoescape=True),
            RagDocument.path.icontains(token, autoescape=True),
            RagDocument.filename.icontains(token, autoescape=True),
        ])
    stmt = select(RagChunk, RagDocument, RagSource).join(
        RagDocument, RagDocument.id == RagChunk.document_id
    ).join(RagSource, RagSource.id == RagChunk.source_id).where(
        *_base_conditions(pc_name=pc_name, project_root=project_root, source_ids=source_ids, filters=filters, security_scope=security_scope),
        or_(*token_conditions),
    ).limit(max(50, min(candidate_limit * 8, 400)))
    rows = (await session.execute(stmt)).all()
    results: list[dict[str, Any]] = []
    for chunk, document, source in rows:
        item = _base_result(chunk, document, source)
        score = keyword_score(item, query, tokens)
        if score <= 0:
            continue
        item["keyword_score"] = round(score, 6)
        item["score"] = round(score, 6)
        results.append(item)
    results.sort(key=lambda item: (float(item.get("keyword_score") or 0), -int(item["chunk_id"])), reverse=True)
    return results[:candidate_limit]


async def _collection_map(session, source_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    if not source_ids:
        return {}
    rows = (await session.execute(select(
        RagCollectionSource.source_id, RagCollection.id, RagCollection.name
    ).join(RagCollection, RagCollection.id == RagCollectionSource.collection_id).where(
        RagCollectionSource.source_id.in_(source_ids),
        RagCollection.is_active.is_(True),
        RagCollection.is_deleted.is_(False),
    ).order_by(RagCollection.name.asc()))).all()
    result: dict[int, list[dict[str, Any]]] = {}
    for source_id, collection_id, name in rows:
        result.setdefault(int(source_id), []).append({"id": int(collection_id), "name": str(name)})
    return result


async def _write_search_log(
    *,
    pc_name: str,
    project_root: str,
    query: str,
    mode: str,
    top_k: int,
    threshold: float,
    filters: dict[str, Any],
    result_count: int,
    vector_candidate_count: int,
    keyword_candidate_count: int,
    duration_ms: int,
    provider: str,
    model: str,
    results: list[dict[str, Any]],
    warnings: list[str],
    router_decision: dict[str, Any] | None = None,
    reranking: dict[str, Any] | None = None,
    error_message: str = "",
) -> int:
    summary = {
        "warnings": warnings,
        "router_decision": router_decision or {},
        "reranking": reranking or {},
        "results": [
            {
                "rank": item.get("rank"),
                "chunk_id": item.get("chunk_id"),
                "document_id": item.get("document_id"),
                "source_id": item.get("source_id"),
                "document_path": item.get("document_path"),
                "score": item.get("score"),
                "vector_similarity": item.get("vector_similarity"),
                "keyword_score": item.get("keyword_score"),
                "fusion_score": item.get("fusion_score"),
            }
            for item in results[:20]
        ],
    }
    async with SessionLocal() as session:
        row = RagSearchLog(
            pc_name=pc_name,
            project_root=project_root,
            query_text=query,
            search_mode=mode,
            top_k=top_k,
            similarity_threshold=threshold,
            metadata_filter=filters,
            result_count=result_count,
            vector_candidate_count=vector_candidate_count,
            keyword_candidate_count=keyword_candidate_count,
            duration_ms=max(0, int(duration_ms)),
            embedding_provider=provider,
            embedding_model=model,
            result_summary=summary,
            error_message=error_message,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return int(row.id)


async def retrieve(payload: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    pc_name = current_pc_name()
    project_root = _root(payload.get("project_root"))
    query = str(payload.get("query") or "").strip()
    if not project_root:
        raise ValueError("Retrieval Test 전에 Agent 프로젝트 경로를 설정하세요.")
    if not query:
        raise ValueError("검색 질문을 입력하세요.")
    if len(query) > 8000:
        raise ValueError("검색 질문은 8,000자 이하로 입력하세요.")

    requested_mode = _normalize_mode(payload.get("search_mode"))
    top_k = _clamp_top_k(payload.get("top_k"))
    threshold = _clamp_threshold(payload.get("similarity_threshold"))
    filters = normalize_metadata_filter(payload.get("metadata_filter"))
    security_context = normalize_security_context(payload.get("security_context"))
    security_scope: dict[str, Any] = {**security_context, "allowed_collection_ids": [], "denied_collection_ids": [], "allowed_document_security_levels": ["PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED"]}
    resolved_source_ids: list[int] = []
    intelligence = await _resolve_intelligence_config(project_root, payload, top_k)
    router_decision = route_retrieval_mode(query, requested_mode) if intelligence["router_enabled"] else {
        "configured_mode": requested_mode,
        "selected_mode": requested_mode,
        "reason": "Retrieval Router가 비활성화되어 저장된 검색 방식을 그대로 사용합니다.",
        "confidence": 1.0,
        "signals": {},
    }
    mode = _normalize_mode(router_decision.get("selected_mode"))
    reranking_enabled = bool(intelligence["reranking_enabled"])
    rerank_top_n = int(intelligence["rerank_top_n"])
    candidate_limit = min(200, max(20, top_k * 5, rerank_top_n * 2 if reranking_enabled else 0))
    provider, model_name = _embedding_identity()
    warnings: list[str] = []
    results: list[dict[str, Any]] = []
    vector_results: list[dict[str, Any]] = []
    keyword_results: list[dict[str, Any]] = []
    source_dimension = 0

    try:
        async with SessionLocal() as session:
            security_scope = await resolve_security_scope(
                session,
                pc_name=pc_name,
                project_root=project_root,
                security_context=security_context,
                requested_collection_ids=filters.get("collection_ids") or [],
            )
            source_ids = await _resolve_source_ids(session, pc_name=pc_name, project_root=project_root, filters=filters, security_scope=security_scope)
            resolved_source_ids = list(source_ids)
            if not source_ids:
                warnings.append("현재 Metadata Filter 범위에 Indexed Source가 없습니다.")
            else:
                if mode in {"VECTOR", "HYBRID"}:
                    try:
                        vector_results, provider, model_name, source_dimension = await _vector_search(
                            session,
                            pc_name=pc_name,
                            project_root=project_root,
                            source_ids=source_ids,
                            filters=filters,
                            security_scope=security_scope,
                            query=query,
                            threshold=threshold,
                            candidate_limit=candidate_limit,
                        )
                        if not vector_results:
                            indexed_models = (await session.execute(select(
                                RagEmbedding.provider, RagEmbedding.model, RagEmbedding.source_dimension
                            ).join(RagChunk, RagChunk.id == RagEmbedding.chunk_id).join(
                                RagDocument, RagDocument.id == RagChunk.document_id
                            ).where(
                                RagDocument.project_root == project_root,
                                RagDocument.pc_name == pc_name,
                                RagDocument.status == "INDEXED",
                                RagChunk.source_id.in_(source_ids),
                            ).distinct())).all()
                            if indexed_models:
                                available = ", ".join(f"{p}/{m}({d}d)" for p, m, d in indexed_models[:5])
                                warnings.append(
                                    "Vector 후보가 없습니다. Similarity Threshold 또는 현재 Embedding 모델과 Index 모델 일치 여부를 확인하세요. "
                                    f"현재={provider}/{model_name}({source_dimension}d), Index={available}"
                                )
                    except Exception as exc:
                        if mode == "VECTOR":
                            raise
                        warnings.append(f"Vector Search를 실행하지 못해 Hybrid를 Keyword Search 중심으로 계속했습니다: {exc}")

                if mode in {"KEYWORD", "HYBRID"}:
                    keyword_results = await _keyword_search(
                        session,
                        pc_name=pc_name,
                        project_root=project_root,
                        source_ids=source_ids,
                        filters=filters,
                        security_scope=security_scope,
                        query=query,
                        candidate_limit=candidate_limit,
                    )

                pool_limit = rerank_top_n if reranking_enabled else top_k
                if mode == "VECTOR":
                    results = vector_results[:pool_limit]
                elif mode == "KEYWORD":
                    results = keyword_results[:pool_limit]
                else:
                    results = hybrid_fusion(vector_results, keyword_results, pool_limit)

                if reranking_enabled and results:
                    results = rerank_results(results[:rerank_top_n], query, top_k)
                else:
                    results = results[:top_k]

                collections_by_source = await _collection_map(session, [int(item["source_id"]) for item in results])
                for rank, item in enumerate(results, start=1):
                    item["rank"] = rank
                    item["collections"] = collections_by_source.get(int(item["source_id"]), [])

        duration_ms = round((time.perf_counter() - started) * 1000)
        log_id = await _write_search_log(
            pc_name=pc_name,
            project_root=project_root,
            query=query,
            mode=mode,
            top_k=top_k,
            threshold=threshold,
            filters=filters,
            result_count=len(results),
            vector_candidate_count=len(vector_results),
            keyword_candidate_count=len(keyword_results),
            duration_ms=duration_ms,
            provider=provider if mode in {"VECTOR", "HYBRID"} else "",
            model=model_name if mode in {"VECTOR", "HYBRID"} else "",
            results=results,
            warnings=warnings,
            router_decision=router_decision,
            reranking={"enabled": reranking_enabled, "top_n": rerank_top_n, "engine": "LIGHTWEIGHT_RELEVANCE_V1" if reranking_enabled else "OFF"},
        )
        audit_decision = "DENY" if not resolved_source_ids and bool(security_scope.get("denied_collection_ids")) else "ALLOW"
        audit_id = await write_search_audit(
            project_root=project_root,
            query=query,
            security_scope=security_scope,
            allowed_source_count=len(resolved_source_ids),
            result_count=len(results),
            search_log_id=log_id,
            decision=audit_decision,
            reason="검색 전 Collection/Role/Document 보안 필터를 적용했습니다.",
        )
        return {
            "search_log_id": log_id,
            "search_audit_log_id": audit_id,
            "security": security_scope,
            "query": query,
            "requested_search_mode": requested_mode,
            "search_mode": mode,
            "router": {"enabled": bool(intelligence["router_enabled"]), **router_decision},
            "reranking": {"enabled": reranking_enabled, "top_n": rerank_top_n, "engine": "LIGHTWEIGHT_RELEVANCE_V1" if reranking_enabled else "OFF"},
            "top_k": top_k,
            "similarity_threshold": threshold,
            "metadata_filter": filters,
            "result_count": len(results),
            "vector_candidate_count": len(vector_results),
            "keyword_candidate_count": len(keyword_results),
            "duration_ms": duration_ms,
            "embedding_provider": provider if mode in {"VECTOR", "HYBRID"} else "",
            "embedding_model": model_name if mode in {"VECTOR", "HYBRID"} else "",
            "embedding_dimension": source_dimension,
            "hnsw_index_name": HNSW_INDEX_NAME,
            "rrf_k": RRF_K if mode == "HYBRID" else None,
            "warnings": warnings,
            "results": results,
        }
    except Exception as exc:
        duration_ms = round((time.perf_counter() - started) * 1000)
        try:
            await _write_search_log(
                pc_name=pc_name,
                project_root=project_root,
                query=query,
                mode=mode,
                top_k=top_k,
                threshold=threshold,
                filters=filters,
                result_count=0,
                vector_candidate_count=len(vector_results),
                keyword_candidate_count=len(keyword_results),
                duration_ms=duration_ms,
                provider=provider if mode in {"VECTOR", "HYBRID"} else "",
                model=model_name if mode in {"VECTOR", "HYBRID"} else "",
                results=[],
                warnings=warnings,
                router_decision=router_decision,
                reranking={"enabled": reranking_enabled, "top_n": rerank_top_n, "engine": "LIGHTWEIGHT_RELEVANCE_V1" if reranking_enabled else "OFF"},
                error_message=str(exc),
            )
        except Exception:
            pass
        try:
            await write_search_audit(
                project_root=project_root,
                query=query,
                security_scope=security_scope,
                allowed_source_count=len(resolved_source_ids),
                result_count=0,
                search_log_id=None,
                decision="ERROR",
                reason=str(exc),
            )
        except Exception:
            pass
        raise


async def list_search_logs(project_root: str = "", limit: int = 30) -> list[dict[str, Any]]:
    pc_name = current_pc_name()
    root = _root(project_root)
    limit = max(1, min(int(limit), 100))
    async with SessionLocal() as session:
        stmt = select(RagSearchLog).where(RagSearchLog.pc_name == pc_name)
        if root:
            stmt = stmt.where(RagSearchLog.project_root == root)
        rows = (await session.execute(stmt.order_by(RagSearchLog.id.desc()).limit(limit))).scalars().all()
        return [_serialize_log(row) for row in rows]
