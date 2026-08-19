from langchain_core.messages import SystemMessage, HumanMessage
from app.services.model_router import model_for_task, LLMTask

async def organize_memory(text: str) -> str:
    llm = model_for_task(LLMTask.MEMORY_ORGANIZATION)
    result = await llm.ainvoke([
        SystemMessage(content=(
            "프로젝트 장기 기억으로 저장할 내용을 간결하게 정리하십시오. "
            "결정사항, 고정 규칙, 경로, 기술 선택, 해결된 오류를 우선하십시오."
        )),
        HumanMessage(content=text)
    ])
    return str(result.content)
