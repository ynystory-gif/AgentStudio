from __future__ import annotations

import json
from typing import Any

from app.services.media_workflow_core import media_workflow_contract_bundle


MEDIA_AGENT_MARKERS = (
    "media agent", "media creation", "미디어 agent", "미디어 에이전트", "이미지 생성 agent", "이미지 생성 에이전트",
    "영상 생성 agent", "영상 생성 에이전트", "포스터 생성", "광고 이미지", "상품 이미지", "쇼츠", "릴스",
    "comfyui", "diffusers", "text-to-image", "image-to-image", "text-to-video", "image-to-video", "MEDIA_CREATION",
)


def is_media_agent_request(text: str | None) -> bool:
    value = str(text or "").casefold()
    return any(marker.casefold() in value for marker in MEDIA_AGENT_MARKERS)


def is_media_agent_design(design: dict[str, Any] | None, request: str | None = None) -> bool:
    value = design or {}
    if is_media_agent_request(request):
        return True
    plan = value.get("media_agent_plan") or {}
    if isinstance(plan, dict) and str(plan.get("type") or "").upper() == "MEDIA_CREATION":
        return True
    runtime = value.get("design_runtime") or {}
    if isinstance(runtime, dict) and str(runtime.get("agent_specialization") or "").upper() == "MEDIA_CREATION":
        return True
    confirmed = value.get("confirmed_requirements") or {}
    specialization = confirmed.get("agent_specialization") if isinstance(confirmed, dict) else None
    return isinstance(specialization, dict) and str(specialization.get("type") or "").upper() == "MEDIA_CREATION"


def _append_unique_text(target: list, *values: str) -> None:
    existing = {str(item).casefold() for item in target if isinstance(item, str)}
    for value in values:
        if value and value.casefold() not in existing:
            target.append(value); existing.add(value.casefold())


def _append_unique_dict(target: list, item: dict, key: str = "name") -> None:
    wanted = str(item.get(key) or "").strip().casefold()
    if not wanted:
        target.append(item); return
    for current in target:
        if isinstance(current, dict) and str(current.get(key) or "").strip().casefold() == wanted:
            current.update(item); return
    target.append(item)


def _ensure_workflow_step(workflow: dict, name: str, label: str, description: str, step_type: str) -> None:
    steps = workflow.setdefault("steps", [])
    for row in steps:
        if isinstance(row, dict) and str(row.get("name") or "") == name:
            row.update({"label": label, "description": description, "type": step_type}); return
    steps.append({"name": name, "label": label, "description": description, "type": step_type})


def _ensure_branch(workflow: dict, source: str, condition: str, yes: str, no: str) -> None:
    rows = workflow.setdefault("branches", [])
    for row in rows:
        if isinstance(row, dict) and (str(row.get("from") or ""), str(row.get("condition") or "")) == (source, condition):
            row.update({"yes": yes, "no": no}); return
    rows.append({"from": source, "condition": condition, "yes": yes, "no": no})


def _ensure_policy(rows: list, target: str, payload: dict) -> None:
    for row in rows:
        if isinstance(row, dict) and str(row.get("target") or "") == target:
            row.update(payload); return
    rows.append({"target": target, **payload})


def _ensure_file(file_plan: dict, path: str, purpose: str, component: str) -> None:
    rows = file_plan.setdefault("new_files", [])
    for row in rows:
        if isinstance(row, dict) and str(row.get("path") or "") == path:
            row.update({"purpose": purpose, "required": True, "component": component}); break
    else:
        rows.append({"path": path, "purpose": purpose, "required": True, "component": component})
    maps = file_plan.setdefault("component_file_map", [])
    for row in maps:
        if isinstance(row, dict) and str(row.get("component") or "") == component:
            files = row.setdefault("files", [])
            if path not in files: files.append(path)
            row["status"] = "planned"; break
    else:
        maps.append({"component": component, "files": [path], "status": "planned"})


def _ensure_setting_category(settings_plan: dict, category: dict) -> None:
    categories = settings_plan.setdefault("categories", [])
    for row in categories:
        if isinstance(row, dict) and str(row.get("id") or "") == str(category.get("id") or ""):
            existing = {str(field.get("key") or ""): field for field in row.setdefault("fields", []) if isinstance(field, dict)}
            for field in category.get("fields") or []:
                key = str(field.get("key") or "")
                if key in existing: existing[key].update(field)
                else: row["fields"].append(field)
            row.update({key: value for key, value in category.items() if key != "fields"}); return
    categories.append(category)


