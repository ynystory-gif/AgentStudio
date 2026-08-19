from langchain_core.messages import SystemMessage, HumanMessage
from app.services.model_router import model_for_task, LLMTask
from app.services.agent_factory_policy import format_agent_factory_policy_for_prompt

SYSTEM = """당신은 AI Agent + MCP 프로그램 전문 소프트웨어 아키텍트입니다.
사용자의 요구사항으로 실행 가능한 구현 계획과 필요한 파일을 설계합니다.
원칙:
- FastAPI, PostgreSQL, React 환경을 우선 고려합니다.
- MCP Tool은 name/description/inputSchema/capability/risk를 분석합니다.
- 코드 수정 시 전체 덮어쓰기보다 최소 patch를 우선합니다.
- 로컬 시스템 위험 작업은 사용자 승인 단계를 둡니다.
- 실행/테스트/오류수정 루프를 포함합니다.
"""

async def build_plan(requirements: str, provider: str | None = None) -> str:
    llm = model_for_task(LLMTask.CODE_GENERATION)
    factory_policy = format_agent_factory_policy_for_prompt()
    result = await llm.ainvoke([
        SystemMessage(content=f"{SYSTEM}\n\n[Agent Factory 제작 기본 방향]\n{factory_policy}"),
        HumanMessage(content=requirements)
    ])
    return str(result.content)
