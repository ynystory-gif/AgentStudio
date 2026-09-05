from __future__ import annotations

from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, Header
from pydantic import BaseModel, Field


from app.rag.indexing_service import (
    create_index_job,
    get_index_job,
    indexing_config,
    list_index_jobs,
    preview_source_chunks,
    run_index_job,
)


from app.rag.agent_integration_service import (
    bind_workflow,
    execute_rag_tool,
    generate_agent_tool,
    list_agent_test_logs,
    list_agent_tools,
    mark_prompt_tool_registered,
    prepare_agent_test,
    update_prompt_context,
)


from app.rag.intelligence_service import (
    apply_ai_recommendation,
    create_ai_recommendation,
    evaluate_rag_settings,
    get_or_create_intelligence_setting,
    list_recommendations,
    update_intelligence_setting,
)

from app.rag.operation_service import (
    create_sync_job,
    detect_source_changes,
    get_sync_job,
    list_document_versions,
    list_operation_documents,
    list_operation_sources,
    list_sync_jobs,
    rollback_document_version,
    run_sync_job,
    set_document_active,
    set_source_active,
    set_source_sync_mode,
)
from app.rag.security_service import (
    create_access_rule,
    delete_access_rule,
    list_access_rules,
    list_search_audits,
    set_document_security,
)
from app.rag.evaluation_service import (
    create_evaluation_case,
    create_evaluation_run,
    delete_evaluation_case,
    get_evaluation_run,
    list_evaluation_cases,
    list_evaluation_runs,
    run_evaluation,
)
from app.rag.retrieval_service import (
    get_or_create_retrieval_setting,
    list_search_logs,
    retrieval_options,
    retrieve,
    update_retrieval_setting,
)


from app.services.account_setting_service import append_project_history, upsert_project_setting
from app.services.auth_service import authenticate_token

from app.services.rag_studio_service import (
    analyze_source,
    approve_source,
    create_collection,
    create_source,
    delete_collection,
    delete_source,
    get_or_create_studio_setting,
    list_collections,
    list_sources,
    review_source,
    test_rag_database,
    update_collection,
    update_studio_setting,
)

router = APIRouter(prefix='/rag', tags=['RAG Studio'])

def _bearer(value: str) -> str:
    return value[7:].strip() if str(value or '').lower().startswith('bearer ') else ''


async def _member(authorization: str) -> dict | None:
    token = _bearer(authorization)
    return await authenticate_token(token) if token else None


async def _record(member: dict | None, project_root: str, *, category: str, action: str, title: str, before: dict | None = None, after: dict | None = None, summary: str = '') -> None:
    if not member or not str(project_root or '').strip():
        return
    await append_project_history(member['id'], project_root, category=category, action=action, title=title, summary=summary, before=before or {}, after=after or {})



class RagSettingRequest(BaseModel):
    project_root: str = ''
    rag_enabled: bool | None = None
    db_provider: str | None = None
    connection_mode: str | None = None
    db_schema: str | None = None
    scope: str | None = None


class RagCollectionCreateRequest(BaseModel):
    project_root: str = ''
    agent_design_project_id: int | None = None
    name: str = Field(min_length=1, max_length=300)
    description: str = ''
    scope: str = 'AGENT'
    security_level: str = 'INTERNAL'


class RagCollectionUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    scope: str | None = None
    security_level: str | None = None
    is_active: bool | None = None


class RagSourceCreateRequest(BaseModel):
    project_root: str = ''
    source_type: str = 'FILE'
    source_uri: str = Field(default='', max_length=2000)
    source_text: str = Field(default='', max_length=2_000_000)
    display_name: str = ''
    collection_ids: list[int] = Field(default_factory=list)


class RagSourceActionRequest(BaseModel):
    source_id: int


class RagDatabaseTestRequest(BaseModel):
    database_url: str = ''


class RagIndexStartRequest(BaseModel):
    source_id: int


class RagChunkPreviewRequest(BaseModel):
    source_id: int
    limit: int = Field(default=16, ge=1, le=50)


class RagRetrievalSettingRequest(BaseModel):
    project_root: str = ''
    search_mode: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=50)
    similarity_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata_filter: dict[str, Any] | None = None


