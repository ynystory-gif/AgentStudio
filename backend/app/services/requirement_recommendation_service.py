from __future__ import annotations

from typing import Any
import re


def _folded_text(user_text: str, history: list[dict] | None = None, attachment_memory: str = "") -> str:
    rows: list[str] = []
    for item in history or []:
        if str(item.get("role") or "") == "user":
            rows.append(str(item.get("content") or ""))
    rows.append(str(user_text or ""))
    if attachment_memory:
        rows.append(str(attachment_memory))
    return "\n".join(rows).casefold()


def _item(item_id: str, label: str, reason: str, *, priority: int = 50, default_selected: bool = True, **extra: Any) -> dict[str, Any]:
    return {
        "id": item_id,
        "label": label,
        "reason": reason,
        "priority": int(priority),
        "default_selected": bool(default_selected),
        **extra,
    }


def _append_unique(rows: list[dict[str, Any]], row: dict[str, Any]) -> None:
    wanted = str(row.get("id") or "").strip()
    if not wanted:
        return
    for current in rows:
        if str(current.get("id") or "").strip() == wanted:
            current.update(row)
            return
    rows.append(row)


def _token_in_haystack(token: str, haystack: str) -> bool:
    value = str(token or "").casefold().strip()
    if not value:
        return False
    if len(value) <= 3 and value.isascii():
        return re.search(rf"(?:^|[^a-z0-9_]){re.escape(value)}(?:$|[^a-z0-9_])", haystack) is not None
    return value in haystack


def _tool_matches(tool: dict[str, Any], *tokens: str) -> bool:
    haystack = " ".join(
        str(tool.get(key) or "")
        for key in ("name", "description", "category", "subcategory", "capability", "provider")
    ).casefold()
    return any(_token_in_haystack(str(token), haystack) for token in tokens if str(token).strip())


def _best_registered_tool(registered_tools: list[dict[str, Any]], *tokens: str) -> dict[str, Any] | None:
    wanted = [str(token).casefold() for token in tokens if str(token).strip()]
    broad = {"blender", "tool", "mcp", "3d"}
    scored: list[tuple[int, int, dict[str, Any]]] = []
    for tool in registered_tools:
        haystack = " ".join(
            str(tool.get(key) or "")
            for key in ("name", "description", "category", "subcategory", "capability", "provider")
        ).casefold()
        matched = [token for token in wanted if _token_in_haystack(token, haystack)]
        if not matched:
            continue
        specific_count = sum(1 for token in matched if token not in broad)
        if any(token not in broad for token in wanted) and specific_count == 0:
            continue
        scored.append((specific_count, len(matched), tool))
    if not scored:
        return None
    scored.sort(
        key=lambda row: (
            -row[0],
            -row[1],
            int(row[2].get("risk_level") or 0),
            0 if row[2].get("enabled", True) else 1,
            str(row[2].get("name") or ""),
        )
    )
    return scored[0][2]


def _recommended_tool(
    registered_tools: list[dict[str, Any]],
    item_id: str,
    label: str,
    reason: str,
    tokens: tuple[str, ...],
    *,
    category: str,
    priority: int,
    default_selected: bool = True,
) -> dict[str, Any]:
    matched = _best_registered_tool(registered_tools, *tokens)
    if matched:
        return _item(
            item_id,
            str(matched.get("name") or label),
            reason,
            category=str(matched.get("category") or category),
            source="registry",
            registered=True,
            provider=str(matched.get("provider") or ""),
            registry_tool_name=str(matched.get("name") or ""),
            risk_level=int(matched.get("risk_level") or 0),
            requires_confirmation=bool(matched.get("requires_confirmation")),
            priority=priority,
            default_selected=default_selected,
        )
    return _item(
        item_id,
        label,
        reason,
        category=category,
        source="recommended_capability",
        registered=False,
        provider="",
        registry_tool_name="",
        risk_level=0,
        requires_confirmation=False,
        priority=priority,
        default_selected=default_selected,
    )


