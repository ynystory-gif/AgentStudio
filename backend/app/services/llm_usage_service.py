from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
from pathlib import Path
from typing import Any


# USD per 1M text tokens.
# OpenAI official developer model docs checked 2026-08-15.
PRICING_USD_PER_MILLION = {
    "gpt-4o-mini": {"input": 0.15, "cached_input": 0.075, "output": 0.60},
    "gpt-4o": {"input": 2.50, "cached_input": 1.25, "output": 10.00},
    "gpt-4.1-mini": {"input": 0.40, "cached_input": 0.10, "output": 1.60},
    "gpt-5-mini": {"input": 0.25, "cached_input": 0.025, "output": 2.00},
    "gpt-5.6-luna": {"input": 0.20, "cached_input": 0.20, "output": 1.20},
    "gpt-5.6-terra": {"input": 2.00, "cached_input": 2.00, "output": 12.00},
    "gpt-5.6-sol": {"input": 5.00, "cached_input": 5.00, "output": 30.00},
}

_usage_context = ContextVar("agentstudio_llm_usage_context", default={})
_write_lock = threading.Lock()


def usage_log_path() -> Path:
    project_root = Path(__file__).resolve().parents[3]
    path = project_root / "logs" / "llm_usage.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def current_usage_context() -> dict:
    """Return a copy of the current request-scoped LLM usage context."""
    return dict(_usage_context.get() or {})


@contextmanager
def usage_context(**values):
    current = dict(_usage_context.get() or {})
    current.update({
        key: value
        for key, value in values.items()
        if value not in (None, "")
    })
    token = _usage_context.set(current)
    try:
        yield
    finally:
        _usage_context.reset(token)


def _model_name(model: Any) -> str:
    for attr in ("model_name", "model"):
        value = getattr(model, attr, None)
        if value:
            return str(value)
    return type(model).__name__


def _extract_usage(result: Any) -> dict:
    usage = getattr(result, "usage_metadata", None) or {}
    response_metadata = getattr(result, "response_metadata", None) or {}
    token_usage = response_metadata.get("token_usage") or {}

    input_tokens = int(
        usage.get("input_tokens")
        or token_usage.get("prompt_tokens")
        or 0
    )
    output_tokens = int(
        usage.get("output_tokens")
        or token_usage.get("completion_tokens")
        or 0
    )
    total_tokens = int(
        usage.get("total_tokens")
        or token_usage.get("total_tokens")
        or input_tokens + output_tokens
    )

    input_details = usage.get("input_token_details") or {}
    prompt_details = token_usage.get("prompt_tokens_details") or {}
    cached_input_tokens = int(
        input_details.get("cache_read")
        or input_details.get("cached_tokens")
        or prompt_details.get("cached_tokens")
        or 0
    )

    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _pricing_for(model_name: str) -> dict | None:
    key = str(model_name or "").lower().strip()

    if key in PRICING_USD_PER_MILLION:
        return PRICING_USD_PER_MILLION[key]

    candidates = [
        (name, pricing)
        for name, pricing in PRICING_USD_PER_MILLION.items()
        if key.startswith(name + "-")
    ]
    if not candidates:
        return None

    candidates.sort(key=lambda row: len(row[0]), reverse=True)
    return candidates[0][1]


def _cost_usd(model_name: str, usage: dict) -> float:
    pricing = _pricing_for(model_name)
    if not pricing:
        return 0.0

    input_tokens = int(usage.get("input_tokens") or 0)
    cached = min(
        int(usage.get("cached_input_tokens") or 0),
        input_tokens,
    )
    uncached = max(input_tokens - cached, 0)
    output_tokens = int(usage.get("output_tokens") or 0)

    return round(
        (
            uncached * pricing["input"]
            + cached * pricing["cached_input"]
            + output_tokens * pricing["output"]
        ) / 1_000_000,
        10,
    )