def enforce_media_agent_design(design: dict[str, Any], request: str) -> dict[str, Any]:
    """Inject a high-level Media Agent contract without cloning ComfyUI's low-level graph."""
    if not is_media_agent_design(design, request):
        return design

    spec = design.setdefault("requirement_spec", {})
    spec.setdefault("goal", "고수준 Media Workflow와 Provider Adapter를 사용해 이미지/영상 생성·처리 결과를 검증 가능한 Agent")
    for key in ("users", "inputs", "outputs", "constraints", "acceptance_criteria"): spec.setdefault(key, [])
    _append_unique_text(spec["inputs"], "자연어 미디어 제작/보정 요청", "선택적 이미지·영상·오디오·로고·상품/브랜드 Asset", "출력 크기/비율/품질/브랜드/문구 등 생성 조건")
    _append_unique_text(spec["outputs"], "Media Artifact(image/video/audio/mask/json)와 생성 Metadata", "품질/OCR/브랜드/상품 검증 결과", "Human Approval 상태와 최종 저장 결과")
    _append_unique_text(spec["constraints"], "AgentStudio는 ComfyUI 저수준 Node를 복제하지 않고 고수준 Media Node만 설계한다.", "실제 생성은 Media Provider Adapter 뒤의 ComfyUI/Diffusers/외부 API/Custom API가 담당한다.", "Provider API Key/Password/Token은 Workflow JSON이나 Artifact Metadata에 평문 저장하지 않는다.", "기술 장애 재시도와 품질 미달 보정 재생성을 분리하고 bounded retry를 적용한다.", "정확한 제목·날짜·가격 등 결정적 문자열은 가능하면 Text Overlay 후 OCR Validator로 검증한다.")
    _append_unique_text(spec["acceptance_criteria"], "요구 Capability를 지원하는 Provider를 선택하고 실행 전 Health/Readiness를 확인한다.", "Media Node 연결은 Typed Port 계약으로 검증한다.", "장기 실행은 Job ID/Provider Job ID와 진행 상태를 추적하고 취소/재개 가능한 상태를 남긴다.", "생성 결과는 Validator를 통과하거나 Human Approval을 받은 뒤 최종 저장한다.", "기존 비-Media Workflow 파일은 추가 Media Extension 없이도 그대로 읽을 수 있어야 한다.")

    capabilities = design.setdefault("capability_plan", {})
    for key in ("capabilities", "external_dependencies", "data_needs"): capabilities.setdefault(key, [])
    _append_unique_text(capabilities["capabilities"], "Media Requirement Extraction", "Image/Video Analysis", "Prompt/Style/Layout/Scene Planning", "High-level Media Node Orchestration", "Provider Capability Routing", "ComfyUI Workflow Adapter", "Typed Media Artifact Tracking", "Async Media Job/Progress/Cancel", "Media Quality Validation", "Correction Planner와 bounded Quality Retry", "Human Approval Interrupt/Resume")
    _append_unique_text(capabilities["external_dependencies"], "ComfyUI 또는 선택한 Image/Video Provider", "Provider별 Workflow/Model/Runtime", "FFmpeg 또는 외부 Video Engine(영상 Agent에서만)")
    _append_unique_text(capabilities["data_needs"], "Media Artifact metadata", "Provider capability/readiness", "Media Job status/progress", "Validator score/issues/warnings/correction", "Asset/Template reference metadata")

    tool_plan = design.setdefault("tool_mcp_plan", {}); decisions = tool_plan.setdefault("decisions", [])
    for item in (
        {"capability": "Media Provider Discovery", "execution_type": "internal_function", "reason": "Provider capability/health/workflow readiness를 검증하고 Auto 선택합니다."},
        {"capability": "ComfyUI Media Generation", "execution_type": "api_client", "reason": "ComfyUI는 외부 실행 엔진으로 취급하고 Server API/Workflow JSON/Input/Output Mapping으로 호출합니다."},
        {"capability": "Custom Media Provider", "execution_type": "api_client", "reason": "Provider Adapter 계약으로 외부 Image/Video API를 교체 가능하게 연결합니다."},
        {"capability": "Local Media Processing", "execution_type": "internal_function", "reason": "Resize/Crop/Text Overlay 등 결정적 처리는 고수준 Tool 내부 구현으로 숨깁니다."},
        {"capability": "Media Validation", "execution_type": "internal_function", "reason": "OCR/품질/상품/브랜드 검증을 Provider 성공 응답과 분리합니다."},
    ): _append_unique_dict(decisions, item, "capability")

    architecture = design.setdefault("agent_architecture", {})
    for key in ("components", "state", "interfaces", "persistence", "security"): architecture.setdefault(key, [])
    for item in (
        {"name": "Media Requirement Router", "responsibility": "미디어 제작 목적/입력/출력/품질/브랜드 조건을 구조화"},
        {"name": "Media Workflow Planner", "responsibility": "고수준 Media Node와 Condition/Retry/Approval을 실행 가능한 흐름으로 구성"},
        {"name": "Typed Media Node Runtime", "responsibility": "NodeDefinition/Port Type/Artifact/Job 계약과 Edge type validation"},
        {"name": "Media Provider Router", "responsibility": "Capability/Health/Workflow/Queue/정책을 기준으로 Provider Auto/수동 선택"},
        {"name": "ComfyUI Provider Adapter", "responsibility": "Server 연결, Workflow JSON, Input/Output Mapping, Queue/Progress/Result/Cancel"},
        {"name": "Media Artifact Store", "responsibility": "이미지/영상/마스크/오디오 Artifact의 ID/경로/크기/출처/생성정보 추적"},
        {"name": "Media Validator", "responsibility": "OCR/품질/상품/브랜드/레이아웃 기준과 correction instruction 생성"},
        {"name": "Human Approval Gate", "responsibility": "WAITING_APPROVAL 상태를 저장하고 승인/수정/재생성 후 Workflow Resume"},
    ): _append_unique_dict(architecture["components"], item)
    for item in (
        {"name": "media_artifacts", "description": "artifact_id/type/uri/mime/size/source_node/provider/model/metadata"},
        {"name": "media_jobs", "description": "job_id/provider_job_id/status/progress/retry/result/error"},
        {"name": "provider_capabilities", "description": "text_to_image/image_to_image/inpaint/video/progress/cancel"},
        {"name": "validation_result", "description": "valid/score/issues/warnings/retry_recommended/correction"},
        {"name": "approval_state", "description": "pending/approved/revision_requested/rejected + feedback"},
    ): _append_unique_dict(architecture["state"], item)
    _append_unique_text(architecture["interfaces"], "Media Provider Adapter", "ComfyUI Server API", "Optional Diffusers/OpenAI Image/External/Custom API", "Project Asset/Template Store", "Preview/Approval UI")
    _append_unique_text(architecture["persistence"], "기존 Workflow Schema의 additive extensions.media 영역", "Media Job/Artifact 상태 저장", "Human Approval interrupt/resume checkpoint")
    _append_unique_text(architecture["security"], "Provider Secret은 .env/보안 설정에 저장하고 Workflow JSON에는 참조만 저장", "외부 입력 Asset의 형식/크기/경로를 검증하고 허용 Output Root를 사용", "Provider 응답/로그에서 Secret/PII를 제거", "ComfyUI 저수준 Node 편집을 기본 UI에 노출하지 않음")

    workflow = design.setdefault("target_agent_workflow", {}); workflow["name"] = workflow.get("name") or "Media Creation Agent Workflow"
    for key in ("steps", "branches", "retry_policy", "failure_policy", "requirement_coverage"): workflow.setdefault(key, [])
    for row in (
        ("capture_media_request", "미디어 제작 요청 수집", "목표, 입력 Asset, 출력 형식/비율, 정확 문자열, 품질/브랜드 조건을 수집합니다.", "media_input"),
        ("validate_media_inputs", "Media 입력 검증", "파일 형식·크기·경로·필수 Asset과 보안 조건을 검증합니다.", "validation"),
        ("analyze_media", "이미지/영상 분석", "객체·배경·색상·해상도·비율·텍스트·품질 문제를 구조화합니다.", "media_analysis"),
        ("plan_media", "생성 계획 수립", "Content/Style/Layout/Composition/Scene 계획과 deterministic overlay 항목을 구조화합니다.", "media_plan"),
        ("generate_media_prompt", "Prompt 생성", "Provider에 전달할 Prompt/Negative Prompt와 generation config를 만듭니다.", "media_plan"),
        ("resolve_media_provider", "Media Provider 선택", "Capability, 연결 상태, Workflow/Model, Queue와 사용자 정책으로 Provider를 선택합니다.", "decision"),
        ("check_media_provider", "Provider Readiness 확인", "ComfyUI/API Health, Workflow/Model과 필요한 Capability를 확인합니다.", "validation"),
        ("submit_media_job", "Media 생성 Job 제출", "고수준 Media Node 요청을 Provider Adapter로 변환하고 Job ID를 저장합니다.", "media_generate"),
        ("wait_media_job", "Media Job 진행 추적", "Queue/RUNNING/Progress/Cancel/Timeout 상태를 추적합니다.", "media_generate"),
        ("fetch_media_artifact", "Media Artifact 수집", "Provider 결과를 Typed Artifact로 정규화합니다.", "media_process"),
        ("validate_media_result", "생성 결과 검증", "OCR/이미지 품질/상품/브랜드/레이아웃 Validator를 실행합니다.", "media_validate"),
        ("plan_media_correction", "품질 보정 계획", "검증 실패를 Prompt/Parameter/Tool 보정 지시로 변환합니다.", "media_plan"),
        ("human_media_approval", "Human Approval", "Preview를 사람이 승인·수정 요청·재생성할 수 있게 Workflow를 interrupt합니다.", "approval"),
        ("preview_media_result", "Media Preview", "Image/Video/Before-After 결과와 검증 정보를 표시합니다.", "preview"),
        ("save_media_output", "최종 Media 저장", "승인된 Artifact를 허용 Output 경로와 요청 형식으로 저장합니다.", "storage"),
        ("complete_media_workflow", "Media Workflow 완료", "최종 Artifact/검증/Provider/Retry 정보를 반환합니다.", "complete"),
    ): _ensure_workflow_step(workflow, *row)
    _ensure_branch(workflow, "check_media_provider", "provider_ready == true", "submit_media_job", "provider_unavailable")
    _ensure_branch(workflow, "validate_media_result", "validation.valid == true", "human_media_approval", "plan_media_correction")
    _ensure_branch(workflow, "plan_media_correction", "quality_retry_count < max_quality_retry", "submit_media_job", "human_media_approval")
    _ensure_branch(workflow, "human_media_approval", "approved == true", "preview_media_result", "plan_media_correction")
    _ensure_policy(workflow["retry_policy"], "submit_media_job", {"condition": "timeout/HTTP/provider transient error", "strategy": "technical bounded retry with backoff; 품질 Prompt 보정과 구분"})
    _ensure_policy(workflow["retry_policy"], "validate_media_result", {"condition": "quality/OCR/product/brand criteria not met", "strategy": "validator correction → prompt/parameter patch → bounded quality regeneration"})
    _ensure_policy(workflow["failure_policy"], "provider_unavailable", {"action": "호환 Provider를 선택하고 없으면 현재 상태/필요 설정을 안전하게 반환"})
    _ensure_policy(workflow["failure_policy"], "submit_media_job", {"action": "Job/Provider 상태를 보존하고 재시도 한도 초과 시 실패 원인과 재개 가능한 checkpoint 반환"})

    file_plan = design.setdefault("file_plan", {}); file_plan.setdefault("existing_files_to_modify", [])
    for path, purpose, component in (
        ("app/media/contracts.py", "Typed Media Node/Port/Artifact/Job 계약", "Typed Media Node Runtime"),
        ("app/media/node_registry.py", "고수준 Media Node Registry와 Port compatibility", "Typed Media Node Runtime"),
        ("app/media/runtime.py", "Async Media Job 상태/Progress/Cancel/Retry/Resume", "Typed Media Node Runtime"),
        ("app/media/providers/base.py", "Media Provider Adapter 공통 계약", "Media Provider Router"),
        ("app/media/providers/comfyui.py", "ComfyUI Workflow API Adapter", "ComfyUI Provider Adapter"),
        ("app/media/validators.py", "Media Validator와 correction contract", "Media Validator"),
        ("app/media/artifacts.py", "Media Artifact ID/metadata/storage 수명주기", "Media Artifact Store"),
    ): _ensure_file(file_plan, path, purpose, component)

    settings = design.setdefault("settings_plan", {}); settings.setdefault("enabled", True); settings.setdefault("reason", "Media Provider/ComfyUI Workflow/Retry/Output 경로는 런타임 변경이 필요합니다.")
    _ensure_setting_category(settings, {"id": "media_provider", "label": "미디어 생성", "fields": [
        {"key": "MEDIA_PROVIDER", "label": "Media Provider", "type": "select", "default": "auto", "required": True, "secret": False, "options": ["auto", "comfyui", "diffusers", "openai_image", "external_api", "custom_api"], "storage": "config"},
        {"key": "COMFYUI_BASE_URL", "label": "ComfyUI Server URL", "type": "string", "default": "http://127.0.0.1:8188", "required": False, "secret": False, "storage": "env"},
        {"key": "COMFYUI_WORKFLOW_NAME", "label": "ComfyUI Workflow", "type": "string", "default": "", "required": False, "secret": False, "storage": "config"},
        {"key": "COMFYUI_WORKFLOW_JSON", "label": "ComfyUI Workflow JSON", "type": "path", "default": "", "required": False, "secret": False, "storage": "config"},
        {"key": "MEDIA_MAX_RETRY", "label": "Media Max Retry", "type": "number", "default": 3, "required": True, "secret": False, "storage": "config"},
        {"key": "MEDIA_OUTPUT_ROOT", "label": "Media Output Root", "type": "path", "default": "", "required": True, "secret": False, "storage": "config"},
    ]})

    environment = design.setdefault("environment_plan", {})
    for key in ("env_vars", "dependencies", "services", "startup", "validation_commands"): environment.setdefault(key, [])
    _append_unique_text(environment["env_vars"], "MEDIA_PROVIDER", "COMFYUI_BASE_URL", "COMFYUI_WORKFLOW_JSON", "MEDIA_OUTPUT_ROOT")
    _append_unique_text(environment["services"], "선택한 Media Provider", "ComfyUI Server(Provider=ComfyUI일 때)")
    _append_unique_text(environment["validation_commands"], "Media Provider health/capability 확인", "ComfyUI Workflow JSON 및 Input/Output Mapping 검증", "최소 Image Generate → Preview → Save smoke test")

    contract = media_workflow_contract_bundle()
    design["media_agent_plan"] = {"type": "MEDIA_CREATION", "label": "미디어 생성·처리 Agent", "identity": "AgentStudio는 무엇을 만들지 계획/선택/검증하고 실제 생성은 외부 Media Provider가 담당", "workflow_core": {"schema_strategy": contract["schema_strategy"], "port_types": contract["port_types"], "node_categories": contract["node_categories"], "artifact": contract["artifact"], "job": contract["job"], "provider_adapter": contract["provider_adapter"]}, "node_catalog": contract["nodes"], "phase_plan": {"1A": ["Media Node Registry", "Typed Port", "Artifact", "Async Job", "Provider Adapter", "ComfyUI Adapter", "Image Input", "Image Generate", "Preview", "Save Image"], "1B": ["Image Analyzer", "Prompt Generator", "Image-to-Image", "Background Remove", "Resize/Crop", "Text Overlay", "OCR/Image Quality Validator", "Condition", "Retry", "Human Approval"], "2": ["Template/Pattern Search", "Style/Layout Planner", "Inpaint/Mask/Object Remove", "Product/Brand Validator", "Variant Generator"], "3": ["Scene Planner", "Text/Image-to-Video", "TTS", "Subtitle", "BGM", "Video Compose/Validator", "9:16 Export"]}, "retry_semantics": {"technical": "provider/network/queue 오류 → bounded retry/backoff", "quality": "validator 실패 → correction planner → prompt/parameter patch → bounded regeneration"}, "approval_semantics": "Human Approval은 WAITING_APPROVAL interrupt/checkpoint로 저장하고 승인/수정/재생성 후 resume"}
    design.setdefault("design_runtime", {})["agent_specialization"] = "MEDIA_CREATION"
    return design


def compact_media_agent_contract(design: dict[str, Any]) -> str:
    plan = design.get("media_agent_plan") if isinstance(design, dict) else None
    return json.dumps(plan or {}, ensure_ascii=False, separators=(",", ":"))
