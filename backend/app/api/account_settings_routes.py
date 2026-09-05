from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.services.account_setting_service import (
    append_project_history,
    create_project_history_sql_scratch,
    get_account_database_profile,
    get_project_setting,
    list_account_database_profiles,
    list_account_setting_profiles,
    list_project_history,
    list_project_settings,
    project_history_detail,
    upsert_account_database_profile,
    upsert_account_setting_profile,
    upsert_project_setting,
)
from app.services.auth_service import authenticate_token

router = APIRouter(prefix='/account-settings', tags=['Account Settings'])


def _bearer(value: str) -> str:
    return value[7:].strip() if str(value or '').lower().startswith('bearer ') else ''


async def _current(authorization: str) -> dict:
    member = await authenticate_token(_bearer(authorization))
    if not member:
        raise HTTPException(status_code=401, detail='로그인이 필요합니다.')
    return member


class DatabaseProfileRequest(BaseModel):
    profile: dict = Field(default_factory=dict)


class AccountSettingProfileRequest(BaseModel):
    setting_group: str
    profile_name: str
    value: dict = Field(default_factory=dict)
    is_default: bool = False


class ProjectSettingRequest(BaseModel):
    project_root: str
    setting_group: str
    setting_key: str = 'default'
    value: dict = Field(default_factory=dict)
    source_profile_id: int | None = None
    title: str = ''
    summary: str = ''


class ProjectHistoryRequest(BaseModel):
    project_root: str
    category: str = 'GENERAL'
    action: str = 'UPDATE'
    title: str
    summary: str = ''
    before: dict = Field(default_factory=dict)
    after: dict = Field(default_factory=dict)


class ProjectHistorySqlRequest(BaseModel):
    project_root: str = ''


@router.get('/database-profiles')
async def account_database_profiles(authorization: str = Header(default='')):
    member = await _current(authorization)
    return {'ok': True, 'items': await list_account_database_profiles(member['id'])}


@router.post('/database-profiles')
async def save_account_database_profile(req: DatabaseProfileRequest, authorization: str = Header(default='')):
    member = await _current(authorization)
    try:
        return {'ok': True, 'profile': await upsert_account_database_profile(member['id'], req.profile)}
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get('/profiles')
async def account_setting_profiles(setting_group: str = Query(''), authorization: str = Header(default='')):
    member = await _current(authorization)
    return {'ok': True, 'items': await list_account_setting_profiles(member['id'], setting_group)}


@router.post('/profiles')
async def save_account_setting_profile(req: AccountSettingProfileRequest, authorization: str = Header(default='')):
    member = await _current(authorization)
    return {'ok': True, 'profile': await upsert_account_setting_profile(member['id'], req.setting_group, req.profile_name, req.value, is_default=req.is_default)}


@router.get('/project')
async def project_settings(project_root: str = Query(...), authorization: str = Header(default='')):
    member = await _current(authorization)
    items = await list_project_settings(member['id'], project_root)
    db_profiles = await list_account_database_profiles(member['id'])
    return {
        'ok': True,
        'project_root': project_root,
        'items': items,
        'has_project_settings': bool(items),
        'account_database_profiles': db_profiles,
    }


@router.get('/project/value')
async def project_setting_value(project_root: str = Query(...), setting_group: str = Query(...), setting_key: str = Query('default'), authorization: str = Header(default='')):
    member = await _current(authorization)
    row = await get_project_setting(member['id'], project_root, setting_group, setting_key)
    return {'ok': True, 'item': row}


@router.put('/project')
async def save_project_setting(req: ProjectSettingRequest, authorization: str = Header(default='')):
    member = await _current(authorization)
    result = await upsert_project_setting(
        member['id'],
        req.project_root,
        req.setting_group,
        req.setting_key,
        req.value,
        source_profile_id=req.source_profile_id,
        history_title=req.title or f'{req.setting_group} 설정 저장',
        history_summary=req.summary,
    )
    return {'ok': True, 'item': result}


@router.get('/history')
async def project_history(project_root: str = Query(...), limit: int = Query(100), authorization: str = Header(default='')):
    member = await _current(authorization)
    return {'ok': True, 'items': await list_project_history(member['id'], project_root, limit)}


@router.get('/history/{history_id}')
async def project_history_item(history_id: int, authorization: str = Header(default='')):
    member = await _current(authorization)
    row = await project_history_detail(member['id'], history_id)
    if row is None:
        raise HTTPException(status_code=404, detail='수정 이력을 찾을 수 없습니다.')
    return {'ok': True, 'item': row}


@router.post('/history/{history_id}/sql')
async def project_history_sql(history_id: int, req: ProjectHistorySqlRequest, authorization: str = Header(default='')):
    member = await _current(authorization)
    try:
        result = await create_project_history_sql_scratch(member['id'], history_id, project_root=req.project_root)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail='수정 이력을 찾을 수 없습니다.')
    return result


@router.post('/history')
async def save_project_history(req: ProjectHistoryRequest, authorization: str = Header(default='')):
    member = await _current(authorization)
    row = await append_project_history(
        member['id'], req.project_root, category=req.category, action=req.action, title=req.title,
        summary=req.summary, before=req.before, after=req.after,
    )
    return {'ok': True, 'item': row}


@router.get('/database-profiles/{account_profile_id}')
async def account_database_profile(account_profile_id: int, authorization: str = Header(default='')):
    member = await _current(authorization)
    row = await get_account_database_profile(member['id'], account_profile_id)
    if not row:
        raise HTTPException(status_code=404, detail='계정 DB 설정을 찾을 수 없습니다.')
    return {'ok': True, 'profile': row}
