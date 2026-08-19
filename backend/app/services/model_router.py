from enum import StrEnum
from app.core.config import get_settings
from app.services.llm_provider import get_chat_model
from app.services.llm_usage_service import UsageTrackedChatModel

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

LOCAL_TASKS = {
    LLMTask.PROJECT_DISCOVERY,
    LLMTask.TOOL_CLASSIFICATION,
    LLMTask.LOG_TRIAGE,
    LLMTask.SIMPLE_QUESTION,
    LLMTask.MEMORY_ORGANIZATION,
}

OPENAI_TASKS = {
    LLMTask.REQUIREMENTS_ANALYSIS,
    LLMTask.CODE_GENERATION,
    LLMTask.PATCH_GENERATION,
    LLMTask.GENERAL_DEBUGGING,
}

def provider_for(task: LLMTask) -> str:
    s = get_settings()
    if task in LOCAL_TASKS:
        return s.local_llm_provider
    if task == LLMTask.REQUIREMENTS_ANALYSIS:
        return s.requirements_llm_provider
    if task in OPENAI_TASKS:
        return s.coding_llm_provider
    return s.local_llm_provider

def model_for_task(task: LLMTask):
    provider = provider_for(task)
    model = get_chat_model(provider)

    return UsageTrackedChatModel(
        model=model,
        provider=provider,
        task=task.value,
    )

def routing_table() -> list[dict]:
    return [
        {"task": task.value, "provider": provider_for(task)}
        for task in LLMTask
    ]
