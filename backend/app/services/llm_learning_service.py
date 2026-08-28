from __future__ import annotations

import json
import os
import random
import re
import subprocess
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.llm_provider import get_chat_model
from app.services.llm_usage_service import UsageTrackedChatModel, llm_history_log_path


_LOCK = threading.RLock()
_CORRECTION_MARKERS = (
    "아니", "잘못", "틀렸", "다시", "수정해", "요청했는데", "왜", "안된다", "안돼",
    "incorrect", "wrong", "fix", "retry", "not what", "instead",
)
_ERROR_MARKERS = (
    "error", "exception", "traceback", "실패", "오류", "invalid", "not found",
)
_ALLOWED_CASE_STATUS = {"candidate", "confirmed", "rejected"}
_ALLOWED_DATASET_STATUS = {"draft", "review", "validated", "training", "trained", "deployed"}


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def _data_dir() -> Path:
    override = str(os.environ.get("THEANOVA_AGENTSTUDIO_DATA_DIR") or "").strip()
    if override:
        root = Path(os.path.expanduser(override)).resolve()
    else:
        local = str(os.environ.get("LOCALAPPDATA") or "").strip()
        root = Path(local) / "THEANOVA" / "AgentStudio" if local else Path.home() / ".theanova" / "AgentStudio"
    path = root / "learning"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _json_path(name: str) -> Path:
    return _data_dir() / name


