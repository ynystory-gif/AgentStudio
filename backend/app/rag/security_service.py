from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.machine_identity import current_pc_name
from app.models.rag_entities import (
    RagAccessRule,
    RagCollection,
    RagDocument,
    RagDocumentSecurity,
    RagSearchAuditLog,
)

SECURITY_LEVELS = ("PUBLIC", "INTERNAL", "CONFIDENTIAL", "RESTRICTED")
_SECURITY_RANK = {name: index for index, name in enumerate(SECURITY_LEVELS)}


def normalize_security_level(value: Any, default: str = "INTERNAL") -> str:
    level = str(value or default).strip().upper()
    return level if level in _SECURITY_RANK else default


def normalize_security_context(value: Any) -> dict[str, str]:
    raw = value if isinstance(value, dict) else {}
    return {
        "user_id": str(raw.get("user_id") or "agentstudio-local").strip()[:200],
        "role": str(raw.get("role") or "DEVELOPER").strip().upper()[:100],
        "security_clearance": normalize_security_level(raw.get("security_clearance"), "RESTRICTED"),
    }


def allowed_security_levels(clearance: str) -> list[str]:
    max_rank = _SECURITY_RANK[normalize_security_level(clearance)]
    return [name for name in SECURITY_LEVELS if _SECURITY_RANK[name] <= max_rank]


def _subject_matches(rule: RagAccessRule, context: dict[str, str]) -> bool:
    subject_type = str(rule.subject_type or "ROLE").upper()
    subject_value = str(rule.subject_value or "").strip().upper()
    if subject_type == "ALL":
        return True
    if subject_type == "USER":
        return subject_value == context["user_id"].upper()
    return subject_value == context["role"].upper()


async def resolve_security_scope(
    session,
    *,
    pc_name: str,
    project_root: str,
    security_context: dict[str, Any] | None = None,
    requested_collection_ids: list[int] | None = None,
) -> dict[str, Any]:
    context = normalize_security_context(security_context)
    requested = {int(value) for value in (requested_collection_ids or []) if int(value) > 0}
    rows = (await session.execute(select(RagCollection).where(
        RagCollection.pc_name == pc_name,
        RagCollection.project_root == project_root,
        RagCollection.is_active.is_(True),
        RagCollection.is_deleted.is_(False),
    ).order_by(RagCollection.id.asc()))).scalars().all()
    collection_ids = [int(row.id) for row in rows]
    rules = []
    if collection_ids:
        rules = (await session.execute(select(RagAccessRule).where(
            RagAccessRule.pc_name == pc_name,
            RagAccessRule.project_root == project_root,
            RagAccessRule.collection_id.in_(collection_ids),
            RagAccessRule.is_active.is_(True),
            RagAccessRule.permission == "SEARCH",
        ).order_by(RagAccessRule.id.asc()))).scalars().all()
    by_collection: dict[int, list[RagAccessRule]] = {}
    for rule in rules:
        by_collection.setdefault(int(rule.collection_id), []).append(rule)

    allowed: list[int] = []
    denied: list[int] = []
    reasons: dict[str, str] = {}
    clearance_rank = _SECURITY_RANK[context["security_clearance"]]
    for collection in rows:
        cid = int(collection.id)
        if requested and cid not in requested:
            continue
        level = normalize_security_level(collection.security_level)
        if _SECURITY_RANK[level] > clearance_rank:
            denied.append(cid)
            reasons[str(cid)] = f"Collection 보안등급 {level}이 현재 Clearance {context['security_clearance']}보다 높습니다."
            continue
        collection_rules = by_collection.get(cid, [])
        matching = [rule for rule in collection_rules if _subject_matches(rule, context)]
        if any(str(rule.effect or "ALLOW").upper() == "DENY" for rule in matching):
            denied.append(cid)
            reasons[str(cid)] = "현재 사용자/Role에 명시적 DENY Access Rule이 적용되었습니다."
            continue
        has_allowlist = any(str(rule.effect or "ALLOW").upper() == "ALLOW" for rule in collection_rules)
        if has_allowlist and not any(str(rule.effect or "ALLOW").upper() == "ALLOW" for rule in matching):
            denied.append(cid)
            reasons[str(cid)] = "이 Collection은 Access Rule Allow-list 대상이며 현재 사용자/Role이 허용 목록에 없습니다."
            continue
        allowed.append(cid)
        reasons[str(cid)] = "보안등급 및 Access Rule 검사를 통과했습니다."

    return {
        **context,
        "allowed_collection_ids": allowed,
        "denied_collection_ids": denied,
        "reasons": reasons,
        "allowed_document_security_levels": allowed_security_levels(context["security_clearance"]),
    }


async def list_access_rules(project_root: str) -> list[dict[str, Any]]:
    pc_name = current_pc_name()
    root = str(project_root or "").strip()
    async with SessionLocal() as session:
        rows = (await session.execute(select(RagAccessRule).where(
            RagAccessRule.pc_name == pc_name,
            RagAccessRule.project_root == root,
        ).order_by(RagAccessRule.id.desc()))).scalars().all()
        return [{
            "id": row.id,
            "project_root": row.project_root,
            "collection_id": row.collection_id,
            "subject_type": row.subject_type,
            "subject_value": row.subject_value,
            "effect": row.effect,
            "permission": row.permission,
            "is_active": bool(row.is_active),
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        } for row in rows]


