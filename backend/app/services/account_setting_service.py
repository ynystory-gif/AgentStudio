from __future__ import annotations

import os
from copy import deepcopy
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.account_setting_entities import (
    AccountDatabaseProfile,
    AccountProjectSetting,
    AccountSettingProfile,
    ProjectSettingHistory,
)


def normalize_project_key(project_root: str) -> str:
    raw = str(project_root or '').strip()
    if not raw:
        return ''
    return os.path.normcase(os.path.normpath(os.path.abspath(os.path.expanduser(raw))))


def _safe_profile(profile: dict[str, Any]) -> dict[str, Any]:
    data = deepcopy(profile or {})
    for key in ('password', '_password_dpapi', 'service_account_json_content', 'private_key', 'token', 'api_key'):
        data.pop(key, None)
    return data


def _history_payload(row: ProjectSettingHistory, *, detail: bool = False) -> dict[str, Any]:
    result = {
        'project_setting_histories_id': row.project_setting_histories_id,
        'id': row.project_setting_histories_id,
        'category': row.category,
        'action': row.action,
        'title': row.title,
        'summary': row.summary,
        'project_root': row.project_root,
        'created_at': row.created_at.isoformat() if row.created_at else '',
    }
    if detail:
        result['before'] = row.before_json or {}
        result['after'] = row.after_json or {}
    return result


async def upsert_account_database_profile(member_id: str, profile: dict[str, Any]) -> dict[str, Any]:
    clean = _safe_profile(profile)
    connection_id = str(clean.get('connection_id') or '').strip()
    if not connection_id:
        raise ValueError('connection_id가 필요합니다.')
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(AccountDatabaseProfile).where(
                    AccountDatabaseProfile.member_id == member_id,
                    AccountDatabaseProfile.connection_id == connection_id,
                )
            )
        ).scalar_one_or_none()
        now = datetime.utcnow()
        if row is None:
            row = AccountDatabaseProfile(
                member_id=member_id,
                connection_id=connection_id,
                created_at=now,
            )
            session.add(row)
        row.name = str(clean.get('name') or '').strip()
        row.db_type = str(clean.get('db_type') or 'postgresql').strip().lower()
        row.profile_json = clean
        row.credential_saved = bool(profile.get('credential_saved'))
        row.credential_storage = 'WINDOWS_DPAPI' if row.credential_saved else 'NONE'
        row.updated_at = now
        await session.commit()
        await session.refresh(row)
        return account_database_profile_payload(row)


def account_database_profile_payload(row: AccountDatabaseProfile) -> dict[str, Any]:
    payload = dict(row.profile_json or {})
    payload.update({
        'account_database_profiles_id': row.account_database_profiles_id,
        'account_profile_id': row.account_database_profiles_id,
        'connection_id': row.connection_id,
        'name': row.name,
        'db_type': row.db_type,
        'credential_saved': bool(row.credential_saved),
        'credential_storage': row.credential_storage,
        'updated_at': row.updated_at.isoformat() if row.updated_at else '',
    })
    return payload


async def list_account_database_profiles(member_id: str) -> list[dict[str, Any]]:
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(AccountDatabaseProfile)
                .where(AccountDatabaseProfile.member_id == member_id)
                .order_by(AccountDatabaseProfile.updated_at.desc(), AccountDatabaseProfile.account_database_profiles_id.desc())
            )
        ).scalars().all()
        return [account_database_profile_payload(row) for row in rows]


async def delete_account_database_profile(member_id: str, connection_id: str) -> None:
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(AccountDatabaseProfile).where(
                    AccountDatabaseProfile.member_id == member_id,
                    AccountDatabaseProfile.connection_id == str(connection_id or ''),
                )
            )
        ).scalar_one_or_none()
        if row:
            await session.delete(row)
            await session.commit()


async def get_account_database_profile(member_id: str, account_profile_id: int) -> dict[str, Any] | None:
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(AccountDatabaseProfile).where(
                    AccountDatabaseProfile.member_id == member_id,
                    AccountDatabaseProfile.account_database_profiles_id == int(account_profile_id),
                )
            )
        ).scalar_one_or_none()
        return account_database_profile_payload(row) if row else None