def record_llm_usage(
    *,
    result: Any,
    provider: str,
    task: str,
    model: Any,
) -> dict:
    usage = _extract_usage(result)
    model_name = _model_name(model)
    provider_name = str(provider or "").lower()
    paid = provider_name == "openai"
    now = datetime.now().astimezone()
    context = dict(_usage_context.get() or {})

    row = {
        "timestamp": now.isoformat(),
        "date": now.date().isoformat(),
        "provider": provider_name,
        "model": model_name,
        "task": str(task or ""),
        "paid": paid,
        "input_tokens": usage["input_tokens"],
        "cached_input_tokens": usage["cached_input_tokens"],
        "output_tokens": usage["output_tokens"],
        "total_tokens": usage["total_tokens"],
        "cost_usd": _cost_usd(model_name, usage) if paid else 0.0,
        "project_root": str(context.get("project_root") or ""),
        "thread_id": str(context.get("thread_id") or ""),
        "operation": str(context.get("operation") or ""),
    }

    if row["total_tokens"] <= 0:
        return row

    with _write_lock:
        with usage_log_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    return row


class UsageTrackedChatModel:
    def __init__(self, model: Any, provider: str, task: str):
        self._model = model
        self._provider = provider
        self._task = task

    def __getattr__(self, name: str):
        return getattr(self._model, name)

    async def ainvoke(self, *args, **kwargs):
        request = _request_snapshot(args, kwargs, self._provider, self._task, self._model)
        started_at = datetime.now().astimezone()
        started_perf = time.perf_counter()
        try:
            result = await self._model.ainvoke(*args, **kwargs)
            usage_row = record_llm_usage(
                result=result,
                provider=self._provider,
                task=self._task,
                model=self._model,
            )
            _safe_record_llm_exchange(
                provider=self._provider,
                task=self._task,
                model=self._model,
                request=request,
                result=result,
                usage_row=usage_row,
                started_at=started_at,
                elapsed_ms=round((time.perf_counter() - started_perf) * 1000),
            )
            return result
        except Exception as error:
            _safe_record_llm_exchange(
                provider=self._provider,
                task=self._task,
                model=self._model,
                request=request,
                error=error,
                started_at=started_at,
                elapsed_ms=round((time.perf_counter() - started_perf) * 1000),
            )
            raise

    def invoke(self, *args, **kwargs):
        request = _request_snapshot(args, kwargs, self._provider, self._task, self._model)
        started_at = datetime.now().astimezone()
        started_perf = time.perf_counter()
        try:
            result = self._model.invoke(*args, **kwargs)
            usage_row = record_llm_usage(
                result=result,
                provider=self._provider,
                task=self._task,
                model=self._model,
            )
            _safe_record_llm_exchange(
                provider=self._provider,
                task=self._task,
                model=self._model,
                request=request,
                result=result,
                usage_row=usage_row,
                started_at=started_at,
                elapsed_ms=round((time.perf_counter() - started_perf) * 1000),
            )
            return result
        except Exception as error:
            _safe_record_llm_exchange(
                provider=self._provider,
                task=self._task,
                model=self._model,
                request=request,
                error=error,
                started_at=started_at,
                elapsed_ms=round((time.perf_counter() - started_perf) * 1000),
            )
            raise


def _empty_summary() -> dict:
    return {
        "paid_calls": 0,
        "all_calls": 0,
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "cost_usd": 0.0,
    }


def _accumulate(summary: dict, row: dict) -> None:
    summary["all_calls"] += 1
    if row.get("paid"):
        summary["paid_calls"] += 1

    for key in (
        "input_tokens",
        "cached_input_tokens",
        "output_tokens",
        "total_tokens",
    ):
        summary[key] += int(row.get(key) or 0)

    summary["cost_usd"] += float(row.get("cost_usd") or 0)


def _usage_period_matches(
    row_date: str,
    *,
    scope: str,
    selected_date: str,
    selected_month: str,
) -> bool:
    if scope == "all":
        return True
    if scope == "month":
        return row_date.startswith(selected_month + "-")
    return row_date == selected_date


