from __future__ import annotations

from app.services.coding_rule_priority import resolve_rule_conflicts

from app.services.coding_style_registry import (
    format_rules_for_prompt,
    select_rules,
)


def infer_coding_tags(
    request: str,
    path: str = "",
    project_scope: bool = False,
) -> list[str]:
    text = f"{request} {path}".casefold()

    tags = {"all"}

    if path.lower().endswith(".py") or "python" in text or "파이썬" in text:
        tags.add("python")

    if path.lower().endswith(".ipynb") or "notebook" in text or "노트북" in text:
        tags.update({"python", "notebook", "data_pipeline"})

    if any(token in text for token in (
        "rag", "retrieval", "문서 로딩", "문서로딩", "document loader",
        "pypdf", "pymupdf", "pdfplumber", "easyocr", "ocr", ".pdf",
        ".csv", ".json", "csvloader", "jsonloader", "webbaseloader",
    )):
        tags.update({"rag", "data_pipeline", "document_loader", "retrieval"})

    if any(token in text for token in (
        "pii", "개인정보", "개인 정보", "민감정보", "민감 정보", "privacy",
        "마스킹", "masking", "redact", "redaction", "비식별", "익명화",
        "주민등록번호", "주민번호", "전화번호", "연락처", "계좌번호",
        "sanitize", "sanitization", "개인정보 보호", "privacy boundary",
    )):
        tags.update({"privacy", "pii", "security", "sanitization", "data_pipeline", "audit", "testing"})

    if any(token in text for token in (
        "ocr", "easyocr", "paddleocr", "paddlepaddle", "tesseract",
        "doclayout", "opencv", "cuda", "nvidia-smi", "gpu",
    )):
        tags.update({"ocr", "environment", "gpu", "quality_fallback", "data_pipeline"})

    if any(token in text for token in (
        "fallback", "대체 경로", "대체경로", "품질 기준", "quality gate",
    )):
        tags.update({"quality_fallback", "reliability"})

    if any(token in text for token in (
        "vectorstore", "vector store", "벡터 저장소", "벡터스토어", "chroma",
        "embedding", "임베딩", "retriever", "검색", "top-k", "top_k",
        "chunk_size", "chunk overlap", "chunk_overlap", "청크",
    )):
        tags.update({"rag", "retrieval", "vectorstore", "embedding", "data_pipeline"})

    if any(token in text for token in (
        "chunking", "청킹", "textsplitter", "text splitter",
        "charactertextsplitter", "recursivecharactertextsplitter",
        "tokentextsplitter", "chunk_size", "chunk_overlap", "separator",
        "start_index", "markdownheadertextsplitter",
    )):
        tags.update({"rag", "chunking", "retrieval", "document_loader", "data_pipeline"})

    if any(token in text for token in (
        "semantic chunk", "semantic_chunk", "semanticchunk", "의미 기반 청킹",
        "의미기반 청킹", "cosine similarity", "코사인 유사도",
    )):
        tags.update({"rag", "chunking", "semantic_chunking", "embedding", "evaluation"})

    if any(token in text for token in (
        "한국어", "korean", "한글",
    )) and "chunking" in tags:
        tags.add("korean_text")

    if any(token in text for token in (
        "token splitter", "tokentextsplitter", "tiktoken", "tokenizer", "토크나이저",
    )):
        tags.update({"tokenization", "context_budget"})

    if any(token in text for token in (
        "chunk evaluation", "청킹 평가", "청크 평가", "전략 비교",
        "chunk_count", "average token", "max token",
    )):
        tags.update({"rag", "chunking", "evaluation", "testing"})

    if any(token in text for token in (
        "document type", "document_type", "문서 유형", "문서 분류", "문서 자동 분류",
        "knowledge base", "knowledgebase", "지식베이스", "mixed document", "mixed",
        "section classification", "section-level", "문서 종류", "파일 유형",
    )) and "rag" in tags:
        tags.update({"document_detection", "classification", "metadata", "quality_gate"})

    if any(token in text for token in (
        "source code", "소스코드", "ast", "symbol chunk", "class/function",
        "function/method", "코드 검색", ".tsx", ".ts", ".py", ".cs", ".java",
    )) and "rag" in tags:
        tags.update({"document_detection", "code_chunking"})

    if any(token in text for token in (
        "csv", "xlsx", "xls", "table", "표", "json", "jsonl", "structured data", "구조화 데이터",
    )) and "rag" in tags:
        tags.update({"document_detection", "structured_data"})

    if "notebook" in tags and "rag" in tags:
        tags.add("document_detection")

    if any(token in text for token in (
        "mixed", "혼합 문서", "혼합문서", "section별", "section 단위", "섹션별", "섹션 단위",
    )) and "rag" in tags:
        tags.update({"document_detection", "mixed_document"})

    if any(token in text for token in (
        "index", "indexing", "색인", "재색인", "checksum", "document_id", "chunk_id",
    )):
        tags.update({"rag", "indexing", "retrieval", "data_pipeline"})

    if any(token in text for token in (
        "parent-child", "parent child", "parent_child", "parent chunk", "child chunk",
        "부모 청크", "자식 청크", "부모-자식",
    )) and "rag" in tags:
        tags.update({"parent_child_chunking", "context_expansion"})

    if any(token in text for token in (
        "hybrid chunk", "hybrid_chunk", "hybrid chunking", "하이브리드 청킹",
        "구조 + 의미", "structure-aware", "semantic-aware",
    )) and "rag" in tags:
        tags.add("hybrid_chunking")

    if any(token in text for token in (
        "chunk validation", "청크 검증", "청킹 검증", "빈 chunk", "빈 청크",
        "문장 중간", "함수 중간 절단",
    )) and "rag" in tags:
        tags.add("validation")

    if any(token in text for token in (
        "증분 재색인", "incremental reindex", "incremental indexing", "부분 재색인",
        "section hash", "chunk hash", "content hash",
    )) and "rag" in tags:
        tags.update({"incremental_indexing", "indexing"})

    if any(token in text for token in (
        "chunk version", "chunk_version", "청크 버전", "rollback", "롤백",
    )) and "rag" in tags:
        tags.update({"chunk_versioning", "indexing"})

    if any(token in text for token in (
        "context expansion", "컨텍스트 확장", "문맥 확장", "앞뒤 chunk", "앞뒤 청크",
        "dedup", "deduplicate", "중복 chunk", "중복 청크",
    )) and "rag" in tags:
        tags.update({"context_expansion", "deduplication"})

    if any(token in text for token in (
        "auto tune", "auto-tune", "autotune", "자동 튜닝", "최적 전략",
        "recall@k", "precision@k", "mrr", "hit rate",
    )) and "rag" in tags:
        tags.update({"auto_tuning", "evaluation", "testing"})

    if any(token in text for token in (
        "chunk preview", "청크 미리보기", "청킹 미리보기", "색인 전 미리보기",
    )) and "rag" in tags:
        tags.update({"chunk_preview", "rag_ui"})

    if any(token in text for token in (
        "request analyzer", "request analysis", "요청 분석", "질문 분석", "capability router",
        "capability routing", "intent classification", "의도 분류",
    )):
        tags.update({"request_analysis", "capability_routing", "llm_app", "agent"})

    if any(token in text for token in (
        "query analysis", "rag query analyzer", "query analyzer", "질의 분석", "검색 질문 분석",
        "query rewrite", "검색어 보정", "search plan", "검색 계획",
    )):
        tags.update({"rag", "query_analysis", "query_rewrite", "retrieval"})

    if any(token in text for token in (
        "conversation rewrite", "standalone question", "standalone query", "독립 질문", "후속 질문",
        "이전 대화", "대화형 rag",
    )) and "rag" in tags:
        tags.update({"conversation_rewrite", "memory", "query_rewrite"})

    if any(token in text for token in (
        "exact search", "exact query", "정확 검색", "고유 식별자", "문서 id", "상품 코드",
        "semantic search", "filter search", "comparison", "multi-hop", "multi hop", "summary search",
        "search type", "검색 유형",
    )) and "rag" in tags:
        tags.update({"search_type", "retrieval"})

    if any(token in text for token in (
        "multi query", "multi-query", "멀티 쿼리", "복수 query", "복수 쿼리",
    )) and "rag" in tags:
        tags.update({"multi_query", "semantic_search"})

    if any(token in text for token in (
        "permission filter", "permission", "권한 필터", "접근 권한", "security scope", "document acl",
    )) and "rag" in tags:
        tags.update({"permission_filter", "security", "metadata"})

    if any(token in text for token in (
        "multi-hop", "multi hop", "멀티홉", "다단계 검색", "의존 검색",
    )) and "rag" in tags:
        tags.update({"multi_hop", "workflow", "planning"})

    if any(token in text for token in (
        "metadata filter", "metadata schema", "메타데이터 필터", "메타데이터 스키마",
        "hard filter", "soft condition", "canonical metadata", "canonical registry",
    )):
        tags.update({"rag", "metadata", "retrieval", "validation"})

    if any(token in text for token in (
        "relative date", "작년", "지난달", "이번 분기", "최근", "date resolver",
    )) and "rag" in tags:
        tags.update({"metadata", "date", "query_analysis"})

    if any(token in text for token in (
        "neutral filter", "filter adapter", "pgvector filter", "chroma filter",
        "qdrant filter", "pinecone filter", "vector store adapter",
    )) and "rag" in tags:
        tags.update({"metadata", "vectorstore", "architecture"})

    if any(token in text for token in (
        "fail-closed", "fail closed", "security metadata", "보안 메타데이터",
        "tenant_id", "allowed_roles", "allowed_users", "visibility", "security_level",
    )) and "rag" in tags:
        tags.update({"security", "permission_filter", "metadata"})

    if any(token in text for token in (
        "filter relaxation", "필터 완화", "0개", "검색 결과 없음",
    )) and "rag" in tags:
        tags.update({"metadata", "fallback", "retrieval", "security"})

    if any(token in text for token in (
        "metadata profile", "메타데이터 프로필", "metadata recommendation", "metadata 추천",
    )):
        tags.update({"agent_creator", "rag", "metadata", "recommendation"})

    if any(token in text for token in (
        "hybrid search", "하이브리드 검색", "vector search", "벡터 검색",
        "bm25", "keyword search", "키워드 검색",
    )):
        tags.update({"rag", "hybrid_search", "vector_search", "bm25", "retrieval"})

    if any(token in text for token in (
        "rrf", "reciprocal rank fusion", "weighted fusion", "result fusion", "검색 결과 결합",
    )) and "rag" in tags:
        tags.update({"fusion", "rrf"})

    if any(token in text for token in (
        "deduplicate", "dedup", "중복 제거", "중복 chunk",
    )) and "rag" in tags:
        tags.update({"deduplicate", "retrieval", "observability"})

    if any(token in text for token in (
        "reranker", "rerank", "리랭커", "재정렬",
    )) and "rag" in tags:
        tags.update({"reranking", "context"})

    if any(token in text for token in (
        "bm25 tokenizer", "korean tokenizer", "한국어 tokenizer", "한국어 토크나이저",
        "형태소", "synonym registry", "동의어 사전", "keyword normalization",
    )) and "rag" in tags:
        tags.update({"bm25", "tokenizer", "normalization"})

    if any(token in text for token in (
        "search debug", "검색 debug", "검색 디버그", "retrieval trace", "검색 추적",
    )) and "rag" in tags:
        tags.update({"debug", "observability", "agent_editor"})

    if any(token in text for token in (
        "vector only", "hybrid rag", "advanced hybrid", "search preset", "검색 preset", "검색 프리셋",
    )):
        tags.update({"rag", "recommendation", "configuration", "agent_creator"})

    if any(token in text for token in (
        "candidate document", "candidate list", "후보 문서", "검색 결과 ui", "rag 결과 ui",
        "final context", "최종 context", "최종 컨텍스트",
    )):
        tags.update({"rag", "candidate_ui", "retrieval", "context"})

    if any(token in text for token in (
        "document grouping", "문서 단위 그룹", "chunk 펼치기", "chunk group", "문서 그룹",
    )) and "rag" in tags:
        tags.update({"candidate_ui", "document_grouping", "retrieval"})

    if any(token in text for token in (
        "검색 근거", "search evidence", "why selected", "선택 이유", "explain retrieval",
    )) and "rag" in tags:
        tags.update({"candidate_ui", "explainability", "observability"})

    if any(token in text for token in (
        "pipeline summary", "검색 pipeline", "후보 수", "candidate count",
    )) and "rag" in tags:
        tags.update({"debug", "pipeline_summary", "observability"})

    if any(token in text for token in (
        "result view filter", "결과 보기 필터", "검색 결과 필터",
    )) and "rag" in tags:
        tags.update({"candidate_ui", "filter", "metadata"})

    if any(token in text for token in (
        "max_chunks_per_document", "document diversity", "문서 다양성",
        "near duplicate", "near-duplicate", "유사 chunk", "유사 청크",
    )) and "rag" in tags:
        tags.update({"retrieval", "diversity", "deduplicate", "candidate_ui"})

    if any(token in text for token in (
        "원문 열기", "source navigation", "page highlight", "line highlight",
    )) and "rag" in tags:
        tags.update({"candidate_ui", "source_navigation", "agent_editor"})

    if any(token in text for token in (
        "검색 latency", "search latency", "reranker latency", "vector latency", "bm25 latency",
    )) and "rag" in tags:
        tags.update({"debug", "latency", "performance", "observability"})

    if any(token in text for token in (
        "structured response", "structured json", "구조화 응답", "응답 schema", "response schema",
        "dynamic renderer", "동적 renderer", "동적 렌더러",
    )):
        tags.update({"response", "structured_response", "renderer", "schema"})

    if any(token in text for token in (
        "response planner", "응답 planner", "응답 플래너", "presentation resolver",
    )):
        tags.update({"response", "response_planner", "presentation", "routing"})

    if any(token in text for token in (
        "renderer registry", "renderer allowlist", "렌더러 registry", "렌더러 레지스트리",
        "fallback renderer", "responsive renderer",
    )):
        tags.update({"renderer", "registry", "fallback", "responsive"})

    if any(token in text for token in (
        "source reference", "source_ids", "출처 id", "출처 연결",
    )):
        tags.update({"response", "source", "validation", "grounding"})

    if any(token in text for token in (
        "action allowlist", "execute_tool", "open_source", "open_detail",
    )):
        tags.update({"response", "action", "security"})

    if any(token in text for token in (
        "structured evidence", "evidence json", "근거 json", "evidence context",
    )):
        tags.update({"rag", "response", "grounding", "context_builder"})

    if any(token in text for token in (
        "chat history json", "재렌더링", "rerender", "response version",
    )):
        tags.update({"response", "history", "versioning", "renderer"})

    if any(token in text for token in (
        "grounded", "근거", "출처", "abstain", "문서에 답이 없", "문서에서 찾을 수 없",
        "relevance", "관련도", "threshold", "score",
    )):
        tags.update({"rag", "retrieval", "grounding", "quality_gate"})

    if any(token in text for token in (
        "context budget", "token budget", "context window", "컨텍스트", "문맥",
    )):
        tags.update({"rag", "retrieval", "context_budget", "llm_app"})

    if any(token in text for token in (
        "prompt injection", "프롬프트 인젝션", "retrieved context", "검색 문서 지시",
        "문서 내 지시", "지시문",
    )):
        tags.update({"rag", "retrieval", "security", "prompt_injection"})

    if any(token in text for token in (
        "benchmark", "벤치마크", "성능 비교", "cpu/gpu", "cold start", "warm",
    )):
        tags.update({"benchmark", "performance", "testing"})

    if any(token in text for token in (
        "download", "다운로드", "huggingface", "모델 파일", "model file",
        "checksum", "revision",
    )):
        tags.update({"artifact", "external_io"})

    if any(token in text for token in ("requests", "httpx", "외부 api", "외부 연동", "web loader", "웹 로더")):
        tags.add("external_io")

    if "langchain" in text or "랭체인" in text:
        tags.update({"langchain", "llm_app", "agent"})

    if "langgraph" in text or "랭그래프" in text:
        tags.update({"agent", "langchain"})

    if "agent" in text or "에이전트" in text:
        tags.update({"agent", "llm_app"})

    if "fastapi" in text:
        tags.add("fastapi")

    if "mcp" in text:
        tags.update({"mcp", "agent"})

    if "openai" in text or "ollama" in text or "claude" in text:
        tags.update({"llm_app", "agent"})

    if (
        "prompt" in text
        or "프롬프트" in text
        or "rcif" in text
        or "chatprompttemplate" in text
    ):
        tags.update({"llm_app", "agent", "langchain", "prompt_template"})

    if "few-shot" in text or "few shot" in text or "fewshot" in text or "퓨샷" in text:
        tags.update({"few_shot", "classification", "llm_app", "langchain"})

    if "분류" in text or "classification" in text:
        tags.add("classification")

    if "lcel" in text or "runnable" in text or "pipeline" in text or "파이프라인" in text:
        tags.update({"langchain", "llm_app", "lcel"})

    if "pydantic" in text or "basemodel" in text or "structured_output" in text or "구조화 출력" in text:
        tags.update({"pydantic", "structured_output", "llm_app"})

    if "typeddict" in text or "langgraph state" in text or "state" in text:
        tags.update({"langgraph", "python"})

    if "parallel" in text or "병렬" in text:
        tags.update({"parallel", "langchain"})

    if "branch" in text or "분기" in text:
        tags.update({"branching", "langchain"})

    if (
        "tool" in text
        or "도구" in text
        or "function calling" in text
        or "function_calling" in text
        or "bind_tools" in text
        or "@tool" in text
    ):
        tags.update({
            "tool",
            "function_calling",
            "agent",
            "langchain",
        })

    if "mcp" in text:
        tags.update({"mcp", "tool", "agent"})

    if "api" in text or "외부 api" in text:
        tags.update({"api", "tool"})

    if "fastapi" in text:
        tags.update({"fastapi", "async", "production"})

    if "router" in text or "라우터" in text:
        tags.update({"fastapi", "router", "api"})

    if "service" in text or "서비스" in text:
        tags.update({"fastapi", "service"})

    if "schema" in text or "스키마" in text or "basemodel" in text:
        tags.update({"fastapi", "schema", "pydantic", "api"})

    if "rest" in text or "http" in text or "endpoint" in text or "엔드포인트" in text:
        tags.update({"fastapi", "api", "rest"})

    if "devcontainer" in text or "docker" in text:
        tags.update({"devcontainer", "docker", "team"})

    if "cors" in text:
        tags.update({"fastapi", "security", "cors"})

    if "uvicorn" in text:
        tags.update({"fastapi", "uvicorn"})

    if (
        "sse" in text
        or "streaming" in text
        or "stream" in text
        or "스트리밍" in text
        or "실시간" in text
        or "토큰 단위" in text
    ):
        tags.update({
            "streaming",
            "sse",
            "async",
            "fastapi",
        })

    if "httpx" in text:
        tags.update({"httpx", "streaming", "async"})

    if "websocket" in text:
        tags.update({"streaming", "websocket"})

    if "eventsource" in text or "readablestream" in text:
        tags.update({"streaming", "frontend", "browser"})

    if (
        "async" in text
        or "await" in text
        or "ainvoke" in text
        or "astream" in text
        or "abatch" in text
        or "비동기" in text
    ):
        tags.update({"async", "llm_app"})

    if "gather" in text or "동시" in text or "병렬" in text:
        tags.update({"async", "batch", "parallel"})

    if "semaphore" in text or "rate limit" in text or "429" in text:
        tags.update({"async", "batch", "production"})

    if "retry" in text or "재시도" in text or "backoff" in text:
        tags.update({"async", "retry", "production"})

    if project_scope:
        tags.update({"production", "agentstudio"})

    return sorted(tags)


def coding_rules_for_request(
    request: str,
    path: str = "",
    project_scope: bool = False,
) -> dict:
    tags = infer_coding_tags(
        request=request,
        path=path,
        project_scope=project_scope,
    )

    # required / recommended 규칙은 기본 적용,
    # conditional은 해당 태그가 맞을 때만 선택됩니다.
    selected = select_rules(
        tags=tags,
        levels=["required", "recommended", "conditional"],
    )

    resolved = resolve_rule_conflicts(selected)
    ordered_rules = resolved.get("rules") or []

    return {
        "tags": tags,
        "rules": ordered_rules,
        "prompt": format_rules_for_prompt(ordered_rules),
        "priority_scores": resolved.get("scores") or {},
    }
