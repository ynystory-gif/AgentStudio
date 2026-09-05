from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any


def _text(*values: Any) -> str:
    parts: list[str] = []
    for value in values:
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, dict):
            for key, item in value.items():
                parts.append(str(key))
                parts.append(_text(item))
        elif isinstance(value, (list, tuple, set)):
            for item in value:
                parts.append(_text(item))
        elif value is not None:
            parts.append(str(value))
    return "\n".join(part for part in parts if part).casefold()


def _contains(text: str, *keywords: str) -> bool:
    return any(keyword.casefold() in text for keyword in keywords)


def _stage(
    stage_id: str,
    order: int,
    title: str,
    goal: str,
    topics: list[str],
    deliverables: list[str],
    validation: list[str],
    depends_on: list[str] | None = None,
) -> dict:
    return {
        "id": stage_id,
        "order": order,
        "title": title,
        "goal": goal,
        "requirement_topics": topics,
        "deliverables": deliverables,
        "validation": validation,
        "depends_on": list(depends_on or []),
        "status": "RECOMMENDED",
    }


def recommend_development_stage_plan(
    request: str,
    interview_messages: list[dict] | None = None,
    confirmed_requirements: dict | None = None,
    attachment_memory: str = "",
) -> dict:
    """Recommend a bounded implementation-stage plan without another LLM call.

    The planner deliberately separates *development stages* from the target
    Agent runtime workflow.  It uses the collected requirement context to keep
    large builds incremental, reviewable and resumable.  The recommendation is
    not authoritative until the user explicitly approves it.
    """
    confirmed = confirmed_requirements if isinstance(confirmed_requirements, dict) else {}
    text = _text(request, interview_messages or [], confirmed, attachment_memory)

    rag = _contains(text, "rag", "retrieval", "pgvector", "vector search", "bm25", "reranker", "embedding", "문서 검색")
    documents = _contains(text, "pdf", "docx", "pptx", "xlsx", "document", "문서", "parser", "chunk", "색인", "index")
    incremental = _contains(text, "증분", "reindex", "재색인", "hash", "변경 파일", "삭제 파일")
    security = _contains(text, "security", "보안", "acl", "permission", "권한", "restricted", "no_index", "sensitive", "민감", "redact", "secret")
    performance = _contains(text, "benchmark", "성능", "p50", "p95", "throughput", "mb/s", "chunks/s", "gpu", "cpu", "병목")
    quality = _contains(text, "golden", "quality", "품질", "hallucination", "정답", "평가", "테스트 dataset")
    ui = _contains(text, "react", "typescript", "frontend", "사용자 화면", "관리자 화면", "ui")
    database = _contains(text, "postgresql", "database", "db", "redis", "pgvector", "vector db")
    auth = _contains(text, "로그인", "인증", "auth", "rbac", "사용자 권한", "role")
    mcp = _contains(text, "mcp", "tool registry", "tool")
    deployment = _contains(text, "docker", "배포", "deployment", "운영", "on-premise", "온프레미스")

    signals = [rag, documents, incremental, security, performance, quality, ui, database, auth, mcp, deployment]
    signal_count = sum(1 for value in signals if value)
    long_requirement = len(text) >= 5000
    very_long_requirement = len(text) >= 12000

    reasons: list[str] = []
    if long_requirement:
        reasons.append("요구사항 범위와 설명량이 커 단일 생성보다 단계 분리가 안전합니다.")
    if rag and documents:
        reasons.append("RAG 검색과 문서 수집/색인은 실패 원인과 성능 특성이 달라 분리하는 편이 좋습니다.")
    if security:
        reasons.append("권한·민감정보·검색 차단/완전 제거는 별도 보안 검증 단계가 필요합니다.")
    if performance or quality:
        reasons.append("Benchmark/품질 평가는 기능 구현 후 실제 데이터로 검증해야 합니다.")
    if not reasons:
        reasons.append("기능 의존성과 테스트 경계를 기준으로 증분 구현 단계를 추천했습니다.")

    stages: list[dict] = []

    # Development-team RAG is intentionally grouped into four major stages.
    # This is the best balance between keeping each build bounded and avoiding
    # too much orchestration overhead.
    if rag and documents and (security or performance or quality or incremental):
        stages = [
            _stage(
                "STAGE_1_CORE_RAG",
                1,
                "Core RAG 검색 · 질문",
                "사용자가 하나의 자연어 입력창에서 문서 검색과 문서 기반 질문을 사용할 수 있는 핵심 경로를 먼저 완성합니다.",
                ["Intent Router", "Hybrid Search", "Reranker", "Context Builder", "출처 표시", "사용자 검색 UI"],
                ["DOCUMENT_SEARCH", "QUESTION_ANSWER", "DOCUMENT_OPEN/SUMMARY 기본 경로", "React 검색 화면", "FastAPI 검색 API"],
                ["문서 검색 결과 반환", "질문 답변에 근거 문서 표시", "근거 부족 시 생성 억제"],
            ),
            _stage(
                "STAGE_2_DOCUMENT_INDEX",
                2,
                "문서 관리 · 증분 색인",
                "대량 개발 문서를 안정적으로 수집하고 신규/변경/삭제 파일을 전체 재색인 없이 운영할 수 있게 합니다.",
                ["Parser Registry", "Document Metadata", "Chunking", "Embedding", "Hash", "INDEX/SKIP/REINDEX/REMOVE"],
                ["문서 Registry", "확장형 Parser", "pgvector/BM25 색인", "증분 색인", "실패 재처리"],
                ["동일 파일 SKIP", "변경 파일 REINDEX", "삭제 파일 파생 Index 제거", "document_id 추적"],
                ["STAGE_1_CORE_RAG"],
            ),
            _stage(
                "STAGE_3_SECURITY",
                3,
                "보안 · 권한 · 민감정보",
                "권한 없는 문서가 검색/문서명/LLM Context에 노출되지 않도록 검색 전 보안 경계를 완성합니다.",
                ["PUBLIC/INTERNAL/RESTRICTED/NO_INDEX", "ACL", "Sensitive Scanner", "BLOCKED", "PURGE"],
                ["검색 전 Permission Filter", "NO_INDEX", "Masking/Redaction", "검색 제외", "완전 제거 + Audit"],
                ["권한 없는 문서 0 노출", "BLOCKED 검색 0건", "PURGE 후 Vector/BM25/Cache/Search 0건"],
                ["STAGE_2_DOCUMENT_INDEX"],
            ),
            _stage(
                "STAGE_4_PERFORMANCE_QUALITY",
                4,
                "성능 · 품질 · 통합 검증",
                "실제 운영 규모를 가정해 처리량과 검색 품질을 측정하고 전체 Agent의 완료 조건을 검증합니다.",
                ["Benchmark", "P50/P95", "Golden Dataset", "Hallucination", "통합 테스트"],
                ["1GB/10GB Benchmark", "성능 Dashboard", "Golden/Test Dataset", "통합 Acceptance Test"],
                ["색인/검색 성능 지표 기록", "정답 문서 포함 여부", "답변 정확도", "Stage 1~4 회귀 테스트"],
                ["STAGE_3_SECURITY"],
            ),
        ]
    else:
        # General adaptive planner: 2..6 stages.
        stages.append(_stage(
            "STAGE_1_CORE",
            1,
            "핵심 기능",
            "가장 중요한 사용자 시나리오를 먼저 실행 가능한 상태로 만듭니다.",
            ["핵심 Use Case", "Backend", "Agent Workflow"],
            ["핵심 API/Workflow", "최소 실행 UI 또는 인터페이스"],
            ["핵심 시나리오 실행", "기본 오류 처리"],
        ))
        order = 2
        if documents or incremental or database:
            stages.append(_stage(
                f"STAGE_{order}_DATA",
                order,
                "데이터 · 저장 · 색인",
                "데이터 수집·저장·검색/색인 계층을 핵심 기능과 분리해 안정화합니다.",
                ["DB", "문서/파일", "Index", "Cache"],
                ["데이터 Schema", "Repository/Index", "증분 처리"],
                ["CRUD/색인 무결성", "재실행 안전성"],
                [stages[-1]["id"]],
            ))
            order += 1
        if security or auth:
            stages.append(_stage(
                f"STAGE_{order}_SECURITY",
                order,
                "보안 · 권한",
                "인증·권한·민감정보 경계를 별도 단계에서 검증합니다.",
                ["Auth", "Permission", "Sensitive Data"],
                ["권한 Filter", "보안 Validator", "Audit"],
                ["허용/거부 경로 검증", "민감정보 비노출"],
                [stages[-1]["id"]],
            ))
            order += 1
        if ui or mcp or deployment:
            stages.append(_stage(
                f"STAGE_{order}_INTEGRATION",
                order,
                "UI · Tool · 실행 통합",
                "사용자 화면과 외부 Tool/MCP/실행 환경을 통합합니다.",
                ["Frontend", "Tool/MCP", "Runtime"],
                ["UI 연결", "Tool 연동", "실행 환경"],
                ["End-to-End 실행", "상태/오류 표시"],
                [stages[-1]["id"]],
            ))
            order += 1
        if performance or quality or very_long_requirement:
            stages.append(_stage(
                f"STAGE_{order}_QUALITY",
                order,
                "성능 · 품질",
                "성능과 품질 지표를 실제 실행 결과로 검증합니다.",
                ["Benchmark", "Regression", "Quality"],
                ["측정/평가 도구", "회귀 테스트"],
                ["성능 기준", "품질 기준", "최종 회귀"],
                [stages[-1]["id"]],
            ))

        # Always end with a bounded verification stage when the plan would be too small.
        if len(stages) < 2:
            stages.append(_stage(
                "STAGE_2_VERIFY",
                2,
                "통합 검증",
                "핵심 기능을 테스트하고 완료 조건을 확인합니다.",
                ["Test", "Validation"],
                ["통합 테스트", "완료 리포트"],
                ["회귀 테스트 PASS", "필수 산출물 확인"],
                ["STAGE_1_CORE"],
            ))

    stages = stages[:6]
    for index, stage in enumerate(stages, start=1):
        stage["order"] = index
        stage["status"] = "RECOMMENDED"

    score = min(100, 25 + signal_count * 6 + (20 if long_requirement else 0) + (10 if very_long_requirement else 0))
    level = "HIGH" if score >= 70 else "MEDIUM" if score >= 45 else "LOW"
    now = datetime.now(timezone.utc).isoformat()
    return {
        "version": 1,
        "source": "AUTO_DEVELOPMENT_STAGE_PLANNER",
        "status": "RECOMMENDED",
        "approval_required": True,
        "approved": False,
        "approved_at": "",
        "recommended_at": now,
        "recommended_stage_count": len(stages),
        "complexity": {
            "score": score,
            "level": level,
            "signals": {
                "rag": rag,
                "documents": documents,
                "incremental_index": incremental,
                "security": security,
                "performance": performance,
                "quality": quality,
                "ui": ui,
                "database": database,
                "auth": auth,
                "mcp": mcp,
                "deployment": deployment,
            },
        },
        "reason": " ".join(reasons),
        "stages": stages,
    }