async def append_project_history(
    member_id: str,
    project_root: str,
    *,
    category: str,
    action: str,
    title: str,
    summary: str = '',
    before: dict[str, Any] | None = None,
    after: dict[str, Any] | None = None,
) -> dict[str, Any]:
    key = normalize_project_key(project_root)
    row = ProjectSettingHistory(
        member_id=member_id,
        project_root=str(project_root or '').strip(),
        project_key=key,
        category=str(category or 'GENERAL').upper(),
        action=str(action or 'UPDATE').upper(),
        title=str(title or '').strip(),
        summary=str(summary or '').strip(),
        before_json=before or {},
        after_json=after or {},
        created_at=datetime.utcnow(),
    )
    async with SessionLocal() as session:
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return _history_payload(row, detail=True)


async def upsert_project_setting(
    member_id: str,
    project_root: str,
    setting_group: str,
    setting_key: str,
    value: dict[str, Any],
    *,
    source_profile_id: int | None = None,
    history_title: str = '',
    history_summary: str = '',
    history_action: str = 'UPDATE',
) -> dict[str, Any]:
    project_key = normalize_project_key(project_root)
    group = str(setting_group or 'GENERAL').strip().upper()
    key = str(setting_key or 'default').strip()
    before: dict[str, Any] = {}
    row_id = 0
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(AccountProjectSetting).where(
                    AccountProjectSetting.member_id == member_id,
                    AccountProjectSetting.project_key == project_key,
                    AccountProjectSetting.setting_group == group,
                    AccountProjectSetting.setting_key == key,
                )
            )
        ).scalar_one_or_none()
        now = datetime.utcnow()
        if row is None:
            row = AccountProjectSetting(
                member_id=member_id,
                project_root=str(project_root or '').strip(),
                project_key=project_key,
                setting_group=group,
                setting_key=key,
                created_at=now,
            )
            session.add(row)
        else:
            before = dict(row.value_json or {})
        row.value_json = deepcopy(value or {})
        row.source_profile_id = source_profile_id
        row.updated_at = now
        await session.commit()
        await session.refresh(row)
        row_id = row.account_project_settings_id
    if history_title and before != (value or {}):
        await append_project_history(
            member_id,
            project_root,
            category=group,
            action=history_action,
            title=history_title,
            summary=history_summary,
            before=before,
            after=value or {},
        )
    return {
        'account_project_settings_id': row_id,
        'setting_group': group,
        'setting_key': key,
        'value': value or {},
        'source_profile_id': source_profile_id,
        'project_root': str(project_root or '').strip(),
    }


async def list_project_settings(member_id: str, project_root: str) -> list[dict[str, Any]]:
    project_key = normalize_project_key(project_root)
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(AccountProjectSetting)
                .where(
                    AccountProjectSetting.member_id == member_id,
                    AccountProjectSetting.project_key == project_key,
                )
                .order_by(AccountProjectSetting.setting_group, AccountProjectSetting.setting_key)
            )
        ).scalars().all()
    return [{
        'account_project_settings_id': row.account_project_settings_id,
        'setting_group': row.setting_group,
        'setting_key': row.setting_key,
        'value': row.value_json or {},
        'source_profile_id': row.source_profile_id,
        'updated_at': row.updated_at.isoformat() if row.updated_at else '',
    } for row in rows]


async def get_project_setting(member_id: str, project_root: str, setting_group: str, setting_key: str = 'default') -> dict[str, Any] | None:
    project_key = normalize_project_key(project_root)
    group = str(setting_group or '').upper()
    key = str(setting_key or 'default')
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(AccountProjectSetting).where(
                    AccountProjectSetting.member_id == member_id,
                    AccountProjectSetting.project_key == project_key,
                    AccountProjectSetting.setting_group == group,
                    AccountProjectSetting.setting_key == key,
                )
            )
        ).scalar_one_or_none()
        if not row:
            return None
        return {
            'account_project_settings_id': row.account_project_settings_id,
            'setting_group': row.setting_group,
            'setting_key': row.setting_key,
            'value': row.value_json or {},
            'source_profile_id': row.source_profile_id,
            'updated_at': row.updated_at.isoformat() if row.updated_at else '',
        }


