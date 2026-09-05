from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.config import get_settings
from app.services.active_ollama_model_service import resolve_active_ollama_model
from app.core.database import SessionLocal
from app.core.machine_identity import current_pc_name
from app.models.entities import AppSetting
from app.services.codex_app_server_service import codex_app_server_manager
from app.services.llm_provider import get_chat_model
from app.services.llm_usage_service import (
    UsageTrackedChatModel,
    _safe_record_llm_exchange,
    usage_context,
)


class _CodexHistoryModel:
    """Minimal model identity object used by the common LLM history recorder."""

    def __init__(self, model_name: str):
        self.model_name = str(model_name or "codex-default")


class _CodexHistoryResult:
    """Normalize Codex app-server text so it renders like other LLM responses."""

    def __init__(self, content: str):
        self.content = str(content or "")
        self.response_metadata = {"transport": "codex_app_server"}
        self.usage_metadata = {}


async def _pc_settings() -> dict[str, str]:
    keys = {
        "AI_PROVIDER_STRATEGY",
        "OPENAI_ENABLED",
        "OPENAI_MODEL",
        "CODEX_ENABLED",
        "OLLAMA_MODEL",
        "CODING_LLM_PROVIDER",
        "REQUIREMENTS_LLM_PROVIDER",
    }
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(AppSetting).where(
                    AppSetting.pc_name == current_pc_name(),
                    AppSetting.key.in_(list(keys)),
                )
            )
        ).scalars().all()
    return {str(row.key): str(row.value or "") for row in rows}


def _truthy(value: str, default: bool = False) -> bool:
    raw = str(value or "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on", "enabled"}


def _strategy_chain(strategy: str) -> list[str]:
    raw = str(strategy or "").strip().lower()
    normalized = raw.replace("→", ">").replace(";", ",").replace("|", ",")
    if ">" in normalized or "," in normalized:
        tokens = re.split(r"[>,]", normalized)
        result = [token.strip() for token in tokens if token.strip() in {"codex", "openai", "ollama"}]
        if result:
            return list(dict.fromkeys(result))
    mapping = {
        "codex_first": ["codex", "openai", "ollama"],
        "openai_first": ["openai", "codex", "ollama"],
        "cloud_first": ["codex", "openai", "ollama"],
        "ollama_first": ["ollama", "openai", "codex"],
        "local_first": ["ollama", "openai", "codex"],
        "auto": ["codex", "openai", "ollama"],
    }
    return mapping.get(raw, ["codex", "openai", "ollama"])


async def learning_teacher_priority() -> dict[str, Any]:
    settings = get_settings()
    db = await _pc_settings()
    strategy = db.get("AI_PROVIDER_STRATEGY") or str(settings.ai_provider_strategy or "auto")
    chain = _strategy_chain(strategy)

    # If a high-value task provider is explicitly configured, respect it before AUTO strategy.
    explicit: list[str] = []
    for key in ("REQUIREMENTS_LLM_PROVIDER", "CODING_LLM_PROVIDER"):
        value = str(db.get(key) or getattr(settings, key.lower(), "") or "").strip().lower()
        if value in {"codex", "openai", "ollama"} and value not in explicit:
            explicit.append(value)
    chain = list(dict.fromkeys([*explicit, *chain]))

    openai_enabled = _truthy(db.get("OPENAI_ENABLED", ""), bool(settings.openai_enabled))
    codex_enabled = _truthy(db.get("CODEX_ENABLED", ""), bool(settings.codex_enabled))
    openai_model = db.get("OPENAI_MODEL") or str(settings.openai_model or "")
    active_ollama = await resolve_active_ollama_model()
    ollama_model = str(active_ollama.get("active_model") or "")
    return {
        "strategy": strategy,
        "priority": chain,
        "openai_enabled": openai_enabled,
        "codex_enabled": codex_enabled,
        "models": {
            "codex": "codex-default",
            "openai": openai_model,
            "ollama": ollama_model,
        },
    }