def approve_development_stage_plan(plan: dict | None) -> dict:
    value = deepcopy(plan if isinstance(plan, dict) else {})
    stages = value.get("stages") if isinstance(value.get("stages"), list) else []
    if not stages:
        raise ValueError("승인할 개발 Stage가 없습니다.")
    if len(stages) > 8:
        raise ValueError("개발 Stage는 최대 8개까지 승인할 수 있습니다.")

    normalized: list[dict] = []
    seen: set[str] = set()
    for index, raw in enumerate(stages, start=1):
        if not isinstance(raw, dict):
            continue
        stage_id = str(raw.get("id") or f"STAGE_{index}").strip().upper().replace(" ", "_")
        if stage_id in seen:
            stage_id = f"{stage_id}_{index}"
        seen.add(stage_id)
        item = deepcopy(raw)
        item["id"] = stage_id
        item["order"] = index
        item["title"] = str(item.get("title") or f"Stage {index}").strip()
        item["goal"] = str(item.get("goal") or "").strip()
        item["status"] = "APPROVED"
        normalized.append(item)
    if not normalized:
        raise ValueError("유효한 개발 Stage가 없습니다.")

    value["stages"] = normalized
    value["recommended_stage_count"] = len(normalized)
    value["status"] = "APPROVED"
    value["approved"] = True
    value["approval_required"] = True
    value["approved_at"] = datetime.now(timezone.utc).isoformat()
    return value