def read_usage_summary(
    project_root: str = "",
    date: str = "",
    scope: str = "today",
    month: str = "",
) -> dict:
    today = datetime.now().astimezone().date().isoformat()
    normalized_scope = str(scope or "today").strip().lower()
    if normalized_scope not in {"today", "all", "month", "day"}:
        normalized_scope = "today"

    selected_date = (date or "").strip() or today
    selected_month = (month or "").strip() or selected_date[:7]

    # 오늘 전체는 반드시 실제 로컬 오늘 날짜를 사용합니다.
    if normalized_scope == "today":
        selected_date = today
        selected_month = today[:7]

    normalized_project = str(
        project_root or ""
    ).rstrip("\\/").casefold()

    # 기존 현재 Agent/프로젝트 카드의 의미는 오늘 사용량으로 유지합니다.
    project = _empty_summary()
    daily = _empty_summary()
    studio = _empty_summary()
    models: dict[str, dict] = {}
    path = usage_log_path()

    if path.exists():
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except Exception:
                    continue

                row_date = str(row.get("date") or "")
                row_project = str(
                    row.get("project_root") or ""
                ).rstrip("\\/").casefold()

                if row_date == today:
                    _accumulate(daily, row)
                    if normalized_project and row_project == normalized_project:
                        _accumulate(project, row)

                if not _usage_period_matches(
                    row_date,
                    scope=normalized_scope,
                    selected_date=selected_date,
                    selected_month=selected_month,
                ):
                    continue

                _accumulate(studio, row)

                model_key = f"{row.get('provider','')}::{row.get('model','')}"
                model_row = models.setdefault(
                    model_key,
                    {
                        **_empty_summary(),
                        "provider": row.get("provider", ""),
                        "model": row.get("model", ""),
                    },
                )
                _accumulate(model_row, row)

    for item in [daily, project, studio, *models.values()]:
        item["cost_usd"] = round(float(item.get("cost_usd") or 0), 8)

    if normalized_scope == "all":
        period_label = "AgentStudio 전체 누적"
    elif normalized_scope == "month":
        period_label = f"AgentStudio {selected_month} 월별"
    elif normalized_scope == "day":
        period_label = f"AgentStudio {selected_date} 일별"
    else:
        period_label = "AgentStudio 오늘 전체"

    return {
        "ok": True,
        "scope": normalized_scope,
        "date": selected_date,
        "month": selected_month,
        "period_label": period_label,
        "project_root": project_root,
        "project": project,
        "daily": daily,
        "studio": studio,
        "models": list(models.values()),
        "pricing_note": (
            "API token usage 기록을 선택한 기간으로 집계합니다. "
            "비용은 모델별 토큰 단가 기준 추정치이며 별도 Tool 요금은 포함하지 않습니다."
        ),
        "pricing_source": "OpenAI official developer model documentation",
        "log_path": str(path),
    }

# ===== v5.243 LLM Request/Response History (10-day retention) =====
from datetime import timedelta
import os
import re
import time
import uuid

_LLM_HISTORY_RETENTION_DAYS = 10
_history_write_lock = threading.Lock()
_history_last_prune_at: datetime | None = None


def _persistent_agentstudio_data_dir() -> Path:
    override = str(os.environ.get("THEANOVA_AGENTSTUDIO_DATA_DIR") or "").strip()
    if override:
        return Path(os.path.expanduser(override)).resolve()

    local_app_data = str(os.environ.get("LOCALAPPDATA") or "").strip()
    if local_app_data:
        return Path(local_app_data) / "THEANOVA" / "AgentStudio"

    app_data = str(os.environ.get("APPDATA") or "").strip()
    if app_data:
        return Path(app_data) / "THEANOVA" / "AgentStudio"

    return Path.home() / ".theanova" / "AgentStudio"


def llm_history_log_path() -> Path:
    # Upgrade ZIP을 교체해도 기록이 사라지지 않는 사용자 영속 영역에 저장합니다.
    path = _persistent_agentstudio_data_dir() / "logs" / "llm_request_history.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _redact_secret_text(value: str) -> str:
    text = str(value or "")
    # Bearer tokens / OpenAI-style keys / env assignments.
    text = re.sub(r"(?i)(Bearer\s+)[A-Za-z0-9._~+/=-]+", r"\1***MASKED***", text)
    text = re.sub(r"\bsk-[A-Za-z0-9_-]{8,}\b", "sk-***MASKED***", text)
    text = re.sub(
        r"(?im)\b([A-Z0-9_]*(?:API_KEY|PASSWORD|SECRET|ACCESS_TOKEN|REFRESH_TOKEN))\s*=\s*([^\r\n]+)",
        lambda m: f"{m.group(1)}=***MASKED***",
        text,
    )
    return text


