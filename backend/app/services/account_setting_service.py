from __future__ import annotations

import json
import os
import re
from pathlib import Path
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


def _json_equal(left: Any, right: Any) -> bool:
    """Deterministic JSON comparison used by every project-setting save path.

    A save button may be clicked repeatedly, but an unchanged project setting must
    not create another DB write/history row or update timestamp.
    """
    try:
        return json.dumps(left, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str) == json.dumps(right, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    except Exception:
        return left == right


def _sql_literal(value: str) -> str:
    return "'" + str(value or '').replace("'", "''") + "'"


def _looks_like_sql(value: str) -> bool:
    text = str(value or '').lstrip()
    return bool(re.match(r'(?is)^(?:--[^\n]*\n\s*)*(SELECT|WITH|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP|TRUNCATE|GRANT|REVOKE|EXPLAIN|CALL|DO)\b', text))


def _collect_sql_fragments(value: Any, path: str = '') -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, dict):
        for key, item in value.items():
            child = f'{path}.{key}' if path else str(key)
            key_text = str(key).casefold()
            if isinstance(item, str) and (
                _looks_like_sql(item)
                or any(token in key_text for token in ('sql', 'ddl', 'query', 'statement', 'migration'))
            ):
                text = item.strip()
                if text:
                    found.append((child, text))
            else:
                found.extend(_collect_sql_fragments(item, child))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_collect_sql_fragments(item, f'{path}[{index}]'))
    elif isinstance(value, str) and _looks_like_sql(value):
        found.append((path or 'value', value.strip()))
    return found


