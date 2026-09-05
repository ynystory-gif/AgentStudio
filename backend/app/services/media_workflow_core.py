from __future__ import annotations

from copy import deepcopy
from enum import StrEnum
from typing import Any


class MediaPortType(StrEnum):
    TEXT = "TEXT"
    PROMPT = "PROMPT"
    IMAGE = "IMAGE"
    IMAGE_LIST = "IMAGE_LIST"
    VIDEO = "VIDEO"
    AUDIO = "AUDIO"
    MASK = "MASK"
    JSON = "JSON"
    MODEL = "MODEL"
    BOOLEAN = "BOOLEAN"
    NUMBER = "NUMBER"


class MediaNodeCategory(StrEnum):
    INPUT = "MEDIA_INPUT"
    ANALYSIS = "MEDIA_ANALYSIS"
    PLANNING = "MEDIA_PLANNING"
    PROCESSING = "MEDIA_PROCESSING"
    GENERATION = "MEDIA_GENERATION"
    VALIDATION = "MEDIA_VALIDATION"
    CONTROL = "MEDIA_CONTROL"
    PREVIEW = "MEDIA_PREVIEW"
    OUTPUT = "MEDIA_OUTPUT"


class MediaJobStatus(StrEnum):
    PENDING = "PENDING"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    VALIDATING = "VALIDATING"
    RETRYING = "RETRYING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


MEDIA_PROVIDER_ADAPTER_METHODS = ("health_check", "capabilities", "submit", "get_status", "get_result", "cancel")


def _port(name: str, port_type: MediaPortType, *, required: bool = True, many: bool = False) -> dict[str, Any]:
    return {"name": name, "type": port_type.value, "required": required, "many": many}


def _node(node_type: str, label: str, category: MediaNodeCategory, inputs: list[dict[str, Any]], outputs: list[dict[str, Any]], *, phase: str, execution_mode: str = "SYNC", provider_capability: str = "", description: str = "") -> dict[str, Any]:
    return {"type": node_type, "label": label, "category": category.value, "inputs": inputs, "outputs": outputs, "phase": phase, "execution_mode": execution_mode, "provider_capability": provider_capability, "description": description}


