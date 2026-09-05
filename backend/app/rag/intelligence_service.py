from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.machine_identity import current_pc_name
from app.models.rag_entities import (
    RagAgentTool,
    RagIntelligenceSetting,
    RagRecommendationRun,
    RagRetrievalSetting,
)
from app.rag.retrieval_logic import normalize_metadata_filter
from app.rag.retrieval_service import (
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_TOP_K,
    _clamp_threshold,
    _clamp_top_k,
    _normalize_mode,
    list_search_logs,
    retrieval_options,
)
from app.services.model_router import LLMTask, model_for_task


DEFAULT_INTELLIGENCE = {
    "router_enabled": True,
    "reranking_enabled": True,
    "rerank_top_n": 12,
}
ALLOWED_APPLY_KEYS = {
    "search_mode",
    "top_k",
    "similarity_threshold",
    "router_enabled",
    "reranking_enabled",
    "rerank_top_n",
}
FIELD_LABELS = {
    "search_mode": "검색 방식",
    "top_k": "Top K",
    "similarity_threshold": "Similarity Threshold",
    "router_enabled": "Retrieval Router",
    "reranking_enabled": "Reranking",
    "rerank_top_n": "Rerank 후보 수",
}


def _root(value: str | None) -> str:
    return str(value or "").strip()


def _clamp_rerank_top_n(value: Any, top_k: int = 5) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = max(12, top_k * 2)
    return max(max(1, top_k), min(parsed, 50))


