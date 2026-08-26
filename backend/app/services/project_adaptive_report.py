from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from app.services.project_analyzer import scan_project


def _text(value: Any) -> str:
    return str(value or "").strip()


def _has(haystack: str, *needles: str) -> bool:
    h = haystack.casefold()
    return any(n.casefold() in h for n in needles)


def _unique(items: list[Any]) -> list[Any]:
    out: list[Any] = []
    seen: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            key = _text(item.get("label") or item.get("name") or item.get("component") or item)
        else:
            key = _text(item)
        norm = key.casefold()
        if key and norm not in seen:
            seen.add(norm)
            out.append(item)
    return out


def _entry(label: str, description: str, kind: str = "component") -> dict[str, str]:
    return {"label": label, "description": description, "type": kind}


def _step(label: str, description: str, kind: str = "process") -> dict[str, str]:
    return {"label": label, "description": description, "type": kind}


def _detect_test_command(names: set[str], haystack: str) -> str:
    if "pytest.ini" in names or "conftest.py" in names or _has(haystack, "pytest"):
        return "python -m pytest"
    if "package.json" in names:
        if _has(haystack, '"test"', "vitest", "jest"):
            return "npm test"
        return "npm run build"
    if "pyproject.toml" in names or "requirements.txt" in names:
        return "python -m compileall ."
    return "프로젝트별 실행/테스트 명령을 확인하세요."


