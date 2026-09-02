from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.media_workflow_core import (
    is_media_port_connection_allowed,
    media_node_catalog,
    media_workflow_contract_bundle,
    normalize_workflow_media_extension,
    validate_media_workflow_definition,
)


router = APIRouter(prefix="/media/workflow", tags=["media-workflow"])


class MediaPortValidationRequest(BaseModel):
    output_type: str = Field(min_length=1)
    input_type: str = Field(min_length=1)


class MediaWorkflowValidationRequest(BaseModel):
    workflow: dict[str, Any]


@router.get("/catalog")
async def media_workflow_catalog(phase: str | None = None):
    return {"ok": True, "phase": phase or "all", "nodes": media_node_catalog(max_phase=phase)}


@router.get("/contracts")
async def media_workflow_contracts():
    return {"ok": True, **media_workflow_contract_bundle()}


@router.post("/validate-port")
async def validate_media_port(payload: MediaPortValidationRequest):
    return {
        "ok": True,
        "compatible": is_media_port_connection_allowed(payload.output_type, payload.input_type),
        "output_type": payload.output_type.upper(),
        "input_type": payload.input_type.upper(),
    }


@router.post("/normalize")
async def normalize_media_workflow(payload: MediaWorkflowValidationRequest):
    return {"ok": True, "workflow": normalize_workflow_media_extension(payload.workflow)}


@router.post("/validate")
async def validate_media_workflow(payload: MediaWorkflowValidationRequest):
    return {"ok": True, **validate_media_workflow_definition(payload.workflow)}
