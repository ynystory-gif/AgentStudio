from __future__ import annotations

import json

from langchain_core.messages import SystemMessage, HumanMessage

from app.services.model_router import model_for_task, LLMTask
from app.services.coding_rule_governance import classify_candidates


SYSTEM = """당신은 THEANOVA AgentStudio의 Coding Style Analyzer입니다.

사용자가 제공한 강의자료, 코드 예제, 개발 가이드를 읽고
'에이전트 프로그램 생성 시 실제 적용할 코딩 규칙 후보'만 추출합니다.

교육 일정, 강의 날짜, 가격 예시, 단순 출력 예시 등은 무조건 규칙으로 만들지 마십시오.

RAG/문서 처리 자료를 분석할 때는 특정 예제 수치를 그대로 규칙화하지 말고,
문서 구조에 따른 전략 선택 조건, 설정화해야 할 Parameter, Metadata/원문 추적,
품질 평가 기준, 빈 검색 결과/근거 부족 처리처럼 재사용 가능한 설계 원칙을 우선 추출하십시오.

반드시 아래 5개 유형으로 분류합니다.
- required: 반드시 지켜야 하는 규칙
- recommended: 기본적으로 권장되는 규칙
- conditional: 특정 기술/상황에서만 적용
- template_candidate: 코드 골격/템플릿으로 보관할 후보
- reference_only: 교육 설명/예시이며 코딩 규칙에는 미적용

JSON 하나만 반환합니다.
"""


async def analyze_coding_style_text(text: str) -> dict:
    content = (text or "").strip()
    if not content:
        raise ValueError("분석할 코딩 스타일 텍스트가 없습니다.")

    llm = model_for_task(LLMTask.CODE_GENERATION)

    result = await llm.ainvoke([
        SystemMessage(content=SYSTEM),
        HumanMessage(content=f"""
다음 자료를 분석하십시오.

[자료]
{content}

[반환 형식]
{{
  "summary": "자료 요약",
  "candidates": [
    {{
      "category": "prompt/security/architecture 등",
      "name": "규칙 이름",
      "classification": "required|recommended|conditional|template_candidate|reference_only",
      "rule": "실제 적용할 규칙 또는 참고 설명",
      "applies_to": ["python", "langchain", "agent"],
      "reason": "분류 이유"
    }}
  ]
}}
""")
    ])

    raw = str(result.content or "").strip()

    if raw.startswith("```"):
        lines = raw.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        raw = "\n".join(lines).strip()
        if raw.lower().startswith("json"):
            raw = raw[4:].lstrip()

    analyzed = json.loads(raw)

    candidates = list(
        analyzed.get("candidates") or []
    )

    analyzed["governance"] = classify_candidates(
        candidates
    )

    return analyzed