def _is_secret_key(key: str) -> bool:
    normalized = str(key or "").casefold().replace("-", "_")
    markers = (
        "api_key", "apikey", "password", "secret", "authorization",
        "access_token", "refresh_token", "client_secret", "private_key",
    )
    return any(marker in normalized for marker in markers)


def _safe_jsonable(value: Any, *, depth: int = 0) -> Any:
    if depth > 20:
        return "<max-depth>"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return _redact_secret_text(value)
    if isinstance(value, bytes):
        return f"<bytes:{len(value)}>"
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            key_text = str(key)
            if _is_secret_key(key_text):
                result[key_text] = "***MASKED***"
            else:
                result[key_text] = _safe_jsonable(item, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple, set)):
        return [_safe_jsonable(item, depth=depth + 1) for item in value]

    # LangChain / Pydantic objects.
    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            data = model_dump()
            if isinstance(data, dict):
                # BaseMessage dumps contain useful role/type/content fields.
                return _safe_jsonable(data, depth=depth + 1)
        except Exception:
            pass

    to_json = getattr(value, "to_json", None)
    if callable(to_json):
        try:
            return _safe_jsonable(to_json(), depth=depth + 1)
        except Exception:
            pass

    if hasattr(value, "content"):
        try:
            payload = {
                "type": type(value).__name__,
                "content": getattr(value, "content", ""),
            }
            for attr in ("name", "id", "tool_calls", "additional_kwargs"):
                item = getattr(value, attr, None)
                if item not in (None, "", [], {}):
                    payload[attr] = item
            return _safe_jsonable(payload, depth=depth + 1)
        except Exception:
            pass

    return _redact_secret_text(str(value))


def _request_snapshot(args: tuple, kwargs: dict, provider: str, task: str, model: Any) -> dict:
    model_name = _model_name(model)
    input_value = args[0] if args else kwargs.get("input")
    options = {key: value for key, value in kwargs.items() if key != "input"}
    return {
        "provider": str(provider or "").lower(),
        "model": model_name,
        "task": str(task or ""),
        "input": _safe_jsonable(input_value),
        "options": _safe_jsonable(options),
    }


def _response_snapshot(result: Any) -> dict:
    if result is None:
        return {}
    payload = {
        "type": type(result).__name__,
        "content": getattr(result, "content", None),
        "response_metadata": getattr(result, "response_metadata", None),
        "usage_metadata": getattr(result, "usage_metadata", None),
    }
    for attr in ("id", "name", "tool_calls", "additional_kwargs"):
        item = getattr(result, attr, None)
        if item not in (None, "", [], {}):
            payload[attr] = item
    return _safe_jsonable(payload)


def _history_cutoff(now: datetime | None = None, days: int = _LLM_HISTORY_RETENTION_DAYS) -> datetime:
    current = now or datetime.now().astimezone()
    return current - timedelta(days=max(1, int(days)))


def _parse_history_timestamp(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value or ""))
        if parsed.tzinfo is None:
            parsed = parsed.astimezone()
        return parsed
    except Exception:
        return None


def prune_llm_history(*, force: bool = False) -> dict:
    global _history_last_prune_at
    now = datetime.now().astimezone()
    if (
        not force
        and _history_last_prune_at is not None
        and (now - _history_last_prune_at).total_seconds() < 3600
    ):
        return {"ok": True, "skipped": True}

    path = llm_history_log_path()
    cutoff = _history_cutoff(now)
    kept: list[str] = []
    removed = 0
    if path.exists():
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    row = json.loads(stripped)
                except Exception:
                    removed += 1
                    continue
                timestamp = _parse_history_timestamp(row.get("timestamp"))
                if timestamp is None or timestamp >= cutoff:
                    kept.append(json.dumps(row, ensure_ascii=False))
                else:
                    removed += 1
        temp = path.with_suffix(path.suffix + ".tmp")
        with temp.open("w", encoding="utf-8") as handle:
            if kept:
                handle.write("\n".join(kept) + "\n")
        temp.replace(path)
    _history_last_prune_at = now
    return {"ok": True, "removed": removed, "kept": len(kept), "retention_days": _LLM_HISTORY_RETENTION_DAYS}


