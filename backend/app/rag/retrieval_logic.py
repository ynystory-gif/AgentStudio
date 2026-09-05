from __future__ import annotations

import re
from typing import Any

RRF_K = 60


def normalize_metadata_filter(value: Any) -> dict[str, Any]:
    """Normalize the phase-3 DB-neutral metadata filter contract."""
    raw = value if isinstance(value, dict) else {}

    def int_list(key: str) -> list[int]:
        values = raw.get(key) if isinstance(raw.get(key), list) else []
        result: list[int] = []
        for item in values:
            try:
                parsed = int(item)
            except Exception:
                continue
            if parsed > 0 and parsed not in result:
                result.append(parsed)
        return result[:100]

    def str_list(key: str) -> list[str]:
        values = raw.get(key) if isinstance(raw.get(key), list) else []
        result: list[str] = []
        for item in values:
            text = str(item or "").strip()
            if text and text not in result:
                result.append(text)
        return result[:100]

    return {
        "collection_ids": int_list("collection_ids"),
        "source_ids": int_list("source_ids"),
        "document_types": str_list("document_types"),
        "languages": str_list("languages"),
        "path_contains": str(raw.get("path_contains") or "").strip()[:500],
    }


def keyword_tokens(query: str) -> list[str]:
    tokens = re.findall(r"[0-9A-Za-z_가-힣][0-9A-Za-z_가-힣.\-/:]*", query)
    if not tokens and query.strip():
        tokens = [query.strip()]
    result: list[str] = []
    for token in tokens:
        lowered = token.casefold()
        if len(lowered) < 2 and not lowered.isdigit():
            continue
        if lowered not in result:
            result.append(lowered)
    return result[:16]


def keyword_score(item: dict[str, Any], query: str, tokens: list[str]) -> float:
    content = str(item.get("content") or "").casefold()
    heading = str(item.get("heading") or "").casefold()
    symbol = str(item.get("symbol_name") or "").casefold()
    path = str(item.get("document_path") or "").casefold()
    haystack = "\n".join((content, heading, symbol, path))
    query_norm = query.strip().casefold()
    if not tokens:
        return 0.0
    covered = sum(1 for token in tokens if token in haystack)
    coverage = covered / len(tokens)
    frequency = sum(min(haystack.count(token), 5) / 5.0 for token in tokens) / len(tokens)
    phrase_bonus = 0.25 if query_norm and query_norm in haystack else 0.0
    symbol_bonus = 0.15 if query_norm and (query_norm == symbol or query_norm in symbol) else 0.0
    path_bonus = 0.05 if query_norm and query_norm in path else 0.0
    return min(1.0, 0.45 * coverage + 0.20 * frequency + phrase_bonus + symbol_bonus + path_bonus)


def hybrid_fusion(
    vector_results: list[dict[str, Any]],
    keyword_results: list[dict[str, Any]],
    limit: int,
    *,
    rrf_k: int = RRF_K,
) -> list[dict[str, Any]]:
    """Reciprocal Rank Fusion with a normalized UI score in the 0..1 range."""
    merged: dict[int, dict[str, Any]] = {}
    rrf_scores: dict[int, float] = {}
    vector_rank: dict[int, int] = {}
    keyword_rank: dict[int, int] = {}

    for rank, item in enumerate(vector_results, start=1):
        chunk_id = int(item["chunk_id"])
        merged[chunk_id] = dict(item)
        vector_rank[chunk_id] = rank
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
    for rank, item in enumerate(keyword_results, start=1):
        chunk_id = int(item["chunk_id"])
        existing = merged.get(chunk_id)
        if existing is None:
            merged[chunk_id] = dict(item)
        else:
            existing["keyword_score"] = item.get("keyword_score")
        keyword_rank[chunk_id] = rank
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)

    normalization = 2.0 / (rrf_k + 1)
    results: list[dict[str, Any]] = []
    for chunk_id, item in merged.items():
        score = rrf_scores[chunk_id] / normalization if normalization else 0.0
        item["fusion_score"] = round(score, 6)
        item["score"] = round(score, 6)
        item["vector_rank"] = vector_rank.get(chunk_id)
        item["keyword_rank"] = keyword_rank.get(chunk_id)
        results.append(item)
    results.sort(
        key=lambda item: (
            float(item.get("fusion_score") or 0),
            float(item.get("vector_similarity") or 0),
            float(item.get("keyword_score") or 0),
        ),
        reverse=True,
    )
    return results[: max(1, int(limit))]