class RagRetrieveRequest(BaseModel):
    project_root: str = ''
    query: str = Field(min_length=1, max_length=8000)
    search_mode: str = 'HYBRID'
    top_k: int = Field(default=5, ge=1, le=50)
    similarity_threshold: float = Field(default=0.20, ge=0.0, le=1.0)
    metadata_filter: dict[str, Any] = Field(default_factory=dict)
    router_enabled: bool | None = None
    reranking_enabled: bool | None = None
    rerank_top_n: int | None = Field(default=None, ge=1, le=50)
    security_context: dict[str, Any] | None = None


class RagToolGenerateRequest(BaseModel):
    project_root: str = ''
    agent_design_project_id: int | None = None
    collection_id: int | None = None
    tool_name: str = ''
    description: str = ''
    search_mode: str | None = None
    top_k: int | None = Field(default=None, ge=1, le=50)
    similarity_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata_filter: dict[str, Any] | None = None
    prompt_context_enabled: bool = False


class RagToolRegistrationRequest(BaseModel):
    registered: bool = True


class RagPromptContextRequest(BaseModel):
    enabled: bool = True


class RagWorkflowBindRequest(BaseModel):
    agent_design_project_id: int | None = None


class RagToolExecuteRequest(BaseModel):
    query: str = Field(min_length=1, max_length=8000)
    top_k: int | None = Field(default=None, ge=1, le=50)
    similarity_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    security_context: dict[str, Any] | None = None


class RagAgentTestPrepareRequest(BaseModel):
    query: str = Field(min_length=1, max_length=8000)


class RagIntelligenceSettingRequest(BaseModel):
    project_root: str = ''
    router_enabled: bool | None = None
    reranking_enabled: bool | None = None
    rerank_top_n: int | None = Field(default=None, ge=1, le=50)


class RagRecommendationRequest(BaseModel):
    project_root: str = ''


class RagRecommendationApplyRequest(BaseModel):
    keys: list[str] = Field(default_factory=list)
    apply_all: bool = False



class RagSourceSyncModeRequest(BaseModel):
    sync_mode: str = 'MANUAL'


class RagActiveRequest(BaseModel):
    active: bool = True


class RagDocumentSecurityRequest(BaseModel):
    security_level: str = 'INTERNAL'
    note: str = ''


class RagAccessRuleCreateRequest(BaseModel):
    project_root: str = ''
    collection_id: int
    subject_type: str = 'ROLE'
    subject_value: str = 'DEVELOPER'
    effect: str = 'ALLOW'


class RagEvaluationCaseCreateRequest(BaseModel):
    project_root: str = ''
    question: str = Field(min_length=1, max_length=8000)
    expected_document_path: str = ''
    expected_text: str = ''


class RagEvaluationRunRequest(BaseModel):
    project_root: str = ''
    security_context: dict[str, Any] | None = None

def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@router.get('/state')
async def rag_state(project_root: str = Query(default='')):
    return await get_or_create_studio_setting(project_root)


@router.put('/state')
async def rag_state_update(req: RagSettingRequest, authorization: str = Header(default='')):
    patch = req.model_dump(exclude={'project_root'}, exclude_none=True)
    before = await get_or_create_studio_setting(req.project_root)
    result = await update_studio_setting(req.project_root, patch)
    member = await _member(authorization)
    if member:
        await upsert_project_setting(member['id'], req.project_root, 'RAG', 'studio', result, history_title='RAG Studio 기본 설정 변경', history_summary='RAG 사용/DB/Scope 설정을 저장했습니다.')
    return result


@router.get('/collections')
async def rag_collections(project_root: str = Query(default='')):
    return {'items': await list_collections(project_root)}


@router.post('/collections')
async def rag_collection_create(req: RagCollectionCreateRequest, authorization: str = Header(default='')):
    try:
        result = await create_collection(req.model_dump())
        await _record(await _member(authorization), req.project_root, category='RAG_KNOWLEDGE', action='CREATE', title='Knowledge Collection 생성', after=result, summary=result.get('name',''))
        return result
    except Exception as exc:
        raise _http_error(exc)


