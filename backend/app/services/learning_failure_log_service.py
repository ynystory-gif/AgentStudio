from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def learning_job_log_dir() -> Path:
    path = _project_root() / "logs" / "learning_jobs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_learning_job_failure(job: dict[str, Any], *, kind: str = "problem_collection") -> str:
    job_id = str(job.get("id") or "unknown")
    path = learning_job_log_dir() / f"{kind}_{job_id}.log"
    if path.exists():
        return str(path)
    payload = {
        "created_at": datetime.now().isoformat(),
        "pc_name": os.environ.get("AGENTSTUDIO_PC_NAME", ""),
        "kind": kind,
        "job_id": job_id,
        "status": job.get("status"),
        "stage": job.get("stage"),
        "progress": job.get("progress"),
        "message": job.get("message"),
        "error": job.get("error"),
        "current_topic": job.get("current_topic"),
        "total_topics": job.get("total_topics"),
        "result": job.get("result") or {},
        "job": job,
    }
    lines = [
        "THEANOVA AgentStudio - LLM Learning Failure Diagnostic",
        "=" * 72,
        f"CreatedAt: {payload['created_at']}",
        f"PC: {payload['pc_name']}",
        f"Kind: {kind}",
        f"JobId: {job_id}",
        f"Status: {payload['status']}",
        f"Stage: {payload['stage']}",
        f"Progress: {payload['progress']}",
        f"Message: {payload['message']}",
        f"Error: {payload['error']}",
        "",
        "Result / Errors:",
        json.dumps(payload.get("result") or {}, ensure_ascii=False, indent=2, default=str),
        "",
        "Full Job:",
        json.dumps(payload.get("job") or {}, ensure_ascii=False, indent=2, default=str),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def attach_failure_log(job: dict[str, Any], *, kind: str = "problem_collection") -> dict[str, Any]:
    result = dict(job or {})
    if str(result.get("status") or "").lower() != "failed":
        return result
    try:
        log_path = write_learning_job_failure(result, kind=kind)
        result["log_path"] = log_path
        base = str(result.get("message") or result.get("error") or "작업에 실패했습니다.").strip()
        if "실패 로그:" not in base:
            result["message"] = f"{base} · 실패 로그: {log_path}"
    except Exception as exc:
        result["log_write_error"] = str(exc) or type(exc).__name__
    return result