def _detect_profile(files: list[dict[str, Any]], project_name: str, request: str = "") -> dict[str, Any]:
    names = {Path(_text(f.get("relative"))).name.casefold() for f in files}
    rels = [(_text(f.get("relative"))).replace("\\", "/") for f in files]
    languages = Counter(_text(f.get("language")) for f in files if _text(f.get("language")))
    previews = "\n".join(_text(f.get("preview"))[:5000] for f in files[:450])
    rel_hay = "\n".join(rels)
    haystack = f"{rel_hay}\n{previews}\n{request}".casefold()

    detected: list[str] = []
    components: list[dict[str, str]] = []
    interfaces: list[dict[str, str]] = []
    persistence: list[dict[str, str]] = []
    security: list[dict[str, str]] = []
    state: list[dict[str, str]] = []
    infrastructure: list[dict[str, str]] = []
    capabilities: list[dict[str, str]] = []
    tool_decisions: list[dict[str, str]] = []

    def mark(name: str) -> None:
        if name not in detected:
            detected.append(name)

    # Frontend / presentation layer
    if _has(haystack, "react", "react-dom", ".tsx", ".jsx"):
        mark("React")
        components.append(_entry("React Frontend", "사용자 화면과 클라이언트 상태를 담당", "frontend"))
        interfaces.append(_entry("Web UI", "브라우저 기반 사용자 인터페이스", "ui"))
    if _has(haystack, "vite", "vite.config"):
        mark("Vite")
    if _has(haystack, "streamlit"):
        mark("Streamlit")
        components.append(_entry("Streamlit UI", "데이터/AI 기능을 제공하는 웹 UI", "frontend"))
        interfaces.append(_entry("Streamlit Web UI", "사용자 입력과 결과 시각화", "ui"))
    if _has(haystack, "next/", "nextjs", '"next"'):
        mark("Next.js")
        components.append(_entry("Next.js Web App", "웹 UI 및 서버 렌더링 계층", "frontend"))
        interfaces.append(_entry("Web UI", "브라우저 클라이언트", "ui"))

    # Backend / API
    if _has(haystack, "fastapi", "from fastapi", "@app.get", "apirouter"):
        mark("FastAPI")
        components.append(_entry("FastAPI Backend", "HTTP API와 백엔드 서비스 진입점", "backend"))
        interfaces.append(_entry("REST API", "FastAPI HTTP endpoint", "api"))
    elif _has(haystack, "flask", "from flask"):
        mark("Flask")
        components.append(_entry("Flask Backend", "HTTP API와 서버 로직", "backend"))
        interfaces.append(_entry("REST API", "Flask HTTP endpoint", "api"))
    elif _has(haystack, "django", "django."):
        mark("Django")
        components.append(_entry("Django Backend", "웹/API 서버와 애플리케이션 로직", "backend"))
        interfaces.append(_entry("Web / API", "Django request interface", "api"))
    if _has(haystack, "express(", "from 'express'", 'require("express")', '"express"'):
        mark("Express")
        components.append(_entry("Node/Express Backend", "HTTP API와 서비스 로직", "backend"))
        interfaces.append(_entry("REST API", "Express HTTP endpoint", "api"))

    # Realtime
    if _has(haystack, "websocket", "websocketroute", "@app.websocket"):
        mark("WebSocket")
        interfaces.append(_entry("WebSocket", "실시간 양방향 통신", "realtime"))
    if _has(haystack, "eventsource", "text/event-stream", "server-sent", "sse"):
        mark("SSE")
        interfaces.append(_entry("SSE", "서버 이벤트 스트리밍", "realtime"))

    # Agent / LLM
    has_langgraph = _has(haystack, "langgraph", "stategraph")
    has_langchain = _has(haystack, "langchain")
    has_agent = has_langgraph or _has(
        haystack,
        "agentexecutor", "create_react_agent", "tool_call", "tools_condition",
        "agent.py", "/agents/", "agent_service", "agent_orchestrator", "agentgraph",
    )
    has_llm = _has(haystack, "openai", "ollama", "chatopenai", "chatollama", "ainvoke", ".invoke(", "llm")
    has_embedding = _has(haystack, "embedding", "embeddings", "text-embedding", "vectorstore")
    has_retrieval = _has(
        haystack,
        "retriever", "retrieval", "similarity_search", "vector_search",
        "semantic search", "rag_", "/rag/", "rag pipeline",
    )
    has_mcp = _has(haystack, "model context protocol", "mcpclient", "mcp_client", "mcp server", "mcp_server", "/mcp/")

    if has_langgraph:
        mark("LangGraph")
        components.append(_entry("LangGraph Orchestrator", "StateGraph 기반 Agent workflow와 상태 전이", "orchestrator"))
        state.append(_entry("LangGraph State", "노드 간 실행 상태와 중간 결과", "state"))
    elif has_agent:
        components.append(_entry("Agent Orchestrator", "요청 분석, 계획, 실행 결과 조정", "orchestrator"))
    if has_langchain:
        mark("LangChain")
        components.append(_entry("LangChain Layer", "LLM, prompt, tool 연결 계층", "ai"))
    if _has(haystack, "openai", "chatopenai"):
        mark("OpenAI")
        components.append(_entry("OpenAI LLM", "생성/추론 모델 호출", "llm"))
    if _has(haystack, "ollama", "chatollama"):
        mark("Ollama")
        components.append(_entry("Ollama Local LLM", "로컬 모델 실행", "llm"))
    if has_mcp:
        mark("MCP")
        components.append(_entry("MCP Integration", "MCP Client/Server 및 Tool 연동", "mcp"))
        interfaces.append(_entry("MCP", "Model Context Protocol 연결", "mcp"))
        tool_decisions.append({"capability": "MCP Integration", "execution_type": "mcp", "reason": "프로젝트 소스에서 MCP 사용 증거 감지"})
    if _has(haystack, "@tool", "structuredtool", "basetool", "tool("):
        components.append(_entry("Tool Layer", "Agent가 호출하는 로컬/외부 기능", "tool"))
        tool_decisions.append({"capability": "Local Tools", "execution_type": "tool", "reason": "프로젝트 소스에서 Tool 정의/호출 감지"})

    # Persistence / data services
    if _has(haystack, "psycopg", "postgresql", "postgres://", "pg_host", "pgpassword"):
        mark("PostgreSQL")
        persistence.append(_entry("PostgreSQL", "관계형 데이터 저장소", "database"))
    if _has(haystack, "pgvector", "vector(", "vector_cosine_ops"):
        mark("pgvector")
        persistence.append(_entry("pgvector", "Embedding / Vector 검색 저장소", "vector-db"))
    if _has(haystack, "redis", "redis_client", "from redis"):
        mark("Redis")
        persistence.append(_entry("Redis", "Cache / Session / Runtime state", "cache"))
        state.append(_entry("Redis Runtime State", "세션/캐시/단기 상태", "state"))
    if _has(haystack, "sqlite3", "sqlite://", ".sqlite", ".db"):
        mark("SQLite")
        persistence.append(_entry("SQLite", "로컬 관계형 데이터 저장소", "database"))
    if _has(haystack, "pyodbc", "sql server", "mssql"):
        mark("MSSQL")
        persistence.append(_entry("Microsoft SQL Server", "관계형 데이터 저장소", "database"))
    if _has(haystack, "oracledb", "cx_oracle", "oracle"):
        mark("Oracle")
        persistence.append(_entry("Oracle Database", "관계형 데이터 저장소", "database"))
    if _has(haystack, "firestore", "firebase_admin"):
        mark("Firestore")
        persistence.append(_entry("Google Cloud Firestore", "NoSQL Document 저장소", "document-db"))
    if _has(haystack, "supabase", "supabase.com"):
        mark("Supabase")
        persistence.append(_entry("Supabase", "Managed PostgreSQL / Backend service", "cloud-db"))

    # Security
    if _has(haystack, "oauth", "oauth2"):
        mark("OAuth")
        security.append(_entry("OAuth", "사용자/서비스 인증", "security"))
    if _has(haystack, "jwt", "bearer", "authorization"):
        mark("JWT/Bearer")
        security.append(_entry("JWT / Bearer Auth", "API 접근 토큰 검증", "security"))
    if _has(haystack, "api_key", "apikey", "secret_key", "dotenv", "load_dotenv"):
        security.append(_entry("Secret / Environment Config", "API Key와 비밀정보를 환경변수로 관리", "security"))

    # Infrastructure
    if "dockerfile" in names or "docker-compose.yml" in names or "docker-compose.yaml" in names or _has(haystack, "docker compose"):
        mark("Docker")
        infrastructure.append(_entry("Docker / Container", "컨테이너 기반 실행 환경", "container"))
    if _has(haystack, "kubernetes", "apiVersion: apps/v1", "kind: deployment", "k8s"):
        mark("Kubernetes")
        infrastructure.append(_entry("Kubernetes", "컨테이너 오케스트레이션", "cluster"))
    if _has(haystack, "aws_", "boto3", "amazonaws.com", "s3://"):
        mark("AWS")
        infrastructure.append(_entry("AWS Cloud", "클라우드 인프라/스토리지 연동", "cloud"))
    if _has(haystack, "google.cloud", "gcp", "storage.googleapis.com"):
        mark("GCP")
        infrastructure.append(_entry("Google Cloud", "클라우드 서비스 연동", "cloud"))
    if _has(haystack, "azure", "blob.core.windows.net"):
        mark("Azure")
        infrastructure.append(_entry("Microsoft Azure", "클라우드 서비스 연동", "cloud"))

    # Capabilities
    if interfaces:
        capabilities.append({"label": "User/API Interface", "description": "사용자 또는 외부 시스템 요청 처리"})
    if has_agent:
        capabilities.append({"label": "Agent Orchestration", "description": "LLM/Tool/State 기반 작업 오케스트레이션"})
    if has_retrieval or has_embedding:
        capabilities.append({"label": "RAG / Retrieval", "description": "Embedding과 검색 결과를 LLM context로 활용"})
    if has_mcp:
        capabilities.append({"label": "MCP Tool Integration", "description": "외부 MCP Server/Tool 연결"})
    if persistence:
        capabilities.append({"label": "Persistence", "description": "DB/Cache/Vector 저장소 사용"})
    if _has(haystack, "streamingresponse", "eventsource", "websocket", "text/event-stream"):
        capabilities.append({"label": "Realtime Streaming", "description": "WebSocket/SSE 기반 실시간 전달"})

    # Project nature
    if (has_retrieval or has_embedding) and has_llm:
        project_type = "RAG_AGENT"
        type_label = "RAG 기반 AI Agent"
    elif has_mcp and (has_agent or has_llm):
        project_type = "MCP_AGENT"
        type_label = "MCP 연동 AI Agent"
    elif has_agent or (has_llm and (has_langgraph or has_langchain)):
        project_type = "AI_AGENT"
        type_label = "AI Agent / LLM Application"
    elif _has(haystack, "streamlit"):
        project_type = "DATA_APP"
        type_label = "Streamlit Data/AI Application"
    elif any(x in detected for x in ("FastAPI", "Flask", "Django", "Express")):
        project_type = "WEB_API"
        type_label = "Web / API Application"
    elif persistence:
        project_type = "DATABASE_APP"
        type_label = "Database Application"
    else:
        project_type = "GENERAL"
        type_label = "General Software Project"

    # Workflow inferred from detected nature. No unobserved technology names are introduced.
    if project_type == "RAG_AGENT":
        steps = [
            _step("User Request", "질문 또는 작업 요청 수신", "input"),
            _step("Input / Intent Validation", "입력 형식과 요청 의도를 확인", "validation"),
            _step("Retrieval", "Vector/검색 저장소에서 관련 Context 조회", "retrieval"),
            _step("Context Assembly", "검색 결과와 대화 Context 구성", "context"),
            _step("LLM Generation", "Context를 기반으로 모델 응답 생성", "llm"),
            _step("Response", "결과 검증 후 사용자에게 반환", "output"),
        ]
    elif project_type == "MCP_AGENT":
        steps = [
            _step("Request", "사용자/클라이언트 요청 수신", "input"),
            _step("Intent / Schema Routing", "요청 의미와 필요한 데이터 구조 판단", "routing"),
            _step("Validation", "필수값/업무 규칙 검증", "validation"),
            _step("Agent Planning", "실행 계획과 사용할 Tool 결정", "planning"),
            _step("MCP / Tool Execution", "MCP Server 또는 Tool 호출", "tool"),
            _step("Result Synthesis", "Tool 결과와 LLM 결과를 결합", "llm"),
            _step("Response", "최종 결과 반환", "output"),
        ]
    elif project_type == "AI_AGENT":
        steps = [
            _step("Request", "사용자/시스템 요청 수신", "input"),
            _step("Intent / Requirement", "요청 의도와 요구사항 분석", "analysis"),
            _step("Validation", "입력 및 실행 조건 검증", "validation"),
            _step("Agent Orchestration", "Workflow/State 기반 작업 계획", "planning"),
            _step("LLM / Tool Execution", "모델 및 필요한 Tool 실행", "execution"),
            _step("Result Validation", "실행 결과 확인 및 오류 처리", "validation"),
            _step("Response", "최종 결과 반환", "output"),
        ]
    elif project_type == "DATA_APP":
        steps = [
            _step("User Input", "Streamlit 화면에서 조건/요청 입력", "input"),
            _step("Input Processing", "필터와 입력값 정규화", "validation"),
            _step("Service / Query", "비즈니스 로직과 데이터 조회 수행", "process"),
            _step("Cache / Persistence", "감지된 저장소를 조회/갱신", "database"),
            _step("Render Result", "표/차트/응답을 화면에 표시", "output"),
        ]
    elif project_type == "WEB_API":
        steps = [
            _step("Client Request", "웹/외부 클라이언트 요청 수신", "input"),
            _step("API Routing", "Endpoint와 Handler 선택", "routing"),
            _step("Validation", "Request 데이터 검증", "validation"),
            _step("Service Logic", "프로젝트 핵심 비즈니스 로직 수행", "process"),
        ]
        if persistence:
            steps.append(_step("Persistence", "감지된 DB/Cache와 데이터 처리", "database"))
        steps.append(_step("Response", "HTTP 결과 반환", "output"))
    elif project_type == "DATABASE_APP":
        steps = [
            _step("Input / Request", "조회/저장 요청 수신", "input"),
            _step("Validation", "조건과 데이터 검증", "validation"),
            _step("Query / Command", "DB Query 또는 Command 수행", "database"),
            _step("Transform", "조회 결과 가공", "process"),
            _step("Output", "결과 반환", "output"),
        ]
    else:
        steps = [
            _step("Input / Trigger", "프로그램 입력 또는 실행 Trigger", "input"),
            _step("Core Logic", "프로젝트 핵심 로직 수행", "process"),
            _step("Output", "처리 결과 반환/저장", "output"),
        ]

    branches: list[dict[str, str]] = []
    if _has(haystack, "if ", "match ", "router", "route"):
        branches.append({"label": "조건/라우팅 분기", "description": "소스에서 조건 분기 또는 Router 사용 증거 감지"})

    retry = ""
    if _has(haystack, "retry", "tenacity", "backoff"):
        retry = "Retry / Backoff 정책이 소스에서 감지되었습니다."

    components = _unique(components)
    interfaces = _unique(interfaces)
    persistence = _unique(persistence)
    security = _unique(security)
    state = _unique(state)
    infrastructure = _unique(infrastructure)
    capabilities = _unique(capabilities)
    tool_decisions = _unique(tool_decisions)

    # At least expose the actual source/runtime boundary without inventing frameworks.
    if not components:
        top_lang = languages.most_common(1)[0][0] if languages else "Application"
        components.append(_entry(f"{top_lang} Application Core", "프로젝트 소스에서 확인된 핵심 실행 계층", "application"))
    if not interfaces:
        interfaces.append(_entry("Program Entry Point", "파일/함수 기반 실행 진입점", "entry"))

    primary_tech = detected or [name for name, _ in languages.most_common(6)]
    top_langs = [name for name, _ in languages.most_common(8)]
    test_command = _detect_test_command(names, haystack)

    summary = (
        f"{project_name}: {type_label} 성격으로 분석되었습니다. "
        f"소스 {len(files)}개, 주요 기술 {', '.join(primary_tech[:8]) if primary_tech else '미확인'}를 기준으로 "
        "워크플로우·리포트·아키텍처를 프로젝트 맞춤형으로 구성합니다."
    )

    return {
        "project_name": project_name,
        "project_type": project_type,
        "project_type_label": type_label,
        "summary": summary,
        "tech_stack": primary_tech,
        "languages": top_langs,
        "source_file_count": len(files),
        "workflow": {
            "name": f"{project_name} · {type_label} Workflow",
            "steps": steps,
            "branches": branches,
            "retry": retry,
            "source": "PROJECT_SOURCE_INFERENCE",
        },
        "requirement_spec": {
            "goal": summary,
            "acceptance_criteria": [
                "현재 프로젝트 소스에서 감지한 기술과 연결 관계를 우선 사용",
                "감지되지 않은 DB/LLM/MCP/Cloud 기술을 임의로 표시하지 않음",
                "프로젝트 실행 결과가 존재하면 추론 정보보다 실제 결과를 우선 사용",
            ],
            "constraints": ["SOURCE_ONLY deterministic inference"],
        },
        "capability_plan": {"capabilities": capabilities},
        "tool_mcp_plan": {"decisions": tool_decisions},
        "architecture": {
            "components": components,
            "interfaces": interfaces,
            "persistence": persistence,
            "security": security,
            "state": state,
            "infrastructure": infrastructure,
            "source": "PROJECT_SOURCE_INFERENCE",
        },
        "execution_baseline": {
            "status": "PROJECT_LOADED",
            "test_command": test_command,
            "test_returncode": None,
            "message": "프로젝트 로드 완료 · 실제 실행 전 상태",
        },
        "analysis_report": {
            "findings": [
                f"프로젝트 유형: {type_label}",
                f"감지 기술: {', '.join(primary_tech[:10]) if primary_tech else '미확인'}",
                f"구성 요소 {len(components)} · 인터페이스 {len(interfaces)} · 영속성 {len(persistence)}",
            ],
            "source": "PROJECT_SOURCE_INFERENCE",
        },
        "infrastructure": infrastructure,
        "analysis_mode": "SOURCE_ONLY_ADAPTIVE",
        "llm_called": False,
    }


async def build_project_adaptive_report(root: str, request: str = "") -> dict[str, Any]:
    data = await scan_project(root)
    project_name = Path(data["root"]).name
    profile = _detect_profile(data.get("files") or [], project_name, request)
    return {"ok": True, "root": data["root"], **profile}