@router.put('/collections/{collection_id}')
async def rag_collection_update(collection_id: int, req: RagCollectionUpdateRequest, authorization: str = Header(default='')):
    try:
        result = await update_collection(collection_id, req.model_dump(exclude_none=True))
        await _record(await _member(authorization), result.get('project_root',''), category='RAG_KNOWLEDGE', action='UPDATE', title='Knowledge Collection 수정', after=result, summary=result.get('name',''))
        return result
    except Exception as exc:
        raise _http_error(exc)


@router.delete('/collections/{collection_id}')
async def rag_collection_delete(collection_id: int, authorization: str = Header(default='')):
    try:
        result = await delete_collection(collection_id)
        await _record(await _member(authorization), result.get('project_root',''), category='RAG_KNOWLEDGE', action='DELETE', title='Knowledge Collection 삭제', after=result)
        return result
    except Exception as exc:
        raise _http_error(exc)


@router.get('/sources')
async def rag_sources(project_root: str = Query(default='')):
    return {'items': await list_sources(project_root)}


@router.post('/sources')
async def rag_source_create(req: RagSourceCreateRequest, authorization: str = Header(default='')):
    try:
        result = await create_source(req.model_dump())
        await _record(await _member(authorization), req.project_root, category='RAG_KNOWLEDGE', action='CREATE', title='RAG Source 등록', after=result, summary=result.get('display_name',''))
        return result
    except Exception as exc:
        raise _http_error(exc)


@router.post('/sources/analyze')
async def rag_source_analyze(req: RagSourceActionRequest):
    try:
        return await analyze_source(req.source_id)
    except Exception as exc:
        raise _http_error(exc)


@router.post('/sources/review')
async def rag_source_review(req: RagSourceActionRequest):
    try:
        return await review_source(req.source_id)
    except Exception as exc:
        raise _http_error(exc)


@router.post('/sources/approve')
async def rag_source_approve(req: RagSourceActionRequest):
    try:
        return await approve_source(req.source_id)
    except Exception as exc:
        raise _http_error(exc)


@router.delete('/sources/{source_id}')
async def rag_source_delete(source_id: int, authorization: str = Header(default='')):
    try:
        result = await delete_source(source_id)
        await _record(await _member(authorization), result.get('project_root',''), category='RAG_KNOWLEDGE', action='DELETE', title='RAG Source 삭제', after=result)
        return result
    except Exception as exc:
        raise _http_error(exc)


@router.post('/database/test')
async def rag_database_test(req: RagDatabaseTestRequest):
    return await test_rag_database(req.database_url or None)

@router.get('/index/config')
async def rag_index_config():
    return indexing_config()


@router.post('/chunk-preview')
async def rag_chunk_preview(req: RagChunkPreviewRequest):
    try:
        return await preview_source_chunks(req.source_id, req.limit)
    except Exception as exc:
        raise _http_error(exc)


@router.get('/index/jobs')
async def rag_index_jobs(project_root: str = Query(default=''), limit: int = Query(default=30, ge=1, le=100)):
    return {'items': await list_index_jobs(project_root, limit)}


@router.get('/index/jobs/{job_id}')
async def rag_index_job(job_id: int):
    try:
        return await get_index_job(job_id)
    except Exception as exc:
        raise _http_error(exc)


@router.post('/index')
async def rag_index_start(req: RagIndexStartRequest, background_tasks: BackgroundTasks):
    try:
        job = await create_index_job(req.source_id)
        if job.get('should_start'):
            background_tasks.add_task(run_index_job, int(job['id']))
        return job
    except Exception as exc:
        raise _http_error(exc)

@router.get('/retrieval/settings')
async def rag_retrieval_settings(project_root: str = Query(default='')):
    return await get_or_create_retrieval_setting(project_root)


