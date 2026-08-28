from __future__ import annotations

from datetime import datetime
from typing import Any

import psycopg

from app.core import database as db_runtime
from app.core.machine_identity import current_pc_name
from app.services import llm_usage_service as legacy


_TABLE_READY_FOR: set[tuple[str, str]] = set()


def _connection_target() -> tuple[str, str]:
    url = str(db_runtime.database_url or "").strip()
    if url.startswith("postgresql+psycopg://"):
        url = url.replace("postgresql+psycopg://", "postgresql://", 1)
    schema = str(db_runtime.runtime_schema or "").strip()
    return url, schema


def _connect():
    url, schema = _connection_target()
    if not url:
        raise RuntimeError("LLM 사용량을 저장할 Runtime DB가 설정되어 있지 않습니다.")
    conn = psycopg.connect(url, connect_timeout=5)
    if schema:
        safe_schema = schema.replace('"', '""')
        conn.execute(f'SET search_path TO "{safe_schema}", extensions, public')
    return conn


def _ensure_table(conn) -> None:
    key = _connection_target()
    if key in _TABLE_READY_FOR:
        return
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS llm_usage_records (
            id BIGSERIAL PRIMARY KEY,
            pc_name VARCHAR(255) NOT NULL,
            occurred_at TIMESTAMPTZ NOT NULL,
            usage_date DATE NOT NULL,
            provider VARCHAR(100) NOT NULL DEFAULT '',
            model VARCHAR(200) NOT NULL DEFAULT '',
            task VARCHAR(200) NOT NULL DEFAULT '',
            paid BOOLEAN NOT NULL DEFAULT FALSE,
            input_tokens BIGINT NOT NULL DEFAULT 0,
            cached_input_tokens BIGINT NOT NULL DEFAULT 0,
            output_tokens BIGINT NOT NULL DEFAULT 0,
            total_tokens BIGINT NOT NULL DEFAULT 0,
            cost_usd DOUBLE PRECISION NOT NULL DEFAULT 0,
            project_root TEXT NOT NULL DEFAULT '',
            thread_id VARCHAR(255) NOT NULL DEFAULT '',
            operation VARCHAR(255) NOT NULL DEFAULT ''
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS ix_llm_usage_records_pc_date ON llm_usage_records (pc_name, usage_date)")
    conn.execute("CREATE INDEX IF NOT EXISTS ix_llm_usage_records_pc_model ON llm_usage_records (pc_name, provider, model)")
    conn.commit()
    _TABLE_READY_FOR.add(key)


def _build_usage_row(*, result: Any, provider: str, task: str, model: Any) -> dict:
    usage = legacy._extract_usage(result)
    model_name = legacy._model_name(model)
    provider_name = str(provider or "").lower()
    paid = provider_name == "openai"
    now = datetime.now().astimezone()
    context = dict(legacy._usage_context.get() or {})
    return {
        "timestamp": now.isoformat(),
        "date": now.date().isoformat(),
        "pc_name": current_pc_name(),
        "provider": provider_name,
        "model": model_name,
        "task": str(task or ""),
        "paid": paid,
        "input_tokens": int(usage.get("input_tokens") or 0),
        "cached_input_tokens": int(usage.get("cached_input_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
        "cost_usd": legacy._cost_usd(model_name, usage) if paid else 0.0,
        "project_root": str(context.get("project_root") or ""),
        "thread_id": str(context.get("thread_id") or ""),
        "operation": str(context.get("operation") or ""),
    }


def record_llm_usage(*, result: Any, provider: str, task: str, model: Any) -> dict:
    row = _build_usage_row(result=result, provider=provider, task=task, model=model)
    if row["total_tokens"] <= 0:
        return row
    try:
        with _connect() as conn:
            _ensure_table(conn)
            conn.execute(
                """
                INSERT INTO llm_usage_records (
                    pc_name, occurred_at, usage_date, provider, model, task, paid,
                    input_tokens, cached_input_tokens, output_tokens, total_tokens,
                    cost_usd, project_root, thread_id, operation
                ) VALUES (
                    %(pc_name)s, %(timestamp)s, %(date)s, %(provider)s, %(model)s, %(task)s, %(paid)s,
                    %(input_tokens)s, %(cached_input_tokens)s, %(output_tokens)s, %(total_tokens)s,
                    %(cost_usd)s, %(project_root)s, %(thread_id)s, %(operation)s
                )
                """,
                row,
            )
            conn.commit()
    except Exception as exc:
        # Usage accounting must never break the actual LLM request.
        print(f"[경고] PC별 LLM 사용량 DB 저장 실패: {exc}")
    return row


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
    for key in ("input_tokens", "cached_input_tokens", "output_tokens", "total_tokens"):
        summary[key] += int(row.get(key) or 0)
    summary["cost_usd"] += float(row.get("cost_usd") or 0)


def _period_matches(row_date: str, scope: str, selected_date: str, selected_month: str) -> bool:
    if scope == "all":
        return True
    if scope == "month":
        return row_date.startswith(selected_month + "-")
    return row_date == selected_date


def read_usage_summary(project_root: str = "", date: str = "", scope: str = "today", month: str = "") -> dict:
    today = datetime.now().astimezone().date().isoformat()
    normalized_scope = str(scope or "today").strip().lower()
    if normalized_scope not in {"today", "all", "month", "day"}:
        normalized_scope = "today"
    selected_date = (date or "").strip() or today
    selected_month = (month or "").strip() or selected_date[:7]
    if normalized_scope == "today":
        selected_date = today
        selected_month = today[:7]

    pc_name = current_pc_name()
    normalized_project = str(project_root or "").rstrip("\\/").casefold()
    project = _empty_summary()
    daily = _empty_summary()
    studio = _empty_summary()
    models: dict[str, dict] = {}

    try:
        with _connect() as conn:
            _ensure_table(conn)
            rows = conn.execute(
                """
                SELECT usage_date, provider, model, paid, input_tokens, cached_input_tokens,
                       output_tokens, total_tokens, cost_usd, project_root
                FROM llm_usage_records
                WHERE pc_name = %s
                ORDER BY occurred_at ASC
                """,
                (pc_name,),
            ).fetchall()
            for data in rows:
                row = {
                    "date": str(data[0]), "provider": data[1], "model": data[2], "paid": bool(data[3]),
                    "input_tokens": data[4], "cached_input_tokens": data[5], "output_tokens": data[6],
                    "total_tokens": data[7], "cost_usd": data[8], "project_root": data[9],
                }
                row_date = row["date"]
                row_project = str(row.get("project_root") or "").rstrip("\\/").casefold()
                if row_date == today:
                    _accumulate(daily, row)
                    if normalized_project and row_project == normalized_project:
                        _accumulate(project, row)
                if not _period_matches(row_date, normalized_scope, selected_date, selected_month):
                    continue
                _accumulate(studio, row)
                model_key = f"{row.get('provider','')}::{row.get('model','')}"
                model_row = models.setdefault(model_key, {**_empty_summary(), "provider": row.get("provider", ""), "model": row.get("model", "")})
                _accumulate(model_row, row)
    except Exception as exc:
        return {"ok": False, "message": f"LLM 사용량 DB 조회 실패: {exc}", "pc_name": pc_name, "storage": "runtime_db_pc_scoped"}

    for item in [daily, project, studio, *models.values()]:
        item["cost_usd"] = round(float(item.get("cost_usd") or 0), 8)
    if normalized_scope == "all":
        period_label = "현재 PC 전체 누적"
    elif normalized_scope == "month":
        period_label = f"현재 PC {selected_month} 월별"
    elif normalized_scope == "day":
        period_label = f"현재 PC {selected_date} 일별"
    else:
        period_label = "현재 PC 오늘 전체"
    return {
        "ok": True,
        "scope": normalized_scope,
        "date": selected_date,
        "month": selected_month,
        "period_label": period_label,
        "project_root": project_root,
        "pc_name": pc_name,
        "project": project,
        "daily": daily,
        "studio": studio,
        "models": list(models.values()),
        "pricing_note": "현재 PC의 Runtime DB LLM 사용량을 집계합니다. 비용은 토큰 단가 기준 추정치입니다.",
        "pricing_source": "OpenAI official developer model documentation",
        "storage": "runtime_db_pc_scoped",
        "log_path": "",
    }


# Patch the existing common usage layer before API routes and LLM services are loaded.
legacy.record_llm_usage = record_llm_usage
legacy.read_usage_summary = read_usage_summary
