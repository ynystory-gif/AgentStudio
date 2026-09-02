from __future__ import annotations

"""Repair fine-tune readiness from legacy validated Dataset state and select a CUDA Python.

This bridge intentionally loads after ``learning_finetune_paths_bridge`` and before the
fine-tune functions are imported by the API router.

It fixes two compatibility gaps:
1) Older validated Datasets can show ``2 approved / 0 pending`` in the UI while their
   normalized ``llm_learning_problems.validated`` flags are still false. The Dataset
   validation result is authoritative and is reconciled back into normalized rows.
2) The FastAPI interpreter may have CPU-only PyTorch even when an AgentStudio project
   venv has CUDA PyTorch. Candidate Python interpreters are probed and the CUDA-capable
   one is used for both the fine-tune worker and its package installation.
"""

import json
import os
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.learning_entities import LlmLearningDataset, LlmLearningProblem
from app.services.learning_relational_schema_service import assert_learning_relational_schema_ready
from app.services import learning_finetune_job_service as finetune


_ORIGINAL_CONFIGURED_CAPABILITY = finetune.get_weight_finetune_capability
_ORIGINAL_INSTALL_RUNTIME = finetune._install_finetune_runtime_sync
_ORIGINAL_RUN_WORKER = finetune._run_worker_sync


def _fingerprint(instruction: str, input_text: str, output_text: str) -> str:
    payload = "\n".join([instruction.strip(), input_text.strip(), output_text.strip()]).casefold()
    import hashlib
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _validated_training_rows_reconciled() -> tuple[list[dict], list[LlmLearningDataset]]:
    """Use Dataset validation state as source of truth and repair normalized flags."""
    await assert_learning_relational_schema_ready()
    async with SessionLocal() as session:
        datasets = (
            await session.execute(
                select(LlmLearningDataset)
                .where(LlmLearningDataset.status == "validated")
                .order_by(LlmLearningDataset.created_at.asc())
            )
        ).scalars().all()
        if not datasets:
            return [], []

        dataset_ids = [str(row.id) for row in datasets]
        normalized = (
            await session.execute(
                select(LlmLearningProblem)
                .where(LlmLearningProblem.dataset_id.in_(dataset_ids))
                .order_by(LlmLearningProblem.created_at.asc())
            )
        ).scalars().all()
        normalized_by_dataset: dict[str, list[LlmLearningProblem]] = {}
        for row in normalized:
            normalized_by_dataset.setdefault(str(row.dataset_id), []).append(row)

        rows: list[dict] = []
        used_dataset_ids: set[str] = set()
        seen: set[str] = set()
        changed = False

        for dataset in datasets:
            dataset_id = str(dataset.id)
            validation = dict(dataset.validation_json or {})
            approved = int(validation.get("approved") or 0)
            legacy_problems = [item for item in list(dataset.problems_json or []) if isinstance(item, dict)]

            # A Dataset marked validated with no explicit approved count is a legacy case.
            # In that case every structurally valid problem is treated as approved.
            if approved <= 0 and str(dataset.status or "").lower() == "validated":
                approved = len([
                    item for item in legacy_problems
                    if str(item.get("instruction") or "").strip()
                    and str(item.get("output") or "").strip()
                ])

            problem_rows = normalized_by_dataset.get(dataset_id, [])
            structurally_valid_rows = [
                row for row in problem_rows
                if str(row.instruction or "").strip() and str(row.output_text or "").strip()
            ]

            # Reconcile normalized flags from the Dataset-level approval count. When the
            # UI says 2 approved and there are 2 valid normalized rows, both must be true.
            if approved > 0 and structurally_valid_rows:
                for index, problem in enumerate(structurally_valid_rows):
                    should_validate = index < approved
                    if bool(problem.validated) != should_validate:
                        problem.validated = should_validate
                        problem.updated_at = datetime.utcnow()
                        changed = True

            selected_normalized = [row for row in structurally_valid_rows if bool(row.validated)]
            for problem in selected_normalized:
                instruction = str(problem.instruction or "").strip()
                output = str(problem.output_text or "").strip()
                input_text = str(problem.input_text or "").strip()
                fp = _fingerprint(instruction, input_text, output)
                if fp in seen:
                    continue
                seen.add(fp)
                rows.append({
                    "id": str(problem.id),
                    "dataset_id": dataset_id,
                    "group_id": str(problem.group_id or dataset.group_id or ""),
                    "source_case_id": str(problem.source_case_id or dataset.source_case_id or ""),
                    "instruction": instruction,
                    "input": input_text,
                    "output": output,
                })
                used_dataset_ids.add(dataset_id)

            # Compatibility source: validated Dataset JSON. This is needed for historical
            # rows created before normalized problem validation existed.
            already_for_dataset = sum(1 for row in rows if row["dataset_id"] == dataset_id)
            remaining = max(0, approved - already_for_dataset)
            if remaining > 0:
                candidates = [
                    item for item in legacy_problems
                    if item.get("validated") is not False
                    and str(item.get("instruction") or "").strip()
                    and str(item.get("output") or "").strip()
                ]
                for item in candidates:
                    if remaining <= 0:
                        break
                    instruction = str(item.get("instruction") or "").strip()
                    output = str(item.get("output") or "").strip()
                    input_text = str(item.get("input") or "").strip()
                    fp = _fingerprint(instruction, input_text, output)
                    if fp in seen:
                        continue
                    seen.add(fp)
                    rows.append({
                        "id": str(item.get("id") or uuid.uuid4().hex),
                        "dataset_id": dataset_id,
                        "group_id": str(dataset.group_id or ""),
                        "source_case_id": str(dataset.source_case_id or ""),
                        "instruction": instruction,
                        "input": input_text,
                        "output": output,
                    })
                    used_dataset_ids.add(dataset_id)
                    remaining -= 1

        if changed:
            await session.commit()

    dataset_by_id = {str(row.id): row for row in datasets}
    used = [dataset_by_id[dataset_id] for dataset_id in used_dataset_ids if dataset_id in dataset_by_id]
    used.sort(key=lambda row: row.created_at or datetime.min)
    return rows, used


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _python_candidates() -> list[Path]:
    root = _repo_root()
    raw = [
        Path(sys.executable),
        root / ".venv" / "Scripts" / "python.exe",
        root / "backend" / ".venv" / "Scripts" / "python.exe",
    ]
    # Also inspect VIRTUAL_ENV and PATH-resolved python without assuming either is valid.
    virtual_env = str(os.environ.get("VIRTUAL_ENV") or "").strip()
    if virtual_env:
        raw.append(Path(virtual_env) / "Scripts" / "python.exe")
    try:
        import shutil
        found = shutil.which("python")
        if found:
            raw.append(Path(found))
    except Exception:
        pass

    seen: set[str] = set()
    result: list[Path] = []
    for path in raw:
        try:
            resolved = path.resolve()
        except Exception:
            resolved = path
        key = str(resolved).lower()
        if key in seen or not resolved.exists():
            continue
        seen.add(key)
        result.append(resolved)
    return result