def _content_text(result: Any) -> str:
    content = getattr(result, "content", result)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
            else:
                parts.append(str(item))
        return "".join(parts)
    return str(content or "")


async def _complete_provider(provider: str, prompt: str, model_name: str) -> str:
    if provider == "codex":
        model = _CodexHistoryModel(model_name)
        request = {
            "provider": "codex",
            "model": model.model_name,
            "task": "llm_learning_teacher_generation",
            "transport": "codex_app_server",
            "input": prompt,
        }
        started_at = datetime.now().astimezone()
        started_perf = time.perf_counter()
        with usage_context(operation="llm_learning_teacher_generation"):
            try:
                text = await asyncio.to_thread(
                    codex_app_server_manager.run_text_completion,
                    prompt,
                    "",
                    "",
                    "",
                    240.0,
                )
                normalized = str(text or "").strip()
                if not normalized:
                    raise RuntimeError("codex가 빈 응답을 반환했습니다.")
                _safe_record_llm_exchange(
                    provider="codex",
                    task="llm_learning_teacher_generation",
                    model=model,
                    request=request,
                    result=_CodexHistoryResult(normalized),
                    usage_row={
                        "input_tokens": 0,
                        "cached_input_tokens": 0,
                        "output_tokens": 0,
                        "total_tokens": 0,
                        "cost_usd": 0.0,
                        "usage_source": "codex_app_server_unavailable",
                    },
                    started_at=started_at,
                    elapsed_ms=round((time.perf_counter() - started_perf) * 1000),
                )
                return normalized
            except Exception as error:
                _safe_record_llm_exchange(
                    provider="codex",
                    task="llm_learning_teacher_generation",
                    model=model,
                    request=request,
                    error=error,
                    started_at=started_at,
                    elapsed_ms=round((time.perf_counter() - started_perf) * 1000),
                )
                raise

    tracked = UsageTrackedChatModel(
        get_chat_model(provider),
        provider,
        "llm_learning_teacher_generation",
    )
    result = await asyncio.to_thread(tracked.invoke, prompt)
    text = _content_text(result).strip()
    if not text:
        raise RuntimeError(f"{provider}가 빈 응답을 반환했습니다.")
    return text


def _parse_json_payload(text: str) -> Any:
    value = str(text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.I)
        value = re.sub(r"\s*```$", "", value)
    starts = [pos for pos in (value.find("{"), value.find("[")) if pos >= 0]
    if starts:
        value = value[min(starts):]
    for end_char in ("}", "]"):
        end = value.rfind(end_char)
        if end >= 0:
            try:
                return json.loads(value[: end + 1])
            except Exception:
                pass
    return json.loads(value)


def _scope_prompt(case: dict) -> str:
    return f"""당신은 THEANOVA AgentStudio의 LLM 학습 데이터 설계 Teacher입니다.
아래 확정 오판 한 건의 취약한 지식/판단 범위를 넓게 정의하세요. JSON 객체만 반환하세요.
필드: domain, topic, root_cause, learning_objective, subtopics(6~15개), variation_axes(5~10개), pitfalls(5~10개), prerequisites(0~8개).
사용자 요청: {case.get('user_request','')}
잘못된 결과: {case.get('wrong_output','')}
기대 결과: {case.get('expected_output','')}
오류 유형: {case.get('error_type','')}
오류 원인: {case.get('error_reason','')}
"""


def _problem_prompt(case: dict, scope: dict, need: int, existing_count: int) -> str:
    return f"""THEANOVA AgentStudio 학습 데이터 Teacher입니다.
확정 오판의 취약 범위를 학습하기 위한 서로 다른 문제 {need}개를 생성하세요.
단순 문장 바꿔쓰기를 금지합니다. 개념/상황판단/코드수정/디버그/Tool선택/예외·함정을 섞으세요.
난이도 easy/medium/hard를 섞고, 실제 프로젝트 환경과 사용자 표현도 다양하게 만드세요.
이미 생성된 문제 수: {existing_count}
학습 범위 JSON: {json.dumps(scope, ensure_ascii=False)}
원본 오판 사용자 요청: {case.get('user_request','')}
원본 잘못된 결과: {case.get('wrong_output','')}
JSON 배열만 반환하세요. 각 항목 필드:
instruction, input, output, domain, topic, subtopic, difficulty, problem_type.
output은 정답/권장 응답이어야 하며 잘못된 원본 답을 그대로 반복하지 마세요.
"""