def _read_json(name: str, default: Any) -> Any:
    path = _json_path(name)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(name: str, value: Any) -> None:
    path = _json_path(name)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def _flatten_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(_flatten_text(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return " ".join(_flatten_text(item) for item in value)
    return str(value)


def _safe_excerpt(value: Any, limit: int = 2400) -> str:
    text = re.sub(r"\s+", " ", _flatten_text(value)).strip()
    return text[:limit]


def _history_rows(limit: int = 4000) -> list[dict]:
    path = llm_history_log_path()
    if not path.exists():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                rows.append(json.loads(line))
            except Exception:
                continue
    rows.sort(key=lambda row: str(row.get("timestamp") or ""))
    return rows[-max(1, int(limit)):]


def _candidate_reason(row: dict, next_row: dict | None) -> tuple[str, float] | None:
    if str(row.get("status") or "").lower() == "error":
        return "llm_or_tool_error", 0.96
    response_text = _safe_excerpt(row.get("response"), 1600).casefold()
    if any(marker in response_text for marker in _ERROR_MARKERS):
        return "error_signal_in_response", 0.72
    if next_row and str(next_row.get("thread_id") or "") == str(row.get("thread_id") or ""):
        next_request = _safe_excerpt(next_row.get("request"), 1600).casefold()
        if any(marker in next_request for marker in _CORRECTION_MARKERS):
            return "user_correction_after_response", 0.86
    return None


def sync_misjudgment_candidates() -> dict:
    """Convert suspicious LLM history exchanges into reviewable learning candidates.

    A candidate is never considered ground truth. It must be explicitly confirmed before
    problem generation is allowed.
    """
    with _LOCK:
        cases = _read_json("misjudgment_cases.json", [])
        existing_sources = {str(item.get("source_exchange_id") or "") for item in cases}
        rows = _history_rows()
        added = 0
        for index, row in enumerate(rows):
            source_id = str(row.get("id") or "")
            if not source_id or source_id in existing_sources:
                continue
            next_row = rows[index + 1] if index + 1 < len(rows) else None
            signal = _candidate_reason(row, next_row)
            if not signal:
                continue
            reason, confidence = signal
            request_text = _safe_excerpt(row.get("request"))
            response_text = _safe_excerpt(row.get("response") or row.get("error"))
            correction_text = _safe_excerpt(next_row.get("request")) if reason == "user_correction_after_response" else ""
            cases.append({
                "id": uuid.uuid4().hex,
                "created_at": _now(),
                "updated_at": _now(),
                "status": "candidate",
                "provider": str(row.get("provider") or "unknown"),
                "model": str(row.get("model") or "unknown"),
                "task": str(row.get("task") or ""),
                "project_root": str(row.get("project_root") or ""),
                "thread_id": str(row.get("thread_id") or ""),
                "source_exchange_id": source_id,
                "detection_reason": reason,
                "confidence": confidence,
                "user_request": request_text,
                "wrong_output": response_text,
                "correction_evidence": correction_text,
                "expected_output": "",
                "error_type": "unclassified",
                "error_reason": "",
                "domain": "",
                "topic": "",
                "training_eligible": False,
            })
            existing_sources.add(source_id)
            added += 1
        _write_json("misjudgment_cases.json", cases)
        return {"ok": True, "added": added, "total": len(cases), "scanned": len(rows)}


def list_misjudgment_cases(provider: str = "", status: str = "", limit: int = 500) -> dict:
    sync_misjudgment_candidates()
    with _LOCK:
        rows = list(_read_json("misjudgment_cases.json", []))
    if provider:
        rows = [row for row in rows if str(row.get("provider") or "").casefold() == provider.casefold()]
    if status:
        rows = [row for row in rows if str(row.get("status") or "").casefold() == status.casefold()]
    rows.sort(key=lambda row: str(row.get("updated_at") or row.get("created_at") or ""), reverse=True)
    total = len(rows)
    rows = rows[: max(1, min(int(limit or 500), 2000))]
    providers: dict[str, int] = {}
    for row in rows:
        key = f"{row.get('provider','unknown')}::{row.get('model','unknown')}"
        providers[key] = providers.get(key, 0) + 1
    return {"ok": True, "items": rows, "total": total, "providers": providers}


def review_misjudgment_case(case_id: str, patch: dict) -> dict:
    with _LOCK:
        cases = _read_json("misjudgment_cases.json", [])
        target = next((item for item in cases if item.get("id") == case_id), None)
        if not target:
            raise KeyError("오판 후보를 찾을 수 없습니다.")
        status = str(patch.get("status") or target.get("status") or "candidate").lower()
        if status not in _ALLOWED_CASE_STATUS:
            raise ValueError("지원하지 않는 오판 검토 상태입니다.")
        for key in ("expected_output", "error_type", "error_reason", "domain", "topic"):
            if key in patch:
                target[key] = str(patch.get(key) or "").strip()
        target["status"] = status
        target["training_eligible"] = status == "confirmed" and bool(str(target.get("expected_output") or "").strip())
        target["updated_at"] = _now()
        _write_json("misjudgment_cases.json", cases)
        return {"ok": True, "item": target}


def add_manual_misjudgment_case(payload: dict) -> dict:
    provider = str(payload.get("provider") or "unknown").strip().lower()
    model = str(payload.get("model") or "unknown").strip()
    item = {
        "id": uuid.uuid4().hex,
        "created_at": _now(), "updated_at": _now(), "status": "candidate",
        "provider": provider, "model": model, "task": str(payload.get("task") or "manual"),
        "project_root": str(payload.get("project_root") or ""), "thread_id": "", "source_exchange_id": "",
        "detection_reason": "manual", "confidence": 1.0,
        "user_request": str(payload.get("user_request") or "").strip(),
        "wrong_output": str(payload.get("wrong_output") or "").strip(),
        "correction_evidence": str(payload.get("correction_evidence") or "").strip(),
        "expected_output": str(payload.get("expected_output") or "").strip(),
        "error_type": str(payload.get("error_type") or "unclassified"),
        "error_reason": str(payload.get("error_reason") or ""),
        "domain": str(payload.get("domain") or ""), "topic": str(payload.get("topic") or ""),
        "training_eligible": False,
    }
    with _LOCK:
        cases = _read_json("misjudgment_cases.json", [])
        cases.append(item)
        _write_json("misjudgment_cases.json", cases)
    return {"ok": True, "item": item}


def _parse_json_payload(text: str) -> Any:
    value = str(text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.I)
        value = re.sub(r"\s*```$", "", value)
    start_candidates = [pos for pos in (value.find("{"), value.find("[")) if pos >= 0]
    if start_candidates:
        value = value[min(start_candidates):]
    for end_char in ("}", "]"):
        end = value.rfind(end_char)
        if end >= 0:
            candidate = value[: end + 1]
            try:
                return json.loads(candidate)
            except Exception:
                pass
    return json.loads(value)


def _learning_model(provider: str = "ollama") -> UsageTrackedChatModel:
    raw = get_chat_model(provider)
    return UsageTrackedChatModel(raw, provider, "llm_learning_dataset_generation")


def analyze_learning_scope(case: dict, provider: str = "ollama") -> dict:
    prompt = f"""당신은 THEANOVA AgentStudio의 LLM 학습 데이터 설계 Validator입니다.
아래 확정 오판 한 건을 단순히 같은 문장으로 변형하지 말고, 모델이 취약한 지식/판단 범위를 넓게 정의하세요.
반드시 JSON 객체만 반환하세요.
필드: domain, topic, root_cause, learning_objective, subtopics(6~15개), variation_axes(5~10개), pitfalls(5~10개), prerequisites(0~8개).

사용자 요청: {case.get('user_request','')}
잘못된 결과: {case.get('wrong_output','')}
기대 결과: {case.get('expected_output','')}
오류 유형: {case.get('error_type','')}
오류 원인: {case.get('error_reason','')}
"""
    result = _learning_model(provider).invoke(prompt)
    parsed = _parse_json_payload(getattr(result, "content", str(result)))
    if not isinstance(parsed, dict):
        raise ValueError("학습 범위 분석 결과가 JSON 객체가 아닙니다.")
    return parsed


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


def generate_problem_dataset(case_id: str, target_count: int = 100, provider: str = "ollama") -> dict:
    target_count = max(10, min(int(target_count or 100), 2000))
    with _LOCK:
        cases = _read_json("misjudgment_cases.json", [])
        case = next((item for item in cases if item.get("id") == case_id), None)
    if not case:
        raise KeyError("오판 후보를 찾을 수 없습니다.")
    if case.get("status") != "confirmed" or not case.get("training_eligible"):
        raise ValueError("오판이 확정되고 기대 결과가 검증된 경우에만 대량 문제를 생성할 수 있습니다.")

    scope = analyze_learning_scope(case, provider=provider)
    generated: list[dict] = []
    fingerprints: set[str] = set()
    batch_size = 20
    attempts = 0
    while len(generated) < target_count and attempts < max(4, (target_count // batch_size) + 5):
        attempts += 1
        need = min(batch_size, target_count - len(generated))
        prompt = f"""THEANOVA AgentStudio 학습 데이터 생성기입니다.
확정 오판의 취약 범위를 학습하기 위한 서로 다른 문제 {need}개를 만드세요.
단순 문장 치환/동의어 바꾸기 금지. 실제 개발/Agent/Tool/DB/예외 상황을 다양하게 구성하세요.
난이도 easy/medium/hard, 유형 concept/scenario/code/tool_selection/debug/edge_case를 고르게 섞으세요.
정답은 실제 학습에 사용할 수 있을 만큼 정확하고 직접적이어야 합니다.
JSON 배열만 반환하세요. 각 항목 필드: instruction,input,output,domain,topic,subtopic,difficulty,problem_type.

학습 범위:
{json.dumps(scope, ensure_ascii=False)}

원본 확정 사례:
사용자 요청={case.get('user_request','')}
잘못된 결과={case.get('wrong_output','')}
기대 결과={case.get('expected_output','')}
"""
        result = _learning_model(provider).invoke(prompt)
        parsed = _parse_json_payload(getattr(result, "content", str(result)))
        if isinstance(parsed, dict):
            parsed = parsed.get("items") or parsed.get("problems") or []
        if not isinstance(parsed, list):
            continue
        for raw in parsed:
            problem = _validate_problem(raw)
            if not problem:
                continue
            fingerprint = re.sub(r"\W+", "", (problem["instruction"] + problem["input"]).casefold())[:600]
            if not fingerprint or fingerprint in fingerprints:
                continue
            fingerprints.add(fingerprint)
            generated.append(problem)
            if len(generated) >= target_count:
                break

    dataset = {
        "id": uuid.uuid4().hex,
        "created_at": _now(), "updated_at": _now(),
        "status": "review",
        "source_case_id": case_id,
        "provider": provider,
        "source_provider": case.get("provider"), "source_model": case.get("model"),
        "scope": scope,
        "target_count": target_count, "problem_count": len(generated),
        "problems": generated,
        "validation": {"approved": 0, "rejected": 0, "pending": len(generated)},
        "split": {},
        "training": {},
        "evaluation": {},
        "deployment": {},
    }
    with _LOCK:
        datasets = _read_json("learning_datasets.json", [])
        datasets.append(dataset)
        _write_json("learning_datasets.json", datasets)
    return {"ok": True, "dataset": dataset}


def list_datasets() -> dict:
    with _LOCK:
        rows = list(_read_json("learning_datasets.json", []))
    rows.sort(key=lambda item: str(item.get("updated_at") or item.get("created_at") or ""), reverse=True)
    return {"ok": True, "items": rows, "total": len(rows)}


def validate_dataset(dataset_id: str, approved_problem_ids: list[str] | None = None) -> dict:
    with _LOCK:
        datasets = _read_json("learning_datasets.json", [])
        dataset = next((item for item in datasets if item.get("id") == dataset_id), None)
        if not dataset:
            raise KeyError("Dataset을 찾을 수 없습니다.")
        approved_set = set(approved_problem_ids or [])
        if not approved_set:
            approved_set = {str(item.get("id")) for item in dataset.get("problems", [])}
        approved = 0
        for problem in dataset.get("problems", []):
            problem["validated"] = str(problem.get("id")) in approved_set
            if problem["validated"]:
                approved += 1
        if approved < 10:
            raise ValueError("검증 완료 문제는 최소 10개 이상이어야 합니다.")
        dataset["status"] = "validated"
        dataset["validation"] = {
            "approved": approved,
            "rejected": len(dataset.get("problems", [])) - approved,
            "pending": 0,
            "validated_at": _now(),
        }
        dataset["updated_at"] = _now()
        _write_json("learning_datasets.json", datasets)
        return {"ok": True, "dataset": dataset}


def _split_items(items: list[dict], seed: int = 5413) -> tuple[list[dict], list[dict], list[dict]]:
    values = list(items)
    random.Random(seed).shuffle(values)
    count = len(values)
    train_end = max(1, int(count * 0.8))
    validation_end = min(count, train_end + max(1, int(count * 0.1)))
    return values[:train_end], values[train_end:validation_end], values[validation_end:]


def prepare_training(dataset_id: str, base_model: str = "") -> dict:
    settings = get_settings()
    with _LOCK:
        datasets = _read_json("learning_datasets.json", [])
        dataset = next((item for item in datasets if item.get("id") == dataset_id), None)
        if not dataset:
            raise KeyError("Dataset을 찾을 수 없습니다.")
        if dataset.get("status") != "validated":
            raise ValueError("검증 완료(validated) Dataset만 학습 단계로 이동할 수 있습니다.")
        items = [item for item in dataset.get("problems", []) if item.get("validated")]
        train, validation, test = _split_items(items)
        out = _data_dir() / "datasets" / dataset_id
        out.mkdir(parents=True, exist_ok=True)
        for name, rows in (("train", train), ("validation", validation), ("test", test)):
            with (out / f"{name}.jsonl").open("w", encoding="utf-8") as handle:
                for item in rows:
                    payload = {"instruction": item["instruction"], "input": item.get("input", ""), "output": item["output"]}
                    handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        selected_base = str(base_model or settings.ollama_model or "qwen2.5:7b")
        hf_base = {
            "qwen2.5:7b": "Qwen/Qwen2.5-7B-Instruct",
            "qwen2.5:3b": "Qwen/Qwen2.5-3B-Instruct",
            "qwen2.5:1.5b": "Qwen/Qwen2.5-1.5B-Instruct",
        }.get(selected_base.lower(), selected_base)
        manifest = {
            "dataset_id": dataset_id,
            "created_at": _now(),
            "ollama_base_model": selected_base,
            "training_base_model": hf_base,
            "method": "QLoRA",
            "split": {"train": len(train), "validation": len(validation), "test": len(test)},
            "dataset_dir": str(out),
            "adapter_dir": str(out / "adapter"),
            "gate": "evaluation_pass_required_before_ollama_apply",
        }
        (out / "training_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        dataset["status"] = "training"
        dataset["split"] = manifest["split"]
        dataset["training"] = manifest
        dataset["updated_at"] = _now()
        _write_json("learning_datasets.json", datasets)
        return {"ok": True, "manifest": manifest}


def record_evaluation(dataset_id: str, baseline_score: float, trained_score: float, minimum_gain: float = 0.03) -> dict:
    with _LOCK:
        datasets = _read_json("learning_datasets.json", [])
        dataset = next((item for item in datasets if item.get("id") == dataset_id), None)
        if not dataset:
            raise KeyError("Dataset을 찾을 수 없습니다.")
        baseline = float(baseline_score)
        trained = float(trained_score)
        gain = trained - baseline
        passed = trained >= baseline and gain >= float(minimum_gain)
        dataset["evaluation"] = {
            "baseline_score": baseline, "trained_score": trained, "gain": gain,
            "minimum_gain": float(minimum_gain), "passed": passed, "evaluated_at": _now(),
        }
        dataset["status"] = "trained" if passed else "validated"
        dataset["updated_at"] = _now()
        _write_json("learning_datasets.json", datasets)
        return {"ok": True, "passed": passed, "evaluation": dataset["evaluation"]}


def apply_to_ollama(dataset_id: str, model_name: str, adapter_path: str = "") -> dict:
    """Register an evaluated adapter with Ollama. Never deploys without an evaluation pass."""
    with _LOCK:
        datasets = _read_json("learning_datasets.json", [])
        dataset = next((item for item in datasets if item.get("id") == dataset_id), None)
        if not dataset:
            raise KeyError("Dataset을 찾을 수 없습니다.")
        if not bool((dataset.get("evaluation") or {}).get("passed")):
            raise ValueError("기존 모델 대비 평가 Gate를 통과한 학습 모델만 Ollama에 적용할 수 있습니다.")
        training = dataset.get("training") or {}
        adapter = Path(adapter_path or training.get("adapter_dir") or "")
        if not adapter.exists():
            raise ValueError("학습 Adapter 경로가 존재하지 않습니다. 실제 학습 완료 후 적용하세요.")
        base_model = str(training.get("ollama_base_model") or get_settings().ollama_model)
        model_dir = _data_dir() / "models" / dataset_id
        model_dir.mkdir(parents=True, exist_ok=True)
        modelfile = model_dir / "Modelfile"
        modelfile.write_text(f"FROM {base_model}\nADAPTER {adapter}\nPARAMETER temperature 0\n", encoding="utf-8")
        completed = subprocess.run(
            ["ollama", "create", model_name, "-f", str(modelfile)],
            capture_output=True, text=True, timeout=600, check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError((completed.stderr or completed.stdout or "ollama create 실패").strip())
        dataset["status"] = "deployed"
        dataset["deployment"] = {
            "model_name": model_name, "base_model": base_model, "adapter_path": str(adapter),
            "applied_at": _now(), "stdout": (completed.stdout or "")[-2000:],
        }
        dataset["updated_at"] = _now()
        _write_json("learning_datasets.json", datasets)
        return {"ok": True, "deployment": dataset["deployment"]}


def learning_summary() -> dict:
    cases = list_misjudgment_cases(limit=2000)["items"]
    datasets = list_datasets()["items"]
    return {
        "ok": True,
        "cases": {
            "candidate": sum(1 for item in cases if item.get("status") == "candidate"),
            "confirmed": sum(1 for item in cases if item.get("status") == "confirmed"),
            "rejected": sum(1 for item in cases if item.get("status") == "rejected"),
        },
        "datasets": {status: sum(1 for item in datasets if item.get("status") == status) for status in _ALLOWED_DATASET_STATUS},
        "current_ollama_model": get_settings().ollama_model,
        "current_strategy": get_settings().ai_provider_strategy,
        "data_dir": str(_data_dir()),
        "safety_gate": "confirmed case -> validated dataset -> evaluation pass -> ollama apply",
    }
