from __future__ import annotations

"""True weight fine-tuning pipeline for THEANOVA AgentStudio.

This is intentionally separate from learning_apply_job_service. The existing apply job
builds a fast Ollama curriculum/System-prompt model. This service performs actual QLoRA
weight training, merges the adapter into Qwen3.5-4B, imports the merged Safetensors into
Ollama, smoke-tests it, then atomically promotes it to ``theanova-learn:latest``.
"""

import asyncio
import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.machine_identity import current_pc_name
from app.models.learning_entities import LlmLearningDataset, LlmLearningPcApplication, LlmLearningProblem
from app.services.learning_relational_schema_service import assert_learning_relational_schema_ready
from app.services.learning_visibility_bridge import backfill_current_pc_learning_group_mappings
from app.services.ollama_model_manager_service import get_recommended_model_status, persist_current_ollama_model

HF_BASE_MODEL = "Qwen/Qwen3.5-4B"
OLLAMA_BASE_MODEL = "qwen3.5:4b"
TARGET_MODEL = "theanova-learn:latest"
MIN_VALIDATED_EXAMPLES = 8
_FINETUNE_JOBS: dict[str, dict] = {}

# Fine-tuning packages live outside the AgentStudio venv. The subprocess prepends this
# folder to sys.path while continuing to reuse the already-installed CUDA PyTorch.
_FINETUNE_REQUIREMENTS = [
    "transformers>=5.3.0",
    "peft>=0.18.0",
    "accelerate>=1.10.0",
    "bitsandbytes>=0.48.0",
    "sentencepiece>=0.2.0",
    "protobuf>=5.0.0",
]


def _root() -> Path:
    local = str(os.environ.get("LOCALAPPDATA") or "").strip()
    root = Path(local) / "THEANOVA" / "AgentStudio" if local else Path.home() / ".theanova" / "AgentStudio"
    path = root / "learning" / "weight_finetune"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _package_dir() -> Path:
    path = _root() / "python_packages"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _set_job(job_id: str, progress: int, stage: str, message: str, **extra) -> None:
    job = _FINETUNE_JOBS.setdefault(job_id, {})
    logs = list(job.get("logs") or [])
    if message and (not logs or logs[-1] != message):
        logs.append(message)
    job.update({
        "id": job_id,
        "progress": max(0, min(100, int(progress))),
        "stage": stage,
        "message": message,
        "logs": logs[-80:],
        "updated_at": datetime.utcnow().isoformat(),
        **extra,
    })


def _append_log(job_id: str, text: str) -> None:
    clean = str(text or "").strip()
    if not clean:
        return
    job = _FINETUNE_JOBS.setdefault(job_id, {})
    logs = list(job.get("logs") or [])
    logs.append(clean[-1200:])
    job["logs"] = logs[-80:]
    job["updated_at"] = datetime.utcnow().isoformat()


def _runtime_marker() -> Path:
    return _package_dir() / ".agentstudio_qwen35_finetune_runtime_v1"


def _install_finetune_runtime_sync(job_id: str) -> None:
    marker = _runtime_marker()
    if marker.exists():
        _append_log(job_id, "파인튜닝 전용 Python 패키지 캐시 확인 완료")
        return
    target = _package_dir()
    command = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--target",
        str(target),
        *_FINETUNE_REQUIREMENTS,
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    if process.stdout is None:
        raise RuntimeError("파인튜닝 패키지 설치 출력을 읽을 수 없습니다.")
    for line in process.stdout:
        value = line.strip()
        if value:
            _append_log(job_id, value)
    code = process.wait()
    if code != 0:
        raise RuntimeError(f"파인튜닝 전용 패키지 설치 실패 (ExitCode={code})")
    marker.write_text(datetime.utcnow().isoformat(), encoding="utf-8")


def _problem_fingerprint(instruction: str, input_text: str, output_text: str) -> str:
    payload = "\n".join([instruction.strip(), input_text.strip(), output_text.strip()]).casefold()
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