def route_retrieval_mode(query: str, configured_mode: str = "HYBRID") -> dict[str, Any]:
    """Explainable phase-5 Retrieval Router.

    The router deliberately avoids an LLM call on every search. It classifies query
    shape deterministically so Agent execution remains fast/reproducible, while the
    phase-5 AI recommendation service decides whether this Router should be enabled.
    """
    text = str(query or "").strip()
    lowered = text.casefold()
    tokens = keyword_tokens(text)

    exact_patterns = [
        r"\b(?:err|error|http|sql|ora|pg|code)[-_ ]?\d{2,}\b",
        r"\b[a-zA-Z_][a-zA-Z0-9_]*\([^)]*\)",
        r"\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b",
        r"(?:^|[\\/])[\w.\-]+(?:[\\/][\w.\-]+)+",
        r"\.(?:py|tsx?|jsx?|java|cs|sql|json|ya?ml|md)\b",
    ]
    exact_hits = sum(1 for pattern in exact_patterns if re.search(pattern, text, flags=re.IGNORECASE))
    quoted = bool(re.search(r"['\"`][^'\"`]{2,}['\"`]", text))
    concept_terms = (
        "무엇", "왜", "어떻게", "설명", "구조", "개념", "원리", "방식", "의미",
        "what", "why", "how", "explain", "architecture", "concept", "meaning",
    )
    conceptual = any(term in lowered for term in concept_terms)
    long_natural = len(text) >= 55 and len(tokens) >= 5

    if exact_hits >= 2 or (exact_hits >= 1 and quoted):
        selected = "KEYWORD"
        reason = "오류 코드·함수명·경로처럼 정확 문자열 신호가 강해 Keyword Search를 우선합니다."
        confidence = 0.92
    elif exact_hits >= 1:
        selected = "HYBRID"
        reason = "정확 문자열 신호와 자연어 문맥이 함께 있어 Vector + Keyword Hybrid Search가 적합합니다."
        confidence = 0.86
    elif conceptual and long_natural:
        selected = "VECTOR"
        reason = "긴 설명형 자연어 질문으로 판단되어 의미 유사도 중심 Vector Search를 선택합니다."
        confidence = 0.82
    else:
        selected = "HYBRID"
        reason = "질문 유형이 혼합되거나 불확실하여 의미 검색과 정확 검색을 함께 사용하는 Hybrid Search를 선택합니다."
        confidence = 0.78

    configured = str(configured_mode or "HYBRID").upper()
    return {
        "configured_mode": configured,
        "selected_mode": selected,
        "reason": reason,
        "confidence": round(confidence, 2),
        "signals": {
            "exact_hits": exact_hits,
            "quoted_phrase": quoted,
            "conceptual": conceptual,
            "long_natural": long_natural,
            "token_count": len(tokens),
        },
    }


def _lexical_relevance(item: dict[str, Any], query: str) -> tuple[float, float]:
    tokens = keyword_tokens(query)
    if not tokens:
        return 0.0, 0.0
    content = str(item.get("content") or "").casefold()
    heading = str(item.get("heading") or "").casefold()
    symbol = str(item.get("symbol_name") or "").casefold()
    path = str(item.get("document_path") or "").casefold()
    combined = "\n".join((content, heading, symbol, path))
    covered = sum(1 for token in tokens if token in combined) / len(tokens)
    structural_hits = sum(1 for token in tokens if token in heading or token in symbol or token in path)
    structural = min(1.0, structural_hits / max(1, min(len(tokens), 3)))
    return covered, structural


def rerank_results(results: list[dict[str, Any]], query: str, limit: int) -> list[dict[str, Any]]:
    """Lightweight second-stage reranker used by phase-5.

    This reranker combines the first-stage retrieval score with lexical coverage and
    structural provenance (heading/symbol/path). It is deterministic and provider-free,
    so it can be used for every Agent execution without an additional paid/slow model.
    """
    reranked: list[dict[str, Any]] = []
    for item in results:
        next_item = dict(item)
        base = max(0.0, min(float(item.get("score") or 0.0), 1.0))
        vector = max(0.0, min(float(item.get("vector_similarity") or 0.0), 1.0))
        keyword = max(0.0, min(float(item.get("keyword_score") or 0.0), 1.0))
        lexical, structural = _lexical_relevance(item, query)
        score = 0.50 * base + 0.18 * vector + 0.14 * keyword + 0.13 * lexical + 0.05 * structural
        next_item["retrieval_score"] = round(base, 6)
        next_item["rerank_score"] = round(score, 6)
        next_item["rerank_lexical"] = round(lexical, 6)
        next_item["rerank_structural"] = round(structural, 6)
        next_item["score"] = round(score, 6)
        reranked.append(next_item)
    reranked.sort(
        key=lambda item: (
            float(item.get("rerank_score") or 0.0),
            float(item.get("retrieval_score") or 0.0),
            -int(item.get("chunk_id") or 0),
        ),
        reverse=True,
    )
    return reranked[: max(1, int(limit))]
