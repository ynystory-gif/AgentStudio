from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import get_settings
from app.services.codex_app_server_service import codex_app_server_manager
from app.services.learning_teacher_router import learning_teacher_priority
from app.services.llm_provider import get_chat_model

PRIMARY_CATEGORIES = ("models", "papers", "news")
SECONDARY_CATEGORIES = ("spaces", "datasets")


def _extract_json(text: str) -> Any:
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("LLM 번역 응답이 비어 있습니다.")
    fenced = re.search(r"```(?:json)?\s*(.*?)```", raw, re.IGNORECASE | re.DOTALL)
    if fenced:
        raw = fenced.group(1).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("[")
        end = raw.rfind("]")
        if start >= 0 and end > start:
            return json.loads(raw[start:end + 1])
        raise


def _translation_rows(categories: dict[str, Any], category_order: tuple[str, ...]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for category in category_order:
        payload = categories.get(category)
        if not isinstance(payload, dict):
            continue
        for item in payload.get("items") or []:
            if not isinstance(item, dict):
                continue
            rows.append({
                "id": str(item.get("id") or ""),
                "category": category,
                "title_original": str(item.get("title_original") or ""),
                "summary_original": str(item.get("summary_original") or item.get("summary_ko") or ""),
                "tags": list(item.get("tags") or [])[:8],
                "pipeline_tag": str(item.get("pipeline_tag") or ""),
                "library_name": str(item.get("library_name") or ""),
            })
    return rows


def _system_prompt() -> str:
    return (
        "당신은 THEANOVA AgentStudio의 Hugging Face AI 개발 동향 전문 한국어 번역기입니다. "
        "입력 데이터에 근거해서만 번역/정리하고, 원문에 없는 기능이나 사실을 만들어내지 마세요. "
        "models의 owner/repository 식별자와 모델명, 제품명, 기술명은 원문을 유지합니다. "
        "models의 summary_ko는 마우스 오버 설명용입니다. task/library/tags/원문 설명을 근거로 모델이 어떤 모델인지 개발자가 빠르게 이해할 수 있게 1~3문장으로 한국어로 정리하세요. "
        "papers의 title_ko와 summary_ko는 논문 제목과 초록/본문 요약을 자연스럽고 정확한 한국어로 번역하세요. "
        "news의 title_ko와 summary_ko는 뉴스/블로그 제목과 본문 요약을 자연스럽고 정확한 한국어로 번역하세요. "
        "spaces는 무엇을 할 수 있는 Space인지, datasets는 어떤 데이터셋인지 입력 근거 범위에서 짧게 한국어로 설명하세요. "
        "developer_point는 AI 개발자가 왜 확인할 가치가 있는지 입력 근거 범위에서 한국어 한 문장으로 작성하세요. "
        "반드시 JSON 배열만 반환하고 입력 id/category를 그대로 유지하세요. "
        "각 원소는 id, category, title_ko, summary_ko, developer_point 키를 가져야 합니다."
    )


def _human_prompt(rows: list[dict[str, Any]]) -> str:
    return (
        "아래 항목들을 개별 호출하지 말고 이 배치 전체를 한 번에 처리하세요.\n"
        + json.dumps(rows, ensure_ascii=False)
    )


async def _provider_candidates() -> list[str]:
    """Prefer OpenAI/Codex for dashboard translation; use Ollama only as final fallback."""
    try:
        policy = await learning_teacher_priority()
        ordered = [str(x).lower() for x in (policy.get("priority") or [])]
        enabled: list[str] = []
        if policy.get("openai_enabled"):
            enabled.append("openai")
        if policy.get("codex_enabled"):
            enabled.append("codex")
        cloud = [name for name in ordered if name in enabled and name in {"openai", "codex"}]
        for name in enabled:
            if name not in cloud:
                cloud.append(name)
        if cloud:
            return cloud + ["ollama"]
    except Exception:
        pass

    settings = get_settings()
    cloud: list[str] = []
    if bool(settings.openai_enabled):
        cloud.append("openai")
    if bool(settings.codex_enabled):
        cloud.append("codex")
    return cloud + ["ollama"]


async def _invoke_provider(provider: str, system_text: str, human_text: str) -> str:
    if provider == "codex":
        prompt = f"{system_text}\n\n{human_text}"
        text = await asyncio.to_thread(
            codex_app_server_manager.run_text_completion,
            prompt,
            "",
            "",
            "",
            180.0,
        )
        result = str(text or "").strip()
        if not result:
            raise RuntimeError("Codex 번역 응답이 비어 있습니다.")
        return result

    model = get_chat_model(provider)
    response = await model.ainvoke([
        SystemMessage(content=system_text),
        HumanMessage(content=human_text),
    ])
    content = getattr(response, "content", "")
    if isinstance(content, list):
        content = "".join(
            str(part.get("text") or part.get("content") or "") if isinstance(part, dict) else str(part)
            for part in content
        )
    result = str(content or "").strip()
    if not result:
        raise RuntimeError(f"{provider} 번역 응답이 비어 있습니다.")
    return result


async def _translate_batch(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str, list[str]]:
    if not rows:
        return [], "", []
    errors: list[str] = []
    system_text = _system_prompt()
    human_text = _human_prompt(rows)
    for provider in await _provider_candidates():
        try:
            raw = await _invoke_provider(provider, system_text, human_text)
            parsed = _extract_json(raw)
            if not isinstance(parsed, list):
                raise ValueError("번역 결과가 JSON 배열이 아닙니다.")
            return [row for row in parsed if isinstance(row, dict)], provider, errors
        except Exception as exc:
            errors.append(f"{provider}: {exc}")
    raise RuntimeError(" / ".join(errors) or "사용 가능한 번역 Provider가 없습니다.")


def _apply_rows(categories: dict[str, Any], parsed: list[dict[str, Any]]) -> int:
    translated: dict[tuple[str, str], dict[str, Any]] = {}
    for row in parsed:
        key = (str(row.get("category") or ""), str(row.get("id") or ""))
        translated[key] = row

    applied = 0
    for category, payload in categories.items():
        if not isinstance(payload, dict):
            continue
        for item in payload.get("items") or []:
            if not isinstance(item, dict):
                continue
            row = translated.get((category, str(item.get("id") or "")))
            if not row:
                continue
            title_ko = str(row.get("title_ko") or "").strip()
            summary_ko = str(row.get("summary_ko") or "").strip()
            developer_point = str(row.get("developer_point") or "").strip()
            if title_ko:
                item["title_ko"] = title_ko
            item["summary_ko"] = summary_ko
            item["developer_point"] = developer_point
            applied += 1
    return applied


async def translate_categories_to_korean(categories: dict[str, Any]) -> dict[str, Any]:
    """Translate AI trends in two batched calls instead of per-item calls.

    Batch 1 contains all model hover descriptions + paper titles/bodies + AI news titles/bodies.
    Batch 2 contains Spaces + model-related datasets. OpenAI/Codex are preferred; Ollama is a
    final safety fallback so the home dashboard can still render when cloud providers are disabled.
    """
    primary_rows = _translation_rows(categories, PRIMARY_CATEGORIES)
    secondary_rows = _translation_rows(categories, SECONDARY_CATEGORIES)
    if not primary_rows and not secondary_rows:
        return {"status": "SKIPPED", "message": "번역할 항목이 없습니다.", "batch_requests": 0}

    applied = 0
    providers: list[str] = []
    warnings: list[str] = []
    batch_requests = 0

    if primary_rows:
        parsed, provider, errors = await _translate_batch(primary_rows)
        batch_requests += 1
        applied += _apply_rows(categories, parsed)
        if provider:
            providers.append(provider)
        warnings.extend(errors)

    if secondary_rows:
        parsed, provider, errors = await _translate_batch(secondary_rows)
        batch_requests += 1
        applied += _apply_rows(categories, parsed)
        if provider:
            providers.append(provider)
        warnings.extend(errors)

    if not applied:
        raise ValueError("LLM 번역 결과를 수집 항목과 매칭하지 못했습니다.")

    return {
        "status": "OK",
        "translated_items": applied,
        "batch_requests": batch_requests,
        "providers": list(dict.fromkeys(providers)),
        "message": "",
        "warnings": warnings[-4:],
    }