async def _validated_training_rows() -> tuple[list[dict], list[LlmLearningDataset]]:
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
        problems = (
            await session.execute(
                select(LlmLearningProblem)
                .where(
                    LlmLearningProblem.dataset_id.in_(dataset_ids),
                    LlmLearningProblem.validated == True,
                )
                .order_by(LlmLearningProblem.created_at.asc())
            )
        ).scalars().all()

    rows: list[dict] = []
    seen: set[str] = set()
    dataset_by_id = {str(row.id): row for row in datasets}
    dataset_ids_with_rows: set[str] = set()
    for problem in problems:
        instruction = str(problem.instruction or "").strip()
        output = str(problem.output_text or "").strip()
        input_text = str(problem.input_text or "").strip()
        if not instruction or not output:
            continue
        fingerprint = _problem_fingerprint(instruction, input_text, output)
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        dataset_id = str(problem.dataset_id or "")
        dataset_ids_with_rows.add(dataset_id)
        rows.append({
            "id": str(problem.id),
            "dataset_id": dataset_id,
            "group_id": str(problem.group_id or ""),
            "source_case_id": str(problem.source_case_id or ""),
            "instruction": instruction,
            "input": input_text,
            "output": output,
        })

    # Compatibility fallback for old validated Datasets whose relational problem rows were
    # created before their validation flags were backfilled.
    for dataset in datasets:
        if str(dataset.id) in dataset_ids_with_rows:
            continue
        validation = dict(dataset.validation_json or {})
        if int(validation.get("approved") or 0) < 1:
            continue
        for item in list(dataset.problems_json or []):
            if not isinstance(item, dict) or item.get("validated") is False:
                continue
            instruction = str(item.get("instruction") or "").strip()
            output = str(item.get("output") or "").strip()
            input_text = str(item.get("input") or "").strip()
            if not instruction or not output:
                continue
            fingerprint = _problem_fingerprint(instruction, input_text, output)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            rows.append({
                "id": str(item.get("id") or uuid.uuid4().hex),
                "dataset_id": str(dataset.id),
                "group_id": str(dataset.group_id or ""),
                "source_case_id": str(dataset.source_case_id or ""),
                "instruction": instruction,
                "input": input_text,
                "output": output,
            })
            dataset_ids_with_rows.add(str(dataset.id))

    used_datasets = [dataset_by_id[value] for value in dataset_ids_with_rows if value in dataset_by_id]
    used_datasets.sort(key=lambda row: row.created_at or datetime.min)
    return rows, used_datasets


def _write_dataset(job_dir: Path, rows: list[dict]) -> Path:
    path = job_dir / "validated_training.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return path


def _run_worker_sync(job_id: str, phase: str, progress_start: int, progress_end: int, args: list[str]) -> None:
    worker = Path(__file__).with_name("learning_finetune_worker.py")
    command = [sys.executable, "-u", str(worker), phase, "--package-dir", str(_package_dir()), *args]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
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
            _set_job(job_id, overall, phase, message, status="running")
        else:
            _append_log(job_id, clean)
    code = process.wait()
    if code != 0:
        raise RuntimeError(f"{phase} Worker 실패 (ExitCode={code}): " + "\n".join(last_lines[-10:]))


def _run_ollama_sync(command: list[str], timeout: int = 1800) -> str:
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    output = str(completed.stdout or "")
    if completed.returncode != 0:
        raise RuntimeError(f"Ollama 명령 실패 (ExitCode={completed.returncode}): {' '.join(command[1:])}\n{output[-4000:]}")
    return output