def _probe_python(path: Path) -> dict:
    code = (
        "import json\n"
        "try:\n"
        " import torch\n"
        " ok=bool(torch.cuda.is_available())\n"
        " name=str(torch.cuda.get_device_name(0)) if ok else ''\n"
        " mem=round(float(torch.cuda.get_device_properties(0).total_memory)/(1024**3),1) if ok else 0\n"
        " print(json.dumps({'ok':ok,'name':name,'memory_gb':mem,'torch':str(torch.__version__),'cuda':str(torch.version.cuda or '')}))\n"
        "except Exception as e:\n"
        " print(json.dumps({'ok':False,'error':str(e)}))\n"
    )
    try:
        completed = subprocess.run(
            [str(path), "-c", code],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
            env=os.environ.copy(),
        )
        lines = [line.strip() for line in str(completed.stdout or "").splitlines() if line.strip()]
        payload = json.loads(lines[-1]) if lines else {"ok": False, "error": "empty output"}
        payload["python"] = str(path)
        return payload
    except Exception as exc:
        return {"ok": False, "python": str(path), "error": str(exc)}


def _select_finetune_python() -> dict:
    probes = [_probe_python(path) for path in _python_candidates()]
    selected = next((item for item in probes if item.get("ok")), None)
    if selected is None:
        selected = probes[0] if probes else {"ok": False, "python": sys.executable, "error": "Python candidate not found"}
    os.environ["AGENTSTUDIO_FINETUNE_PYTHON"] = str(selected.get("python") or sys.executable)
    return {**selected, "candidates": probes}


def _selected_python() -> str:
    value = str(os.environ.get("AGENTSTUDIO_FINETUNE_PYTHON") or "").strip()
    if value and Path(value).exists():
        return value
    return str(_select_finetune_python().get("python") or sys.executable)