@router.put('/retrieval/settings')
async def rag_retrieval_settings_update(req: RagRetrievalSettingRequest, authorization: str = Header(default='')):
    try:
        before = await get_or_create_retrieval_setting(req.project_root)
        patch = req.model_dump(exclude={'project_root'}, exclude_none=True)
        result = await update_retrieval_setting(req.project_root, patch)
        member = await _member(authorization)
        if member:
            await upsert_project_setting(member['id'], req.project_root, 'RAG_RETRIEVAL', 'default', result, history_title='RAG Retrieval 설정 변경', history_summary='Search Mode / Top K / Threshold / Metadata Filter를 저장했습니다.')
        return result
    except Exception as exc:
        raise _http_error(exc)


@router.get('/retrieval/options')
async def rag_retrieval_options(project_root: str = Query(default='')):
    try:
        return await retrieval_options(project_root)
    except Exception as exc:
        raise _http_error(exc)


@router.post('/retrieve')
async def rag_retrieve(req: RagRetrieveRequest):
    try:
        return await retrieve(req.model_dump())
    except Exception as exc:
        raise _http_error(exc)


@router.get('/search-logs')
async def rag_search_logs(project_root: str = Query(default=''), limit: int = Query(default=30, ge=1, le=100)):
    return {'items': await list_search_logs(project_root, limit)}

@router.get('/intelligence/settings')
async def rag_intelligence_settings(project_root: str = Query(default='')):
    return await get_or_create_intelligence_setting(project_root)


@router.put('/intelligence/settings')
async def rag_intelligence_settings_update(req: RagIntelligenceSettingRequest, authorization: str = Header(default='')):
    try:
        patch = req.model_dump(exclude={'project_root'}, exclude_none=True)
        result = await update_intelligence_setting(req.project_root, patch)
        member = await _member(authorization)
        if member:
            await upsert_project_setting(member['id'], req.project_root, 'RAG_INTELLIGENCE', 'default', result, history_title='RAG Intelligence 설정 변경', history_summary='Router / Reranking 설정을 저장했습니다.')
        return result
    except Exception as exc:
        raise _http_error(exc)


@router.get('/evaluation')
async def rag_evaluation(project_root: str = Query(default='')):
    try:
        return await evaluate_rag_settings(project_root)
    except Exception as exc:
        raise _http_error(exc)


@router.post('/recommendations')
async def rag_recommendation_create(req: RagRecommendationRequest):
    try:
        return await create_ai_recommendation(req.project_root)
    except Exception as exc:
        raise _http_error(exc)


@router.get('/recommendations')
async def rag_recommendations(project_root: str = Query(default=''), limit: int = Query(default=10, ge=1, le=50)):
    try:
        return {'items': await list_recommendations(project_root, limit)}
    except Exception as exc:
        raise _http_error(exc)


@router.post('/recommendations/{recommendation_id}/apply')
async def rag_recommendation_apply(recommendation_id: int, req: RagRecommendationApplyRequest):
    try:
        return await apply_ai_recommendation(recommendation_id, req.keys, apply_all=req.apply_all)
    except Exception as exc:
        raise _http_error(exc)


@router.get('/tools')
async def rag_tools(project_root: str = Query(default='')):
    try:
        return {'items': await list_agent_tools(project_root)}
    except Exception as exc:
        raise _http_error(exc)


@router.post('/tools/generate')
async def rag_tool_generate(req: RagToolGenerateRequest):
    try:
        return await generate_agent_tool(req.model_dump())
    except Exception as exc:
        raise _http_error(exc)


@router.put('/tools/{tool_id}/prompt-context')
async def rag_tool_prompt_context(tool_id: int, req: RagPromptContextRequest):
    try:
        return await update_prompt_context(tool_id, req.enabled)
    except Exception as exc:
        raise _http_error(exc)


@router.post('/tools/{tool_id}/register')
async def rag_tool_register(tool_id: int, req: RagToolRegistrationRequest):
    try:
        return await mark_prompt_tool_registered(tool_id, req.registered)
    except Exception as exc:
        raise _http_error(exc)


@router.post('/tools/{tool_id}/workflow-bind')
async def rag_tool_workflow_bind(tool_id: int, req: RagWorkflowBindRequest):
    try:
        return await bind_workflow(tool_id, req.agent_design_project_id)
    except Exception as exc:
        raise _http_error(exc)


