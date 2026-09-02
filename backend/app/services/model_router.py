from __future__ import annotations

import asyncio
from enum import StrEnum
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage

from app.core.config import get_settings
from app.services.codex_app_server_service import codex_app_server_manager
from app.services.llm_provider import get_chat_model
from app.services.active_ollama_model_service import current_runtime_ollama_model
from app.services.llm_usage_service import UsageTrackedChatModel, current_usage_context


class LLMTask(StrEnum):
    PROJECT_DISCOVERY = "project_discovery"
    TOOL_CLASSIFICATION = "tool_classification"
    LOG_TRIAGE = "log_triage"
    SIMPLE_QUESTION = "simple_question"
    MEMORY_ORGANIZATION = "memory_organization"

    REQUIREMENTS_ANALYSIS = "requirements_analysis"
    CODE_GENERATION = "code_generation"
    PATCH_GENERATION = "patch_generation"
    GENERAL_DEBUGGING = "general_debugging"

    # v5.340: architecture-critical tasks use the high-performance provider chain.
    # WORKFLOW_DESIGN includes target Workflow + LangGraph branch/state design.
    WORKFLOW_DESIGN = "workflow_design"
    DATABASE_SCHEMA_DESIGN = "database_schema_design"
    MULTI_FILE_CODE_CHANGE = "multi_file_code_change"
    EXECUTION_DEBUG_REPAIR = "execution_debug_repair"
    ARCHITECTURE_CONFORMANCE = "architecture_conformance"


LOCAL_TASKS = {
    LLMTask.PROJECT_DISCOVERY,
    LLMTask.TOOL_CLASSIFICATION,
    LLMTask.LOG_TRIAGE,
    LLMTask.SIMPLE_QUESTION,
    LLMTask.MEMORY_ORGANIZATION,
}

HIGH_PERFORMANCE_TASKS = {
    LLMTask.WORKFLOW_DESIGN,
    LLMTask.DATABASE_SCHEMA_DESIGN,
    LLMTask.MULTI_FILE_CODE_CHANGE,
    LLMTask.EXECUTION_DEBUG_REPAIR,
    LLMTask.ARCHITECTURE_CONFORMANCE,
}

CODEX_ELIGIBLE_TASKS = {
    LLMTask.REQUIREMENTS_ANALYSIS,
    LLMTask.CODE_GENERATION,
    LLMTask.PATCH_GENERATION,
    LLMTask.GENERAL_DEBUGGING,
    *HIGH_PERFORMANCE_TASKS,
}


def _configured_provider_for(task: LLMTask) -> str:
    s = get_settings()
    if task in LOCAL_TASKS:
        return (s.local_llm_provider or "auto").lower()
    if task in {LLMTask.REQUIREMENTS_ANALYSIS, LLMTask.WORKFLOW_DESIGN, LLMTask.DATABASE_SCHEMA_DESIGN}:
        return (s.requirements_llm_provider or "auto").lower()
    return (s.coding_llm_provider or "auto").lower()


def provider_candidates_for(task: LLMTask, provider_override: str | None = None) -> list[str]:
    """Return the provider attempt order for an AgentStudio AI task.

    v5.340 policy:
    - an explicit request/manual provider always wins;
    - lightweight/general tasks keep Ollama-first routing;
    - architecture-critical tasks use Codex -> OpenAI -> Ollama in automatic mode;
    - disabled providers are removed before execution; runtime/config failures fall
      through to the next candidate automatically.

    High-performance tasks are Workflow/LangGraph design, DB Entity/relationship
    design, complex multi-file changes, and execution/debug/large repair work.
    """
    s = get_settings()
    explicit = (provider_override or "").strip().lower()
    if explicit in {"ollama", "openai", "codex"}:
        if explicit == "openai" and not s.openai_enabled:
            return ["ollama"]
        if explicit == "codex" and not s.codex_enabled:
            return ["ollama"]
        if explicit == "codex" and task in {
            LLMTask.CODE_GENERATION,
            LLMTask.PATCH_GENERATION,
            LLMTask.MULTI_FILE_CODE_CHANGE,
            LLMTask.EXECUTION_DEBUG_REPAIR,
        }:
            # v5.392: a Windows Codex sandbox-helper outage is provider
            # infrastructure, not a project-code defect. Keep Codex first, but
            # preserve a repair/generation fallback so the whole workflow does
            # not stop solely because codex-windows-sandbox-setup.exe failed.
            candidates = ["codex"]
            if s.openai_enabled:
                candidates.append("openai")
            candidates.append("ollama")
            return candidates
        return [explicit]

    strategy = (s.ai_provider_strategy or "ollama_first").strip().lower()
    configured = _configured_provider_for(task)

    # Manual mode deliberately respects the user's selected provider. If the
    # selected provider is disabled, filtering below falls back safely.
    if strategy == "manual" and configured in {"ollama", "openai", "codex"}:
        candidates = [configured]
    elif task in HIGH_PERFORMANCE_TASKS:
        # User-requested v5.340 policy: expensive/structural decisions should use
        # the strongest connected provider first, while still remaining usable
        # without paid providers.
        candidates = []
        if s.codex_enabled:
            candidates.append("codex")
        if s.openai_enabled:
            candidates.append("openai")
        candidates.append("ollama")
    else:
        candidates = ["ollama"]
        if s.openai_enabled:
            candidates.append("openai")
        if s.codex_enabled and task in CODEX_ELIGIBLE_TASKS:
            candidates.append("codex")

    filtered: list[str] = []
    for provider in candidates:
        if provider == "openai" and not s.openai_enabled:
            continue
        if provider == "codex" and (not s.codex_enabled or task not in CODEX_ELIGIBLE_TASKS):
            continue
        if provider not in filtered:
            filtered.append(provider)
    return filtered or ["ollama"]


