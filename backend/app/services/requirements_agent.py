import re

from langchain_core.messages import SystemMessage, HumanMessage
from app.services.model_router import model_for_task, LLMTask

SYSTEM = """당신은 AI Agent + MCP 프로그램 개발 요구사항을 분석하는 전문 인터뷰 에이전트입니다.

절대 규칙:
1. 한 메시지에서 질문은 정확히 하나만 합니다.
2. 사용자가 이미 알려준 내용을 다시 묻지 않습니다.
3. 답변을 짧게 확인한 뒤 가장 중요한 미확정 항목 하나만 질문합니다.
4. 불필요한 질문은 하지 않습니다.
5. 충분한 정보가 모이면 더 이상 질문하지 않고 요구사항을 요약합니다.
6. AI Agent, MCP Server/Client, Tool, 권한, 실행환경, LLM, DB, UI, 배포 요구를 고려합니다.
7. 요구사항 분석이 완료된 응답의 마지막 문장은 반드시 정확히 다음 문장으로 끝냅니다:
   "요구사항 분석이 완료되었습니다. Workflow 설계 단계로 진행할 수 있습니다."
8. 요구사항 분석 완료 후 "추가 요구사항이 필요하시면 말씀해 주세요", "더 필요한 내용이 있으면 알려주세요"처럼 사용자의 추가 입력을 유도하는 문장을 출력하지 않습니다.
9. 분석이 완료되지 않은 상태에서는 위 완료 문장을 사용하지 않습니다.
"""

async def next_interview_message(user_text: str, history: list[dict], provider: str | None = None) -> str:
    llm = model_for_task(LLMTask.REQUIREMENTS_ANALYSIS)
    compact = "\n".join(f"{x['role']}: {x['content']}" for x in history[-20:])
    messages = [
        SystemMessage(content=SYSTEM),
        HumanMessage(content=f"이전 대화:\n{compact}\n\n사용자 최신 답변:\n{user_text}")
    ]
    result = await llm.ainvoke(messages)
    content = str(result.content).strip()

    completion_markers = (
        "요구사항 분석 완료",
        "요구사항 분석이 완료",
    )
    if any(marker in content for marker in completion_markers):
        trailing_patterns = (
            r"\n*추가 요구사항이 필요하시면[^\n]*[.!！?？]?$",
            r"\n*추가적인 질문이나 요구사항이 생기면[^\n]*[.!！?？]?$",
            r"\n*더 필요한 내용이 있으면[^\n]*[.!！?？]?$",
            r"\n*추가로 필요한 사항이 있으면[^\n]*[.!！?？]?$",
        )
        for pattern in trailing_patterns:
            content = re.sub(
                pattern,
                "",
                content,
                flags=re.IGNORECASE,
            ).rstrip()

        final_message = (
            "요구사항 분석이 완료되었습니다. "
            "Workflow 설계 단계로 진행할 수 있습니다."
        )
        if not content.endswith(final_message):
            content = content.rstrip() + "\n\n" + final_message

    return content
