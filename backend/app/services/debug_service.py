import json
import re
from langchain_core.messages import SystemMessage, HumanMessage
from app.services.model_router import model_for_task, LLMTask

TRIAGE_SYSTEM = """당신은 로컬 로그 1차 분석기입니다.
긴 오류 로그에서 핵심 오류, 관련 파일, 예외명, 마지막 실패 원인을 짧게 추출하십시오.
추측보다 로그에 실제로 나타난 사실을 우선하십시오.
"""

DEBUG_SYSTEM = """당신은 코드 디버깅 전문 에이전트입니다.
로컬 1차 로그 분석과 테스트 실패 로그, 현재 Patch를 바탕으로 다음 수정 전략을 JSON으로만 반환합니다.

형식:
{
  "diagnosis": "원인",
  "request_for_patch": "다음 Patch Agent에게 전달할 구체적 수정 지시",
  "should_retry": true
}
동일한 수정이 반복되지 않도록 실제 실패 원인에 집중하십시오.
"""


def _deterministic_triage(test_output: str, local_error: str = "") -> str:
    text = str(test_output or "")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    interesting = [
        line for line in lines
        if re.search(r"(?i)(error|exception|failed|traceback|assert|modulenotfound|syntaxerror|importerror|connecterror|timeout)", line)
    ]
    tail = interesting[-8:] if interesting else lines[-8:]
    summary = "\n".join(tail) or "테스트 로그가 비어 있습니다."
    if local_error:
        summary += f"\n[로컬 로그 분석기 사용 불가: {local_error}]"
    return summary[-6000:]


async def triage_log(test_output: str) -> str:
    llm = model_for_task(LLMTask.LOG_TRIAGE)
    result = await llm.ainvoke([
        SystemMessage(content=TRIAGE_SYSTEM),
        HumanMessage(content=str(test_output or "")[-12000:])
    ])
    return str(result.content)


async def analyze_failure(
    original_request: str,
    test_output: str,
    previous_patch: dict,
    iteration: int,
    provider: str | None = None,
) -> dict:
    triage_source = "adaptive_llm"
    triage_error = ""
    try:
        triage = await triage_log(test_output)
    except Exception as exc:
        triage_source = "deterministic_fallback"
        triage_error = f"{type(exc).__name__}: {exc}"
        triage = _deterministic_triage(test_output, triage_error)

    llm = model_for_task(LLMTask.EXECUTION_DEBUG_REPAIR, provider)
    result = await llm.ainvoke([
        SystemMessage(content=DEBUG_SYSTEM),
        HumanMessage(content=(
            f"원래 요청:\n{original_request}\n\n"
            f"디버그 반복: {iteration}\n\n"
            f"1차 로그 분석({triage_source}):\n{triage}\n\n"
            f"원본 테스트 실패 로그:\n{str(test_output or '')[-8000:]}\n\n"
            f"이전 Patch:\n{json.dumps(previous_patch, ensure_ascii=False)[:8000]}"
        ))
    ])
    text = str(result.content).strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    data = json.loads(text)
    data["local_log_triage"] = triage
    data["local_log_triage_source"] = triage_source
    if triage_error:
        data["local_log_triage_error"] = triage_error
    return data