@router.post('/tools/{tool_id}/execute')
async def rag_tool_execute(tool_id: int, req: RagToolExecuteRequest):
    try:
        return await execute_rag_tool(tool_id, req.model_dump(exclude_none=True), test_mode='RAG_STUDIO_TOOL_TEST')
    except Exception as exc:
        raise _http_error(exc)


@router.post('/tools/{tool_id}/agent-test/prepare')
async def rag_tool_agent_test_prepare(tool_id: int, req: RagAgentTestPrepareRequest):
    try:
        return await prepare_agent_test(tool_id, req.query)
    except Exception as exc:
        raise _http_error(exc)


@router.get('/agent-test-logs')
async def rag_agent_test_logs(project_root: str = Query(default=''), limit: int = Query(default=30, ge=1, le=100)):
    try:
        return {'items': await list_agent_test_logs(project_root, limit)}
    except Exception as exc:
        raise _http_error(exc)

# ---- Phase-6 Operation / Security / Evaluation ----

@router.get('/operation/sources')
async def rag_operation_sources(project_root: str = Query(default='')):
    try:
        return {'items': await list_operation_sources(project_root)}
    except Exception as exc:
        raise _http_error(exc)


@router.put('/operation/sources/{source_id}/sync-mode')
async def rag_operation_source_sync_mode(source_id: int, req: RagSourceSyncModeRequest, authorization: str = Header(default='')):
    try:
        result = await set_source_sync_mode(source_id, req.sync_mode)
        await _record(await _member(authorization), result.get('project_root',''), category='RAG_OPERATION', action='UPDATE', title='RAG Source Sync Mode 변경', after=result, summary=req.sync_mode)
        return result
    except Exception as exc:
        raise _http_error(exc)


@router.post('/operation/sources/{source_id}/changes')
async def rag_operation_source_changes(source_id: int):
    try:
        return await detect_source_changes(source_id)
    except Exception as exc:
        raise _http_error(exc)


@router.post('/operation/sources/{source_id}/sync')
async def rag_operation_source_sync(source_id: int, background_tasks: BackgroundTasks, authorization: str = Header(default='')):
    try:
        job = await create_sync_job(source_id)
        if job.get('should_start'):
            background_tasks.add_task(run_sync_job, int(job['id']))
        await _record(await _member(authorization), job.get('project_root',''), category='RAG_OPERATION', action='SYNC', title='RAG Source 증분 Re-index 시작', after=job, summary=f"Source {source_id}")
        return job
    except Exception as exc:
        raise _http_error(exc)


@router.get('/operation/sync-jobs')
async def rag_operation_sync_jobs(project_root: str = Query(default=''), limit: int = Query(default=30, ge=1, le=100)):
    return {'items': await list_sync_jobs(project_root, limit)}


@router.get('/operation/sync-jobs/{job_id}')
async def rag_operation_sync_job(job_id: int):
    try:
        return await get_sync_job(job_id)
    except Exception as exc:
        raise _http_error(exc)


@router.put('/operation/sources/{source_id}/active')
async def rag_operation_source_active(source_id: int, req: RagActiveRequest, authorization: str = Header(default='')):
    try:
        result = await set_source_active(source_id, req.active)
        await _record(await _member(authorization), result.get('project_root',''), category='RAG_OPERATION', action='ENABLE' if req.active else 'DISABLE', title='RAG Source 활성 상태 변경', after=result)
        return result
    except Exception as exc:
        raise _http_error(exc)


@router.get('/operation/documents')
async def rag_operation_documents(project_root: str = Query(default=''), source_id: int | None = Query(default=None)):
    try:
        return {'items': await list_operation_documents(project_root, source_id)}
    except Exception as exc:
        raise _http_error(exc)


@router.put('/operation/documents/{document_id}/active')
async def rag_operation_document_active(document_id: int, req: RagActiveRequest, authorization: str = Header(default='')):
    try:
        result = await set_document_active(document_id, req.active)
        await _record(await _member(authorization), result.get('project_root',''), category='RAG_OPERATION', action='ENABLE' if req.active else 'DISABLE', title='RAG Document 활성 상태 변경', after=result)
        return result
    except Exception as exc:
        raise _http_error(exc)