MEDIA_NODE_DEFINITIONS: tuple[dict[str, Any], ...] = (
    _node("IMAGE_INPUT", "Image Input", MediaNodeCategory.INPUT, [], [_port("image", MediaPortType.IMAGE)], phase="1A"),
    _node("MULTIPLE_IMAGE_INPUT", "Multiple Image Input", MediaNodeCategory.INPUT, [], [_port("images", MediaPortType.IMAGE_LIST)], phase="2"),
    _node("VIDEO_INPUT", "Video Input", MediaNodeCategory.INPUT, [], [_port("video", MediaPortType.VIDEO)], phase="3"),
    _node("AUDIO_INPUT", "Audio Input", MediaNodeCategory.INPUT, [], [_port("audio", MediaPortType.AUDIO)], phase="3"),
    _node("IMAGE_ANALYZER", "Image Analyzer", MediaNodeCategory.ANALYSIS, [_port("image", MediaPortType.IMAGE)], [_port("analysis", MediaPortType.JSON)], phase="1B", provider_capability="vision_analysis"),
    _node("VIDEO_ANALYZER", "Video Analyzer", MediaNodeCategory.ANALYSIS, [_port("video", MediaPortType.VIDEO)], [_port("analysis", MediaPortType.JSON)], phase="3", provider_capability="video_analysis"),
    _node("PROMPT_GENERATOR", "Prompt Generator", MediaNodeCategory.PLANNING, [_port("request", MediaPortType.TEXT), _port("analysis", MediaPortType.JSON, required=False)], [_port("prompt", MediaPortType.PROMPT), _port("plan", MediaPortType.JSON)], phase="1B"),
    _node("STYLE_PLANNER", "Style Planner", MediaNodeCategory.PLANNING, [_port("request", MediaPortType.TEXT), _port("reference", MediaPortType.IMAGE, required=False)], [_port("style", MediaPortType.JSON)], phase="2"),
    _node("LAYOUT_PLANNER", "Layout Planner", MediaNodeCategory.PLANNING, [_port("request", MediaPortType.TEXT), _port("assets", MediaPortType.JSON, required=False)], [_port("layout", MediaPortType.JSON)], phase="2"),
    _node("SCENE_PLANNER", "Scene Planner", MediaNodeCategory.PLANNING, [_port("request", MediaPortType.TEXT)], [_port("scene_plan", MediaPortType.JSON)], phase="3"),
    _node("BACKGROUND_REMOVE", "Background Remove", MediaNodeCategory.PROCESSING, [_port("image", MediaPortType.IMAGE)], [_port("image", MediaPortType.IMAGE), _port("mask", MediaPortType.MASK, required=False)], phase="1B", execution_mode="ASYNC", provider_capability="background_remove"),
    _node("RESIZE", "Resize", MediaNodeCategory.PROCESSING, [_port("image", MediaPortType.IMAGE), _port("width", MediaPortType.NUMBER), _port("height", MediaPortType.NUMBER)], [_port("image", MediaPortType.IMAGE)], phase="1B"),
    _node("CROP", "Crop", MediaNodeCategory.PROCESSING, [_port("image", MediaPortType.IMAGE), _port("config", MediaPortType.JSON)], [_port("image", MediaPortType.IMAGE)], phase="1B"),
    _node("TEXT_OVERLAY", "Text Overlay", MediaNodeCategory.PROCESSING, [_port("image", MediaPortType.IMAGE), _port("text", MediaPortType.TEXT), _port("layout", MediaPortType.JSON, required=False)], [_port("image", MediaPortType.IMAGE)], phase="1B"),
    _node("INPAINT", "Inpaint", MediaNodeCategory.PROCESSING, [_port("image", MediaPortType.IMAGE), _port("mask", MediaPortType.MASK), _port("prompt", MediaPortType.PROMPT)], [_port("image", MediaPortType.IMAGE)], phase="2", execution_mode="ASYNC", provider_capability="inpaint"),
    _node("OBJECT_REMOVE", "Object Remove", MediaNodeCategory.PROCESSING, [_port("image", MediaPortType.IMAGE), _port("mask", MediaPortType.MASK)], [_port("image", MediaPortType.IMAGE)], phase="2", execution_mode="ASYNC", provider_capability="inpaint"),
    _node("IMAGE_GENERATE", "Image Generate", MediaNodeCategory.GENERATION, [_port("prompt", MediaPortType.PROMPT), _port("reference_image", MediaPortType.IMAGE, required=False), _port("config", MediaPortType.JSON, required=False)], [_port("image", MediaPortType.IMAGE), _port("metadata", MediaPortType.JSON)], phase="1A", execution_mode="ASYNC", provider_capability="text_to_image"),
    _node("IMAGE_TO_IMAGE", "Image-to-Image", MediaNodeCategory.GENERATION, [_port("image", MediaPortType.IMAGE), _port("prompt", MediaPortType.PROMPT), _port("config", MediaPortType.JSON, required=False)], [_port("image", MediaPortType.IMAGE)], phase="1B", execution_mode="ASYNC", provider_capability="image_to_image"),
    _node("TEXT_TO_VIDEO", "Text-to-Video", MediaNodeCategory.GENERATION, [_port("prompt", MediaPortType.PROMPT), _port("config", MediaPortType.JSON, required=False)], [_port("video", MediaPortType.VIDEO), _port("metadata", MediaPortType.JSON)], phase="3", execution_mode="ASYNC", provider_capability="text_to_video"),
    _node("IMAGE_TO_VIDEO", "Image-to-Video", MediaNodeCategory.GENERATION, [_port("image", MediaPortType.IMAGE), _port("prompt", MediaPortType.PROMPT, required=False), _port("config", MediaPortType.JSON, required=False)], [_port("video", MediaPortType.VIDEO), _port("metadata", MediaPortType.JSON)], phase="3", execution_mode="ASYNC", provider_capability="image_to_video"),
    _node("OCR_VALIDATOR", "OCR Validator", MediaNodeCategory.VALIDATION, [_port("image", MediaPortType.IMAGE), _port("expected_text", MediaPortType.TEXT, required=False)], [_port("validation", MediaPortType.JSON), _port("valid", MediaPortType.BOOLEAN)], phase="1B"),
    _node("IMAGE_QUALITY_VALIDATOR", "Image Quality Validator", MediaNodeCategory.VALIDATION, [_port("image", MediaPortType.IMAGE), _port("criteria", MediaPortType.JSON, required=False)], [_port("validation", MediaPortType.JSON), _port("valid", MediaPortType.BOOLEAN)], phase="1B"),
    _node("PRODUCT_VALIDATOR", "Product Validator", MediaNodeCategory.VALIDATION, [_port("source_image", MediaPortType.IMAGE), _port("generated_image", MediaPortType.IMAGE)], [_port("validation", MediaPortType.JSON), _port("valid", MediaPortType.BOOLEAN)], phase="2"),
    _node("BRAND_VALIDATOR", "Brand Validator", MediaNodeCategory.VALIDATION, [_port("image", MediaPortType.IMAGE), _port("brand_rules", MediaPortType.JSON)], [_port("validation", MediaPortType.JSON), _port("valid", MediaPortType.BOOLEAN)], phase="2"),
    _node("VIDEO_QUALITY_VALIDATOR", "Video Quality Validator", MediaNodeCategory.VALIDATION, [_port("video", MediaPortType.VIDEO), _port("criteria", MediaPortType.JSON, required=False)], [_port("validation", MediaPortType.JSON), _port("valid", MediaPortType.BOOLEAN)], phase="3"),
    _node("CONDITION", "Condition", MediaNodeCategory.CONTROL, [_port("condition", MediaPortType.BOOLEAN)], [_port("result", MediaPortType.BOOLEAN)], phase="1B"),
    _node("RETRY", "Retry", MediaNodeCategory.CONTROL, [_port("validation", MediaPortType.JSON)], [_port("retry_plan", MediaPortType.JSON)], phase="1B"),
    _node("HUMAN_APPROVAL", "Human Approval", MediaNodeCategory.CONTROL, [_port("artifact", MediaPortType.JSON)], [_port("approved", MediaPortType.BOOLEAN), _port("feedback", MediaPortType.TEXT, required=False)], phase="1B", execution_mode="INTERRUPT"),
    _node("IMAGE_PREVIEW", "Image Preview", MediaNodeCategory.PREVIEW, [_port("image", MediaPortType.IMAGE)], [_port("artifact", MediaPortType.JSON)], phase="1A"),
    _node("VIDEO_PREVIEW", "Video Preview", MediaNodeCategory.PREVIEW, [_port("video", MediaPortType.VIDEO)], [_port("artifact", MediaPortType.JSON)], phase="3"),
    _node("BEFORE_AFTER_COMPARE", "Before / After Compare", MediaNodeCategory.PREVIEW, [_port("before", MediaPortType.IMAGE), _port("after", MediaPortType.IMAGE)], [_port("comparison", MediaPortType.JSON)], phase="2"),
    _node("SAVE_IMAGE", "Save Image", MediaNodeCategory.OUTPUT, [_port("image", MediaPortType.IMAGE), _port("config", MediaPortType.JSON, required=False)], [_port("artifact", MediaPortType.JSON)], phase="1A"),
    _node("SAVE_VIDEO", "Save Video", MediaNodeCategory.OUTPUT, [_port("video", MediaPortType.VIDEO), _port("config", MediaPortType.JSON, required=False)], [_port("artifact", MediaPortType.JSON)], phase="3"),
)