def _safe_scratch_name(value: str) -> str:
    normalized = re.sub(r'[^A-Za-z0-9가-힣_.-]+', '_', str(value or '').strip())
    return normalized.strip('._')[:80] or 'history'


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
        created = row is None
        requested_name = str(clean.get('name') or '').strip()
        requested_type = str(clean.get('db_type') or 'postgresql').strip().lower()
        requested_credential_saved = bool(profile.get('credential_saved'))
        requested_storage = 'WINDOWS_DPAPI' if requested_credential_saved else 'NONE'
        if row is None:
            row = AccountDatabaseProfile(
                member_id=member_id,
                connection_id=connection_id,
                created_at=now,
            )
            session.add(row)
        else:
            unchanged = (
                str(row.name or '') == requested_name
                and str(row.db_type or '') == requested_type
                and _json_equal(dict(row.profile_json or {}), clean)
                and bool(row.credential_saved) == requested_credential_saved
                and str(row.credential_storage or '') == requested_storage
            )
            if unchanged:
                payload = account_database_profile_payload(row)
                payload.update({'changed': False, 'saved': False, 'message': '변경사항이 없어 저장하지 않았습니다.'})
                return payload
        row.name = requested_name
        row.db_type = requested_type
        row.profile_json = clean
        row.credential_saved = requested_credential_saved
        row.credential_storage = requested_storage
        row.updated_at = now
        await session.commit()
        await session.refresh(row)
        payload = account_database_profile_payload(row)
        payload.update({'changed': True, 'saved': True, 'created': created, 'message': '저장했습니다.'})
        return payload


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
    category_value = str(category or 'GENERAL').upper()
    action_value = str(action or 'UPDATE').upper()
    title_value = str(title or '').strip()
    summary_value = str(summary or '').strip()
    before_value = deepcopy(before or {})
    after_value = deepcopy(after or {})
    async with SessionLocal() as session:
        # Repeated clicks on the same save/apply button must not create another
        # history row when the effective before/after payload has not changed.
        latest = (
            await session.execute(
                select(ProjectSettingHistory)
                .where(
                    ProjectSettingHistory.member_id == member_id,
                    ProjectSettingHistory.project_key == key,
                    ProjectSettingHistory.category == category_value,
                    ProjectSettingHistory.action == action_value,
                    ProjectSettingHistory.title == title_value,
                )
                .order_by(ProjectSettingHistory.project_setting_histories_id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if (
            latest is not None
            and str(latest.summary or '') == summary_value
            and _json_equal(latest.before_json or {}, before_value)
            and _json_equal(latest.after_json or {}, after_value)
        ):
            payload = _history_payload(latest, detail=True)
            payload.update({
                'changed': False,
                'saved': False,
                'duplicate': True,
                'message': '변경사항이 없어 이력을 추가하지 않았습니다.',
            })
            return payload

        row = ProjectSettingHistory(
            member_id=member_id,
            project_root=str(project_root or '').strip(),
            project_key=key,
            category=category_value,
            action=action_value,
            title=title_value,
            summary=summary_value,
            before_json=before_value,
            after_json=after_value,
            created_at=datetime.utcnow(),
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        payload = _history_payload(row, detail=True)
        payload.update({'changed': True, 'saved': True, 'duplicate': False})
        return payload


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
    incoming = deepcopy(value or {})
    before: dict[str, Any] = {}
    row_id = 0
    changed = False
    created = False
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
            created = True
            changed = True
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
            changed = (not _json_equal(before, incoming)) or row.source_profile_id != source_profile_id
            if not changed:
                return {
                    'account_project_settings_id': row.account_project_settings_id,
                    'setting_group': group,
                    'setting_key': key,
                    'value': before,
                    'source_profile_id': row.source_profile_id,
                    'project_root': str(project_root or '').strip(),
                    'changed': False,
                    'saved': False,
                    'message': '변경사항이 없어 저장하지 않았습니다.',
                }
        row.value_json = incoming
        row.source_profile_id = source_profile_id
        row.updated_at = now
        await session.commit()
        await session.refresh(row)
        row_id = row.account_project_settings_id
    if history_title and changed:
        await append_project_history(
            member_id,
            project_root,
            category=group,
            action=history_action,
            title=history_title,
            summary=history_summary,
            before=before,
            after=incoming,
        )
    return {
        'account_project_settings_id': row_id,
        'setting_group': group,
        'setting_key': key,
        'value': incoming,
        'source_profile_id': source_profile_id,
        'project_root': str(project_root or '').strip(),
        'changed': changed,
        'saved': changed,
        'created': created,
        'message': '저장했습니다.' if changed else '변경사항이 없어 저장하지 않았습니다.',
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
        created = row is None
        incoming = deepcopy(value or {})
        if row is not None and _json_equal(dict(row.value_json or {}), incoming) and bool(row.is_default) == bool(is_default):
            return {
                'account_setting_profiles_id': row.account_setting_profiles_id,
                'setting_group': row.setting_group,
                'profile_name': row.profile_name,
                'value': row.value_json or {},
                'is_default': bool(row.is_default),
                'updated_at': row.updated_at.isoformat() if row.updated_at else '',
                'changed': False,
                'saved': False,
                'message': '변경사항이 없어 저장하지 않았습니다.',
            }
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
        row.value_json = incoming
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
            'changed': True,
            'saved': True,
            'created': created,
            'message': '저장했습니다.',
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


async def create_project_history_sql_scratch(
    member_id: str,
    history_id: int,
    *,
    project_root: str = '',
) -> dict[str, Any] | None:
    """Create a project-local temporary .sql file for one history record.

    If the history payload contains actual SQL/DDL/query text it is copied into the
    scratch file.  Otherwise the file still contains a safe SELECT that opens the
    exact history row plus JSON snapshots as comments.  Nothing is auto-executed.
    """
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(ProjectSettingHistory).where(
                    ProjectSettingHistory.member_id == member_id,
                    ProjectSettingHistory.project_setting_histories_id == int(history_id),
                )
            )
        ).scalar_one_or_none()
        if row is None:
            return None
        row_root = str(row.project_root or '').strip()
        if project_root and normalize_project_key(project_root) != normalize_project_key(row_root):
            raise ValueError('요청 프로젝트와 수정 이력의 프로젝트가 다릅니다.')
        payload = _history_payload(row, detail=True)

    root = Path(row_root or project_root).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError('수정 이력의 프로젝트 경로를 찾을 수 없습니다.')
    scratch_dir = root / '.agentstudio' / 'sql_scratch'
    scratch_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]
    file_name = f'history_{int(history_id)}_{_safe_scratch_name(payload.get("category") or "GENERAL")}_{stamp}.sql'
    path = scratch_dir / file_name

    before = payload.get('before') or {}
    after = payload.get('after') or {}
    fragments = _collect_sql_fragments(before, 'before') + _collect_sql_fragments(after, 'after')
    deduped: list[tuple[str, str]] = []
    seen: set[str] = set()
    for source, sql in fragments:
        key = sql.strip()
        if key and key not in seen:
            seen.add(key)
            deduped.append((source, key))

    lines = [
        '-- THEANOVA AgentStudio · 프로젝트 수정 이력 SQL 임시 파일',
        f'-- History ID: {int(history_id)}',
        f'-- Category: {payload.get("category") or "GENERAL"}',
        f'-- Action: {payload.get("action") or "UPDATE"}',
        f'-- Title: {str(payload.get("title") or "").replace(chr(10), " ")}',
        f'-- Project: {row_root}',
        f'-- History Created: {payload.get("created_at") or ""}',
        f'-- Scratch Created: {datetime.now().isoformat(timespec="seconds")}',
        '-- 이 파일은 자동 실행되지 않습니다. SQL 실행 전 반드시 내용을 검토하세요.',
        '',
        '-- [수정 이력 원본 조회]',
        'SELECT',
        '    project_setting_histories_id,',
        '    project_root,',
        '    category,',
        '    action,',
        '    title,',
        '    summary,',
        '    before_json,',
        '    after_json,',
        '    created_at',
        'FROM project_setting_histories',
        f'WHERE project_setting_histories_id = {int(history_id)};',
        '',
        '-- [변경 전 JSON]',
    ]
    for line in json.dumps(before, ensure_ascii=False, indent=2, default=str).splitlines():
        lines.append('-- ' + line)
    lines.extend(['', '-- [변경 후 JSON]'])
    for line in json.dumps(after, ensure_ascii=False, indent=2, default=str).splitlines():
        lines.append('-- ' + line)
    if deduped:
        lines.extend(['', '-- [History payload에서 감지한 관련 SQL / DDL]'])
        for index, (source, sql) in enumerate(deduped, start=1):
            lines.extend(['', f'-- #{index} source: {source}', sql.rstrip(';') + ';'])
    else:
        lines.extend(['', '-- 이 이력 payload에는 직접 실행 가능한 SQL/DDL 문자열이 없습니다.', '-- 위 SELECT와 변경 전/후 JSON으로 설정 변경 내용을 확인할 수 있습니다.'])

    content = '\n'.join(lines).rstrip() + '\n'
    path.write_text(content, encoding='utf-8', newline='\n')
    return {
        'ok': True,
        'history_id': int(history_id),
        'relative_path': path.relative_to(root).as_posix(),
        'content': content,
        'sql_fragment_count': len(deduped),
        'message': '수정 이력 관련 SQL을 임시 파일로 생성했습니다.',
    }


_DESIGN_SNAPSHOT_GROUPS = {
    'confirmed_requirements': 'REQUIREMENTS',
    'workflow_preview': 'WORKFLOW',
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