async def upsert_account_setting_profile(member_id: str, setting_group: str, profile_name: str, value: dict[str, Any], *, is_default: bool = False) -> dict[str, Any]:
    group = str(setting_group or 'GENERAL').upper()
    name = str(profile_name or '기본 설정').strip()
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(AccountSettingProfile).where(
                    AccountSettingProfile.member_id == member_id,
                    AccountSettingProfile.setting_group == group,
                    AccountSettingProfile.profile_name == name,
                )
            )
        ).scalar_one_or_none()
        now = datetime.utcnow()
        if row is None:
            row = AccountSettingProfile(member_id=member_id, setting_group=group, profile_name=name, created_at=now)
            session.add(row)
        if is_default:
            siblings = (
                await session.execute(
                    select(AccountSettingProfile).where(
                        AccountSettingProfile.member_id == member_id,
                        AccountSettingProfile.setting_group == group,
                    )
                )
            ).scalars().all()
            for sibling in siblings:
                sibling.is_default = False
        row.value_json = deepcopy(value or {})
        row.is_default = bool(is_default)
        row.updated_at = now
        await session.commit()
        await session.refresh(row)
        return {
            'account_setting_profiles_id': row.account_setting_profiles_id,
            'setting_group': row.setting_group,
            'profile_name': row.profile_name,
            'value': row.value_json or {},
            'is_default': bool(row.is_default),
            'updated_at': row.updated_at.isoformat() if row.updated_at else '',
        }


async def list_account_setting_profiles(member_id: str, setting_group: str = '') -> list[dict[str, Any]]:
    async with SessionLocal() as session:
        stmt = select(AccountSettingProfile).where(AccountSettingProfile.member_id == member_id)
        if setting_group:
            stmt = stmt.where(AccountSettingProfile.setting_group == str(setting_group).upper())
        rows = (await session.execute(stmt.order_by(AccountSettingProfile.is_default.desc(), AccountSettingProfile.updated_at.desc()))).scalars().all()
        return [{
            'account_setting_profiles_id': row.account_setting_profiles_id,
            'setting_group': row.setting_group,
            'profile_name': row.profile_name,
            'value': row.value_json or {},
            'is_default': bool(row.is_default),
            'updated_at': row.updated_at.isoformat() if row.updated_at else '',
        } for row in rows]


async def list_project_history(member_id: str, project_root: str, limit: int = 100) -> list[dict[str, Any]]:
    project_key = normalize_project_key(project_root)
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(ProjectSettingHistory)
                .where(
                    ProjectSettingHistory.member_id == member_id,
                    ProjectSettingHistory.project_key == project_key,
                )
                .order_by(ProjectSettingHistory.created_at.desc(), ProjectSettingHistory.project_setting_histories_id.desc())
                .limit(max(1, min(int(limit or 100), 500)))
            )
        ).scalars().all()
        return [_history_payload(row) for row in rows]


async def project_history_detail(member_id: str, history_id: int) -> dict[str, Any] | None:
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(ProjectSettingHistory).where(
                    ProjectSettingHistory.member_id == member_id,
                    ProjectSettingHistory.project_setting_histories_id == int(history_id),
                )
            )
        ).scalar_one_or_none()
        return _history_payload(row, detail=True) if row else None


_DESIGN_SNAPSHOT_GROUPS = {
    'confirmed_requirements': 'REQUIREMENTS',
    'manual_requirement_overrides': 'REQUIREMENTS_OVERRIDE',
    'runtime_setup': 'RUNTIME',
    'database_setup': 'DATABASE',
    'database_resource_plan': 'DATABASE_RESOURCE_PLAN',
    'ui_layout': 'UI_LAYOUT',
    'tool_prompt_settings': 'TOOL_PROMPT',
    'prompt_tool_studio': 'PROMPT_TOOL_STUDIO',
    'development_stage_plan': 'DEVELOPMENT_STAGE',
    'requirement_recommendation_settings': 'RECOMMENDATION',
    'user_coding_style': 'CODING_STYLE',
    'code_documentation': 'CODE_DOCUMENTATION',
}


async def sync_design_snapshot(member_id: str, project_root: str, snapshot: dict[str, Any], *, title_prefix: str = 'Agent 설계 저장') -> int:
    if not project_root:
        return 0
    changed = 0
    for snapshot_key, group in _DESIGN_SNAPSHOT_GROUPS.items():
        if snapshot_key not in snapshot:
            continue
        value = snapshot.get(snapshot_key)
        if value is None:
            continue
        if not isinstance(value, dict):
            value = {'value': value}
        previous = await get_project_setting(member_id, project_root, group, 'default')
        before = (previous or {}).get('value') or {}
        if before == value:
            continue
        await upsert_project_setting(
            member_id,
            project_root,
            group,
            'default',
            value,
            history_title=f'{title_prefix} · {group}',
            history_summary=f'{group} 프로젝트 설정이 저장되었습니다.',
        )
        changed += 1
    return changed
