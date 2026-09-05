from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4
import re

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError

from app.core.database import SessionLocal
from app.core.machine_identity import current_pc_name
from app.models.rag_entities import RagCollection, RagCollectionSource, RagDocument, RagSource, RagStudioSetting
from app.rag.constants import SENSITIVE_FILE_NAMES, SENSITIVE_PARTS, SOURCE_CODE_EXTENSIONS
from app.services.connection_test_service import test_pgvector, test_postgresql



def _root(value: str | None) -> str:
    return str(value or '').strip()


def _serialize_setting(row: RagStudioSetting) -> dict[str, Any]:
    return {
        'id': row.id,
        'pc_name': row.pc_name,
        'project_root': row.project_root,
        'rag_enabled': row.rag_enabled,
        'db_provider': row.db_provider,
        'connection_mode': row.connection_mode,
        'db_schema': row.db_schema,
        'scope': row.scope,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_collection(row: RagCollection) -> dict[str, Any]:
    return {
        'id': row.id,
        'pc_name': row.pc_name,
        'project_root': row.project_root,
        'agent_design_project_id': row.agent_design_project_id,
        'name': row.name,
        'description': row.description,
        'scope': row.scope,
        'security_level': row.security_level,
        'is_active': row.is_active,
        'is_deleted': row.is_deleted,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


def _serialize_source(row: RagSource, collection_ids: list[int] | None = None) -> dict[str, Any]:
    return {
        'id': row.id,
        'pc_name': row.pc_name,
        'project_root': row.project_root,
        'source_type': row.source_type,
        'source_uri': row.source_uri,
        'display_name': row.display_name,
        'status': row.status,
        'suitability': row.suitability,
        'risk_level': row.risk_level,
        'recommendation_reason': row.recommendation_reason,
        'recommended_chunking': row.recommended_chunking,
        'analysis_engine': row.analysis_engine,
        'analysis_result': row.analysis_result or {},
        'collection_ids': collection_ids or [],
        'reviewed_at': row.reviewed_at.isoformat() if row.reviewed_at else None,
        'approved_at': row.approved_at.isoformat() if row.approved_at else None,
        'is_active': row.is_active,
        'created_at': row.created_at.isoformat() if row.created_at else None,
        'updated_at': row.updated_at.isoformat() if row.updated_at else None,
    }


async def get_or_create_studio_setting(project_root: str = '') -> dict[str, Any]:
    pc_name = current_pc_name()
    root = _root(project_root)
    async with SessionLocal() as session:
        row = (await session.execute(select(RagStudioSetting).where(
            RagStudioSetting.pc_name == pc_name,
            RagStudioSetting.project_root == root,
        ))).scalar_one_or_none()
        if row is None:
            row = RagStudioSetting(pc_name=pc_name, project_root=root)
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return _serialize_setting(row)


async def update_studio_setting(project_root: str, patch: dict[str, Any]) -> dict[str, Any]:
    pc_name = current_pc_name()
    root = _root(project_root)
    allowed = {'rag_enabled', 'db_provider', 'connection_mode', 'db_schema', 'scope'}
    async with SessionLocal() as session:
        row = (await session.execute(select(RagStudioSetting).where(
            RagStudioSetting.pc_name == pc_name,
            RagStudioSetting.project_root == root,
        ))).scalar_one_or_none()
        if row is None:
            row = RagStudioSetting(pc_name=pc_name, project_root=root)
            session.add(row)
        for key, value in patch.items():
            if key in allowed:
                setattr(row, key, value)
        row.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(row)
        return _serialize_setting(row)


async def list_collections(project_root: str = '') -> list[dict[str, Any]]:
    pc_name = current_pc_name()
    root = _root(project_root)
    async with SessionLocal() as session:
        rows = (await session.execute(select(RagCollection).where(
            RagCollection.pc_name == pc_name,
            RagCollection.project_root == root,
            RagCollection.is_deleted.is_(False),
        ).order_by(RagCollection.name.asc()))).scalars().all()
        return [_serialize_collection(row) for row in rows]


async def create_collection(payload: dict[str, Any]) -> dict[str, Any]:
    name = str(payload.get('name') or '').strip()
    if not name:
        raise ValueError('Knowledge Collection 이름을 입력하세요.')
    pc_name = current_pc_name()
    root = _root(payload.get('project_root'))
    async with SessionLocal() as session:
        row = RagCollection(
            pc_name=pc_name,
            project_root=root,
            agent_design_project_id=payload.get('agent_design_project_id') or None,
            name=name,
            description=str(payload.get('description') or ''),
            scope=str(payload.get('scope') or 'AGENT'),
            security_level=str(payload.get('security_level') or 'INTERNAL'),
        )
        session.add(row)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise ValueError(f"같은 프로젝트에 '{name}' Knowledge Collection이 이미 있습니다.") from exc
        await session.refresh(row)
        return _serialize_collection(row)


async def update_collection(collection_id: int, patch: dict[str, Any]) -> dict[str, Any]:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        row = (await session.execute(select(RagCollection).where(
            RagCollection.id == collection_id,
            RagCollection.pc_name == pc_name,
            RagCollection.is_deleted.is_(False),
        ))).scalar_one_or_none()
        if row is None:
            raise LookupError('Knowledge Collection을 찾을 수 없습니다.')
        for key in ('name', 'description', 'scope', 'security_level', 'is_active'):
            if key in patch:
                setattr(row, key, patch[key])
        row.updated_at = datetime.utcnow()
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise ValueError('같은 이름의 Knowledge Collection이 이미 있습니다.') from exc
        await session.refresh(row)
        return _serialize_collection(row)


async def delete_collection(collection_id: int) -> dict[str, Any]:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        row = (await session.execute(select(RagCollection).where(
            RagCollection.id == collection_id,
            RagCollection.pc_name == pc_name,
            RagCollection.is_deleted.is_(False),
        ))).scalar_one_or_none()
        if row is None:
            raise LookupError('Knowledge Collection을 찾을 수 없습니다.')
        row.is_deleted = True
        row.is_active = False
        row.updated_at = datetime.utcnow()
        await session.execute(delete(RagCollectionSource).where(RagCollectionSource.collection_id == collection_id))
        await session.commit()
        return {'ok': True, 'id': collection_id, 'project_root': row.project_root, 'name': row.name}


def _materialize_pasted_source_code(project_root: str, source_text: str, display_name: str) -> tuple[str, str]:
    root_text = str(project_root or '').strip()
    if not root_text:
        raise ValueError('Source Code 붙여넣기 등록은 Agent 프로젝트 경로가 필요합니다.')
    root = Path(root_text).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f'Agent 프로젝트 경로가 존재하지 않습니다: {root}')
    requested = str(display_name or '').strip() or 'pasted_source.txt'
    safe_name = re.sub(r'[^0-9A-Za-z._-]+', '_', Path(requested).name).strip('._') or 'pasted_source.txt'
    if not Path(safe_name).suffix:
        safe_name += '.txt'
    target_dir = root / '.agentstudio' / 'rag_sources' / 'pasted'
    target_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    target = target_dir / f'{stamp}_{uuid4().hex[:8]}_{safe_name}'
    target.write_text(str(source_text or ''), encoding='utf-8')
    relative = str(target.relative_to(root))
    return relative, requested


def _resolve_local_path(project_root: str, source_uri: str) -> tuple[Path | None, str]:
    raw = str(source_uri or '').strip()
    if not raw:
        return None, 'Source 경로를 입력하세요.'
    path = Path(raw).expanduser()
    explicit_absolute = path.is_absolute()
    if not explicit_absolute and project_root:
        path = Path(project_root) / path
    try:
        resolved = path.resolve()
    except Exception:
        resolved = path
    # Relative paths are project-scoped and cannot escape with ../. An explicit
    # absolute path is allowed because File/Folder picker selection is a direct
    # local-user action in AgentStudio.
    if project_root and not explicit_absolute:
        try:
            root = Path(project_root).resolve()
            resolved.relative_to(root)
        except Exception:
            return None, '상대 Source 경로는 현재 Agent 프로젝트 밖으로 벗어날 수 없습니다.'
    return resolved, ''


def _chunking_for(path: Path | None, source_type: str) -> str:
    if source_type == 'SOURCE_CODE':
        return 'Code Structure Chunking'
    suffix = (path.suffix.lower() if path else '')
    if suffix in {'.md', '.markdown'}:
        return 'Header-aware Chunking'
    if suffix in {'.pdf'}:
        return 'Header + Recursive Chunking'
    if suffix in {'.csv', '.xlsx', '.xls'}:
        return 'Table Logical Group Chunking'
    if suffix in SOURCE_CODE_EXTENSIONS:
        return 'Code Structure Chunking'
    return 'Recursive Chunking'


def analyze_source_metadata(project_root: str, source_type: str, source_uri: str) -> dict[str, Any]:
    source_type = str(source_type or 'FILE').upper()
    path, path_error = _resolve_local_path(project_root, source_uri)
    if path_error:
        return {
            'suitability': 'NOT_RECOMMENDED', 'risk_level': 'HIGH', 'reason': path_error,
            'recommended_chunking': _chunking_for(path, source_type), 'exists': False,
            'engine': 'baseline_rules_v1', 'warnings': [path_error],
        }

    exists = bool(path and path.exists())
    name_lower = path.name.lower() if path else str(source_uri).lower()
    parts_lower = {part.lower() for part in (path.parts if path else ())}
    warnings: list[str] = []
    suitability = 'SUITABLE'
    risk_level = 'LOW'

    if name_lower in SENSITIVE_FILE_NAMES or name_lower.endswith(('.key', '.pem', '.p12', '.pfx')):
        suitability, risk_level = 'NOT_RECOMMENDED', 'HIGH'
        warnings.append('Secret/인증정보 가능성이 높은 파일입니다. RAG 등록 비추천 대상입니다.')
    if parts_lower & SENSITIVE_PARTS:
        suitability, risk_level = 'PARTIAL_REVIEW', 'MEDIUM'
        warnings.append('빌드/의존성/가상환경 폴더가 포함되어 있어 일부 제외를 권장합니다.')
    if path and path.suffix.lower() == '.log':
        suitability = 'PARTIAL_REVIEW' if suitability != 'NOT_RECOMMENDED' else suitability
        risk_level = 'MEDIUM' if risk_level != 'HIGH' else risk_level
        warnings.append('로그 파일에는 개인정보/Token이 포함될 수 있어 검토가 필요합니다.')
    if not exists:
        suitability, risk_level = 'NOT_RECOMMENDED', 'MEDIUM'
        warnings.append('현재 경로에서 Source를 찾을 수 없습니다.')

    file_count = 0
    size_bytes = 0
    detected_type = 'unknown'
    if exists and path:
        if path.is_file():
            file_count = 1
            try:
                size_bytes = path.stat().st_size
            except Exception:
                size_bytes = 0
            detected_type = path.suffix.lower().lstrip('.') or 'file'
        elif path.is_dir():
            detected_type = 'folder'
            try:
                for index, item in enumerate(path.rglob('*')):
                    if index >= 5000:
                        warnings.append('1차 분석은 최대 5,000개 항목까지만 확인합니다.')
                        break
                    if item.is_file():
                        file_count += 1
                        try:
                            size_bytes += item.stat().st_size
                        except Exception:
                            pass
            except Exception as exc:
                warnings.append(f'폴더 요약 중 일부 항목을 읽지 못했습니다: {exc}')

    if suitability == 'SUITABLE':
        reason = '현재 Source 유형과 경로 기준으로 RAG Knowledge 등록에 적합합니다.'
    elif suitability == 'PARTIAL_REVIEW':
        reason = '등록은 가능하지만 제외 대상 또는 민감정보 가능성을 검토한 뒤 승인하는 것을 권장합니다.'
    else:
        reason = warnings[0] if warnings else 'RAG 등록을 권장하지 않습니다.'

    return {
        'suitability': suitability,
        'risk_level': risk_level,
        'reason': reason,
        'recommended_chunking': _chunking_for(path, source_type),
        'exists': exists,
        'resolved_path': str(path or ''),
        'detected_type': detected_type,
        'file_count': file_count,
        'size_bytes': size_bytes,
        'warnings': warnings,
        'engine': 'baseline_rules_v1',
        'note': '1차 개발은 메타데이터/경로 기반 기본 적합성 분석이며, 본문 Secret/Prompt Injection 검사는 2차 Safety Scan에서 강화됩니다.',
    }


async def list_sources(project_root: str = '') -> list[dict[str, Any]]:
    pc_name = current_pc_name()
    root = _root(project_root)
    async with SessionLocal() as session:
        rows = (await session.execute(select(RagSource).where(
            RagSource.pc_name == pc_name,
            RagSource.project_root == root,
            RagSource.is_deleted.is_(False),
        ).order_by(RagSource.created_at.desc()))).scalars().all()
        source_ids = [row.id for row in rows]
        links: dict[int, list[int]] = {source_id: [] for source_id in source_ids}
        if source_ids:
            pairs = (await session.execute(select(RagCollectionSource).where(
                RagCollectionSource.source_id.in_(source_ids)
            ))).scalars().all()
            for pair in pairs:
                links.setdefault(pair.source_id, []).append(pair.collection_id)
        return [_serialize_source(row, links.get(row.id, [])) for row in rows]


async def create_source(payload: dict[str, Any]) -> dict[str, Any]:
    source_type = str(payload.get('source_type') or 'FILE').strip().upper()
    if source_type not in {'FILE', 'FOLDER', 'SOURCE_CODE'}:
        raise ValueError('File / Folder / Source Code 등록을 지원합니다.')
    project_root = _root(payload.get('project_root'))
    source_uri = str(payload.get('source_uri') or '').strip()
    source_text = str(payload.get('source_text') or '')
    requested_display_name = str(payload.get('display_name') or '').strip()
    if source_type == 'SOURCE_CODE' and source_text.strip():
        source_uri, materialized_name = _materialize_pasted_source_code(project_root, source_text, requested_display_name)
        requested_display_name = requested_display_name or materialized_name
    if not source_uri:
        raise ValueError('Source 경로를 입력하거나 Source Code를 붙여넣으세요.')
    pc_name = current_pc_name()
    display_name = requested_display_name or Path(source_uri).name or source_uri
    collection_ids = [int(v) for v in (payload.get('collection_ids') or []) if str(v).isdigit()]

    async with SessionLocal() as session:
        row = RagSource(
            pc_name=pc_name,
            project_root=project_root,
            source_type=source_type,
            source_uri=source_uri,
            display_name=display_name,
            status='REGISTERED',
        )
        session.add(row)
        await session.flush()
        if collection_ids:
            valid_ids = set((await session.execute(select(RagCollection.id).where(
                RagCollection.id.in_(collection_ids),
                RagCollection.pc_name == pc_name,
                RagCollection.project_root == project_root,
                RagCollection.is_deleted.is_(False),
            ))).scalars().all())
            for collection_id in sorted(valid_ids):
                session.add(RagCollectionSource(collection_id=collection_id, source_id=row.id))
        await session.commit()
        await session.refresh(row)
        return _serialize_source(row, collection_ids)


async def analyze_source(source_id: int) -> dict[str, Any]:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        row = (await session.execute(select(RagSource).where(
            RagSource.id == source_id,
            RagSource.pc_name == pc_name,
            RagSource.is_deleted.is_(False),
        ))).scalar_one_or_none()
        if row is None:
            raise LookupError('RAG Source를 찾을 수 없습니다.')
        row.status = 'ANALYZING'
        await session.flush()
        analysis = analyze_source_metadata(row.project_root, row.source_type, row.source_uri)
        row.suitability = str(analysis['suitability'])
        row.risk_level = str(analysis['risk_level'])
        row.recommendation_reason = str(analysis['reason'])
        row.recommended_chunking = str(analysis['recommended_chunking'])
        row.analysis_engine = str(analysis['engine'])
        row.analysis_result = analysis
        row.status = 'REVIEW_REQUIRED'
        row.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(row)
        links = (await session.execute(select(RagCollectionSource.collection_id).where(
            RagCollectionSource.source_id == row.id
        ))).scalars().all()
        return _serialize_source(row, list(links))


async def review_source(source_id: int) -> dict[str, Any]:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        row = (await session.execute(select(RagSource).where(
            RagSource.id == source_id,
            RagSource.pc_name == pc_name,
            RagSource.is_deleted.is_(False),
        ))).scalar_one_or_none()
        if row is None:
            raise LookupError('RAG Source를 찾을 수 없습니다.')
        if row.status not in {'REVIEW_REQUIRED', 'REVIEWED', 'APPROVED'}:
            raise ValueError('먼저 Source 분석을 실행하세요.')
        row.status = 'REVIEWED'
        row.reviewed_at = datetime.utcnow()
        row.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(row)
        links = (await session.execute(select(RagCollectionSource.collection_id).where(
            RagCollectionSource.source_id == row.id
        ))).scalars().all()
        return _serialize_source(row, list(links))


async def approve_source(source_id: int) -> dict[str, Any]:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        row = (await session.execute(select(RagSource).where(
            RagSource.id == source_id,
            RagSource.pc_name == pc_name,
            RagSource.is_deleted.is_(False),
        ))).scalar_one_or_none()
        if row is None:
            raise LookupError('RAG Source를 찾을 수 없습니다.')
        if row.status not in {'REVIEWED', 'APPROVED'}:
            raise ValueError('Analyse 후 검토 완료한 Source만 승인할 수 있습니다.')
        row.status = 'APPROVED'
        row.approved_at = datetime.utcnow()
        row.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(row)
        links = (await session.execute(select(RagCollectionSource.collection_id).where(
            RagCollectionSource.source_id == row.id
        ))).scalars().all()
        return _serialize_source(row, list(links))


async def delete_source(source_id: int) -> dict[str, Any]:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        row = (await session.execute(select(RagSource).where(
            RagSource.id == source_id,
            RagSource.pc_name == pc_name,
            RagSource.is_deleted.is_(False),
        ))).scalar_one_or_none()
        if row is None:
            raise LookupError('RAG Source를 찾을 수 없습니다.')
        row.is_deleted = True
        row.is_active = False
        row.updated_at = datetime.utcnow()
        await session.execute(delete(RagCollectionSource).where(RagCollectionSource.source_id == source_id))
        # Keep indexed rows for later operational history/rollback, but immediately
        # exclude them from duplicate detection and future Retrieval.
        await session.execute(update(RagDocument).where(
            RagDocument.source_id == source_id,
            RagDocument.is_deleted.is_(False),
        ).values(is_active=False, is_deleted=True, updated_at=datetime.utcnow()))
        await session.commit()
        return {'ok': True, 'id': source_id, 'project_root': row.project_root, 'display_name': row.display_name}


async def test_rag_database(database_url: str | None = None) -> dict[str, Any]:
    postgres = await test_postgresql(database_url or None)
    pgvector = await test_pgvector(database_url or None) if postgres.get('ok') else {
        'ok': False,
        'message': 'PostgreSQL 연결 실패로 pgvector 확인을 생략했습니다.',
    }
    return {
        'ok': bool(postgres.get('ok') and pgvector.get('ok')),
        'postgresql': postgres,
        'pgvector': pgvector,
        'ready_for_phase2_indexing': bool(postgres.get('ok') and pgvector.get('ok')),
    }
