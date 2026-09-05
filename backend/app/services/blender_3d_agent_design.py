from __future__ import annotations

import json
from typing import Any


BLENDER_3D_MARKERS = (
    "blender",
    "블렌더",
    "3d 제작",
    "3d 모델",
    "3d 모델링",
    "3d agent",
    "3d 에이전트",
    "blender mcp",
    "BLENDER_3D",
)


def is_blender_3d_agent_request(text: str | None) -> bool:
    value = str(text or "")
    folded = value.casefold()
    return any(marker.casefold() in folded for marker in BLENDER_3D_MARKERS)


def is_blender_3d_design(design: dict[str, Any] | None, request: str | None = None) -> bool:
    """Keep the specialization sticky for Agent Editor incremental revisions.

    A user may later ask only "추천 기능 추가" or "UI 변경" while editing an
    existing Blender Agent. The Editor must not lose the original 3D contract just
    because the delta request does not repeat the word Blender.
    """
    value = design or {}
    if is_blender_3d_agent_request(request):
        return True
    plan = value.get("three_d_agent_plan") or {}
    if isinstance(plan, dict) and str(plan.get("type") or "").upper() == "BLENDER_3D":
        return True
    runtime = value.get("design_runtime") or {}
    if isinstance(runtime, dict) and str(runtime.get("agent_specialization") or "").upper() == "BLENDER_3D":
        return True
    confirmed = value.get("confirmed_requirements") or {}
    specialization = confirmed.get("agent_specialization") if isinstance(confirmed, dict) else None
    return isinstance(specialization, dict) and str(specialization.get("type") or "").upper() == "BLENDER_3D"


def _append_unique_text(target: list, *values: str) -> None:
    existing = {str(item).casefold() for item in target if isinstance(item, str)}
    for value in values:
        if value and value.casefold() not in existing:
            target.append(value)
            existing.add(value.casefold())


def _append_unique_dict(target: list, item: dict, key: str = "name") -> None:
    wanted = str(item.get(key) or "").strip().casefold()
    if not wanted:
        target.append(item)
        return
    for current in target:
        if isinstance(current, dict) and str(current.get(key) or "").strip().casefold() == wanted:
            current.update(item)
            return
    target.append(item)


def _ensure_workflow_step(workflow: dict, name: str, label: str, description: str, step_type: str) -> None:
    steps = workflow.setdefault("steps", [])
    for row in steps:
        if isinstance(row, dict) and str(row.get("name") or "") == name:
            row.update({"label": label, "description": description, "type": step_type})
            return
    steps.append({"name": name, "label": label, "description": description, "type": step_type})


def _ensure_branch(workflow: dict, source: str, condition: str, yes: str, no: str) -> None:
    rows = workflow.setdefault("branches", [])
    key = (source, condition)
    for row in rows:
        if isinstance(row, dict) and (str(row.get("from") or ""), str(row.get("condition") or "")) == key:
            row.update({"yes": yes, "no": no})
            return
    rows.append({"from": source, "condition": condition, "yes": yes, "no": no})


def _ensure_policy(rows: list, target: str, payload: dict) -> None:
    for row in rows:
        if isinstance(row, dict) and str(row.get("target") or "") == target:
            row.update(payload)
            return
    rows.append({"target": target, **payload})


def _ensure_file(file_plan: dict, path: str, purpose: str, component: str) -> None:
    rows = file_plan.setdefault("new_files", [])
    for row in rows:
        if isinstance(row, dict) and str(row.get("path") or "") == path:
            row.update({"purpose": purpose, "required": True, "component": component})
            break
    else:
        rows.append({"path": path, "purpose": purpose, "required": True, "component": component})
    maps = file_plan.setdefault("component_file_map", [])
    for row in maps:
        if isinstance(row, dict) and str(row.get("component") or "") == component:
            files = row.setdefault("files", [])
            if path not in files:
                files.append(path)
            row["status"] = "planned"
            break
    else:
        maps.append({"component": component, "files": [path], "status": "planned"})


def _ensure_setting_category(settings_plan: dict, category: dict) -> None:
    categories = settings_plan.setdefault("categories", [])
    for row in categories:
        if isinstance(row, dict) and str(row.get("id") or "") == str(category.get("id") or ""):
            existing_fields = {str(field.get("key") or ""): field for field in row.setdefault("fields", []) if isinstance(field, dict)}
            for field in category.get("fields") or []:
                key = str(field.get("key") or "")
                if key in existing_fields:
                    existing_fields[key].update(field)
                else:
                    row["fields"].append(field)
            row.update({key: value for key, value in category.items() if key != "fields"})
            return
    categories.append(category)


