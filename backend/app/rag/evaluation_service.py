from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.machine_identity import current_pc_name
from app.models.rag_entities import RagEvaluationCase, RagEvaluationRun, RagRetrievalSetting
from app.rag.retrieval_service import retrieve
from app.rag.security_service import normalize_security_context


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _serialize_case(row: RagEvaluationCase) -> dict[str, Any]:
    return {
        "id": row.id,
        "question": row.question,
        "expected_document_path": row.expected_document_path,
        "expected_text": row.expected_text,
        "is_active": bool(row.is_active),
        "created_at": _iso(row.created_at),
        "updated_at": _iso(row.updated_at),
    }


def _serialize_run(row: RagEvaluationRun) -> dict[str, Any]:
    return {
        "id": row.id,
        "status": row.status,
        "total_cases": row.total_cases,
        "passed_cases": row.passed_cases,
        "hit_rate": row.hit_rate,
        "mrr": row.mrr,
        "recall_at_k": row.recall_at_k,
        "zero_result_rate": row.zero_result_rate,
        "avg_duration_ms": row.avg_duration_ms,
        "security_context": row.security_context or {},
        "result_json": row.result_json or {},
        "error_message": row.error_message,
        "started_at": _iso(row.started_at),
        "finished_at": _iso(row.finished_at),
        "created_at": _iso(row.created_at),
    }


async def list_evaluation_cases(project_root: str) -> list[dict[str, Any]]:
    pc_name = current_pc_name()
    root = str(project_root or "").strip()
    async with SessionLocal() as session:
        rows = (await session.execute(select(RagEvaluationCase).where(
            RagEvaluationCase.pc_name == pc_name,
            RagEvaluationCase.project_root == root,
        ).order_by(RagEvaluationCase.id.asc()))).scalars().all()
        return [_serialize_case(row) for row in rows]


async def create_evaluation_case(payload: dict[str, Any]) -> dict[str, Any]:
    pc_name = current_pc_name()
    root = str(payload.get("project_root") or "").strip()
    question = str(payload.get("question") or "").strip()
    expected_path = str(payload.get("expected_document_path") or "").strip()
    expected_text = str(payload.get("expected_text") or "").strip()
    if not root or not question:
        raise ValueError("Evaluation Case에는 프로젝트와 질문이 필요합니다.")
    if not expected_path and not expected_text:
        raise ValueError("평가 기준으로 예상 문서 경로 또는 포함되어야 할 텍스트 중 하나를 입력하세요.")
    async with SessionLocal() as session:
        row = RagEvaluationCase(pc_name=pc_name, project_root=root, question=question, expected_document_path=expected_path, expected_text=expected_text, is_active=True)
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return _serialize_case(row)


async def delete_evaluation_case(case_id: int) -> dict[str, Any]:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        row = await session.get(RagEvaluationCase, int(case_id))
        if row is None or row.pc_name != pc_name:
            raise LookupError("RAG Evaluation Case를 찾을 수 없습니다.")
        await session.delete(row)
        await session.commit()
        return {"ok": True, "id": int(case_id)}


async def create_evaluation_run(project_root: str, security_context: dict[str, Any] | None = None) -> dict[str, Any]:
    pc_name = current_pc_name()
    root = str(project_root or "").strip()
    async with SessionLocal() as session:
        count = len((await session.execute(select(RagEvaluationCase.id).where(
            RagEvaluationCase.pc_name == pc_name,
            RagEvaluationCase.project_root == root,
            RagEvaluationCase.is_active.is_(True),
        ))).scalars().all())
        if count <= 0:
            raise ValueError("반복 Evaluation을 실행하려면 활성 테스트 Case를 먼저 등록하세요.")
        row = RagEvaluationRun(pc_name=pc_name, project_root=root, status="PENDING", total_cases=count, security_context=normalize_security_context(security_context))
        session.add(row)
        await session.commit()
        await session.refresh(row)
        result = _serialize_run(row)
        result["should_start"] = True
        return result