def _validate_problem(item: dict) -> dict | None:
    if not isinstance(item, dict):
        return None
    instruction = str(item.get("instruction") or "").strip()
    output = str(item.get("output") or "").strip()
    if len(instruction) < 8 or len(output) < 2:
        return None
    return {
        "id": uuid.uuid4().hex,
        "instruction": instruction,
        "input": str(item.get("input") or "").strip(),
        "output": output,
        "domain": str(item.get("domain") or "").strip(),
        "topic": str(item.get("topic") or "").strip(),
        "subtopic": str(item.get("subtopic") or "").strip(),
        "difficulty": str(item.get("difficulty") or "medium").strip().lower(),
        "problem_type": str(item.get("problem_type") or "scenario").strip().lower(),
        "source": "expanded_from_confirmed_misjudgment",
        "validated": False,
    }


async def generate_dataset_with_priority(case: dict, target_count: int) -> dict[str, Any]:
    policy = await learning_teacher_priority()
    attempts: list[dict[str, Any]] = []
    for provider in policy["priority"]:
        model_name = str(policy["models"].get(provider) or "")
        if provider == "codex" and not policy["codex_enabled"]:
            attempts.append({"provider": provider, "model": model_name, "ok": False, "error": "Codex 사용 설정 OFF"})
            continue
        if provider == "openai" and not policy["openai_enabled"]:
            attempts.append({"provider": provider, "model": model_name, "ok": False, "error": "OpenAI 사용 설정 OFF"})
            continue
        try:
            scope_text = await _complete_provider(provider, _scope_prompt(case), model_name)
            scope = _parse_json_payload(scope_text)
            if not isinstance(scope, dict):
                raise ValueError("학습 범위 분석 결과가 JSON 객체가 아닙니다.")

            generated: list[dict] = []
            fingerprints: set[str] = set()
            batch_size = 20
            attempts_count = 0
            while len(generated) < target_count and attempts_count < max(4, (target_count // batch_size) + 5):
                attempts_count += 1
                need = min(batch_size, target_count - len(generated))
                text = await _complete_provider(provider, _problem_prompt(case, scope, need, len(generated)), model_name)
                parsed = _parse_json_payload(text)
                if not isinstance(parsed, list):
                    raise ValueError("문제 생성 결과가 JSON 배열이 아닙니다.")
                for raw in parsed:
                    item = _validate_problem(raw)
                    if not item:
                        continue
                    fingerprint = re.sub(r"\s+", " ", (item["instruction"] + " " + item["input"]).casefold()).strip()[:700]
                    if fingerprint in fingerprints:
                        continue
                    fingerprints.add(fingerprint)
                    generated.append(item)
                    if len(generated) >= target_count:
                        break
            if len(generated) < min(10, target_count):
                raise RuntimeError(f"유효한 학습 문제를 충분히 생성하지 못했습니다: {len(generated)}/{target_count}")
            attempts.append({"provider": provider, "model": model_name, "ok": True})
            return {
                "scope": scope,
                "problems": generated,
                "teacher_provider": provider,
                "teacher_model": model_name,
                "teacher_strategy": policy["strategy"],
                "teacher_priority": list(policy["priority"]),
                "teacher_attempts": attempts,
            }
        except Exception as exc:
            attempts.append({
                "provider": provider,
                "model": model_name,
                "ok": False,
                "error": str(exc) or type(exc).__name__,
            })
            continue
    detail = " | ".join(f"{row['provider']}({row.get('model','')}): {row.get('error','실패')}" for row in attempts)
    raise RuntimeError("설정된 상위 모델 우선순위의 모든 Teacher 호출이 실패했습니다. " + detail)