def _score_stage_for_file(stage: dict, path: str, purpose: str) -> int:
    text = f"{path} {purpose}".casefold()
    topics = _text(stage.get("title"), stage.get("goal"), stage.get("requirement_topics"), stage.get("deliverables"))
    score = 0
    tokens = [token for token in topics.replace("/", " ").replace("·", " ").replace("_", " ").split() if len(token) >= 3]
    for token in tokens[:80]:
        if token in text:
            score += 3
    keyword_groups = {
        "security": ("security", "auth", "permission", "acl", "role", "redact", "secret", "credential"),
        "보안": ("security", "auth", "permission", "acl", "role", "redact", "secret", "credential"),
        "index": ("index", "parser", "document", "chunk", "embed", "vector", "repository", "ingest"),
        "색인": ("index", "parser", "document", "chunk", "embed", "vector", "repository", "ingest"),
        "rag": ("rag", "search", "retrieval", "rerank", "query", "answer"),
        "검색": ("rag", "search", "retrieval", "rerank", "query", "answer"),
        "performance": ("benchmark", "metric", "performance", "monitor", "eval", "quality", "test"),
        "성능": ("benchmark", "metric", "performance", "monitor", "eval", "quality", "test"),
        "품질": ("benchmark", "metric", "performance", "monitor", "eval", "quality", "test"),
        "ui": ("frontend", "react", "tsx", "component", "page", "view", "ui"),
    }
    for marker, file_tokens in keyword_groups.items():
        if marker in topics and any(token in text for token in file_tokens):
            score += 8
    return score