MEDIA_NODE_BY_TYPE = {row["type"]: row for row in MEDIA_NODE_DEFINITIONS}
_PORT_COMPATIBILITY: dict[str, set[str]] = {
    MediaPortType.TEXT.value: {MediaPortType.TEXT.value}, MediaPortType.PROMPT.value: {MediaPortType.PROMPT.value, MediaPortType.TEXT.value},
    MediaPortType.IMAGE.value: {MediaPortType.IMAGE.value}, MediaPortType.IMAGE_LIST.value: {MediaPortType.IMAGE_LIST.value, MediaPortType.IMAGE.value},
    MediaPortType.VIDEO.value: {MediaPortType.VIDEO.value}, MediaPortType.AUDIO.value: {MediaPortType.AUDIO.value}, MediaPortType.MASK.value: {MediaPortType.MASK.value},
    MediaPortType.JSON.value: {MediaPortType.JSON.value}, MediaPortType.MODEL.value: {MediaPortType.MODEL.value}, MediaPortType.BOOLEAN.value: {MediaPortType.BOOLEAN.value}, MediaPortType.NUMBER.value: {MediaPortType.NUMBER.value},
}


def media_node_catalog(*, max_phase: str | None = None) -> list[dict[str, Any]]:
    rows = [deepcopy(row) for row in MEDIA_NODE_DEFINITIONS]
    if max_phase is None:
        return rows
    order = {"1A": 1, "1B": 2, "2": 3, "3": 4}
    limit = order.get(str(max_phase).upper(), 4)
    return [row for row in rows if order.get(str(row.get("phase") or "3").upper(), 4) <= limit]