def _serialize_intelligence(row: RagIntelligenceSetting) -> dict[str, Any]:
    return {
        "id": row.id,
        "pc_name": row.pc_name,
        "project_root": row.project_root,
        "router_enabled": bool(row.router_enabled),
        "reranking_enabled": bool(row.reranking_enabled),
        "rerank_top_n": int(row.rerank_top_n or 12),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_recommendation(row: RagRecommendationRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "pc_name": row.pc_name,
        "project_root": row.project_root,
        "provider": row.provider,
        "status": row.status,
        "summary": row.summary,
        "current_config": row.current_config or {},
        "recommended_config": row.recommended_config or {},
        "diff": row.diff_json or [],
        "evaluation": row.evaluation_json or {},
        "test_insights": row.test_insights or [],
        "warnings": row.warnings or [],
        "applied_keys": row.applied_keys or [],
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "applied_at": row.applied_at.isoformat() if row.applied_at else None,
    }


async def get_or_create_intelligence_setting(project_root: str = "") -> dict[str, Any]:
    pc_name = current_pc_name()
    root = _root(project_root)
    async with SessionLocal() as session:
        row = (await session.execute(select(RagIntelligenceSetting).where(
            RagIntelligenceSetting.pc_name == pc_name,
            RagIntelligenceSetting.project_root == root,
        ))).scalar_one_or_none()
        if row is None:
            row = RagIntelligenceSetting(pc_name=pc_name, project_root=root, **DEFAULT_INTELLIGENCE)
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return _serialize_intelligence(row)


async def update_intelligence_setting(project_root: str, patch: dict[str, Any]) -> dict[str, Any]:
    pc_name = current_pc_name()
    root = _root(project_root)
    async with SessionLocal() as session:
        row = (await session.execute(select(RagIntelligenceSetting).where(
            RagIntelligenceSetting.pc_name == pc_name,
            RagIntelligenceSetting.project_root == root,
        ))).scalar_one_or_none()
        if row is None:
            row = RagIntelligenceSetting(pc_name=pc_name, project_root=root, **DEFAULT_INTELLIGENCE)
            session.add(row)
        if "router_enabled" in patch:
            row.router_enabled = bool(patch.get("router_enabled"))
        if "reranking_enabled" in patch:
            row.reranking_enabled = bool(patch.get("reranking_enabled"))
        if "rerank_top_n" in patch:
            row.rerank_top_n = _clamp_rerank_top_n(patch.get("rerank_top_n"))
        row.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(row)
        return _serialize_intelligence(row)


async def _current_config(project_root: str) -> dict[str, Any]:
    pc_name = current_pc_name()
    root = _root(project_root)
    async with SessionLocal() as session:
        retrieval = (await session.execute(select(RagRetrievalSetting).where(
            RagRetrievalSetting.pc_name == pc_name,
            RagRetrievalSetting.project_root == root,
        ))).scalar_one_or_none()
        intelligence = (await session.execute(select(RagIntelligenceSetting).where(
            RagIntelligenceSetting.pc_name == pc_name,
            RagIntelligenceSetting.project_root == root,
        ))).scalar_one_or_none()
        if retrieval is None:
            retrieval = RagRetrievalSetting(
                pc_name=pc_name,
                project_root=root,
                search_mode="HYBRID",
                top_k=DEFAULT_TOP_K,
                similarity_threshold=DEFAULT_SIMILARITY_THRESHOLD,
                metadata_filter=normalize_metadata_filter({}),
            )
            session.add(retrieval)
        if intelligence is None:
            intelligence = RagIntelligenceSetting(pc_name=pc_name, project_root=root, **DEFAULT_INTELLIGENCE)
            session.add(intelligence)
        await session.commit()
        return {
            "search_mode": _normalize_mode(retrieval.search_mode),
            "top_k": _clamp_top_k(retrieval.top_k),
            "similarity_threshold": _clamp_threshold(retrieval.similarity_threshold),
            "router_enabled": bool(intelligence.router_enabled),
            "reranking_enabled": bool(intelligence.reranking_enabled),
            "rerank_top_n": _clamp_rerank_top_n(intelligence.rerank_top_n, _clamp_top_k(retrieval.top_k)),
        }


def _log_insights(logs: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(logs)
    if not total:
        return {
            "test_count": 0,
            "zero_result_rate": 0.0,
            "warning_rate": 0.0,
            "avg_duration_ms": 0,
            "avg_result_count": 0.0,
            "exact_query_ratio": 0.0,
        }
    zero = sum(1 for row in logs if int(row.get("result_count") or 0) == 0)
    warnings = sum(1 for row in logs if (row.get("result_summary") or {}).get("warnings"))
    durations = [max(0, int(row.get("duration_ms") or 0)) for row in logs]
    counts = [max(0, int(row.get("result_count") or 0)) for row in logs]
    exact_re = re.compile(r"(?:\b(?:ERR|HTTP|ORA|SQL)[-_ ]?\d+\b|\b[a-zA-Z_][a-zA-Z0-9_]{2,}\b|\.(?:py|tsx?|jsx?|sql)\b)", re.I)
    exact = sum(1 for row in logs if exact_re.search(str(row.get("query_text") or "")))
    return {
        "test_count": total,
        "zero_result_rate": round(zero / total, 4),
        "warning_rate": round(warnings / total, 4),
        "avg_duration_ms": round(sum(durations) / total),
        "avg_result_count": round(sum(counts) / total, 2),
        "exact_query_ratio": round(exact / total, 4),
    }


def _score_evaluation(current: dict[str, Any], options: dict[str, Any], insight: dict[str, Any]) -> dict[str, Any]:
    indexed_sources = int(options.get("indexed_source_count") or 0)
    chunks = int(options.get("indexed_chunk_count") or 0)
    embeddings = int(options.get("embedding_count") or 0)
    if chunks <= 0:
        readiness = 25 if indexed_sources else 10
    else:
        embedding_ratio = min(1.0, embeddings / max(1, chunks))
        readiness = round(70 + embedding_ratio * 30)

    coverage = 62
    if current["search_mode"] == "HYBRID":
        coverage = 86
    elif current["search_mode"] == "VECTOR":
        coverage = 72
    elif current["search_mode"] == "KEYWORD":
        coverage = 68
    if current["router_enabled"]:
        coverage = min(100, coverage + 7)
    if current["reranking_enabled"]:
        coverage = min(100, coverage + 6)

    stability = 92
    if insight["test_count"]:
        stability = round(100 - insight["zero_result_rate"] * 70 - insight["warning_rate"] * 20)
        stability = max(30, min(100, stability))

    avg_ms = int(insight["avg_duration_ms"] or 0)
    if avg_ms <= 0:
        efficiency = 85
    elif avg_ms <= 250:
        efficiency = 96
    elif avg_ms <= 500:
        efficiency = 90
    elif avg_ms <= 1000:
        efficiency = 80
    elif avg_ms <= 2000:
        efficiency = 68
    else:
        efficiency = 52

    quality = round(readiness * 0.30 + coverage * 0.30 + stability * 0.25 + efficiency * 0.15)
    return {
        "overall_score": quality,
        "retrieval_readiness": readiness,
        "search_coverage": coverage,
        "test_stability": stability,
        "efficiency": efficiency,
        "basis": "현재 Index 상태와 최근 Retrieval Test 로그를 이용한 설정 품질 추정치이며 정답률 지표는 아닙니다.",
        "test_summary": insight,
    }


def _baseline_recommendation(current: dict[str, Any], options: dict[str, Any], insight: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str], list[str]]:
    chunks = int(options.get("indexed_chunk_count") or 0)
    doc_types = {str(v).upper() for v in (options.get("document_types") or [])}
    languages = {str(v).lower() for v in (options.get("languages") or [])}
    mixed_or_code = len(doc_types) > 1 or bool(languages) or any("CODE" in value or value in {"PYTHON", "TYPESCRIPT", "JAVASCRIPT", "SQL"} for value in doc_types)

    recommended = dict(current)
    reasons: dict[str, str] = {}
    warnings: list[str] = []

    recommended["search_mode"] = "HYBRID" if mixed_or_code or chunks >= 50 else current["search_mode"]
    reasons["search_mode"] = "코드/문서 또는 여러 문서 유형에서 의미 검색과 정확 문자열 검색을 함께 확보하기 위해 Hybrid를 권장합니다." if recommended["search_mode"] == "HYBRID" else "현재 데이터 규모에서는 기존 검색 방식을 유지해도 충분합니다."

    recommended["router_enabled"] = True
    reasons["router_enabled"] = "질문이 오류 코드·함수명·설명형 문장인지 분석해 Keyword/Vector/Hybrid 실행을 자동 선택하면 불필요한 검색을 줄일 수 있습니다."

    should_rerank = chunks >= 30 or insight["avg_result_count"] >= 4 or current["top_k"] >= 5
    recommended["reranking_enabled"] = bool(should_rerank)
    reasons["reranking_enabled"] = "1차 검색 후보를 질문 단어·구조 Metadata와 함께 다시 정렬해 최종 Context 관련도를 높입니다." if should_rerank else "현재 Corpus가 작아 Reranking 이득이 제한적이므로 필수로 켜지 않아도 됩니다."

    if insight["zero_result_rate"] >= 0.30:
        recommended["similarity_threshold"] = max(0.10, round(float(current["similarity_threshold"]) - 0.05, 2))
        reasons["similarity_threshold"] = "최근 Retrieval Test에서 검색 결과 없음 비율이 높아 Vector 후보가 지나치게 잘리지 않도록 Threshold를 낮춥니다."
    elif insight["test_count"] >= 5 and insight["zero_result_rate"] == 0 and insight["avg_result_count"] >= current["top_k"]:
        recommended["similarity_threshold"] = min(0.35, round(float(current["similarity_threshold"]) + 0.05, 2))
        reasons["similarity_threshold"] = "최근 테스트에서 후보가 충분히 검색되어 낮은 관련도 후보를 줄이도록 Threshold를 소폭 높입니다."
    else:
        recommended["similarity_threshold"] = float(current["similarity_threshold"])
        reasons["similarity_threshold"] = "최근 테스트에서 Threshold를 변경해야 할 강한 신호가 없어 현재 값을 유지합니다."

    if should_rerank and chunks >= 100:
        recommended["top_k"] = min(8, max(5, int(current["top_k"])))
    else:
        recommended["top_k"] = min(6, max(4, int(current["top_k"])))
    reasons["top_k"] = "최종 LLM Context는 너무 길지 않게 유지하면서 Reranking 후 충분한 근거 Chunk가 남도록 조정합니다."

    recommended["rerank_top_n"] = _clamp_rerank_top_n(max(int(recommended["top_k"]) * 2, 10), int(recommended["top_k"]))
    reasons["rerank_top_n"] = "최종 Top K보다 넓은 후보를 먼저 수집한 뒤 Reranking하여 상위 근거를 다시 선별합니다."

    if chunks <= 0:
        warnings.append("Indexed Chunk가 없어 추천은 데이터 구조와 현재 설정 중심입니다. Index 완료 후 Retrieval Test를 실행하면 테스트 기반 추천이 더 정확해집니다.")
    elif insight["test_count"] == 0:
        warnings.append("Retrieval Test 로그가 없어 테스트 기반 조정은 제한적입니다. 추천 적용 후 동일 질문으로 테스트를 실행하세요.")

    return recommended, reasons, warnings


def _extract_json(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
        raw = re.sub(r"\s*```$", "", raw)
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        match = re.search(r"\{.*\}", raw, flags=re.S)
        if not match:
            return {}
        try:
            parsed = json.loads(match.group(0))
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}


def _validate_ai_recommendation(value: dict[str, Any], fallback: dict[str, Any], fallback_reasons: dict[str, str]) -> tuple[dict[str, Any], dict[str, str], str]:
    result = dict(fallback)
    reasons = dict(fallback_reasons)
    try:
        result["search_mode"] = _normalize_mode(value.get("search_mode", result["search_mode"]))
    except Exception:
        pass
    result["top_k"] = _clamp_top_k(value.get("top_k", result["top_k"]))
    result["similarity_threshold"] = _clamp_threshold(value.get("similarity_threshold", result["similarity_threshold"]))
    if "router_enabled" in value:
        result["router_enabled"] = bool(value["router_enabled"])
    if "reranking_enabled" in value:
        result["reranking_enabled"] = bool(value["reranking_enabled"])
    result["rerank_top_n"] = _clamp_rerank_top_n(value.get("rerank_top_n", result["rerank_top_n"]), result["top_k"])
    raw_reasons = value.get("reasons") if isinstance(value.get("reasons"), dict) else {}
    for key in ALLOWED_APPLY_KEYS:
        text = str(raw_reasons.get(key) or "").strip()
        if text:
            reasons[key] = text[:1000]
    summary = str(value.get("summary") or "").strip()[:2000]
    return result, reasons, summary


def _diff(current: dict[str, Any], recommended: dict[str, Any], reasons: dict[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in ("search_mode", "top_k", "similarity_threshold", "router_enabled", "reranking_enabled", "rerank_top_n"):
        rows.append({
            "key": key,
            "label": FIELD_LABELS[key],
            "current": current.get(key),
            "recommended": recommended.get(key),
            "changed": current.get(key) != recommended.get(key),
            "reason": reasons.get(key, ""),
        })
    return rows


async def evaluate_rag_settings(project_root: str) -> dict[str, Any]:
    root = _root(project_root)
    if not root:
        raise ValueError("RAG 설정 평가 전에 Agent 프로젝트 경로를 설정하세요.")
    current = await _current_config(root)
    options, logs = await asyncio.gather(retrieval_options(root), list_search_logs(root, 30))
    insight = _log_insights(logs)
    evaluation = _score_evaluation(current, options, insight)
    improvements: list[dict[str, Any]] = []
    if int(options.get("indexed_chunk_count") or 0) <= 0:
        improvements.append({"level": "WARN", "text": "Indexed Chunk가 없습니다. 먼저 2차 Indexing을 완료하세요."})
    if current["search_mode"] == "VECTOR" and insight["exact_query_ratio"] >= 0.25:
        improvements.append({"level": "INFO", "text": "정확 문자열형 질문 비율이 높습니다. Hybrid Search 또는 Retrieval Router를 권장합니다."})
    if insight["zero_result_rate"] >= 0.30:
        improvements.append({"level": "WARN", "text": "검색 결과 없음 비율이 높습니다. Threshold를 낮추거나 Hybrid Search를 사용하세요."})
    if not current["router_enabled"]:
        improvements.append({"level": "INFO", "text": "Retrieval Router를 켜면 질문 성격에 따라 검색 방식을 자동 선택할 수 있습니다."})
    if not current["reranking_enabled"] and int(options.get("indexed_chunk_count") or 0) >= 30:
        improvements.append({"level": "INFO", "text": "Corpus가 충분히 큽니다. Reranking을 켜서 최종 Context 순서를 개선하세요."})
    evaluation["improvements"] = improvements
    evaluation["current_config"] = current
    return evaluation


async def create_ai_recommendation(project_root: str) -> dict[str, Any]:
    root = _root(project_root)
    if not root:
        raise ValueError("AI RAG 추천 전에 Agent 프로젝트 경로를 설정하세요.")
    current = await _current_config(root)
    options, logs = await asyncio.gather(retrieval_options(root), list_search_logs(root, 30))
    insight = _log_insights(logs)
    evaluation = _score_evaluation(current, options, insight)
    baseline, baseline_reasons, warnings = _baseline_recommendation(current, options, insight)
    provider = "RULE_FALLBACK"
    summary = "현재 Index/검색 테스트 상태를 바탕으로 안전한 RAG 설정을 추천했습니다."
    recommended = dict(baseline)
    reasons = dict(baseline_reasons)

    prompt_payload = {
        "current": current,
        "corpus": {
            "indexed_source_count": options.get("indexed_source_count", 0),
            "indexed_chunk_count": options.get("indexed_chunk_count", 0),
            "embedding_count": options.get("embedding_count", 0),
            "document_types": options.get("document_types", []),
            "languages": options.get("languages", []),
        },
        "recent_test_summary": insight,
        "baseline": baseline,
    }
    system = (
        "당신은 THEANOVA AgentStudio RAG 설계 추천기입니다. 입력된 현재 설정, Indexed Corpus, 최근 Retrieval Test 요약만 근거로 판단하세요. "
        "추천 값은 search_mode(VECTOR/KEYWORD/HYBRID), top_k(1~50), similarity_threshold(0~1), router_enabled(boolean), "
        "reranking_enabled(boolean), rerank_top_n(1~50)만 제안하세요. 기존 설정을 무조건 바꾸지 말고 개선 근거가 없으면 유지하세요. "
        "출력은 설명 문장 없이 JSON 객체 하나만 반환하세요. keys: search_mode, top_k, similarity_threshold, router_enabled, "
        "reranking_enabled, rerank_top_n, reasons(각 key별 한국어 이유), summary."
    )
    human = json.dumps(prompt_payload, ensure_ascii=False, separators=(",", ":"))
    try:
        model = model_for_task(LLMTask.SIMPLE_QUESTION)
        response = await asyncio.wait_for(
            model.ainvoke([SystemMessage(content=system), HumanMessage(content=human)]),
            timeout=45.0,
        )
        parsed = _extract_json(str(getattr(response, "content", response) or ""))
        if parsed:
            recommended, reasons, ai_summary = _validate_ai_recommendation(parsed, baseline, baseline_reasons)
            summary = ai_summary or summary
            provider = str(getattr(model, "last_provider", "AI") or "AI").upper()
        else:
            warnings.append("AI 응답을 JSON으로 해석하지 못해 검증된 규칙 기반 추천을 사용했습니다.")
    except Exception as exc:
        warnings.append(f"AI Provider 추천 호출 실패로 규칙 기반 추천을 사용했습니다: {type(exc).__name__}: {exc}")

    diff = _diff(current, recommended, reasons)
    test_insights: list[str] = []
    if insight["test_count"]:
        test_insights.append(f"최근 Retrieval Test {insight['test_count']}건 · 결과 없음 {insight['zero_result_rate']*100:.0f}% · 평균 {insight['avg_duration_ms']}ms")
        if insight["exact_query_ratio"] >= 0.25:
            test_insights.append("최근 질문에 함수명/오류코드/파일명 등 정확 문자열 검색 신호가 자주 포함됩니다.")
    else:
        test_insights.append("아직 Retrieval Test 로그가 없어 Corpus/현재 설정 중심으로 추천했습니다.")

    pc_name = current_pc_name()
    async with SessionLocal() as session:
        row = RagRecommendationRun(
            pc_name=pc_name,
            project_root=root,
            provider=provider,
            status="COMPLETED",
            summary=summary,
            current_config=current,
            recommended_config=recommended,
            diff_json=diff,
            evaluation_json=evaluation,
            test_insights=test_insights,
            warnings=warnings,
            applied_keys=[],
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return _serialize_recommendation(row)


async def apply_ai_recommendation(recommendation_id: int, keys: list[str] | None = None, *, apply_all: bool = False) -> dict[str, Any]:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        recommendation = (await session.execute(select(RagRecommendationRun).where(
            RagRecommendationRun.id == int(recommendation_id),
            RagRecommendationRun.pc_name == pc_name,
        ))).scalar_one_or_none()
        if recommendation is None:
            raise LookupError("AI RAG 추천 결과를 찾을 수 없습니다.")
        recommended = dict(recommendation.recommended_config or {})
        requested = ALLOWED_APPLY_KEYS if apply_all else {str(key) for key in (keys or []) if str(key) in ALLOWED_APPLY_KEYS}
        if not requested:
            raise ValueError("적용할 추천 항목을 선택하세요.")

        retrieval = (await session.execute(select(RagRetrievalSetting).where(
            RagRetrievalSetting.pc_name == pc_name,
            RagRetrievalSetting.project_root == recommendation.project_root,
        ))).scalar_one_or_none()
        intelligence = (await session.execute(select(RagIntelligenceSetting).where(
            RagIntelligenceSetting.pc_name == pc_name,
            RagIntelligenceSetting.project_root == recommendation.project_root,
        ))).scalar_one_or_none()
        if retrieval is None:
            retrieval = RagRetrievalSetting(pc_name=pc_name, project_root=recommendation.project_root, metadata_filter=normalize_metadata_filter({}))
            session.add(retrieval)
        if intelligence is None:
            intelligence = RagIntelligenceSetting(pc_name=pc_name, project_root=recommendation.project_root, **DEFAULT_INTELLIGENCE)
            session.add(intelligence)

        if "search_mode" in requested:
            retrieval.search_mode = _normalize_mode(recommended.get("search_mode"))
        if "top_k" in requested:
            retrieval.top_k = _clamp_top_k(recommended.get("top_k"))
        if "similarity_threshold" in requested:
            retrieval.similarity_threshold = _clamp_threshold(recommended.get("similarity_threshold"))
        if "router_enabled" in requested:
            intelligence.router_enabled = bool(recommended.get("router_enabled"))
        if "reranking_enabled" in requested:
            intelligence.reranking_enabled = bool(recommended.get("reranking_enabled"))
        if "rerank_top_n" in requested:
            intelligence.rerank_top_n = _clamp_rerank_top_n(recommended.get("rerank_top_n"), _clamp_top_k(retrieval.top_k))

        now = datetime.utcnow()
        retrieval.updated_at = now
        intelligence.updated_at = now

        # Keep already-generated RAG Tools aligned with project-level Retrieval
        # changes so Agent Test/Workflow execution uses the applied Intelligence
        # recommendation immediately. Collection-specific Metadata remains intact.
        tool_rows = (await session.execute(select(RagAgentTool).where(
            RagAgentTool.pc_name == pc_name,
            RagAgentTool.project_root == recommendation.project_root,
            RagAgentTool.is_active.is_(True),
        ))).scalars().all()
        for tool_row in tool_rows:
            if "search_mode" in requested:
                tool_row.search_mode = retrieval.search_mode
            if "top_k" in requested:
                tool_row.top_k = retrieval.top_k
            if "similarity_threshold" in requested:
                tool_row.similarity_threshold = retrieval.similarity_threshold
            tool_row.updated_at = now

        recommendation.applied_keys = sorted(requested)
        recommendation.applied_at = now
        await session.commit()
        await session.refresh(retrieval)
        await session.refresh(intelligence)
        await session.refresh(recommendation)
        return {
            "ok": True,
            "applied_keys": sorted(requested),
            "retrieval_setting": {
                "id": retrieval.id,
                "pc_name": retrieval.pc_name,
                "project_root": retrieval.project_root,
                "search_mode": retrieval.search_mode,
                "top_k": retrieval.top_k,
                "similarity_threshold": retrieval.similarity_threshold,
                "metadata_filter": normalize_metadata_filter(retrieval.metadata_filter),
                "created_at": retrieval.created_at.isoformat() if retrieval.created_at else None,
                "updated_at": retrieval.updated_at.isoformat() if retrieval.updated_at else None,
            },
            "intelligence_setting": _serialize_intelligence(intelligence),
            "recommendation": _serialize_recommendation(recommendation),
            "updated_tool_count": len(tool_rows),
        }


async def list_recommendations(project_root: str = "", limit: int = 10) -> list[dict[str, Any]]:
    pc_name = current_pc_name()
    root = _root(project_root)
    limit = max(1, min(int(limit), 50))
    async with SessionLocal() as session:
        stmt = select(RagRecommendationRun).where(RagRecommendationRun.pc_name == pc_name)
        if root:
            stmt = stmt.where(RagRecommendationRun.project_root == root)
        rows = (await session.execute(stmt.order_by(RagRecommendationRun.id.desc()).limit(limit))).scalars().all()
        return [_serialize_recommendation(row) for row in rows]