def _ollama_has_model_sync(ollama_exe: str, model_name: str) -> bool:
    completed = subprocess.run(
        [ollama_exe, "list"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    return completed.returncode == 0 and model_name.lower() in str(completed.stdout or "").lower()


def _register_independent_model_sync(job_id: str, ollama_exe: str, merged_dir: Path, temp_model: str) -> Path:
    modelfile = merged_dir / "Modelfile.agentstudio"
    # FROM a merged Safetensors directory makes the Ollama artifact independent from the
    # original LoRA adapter. Quantization is performed only after the weights are merged.
    modelfile.write_text(
        f'FROM "{merged_dir}"\nPARAMETER temperature 0\n',
        encoding="utf-8",
    )
    _append_log(job_id, f"Ollama 독립 모델 Import: {temp_model}")
    output = _run_ollama_sync(
        [ollama_exe, "create", temp_model, "--quantize", "q4_K_M", "-f", str(modelfile)],
        timeout=3600,
    )
    _append_log(job_id, output[-1200:])
    return modelfile


def _smoke_test_sync(job_id: str, ollama_exe: str, model_name: str) -> str:
    output = _run_ollama_sync(
        [ollama_exe, "run", model_name, "짧게 'OK'라고만 답하세요."],
        timeout=240,
    )
    if not output.strip():
        raise RuntimeError("파인튜닝 모델 Smoke Test 응답이 비어 있습니다.")
    _append_log(job_id, "Smoke Test 응답: " + output.strip()[:500])
    return output.strip()


def _promote_model_sync(job_id: str, ollama_exe: str, temp_model: str) -> str:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = f"theanova-learn:backup-{timestamp}"
    had_old = _ollama_has_model_sync(ollama_exe, TARGET_MODEL)
    if had_old:
        _append_log(job_id, f"기존 {TARGET_MODEL} 백업 → {backup}")
        _run_ollama_sync([ollama_exe, "cp", TARGET_MODEL, backup], timeout=300)
    try:
        if had_old:
            _run_ollama_sync([ollama_exe, "rm", TARGET_MODEL], timeout=120)
        _run_ollama_sync([ollama_exe, "cp", temp_model, TARGET_MODEL], timeout=300)
        if not _ollama_has_model_sync(ollama_exe, TARGET_MODEL):
            raise RuntimeError(f"승격 후 {TARGET_MODEL}을 Ollama 목록에서 찾을 수 없습니다.")
    except Exception:
        if had_old and _ollama_has_model_sync(ollama_exe, backup):
            try:
                if _ollama_has_model_sync(ollama_exe, TARGET_MODEL):
                    _run_ollama_sync([ollama_exe, "rm", TARGET_MODEL], timeout=120)
                _run_ollama_sync([ollama_exe, "cp", backup, TARGET_MODEL], timeout=300)
                _append_log(job_id, "승격 실패로 기존 모델을 복구했습니다.")
            except Exception as restore_error:
                _append_log(job_id, f"기존 모델 복구 실패: {restore_error}")
        raise
    finally:
        try:
            _run_ollama_sync([ollama_exe, "rm", temp_model], timeout=120)
        except Exception:
            pass
    return backup if had_old else ""


async def _save_weight_applications(datasets: list[LlmLearningDataset], job_id: str, job_dir: Path, example_count: int) -> None:
    pc_name = current_pc_name()
    now = datetime.utcnow()
    async with SessionLocal() as session:
        db_datasets = (
            await session.execute(select(LlmLearningDataset).where(LlmLearningDataset.id.in_([row.id for row in datasets])))
        ).scalars().all()
        existing = (
            await session.execute(select(LlmLearningPcApplication).where(LlmLearningPcApplication.pc_name == pc_name))
        ).scalars().all()
        by_dataset = {str(row.dataset_id): row for row in existing}
        included = {str(row.id) for row in db_datasets}

        for dataset in db_datasets:
            app = by_dataset.get(str(dataset.id))
            if app is None:
                app = LlmLearningPcApplication(
                    id=uuid.uuid4().hex,
                    dataset_id=str(dataset.id),
                    group_id=str(dataset.group_id or ""),
                    pc_name=pc_name,
                )
                session.add(app)
            app.group_id = str(dataset.group_id or "")
            app.model_name = TARGET_MODEL
            app.base_model = HF_BASE_MODEL
            app.adapter_path = str(job_dir / "adapter")
            app.installed = True
            app.enabled = True
            app.status = "applied"
            app.last_error = ""
            app.applied_at = now
            app.metadata_json = {
                "application_method": "qlora_weight_finetune_merged_q4_k_m",
                "job_id": job_id,
                "base_model": HF_BASE_MODEL,
                "model_alias": TARGET_MODEL,
                "adapter_path": str(job_dir / "adapter"),
                "merged_model_path": str(job_dir / "merged"),
                "validated_example_count": example_count,
                "weight_trained": True,
            }
            training = dict(dataset.training_json or {})
            training["weight_finetune"] = {
                "job_id": job_id,
                "method": "QLoRA",
                "base_model": HF_BASE_MODEL,
                "adapter_path": str(job_dir / "adapter"),
                "merged_model_path": str(job_dir / "merged"),
                "completed_at": now.isoformat(),
            }
            dataset.training_json = training
            deployment = dict(dataset.deployment_json or {})
            history = list(deployment.get("pc_history") or [])
            history.append({
                "pc_name": pc_name,
                "model_name": TARGET_MODEL,
                "method": "qlora_weight_finetune_merged_q4_k_m",
                "job_id": job_id,
                "applied_at": now.isoformat(),
            })
            deployment["pc_history"] = history[-100:]
            deployment["weight_finetune_latest"] = history[-1]
            dataset.deployment_json = deployment
            dataset.updated_by_pc_name = pc_name

        # The independent model was trained from the validated Dataset set above, so only
        # those rows are marked enabled for this PC.
        for app in existing:
            if str(app.dataset_id) not in included:
                app.enabled = False
                app.status = "not_applied"
        await session.commit()


async def get_weight_finetune_capability() -> dict:
    rows, datasets = await _validated_training_rows()
    status = await get_recommended_model_status()
    cuda_available = False
    gpu_name = ""
    gpu_memory_gb = 0.0
    torch_error = ""
    try:
        import torch
        cuda_available = bool(torch.cuda.is_available())
        if cuda_available:
            gpu_name = str(torch.cuda.get_device_name(0))
            gpu_memory_gb = round(float(torch.cuda.get_device_properties(0).total_memory) / (1024 ** 3), 1)
    except Exception as exc:
        torch_error = str(exc)
    disk = shutil.disk_usage(_root())
    disk_free_gb = round(disk.free / (1024 ** 3), 1)
    reasons: list[str] = []
    if not cuda_available:
        reasons.append("CUDA GPU를 사용할 수 없습니다.")
    if cuda_available and gpu_memory_gb < 6.0:
        reasons.append(f"GPU VRAM이 부족합니다. 현재 {gpu_memory_gb}GB, 권장 6GB 이상")
    if len(rows) < MIN_VALIDATED_EXAMPLES:
        reasons.append(f"검증 완료 학습 문제가 부족합니다. 현재 {len(rows)}개, 최소 {MIN_VALIDATED_EXAMPLES}개")
    if disk_free_gb < 20:
        reasons.append(f"디스크 여유 공간이 부족합니다. 현재 {disk_free_gb}GB, 권장 20GB 이상")
    if not str(status.get("ollama_executable") or "").strip():
        reasons.append("Ollama 실행 파일을 찾을 수 없습니다.")
    return {
        "ok": True,
        "ready": not reasons,
        "reasons": reasons,
        "base_model": HF_BASE_MODEL,
        "ollama_base_model": OLLAMA_BASE_MODEL,
        "target_model": TARGET_MODEL,
        "validated_dataset_count": len(datasets),
        "validated_problem_count": len(rows),
        "minimum_validated_problem_count": MIN_VALIDATED_EXAMPLES,
        "cuda_available": cuda_available,
        "gpu_name": gpu_name,
        "gpu_memory_gb": gpu_memory_gb,
        "disk_free_gb": disk_free_gb,
        "torch_error": torch_error,
        "training_method": "QLoRA 4-bit NF4 -> LoRA merge -> Ollama Q4_K_M",
        "independent_model": True,
    }


async def _run_weight_finetune_job(job_id: str) -> None:
    job_dir = _root() / "jobs" / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    try:
        _set_job(job_id, 2, "capability", "GPU·Dataset·Ollama 학습 조건을 확인 중...", status="running")
        capability = await get_weight_finetune_capability()
        if not capability.get("ready"):
            raise ValueError(" / ".join(capability.get("reasons") or ["파인튜닝 준비 조건을 충족하지 못했습니다."]))

        rows, datasets = await _validated_training_rows()
        dataset_path = await asyncio.to_thread(_write_dataset, job_dir, rows)
        _set_job(
            job_id,
            8,
            "runtime",
            f"파인튜닝 전용 실행환경 준비 · 검증 Dataset {len(datasets)}개 / 문제 {len(rows)}개",
            status="running",
            dataset_count=len(datasets),
            problem_count=len(rows),
            gpu_name=capability.get("gpu_name"),
            gpu_memory_gb=capability.get("gpu_memory_gb"),
        )
        await asyncio.to_thread(_install_finetune_runtime_sync, job_id)

        adapter_root = job_dir
        _set_job(job_id, 15, "train", "Qwen3.5-4B QLoRA 실제 가중치 학습을 시작합니다.", status="running")
        await asyncio.to_thread(
            _run_worker_sync,
            job_id,
            "train",
            15,
            68,
            [
                "--base-model", HF_BASE_MODEL,
                "--dataset", str(dataset_path),
                "--output", str(adapter_root),
                "--max-length", "768",
                "--epochs", "2",
                "--gradient-accumulation", "8",
                "--learning-rate", "0.0001",
                "--lora-rank", "16",
                "--lora-alpha", "32",
            ],
        )
        adapter = adapter_root / "adapter"
        if not (adapter / "adapter_model.safetensors").exists():
            raise RuntimeError("QLoRA 학습은 완료됐지만 adapter_model.safetensors가 생성되지 않았습니다.")

        merged = job_dir / "merged"
        _set_job(job_id, 69, "merge", "LoRA Adapter를 Base Model에 병합해 독립 가중치 모델을 만드는 중...", status="running")
        await asyncio.to_thread(
            _run_worker_sync,
            job_id,
            "merge",
            69,
            83,
            [
                "--base-model", HF_BASE_MODEL,
                "--adapter", str(adapter),
                "--output", str(merged),
            ],
        )
        if not list(merged.glob("*.safetensors")):
            raise RuntimeError("Merge 완료 후 독립 Safetensors 가중치 파일을 찾을 수 없습니다.")

        status = await get_recommended_model_status()
        ollama_exe = str(status.get("ollama_executable") or "").strip()
        if not ollama_exe:
            raise RuntimeError("Ollama 실행 파일을 찾을 수 없습니다.")
        temp_model = f"theanova-learn-finetuned:{job_id[:10]}"
        _set_job(job_id, 84, "ollama_import", "Merge 가중치를 Q4_K_M으로 양자화하여 임시 Ollama 모델 생성 중...", status="running")
        modelfile = await asyncio.to_thread(_register_independent_model_sync, job_id, ollama_exe, merged, temp_model)

        _set_job(job_id, 92, "smoke_test", "새 독립 모델을 실제 실행해 Smoke Test 중...", status="running")
        smoke = await asyncio.to_thread(_smoke_test_sync, job_id, ollama_exe, temp_model)

        _set_job(job_id, 95, "promote", f"검증된 모델을 {TARGET_MODEL}로 안전하게 교체 중...", status="running")
        backup_model = await asyncio.to_thread(_promote_model_sync, job_id, ollama_exe, temp_model)
        await persist_current_ollama_model(TARGET_MODEL, str(status.get("common_models_root") or ""))

        _set_job(job_id, 97, "database", "Dataset → 그룹 → PC 학습 적용 관계를 DB에 기록 중...", status="running")
        await _save_weight_applications(datasets, job_id, job_dir, len(rows))
        mapping = await backfill_current_pc_learning_group_mappings()

        manifest = {
            "job_id": job_id,
            "created_at": datetime.utcnow().isoformat(),
            "base_model": HF_BASE_MODEL,
            "target_model": TARGET_MODEL,
            "training_method": "QLoRA 4-bit NF4",
            "merge": True,
            "ollama_quantization": "Q4_K_M",
            "validated_dataset_ids": [str(row.id) for row in datasets],
            "validated_dataset_count": len(datasets),
            "validated_problem_count": len(rows),
            "adapter_path": str(adapter),
            "merged_model_path": str(merged),
            "modelfile": str(modelfile),
            "backup_model": backup_model,
            "smoke_test": smoke[:1000],
            "mapping": mapping,
        }
        (job_dir / "finetune_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        _set_job(
            job_id,
            100,
            "done",
            f"독립 가중치 파인튜닝 완료 · Dataset {len(datasets)}개 / 문제 {len(rows)}개 → {TARGET_MODEL}",
            status="completed",
            result=manifest,
        )
    except Exception as exc:
        _set_job(
            job_id,
            int(_FINETUNE_JOBS.get(job_id, {}).get("progress") or 0),
            "failed",
            str(exc) or type(exc).__name__,
            status="failed",
            error=str(exc) or type(exc).__name__,
        )


async def start_weight_finetune_job() -> dict:
    for job in _FINETUNE_JOBS.values():
        if job.get("status") == "running":
            return dict(job)
    capability = await get_weight_finetune_capability()
    if not capability.get("ready"):
        raise ValueError(" / ".join(capability.get("reasons") or ["파인튜닝 준비 조건을 충족하지 못했습니다."]))
    job_id = uuid.uuid4().hex
    _set_job(
        job_id,
        1,
        "queued",
        "Qwen3.5-4B 기반 독립 가중치 파인튜닝 작업을 준비합니다.",
        status="running",
        created_at=datetime.utcnow().isoformat(),
        base_model=HF_BASE_MODEL,
        target_model=TARGET_MODEL,
        dataset_count=capability.get("validated_dataset_count"),
        problem_count=capability.get("validated_problem_count"),
    )
    asyncio.create_task(_run_weight_finetune_job(job_id))
    return dict(_FINETUNE_JOBS[job_id])


async def get_weight_finetune_job(job_id: str) -> dict:
    job = _FINETUNE_JOBS.get(str(job_id or ""))
    if not job:
        raise KeyError("가중치 파인튜닝 작업을 찾을 수 없습니다.")
    return dict(job)