def build_requirement_recommendations(
    user_text: str,
    history: list[dict] | None = None,
    *,
    attachment_memory: str = "",
    agent_specialization: str = "",
    registered_tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build explainable Requirement Analysis recommendations without another LLM call.

    The recommendation layer is intentionally deterministic and cheap. The interview LLM
    remains responsible for conversation. This layer recommends feature/menu/tool defaults
    and a two-stage Tool classification policy that AgentStudio can persist into the final
    confirmed requirements and Workflow design.
    """

    text = _folded_text(user_text, history, attachment_memory)
    specialization = str(agent_specialization or "").strip().upper()
    tools = list(registered_tools or [])
    features: list[dict[str, Any]] = []
    menus: list[dict[str, Any]] = []
    recommended_tools: list[dict[str, Any]] = []

    # Universal Agent Creator/Editor support.
    _append_unique(features, _item("activity_history", "작업 이력 / Activity", "장시간 Agent 작업, 실패/재개, Tool 호출 결과를 확인할 수 있어야 합니다.", priority=35))
    _append_unique(features, _item("runtime_settings", "실행 설정", "LLM, MCP, 경로, Timeout, 승인 정책을 소스 수정 없이 바꿀 수 있게 합니다.", priority=40))
    _append_unique(menus, _item("dashboard", "Dashboard", "현재 Agent 상태와 핵심 결과를 한 화면에서 확인합니다.", priority=25))
    _append_unique(menus, _item("activity", "Activity", "실행/Tool/오류/재개 이력을 확인합니다.", priority=35))
    _append_unique(menus, _item("settings", "Settings", "LLM·Tool·MCP·Runtime 설정을 관리합니다.", priority=40))

    if any(token in text for token in ("검색", "search", "상품", "product", "catalog", "카탈로그")):
        _append_unique(features, _item("natural_language_search", "자연어 검색", "사용자가 키워드가 아닌 문장으로도 대상을 찾을 수 있게 합니다.", priority=80))
        _append_unique(menus, _item("search", "Search", "검색 조건과 결과를 독립 화면으로 제공합니다.", priority=80))
        _append_unique(recommended_tools, _recommended_tool(tools, "search_tool", "검색 Tool", "검색/조회 기능을 실제 데이터 소스와 연결합니다.", ("search", "검색", "query"), category="SEARCH", priority=80))

    if any(token in text for token in ("추천", "recommend", "personalize", "개인화")):
        _append_unique(features, _item("recommendation", "추천 / 개인화", "검색 결과 또는 사용자 Context를 이용해 추천 후보를 생성합니다.", priority=90))
        _append_unique(menus, _item("recommendations", "Recommendations", "추천 결과와 추천 근거를 별도 화면에서 확인합니다.", priority=88))
        _append_unique(recommended_tools, _recommended_tool(tools, "vector_retrieval_tool", "Vector / Similarity Tool", "추천 후보 생성에 의미 유사도 검색을 사용할 수 있게 합니다.", ("pgvector", "vector", "similarity", "embedding", "recommend"), category="SEARCH", priority=88))

    if any(token in text for token in ("주문", "order", "cart", "장바구니", "결제")):
        _append_unique(features, _item("order_workflow", "주문 Workflow", "조회 → 선택 → 확인 → 주문 생성 과정을 상태 기반으로 처리합니다.", priority=85))
        _append_unique(menus, _item("orders", "Orders", "주문 상태와 이력을 확인합니다.", priority=82))

    if any(token in text for token in ("rag", "문서", "knowledge", "지식", "faq", "pdf")):
        _append_unique(features, _item("rag", "RAG / 지식 검색", "문서 지식과 LLM 응답을 분리하고 출처 기반 답변을 구성합니다.", priority=82))
        _append_unique(menus, _item("knowledge", "Knowledge", "문서/Index/동기화 상태를 관리합니다.", priority=72))
        _append_unique(recommended_tools, _recommended_tool(tools, "document_retrieval_tool", "Document Retrieval Tool", "RAG 문서 검색과 Context Retrieval을 담당합니다.", ("rag", "document", "retrieval", "vector", "file"), category="KNOWLEDGE", priority=80))

    if any(token in text for token in ("브라우저", "browser", "웹사이트", "website", "crawl", "크롤")):
        _append_unique(features, _item("browser_automation", "Browser 자동화", "웹 페이지 확인/수집/조작을 Agent Workflow에서 수행합니다.", priority=78))
        _append_unique(recommended_tools, _recommended_tool(tools, "browser_tool", "Browser Tool", "웹 탐색과 페이지 상호작용을 실행합니다.", ("browser", "chromium", "playwright", "web"), category="BROWSER", priority=78))

    if any(token in text for token in ("postgresql", "database", "데이터베이스", " db ", "redis", "pgvector")):
        _append_unique(features, _item("data_persistence", "DB / 상태 저장", "Agent 상태와 업무 데이터를 재실행 가능하게 저장합니다.", priority=75))
        _append_unique(menus, _item("data", "Data", "DB/Cache/Vector 상태를 운영 화면에서 확인합니다.", priority=60))
        _append_unique(recommended_tools, _recommended_tool(tools, "database_tool", "Database Tool", "구조화 조회/저장 작업을 DB 계층으로 분리합니다.", ("postgres", "database", "sql", "redis", "pgvector"), category="DATABASE", priority=75))

    if specialization == "BLENDER_3D" or any(token in text for token in ("blender", "블렌더", "3d 제작", "3d 모델", "3d 모델링")):
        specialization = "BLENDER_3D"
        blender_features = (
            ("scene_spec", "SceneSpec 구조화", "자연어 3D 요청을 Object/Material/Lighting/Camera/Animation/Output 구조로 변환합니다.", 100),
            ("scene_modeling", "Scene / 모델링", "Scene 객체 생성·수정·Transform을 작업 단계로 관리합니다.", 98),
            ("materials", "Material / Texture", "재질·Texture·색상 요구를 Scene State와 동기화합니다.", 94),
            ("lighting_camera", "Lighting / Camera", "조명과 카메라 구도를 별도 검증 가능한 상태로 관리합니다.", 94),
            ("viewport_vision_qa", "Viewport / Render Vision QA", "MCP success만 신뢰하지 않고 실제 화면 결과를 검증합니다.", 100),
            ("bounded_repair", "자동 수정 / 재검증", "품질 미달 시 제한된 횟수로 수정 후 다시 검증합니다.", 96),
            ("render_export", "Render / Export", ".blend와 GLB/GLTF/FBX/OBJ/Render 결과를 검증 후 저장합니다.", 96),
            ("asset_library", "Asset / Texture / HDRI Library", "Primitive만 생성하지 않고 재사용 Asset을 연결할 수 있게 합니다.", 82),
        )
        for item_id, label, reason, priority in blender_features:
            _append_unique(features, _item(item_id, label, reason, priority=priority))

        blender_menus = (
            ("scene", "Scene", "현재 Scene Object와 계층/선택 상태를 확인합니다.", 100),
            ("assets", "Assets", "Model/Texture/HDRI Asset을 검색하고 Scene에 추가합니다.", 90),
            ("materials", "Materials", "Material/Texture 적용 상태를 확인합니다.", 88),
            ("lighting_camera", "Lighting & Camera", "조명·카메라 구도와 Preview를 조정합니다.", 88),
            ("render_export", "Render & Export", "Render 설정, 진행 상태, 최종 출력 파일을 관리합니다.", 96),
        )
        for item_id, label, reason, priority in blender_menus:
            _append_unique(menus, _item(item_id, label, reason, priority=priority))

        blender_tools = (
            ("blender_scene_tool", "Blender MCP · Scene/Mesh Tool", "Object/Mesh/Transform 작업을 Blender MCP로 실행합니다.", ("blender", "mesh", "object", "scene", "bpy"), "3D", 100),
            ("blender_material_tool", "Blender MCP · Material Tool", "Material/Texture 속성을 Blender Scene에 적용합니다.", ("blender", "material", "texture", "shader"), "3D", 94),
            ("blender_camera_light_tool", "Blender MCP · Camera/Light Tool", "Camera/Light 생성·수정·배치를 수행합니다.", ("blender", "camera", "light", "lighting"), "3D", 94),
            ("viewport_capture_tool", "Viewport Capture Tool", "실제 Viewport/Render 캡처를 Vision QA 입력으로 만듭니다.", ("viewport", "screenshot", "render", "capture"), "3D", 98),
            ("vision_qa_tool", "Vision QA Tool / Multimodal LLM", "Viewport/Render 이미지와 SceneSpec을 비교해 누락·배치·재질·구도 문제를 판정합니다.", ("vision", "image", "multimodal", "visual", "qa"), "VISION", 97),
            ("render_export_tool", "Blender MCP · Render/Export Tool", "렌더 실행과 .blend/GLB/FBX/OBJ Export를 처리합니다.", ("blender", "render", "export", "gltf", "fbx", "obj"), "3D", 98),
            ("asset_resolver_tool", "3D Asset Resolver", "로컬 Asset/Texture/HDRI 또는 연결된 Asset Provider를 검색합니다.", ("asset", "texture", "hdri", "model"), "ASSET", 82),
        )
        for item_id, label, reason, tokens, category, priority in blender_tools:
            _append_unique(recommended_tools, _recommended_tool(tools, item_id, label, reason, tokens, category=category, priority=priority))

    # LLM is not used blindly for every Tool selection. First narrow to a capability
    # category; then select a concrete Tool from the registry with schema/risk checks.
    llm_tool_routing = {
        "enabled": True,
        "policy": "TWO_STAGE_TOOL_ROUTING",
        "first_stage": {
            "id": "llm_intent_capability_classifier",
            "label": "1차 분류 · Intent / Capability Router",
            "mode": "llm_structured_classification",
            "purpose": "사용자 요청을 Tool 카테고리와 필요한 Capability로 먼저 분류합니다.",
            "input": "user_intent + LangGraph state + confirmed requirements",
            "output_schema": ["primary_category", "secondary_categories", "capabilities", "confidence"],
            "categories": ["INTERNAL", "MCP", "DATABASE", "SEARCH", "BROWSER", "FILE", "KNOWLEDGE", "3D", "ASSET", "API"],
            "llm_condition": "deterministic confidence < 0.80 또는 복수 카테고리 충돌 시",
            "fallback": "deterministic_capability_router",
            "default_selected": True,
        },
        "second_stage": {
            "id": "tool_registry_candidate_selector",
            "label": "2차 분류 · Tool Registry Candidate Selector",
            "mode": "schema_risk_scoring_then_llm_if_ambiguous",
            "purpose": "1차 분류 카테고리 안에서 Tool schema/capability/권한/위험도/가용성을 비교해 실제 Tool을 선택합니다.",
            "input": "stage1 categories + tool registry(name/description/input_schema/capability/risk/permission)",
            "output_schema": ["selected_tool", "alternatives", "reason", "risk_level", "requires_confirmation", "confidence"],
            "llm_condition": "동일 Capability 후보가 2개 이상이고 deterministic score 차이가 작을 때",
            "fallback": "highest_validated_registry_score",
            "default_selected": True,
        },
        "safety": {
            "tool_validation_before_invoke": True,
            "respect_registry_enabled": True,
            "respect_permission_and_confirmation": True,
            "high_risk_requires_confirmation": True,
            "never_invent_unregistered_tool": True,
        },
    }

    features.sort(key=lambda row: (-int(row.get("priority") or 0), str(row.get("label") or "")))
    menus.sort(key=lambda row: (-int(row.get("priority") or 0), str(row.get("label") or "")))
    recommended_tools.sort(key=lambda row: (-int(row.get("priority") or 0), str(row.get("label") or "")))

    default_settings = {
        "features": [row["id"] for row in features if row.get("default_selected", True)],
        "menus": [row["id"] for row in menus if row.get("default_selected", True)],
        "tools": [row["id"] for row in recommended_tools if row.get("default_selected", True)],
        "llm_tool_routing": {
            "enabled": True,
            "first_stage_id": llm_tool_routing["first_stage"]["id"],
            "second_stage_id": llm_tool_routing["second_stage"]["id"],
            "llm_only_when_ambiguous": True,
        },
        "customized": False,
    }

    return {
        "version": 1,
        "agent_specialization": specialization or "GENERAL",
        "features": features,
        "menus": menus,
        "tools": recommended_tools,
        "llm_tool_routing": llm_tool_routing,
        "default_settings": default_settings,
    }


def apply_recommendation_settings_to_design(
    design: dict[str, Any],
    confirmed_requirements: dict[str, Any] | None,
) -> dict[str, Any]:
    """Enforce user-applied recommendation settings even on deterministic fallback designs."""
    confirmed = confirmed_requirements if isinstance(confirmed_requirements, dict) else {}
    settings = confirmed.get("recommendation_settings")
    if not isinstance(settings, dict):
        return design

    selected_features = [row for row in settings.get("selected_features") or [] if isinstance(row, dict)]
    selected_menus = [row for row in settings.get("selected_menus") or [] if isinstance(row, dict)]
    selected_tools = [row for row in settings.get("selected_tools") or [] if isinstance(row, dict)]
    routing = settings.get("llm_tool_routing") if isinstance(settings.get("llm_tool_routing"), dict) else {}

    requirement_spec = design.setdefault("requirement_spec", {})
    acceptance = requirement_spec.setdefault("acceptance_criteria", [])
    capability_plan = design.setdefault("capability_plan", {})
    capabilities = capability_plan.setdefault("capabilities", [])
    tool_plan = design.setdefault("tool_mcp_plan", {})
    decisions = tool_plan.setdefault("decisions", [])
    architecture = design.setdefault("agent_architecture", {})
    components = architecture.setdefault("components", [])
    interfaces = architecture.setdefault("interfaces", [])
    workflow = design.setdefault("target_agent_workflow", {})
    steps = workflow.setdefault("steps", [])
    coverage = workflow.setdefault("requirement_coverage", [])
    file_plan = design.setdefault("file_plan", {})
    new_files = file_plan.setdefault("new_files", [])
    component_file_map = file_plan.setdefault("component_file_map", [])

    def append_text(rows: list, value: str) -> None:
        folded = value.casefold()
        if not any(isinstance(row, str) and row.casefold() == folded for row in rows):
            rows.append(value)

    def append_named(rows: list, item: dict, key: str = "name") -> None:
        wanted = str(item.get(key) or "").casefold()
        for current in rows:
            if isinstance(current, dict) and str(current.get(key) or "").casefold() == wanted:
                current.update(item)
                return
        rows.append(item)

    for feature in selected_features:
        label = str(feature.get("label") or feature.get("id") or "").strip()
        if not label:
            continue
        append_text(capabilities, label)
        append_text(acceptance, f"추천 기능 '{label}'이 최종 Agent에 구현되어야 한다.")
        append_named(coverage, {"requirement": f"추천 기능: {label}", "covered_by": [], "status": "covered"}, key="requirement")

    for menu in selected_menus:
        label = str(menu.get("label") or menu.get("id") or "").strip()
        if not label:
            continue
        append_named(interfaces, {"name": f"UI Menu · {label}", "type": "ui_menu", "responsibility": f"추천 메뉴 '{label}' 화면/Navigation 제공"})
        append_text(acceptance, f"추천 메뉴 '{label}'이 UI Navigation과 실제 페이지/기능에 연결되어야 한다.")

    for tool in selected_tools:
        label = str(tool.get("label") or tool.get("registry_tool_name") or tool.get("id") or "").strip()
        if not label:
            continue
        registered = tool.get("registered") is True
        capability = str(tool.get("category") or label)
        append_named(decisions, {
            "capability": label,
            "execution_type": "mcp" if registered else "none",
            "reason": (
                "요구사항 분석에서 사용자가 적용한 Registry Tool입니다. enabled/schema/risk/permission 검증 후 호출합니다."
                if registered
                else "요구사항 분석에서 사용자가 적용한 추천 Capability입니다. Registry에 실제 Tool이 등록되기 전에는 호출하지 않고 setup needed 상태로 처리합니다."
            ),
            "registry_tool_name": str(tool.get("registry_tool_name") or ""),
            "registered": registered,
            "risk_level": int(tool.get("risk_level") or 0),
            "requires_confirmation": bool(tool.get("requires_confirmation")),
        }, key="capability")
        append_text(capabilities, f"Tool Capability · {capability}")

    if routing.get("enabled") is not False:
        first_id = str(routing.get("first_stage_id") or "llm_intent_capability_classifier")
        second_id = str(routing.get("second_stage_id") or "tool_registry_candidate_selector")
        only_ambiguous = routing.get("llm_only_when_ambiguous") is not False
        append_named(components, {
            "name": "Tool Capability Router (1차)",
            "responsibility": f"{first_id}: 사용자 Intent를 Tool Category/Capability로 1차 분류" + ("; deterministic confidence가 충분하면 LLM 생략" if only_ambiguous else ""),
        })
        append_named(components, {
            "name": "Tool Registry Selector (2차)",
            "responsibility": f"{second_id}: 1차 후보 안에서 Tool schema/capability/risk/permission/enabled를 검증해 실제 Tool 선택",
        })

        def ensure_step(name: str, label: str, description: str, step_type: str) -> None:
            for row in steps:
                if isinstance(row, dict) and str(row.get("name") or "") == name:
                    row.update({"label": label, "description": description, "type": step_type})
                    return
            item = {"name": name, "label": label, "description": description, "type": step_type}
            complete_index = next((idx for idx, row in enumerate(steps) if isinstance(row, dict) and str(row.get("type") or "") == "complete"), len(steps))
            steps.insert(complete_index, item)

        ensure_step(
            "classify_tool_capability",
            "1차 Tool 분류",
            f"{first_id}로 Intent → Tool Category/Capability를 구조화 분류합니다. LLM은 {'애매한 경우에만 사용합니다.' if only_ambiguous else '분류에 사용할 수 있습니다.'}",
            "llm" if first_id == "llm_intent_capability_classifier" else "decision",
        )
        ensure_step(
            "select_registry_tool",
            "2차 Tool 선택",
            f"{second_id}로 Tool Registry 후보의 schema/capability/risk/permission/enabled를 검증해 실행 Tool을 확정합니다.",
            "decision",
        )
        append_named(coverage, {
            "requirement": "LLM Tool 2단계 분류",
            "covered_by": ["classify_tool_capability", "select_registry_tool"],
            "status": "covered",
        }, key="requirement")

        def ensure_file(path: str, purpose: str, component: str) -> None:
            for row in new_files:
                if isinstance(row, dict) and str(row.get("path") or "") == path:
                    row.update({"purpose": purpose, "required": True, "component": component})
                    break
            else:
                new_files.append({"path": path, "purpose": purpose, "required": True, "component": component})
            for row in component_file_map:
                if isinstance(row, dict) and str(row.get("component") or "") == component:
                    files = row.setdefault("files", [])
                    if path not in files:
                        files.append(path)
                    row["status"] = "planned"
                    break
            else:
                component_file_map.append({"component": component, "files": [path], "status": "planned"})

        ensure_file(
            "backend/app/services/tool_category_router.py",
            "1차 Intent/Capability 분류: deterministic confidence 우선, 필요할 때만 LLM structured classification",
            "Tool Capability Router (1차)",
        )
        ensure_file(
            "backend/app/services/tool_candidate_selector.py",
            "2차 Tool Registry 후보 선택: schema/capability/risk/permission/enabled 검증 및 ambiguity fallback",
            "Tool Registry Selector (2차)",
        )
        ensure_file(
            "backend/tests/test_two_stage_tool_routing.py",
            "1차/2차 Tool 분류, disabled/risk/permission/confirmation 정책 Regression Test",
            "Tool Registry Selector (2차)",
        )

    return design