def _install_runtime_with_selected_python(job_id: str) -> None:
    marker = finetune._runtime_marker()
    python_exe = _selected_python()
    if marker.exists():
        finetune._append_log(job_id, f"파인튜닝 전용 Python 패키지 캐시 확인 완료 · {python_exe}")
        return
    target = finetune._package_dir()
    command = [
        python_exe,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--target",
        str(target),
        *finetune._FINETUNE_REQUIREMENTS,
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=os.environ.copy(),
    )
    if process.stdout is None:
        raise RuntimeError("파인튜닝 패키지 설치 출력을 읽을 수 없습니다.")
    for line in process.stdout:
        value = line.strip()
        if value:
            finetune._append_log(job_id, value)
    code = process.wait()
    if code != 0:
        raise RuntimeError(f"파인튜닝 전용 패키지 설치 실패 (ExitCode={code})")
    marker.write_text(datetime.utcnow().isoformat(), encoding="utf-8")


def _run_worker_with_selected_python(job_id: str, phase: str, progress_start: int, progress_end: int, args: list[str]) -> None:
    worker = Path(finetune.__file__).with_name("learning_finetune_worker.py")
    python_exe = _selected_python()
    command = [python_exe, "-u", str(worker), phase, "--package-dir", str(finetune._package_dir()), *args]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=os.environ.copy(),
    )
    if process.stdout is None:
        raise RuntimeError("파인튜닝 Worker 출력을 읽을 수 없습니다.")
    last_lines: list[str] = []
    for line in process.stdout:
        clean = line.strip()
        if not clean:
            continue
        last_lines.append(clean)
        last_lines = last_lines[-20:]
        if clean.startswith("PROGRESS|"):
            parts = clean.split("|", 2)
            try:
                local = max(0, min(100, int(parts[1])))
            except Exception:
                local = 0
            message = parts[2] if len(parts) > 2 else phase
            overall = progress_start + int((progress_end - progress_start) * local / 100)
            finetune._set_job(job_id, overall, phase, message, status="running", finetune_python=python_exe)
        else:
            finetune._append_log(job_id, clean)
    code = process.wait()
    if code != 0:
        raise RuntimeError(f"{phase} Worker 실패 (ExitCode={code}): " + "\n".join(last_lines[-10:]))


async def _capability_with_reconciled_data_and_python() -> dict:
    # The configured capability wrapper calls finetune._validated_training_rows, so patching
    # that function below makes its problem count reflect the same Dataset validation the UI shows.
    result = await _ORIGINAL_CONFIGURED_CAPABILITY()
    python_info = _select_finetune_python()

    reasons = [
        str(value) for value in list(result.get("reasons") or [])
        if not str(value).startswith("NVIDIA GPU는 감지되지만 AgentStudio Python")
        and not str(value).startswith("CUDA GPU를 사용할 수 없습니다")
        and not str(value).startswith("GPU VRAM이 부족합니다")
    ]

    cuda_ok = bool(python_info.get("ok"))
    gpu_name = str(python_info.get("name") or result.get("gpu_name") or "")
    gpu_memory = float(python_info.get("memory_gb") or result.get("gpu_memory_gb") or 0.0)
    if not cuda_ok:
        candidate_text = " · ".join(
            f"{Path(str(item.get('python') or '')).name}: {item.get('error') or 'CUDA=False'}"
            for item in python_info.get("candidates", [])
        )
        reasons.insert(0, "NVIDIA GPU는 감지되지만 CUDA를 사용할 수 있는 AgentStudio Python 환경을 찾지 못했습니다." + (f" ({candidate_text})" if candidate_text else ""))
    elif gpu_memory < 6.0:
        reasons.insert(0, f"GPU VRAM이 부족합니다. 현재 {gpu_memory}GB, 권장 6GB 이상")

    result.update({
        "ready": not reasons,
        "reasons": reasons,
        "cuda_available": cuda_ok,
        "gpu_name": gpu_name,
        "gpu_memory_gb": gpu_memory,
        "finetune_python": str(python_info.get("python") or sys.executable),
        "torch_version": str(python_info.get("torch") or result.get("torch_version") or ""),
        "torch_cuda_version": str(python_info.get("cuda") or result.get("torch_cuda_version") or ""),
        "python_probe_candidates": python_info.get("candidates", []),
        "validation_source": "dataset_validation_reconciled_to_learning_problem_rows",
    })
    return result


finetune._validated_training_rows = _validated_training_rows_reconciled
finetune._install_finetune_runtime_sync = _install_runtime_with_selected_python
finetune._run_worker_sync = _run_worker_with_selected_python
finetune.get_weight_finetune_capability = _capability_with_reconciled_data_and_python