def provider_for(task: LLMTask) -> str:
    return provider_candidates_for(task)[0]


def _prompt_from_invocation(args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    value: Any = args[0] if args else kwargs.get("input")
    if isinstance(value, str):
        return value
    if isinstance(value, BaseMessage):
        return f"{value.type}: {value.content}"
    if isinstance(value, (list, tuple)):
        lines: list[str] = []
        for item in value:
            if isinstance(item, BaseMessage):
                lines.append(f"{item.type}: {item.content}")
            elif isinstance(item, dict):
                role = item.get("role") or item.get("type") or "message"
                lines.append(f"{role}: {item.get('content') or item}")
            else:
                lines.append(str(item))
        return "\n\n".join(lines)
    return str(value or "")


class AdaptiveTaskChatModel:
    """Minimal LangChain-compatible adapter with provider failover.

    AgentStudio services currently use ``ainvoke``/``invoke`` only. The adapter
    preserves that contract while making provider selection resilient. Codex is
    adapted to an ``AIMessage`` through a read-only ephemeral app-server thread.
    """

    def __init__(self, task: LLMTask, provider_override: str | None = None):
        self.task = task
        self.provider_override = provider_override
        self.candidates = provider_candidates_for(task, provider_override)
        self.last_provider = self.candidates[0]
        self.last_errors: list[str] = []

    def __getattr__(self, name: str):
        # Some framework code inspects model/model_name. Expose the primary model
        # when possible without starting any external process.
        if name in {"model", "model_name"}:
            s = get_settings()
            provider = self.candidates[0]
            if provider == "ollama":
                return current_runtime_ollama_model()
            if provider == "openai":
                return s.openai_model
            return "codex"
        raise AttributeError(name)

    async def ainvoke(self, *args, **kwargs):
        errors: list[str] = []
        for provider in self.candidates:
            try:
                if provider == "codex":
                    prompt = _prompt_from_invocation(args, kwargs)
                    context = current_usage_context()
                    project_root = str(context.get("project_root") or "")
                    text = await asyncio.to_thread(
                        codex_app_server_manager.run_text_completion,
                        prompt,
                        project_root,
                    )
                    self.last_provider = "codex"
                    return AIMessage(
                        content=text,
                        response_metadata={"agentstudio_provider": "codex"},
                    )

                model = get_chat_model(provider)
                tracked = UsageTrackedChatModel(model=model, provider=provider, task=self.task.value)
                result = await tracked.ainvoke(*args, **kwargs)
                content = getattr(result, "content", None)
                if content is not None and not str(content).strip():
                    raise RuntimeError("LLM이 빈 응답을 반환했습니다.")
                self.last_provider = provider
                try:
                    metadata = dict(getattr(result, "response_metadata", None) or {})
                    metadata["agentstudio_provider"] = provider
                    result.response_metadata = metadata
                except Exception:
                    pass
                return result
            except Exception as exc:
                errors.append(f"{provider}: {type(exc).__name__}: {exc}")

        self.last_errors = errors
        raise RuntimeError("AI Provider 호출이 모두 실패했습니다. " + " | ".join(errors))

    def invoke(self, *args, **kwargs):
        errors: list[str] = []
        for provider in self.candidates:
            try:
                if provider == "codex":
                    prompt = _prompt_from_invocation(args, kwargs)
                    context = current_usage_context()
                    project_root = str(context.get("project_root") or "")
                    text = codex_app_server_manager.run_text_completion(prompt, project_root)
                    self.last_provider = "codex"
                    return AIMessage(
                        content=text,
                        response_metadata={"agentstudio_provider": "codex"},
                    )

                model = get_chat_model(provider)
                tracked = UsageTrackedChatModel(model=model, provider=provider, task=self.task.value)
                result = tracked.invoke(*args, **kwargs)
                content = getattr(result, "content", None)
                if content is not None and not str(content).strip():
                    raise RuntimeError("LLM이 빈 응답을 반환했습니다.")
                self.last_provider = provider
                try:
                    metadata = dict(getattr(result, "response_metadata", None) or {})
                    metadata["agentstudio_provider"] = provider
                    result.response_metadata = metadata
                except Exception:
                    pass
                return result
            except Exception as exc:
                errors.append(f"{provider}: {type(exc).__name__}: {exc}")

        self.last_errors = errors
        raise RuntimeError("AI Provider 호출이 모두 실패했습니다. " + " | ".join(errors))


def model_for_task(task: LLMTask, provider_override: str | None = None):
    return AdaptiveTaskChatModel(task, provider_override)


def routing_table() -> list[dict]:
    return [
        {
            "task": task.value,
            "provider": provider_for(task),
            "candidates": provider_candidates_for(task),
        }
        for task in LLMTask
    ]
