from __future__ import annotations

from datetime import datetime

from app.core.config import get_settings
from app.services.model_router import LLMTask, provider_for


def _task_label(task: LLMTask) -> str:
    labels = {
        LLMTask.PROJECT_DISCOVERY: "프로젝트 탐색",
        LLMTask.TOOL_CLASSIFICATION: "도구 분류",
        LLMTask.LOG_TRIAGE: "로그 1차 진단",
        LLMTask.SIMPLE_QUESTION: "간단 질의 응답",
        LLMTask.MEMORY_ORGANIZATION: "메모리 정리",
        LLMTask.REQUIREMENTS_ANALYSIS: "요구사항 분석",
        LLMTask.CODE_GENERATION: "코드 생성",
        LLMTask.PATCH_GENERATION: "패치 생성",
        LLMTask.GENERAL_DEBUGGING: "일반 디버깅",
    }
    return labels.get(task, task.value)


def _task_group(task: LLMTask) -> str:
    if task in {
        LLMTask.PROJECT_DISCOVERY,
        LLMTask.TOOL_CLASSIFICATION,
        LLMTask.LOG_TRIAGE,
        LLMTask.SIMPLE_QUESTION,
        LLMTask.MEMORY_ORGANIZATION,
    }:
        return "Local / Lightweight"
    if task == LLMTask.REQUIREMENTS_ANALYSIS:
        return "Planning / Requirements"
    return "Coding / Debugging"


SYSTEM_SNIPPETS = {
    LLMTask.PROJECT_DISCOVERY: "프로젝트 파일 구조를 요약하고 핵심 진입점을 찾아라.",
    LLMTask.TOOL_CLASSIFICATION: "도구 이름/설명을 분석해 카테고리와 위험도를 분류하라.",
    LLMTask.LOG_TRIAGE: "에러 로그를 읽고 원인 후보와 다음 확인 포인트를 제시하라.",
    LLMTask.SIMPLE_QUESTION: "짧고 명확하게 사용자의 질문에 답하라.",
    LLMTask.MEMORY_ORGANIZATION: "최근 대화/메모를 정리하고 기억 후보를 구조화하라.",
    LLMTask.REQUIREMENTS_ANALYSIS: "사용자 요구사항을 구현 가능한 Agent 설계 JSON으로 바꿔라.",
    LLMTask.CODE_GENERATION: "기존 파일과 요구사항을 바탕으로 실제 동작하는 코드를 생성하라.",
    LLMTask.PATCH_GENERATION: "기존 코드와 지시사항을 바탕으로 최소 수정 패치를 생성하라.",
    LLMTask.GENERAL_DEBUGGING: "실패 로그/코드를 분석하고 수정 방향과 복구 패치를 제시하라.",
}

USER_SNIPPETS = {
    LLMTask.PROJECT_DISCOVERY: "이 프로젝트의 핵심 구조와 실행 진입점을 분석해줘.",
    LLMTask.TOOL_CLASSIFICATION: "이 MCP Tool의 역할과 위험도를 평가해줘.",
    LLMTask.LOG_TRIAGE: "아래 실행 로그를 보고 실패 원인을 추정해줘.",
    LLMTask.SIMPLE_QUESTION: "OpenAI와 Ollama의 차이를 짧게 설명해줘.",
    LLMTask.MEMORY_ORGANIZATION: "최근 작업 메모를 요약하고 기억할 핵심을 정리해줘.",
    LLMTask.REQUIREMENTS_ANALYSIS: "PostgreSQL을 조회하는 MCP Agent를 설계해줘.",
    LLMTask.CODE_GENERATION: "FastAPI + React 구조로 설정 화면을 추가해줘.",
    LLMTask.PATCH_GENERATION: "이 오류를 수정하는 최소 패치를 만들어줘.",
    LLMTask.GENERAL_DEBUGGING: "Traceback을 보고 고장 원인을 분석해줘.",
}


def _message_bundle(task: LLMTask) -> list[dict]:
    return [
        {"role": "system", "content": SYSTEM_SNIPPETS.get(task, "작업을 수행하라.")},
        {"role": "user", "content": USER_SNIPPETS.get(task, "작업을 요청합니다.")},
    ]


def _route_for_provider(provider: str, model: str, base_url: str = "") -> dict:
    provider = str(provider or "").lower()
    if provider == "ollama":
        endpoint = f"{str(base_url or 'http://127.0.0.1:11434').rstrip('/')}/api/chat"
        return {
            "provider": "ollama",
            "endpoint": endpoint,
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "body_template": {
                "model": model,
                "stream": False,
                "options": {"temperature": 0},
                "messages": [],
            },
        }

    return {
        "provider": "openai",
        "endpoint": "https://api.openai.com/v1/chat/completions",
        "method": "POST",
        "headers": {
            "Content-Type": "application/json",
            "Authorization": "Bearer ${OPENAI_API_KEY}",
        },
        "body_template": {
            "model": model,
            "temperature": 0,
            "messages": [],
        },
    }



def build_llm_catalog() -> dict:
    s = get_settings()

    items = []
    for task in LLMTask:
        provider = provider_for(task)
        model = s.openai_model if provider == "openai" else s.ollama_model
        route = _route_for_provider(provider, model, s.ollama_base_url)
        body = dict(route["body_template"])
        body["messages"] = _message_bundle(task)
        items.append(
            {
                "task": task.value,
                "label": _task_label(task),
                "group": _task_group(task),
                "provider": provider,
                "model": model,
                "request": {
                    "method": route["method"],
                    "endpoint": route["endpoint"],
                    "headers": route["headers"],
                    "body": body,
                },
                "notes": [
                    "AgentStudio 내부에서는 LangChain Chat Model 래퍼를 통해 호출됩니다.",
                    "아래 JSON은 실제 요청 구조를 이해하기 위한 표시용 예시입니다.",
                ],
            }
        )

    return {
        "generated_at": datetime.now().isoformat(),
        "defaults": {
            "llm_provider": s.llm_provider,
            "local_llm_provider": s.local_llm_provider,
            "requirements_llm_provider": s.requirements_llm_provider,
            "coding_llm_provider": s.coding_llm_provider,
            "openai_model": s.openai_model,
            "ollama_model": s.ollama_model,
            "ollama_base_url": s.ollama_base_url,
        },
        "items": items,
    }