def record_llm_exchange(
    *,
    provider: str,
    task: str,
    model: Any,
    request: dict,
    result: Any = None,
    usage_row: dict | None = None,
    error: BaseException | None = None,
    started_at: datetime | None = None,
    elapsed_ms: int = 0,
) -> dict:
    now = datetime.now().astimezone()
    context = dict(_usage_context.get() or {})
    model_name = _model_name(model)
    row = {
        "id": uuid.uuid4().hex,
        "timestamp": now.isoformat(),
        "date": now.date().isoformat(),
        "started_at": (started_at or now).isoformat(),
        "elapsed_ms": max(0, int(elapsed_ms or 0)),
        "status": "error" if error else "success",
        "provider": str(provider or "").lower(),
        "model": model_name,
        "task": str(task or ""),
        "project_root": str(context.get("project_root") or ""),
        "thread_id": str(context.get("thread_id") or ""),
        "operation": str(context.get("operation") or ""),
        "request": _safe_jsonable(request),
        "response": _response_snapshot(result) if error is None else {},
        "usage": _safe_jsonable(usage_row or {}),
        "error": (
            {
                "type": type(error).__name__,
                "message": _redact_secret_text(str(error)),
            }
            if error else None
        ),
    }

    with _history_write_lock:
        prune_llm_history()
        path = llm_history_log_path()
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def _safe_record_llm_exchange(**kwargs) -> dict | None:
    try:
        return record_llm_exchange(**kwargs)
    except Exception as history_error:
        # Observability must never break the LLM call itself.
        print(f"[경고] LLM 요청/응답 기록 저장 실패: {history_error}")
        return None


def read_llm_history(
    *,
    days: int = _LLM_HISTORY_RETENTION_DAYS,
    project_root: str = "",
    task: str = "",
    limit: int = 300,
) -> dict:
    normalized_days = min(max(int(days or _LLM_HISTORY_RETENTION_DAYS), 1), _LLM_HISTORY_RETENTION_DAYS)
    normalized_limit = min(max(int(limit or 300), 1), 1000)
    normalized_project = str(project_root or "").rstrip("\\/").casefold()
    normalized_task = str(task or "").strip().casefold()
    now = datetime.now().astimezone()
    cutoff = _history_cutoff(now, normalized_days)

    with _history_write_lock:
        prune_llm_history(force=True)
        path = llm_history_log_path()
        rows: list[dict] = []
        if path.exists():
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    try:
                        row = json.loads(line)
                    except Exception:
                        continue
                    timestamp = _parse_history_timestamp(row.get("timestamp"))
                    if timestamp is not None and timestamp < cutoff:
                        continue
                    row_project = str(row.get("project_root") or "").rstrip("\\/").casefold()
                    if normalized_project and row_project != normalized_project:
                        continue
                    if normalized_task and str(row.get("task") or "").casefold() != normalized_task:
                        continue
                    rows.append(row)

    rows.sort(key=lambda item: str(item.get("timestamp") or ""), reverse=True)
    total_count = len(rows)
    rows = rows[:normalized_limit]
    return {
        "ok": True,
        "retention_days": _LLM_HISTORY_RETENTION_DAYS,
        "requested_days": normalized_days,
        "count": len(rows),
        "total_count": total_count,
        "truncated": total_count > len(rows),
        "project_root": project_root,
        "task": task,
        "items": rows,
        "log_path": str(llm_history_log_path()),
        "note": "실제 LangChain LLM 호출의 요청/응답을 저장하며 Secret 패턴은 마스킹합니다.",
    }