async def run_evaluation(run_id: int) -> None:
    try:
        pc_name = current_pc_name()
        async with SessionLocal() as session:
            run = await session.get(RagEvaluationRun, int(run_id))
            if run is None or run.pc_name != pc_name:
                return
            run.status = "RUNNING"
            run.started_at = datetime.utcnow()
            await session.commit()
            root = run.project_root
            cases = (await session.execute(select(RagEvaluationCase).where(
                RagEvaluationCase.pc_name == pc_name,
                RagEvaluationCase.project_root == root,
                RagEvaluationCase.is_active.is_(True),
            ).order_by(RagEvaluationCase.id.asc()))).scalars().all()
            setting = (await session.execute(select(RagRetrievalSetting).where(
                RagRetrievalSetting.pc_name == pc_name,
                RagRetrievalSetting.project_root == root,
            ))).scalar_one_or_none()
        mode = setting.search_mode if setting else "HYBRID"
        top_k = int(setting.top_k if setting else 5)
        threshold = float(setting.similarity_threshold if setting else 0.20)
        metadata_filter = dict(setting.metadata_filter or {}) if setting else {}
        security_context = normalize_security_context(run.security_context or {"user_id": "evaluation", "role": "DEVELOPER", "security_clearance": "RESTRICTED"})
        passed = 0
        reciprocal_sum = 0.0
        zero = 0
        durations: list[int] = []
        results: list[dict[str, Any]] = []
        for case in cases:
            response = await retrieve({
                "project_root": root,
                "query": case.question,
                "search_mode": mode,
                "top_k": top_k,
                "similarity_threshold": threshold,
                "metadata_filter": metadata_filter,
                "security_context": security_context,
            })
            items = list(response.get("results") or [])
            durations.append(int(response.get("duration_ms") or 0))
            if not items:
                zero += 1
            hit_rank = 0
            expected_path = str(case.expected_document_path or "").lower()
            expected_text = str(case.expected_text or "").lower()
            for rank, item in enumerate(items, start=1):
                path_ok = bool(expected_path) and expected_path in str(item.get("document_path") or "").lower()
                text_ok = bool(expected_text) and expected_text in str(item.get("content") or "").lower()
                if path_ok or text_ok:
                    hit_rank = rank
                    break
            hit = hit_rank > 0
            if hit:
                passed += 1
                reciprocal_sum += 1.0 / hit_rank
            results.append({"case_id": case.id, "question": case.question, "hit": hit, "hit_rank": hit_rank, "result_count": len(items), "duration_ms": int(response.get("duration_ms") or 0), "search_log_id": response.get("search_log_id")})
        total = len(cases)
        hit_rate = passed / total if total else 0.0
        mrr = reciprocal_sum / total if total else 0.0
        zero_rate = zero / total if total else 0.0
        avg_ms = round(sum(durations) / total) if total else 0
        async with SessionLocal() as session:
            run = await session.get(RagEvaluationRun, int(run_id))
            if run is None:
                return
            run.status = "COMPLETED"
            run.total_cases = total
            run.passed_cases = passed
            run.hit_rate = round(hit_rate, 6)
            run.mrr = round(mrr, 6)
            # One explicit expected evidence target per case: Recall@K equals Hit Rate in this phase.
            run.recall_at_k = round(hit_rate, 6)
            run.zero_result_rate = round(zero_rate, 6)
            run.avg_duration_ms = int(avg_ms)
            run.result_json = {"top_k": top_k, "search_mode": mode, "security_context": security_context, "cases": results, "metric_note": "각 Case는 예상 문서 경로 또는 예상 텍스트 1개를 관련 근거로 정의하므로 Phase-6 Recall@K는 Hit Rate와 동일한 기준입니다."}
            run.finished_at = datetime.utcnow()
            await session.commit()
    except Exception as exc:
        async with SessionLocal() as session:
            run = await session.get(RagEvaluationRun, int(run_id))
            if run is not None:
                run.status = "FAILED"
                run.error_message = str(exc)
                run.finished_at = datetime.utcnow()
                await session.commit()


async def list_evaluation_runs(project_root: str, limit: int = 30) -> list[dict[str, Any]]:
    pc_name = current_pc_name()
    root = str(project_root or "").strip()
    async with SessionLocal() as session:
        rows = (await session.execute(select(RagEvaluationRun).where(
            RagEvaluationRun.pc_name == pc_name,
            RagEvaluationRun.project_root == root,
        ).order_by(RagEvaluationRun.id.desc()).limit(max(1, min(int(limit), 100))))).scalars().all()
        return [_serialize_run(row) for row in rows]


async def get_evaluation_run(run_id: int) -> dict[str, Any]:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        row = await session.get(RagEvaluationRun, int(run_id))
        if row is None or row.pc_name != pc_name:
            raise LookupError("RAG Evaluation Run을 찾을 수 없습니다.")
        return _serialize_run(row)
