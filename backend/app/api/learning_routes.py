from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.learning_collection_service import (
    collect_learning_problems,
    list_aggregated_misjudgment_cases,
)
from app.services.llm_learning_service import (
    add_manual_misjudgment_case,
    generate_problem_dataset,
    learning_summary,
    list_datasets,
    prepare_training,
    record_evaluation,
    review_misjudgment_case,
    sync_misjudgment_candidates,
    validate_dataset,
)
from app.services.llm_learning_pc_application_service import (
    apply_to_ollama_for_current_pc,
    list_pc_applications,
    set_current_pc_application_enabled,
)
from app.services.ollama_model_manager_service import (
    get_recommended_model_job,
    get_recommended_model_status,
    start_recommended_model_job,
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


class ProblemCollectionRequest(BaseModel):
    target_per_case: int = 100
    max_cases: int = 5
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


class PcApplicationEnableRequest(BaseModel):
    enabled: bool


@router.get("/summary")
async def summary():
    result = await learning_summary()
    applications = await list_pc_applications(include_all_pcs=True)
    result["pc_applications"] = applications.get("items", [])
    result["application_scope"] = "per_pc"
    result["recommended_ollama"] = await get_recommended_model_status()
    return result


@router.get("/recommended-ollama")
async def recommended_ollama_status():
    return await get_recommended_model_status()


@router.post("/recommended-ollama/download-job")
async def recommended_ollama_download_job():
    try:
        return await start_recommended_model_job()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc) or type(exc).__name__) from exc


@router.get("/recommended-ollama/download-job/{job_id}")
async def recommended_ollama_download_job_status(job_id: str):
    try:
        return await get_recommended_model_job(job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/misjudgments/sync")
async def sync_candidates():
    return await sync_misjudgment_candidates()


@router.get("/misjudgments")
async def misjudgments(
    provider: str = Query(default=""),
    status: str = Query(default=""),
    limit: int = Query(default=500, ge=1, le=2000),
):
    return await list_aggregated_misjudgment_cases(provider, status, limit)


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


@router.post("/problems/collect")
async def collect_problems(req: ProblemCollectionRequest):
    try:
        return await collect_learning_problems(req.target_per_case, req.max_cases, req.provider)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc) or type(exc).__name__) from exc


@router.post("/datasets/generate")
async def generate_dataset(req: ProblemGenerationRequest):
    try:
        return await generate_problem_dataset(req.case_id, req.target_count, req.provider)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"관련 문제 대량 생성 실패: {str(exc) or type(exc).__name__}") from exc


@router.get("/datasets")
async def datasets():
    result = await list_datasets()
    applications = await list_pc_applications(include_all_pcs=True)
    by_dataset: dict[str, list[dict]] = {}
    for item in applications.get("items", []):
        by_dataset.setdefault(str(item.get("dataset_id") or ""), []).append(item)
    current_pc = applications.get("current_pc_name", "")
    for dataset in result.get("items", []):
        rows = by_dataset.get(str(dataset.get("id") or ""), [])
        dataset["pc_applications"] = rows
        dataset["current_pc_application"] = next((row for row in rows if row.get("pc_name") == current_pc), None)
    result["current_pc_name"] = current_pc
    result["dataset_scope"] = "shared_all_pcs"
    result["application_scope"] = "per_pc"
    return result


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


@router.get("/datasets/{dataset_id}/pc-applications")
async def pc_applications(dataset_id: str):
    return await list_pc_applications(dataset_id=dataset_id, include_all_pcs=True)


@router.get("/pc-applications")
async def all_pc_applications(current_pc_only: bool = Query(default=False)):
    return await list_pc_applications(include_all_pcs=not current_pc_only)


@router.post("/datasets/{dataset_id}/apply-ollama")
async def apply(dataset_id: str, req: OllamaApplyRequest):
    try:
        return await apply_to_ollama_for_current_pc(dataset_id, req.model_name, req.adapter_path)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.patch("/datasets/{dataset_id}/current-pc-application")
async def toggle_current_pc_application(dataset_id: str, req: PcApplicationEnableRequest):
    try:
        return await set_current_pc_application_enabled(dataset_id, req.enabled)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
