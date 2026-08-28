from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.llm_learning_service import (
    add_manual_misjudgment_case,
    apply_to_ollama,
    generate_problem_dataset,
    learning_summary,
    list_datasets,
    list_misjudgment_cases,
    prepare_training,
    record_evaluation,
    review_misjudgment_case,
    sync_misjudgment_candidates,
    validate_dataset,
)

router = APIRouter(prefix="/learning", tags=["LLM Learning"])


class MisjudgmentReviewRequest(BaseModel):
    status: str = "candidate"
    expected_output: str = ""
    error_type: str = ""
    error_reason: str = ""
    domain: str = ""
    topic: str = ""


class ManualMisjudgmentRequest(BaseModel):
    provider: str = "unknown"
    model: str = "unknown"
    task: str = "manual"
    project_root: str = ""
    user_request: str = ""
    wrong_output: str = ""
    correction_evidence: str = ""
    expected_output: str = ""
    error_type: str = "unclassified"
    error_reason: str = ""
    domain: str = ""
    topic: str = ""


class ProblemGenerationRequest(BaseModel):
    case_id: str
    target_count: int = 100
    provider: str = "ollama"


class DatasetValidationRequest(BaseModel):
    approved_problem_ids: list[str] = []


class TrainingPrepareRequest(BaseModel):
    base_model: str = ""


class EvaluationRequest(BaseModel):
    baseline_score: float
    trained_score: float
    minimum_gain: float = 0.03


class OllamaApplyRequest(BaseModel):
    model_name: str
    adapter_path: str = ""


@router.get("/summary")
async def summary():
    return await learning_summary()


@router.post("/misjudgments/sync")
async def sync_candidates():
    return await sync_misjudgment_candidates()


@router.get("/misjudgments")
async def misjudgments(
    provider: str = Query(default=""),
    status: str = Query(default=""),
    limit: int = Query(default=500, ge=1, le=2000),
):
    return await list_misjudgment_cases(provider, status, limit)


@router.post("/misjudgments/manual")
async def add_manual(req: ManualMisjudgmentRequest):
    return await add_manual_misjudgment_case(req.model_dump())


@router.patch("/misjudgments/{case_id}")
async def review_case(case_id: str, req: MisjudgmentReviewRequest):
    try:
        return await review_misjudgment_case(case_id, req.model_dump())
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/datasets/generate")
async def generate_dataset(req: ProblemGenerationRequest):
    try:
        return await generate_problem_dataset(req.case_id, req.target_count, req.provider)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"관련 문제 대량 생성 실패: {exc}") from exc


@router.get("/datasets")
async def datasets():
    return await list_datasets()


@router.post("/datasets/{dataset_id}/validate")
async def validate(dataset_id: str, req: DatasetValidationRequest):
    try:
        return await validate_dataset(dataset_id, req.approved_problem_ids)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/datasets/{dataset_id}/prepare-training")
async def prepare(dataset_id: str, req: TrainingPrepareRequest):
    try:
        return await prepare_training(dataset_id, req.base_model)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/datasets/{dataset_id}/evaluation")
async def evaluation(dataset_id: str, req: EvaluationRequest):
    try:
        return await record_evaluation(dataset_id, req.baseline_score, req.trained_score, req.minimum_gain)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/datasets/{dataset_id}/apply-ollama")
async def apply(dataset_id: str, req: OllamaApplyRequest):
    try:
        return await apply_to_ollama(dataset_id, req.model_name, req.adapter_path)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