def enforce_blender_3d_agent_design(design: dict[str, Any], request: str) -> dict[str, Any]:
    """Deterministically inject the minimum contract for a Blender MCP 3D production Agent.

    Blender MCP is treated as an execution/tool layer. The generated Agent must own
    orchestration, structured 3D requirements, scene state, validation, visual QA,
    bounded repair, rendering and artifact export.
    """
    if not is_blender_3d_design(design, request):
        return design

    spec = design.setdefault("requirement_spec", {})
    spec.setdefault("goal", "Blender MCP를 사용해 자연어 요구사항을 검증 가능한 3D Scene으로 제작하는 Agent")
    for key in ("users", "inputs", "outputs", "constraints", "acceptance_criteria"):
        spec.setdefault(key, [])
    _append_unique_text(
        spec["inputs"],
        "자연어 3D 제작 요청",
        "선택적 참고 이미지/Asset",
        "3D SceneSpec(object_type, style, dimensions, materials, colors, geometry_complexity, lighting, camera, animation, output_format, render_resolution)",
    )
    _append_unique_text(
        spec["outputs"],
        "Blender .blend Scene",
        "최종 Render 이미지 또는 Animation",
        "선택한 3D Export(GLB/GLTF/FBX/OBJ 등)",
        "Scene 검증/수정 결과 리포트",
    )
    _append_unique_text(
        spec["constraints"],
        "Blender MCP Tool 실행 전 Structured SceneSpec Validation 필수",
        "Scene 객체/Material/Camera/Light 상태를 LangGraph State와 동기화",
        "MCP 성공 응답만으로 완료 처리하지 않고 Viewport/Render 결과를 검증",
        "실패/품질 미달 수정 루프는 bounded retry로 제한",
    )
    _append_unique_text(
        spec["acceptance_criteria"],
        "Blender MCP 연결과 필요한 Tool Capability를 실행 전에 확인한다.",
        "생성된 Scene의 객체, Material, Camera, Light가 요청과 일치한다.",
        "Viewport/Render 기반 시각 QA를 통과해야 완료한다.",
        "최종 .blend 및 요청한 출력 파일 경로를 사용자에게 반환한다.",
    )

    capabilities = design.setdefault("capability_plan", {})
    capabilities.setdefault("capabilities", [])
    capabilities.setdefault("external_dependencies", [])
    capabilities.setdefault("data_needs", [])
    _append_unique_text(
        capabilities["capabilities"],
        "3D 요구사항 구조화(SceneSpec Extraction)",
        "Blender Scene 작업 계획 및 단계 분해",
        "Blender MCP Tool 선택/호출",
        "Scene State 추적 및 Checkpoint",
        "Material/Lighting/Camera/Rendering 제어",
        "Viewport Screenshot 기반 Vision QA",
        "품질 미달 자동 수정 및 재검증",
        "3D Asset/Texture/HDRI 확장 연결",
    )
    _append_unique_text(
        capabilities["external_dependencies"],
        "Blender Desktop",
        "Blender MCP Server",
        "MCP Python SDK",
        "LangGraph",
        "Vision-capable QA Provider 또는 로컬 Vision Tool(선택)",
    )
    _append_unique_text(
        capabilities["data_needs"],
        "Scene object hierarchy",
        "Materials/Textures",
        "Camera/Light state",
        "Viewport screenshots and render artifacts",
    )

    tool_plan = design.setdefault("tool_mcp_plan", {})
    decisions = tool_plan.setdefault("decisions", [])
    for item in (
        {"capability": "Blender Runtime/Tool Discovery", "execution_type": "mcp", "reason": "Blender MCP Server 연결 상태와 Tool schema/capability/risk를 Registry에서 확인합니다."},
        {"capability": "3D Scene Manipulation", "execution_type": "mcp", "reason": "Object/Mesh/Transform/Material/Camera/Light/Render 작업은 Blender MCP Tool로 실행합니다."},
        {"capability": "Scene State Validation", "execution_type": "internal_function", "reason": "MCP 호출 전후 SceneSpec/상태/업무 규칙을 Agent 내부 Validator에서 검증합니다."},
        {"capability": "Viewport Visual QA", "execution_type": "tool", "reason": "Viewport/Render 캡처를 Vision QA로 확인하여 MCP success와 실제 결과를 분리 검증합니다."},
        {"capability": "Asset Library", "execution_type": "tool", "reason": "모든 모델을 Primitive로 만들지 않고 로컬/외부 Asset Source를 선택적으로 연결할 수 있게 합니다."},
    ):
        _append_unique_dict(decisions, item, "capability")

    architecture = design.setdefault("agent_architecture", {})
    for key in ("components", "state", "interfaces", "persistence", "security"):
        architecture.setdefault(key, [])
    components = (
        {"name": "3D Requirement Router", "responsibility": "Intent Router → 3D Schema Router → Structured Extraction"},
        {"name": "3D Scene Validator", "responsibility": "형식/범위/필수값/Tool Capability/Scene 업무 규칙 검증"},
        {"name": "3D Director LangGraph", "responsibility": "Scene 제작 단계를 분해하고 MCP/QA/Repair 분기를 오케스트레이션"},
        {"name": "Blender MCP Adapter", "responsibility": "Registry 기반 Blender MCP Tool discovery/invoke/timeout/retry"},
        {"name": "Scene State Store", "responsibility": "objects/materials/textures/camera/lights/current_step/output 상태 추적"},
        {"name": "Viewport QA Agent", "responsibility": "Screenshot/Render와 요구사항을 비교하고 수정 지시 생성"},
        {"name": "3D Asset Resolver", "responsibility": "로컬 Asset/Texture/HDRI 및 향후 외부 Asset Provider 연결"},
        {"name": "Render & Export Service", "responsibility": "렌더링, 파일 저장, 형식 Export 및 결과 검증"},
    )
    for item in components:
        _append_unique_dict(architecture["components"], item)
    for item in (
        {"name": "scene_objects", "description": "객체 이름/타입/transform/parent/visibility"},
        {"name": "selected_objects", "description": "현재 작업 대상 객체"},
        {"name": "materials", "description": "Material/Texture 연결 상태"},
        {"name": "textures", "description": "Texture/HDRI Asset 상태"},
        {"name": "camera", "description": "Camera transform/lens/target"},
        {"name": "lights", "description": "Light 종류/transform/energy"},
        {"name": "current_step", "description": "현재 3D 작업 단계"},
        {"name": "completed_steps", "description": "완료 작업"},
        {"name": "failed_steps", "description": "실패/재시도 기록"},
        {"name": "render_status", "description": "렌더 진행/완료/실패"},
        {"name": "output_files", "description": "blend/render/export 산출물"},
    ):
        _append_unique_dict(architecture["state"], item)
    for value in (
        "Blender MCP Client/Transport/Server/Tool",
        "Viewport Screenshot Capture",
        "Vision QA Provider",
        "Local Asset Library",
        "Optional Text/Image-to-3D Provider",
    ):
        _append_unique_text(architecture["interfaces"], value)
    _append_unique_text(
        architecture["persistence"],
        "작업 단계별 .blend Checkpoint",
        "Scene State JSON/DB Snapshot",
        "Render/Export Artifact metadata",
    )
    _append_unique_text(
        architecture["security"],
        "Blender MCP Tool allowlist/risk 분류",
        "파일 입출력은 프로젝트 Output/Asset 허용 경로로 제한",
        "임의 Python/Script 실행 Tool은 고위험으로 분류하고 명시 승인",
        "외부 Asset 다운로드는 출처/라이선스/파일 형식을 검증",
    )

    workflow = design.setdefault("target_agent_workflow", {})
    workflow["name"] = workflow.get("name") or "Blender MCP 3D Production Agent Workflow"
    workflow.setdefault("steps", [])
    workflow.setdefault("branches", [])
    workflow.setdefault("retry_policy", [])
    workflow.setdefault("failure_policy", [])
    workflow.setdefault("requirement_coverage", [])
    step_rows = (
        ("capture_3d_request", "3D 제작 요청 수집", "자연어 요청, 참고 이미지/Asset, 출력 형식과 품질 조건을 수집합니다.", "input"),
        ("extract_scene_spec", "3D SceneSpec 구조화", "Intent Router/Schema Router/Pydantic Extraction으로 객체·스타일·치수·재질·조명·카메라·애니메이션·출력을 구조화합니다.", "llm"),
        ("validate_scene_spec", "SceneSpec 검증", "형식, 값 범위, 필수값, 충돌, Tool 지원 여부와 3D 업무 규칙을 검증합니다.", "validation"),
        ("check_blender_runtime", "Blender Runtime 확인", "Blender 실행 가능 여부, 버전, 작업 Scene과 저장 경로를 확인합니다.", "validation"),
        ("discover_blender_mcp_tools", "Blender MCP Tool 확인", "MCP Registry에서 Blender Server 연결 상태, Tool schema/capability/risk를 조회합니다.", "mcp_client"),
        ("plan_3d_tasks", "3D 제작 계획", "모델링 → Material → Lighting → Camera → Animation(선택) → Render/Export 순서로 실제 작업을 분해합니다.", "decision"),
        ("blender_mcp_transport", "Blender MCP Transport", "설정된 stdio 또는 streamable HTTP Transport로 검증된 Tool 요청을 전달합니다.", "transport"),
        ("execute_blender_tool", "Blender Scene 작업 실행", "Object/Mesh/Transform/Material/Camera/Light/Render 관련 Blender MCP Tool을 단계별 호출합니다.", "tool"),
        ("sync_scene_state", "Scene State 동기화", "실행 결과를 객체/Material/Camera/Light/현재 단계/산출물 State에 반영하고 Checkpoint를 남깁니다.", "storage"),
        ("capture_viewport", "Viewport 캡처", "현재 Scene의 Viewport 또는 임시 Render 이미지를 캡처합니다.", "tool"),
        ("vision_scene_qa", "3D 결과 Vision QA", "캡처 결과와 SceneSpec을 비교해 위치, 누락, Material, Camera, Lighting, 형태 문제를 판정합니다.", "llm"),
        ("decide_scene_repair", "수정 필요 여부 판단", "품질 미달이면 원인과 수정 대상 Tool을 결정하고 bounded repair loop로 돌아갑니다.", "decision"),
        ("render_final_scene", "최종 Render", "검증을 통과한 Scene을 지정 Renderer/해상도로 최종 렌더링합니다.", "tool"),
        ("validate_3d_outputs", "3D 산출물 검증", ".blend와 Render/Export 파일 존재, 크기, 형식, 최종 Scene 상태를 검증합니다.", "validation"),
        ("export_3d_artifacts", "3D 파일 저장/Export", "프로젝트 Output 허용 경로에 .blend와 요청한 GLB/GLTF/FBX/OBJ/Render 산출물을 저장합니다.", "storage"),
        ("complete", "3D 제작 완료", "최종 파일 경로, Scene 요약, 검증 결과와 남은 경고를 사용자에게 반환합니다.", "complete"),
    )
    for args in step_rows:
        _ensure_workflow_step(workflow, *args)
    _ensure_branch(workflow, "validate_scene_spec", "SceneSpec이 유효하고 필요한 정보가 충분한가?", "check_blender_runtime", "request_missing_3d_fields")
    _ensure_branch(workflow, "check_blender_runtime", "Blender Runtime이 준비되었는가?", "discover_blender_mcp_tools", "fail_blender_runtime")
    _ensure_branch(workflow, "discover_blender_mcp_tools", "필요 Blender MCP Tool이 연결/활성 상태인가?", "plan_3d_tasks", "fail_blender_mcp")
    _ensure_branch(workflow, "vision_scene_qa", "Scene이 SceneSpec/품질 기준을 만족하는가?", "render_final_scene", "decide_scene_repair")
    _ensure_branch(workflow, "decide_scene_repair", "재시도 한도 내에서 자동 수정 가능한가?", "execute_blender_tool", "fail_scene_quality")
    _ensure_branch(workflow, "validate_3d_outputs", "최종 산출물이 모두 유효한가?", "export_3d_artifacts", "fail_output_validation")
    _ensure_policy(workflow["retry_policy"], "execute_blender_tool", {"condition": "일시적 MCP/Blender 실행 실패", "strategy": "최대 3회 bounded retry + 짧은 backoff, 동일 실패 반복 시 중단"})
    _ensure_policy(workflow["retry_policy"], "vision_scene_qa", {"condition": "품질 미달이나 자동 수정 가능한 오류", "strategy": "최대 3회 Scene repair loop, 매 회 Viewport 재검증"})
    for target, action in (
        ("check_blender_runtime", "Blender 실행/버전/Scene 준비 실패 원인을 표시하고 작업을 중단합니다."),
        ("discover_blender_mcp_tools", "연결되지 않았거나 필요한 Blender MCP Tool이 없으면 Registry 상태와 필요한 Tool을 표시합니다."),
        ("execute_blender_tool", "Tool 실패 Context와 Scene Checkpoint를 보존하고 안전하게 중단 또는 재시도합니다."),
        ("vision_scene_qa", "수정 한도를 초과하면 마지막 정상 Scene과 QA 리포트를 보존하고 실패 처리합니다."),
        ("validate_3d_outputs", "손상/누락 산출물은 완료 처리하지 않고 Output 경로와 검증 오류를 반환합니다."),
    ):
        _ensure_policy(workflow["failure_policy"], target, {"action": action})
    coverage = [row for row in workflow.get("requirement_coverage") or [] if not (isinstance(row, dict) and str(row.get("requirement") or "").startswith("Blender 3D"))]
    coverage.extend([
        {"requirement": "Blender 3D Structured SceneSpec", "covered_by": ["extract_scene_spec", "validate_scene_spec"], "status": "covered"},
        {"requirement": "Blender MCP 기반 Scene 제작", "covered_by": ["discover_blender_mcp_tools", "blender_mcp_transport", "execute_blender_tool"], "status": "covered"},
        {"requirement": "Scene State 지속 관리", "covered_by": ["sync_scene_state"], "status": "covered"},
        {"requirement": "Viewport/Render 기반 품질 검증", "covered_by": ["capture_viewport", "vision_scene_qa", "decide_scene_repair"], "status": "covered"},
        {"requirement": "Render 및 3D 파일 Export", "covered_by": ["render_final_scene", "validate_3d_outputs", "export_3d_artifacts"], "status": "covered"},
    ])
    workflow["requirement_coverage"] = coverage

    file_plan = design.setdefault("file_plan", {})
    file_plan.setdefault("existing_files_to_modify", [])
    file_plan.setdefault("new_files", [])
    file_plan.setdefault("component_file_map", [])
    planned_files = (
        ("backend/app/schemas/scene_spec.py", "Pydantic 기반 3D SceneSpec/ValidationResult schema", "3D Requirement Router"),
        ("backend/app/services/blender_mcp_adapter.py", "Blender MCP Registry discovery, Tool invocation, timeout/risk policy", "Blender MCP Adapter"),
        ("backend/app/services/scene_validator.py", "SceneSpec/Scene State/Tool capability/업무 규칙 검증", "3D Scene Validator"),
        ("backend/app/services/scene_state_service.py", "Scene object/material/camera/light/checkpoint 상태 관리", "Scene State Store"),
        ("backend/app/services/viewport_qa_service.py", "Viewport/Render capture와 Vision QA 결과 처리", "Viewport QA Agent"),
        ("backend/app/services/asset_resolver.py", "로컬 Asset/Texture/HDRI와 선택적 외부 Asset 연결", "3D Asset Resolver"),
        ("backend/app/services/render_export_service.py", "Render/Blend/GLTF/FBX/OBJ 저장 및 검증", "Render & Export Service"),
        ("backend/app/workflows/blender_3d_workflow.py", "LangGraph 기반 3D Director Workflow와 repair branch", "3D Director LangGraph"),
        ("backend/tests/test_scene_spec_validator.py", "SceneSpec 형식/범위/필수값/충돌 검증 테스트", "3D Scene Validator"),
        ("backend/tests/test_blender_mcp_contract.py", "Blender MCP Tool discovery/invoke/risk/failure 계약 테스트", "Blender MCP Adapter"),
        ("backend/tests/test_blender_3d_workflow.py", "Scene 제작/QA/repair/render/export LangGraph 계약 테스트", "3D Director LangGraph"),
        ("backend/tests/test_blender_3d_regression.py", "Agent Editor 증분 변경 후 기존 SceneSpec/MCP/QA/Render 계약 회귀 테스트", "3D Director LangGraph"),
    )
    for path, purpose, component in planned_files:
        _ensure_file(file_plan, path, purpose, component)

    settings = design.setdefault("settings_plan", {})
    settings["enabled"] = True
    settings.setdefault("reason", "Blender 실행 경로, MCP Transport, Renderer, Output/Asset, QA 정책은 런타임에서 변경 가능해야 합니다.")
    settings.setdefault("backend", {})
    settings.setdefault("frontend", {})
    settings.setdefault("security", {"mask_secrets": True, "never_return_secret_plaintext": True})
    settings.setdefault("tests", [])
    _ensure_setting_category(settings, {
        "id": "blender_3d",
        "label": "Blender / 3D",
        "fields": [
            {"key": "BLENDER_EXECUTABLE", "label": "Blender 실행 파일", "type": "path", "default": "", "required": False, "secret": False, "description": "비우면 OS PATH/기본 설치 경로에서 탐색", "options": [], "validation": {"path_exists_if_set": True}, "storage": "config"},
            {"key": "BLENDER_MCP_TRANSPORT", "label": "Blender MCP Transport", "type": "select", "default": "stdio", "required": True, "secret": False, "description": "연결된 Blender MCP Server 방식", "options": ["stdio", "streamable_http"], "validation": {}, "storage": "config"},
            {"key": "BLENDER_MCP_ENDPOINT", "label": "Blender MCP Endpoint", "type": "string", "default": "", "required": False, "secret": False, "description": "streamable_http 사용 시 Endpoint", "options": [], "validation": {}, "storage": "config"},
            {"key": "BLENDER_MCP_COMMAND", "label": "Blender MCP Command", "type": "string", "default": "", "required": False, "secret": False, "description": "stdio Server 실행 명령", "options": [], "validation": {}, "storage": "config"},
            {"key": "BLENDER_RENDER_ENGINE", "label": "Render Engine", "type": "select", "default": "BLENDER_EEVEE_NEXT", "required": True, "secret": False, "description": "기본 렌더 엔진", "options": ["BLENDER_EEVEE_NEXT", "CYCLES", "BLENDER_WORKBENCH"], "validation": {}, "storage": "config"},
            {"key": "BLENDER_RENDER_RESOLUTION", "label": "Render Resolution", "type": "string", "default": "1024x1024", "required": True, "secret": False, "description": "예: 1024x1024", "options": [], "validation": {"pattern": "^[0-9]{2,5}x[0-9]{2,5}$"}, "storage": "config"},
            {"key": "BLENDER_OUTPUT_DIR", "label": "3D Output 경로", "type": "path", "default": "output/3d", "required": True, "secret": False, "description": "blend/render/export 허용 Root", "options": [], "validation": {}, "storage": "config"},
            {"key": "BLENDER_ASSET_DIR", "label": "3D Asset 경로", "type": "path", "default": "assets/3d", "required": False, "secret": False, "description": "로컬 Model/Texture/HDRI Library", "options": [], "validation": {}, "storage": "config"},
            {"key": "BLENDER_VISION_QA_ENABLED", "label": "Viewport Vision QA", "type": "boolean", "default": True, "required": True, "secret": False, "description": "MCP success 외에 실제 화면을 추가 검증", "options": [], "validation": {}, "storage": "config"},
            {"key": "BLENDER_MAX_REPAIR_ITERATIONS", "label": "자동 수정 최대 횟수", "type": "number", "default": 3, "required": True, "secret": False, "description": "무한 수정 루프 방지", "options": [], "validation": {"min": 0, "max": 10}, "storage": "config"},
        ],
    })
    _append_unique_text(settings["tests"], "Blender runtime discovery", "Blender MCP readiness", "3D output path validation", "Viewport QA toggle and repair limit")

    environment = design.setdefault("environment_plan", {})
    for key in ("env_vars", "dependencies", "services", "startup", "validation_commands"):
        environment.setdefault(key, [])
    for dependency in ("mcp", "langgraph", "pydantic", "Pillow"):
        _append_unique_text(environment["dependencies"], dependency)
    _append_unique_text(environment["services"], "Blender Desktop", "Blender MCP Server")
    _append_unique_text(
        environment["startup"],
        "Blender 설치/실행 경로 확인",
        "Blender MCP Server 연결/Tool discovery",
        "Scene State/Output/Asset 디렉터리 준비",
    )
    _append_unique_text(
        environment["validation_commands"],
        "Blender version/readiness 확인",
        "Blender MCP list_tools 및 필수 3D capability 확인",
        "최소 Cube Scene 생성 → Viewport 캡처 → 임시 Render smoke test",
    )

    design["three_d_agent_plan"] = {
        "type": "BLENDER_3D",
        "label": "3D 제작 Agent · Blender MCP",
        "orchestration": "Intent Router → 3D Schema Router → Structured Extraction(Pydantic) → Validator → LangGraph State → Blender MCP → Viewport QA → Repair → Render/Export",
        "scene_schema_fields": [
            "object_type", "style", "dimensions", "materials", "colors", "geometry_complexity",
            "lighting", "camera", "animation", "output_format", "render_resolution",
        ],
        "scene_state_fields": [
            "scene_objects", "selected_objects", "materials", "textures", "camera", "lights",
            "current_step", "completed_steps", "failed_steps", "render_status", "output_files",
        ],
        "validation_layers": [
            "format", "value_range", "required_fields", "confidence", "scene_conflict",
            "tool_capability", "business_rule", "output_artifact",
        ],
        "qa_loop": "Blender 작업 → Viewport/Render Screenshot → Vision QA → 문제 분석 → bounded MCP 수정 → 재검증",
        "recommended_phases": [
            "1단계: Primitive/Material/Camera/Light/Render",
            "2단계: 복합 Scene/객체 hierarchy",
            "3단계: 참고 이미지 기반 제작과 비교 수정",
            "4단계: Keyframe/Timeline/Camera Animation",
            "5단계: Director + Modeling/Material/Lighting/Animation/Rendering/QA 전문 Agent 분리",
        ],
        "creator_contract": {
            "mode": "AGENT_CREATOR",
            "steps": [
                "3D 요구사항 분석", "Agent Architecture 설계", "LangGraph Workflow 설계",
                "LLM/Vision Provider 선택", "Blender MCP Tool/Transport 연결",
                "Scene State/Memory/DB 설계", "UI/Preview 설계", "실제 소스코드/테스트 생성",
            ],
            "rule": "Blender MCP는 Tool 실행 계층이며 Agent가 계획/검증/QA/수정/완료 판단을 소유한다.",
        },
        "editor_contract": {
            "mode": "AGENT_EDITOR",
            "pipeline": [
                "현재 Agent/소스 분석", "현재 Architecture/Workflow/Scene 계약 파악",
                "변경 요구 분석", "영향 범위/수정 파일 계산", "영향 파일만 증분 수정",
                "기존 3D 핵심 기능 Regression Test", "As-Built/Workflow 재검증",
            ],
            "supported_changes": [
                "3D 기능 추가/삭제", "Workflow/분기/Retry 변경", "Blender MCP Tool 추가/교체",
                "SceneSpec/Validator 변경", "Scene State/Memory/DB 변경", "Prompt/LLM/Vision Provider 변경",
                "Asset/Texture/HDRI Provider 변경", "UI/Preview 변경", "오류 수정/성능 개선",
            ],
            "impact_analysis": [
                "Architecture", "Workflow", "Tool/MCP", "SceneSpec/State", "Memory/DB",
                "Prompt/LLM", "UI", "Render/Export", "Regression Tests",
            ],
            "preserve": [
                "기존 SceneSpec 호환성", "기존 Blender MCP Tool 계약", "기존 Scene State",
                "기존 Render/Export 경로", "기존 정상 Workflow/기능",
            ],
            "baseline_artifacts": [
                "현재 Architecture Snapshot", "현재 Workflow Snapshot", "Tool Registry Snapshot",
                "SceneSpec/State Schema", "기존 Regression Test 결과",
            ],
            "regression_tests": [
                "SceneSpec Validator", "Blender MCP discovery/invoke/risk",
                "기본 Cube Scene smoke", "Viewport/Render QA loop", "Render/Export artifact validation",
            ],
            "rule": "전체 프로젝트를 재생성하지 않고 영향받은 설계 section/파일만 수정한 뒤 기존 기능 회귀 테스트를 수행한다.",
        },
        "mcp_required": True,
        "blender_runtime_required": True,
        "viewport_qa_required": True,
    }
    design.setdefault("design_runtime", {})["agent_specialization"] = "BLENDER_3D"
    return design


def compact_blender_3d_contract(design: dict[str, Any]) -> str:
    plan = design.get("three_d_agent_plan") if isinstance(design, dict) else None
    return json.dumps(plan or {}, ensure_ascii=False, separators=(",", ":"))