def is_media_port_connection_allowed(output_type: str, input_type: str) -> bool:
    source, target = str(output_type or "").upper(), str(input_type or "").upper()
    return source in _PORT_COMPATIBILITY.get(target, set())


def media_artifact_contract() -> dict[str, Any]:
    return {"required": ["artifact_id", "type", "uri", "created_at"], "fields": {"artifact_id": "string", "type": "IMAGE|VIDEO|AUDIO|MASK|JSON", "uri": "project/runtime output URI or path", "mime_type": "string", "width": "integer?", "height": "integer?", "duration": "number?", "fps": "number?", "source_node_id": "string?", "provider": "string?", "model": "string?", "generation_info": "object", "metadata": "object", "created_at": "ISO-8601 string"}, "security": ["Provider API Key/Token/Password는 Artifact metadata에 저장하지 않는다.", "외부 Provider 원본 응답은 Secret/PII를 제거한 뒤 필요한 metadata만 보존한다."]}


def media_job_contract() -> dict[str, Any]:
    return {"statuses": [status.value for status in MediaJobStatus], "required": ["job_id", "node_id", "provider", "status"], "fields": {"job_id": "string", "node_id": "string", "provider": "string", "provider_job_id": "string?", "status": "MediaJobStatus", "progress": "0..1?", "retry_count": "integer", "max_retry": "integer", "technical_retry_count": "integer", "quality_retry_count": "integer", "submitted_at": "ISO-8601 string?", "updated_at": "ISO-8601 string?", "result_artifact_ids": "string[]", "error": "safe structured error?"}}


def media_provider_adapter_contract() -> dict[str, Any]:
    return {"methods": list(MEDIA_PROVIDER_ADAPTER_METHODS), "capability_fields": ["text_to_image", "image_to_image", "inpaint", "background_remove", "text_to_video", "image_to_video", "progress", "cancel"], "routing_order": ["required capability support", "provider health/readiness", "required workflow/model availability", "user/provider policy", "GPU/queue readiness when local", "cost/latency policy when configured"], "providers": ["AUTO", "COMFYUI", "DIFFUSERS", "OPENAI_IMAGE", "EXTERNAL_API", "CUSTOM_API"]}


def normalize_workflow_media_extension(workflow: dict[str, Any] | None) -> dict[str, Any]:
    """Add media metadata without replacing the existing AgentStudio workflow schema."""
    result = deepcopy(workflow or {})
    result.setdefault("nodes", []); result.setdefault("edges", []); result.setdefault("variables", {})
    media = result.setdefault("extensions", {}).setdefault("media", {})
    media.setdefault("schema_version", 1); media.setdefault("providers", {}); media.setdefault("assets", {}); media.setdefault("jobs", {})
    return result


def validate_media_workflow_definition(workflow: dict[str, Any] | None) -> dict[str, Any]:
    value = normalize_workflow_media_extension(workflow)
    nodes, edges = value.get("nodes") or [], value.get("edges") or []
    node_map = {str(row.get("id") or ""): row for row in nodes if isinstance(row, dict) and str(row.get("id") or "")}
    issues: list[dict[str, Any]] = []
    for edge in edges:
        if not isinstance(edge, dict): continue
        source_id, target_id = str(edge.get("source") or edge.get("from") or ""), str(edge.get("target") or edge.get("to") or "")
        source, target = node_map.get(source_id) or {}, node_map.get(target_id) or {}
        if str(source.get("type") or "").upper() not in MEDIA_NODE_BY_TYPE or str(target.get("type") or "").upper() not in MEDIA_NODE_BY_TYPE: continue
        output_type, input_type = str(edge.get("output_type") or "").upper(), str(edge.get("input_type") or "").upper()
        if output_type and input_type and not is_media_port_connection_allowed(output_type, input_type):
            issues.append({"code": "MEDIA_PORT_TYPE_MISMATCH", "source": source_id, "target": target_id, "output_type": output_type, "input_type": input_type})
    return {"valid": not issues, "issues": issues, "workflow": value, "known_media_node_count": sum(1 for row in nodes if isinstance(row, dict) and str(row.get("type") or "").upper() in MEDIA_NODE_BY_TYPE)}


def media_workflow_contract_bundle() -> dict[str, Any]:
    return {"schema_strategy": "additive_extension_backward_compatible", "port_types": [item.value for item in MediaPortType], "node_categories": [item.value for item in MediaNodeCategory], "nodes": media_node_catalog(), "artifact": media_artifact_contract(), "job": media_job_contract(), "provider_adapter": media_provider_adapter_contract()}