async def create_access_rule(payload: dict[str, Any]) -> dict[str, Any]:
    pc_name = current_pc_name()
    root = str(payload.get("project_root") or "").strip()
    collection_id = int(payload.get("collection_id") or 0)
    if not root or collection_id <= 0:
        raise ValueError("Access Rule에는 프로젝트와 Knowledge Collection이 필요합니다.")
    subject_type = str(payload.get("subject_type") or "ROLE").upper()
    if subject_type not in {"ROLE", "USER", "ALL"}:
        raise ValueError("subject_type은 ROLE / USER / ALL 중 하나여야 합니다.")
    subject_value = str(payload.get("subject_value") or "").strip()
    if subject_type != "ALL" and not subject_value:
        raise ValueError("Role 또는 User 식별자를 입력하세요.")
    effect = str(payload.get("effect") or "ALLOW").upper()
    if effect not in {"ALLOW", "DENY"}:
        raise ValueError("effect는 ALLOW / DENY 중 하나여야 합니다.")
    async with SessionLocal() as session:
        collection = await session.get(RagCollection, collection_id)
        if collection is None or collection.pc_name != pc_name or collection.project_root != root or collection.is_deleted:
            raise LookupError("현재 프로젝트의 Knowledge Collection을 찾을 수 없습니다.")
        row = RagAccessRule(
            pc_name=pc_name,
            project_root=root,
            collection_id=collection_id,
            subject_type=subject_type,
            subject_value=subject_value or "*",
            effect=effect,
            permission="SEARCH",
            is_active=True,
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return (await list_access_rules(root))[0]


async def delete_access_rule(rule_id: int) -> dict[str, Any]:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        row = await session.get(RagAccessRule, int(rule_id))
        if row is None or row.pc_name != pc_name:
            raise LookupError("Access Rule을 찾을 수 없습니다.")
        project_root = row.project_root
        await session.delete(row)
        await session.commit()
        return {"ok": True, "project_root": project_root, "id": int(rule_id)}


async def set_document_security(document_id: int, security_level: str, note: str = "") -> dict[str, Any]:
    pc_name = current_pc_name()
    level = normalize_security_level(security_level)
    async with SessionLocal() as session:
        document = await session.get(RagDocument, int(document_id))
        if document is None or document.pc_name != pc_name:
            raise LookupError("RAG Document를 찾을 수 없습니다.")
        row = (await session.execute(select(RagDocumentSecurity).where(
            RagDocumentSecurity.document_id == document.id,
        ))).scalar_one_or_none()
        if row is None:
            row = RagDocumentSecurity(document_id=document.id)
            session.add(row)
        row.security_level = level
        row.note = str(note or "")[:4000]
        row.updated_at = datetime.utcnow()
        await session.commit()
        await session.refresh(row)
        return {
            "id": row.id,
            "project_root": document.project_root,
            "document_id": row.document_id,
            "security_level": row.security_level,
            "note": row.note,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }


async def write_search_audit(
    *,
    project_root: str,
    query: str,
    security_scope: dict[str, Any],
    allowed_source_count: int,
    result_count: int,
    search_log_id: int | None = None,
    decision: str = "ALLOW",
    reason: str = "",
) -> int:
    pc_name = current_pc_name()
    async with SessionLocal() as session:
        row = RagSearchAuditLog(
            pc_name=pc_name,
            project_root=str(project_root or "").strip(),
            search_log_id=search_log_id,
            user_id=str(security_scope.get("user_id") or ""),
            role=str(security_scope.get("role") or "DEVELOPER"),
            security_clearance=normalize_security_level(security_scope.get("security_clearance")),
            query_text=str(query or ""),
            decision=str(decision or "ALLOW").upper(),
            allowed_collection_ids=list(security_scope.get("allowed_collection_ids") or []),
            denied_collection_ids=list(security_scope.get("denied_collection_ids") or []),
            allowed_source_count=max(0, int(allowed_source_count or 0)),
            result_count=max(0, int(result_count or 0)),
            reason=str(reason or ""),
        )
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return int(row.id)


async def list_search_audits(project_root: str, limit: int = 100) -> list[dict[str, Any]]:
    pc_name = current_pc_name()
    root = str(project_root or "").strip()
    async with SessionLocal() as session:
        rows = (await session.execute(select(RagSearchAuditLog).where(
            RagSearchAuditLog.pc_name == pc_name,
            RagSearchAuditLog.project_root == root,
        ).order_by(RagSearchAuditLog.id.desc()).limit(max(1, min(int(limit), 500))))).scalars().all()
        return [{
            "id": row.id,
            "search_log_id": row.search_log_id,
            "user_id": row.user_id,
            "role": row.role,
            "security_clearance": row.security_clearance,
            "query_text": row.query_text,
            "decision": row.decision,
            "allowed_collection_ids": row.allowed_collection_ids or [],
            "denied_collection_ids": row.denied_collection_ids or [],
            "allowed_source_count": row.allowed_source_count,
            "result_count": row.result_count,
            "reason": row.reason,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        } for row in rows]