@router.get('/operation/documents/{document_id}/versions')
async def rag_operation_document_versions(document_id: int):
    try:
        return {'items': await list_document_versions(document_id)}
    except Exception as exc:
        raise _http_error(exc)


@router.post('/operation/versions/{version_id}/rollback')
async def rag_operation_version_rollback(version_id: int, authorization: str = Header(default='')):
    try:
        result = await rollback_document_version(version_id)
        await _record(await _member(authorization), result.get('project_root',''), category='RAG_OPERATION', action='ROLLBACK', title='RAG Document Version Rollback', after=result, summary=f"Version {result.get('version_no','')}")
        return result
    except Exception as exc:
        raise _http_error(exc)


@router.put('/security/documents/{document_id}')
async def rag_security_document(document_id: int, req: RagDocumentSecurityRequest, authorization: str = Header(default='')):
    try:
        result = await set_document_security(document_id, req.security_level, req.note)
        await _record(await _member(authorization), result.get('project_root',''), category='RAG_SECURITY', action='UPDATE', title='RAG 문서 보안등급 변경', after=result, summary=req.security_level)
        return result
    except Exception as exc:
        raise _http_error(exc)


@router.get('/security/access-rules')
async def rag_security_access_rules(project_root: str = Query(default='')):
    return {'items': await list_access_rules(project_root)}


@router.post('/security/access-rules')
async def rag_security_access_rule_create(req: RagAccessRuleCreateRequest, authorization: str = Header(default='')):
    try:
        result = await create_access_rule(req.model_dump())
        await _record(await _member(authorization), req.project_root, category='RAG_SECURITY', action='CREATE', title='RAG Access Rule 추가', after=result, summary=f"{req.subject_type}:{req.subject_value} {req.effect}")
        return result
    except Exception as exc:
        raise _http_error(exc)


@router.delete('/security/access-rules/{rule_id}')
async def rag_security_access_rule_delete(rule_id: int, authorization: str = Header(default='')):
    try:
        result = await delete_access_rule(rule_id)
        await _record(await _member(authorization), result.get('project_root',''), category='RAG_SECURITY', action='DELETE', title='RAG Access Rule 삭제', after=result)
        return result
    except Exception as exc:
        raise _http_error(exc)


@router.get('/security/audit-logs')
async def rag_security_audit_logs(project_root: str = Query(default=''), limit: int = Query(default=100, ge=1, le=500)):
    return {'items': await list_search_audits(project_root, limit)}


@router.get('/evaluation/cases')
async def rag_evaluation_cases(project_root: str = Query(default='')):
    return {'items': await list_evaluation_cases(project_root)}


@router.post('/evaluation/cases')
async def rag_evaluation_case_create(req: RagEvaluationCaseCreateRequest, authorization: str = Header(default='')):
    try:
        result = await create_evaluation_case(req.model_dump())
        await _record(await _member(authorization), req.project_root, category='RAG_EVALUATION', action='CREATE', title='RAG Evaluation Case 추가', after=result, summary=req.question[:180])
        return result
    except Exception as exc:
        raise _http_error(exc)


@router.delete('/evaluation/cases/{case_id}')
async def rag_evaluation_case_delete(case_id: int):
    try:
        return await delete_evaluation_case(case_id)
    except Exception as exc:
        raise _http_error(exc)


@router.post('/evaluation/runs')
async def rag_evaluation_run_create(req: RagEvaluationRunRequest, background_tasks: BackgroundTasks):
    try:
        run = await create_evaluation_run(req.project_root, req.security_context)
        if run.get('should_start'):
            background_tasks.add_task(run_evaluation, int(run['id']))
        return run
    except Exception as exc:
        raise _http_error(exc)


@router.get('/evaluation/runs')
async def rag_evaluation_runs(project_root: str = Query(default=''), limit: int = Query(default=30, ge=1, le=100)):
    return {'items': await list_evaluation_runs(project_root, limit)}


@router.get('/evaluation/runs/{run_id}')
async def rag_evaluation_run(run_id: int):
    try:
        return await get_evaluation_run(run_id)
    except Exception as exc:
        raise _http_error(exc)

