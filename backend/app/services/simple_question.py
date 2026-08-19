from langchain_core.messages import SystemMessage, HumanMessage
from app.services.model_router import model_for_task, LLMTask

async def answer_simple_question(question: str) -> str:
    llm = model_for_task(LLMTask.SIMPLE_QUESTION)
    result = await llm.ainvoke([
        SystemMessage(content="간단한 개발 질문에 짧고 정확하게 답하십시오."),
        HumanMessage(content=question)
    ])
    return str(result.content)