def apply_development_stage_plan_to_design(design: dict, plan: dict | None) -> dict:
    """Attach an approved stage workflow and assign planned files to stages."""
    result = deepcopy(design if isinstance(design, dict) else {})
    approved = approve_development_stage_plan(plan) if isinstance(plan, dict) and plan.get("approved") else None
    if not approved:
        return result

    stages = approved["stages"]
    file_plan = result.get("file_plan") if isinstance(result.get("file_plan"), dict) else {}
    rows = file_plan.get("new_files") if isinstance(file_plan.get("new_files"), list) else []
    stage_file_counts = {stage["id"]: 0 for stage in stages}
    assigned_rows: list[Any] = []
    for raw in rows:
        if not isinstance(raw, dict):
            assigned_rows.append(raw)
            continue
        item = deepcopy(raw)
        path = str(item.get("path") or "")
        purpose = str(item.get("purpose") or item.get("description") or "")
        scored = [(max(0, _score_stage_for_file(stage, path, purpose)), stage) for stage in stages]
        scored.sort(key=lambda pair: (-pair[0], int(pair[1].get("order") or 0)))
        chosen = scored[0][1] if scored else stages[0]
        if scored and scored[0][0] <= 0:
            chosen = stages[0]
        item["development_stage_id"] = chosen["id"]
        item["development_stage_order"] = chosen["order"]
        stage_file_counts[chosen["id"]] = stage_file_counts.get(chosen["id"], 0) + 1
        assigned_rows.append(item)
    file_plan["new_files"] = assigned_rows
    result["file_plan"] = file_plan

    development_stages: list[dict] = []
    for stage in stages:
        stage_copy = deepcopy(stage)
        stage_copy["planned_file_count"] = stage_file_counts.get(stage["id"], 0)
        stage_copy["checkpoint_after_stage"] = True
        stage_copy["test_after_stage"] = True
        development_stages.append(stage_copy)

    development_workflow = {
        "name": "Agent Development Stage Workflow",
        "approval": "USER_APPROVED",
        "stage_count": len(development_stages),
        "stages": development_stages,
        "execution_policy": {
            "sequential": True,
            "checkpoint_each_stage": True,
            "test_each_stage": True,
            "stop_on_stage_failure": True,
            "resume_from_failed_stage": True,
            "preserve_completed_stages": True,
        },
    }
    result["development_stage_plan"] = approved
    result["development_workflow"] = development_workflow
    runtime = result.setdefault("design_runtime", {})
    runtime["development_stage_plan_source"] = approved.get("source") or "AUTO_DEVELOPMENT_STAGE_PLANNER"
    runtime["development_stage_count"] = len(development_stages)
    runtime["development_stage_approved"] = True
    return result
