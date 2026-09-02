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
        "index", "indexing", "색인", "재색인", "checksum", "document_id", "chunk_id",
    )):
        tags.update({"rag", "indexing", "retrieval", "data_pipeline"})

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
