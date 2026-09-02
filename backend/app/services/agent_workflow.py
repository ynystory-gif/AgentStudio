from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from app.core.config import get_settings
from app.services.agent_factory_workflow_design import design_agent_factory
from app.services.as_built_architecture import analyze_as_built_architecture, build_as_built_architecture, compare_architectures
from app.services.approval_service import approval_payload, requires_approval
from app.services.debug_service import analyze_failure
from app.services.git_service import checkpoint
from app.services.local_control import read_file, write_file, run_command
from app.services.codex_app_server_service import codex_app_server_manager
from app.services.patch_service import PatchApplyError, _safe_replacement, _strip_outer_markdown_fence_for_source, apply_patch, create_patch
from app.services.project_analyzer import local_project_summary
from app.services.coding_rule_selector import coding_rules_for_request
from app.services.coding_rule_validator import validate_code_style
from app.services.settings_generator import (
    generate_settings_artifacts,
    validate_settings_artifacts,
)
from app.services.frontend_theme_registry import detect_frontend_theme_target, frontend_theme_generation_instruction


class AgentState(TypedDict, total=False):
    # Workflow identity
    thread_id: str
    project_root: str
    request: str
    provider: str

    # Explicit distinction:
    # AgentStudio 제작 Workflow의 설계 Bundle
    design_bundle: dict
    requirement_coverage_gate: dict
    file_apply_validation: dict
    code_plan_validation: dict
    repair_plan_validation: dict

    # Agent Factory design artifacts
    requirement_spec: dict
    project_analysis: dict
    capability_plan: dict
    tool_mcp_plan: dict
    agent_architecture: dict
    as_built_architecture: dict
    architecture_conformance: dict
    architecture_repair_iteration: int
    database_plan: dict
    target_agent_workflow: dict
    development_stage_plan: dict
    development_workflow: dict
    active_development_stage: dict
    file_plan: dict
    settings_plan: dict
    test_environment_plan: dict
    three_d_agent_plan: dict
    settings_path_normalization: dict
    settings_requirement_spec: dict
    settings_schema: dict
    settings_ui_plan: dict
    settings_generation_result: dict
    settings_validation_result: dict
    build_artifact_validation: dict
    coding_style_context: dict
    environment_plan: dict
    launcher_generation_result: dict
    fastapi_import_validation: dict

    # Existing code context
    target_files: list[str]
    related_files: list[dict]

    # Build / patch
    plan: dict
    checkpoint: dict
    patch_result: list[dict]

    # Runtime validation
    test_command: str
    test_result: dict
    pretest_source_repair: list[dict]
    debug_iteration: int
    debug_history: list[dict]
    validation_fallback: dict

    # Completion
    package_result: dict
    review: str
    status: str
    error: str

    # v5.370 failed-build redevelopment checkpoint routing
    resume_mode: bool
    resume_from_node: str
    resume_run_id: str
    resume_previous_status: str


def _bundle(state: AgentState) -> dict:
    value = state.get("design_bundle")
    return value if isinstance(value, dict) else {}


def _code_documentation_policy(state: AgentState) -> dict:
    """Return the user-selected generated-code documentation policy."""
    raw = (_bundle(state).get("code_documentation") or {}) if isinstance(_bundle(state), dict) else {}
    if not isinstance(raw, dict):
        raw = {}
    return {
        "enabled": bool(raw.get("enabled")),
        "level": str(raw.get("level") or "standard"),
        "preserve_existing_comments": raw.get("preserve_existing_comments", True) is not False,
        "skip_trivial_locals": raw.get("skip_trivial_locals", True) is not False,
    }


def _code_documentation_instruction(state: AgentState) -> str:
    policy = _code_documentation_policy(state)
    if not policy.get("enabled"):
        return ""
    return (
        "\n\n[사용자 선택: 변수·메소드 설명 주석 추가 - 반드시 적용]\n"
        "생성하거나 수정하는 소스에는 유지보수에 도움이 되는 설명 주석을 함께 작성하십시오. "
        "클래스의 역할, 공개 함수/메소드의 목적·주요 파라미터·반환값·중요 예외를 설명하고, "
        "주요 필드/상수/설정 변수에는 값이 무엇을 의미하고 어디에 쓰이는지 설명하십시오. "
        "Python은 docstring과 필요한 # 주석, TypeScript/JavaScript는 JSDoc, C#은 XML documentation, "
        "Java는 Javadoc 등 해당 언어의 표준 문서화 형식을 사용하십시오. "
        "단순 반복문의 index, 임시 문자열처럼 이름만으로 명확한 지역 변수에는 주석을 남발하지 마십시오. "
        "코드를 그대로 한국어로 번역하는 주석보다 왜 필요한지와 역할을 설명하십시오. "
        "기존 파일을 수정할 때 이미 존재하는 유효한 주석/docstring은 삭제하거나 불필요하게 다시 작성하지 마십시오."
    )


USER_CODING_STYLE_DEFAULTS = {
    "meaningful_names": True,
    "uppercase_constants": True,
    "snake_case_functions": True,
    "pascal_case_classes": True,
    "type_hints": True,
    "function_docstrings": True,
    "notebook_single_responsibility": True,
    "refactor_repetition": True,
    "labeled_outputs": True,
    "avoid_magic_numbers": True,
    "staged_data_flow": True,
    "validate_key_results": True,
    "safe_resource_management": True,
    "external_io_validation": True,
    "preserve_source_metadata": True,
    "normalize_external_data": True,
    "prefer_lazy_loading": True,
    "avoid_global_warning_suppression": True,
}


def _user_coding_style_policy(state: AgentState) -> dict:
    """Return the user-selected project code style profile from the design bundle."""
    raw = (_bundle(state).get("user_coding_style") or {}) if isinstance(_bundle(state), dict) else {}
    if not isinstance(raw, dict) or not raw:
        return {"enabled": False, **USER_CODING_STYLE_DEFAULTS}
    return {
        "enabled": raw.get("enabled", True) is not False,
        **{
            key: raw.get(key, default) is not False
            for key, default in USER_CODING_STYLE_DEFAULTS.items()
        },
    }


def _user_coding_style_instruction(state: AgentState) -> str:
    policy = _user_coding_style_policy(state)
    if not policy.get("enabled"):
        return ""

    rules: list[str] = []
    if policy.get("meaningful_names"):
        rules.append("변수·함수·클래스 이름은 역할과 데이터 의미가 드러나게 작성하고 불필요한 축약어를 피하십시오.")
    if policy.get("uppercase_constants"):
        rules.append("Python 등 해당 언어 관례에서 상수는 UPPER_SNAKE_CASE로 구분하고 반복 설정값을 코드 곳곳에 흩어놓지 마십시오.")
    if policy.get("snake_case_functions"):
        rules.append("Python 함수/메소드는 snake_case를 기본으로 하고 외부 Framework 계약이 요구하는 이름은 해당 표준을 우선하십시오.")
    if policy.get("pascal_case_classes"):
        rules.append("클래스/타입 이름은 PascalCase를 기본으로 하고 언어 또는 Framework의 공식 naming convention과 충돌하면 공식 규칙을 우선하십시오.")
    if policy.get("type_hints"):
        rules.append("타입 표현이 가능한 언어에서는 공개 함수/메소드의 파라미터와 반환 타입을 명확히 작성하고 Python에서는 가능한 범위에서 Type Hint를 사용하십시오.")
    if policy.get("function_docstrings") and _code_documentation_policy(state).get("enabled"):
        rules.append("설명 주석 옵션이 켜져 있으므로 공개 함수/메소드에는 해당 언어 표준 Docstring/JSDoc/XML Documentation을 작성하십시오.")
    if policy.get("notebook_single_responsibility"):
        rules.append("Jupyter Notebook을 생성/수정할 때 환경설정, 로딩, 전처리, Chunking, Embedding, Retrieval, Prompt, LLM 호출, 결과 확인처럼 의미가 다른 단계는 가능한 한 한 Cell에 한 역할로 분리하십시오.")
    if policy.get("refactor_repetition"):
        rules.append("동일하거나 유사한 처리 로직이 반복되면 재사용 가능한 함수/메소드/Service로 분리하되 교육용 최소 예제의 흐름 가독성을 해치도록 과도하게 추상화하지 마십시오.")
    if policy.get("labeled_outputs"):
        rules.append("Notebook/CLI의 주요 진행 출력에는 [PDF 로딩], [Chunking], [검색], [LLM]처럼 단계 Label을 사용해 실행 결과의 출처를 쉽게 식별할 수 있게 하십시오.")
    if policy.get("avoid_magic_numbers"):
        rules.append("반복되는 모델명·임계값·Chunk 크기·Top-K·경로·Timeout 등의 Magic Number/String은 상수, Settings 또는 환경설정으로 분리하십시오.")
    if policy.get("staged_data_flow"):
        rules.append("데이터 처리 코드는 설정/상수 → 입력·로딩 → 핵심 처리 → 검증 → 결과 반환·표시 순서가 위에서 아래로 드러나게 구성하고 서로 다른 단계의 책임을 한 블록에 뒤섞지 마십시오.")
    if policy.get("validate_key_results"):
        rules.append("문서 수, 필수 필드, 비어 있지 않은 결과, Shape/Schema 등 다음 단계가 전제로 삼는 핵심 결과는 경계 직후 검증하십시오. 개발·테스트 assert와 운영 Validator/예외 처리를 구분하십시오.")
    if policy.get("safe_resource_management"):
        rules.append("파일·PDF·DB Session·Transaction 등 종료가 필요한 리소스는 with/context manager, yield dependency, try/finally 등 안전한 수명주기로 관리하십시오.")
    if policy.get("external_io_validation"):
        rules.append("외부 HTTP/API/File I/O는 Timeout과 전송 상태를 확인하고 별도 업무 상태 코드가 있으면 함께 검증하십시오. 선택적 API Key/설정 누락은 명시적 Skip/대체 경로로 처리하십시오.")
    if policy.get("preserve_source_metadata"):
        rules.append("RAG·문서 수집·검색 데이터는 page_content만 남기지 말고 source, page/pdf_page, id, date, tags 등 답변 근거와 재추적에 필요한 Metadata를 가능한 범위에서 보존하십시오.")
    if policy.get("normalize_external_data"):
        rules.append("외부 Text/CSV/JSON/OCR 데이터는 Domain Document/Model에 넣기 전에 인코딩, 공백, None/빈 값 등 경계 데이터를 필요한 범위에서 정규화하되 원문의 의미를 바꾸지 마십시오.")
    if policy.get("prefer_lazy_loading"):
        rules.append("대량 문서·CSV·검색 결과처럼 전체 적재가 불필요한 경우 lazy_load/iterator/streaming 기능을 우선 검토하되 작은 데이터에 과도한 복잡성을 추가하지 마십시오.")
    if policy.get("avoid_global_warning_suppression"):
        rules.append("운영 코드에서 warnings.filterwarnings('ignore')처럼 모든 경고를 전역으로 숨기지 마십시오. 필요한 경우 알려진 Warning category와 최소 Scope만 제한하고 원인 해결을 우선하십시오.")

    if not rules:
        return ""
    return (
        "\n\n[사용자 선택: 기본 코딩 스타일 - 반드시 적용]\n"
        + "\n".join(f"{index}. {rule}" for index, rule in enumerate(rules, start=1))
        + "\n기존 프로젝트를 수정할 때는 이미 사용 중인 언어/Framework 표준과 공개 API 계약을 깨지 않는 범위에서 위 규칙을 적용하십시오."
    )


def _nearby_comment(lines: list[str], line_no: int, suffix: str) -> bool:
    """Conservative check for a documentation comment immediately above a symbol."""
    start = max(0, int(line_no or 1) - 6)
    window = "\n".join(lines[start:max(0, int(line_no or 1) - 1)])
    suffix = str(suffix or "").casefold()
    if suffix in {".js", ".jsx", ".ts", ".tsx", ".java"}:
        return "/**" in window or any(row.strip().startswith("//") for row in window.splitlines()[-3:])
    if suffix == ".cs":
        return any(row.strip().startswith("///") for row in window.splitlines()[-4:])
    return False


def _code_documentation_findings(content: str, suffix: str) -> dict:
    """Lightweight language-aware audit used only when the user enabled documentation comments."""
    suffix = str(suffix or "").casefold()
    lines = str(content or "").splitlines()
    missing_symbols: list[dict] = []
    missing_variables: list[dict] = []

    if suffix == ".py":
        try:
            import ast
            tree = ast.parse(content)
        except (SyntaxError, ValueError, TypeError):
            return {"missing_symbols": [], "missing_variables": []}

        def add_symbol(node, kind: str):
            name = str(getattr(node, "name", "") or "")
            if not name or name.startswith("_") or name.startswith("test_"):
                return
            if not ast.get_docstring(node, clean=False):
                missing_symbols.append({"kind": kind, "name": name, "line": int(getattr(node, "lineno", 1) or 1)})

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                add_symbol(node, "class")
                for child in node.body:
                    if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        add_symbol(child, "method")
                    elif isinstance(child, (ast.Assign, ast.AnnAssign)):
                        names = []
                        if isinstance(child, ast.Assign):
                            for target in child.targets:
                                if isinstance(target, ast.Name):
                                    names.append(target.id)
                        elif isinstance(child.target, ast.Name):
                            names.append(child.target.id)
                        for name in names:
                            if name.isupper() and not _python_preceding_comment(lines, int(getattr(child, "lineno", 1) or 1)):
                                missing_variables.append({"kind": "class_constant", "name": name, "line": int(getattr(child, "lineno", 1) or 1)})
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                add_symbol(node, "function")
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                names = []
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            names.append(target.id)
                elif isinstance(node.target, ast.Name):
                    names.append(node.target.id)
                for name in names:
                    if name.isupper() and not _python_preceding_comment(lines, int(getattr(node, "lineno", 1) or 1)):
                        missing_variables.append({"kind": "constant", "name": name, "line": int(getattr(node, "lineno", 1) or 1)})
        return {"missing_symbols": missing_symbols, "missing_variables": missing_variables}

    if suffix in {".js", ".jsx", ".ts", ".tsx"}:
        symbol_patterns = (
            ("function", re.compile(r"^\s*export\s+(?:default\s+)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)")),
            ("class", re.compile(r"^\s*export\s+(?:default\s+)?class\s+([A-Za-z_$][\w$]*)")),
            ("function", re.compile(r"^\s*export\s+const\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>")),
        )
        for index, line in enumerate(lines, 1):
            for kind, pattern in symbol_patterns:
                match = pattern.search(line)
                if match and not _nearby_comment(lines, index, suffix):
                    missing_symbols.append({"kind": kind, "name": match.group(1), "line": index})
            var_match = re.search(r"^\s*export\s+const\s+([A-Z][A-Z0-9_]*)\b", line)
            if var_match and not _nearby_comment(lines, index, suffix):
                missing_variables.append({"kind": "constant", "name": var_match.group(1), "line": index})
        return {"missing_symbols": missing_symbols, "missing_variables": missing_variables}

    if suffix == ".cs":
        for index, line in enumerate(lines, 1):
            class_match = re.search(r"^\s*public\s+(?:sealed\s+|abstract\s+|partial\s+)?class\s+(\w+)", line)
            method_match = re.search(r"^\s*public\s+(?:static\s+|async\s+|virtual\s+|override\s+|sealed\s+|new\s+)*[\w<>,?\[\].]+\s+(\w+)\s*\(", line)
            match = class_match or method_match
            if match and not _nearby_comment(lines, index, suffix):
                missing_symbols.append({"kind": "class" if class_match else "method", "name": match.group(1), "line": index})
        return {"missing_symbols": missing_symbols, "missing_variables": []}

    if suffix == ".java":
        for index, line in enumerate(lines, 1):
            class_match = re.search(r"^\s*public\s+(?:final\s+|abstract\s+)?class\s+(\w+)", line)
            method_match = re.search(r"^\s*public\s+(?:static\s+|final\s+|synchronized\s+)*[\w<>,?\[\].]+\s+(\w+)\s*\(", line)
            match = class_match or method_match
            if match and not _nearby_comment(lines, index, suffix):
                missing_symbols.append({"kind": "class" if class_match else "method", "name": match.group(1), "line": index})
        return {"missing_symbols": missing_symbols, "missing_variables": []}

    return {"missing_symbols": [], "missing_variables": []}


def _python_preceding_comment(lines: list[str], line_no: int) -> bool:
    start = max(0, int(line_no or 1) - 4)
    for row in lines[start:max(0, int(line_no or 1) - 1)]:
        if row.strip().startswith("#"):
            return True
    return False


_RUNTIME_CONTEXT_DIRS = {
    "reports", "debug", "logs", "history", "cache", "temp", "output",
    ".venv", "venv", "node_modules", ".git", "__pycache__",
}


def _is_runtime_artifact_path(project_root: str, raw_path: str) -> bool:
    """AgentStudio 실행/진단 파일이 다음 Code Plan의 수정 대상이 되는 것을 막습니다."""
    if not raw_path:
        return False
    root = Path(project_root).resolve()
    path = Path(str(raw_path)).expanduser()
    try:
        resolved = path.resolve() if path.is_absolute() else (root / path).resolve()
        relative = resolved.relative_to(root)
    except Exception:
        return False
    return any(part.casefold() in _RUNTIME_CONTEXT_DIRS for part in relative.parts[:-1]) or (
        bool(relative.parts) and relative.parts[0].casefold() in _RUNTIME_CONTEXT_DIRS
    )


def _sanitize_context_paths(project_root: str, paths: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for raw in paths or []:
        value = str(raw or "").strip()
        if not value or _is_runtime_artifact_path(project_root, value):
            continue
        key = value.replace("\\", "/").casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def _canonical_planned_path(file_plan: dict, raw_path: str, group: str = "") -> str:
    raw = str(raw_path or "").replace("\\", "/").lstrip("./")
    if not raw:
        return raw

    planned: list[str] = []
    for item in file_plan.get("new_files") or []:
        value = item if isinstance(item, str) else str((item or {}).get("path") or "")
        value = value.replace("\\", "/").lstrip("./")
        if value:
            planned.append(value)

    raw_cf = raw.casefold()
    for candidate in planned:
        if candidate.casefold() == raw_cf:
            return candidate

    # LLM 설계가 app/... 로 반환했어도 File Plan의 backend/app/...가 유일하면 그 경로를 사용합니다.
    suffix_matches = [
        candidate
        for candidate in planned
        if candidate.casefold().endswith("/" + raw_cf)
    ]
    if group == "backend":
        backend_matches = [x for x in suffix_matches if x.casefold().startswith("backend/")]
        if len(backend_matches) == 1:
            return backend_matches[0]
    if len(suffix_matches) == 1:
        return suffix_matches[0]

    if group == "backend" and raw_cf.startswith("app/"):
        return "backend/" + raw
    return raw


def _normalize_settings_plan_paths(plan: dict, file_plan: dict) -> tuple[dict, dict]:
    normalized = dict(plan or {})
    changes: list[dict] = []
    frontend_contract = file_plan.get("frontend_contract") or {}
    frontend_typescript = str(frontend_contract.get("language") or "").casefold() == "typescript"

    def normalize_frontend_extension(raw: str) -> str:
        value = str(raw or "").replace("\\", "/")
        low = value.casefold()
        if frontend_typescript and low.startswith("frontend/src/"):
            if low.endswith(".jsx"):
                return value[:-4] + ".tsx"
            if low.endswith(".js"):
                return value[:-3] + ".ts"
        return value

    for group in ("backend", "frontend"):
        values = dict(normalized.get(group) or {})
        for key, value in list(values.items()):
            if not isinstance(value, str) or not value.strip():
                continue
            source_value = normalize_frontend_extension(value) if group == "frontend" else value
            canonical = _canonical_planned_path(file_plan, source_value, group)
            if canonical != value.replace("\\", "/"):
                changes.append({"group": group, "key": key, "from": value, "to": canonical})
            values[key] = canonical
        normalized[group] = values
    return normalized, {"changed": bool(changes), "changes": changes}


async def requirement_analysis_node(state: AgentState):
    """
    Workflow 설계 단계에서 확정한 design_bundle이 전달되면 그것을 재사용합니다.

    개발 시작 때 짧은 최초 요청만으로 다시 설계하여 React/FastAPI/stdio 등
    인터뷰 확정 요구사항을 잃어버리는 문제를 방지합니다.
    """
    supplied = state.get("design_bundle")

    if isinstance(supplied, dict) and supplied:
        design = supplied
    else:
        design = await design_agent_factory(
            request=state["request"],
            project_context={},
            provider=state.get("provider"),
        )

    return {
        "design_bundle": design,
        "requirement_spec": design.get("requirement_spec") or {},
        "database_plan": design.get("database_plan") or {},
        "development_stage_plan": design.get("development_stage_plan") or {},
        "development_workflow": design.get("development_workflow") or {},
        "active_development_stage": design.get("active_development_stage") or {},
        "test_environment_plan": design.get("test_environment_plan") or {},
        "three_d_agent_plan": design.get("three_d_agent_plan") or {},
        "status": "REQUIREMENTS_ANALYZED",
    }


async def analyze_project_node(state: AgentState):
    explicit_targets = _sanitize_context_paths(
        state["project_root"],
        list(state.get("target_files") or []),
    )
    if explicit_targets:
        related = [
            {
                "path": p,
                "score": 999,
                "matched": ["explicit"],
            }
            for p in explicit_targets
        ]
        analysis = {
            "related_files": related,
            "source": "explicit_target_files",
            "excluded_runtime_artifacts": len(state.get("target_files") or []) - len(explicit_targets),
        }
    else:
        analysis = await local_project_summary(
            state["project_root"],
            state["request"],
        )
        related = list(analysis.get("related_files") or [])

    return {
        "project_analysis": analysis,
        "related_files": related,
        "target_files": [
            x["path"]
            for x in related[:12]
            if isinstance(x, dict) and x.get("path")
        ],
        "status": "PROJECT_ANALYZED",
    }


async def capability_design_node(state: AgentState):
    value = _bundle(state).get("capability_plan") or {}

    return {
        "capability_plan": value,
        "status": "CAPABILITIES_DESIGNED",
    }


async def tool_mcp_decision_node(state: AgentState):
    value = _bundle(state).get("tool_mcp_plan") or {
        "decisions": []
    }

    return {
        "tool_mcp_plan": value,
        "status": "TOOL_MCP_DECIDED",
    }


async def agent_architecture_node(state: AgentState):
    value = _bundle(state).get("agent_architecture") or {}

    return {
        "agent_architecture": value,
        "status": "AGENT_ARCHITECTURE_DESIGNED",
    }


async def database_design_node(state: AgentState):
    """사용자가 Workflow 화면에서 확인/확정한 DB Module 설계를 개발 State에 고정합니다."""
    value = _bundle(state).get("database_plan") or state.get("database_plan") or {}
    return {"database_plan": value, "status": "DATABASE_DESIGNED"}


async def target_workflow_design_node(state: AgentState):
    """
    생성 대상 Agent의 실제 업무 Workflow입니다.

    이 State는 AgentStudio 자체 제작 Graph와 별개입니다.
    """
    value = _bundle(state).get("target_agent_workflow") or {
        "name": "Generated Agent Workflow",
        "steps": [],
        "branches": [],
        "retry_policy": [],
        "failure_policy": [],
    }

    return {
        "target_agent_workflow": value,
        "status": "TARGET_WORKFLOW_DESIGNED",
    }


async def as_built_architecture_node(state: AgentState):
    """생성된 실제 소스를 역분석해 As-Built Architecture를 만듭니다.

    v5.345: 재작업에서는 변경 영향이 없으면 이전 As-Built semantic review를
    재사용하고, 구조와 무관한 부분 변경이면 deterministic scan만 다시 수행합니다.
    """
    revision = _incremental_revision_info(state)
    mode = str(revision.get("mode") or "")
    affected = {str(x or "") for x in revision.get("affected_sections") or []}
    previous_state = (_bundle(state).get("previous_build_state") or {}) if isinstance(_bundle(state), dict) else {}
    previous_as_built = previous_state.get("as_built_architecture") or {}

    try:
        if mode == "FULL_REUSE" and previous_as_built:
            current = build_as_built_architecture(
                project_root=state["project_root"],
                design_architecture=state.get("agent_architecture") or {},
                file_plan=state.get("file_plan") or {},
            )
            if (
                str(current.get("source_fingerprint") or "")
                and str(current.get("source_fingerprint") or "") == str(previous_as_built.get("source_fingerprint") or "")
            ):
                value = json.loads(json.dumps(previous_as_built, ensure_ascii=False))
                value["analysis_mode"] = "incremental_full_reuse_no_llm"
                value["incremental_reused"] = True
                value["scan"] = current.get("scan") or value.get("scan") or {}
                value["source_fingerprint"] = current.get("source_fingerprint")
                return {
                    "as_built_architecture": value,
                    "status": "AS_BUILT_ARCHITECTURE_ANALYZED",
                }

        structural_sections = {"agent_architecture", "target_agent_workflow", "database_plan", "tool_mcp_plan"}
        if mode == "PARTIAL_REVISE" and not structural_sections.intersection(affected):
            value = build_as_built_architecture(
                project_root=state["project_root"],
                design_architecture=state.get("agent_architecture") or {},
                file_plan=state.get("file_plan") or {},
            )
            value["analysis_mode"] = "incremental_static_scan_no_llm"
            value["analysis_provider"] = "not_required"
        else:
            value = await analyze_as_built_architecture(
                project_root=state["project_root"],
                design_architecture=state.get("agent_architecture") or {},
                file_plan=state.get("file_plan") or {},
                provider=state.get("provider"),
            )
    except Exception as exc:
        return {
            "as_built_architecture": {
                "project_root": state.get("project_root") or "",
                "components": [],
                "interfaces": [],
                "persistence": [],
                "security": [],
                "state": [],
                "error": f"{type(exc).__name__}: {exc}",
            },
            "status": "AS_BUILT_ARCHITECTURE_FAILED",
            "error": f"As-Built Architecture 분석 실패: {type(exc).__name__}: {exc}",
        }

    return {
        "as_built_architecture": value,
        "status": "AS_BUILT_ARCHITECTURE_ANALYZED",
    }


async def architecture_conformance_node(state: AgentState):
    """Design Architecture와 실제 구현을 비교하고 자동 보정 여부를 결정합니다."""
    if state.get("status") != "AS_BUILT_ARCHITECTURE_ANALYZED":
        return {
            "architecture_conformance": {
                "ok": False,
                "score": 0,
                "status": "ERROR",
                "mismatches": [],
                "error": "As-Built Architecture 분석이 완료되지 않았습니다.",
            },
            "status": "ARCHITECTURE_CONFORMANCE_FAILED",
        }

    conformance = compare_architectures(
        state.get("agent_architecture") or {},
        state.get("as_built_architecture") or {},
        state.get("file_plan") or {},
    )
    iteration = int(state.get("architecture_repair_iteration") or 0)
    conformance["repair_iteration"] = iteration
    conformance["analysis_provider"] = (state.get("as_built_architecture") or {}).get("analysis_provider") or ""

    if conformance.get("ok"):
        return {
            "architecture_conformance": conformance,
            "status": "ARCHITECTURE_CONFORMANCE_PASSED",
            "error": "",
        }

    if iteration < 2:
        return {
            "architecture_conformance": conformance,
            "status": "ARCHITECTURE_REPAIR_READY",
            "error": "",
        }

    return {
        "architecture_conformance": conformance,
        "status": "ARCHITECTURE_CONFORMANCE_FAILED",
        "error": (
            "Design Architecture와 실제 구현의 핵심 차이가 자동 보정 2회 후에도 남아 있습니다. "
            "아키텍처 탭의 차이점을 확인하십시오."
        ),
    }


def route_after_architecture_conformance(
    state: AgentState,
) -> Literal["environment_configuration", "code_generation", "end"]:
    if state.get("status") == "ARCHITECTURE_CONFORMANCE_PASSED":
        return "environment_configuration"
    if state.get("status") == "ARCHITECTURE_REPAIR_READY":
        return "code_generation"
    return "end"


def _append_planned_file(
    value: dict,
    path: str,
    purpose: str,
    component: str,
    required: bool = True,
) -> None:
    rows = value.setdefault("new_files", [])
    existing = {
        str(
            item.get("path") if isinstance(item, dict) else item
        ).replace("\\", "/").casefold()
        for item in rows
    }

    normalized = path.replace("\\", "/").casefold()
    if normalized not in existing:
        rows.append({
            "path": path,
            "purpose": purpose,
            "required": bool(required),
            "component": component,
        })


def _map_component_file(
    value: dict,
    component: str,
    paths: list[str],
) -> None:
    rows = value.setdefault("component_file_map", [])
    target = component.casefold()
    for item in rows:
        if not isinstance(item, dict):
            continue
        if str(item.get("component") or "").casefold() != target:
            continue
        merged = []
        seen = set()
        for raw in list(item.get("files") or []) + list(paths or []):
            path = str(raw or "").replace("\\", "/")
            key = path.casefold()
            if path and key not in seen:
                merged.append(path)
                seen.add(key)
        item["files"] = merged
        item.setdefault("status", "planned")
        return

    rows.append({
        "component": component,
        "files": list(paths or []),
        "status": "planned",
    })



def _normalize_react_frontend_plan_extensions(value: dict, *, typescript: bool) -> dict:
    """React Frontend의 언어 계약에 맞춰 src 경로 확장자를 결정적으로 정규화합니다.

    React + TypeScript가 확정된 Agent에서 LLM이 App.jsx/main.jsx/api.js를 제안하더라도
    실제 File Plan에는 .tsx/.ts만 남깁니다. JavaScript React는 반대로 기존 확장자를 유지합니다.
    """
    if not typescript:
        return value

    def convert(raw: str) -> str:
        path = str(raw or "").replace("\\", "/")
        low = path.casefold()
        if low.startswith("frontend/src/"):
            # React/Vite의 표준 entry 파일은 운영체제와 무관하게 canonical casing을 유지합니다.
            # Windows에서는 app.tsx/App.tsx가 같은 파일처럼 보이지만 Linux CI/Vercel에서는
            # 서로 다른 경로이므로 File Plan 단계에서부터 App.tsx로 고정합니다.
            if low in {"frontend/src/app.jsx", "frontend/src/app.tsx"}:
                return "frontend/src/App.tsx"
            if low in {"frontend/src/main.jsx", "frontend/src/main.tsx"}:
                return "frontend/src/main.tsx"
            if low in {"frontend/src/services/api.js", "frontend/src/services/api.ts"}:
                return "frontend/src/services/api.ts"
            if low.endswith(".jsx"):
                return path[:-4] + ".tsx"
            if low.endswith(".js"):
                return path[:-3] + ".ts"
        return path

    normalized_rows = []
    seen = set()
    for item in value.get("new_files") or []:
        if isinstance(item, str):
            converted = convert(item)
            key = converted.casefold()
            if key not in seen:
                normalized_rows.append(converted)
                seen.add(key)
            continue
        if not isinstance(item, dict):
            continue
        row = dict(item)
        row["path"] = convert(row.get("path") or "")
        key = str(row.get("path") or "").casefold()
        if key and key not in seen:
            normalized_rows.append(row)
            seen.add(key)
    value["new_files"] = normalized_rows

    normalized_map = []
    for item in value.get("component_file_map") or []:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        row["files"] = [convert(x) for x in row.get("files") or []]
        normalized_map.append(row)
    value["component_file_map"] = normalized_map
    return value


def _cleanup_react_typescript_legacy_sources(state: AgentState) -> dict:
    """React + TypeScript 확정 Agent에 남은 legacy JS/JSX entry를 결정적으로 제거합니다.

    LLM Repair가 금지 파일을 빈 파일로 덮어쓰는 것만으로는 ``Path.is_file()`` 기반
    Architecture Validator를 통과할 수 없습니다. 또한 빈 App.jsx/main.jsx/api.js가 남으면
    Vite/IDE가 잘못된 entry를 잡거나 사용자가 중복 구현으로 오해할 수 있습니다.

    따라서 TypeScript 계약이 확정된 경우 AgentStudio가 LLM에 삭제를 맡기지 않고
    정확히 알려진 legacy entry 세 개를 직접 삭제합니다. 이 처리는 idempotent하며
    ``frontend/src``의 다른 JavaScript 설정/라이브러리 파일은 건드리지 않습니다.
    """
    contracts = _requirement_contracts(state)
    if not contracts.get("react_typescript"):
        return {"ok": True, "patch_rows": [], "removed": []}

    root = Path(state["project_root"]).resolve()
    legacy_paths = (
        "frontend/src/App.jsx",
        "frontend/src/main.jsx",
        "frontend/src/services/api.js",
    )
    rows: list[dict] = []
    removed: list[str] = []

    for relative in legacy_paths:
        target = (root / relative).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            continue
        if not target.is_file():
            continue
        try:
            previous_bytes = target.stat().st_size
            target.unlink(missing_ok=True)
        except OSError as exc:
            return {
                "ok": False,
                "patch_rows": rows,
                "removed": removed,
                "error": f"{type(exc).__name__}: {exc}",
                "path": str(target),
            }
        if target.exists():
            return {
                "ok": False,
                "patch_rows": rows,
                "removed": removed,
                "error": "legacy React JavaScript entry 삭제 후 파일이 남아 있습니다.",
                "path": str(target),
            }
        removed.append(relative)
        rows.append({
            "path": str(target),
            "changed": True,
            "deleted": True,
            "verified": True,
            "bytes": 0,
            "previous_bytes": previous_bytes,
            "reason": (
                "React + TypeScript 확정 요구와 충돌하는 legacy JavaScript/JSX entry를 "
                "AgentStudio가 결정적으로 제거했습니다."
            ),
            "replacement_strategies": ["delete_legacy_react_javascript_entry"],
        })

    return {"ok": True, "patch_rows": rows, "removed": removed}


def _react_frontend_minimum_files(*, typescript: bool) -> list[tuple[str, str]]:
    """생성 Agent React UI를 App 한 파일에 몰아넣지 않는 최소 분리 구조입니다."""
    ext = "tsx" if typescript else "jsx"
    service_ext = "ts" if typescript else "js"
    rows = [
        ("frontend/package.json", "React/Vite 실행, build, typecheck scripts와 의존성"),
        ("frontend/index.html", "Vite HTML entrypoint"),
        (f"frontend/src/main.{ext}", "React Application bootstrap만 담당"),
        (f"frontend/src/App.{ext}", "최상위 Route/Page 조립만 담당하며 대형 UI 구현 금지"),
        (f"frontend/src/layouts/AppLayout.{ext}", "Top/Sidebar/Main/Footer를 조립하는 공통 Layout"),
        (f"frontend/src/components/layout/TopHeader.{ext}", "상단 헤더/전역 액션 영역"),
        (f"frontend/src/components/layout/Sidebar.{ext}", "좌측 메뉴/Navigation 영역"),
        (f"frontend/src/components/layout/Footer.{ext}", "하단 Footer/상태 영역"),
        (f"frontend/src/pages/HomePage.{ext}", "기본 본문 Page; 업무별 Page는 pages 아래 추가 분리"),
        (f"frontend/src/services/api.{service_ext}", "FastAPI API Client와 통신 함수"),
        ("frontend/src/styles/global.css", "전역 Layout/Theme 스타일; Page/Component 전용 스타일과 분리"),
    ]
    if typescript:
        rows.extend([
            ("frontend/tsconfig.json", "React TypeScript compiler 설정"),
            ("frontend/vite.config.ts", "Vite React TypeScript build 설정"),
            ("frontend/src/types/index.ts", "공통 API/Domain Type 정의"),
        ])
    return rows


def _ensure_minimum_agent_file_plan(
    value: dict,
    request: str,
    design_bundle: dict,
) -> dict:
    """
    LLM file_plan이 지나치게 축약되어도 설계된 Agent가 실행 가능한
    애플리케이션 단위 산출물을 갖도록 최소 artifact manifest를 보강합니다.
    """
    text = (
        request
        + "\n"
        + json.dumps(design_bundle or {}, ensure_ascii=False)
    ).casefold()

    is_fastapi = "fastapi" in text
    is_react = "react" in text or "vite" in text
    is_react_typescript = is_react and any(
        token in text
        for token in (
            "typescript", "type script", "타입스크립트", "타입 스크립트", ".tsx", "react+ts", "react + ts"
        )
    )
    frontend_target = detect_frontend_theme_target(text)
    frontend_target_id = str(frontend_target.get("id") or "generic_web")
    has_frontend = frontend_target_id != "generic_web" or any(token in text for token in (
        "frontend", "front-end", "프론트", "web ui", "웹 ui", "웹앱", "관리자 화면", "대시보드"
    ))
    has_mcp = "mcp" in text

    # LLM이 React + TypeScript 요구를 App.jsx 같은 JS 경로로 제안해도
    # Code Generation 전에 File Plan 자체를 TS 계약으로 정규화합니다.
    value = _normalize_react_frontend_plan_extensions(
        value,
        typescript=is_react_typescript,
    )
    needs_settings = bool(
        (design_bundle.get("settings_plan") or {}).get("enabled")
    )

    _append_planned_file(
        value,
        "README.md",
        "설치, 설정, 실행, 테스트 방법과 Agent Workflow 설명",
        "documentation",
    )
    _append_planned_file(
        value,
        ".env.example",
        "실제 Secret 없이 필요한 환경변수 Key와 안전한 예시 제공",
        "configuration",
    )

    # v5.172: 생성 Agent는 SYSTEM_ADMIN.cmd 하나로 실행할 수 있어야 합니다.
    # v5.174: Generated Agent FastAPI import contract + v5.173 UTF-8 BOM launcher contract.
    # Launcher 내용은 package_completion에서 AgentStudio가 결정적으로 생성합니다.
    _append_planned_file(
        value,
        "SYSTEM_ADMIN.cmd",
        "사용자 단일 실행 진입점 — UTF-8 설정 후 SYSTEM_ADMIN.ps1을 호출",
        "system administration",
        required=False,
    )
    _append_planned_file(
        value,
        "SYSTEM_ADMIN.ps1",
        "가상환경/의존성/Backend/Frontend/MCP 준비를 자동 관리하는 실행 스크립트",
        "system administration",
        required=False,
    )
    _map_component_file(
        value,
        "System Administration",
        ["SYSTEM_ADMIN.cmd", "SYSTEM_ADMIN.ps1"],
    )

    if is_fastapi:
        backend_files = [
            ("backend/app/main.py", "FastAPI Application entrypoint와 Router 등록"),
            ("backend/app/routers/summary.py", "파일 요약 HTTP API 경계"),
            ("backend/app/schemas/summary.py", "요약 Request/Response Pydantic Schema"),
            ("backend/app/services/summary_service.py", "요약 Use Case orchestration"),
            ("backend/app/services/llm_service.py", "OpenAI/Ollama Provider 추상화와 실제 LLM 호출"),
            ("backend/app/core/config.py", "환경변수 기반 Runtime 설정"),
            ("backend/requirements.txt", "Backend 실행 의존성"),
            ("backend/tests/test_summary_api.py", "요약 API 핵심 계약 테스트"),
        ]
        for path, purpose in backend_files:
            _append_planned_file(value, path, purpose, "backend")
        _map_component_file(
            value,
            "FastAPI Backend",
            [x[0] for x in backend_files],
        )

    if has_mcp:
        mcp_files = [
            ("backend/app/mcp/client.py", "MCP Client 요청과 응답 처리"),
            ("backend/app/mcp/transport.py", "stdio 기본 및 Streamable HTTP 확장 가능한 Transport 추상화"),
            ("mcp_server/server.py", "로컬 MCP Server entrypoint"),
            ("mcp_server/tools/file_reader.py", "Root/확장자 검증 후 파일을 읽는 MCP Tool"),
            ("backend/tests/test_mcp_file_reader.py", "Root 탈출/확장자/MCP 파일 읽기 계약 테스트"),
        ]
        for path, purpose in mcp_files:
            _append_planned_file(value, path, purpose, "mcp")
        _map_component_file(
            value,
            "MCP File Access",
            [x[0] for x in mcp_files],
        )

    if is_react:
        frontend_files = _react_frontend_minimum_files(
            typescript=is_react_typescript,
        )
        for path, purpose in frontend_files:
            _append_planned_file(value, path, purpose, "frontend")
        _map_component_file(
            value,
            "React Frontend",
            [x[0] for x in frontend_files],
        )
        value["frontend_contract"] = {
            "framework": "React",
            "build_tool": "Vite",
            "language": "TypeScript" if is_react_typescript else "JavaScript",
            "app_entry": (
                "frontend/src/App.tsx" if is_react_typescript else "frontend/src/App.jsx"
            ),
            "modular_layout_required": True,
            "app_max_lines": 220,
            "required_layers": [
                "layouts", "components/layout", "pages", "services", "styles"
            ] + (["types"] if is_react_typescript else []),
        }

    elif has_frontend:
        value["frontend_contract"] = {
            "framework": str(frontend_target.get("label") or "Generic Web Frontend"),
            "target_id": frontend_target_id,
            "language": str(frontend_target.get("language") or "Framework dependent"),
            "theme_strategy": str(frontend_target.get("strategy") or "Canonical Design Token adapter"),
            "theme_adapter_required": True,
            "modular_layout_required": True,
            "required_layers": ["layout/navigation", "pages/views", "services/api", "theme/styles"],
        }

    if needs_settings:
        settings_plan = design_bundle.get("settings_plan") or {}
        for group in ("backend", "frontend"):
            for _, relative in (settings_plan.get(group) or {}).items():
                if isinstance(relative, str) and relative.strip():
                    path = relative.replace("\\", "/")
                    if group == "backend" and not path.startswith("backend/"):
                        path = "backend/" + path.lstrip("/")
                    _append_planned_file(
                        value,
                        path,
                        "Settings Generator가 관리하는 설정 구성요소",
                        "settings",
                    )


    test_environment_plan = design_bundle.get("test_environment_plan") or {}
    if test_environment_plan.get("enabled"):
        test_files: list[str] = []
        backend_plan = test_environment_plan.get("backend") or {}
        for key in ("schema", "service", "router"):
            path = str(backend_plan.get(key) or "").replace("\\", "/").strip()
            if path:
                _append_planned_file(
                    value,
                    path,
                    "DEV/TEST 전용 Seed Data·권한별 테스트 계정·초기화·사용자 전환 관리",
                    "test environment",
                )
                test_files.append(path)

        for raw in test_environment_plan.get("tests") or []:
            path = str(raw or "").replace("\\", "/").strip()
            if path:
                _append_planned_file(
                    value,
                    path,
                    "테스트 데이터 격리·Role/Permission·production 거부·impersonation 계약 테스트",
                    "test environment",
                )
                test_files.append(path)

        frontend_plan = test_environment_plan.get("frontend") or {}
        for key in ("page", "api_client"):
            path = str(frontend_plan.get(key) or "").replace("\\", "/").strip()
            if path and has_frontend:
                _append_planned_file(
                    value,
                    path,
                    "관리자 테스트 환경 UI/API — Seed 현황, 권한별 계정, Test-as-user, 시나리오 실행",
                    "test environment",
                )
                test_files.append(path)

        if test_files:
            _map_component_file(value, "Generated Agent Test Environment", test_files)


    database_plan = design_bundle.get("database_plan") or {}
    if database_plan.get("enabled"):
        migration_paths = []
        for item in database_plan.get("migration_files") or []:
            path = str((item or {}).get("path") or "").replace("\\", "/").strip()
            if not path:
                continue
            migration_paths.append(path)
            _append_planned_file(
                value,
                path,
                str((item or {}).get("purpose") or "확정된 PostgreSQL DB Migration"),
                "database",
                required=False,
            )
        if migration_paths:
            _map_component_file(value, "Database Migration", migration_paths)

    return value


async def project_file_plan_node(state: AgentState):
    bundle = _bundle(state)
    value = dict(bundle.get("file_plan") or {})

    existing = _sanitize_context_paths(
        state["project_root"],
        list(
            value.get("existing_files_to_modify")
            or state.get("target_files")
            or []
        ),
    )

    value["existing_files_to_modify"] = existing
    value.setdefault("new_files", [])
    value.setdefault("component_file_map", [])

    value = _ensure_minimum_agent_file_plan(
        value=value,
        request=state["request"],
        design_bundle=bundle,
    )

    development_workflow = bundle.get("development_workflow") or state.get("development_workflow") or {}
    development_stages = development_workflow.get("stages") if isinstance(development_workflow, dict) else []
    if development_stages:
        first_stage = development_stages[0]
        for row in value.get("new_files") or []:
            if isinstance(row, dict) and not row.get("development_stage_id"):
                row["development_stage_id"] = first_stage.get("id") or "STAGE_1"
                row["development_stage_order"] = int(first_stage.get("order") or 1)

    coding_style = coding_rules_for_request(
        request=state["request"],
        project_scope=True,
    )

    return {
        "file_plan": value,
        "coding_style_context": coding_style,
        "status": "FILE_PLAN_READY",
    }



def _normalized_file_plan_paths(file_plan: dict) -> set[str]:
    result: set[str] = set()

    for item in file_plan.get("new_files") or []:
        if isinstance(item, str):
            path = item
        elif isinstance(item, dict):
            path = str(item.get("path") or "")
        else:
            continue

        value = path.replace("\\", "/").strip().casefold()
        if value:
            result.add(value)

    return result


def _requirement_contracts(state: AgentState) -> dict:
    """
    최초 한 문장뿐 아니라 Workflow Preview가 보존한 인터뷰 전체 문맥,
    confirmed requirements, design bundle을 모두 검사합니다.
    """
    bundle = state.get("design_bundle") or {}
    payload = (
        str(state.get("request") or "")
        + "\n"
        + str(bundle.get("full_request") or "")
        + "\n"
        + str(bundle.get("interview_context") or "")
        + "\n"
        + json.dumps(
            bundle,
            ensure_ascii=False,
        )
    ).casefold()

    frontend_target = detect_frontend_theme_target(payload)
    frontend_target_id = str(frontend_target.get("id") or "generic_web")
    frontend_present = frontend_target_id != "generic_web" or any(token in payload for token in (
        "frontend", "front-end", "프론트", "web ui", "웹 ui", "웹앱", "streamlit", "gradio", "nicegui",
        "blazor", "flutter", "react native", "vue", "angular", "svelte", "astro", "html", "css"
    ))

    return {
        "frontend": frontend_present,
        "frontend_target": frontend_target,
        "fastapi": (
            "fastapi" in payload
            or "uvicorn" in payload
        ),
        "react": (
            "react" in payload
            or "vite" in payload
        ),
        "react_typescript": (
            ("react" in payload or "vite" in payload)
            and any(
                token in payload
                for token in (
                    "typescript", "type script", "타입스크립트", "타입 스크립트",
                    ".tsx", "react+ts", "react + ts"
                )
            )
        ),
        "mcp": "mcp" in payload,
        "stdio": (
            "stdio" in payload
            or "standard input" in payload
            or "표준 입출력" in payload
        ),
        "ollama_switch": "ollama" in payload,
        "gpt_4o_mini": "gpt-4o-mini" in payload,
        "file_limit_10mb": (
            "10mb" in payload
            or "10 mb" in payload
        ),
        "timeout_120s": (
            "120초" in payload
            or "120 second" in payload
            or "120s" in payload
        ),
        "chunking": (
            "chunk" in payload
            or "청크" in payload
        ),
        "no_database": (
            "db 사용하지" in payload
            or "데이터베이스를 사용하지" in payload
            or '"database": {"enabled": false' in payload
        ),
    }


def _enrich_file_plan_from_contracts(
    state: AgentState,
    file_plan: dict,
) -> dict:
    """
    확정 요구사항을 File Plan 설명에 보강합니다.
    자연어 purpose의 특정 단어 유무는 Coverage 실패 조건으로 사용하지 않습니다.
    """
    contracts = _requirement_contracts(state)
    result = json.loads(
        json.dumps(
            file_plan or {},
            ensure_ascii=False,
        )
    )

    for item in result.get("new_files") or []:
        if not isinstance(item, dict):
            continue

        path = str(item.get("path") or "").replace("\\", "/").casefold()
        purpose = str(item.get("purpose") or "").strip()

        if path == "backend/app/mcp/transport.py" and contracts["stdio"]:
            if "stdio" not in purpose.casefold():
                item["purpose"] = (
                    (purpose + " — ") if purpose else ""
                ) + "로컬 stdio를 기본 Transport로 사용하고 확장 가능한 Transport 계층을 구현"

        if path == "backend/app/services/llm_service.py":
            additions = []
            if contracts["gpt_4o_mini"]:
                additions.append("기본 OpenAI gpt-4o-mini")
            if contracts["ollama_switch"]:
                additions.append("Ollama 전환 가능")
            if additions:
                item["purpose"] = (
                    (purpose + " — ") if purpose else ""
                ) + ", ".join(additions)

        if path == "backend/app/core/config.py":
            additions = []
            if contracts["file_limit_10mb"]:
                additions.append("기본 최대 파일 크기 10MB")
            if contracts["timeout_120s"]:
                additions.append("기본 처리 타임아웃 120초")
            if additions:
                item["purpose"] = (
                    (purpose + " — ") if purpose else ""
                ) + ", ".join(additions)

    return result


async def requirement_coverage_gate_node(state: AgentState):
    """
    File Plan의 필수 구조를 검사합니다.

    confirmed requirements가 source of truth이며,
    purpose 문자열에 특정 단어가 없다는 이유만으로 개발을 중단하지 않습니다.
    """
    contracts = _requirement_contracts(state)

    enriched_plan = _enrich_file_plan_from_contracts(
        state,
        state.get("file_plan") or {},
    )

    paths = _normalized_file_plan_paths(enriched_plan)
    missing: list[str] = []
    warnings: list[str] = []

    def require(path: str, reason: str):
        if path.casefold() not in paths:
            missing.append(f"{path} — {reason}")

    require("SYSTEM_ADMIN.cmd", "사용자 단일 실행 진입점")
    require("SYSTEM_ADMIN.ps1", "Windows 실행 관리자 스크립트")

    if contracts["fastapi"]:
        require("backend/app/main.py", "FastAPI Backend entrypoint")
        require("backend/app/routers/summary.py", "FastAPI 요약 API Router")
        require("backend/app/schemas/summary.py", "FastAPI Request/Response Schema")
        require("backend/app/services/summary_service.py", "Backend Service 계층")
        require("backend/app/services/llm_service.py", "LLM Provider Service 계층")
        require("backend/app/core/config.py", "환경/Provider 설정 중앙화")

    if contracts["react"]:
        ext = "tsx" if contracts["react_typescript"] else "jsx"
        service_ext = "ts" if contracts["react_typescript"] else "js"
        require("frontend/package.json", "React/Vite Frontend 의존성 및 scripts")
        require("frontend/index.html", "Vite HTML entrypoint")
        require(f"frontend/src/main.{ext}", "React bootstrap")
        require(f"frontend/src/app.{ext}", "React 최상위 조립")
        require(f"frontend/src/layouts/applayout.{ext}", "공통 Layout 분리")
        require(f"frontend/src/components/layout/topheader.{ext}", "Top Header 분리")
        require(f"frontend/src/components/layout/sidebar.{ext}", "좌측 Navigation 분리")
        require(f"frontend/src/components/layout/footer.{ext}", "Footer 분리")
        require(f"frontend/src/pages/homepage.{ext}", "본문 Page 분리")
        require(f"frontend/src/services/api.{service_ext}", "FastAPI API Client")
        require("frontend/src/styles/global.css", "전역 Layout 스타일")
        if contracts["react_typescript"]:
            require("frontend/tsconfig.json", "TypeScript compiler 설정")
            require("frontend/vite.config.ts", "Vite TypeScript 설정")
            require("frontend/src/types/index.ts", "공통 Type 정의")
            forbidden_ts_paths = {
                "frontend/src/main.jsx",
                "frontend/src/app.jsx",
                "frontend/src/services/api.js",
            }
            conflicting = sorted(paths & forbidden_ts_paths)
            if conflicting:
                missing.append(
                    "React + TypeScript 요구에 JavaScript/JSX 경로가 포함되어 있습니다: "
                    + ", ".join(conflicting)
                )

    if contracts["mcp"]:
        require("backend/app/mcp/client.py", "MCP Client")
        require("backend/app/mcp/transport.py", "분리된 MCP Transport 계층")
        require("mcp_server/server.py", "MCP Server entrypoint")
        require("mcp_server/tools/file_reader.py", "파일 읽기 MCP Tool")

    if contracts["mcp"] and contracts["stdio"]:
        if "backend/app/mcp/transport.py" in paths:
            warnings.append(
                "MCP Transport는 confirmed stdio 계약을 기준으로 Code/Architecture 단계에서 검증합니다."
            )

    result = {
        "ok": not missing,
        "contracts": contracts,
        "planned_file_count": len(paths),
        "missing_requirements": missing,
        "warnings": warnings,
        "validation_mode": "STRUCTURE_FIRST",
    }

    return {
        "file_plan": enriched_plan,
        "requirement_coverage_gate": result,
        "status": (
            "REQUIREMENT_COVERAGE_VALIDATED"
            if result["ok"]
            else "REQUIREMENT_COVERAGE_FAILED"
        ),
        "error": (
            ""
            if result["ok"]
            else "확정 요구사항의 필수 구조가 File Plan에 모두 반영되지 않았습니다."
        ),
    }


def route_after_requirement_coverage(
    state: AgentState,
) -> Literal["settings_requirement_analysis", "end"]:
    return (
        "settings_requirement_analysis"
        if state.get("status")
        == "REQUIREMENT_COVERAGE_VALIDATED"
        else "end"
    )


async def settings_requirement_analysis_node(state: AgentState):
    raw_plan = dict(_bundle(state).get("settings_plan") or {})
    plan, path_normalization = _normalize_settings_plan_paths(
        raw_plan,
        state.get("file_plan") or {},
    )
    categories = list(plan.get("categories") or [])

    requirement_spec = {
        "enabled": bool(plan.get("enabled")),
        "reason": plan.get("reason") or "",
        "categories": [
            {
                "id": item.get("id"),
                "label": item.get("label"),
                "field_count": len(item.get("fields") or []),
            }
            for item in categories
            if isinstance(item, dict)
        ],
    }

    return {
        "settings_plan": plan,
        "settings_path_normalization": path_normalization,
        "settings_requirement_spec": requirement_spec,
        "status": "SETTINGS_REQUIREMENTS_ANALYZED",
    }


async def settings_schema_design_node(state: AgentState):
    plan = state.get("settings_plan") or {}
    fields = []

    for category in plan.get("categories") or []:
        if not isinstance(category, dict):
            continue

        for field in category.get("fields") or []:
            if not isinstance(field, dict):
                continue

            fields.append({
                **field,
                "category_id": category.get("id"),
                "category_label": category.get("label"),
            })

    schema = {
        "enabled": bool(plan.get("enabled")),
        "fields": fields,
        "secret_fields": [
            item.get("key")
            for item in fields
            if item.get("secret")
        ],
        "backend": plan.get("backend") or {},
        "security": plan.get("security") or {},
    }

    return {
        "settings_schema": schema,
        "status": "SETTINGS_SCHEMA_DESIGNED",
    }


async def settings_ui_design_node(state: AgentState):
    plan = state.get("settings_plan") or {}

    ui_plan = {
        "enabled": bool(plan.get("enabled")),
        "categories": [
            {
                "id": item.get("id"),
                "label": item.get("label"),
                "controls": [
                    {
                        "key": field.get("key"),
                        "label": field.get("label"),
                        "type": field.get("type"),
                        "secret": bool(field.get("secret")),
                        "options": field.get("options") or [],
                    }
                    for field in item.get("fields") or []
                    if isinstance(field, dict)
                ],
            }
            for item in plan.get("categories") or []
            if isinstance(item, dict)
        ],
        "frontend": plan.get("frontend") or {},
    }

    return {
        "settings_ui_plan": ui_plan,
        "status": "SETTINGS_UI_DESIGNED",
    }


async def checkpoint_node(state: AgentState):
    cp = await checkpoint(state["project_root"])

    return {
        "checkpoint": cp,
        "status": "CHECKPOINTED",
    }


async def approval_node(state: AgentState):
    capability = "agent_factory_build"

    if requires_approval(
        risk_level=1,
        capability=capability,
        server_trust_level="SYSTEM",
        allow_read_without_prompt=True,
        allow_write_without_prompt=True,
    ):
        decision = interrupt(
            approval_payload(
                action="BUILD_AGENT_PROGRAM",
                summary=(
                    "AgentStudio가 분석한 설계와 파일 계획을 기준으로 "
                    "프로젝트 코드를 생성/수정합니다."
                ),
                risk_level=1,
                capability=capability,
                server_trust_level="SYSTEM",
                payload={
                    "requirement_spec": state.get("requirement_spec", {}),
                    "capability_plan": state.get("capability_plan", {}),
                    "tool_mcp_plan": state.get("tool_mcp_plan", {}),
                    "agent_architecture": state.get("agent_architecture", {}),
                    "target_agent_workflow": state.get(
                        "target_agent_workflow",
                        {},
                    ),
                    "file_plan": state.get("file_plan", {}),
                    "settings_plan": state.get("settings_plan", {}),
                    "three_d_agent_plan": state.get("three_d_agent_plan", {}) or _bundle(state).get("three_d_agent_plan", {}),
                },
            )
        )

        if isinstance(decision, dict):
            decision = decision.get("decision")

        if decision != "approve":
            return {"status": "REJECTED"}

    return {"status": "APPROVED"}


def route_after_approval(
    state: AgentState,
) -> Literal["code_generation", "end"]:
    return (
        "code_generation"
        if state.get("status") == "APPROVED"
        else "end"
    )


async def _read_existing_context(state: AgentState) -> dict[str, str]:
    files: dict[str, str] = {}

    paths = []

    for path in state.get("target_files", [])[:12]:
        if path not in paths:
            paths.append(path)

    file_plan = state.get("file_plan") or {}

    for path in file_plan.get("existing_files_to_modify", [])[:20]:
        if path not in paths:
            paths.append(path)

    for path in paths:
        try:
            files[path] = await read_file(path)
        except (FileNotFoundError, IsADirectoryError):
            continue

    return files


def _absolute_new_file_plan(
    project_root: str,
    file_plan: dict,
) -> list[dict]:
    root = Path(project_root)
    rows = []

    for item in file_plan.get("new_files", []):
        if isinstance(item, str):
            relative = item
            purpose = ""
        elif isinstance(item, dict):
            relative = str(item.get("path") or "")
            purpose = str(item.get("purpose") or "")
        else:
            continue

        relative = relative.strip()

        if not relative:
            continue

        rows.append({
            "path": str((root / relative).resolve()),
            "purpose": purpose,
        })

    return rows



def _normalize_relative_path(
    path: str,
    project_root: str,
) -> str:
    """
    Windows 절대경로/상대경로를 project_root 기준의 동일한 manifest key로 정규화합니다.

    예:
    F:\\Source\\repos\\Test\\agent\\backend\\app\\main.py
    backend/app/main.py

    두 값 모두:
    backend/app/main.py
    """
    raw = str(path or "").strip().replace("\\", "/")
    root_raw = str(project_root or "").strip().replace("\\", "/")

    def clean(value: str) -> str:
        value = re.sub(r"/+", "/", value.strip())
        while value.startswith("./"):
            value = value[2:]
        return value.rstrip("/").casefold()

    raw_clean = clean(raw)
    root_clean = clean(root_raw)

    if not raw_clean:
        return ""

    # Windows 드라이브 경로는 실행 OS와 무관하게 문자열 기준으로 처리합니다.
    if root_clean:
        prefix = root_clean + "/"

        if raw_clean == root_clean:
            return ""

        if raw_clean.startswith(prefix):
            return raw_clean[len(prefix):]

    # Path가 현재 OS에서 정상적인 절대경로로 인식되는 경우도 처리합니다.
    try:
        p = Path(path).expanduser().resolve()
        root = Path(project_root).expanduser().resolve()
        return p.relative_to(root).as_posix().casefold()
    except Exception:
        pass

    # 드라이브 표기가 남아 있는 외부 절대경로는 그대로 상대경로로 오인하지 않습니다.
    if re.match(r"^[a-z]:/", raw_clean):
        return raw_clean

    return raw_clean.lstrip("/")


def _canonical_manifest_path(
    path: str,
    project_root: str,
    required_paths: set[str] | None = None,
) -> str:
    """
    manifest 비교 전 특수 dotfile 이름을 보존/보정합니다.

    일부 LLM Patch 응답이 `.env.example`을 `env.example`로 반환하더라도
    File Plan에 `.env.example`이 required로 존재하면 같은 파일로 간주합니다.
    일반 파일의 선행 점은 임의로 제거하지 않습니다.
    """
    normalized = _normalize_relative_path(
        path,
        project_root,
    )

    required = required_paths or set()

    dotfile_aliases = {
        "env.example": ".env.example",
        "gitignore": ".gitignore",
        "dockerignore": ".dockerignore",
    }

    alias = dotfile_aliases.get(normalized)
    if alias and alias in required:
        return alias

    return normalized


def _required_manifest_paths(state: AgentState) -> set[str]:
    result: set[str] = set()

    for item in (state.get("file_plan") or {}).get("new_files") or []:
        if isinstance(item, str):
            path = item
            required = True
        elif isinstance(item, dict):
            path = str(item.get("path") or "")
            required = bool(item.get("required", True))
        else:
            continue

        if required and path.strip():
            result.add(
                _normalize_relative_path(
                    path,
                    state["project_root"],
                )
            )

    return result


def _existing_project_manifest_paths(
    state: AgentState,
) -> set[str]:
    root = Path(state["project_root"]).resolve()
    result: set[str] = set()

    if not root.exists():
        return result

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        try:
            relative = path.relative_to(root).as_posix().casefold()
        except ValueError:
            continue

        # 진단 산출물은 생성 Agent의 기능 파일로 계산하지 않습니다.
        if relative.split("/", 1)[0] in {
            "reports",
            "debug",
            "logs",
            "venv",
            ".venv",
            "node_modules",
            ".git",
        }:
            continue

        result.add(relative)

    return result


def _patch_plan_paths(
    plan: dict,
    project_root: str,
    required_paths: set[str] | None = None,
) -> set[str]:
    result: set[str] = set()

    for change in plan.get("changes") or []:
        if not isinstance(change, dict):
            continue

        path = str(change.get("path") or "").strip()
        if path:
            result.add(
                _canonical_manifest_path(
                    path,
                    project_root,
                    required_paths,
                )
            )

    return result


def _merge_patch_plans(
    primary: dict,
    supplement: dict,
    project_root: str,
    required_paths: set[str] | None = None,
) -> dict:
    merged: dict[str, dict] = {}

    for source in (
        primary.get("changes") or [],
        supplement.get("changes") or [],
    ):
        for change in source:
            if not isinstance(change, dict):
                continue

            manifest_path = _canonical_manifest_path(
                str(change.get("path") or ""),
                project_root,
                required_paths,
            )

            if not manifest_path:
                continue

            merged[manifest_path] = {
                **change,
                "path": manifest_path,
            }

    return {
        "changes": list(merged.values()),
    }


def _normalize_patch_plan(
    plan: dict,
    project_root: str,
    required_paths: set[str] | None = None,
) -> dict:
    """
    Plan 내부 경로를 project_root 기준 상대경로로 통일하고 중복을 제거합니다.
    required dotfile alias도 여기서 정규화합니다.
    """
    merged: dict[str, dict] = {}

    for change in plan.get("changes") or []:
        if not isinstance(change, dict):
            continue

        manifest_path = _canonical_manifest_path(
            str(change.get("path") or ""),
            project_root,
            required_paths,
        )

        if not manifest_path:
            continue

        merged[manifest_path] = {
            **change,
            "path": manifest_path,
        }

    return {
        **plan,
        "changes": list(merged.values()),
    }


async def _focused_patch_apply_recovery_plan(
    state: AgentState,
    failed_change: dict,
    exc: PatchApplyError,
) -> dict:
    """
    v5.170: stale/exact-string Patch 실패 시 전체 Code Generation을 다시 하지 않고
    실패한 단일 파일의 현재 내용을 다시 읽어 focused whole-file recovery plan을 생성합니다.
    """
    root = Path(state["project_root"]).resolve()
    target = Path(exc.target).resolve()
    try:
        relative = target.relative_to(root).as_posix()
    except ValueError as path_exc:
        raise PermissionError(
            f"Focused Patch Recovery 대상이 프로젝트 Root 밖입니다: {target}"
        ) from path_exc

    current_content = await read_file(str(target))
    intended = {
        "path": relative,
        "reason": str(failed_change.get("reason") or ""),
        "failed_old": exc.old,
        "intended_new": exc.new,
    }

    recovery_request = (
        str(state.get("request") or "")
        + "\n\n[Focused Patch Recovery]\n"
        + "기존 Patch의 old 문자열이 현재 파일과 일치하지 않아 적용에 실패했습니다. "
          "전체 Agent를 다시 생성하지 말고 아래 한 파일만 현재 내용 기준으로 복구하세요.\n"
        + f"대상 파일: {relative}\n"
        + "이전 변경 의도:\n"
        + json.dumps(intended, ensure_ascii=False, indent=2)
        + "\n\n[절대 규칙]\n"
          "1. changes에는 위 대상 파일 하나만 반환합니다.\n"
          "2. 현재 파일을 보존하면서 이전 변경 의도를 실제 코드에 반영합니다.\n"
          "3. 정확한 old 문자열 추측을 다시 하지 않습니다.\n"
          "4. replace_entire_file=true와 content에 수정 완료된 전체 파일을 반환합니다.\n"
          "5. 다른 파일은 수정하지 않습니다.\n"
          "6. TODO/placeholder/stub를 새로 만들지 않습니다.\n"
    )

    raw_plan = await create_patch(
        recovery_request,
        {str(target): current_content},
        state.get("provider"),
        project_scope=True,
    )
    normalized = _normalize_patch_plan(
        raw_plan,
        state["project_root"],
        _required_manifest_paths(state),
    )

    required_paths = _required_manifest_paths(state)
    canonical_target = _canonical_manifest_path(
        relative,
        state["project_root"],
        required_paths,
    )
    matching = []
    for change in normalized.get("changes") or []:
        change_path = _canonical_manifest_path(
            str(change.get("path") or ""),
            state["project_root"],
            required_paths,
        )
        if change_path.casefold() == canonical_target.casefold():
            row = dict(change)
            row["path"] = canonical_target
            # Focused recovery는 현재 파일 전체를 모델이 이미 본 상태이므로
            # content가 있으면 partial replacement 대신 전체 파일 교체를 강제합니다.
            if str(row.get("content") or "").strip():
                row["create_file"] = False
                row["replace_entire_file"] = True
                row["replacements"] = []
            matching.append(row)

    if len(matching) != 1:
        raise RuntimeError(
            "Focused Patch Recovery가 대상 파일 하나의 안전한 Plan을 반환하지 않았습니다: "
            f"{canonical_target}"
        )

    if not str(matching[0].get("content") or "").strip():
        raise RuntimeError(
            "Focused Patch Recovery가 전체 파일 content를 반환하지 않았습니다: "
            f"{canonical_target}"
        )

    return {"changes": matching}


async def _apply_patch_with_focused_recovery(
    state: AgentState,
    plan: dict,
    max_recoveries: int = 2,
) -> tuple[list[dict], list[dict]]:
    """
    Patch를 순서대로 적용하되 old-string drift가 발생하면 해당 파일만 다시 생성합니다.
    이미 성공한 앞쪽 변경은 다시 호출하지 않으므로 중복 적용과 토큰 낭비를 막습니다.
    """
    pending = list(plan.get("changes") or [])
    results: list[dict] = []
    recoveries: list[dict] = []

    while pending:
        try:
            batch_results = await apply_patch(
                {"changes": pending},
                project_root=state["project_root"],
            )
            results.extend(batch_results)
            return results, recoveries
        except PatchApplyError as exc:
            results.extend(exc.partial_results)
            if len(recoveries) >= max_recoveries:
                exc.partial_results = list(results)
                raise
            if exc.change_index < 0 or exc.change_index >= len(pending):
                exc.partial_results = list(results)
                raise

            failed_change = pending[exc.change_index]
            focused_plan = await _focused_patch_apply_recovery_plan(
                state,
                failed_change,
                exc,
            )
            try:
                focused_result = await apply_patch(
                    focused_plan,
                    project_root=state["project_root"],
                )
            except PatchApplyError as focused_exc:
                focused_exc.partial_results = list(results) + list(focused_exc.partial_results or [])
                raise
            results.extend(focused_result)
            recoveries.append({
                "target": exc.target,
                "failed_change_index": exc.change_index,
                "failed_replacement_index": exc.replacement_index,
                "strategy": "focused_replace_entire_file",
                "old_excerpt": exc.old[:500],
                "new_excerpt": exc.new[:500],
                "recovery_plan": focused_plan,
            })

            # 실패 change는 focused whole-file repair로 대체했고, 그 뒤 change만 계속합니다.
            pending = pending[exc.change_index + 1 :]

    return results, recoveries


def _validate_code_plan_manifest(
    state: AgentState,
    plan: dict,
) -> dict:
    required = _required_manifest_paths(state)
    existing = _existing_project_manifest_paths(state)
    planned = _patch_plan_paths(
        plan,
        state["project_root"],
        required,
    )

    missing = sorted(
        required - (existing | planned)
    )

    return {
        "ok": not missing,
        "required_count": len(required),
        "existing_count": len(existing & required),
        "planned_change_count": len(planned),
        "missing_required_paths": missing,
    }


CODE_PLAN_SUPPLEMENT_BATCH_SIZE = 3
CODE_PLAN_SUPPLEMENT_MAX_ROUNDS = 24
CODE_PLAN_SUPPLEMENT_NO_PROGRESS_LIMIT = 3


def _deterministic_support_file_change(
    state: AgentState,
    path: str,
) -> dict | None:
    """
    LLM이 hidden dotfile만 반복 누락할 때 안전하게 만들 수 있는 지원 파일은
    AgentStudio가 결정적으로 보강합니다. 실행 로직 파일은 여기서 임의 생성하지 않습니다.
    """
    normalized = str(path or "").replace("\\", "/").casefold()

    if normalized == ".env.example":
        rows = [
            "# THEANOVA AgentStudio generated environment example",
            "# 실제 비밀키/비밀번호는 이 파일에 넣지 마십시오.",
            "",
        ]
        fields = (state.get("settings_schema") or {}).get("fields") or []
        seen = set()
        for field in fields:
            if not isinstance(field, dict):
                continue
            key = str(field.get("key") or "").strip()
            if not key:
                continue
            env_key = re.sub(r"[^A-Za-z0-9_]+", "_", key).upper().strip("_")
            if not env_key or env_key in seen:
                continue
            seen.add(env_key)
            default = field.get("default")
            secret = bool(field.get("secret"))
            value = "" if secret or default is None else str(default)
            if env_key == "DATABASE_URL":
                rows += [
                    "# DATABASE_URL 입력 방법 (PostgreSQL)",
                    "# 형식: postgresql://사용자:비밀번호@호스트:포트/데이터베이스명",
                    "# 로컬 예시: postgresql://postgres:YOUR_PASSWORD@127.0.0.1:5432/YOUR_DATABASE",
                    "# 실제 값은 사용자가 관리하는 .env 또는 OS 환경변수에 설정하세요.",
                ]
                value = value or "postgresql://postgres:YOUR_PASSWORD@127.0.0.1:5432/YOUR_DATABASE"
            elif env_key == "REDIS_URL":
                rows += [
                    "# REDIS_URL 입력 방법",
                    "# 형식: redis://호스트:포트/DB번호",
                    "# 로컬 예시: redis://127.0.0.1:6379/0",
                ]
                value = value or "redis://127.0.0.1:6379/0"
            elif env_key == "OPENAI_API_KEY":
                rows += [
                    "# OpenAI를 사용할 때만 실제 Key를 .env 또는 OS 환경변수에 설정하세요.",
                    "# 예시: OPENAI_API_KEY=YOUR_OPENAI_API_KEY",
                ]
                value = value or "YOUR_OPENAI_API_KEY"
            rows.append(f"{env_key}={value}")

        if not seen:
            rows += [
                "OPENAI_API_KEY=",
                "OLLAMA_BASE_URL=http://127.0.0.1:11434",
            ]

        return {
            "path": ".env.example",
            "create_file": True,
            "content": "\n".join(rows).rstrip() + "\n",
            "reason": "required .env.example deterministic support-file fallback",
        }

    if normalized == ".gitignore":
        return {
            "path": ".gitignore",
            "create_file": True,
            "content": (
                ".env\n"
                ".venv/\n"
                "venv/\n"
                "__pycache__/\n"
                "*.py[cod]\n"
                "node_modules/\n"
                "dist/\n"
                "logs/\n"
            ),
            "reason": "required .gitignore deterministic support-file fallback",
        }

    if normalized == ".dockerignore":
        return {
            "path": ".dockerignore",
            "create_file": True,
            "content": (
                ".git\n"
                ".env\n"
                ".venv\n"
                "venv\n"
                "node_modules\n"
                "__pycache__\n"
                "logs\n"
            ),
            "reason": "required .dockerignore deterministic support-file fallback",
        }

    return None


def _file_plan_rows_for_paths(
    state: AgentState,
    paths: list[str],
) -> list[dict]:
    """보강 대상 path에 해당하는 File Plan 행만 추립니다."""
    requested = set(paths)
    rows: list[dict] = []

    for item in (state.get("file_plan") or {}).get("new_files") or []:
        if isinstance(item, str):
            raw_path = item
            row = {
                "path": item,
                "required": True,
            }
        elif isinstance(item, dict):
            raw_path = str(item.get("path") or "")
            row = dict(item)
        else:
            continue

        normalized = _normalize_relative_path(
            raw_path,
            state["project_root"],
        )

        if normalized in requested:
            rows.append(row)

    return rows


def _filter_patch_plan_paths(
    plan: dict,
    project_root: str,
    allowed_paths: set[str],
    required_paths: set[str],
) -> dict:
    """
    Code Plan 보강 응답이 이미 생성된 다른 파일까지 다시 반환하더라도
    이번 배치에서 요청한 누락 파일만 병합합니다.
    """
    changes = []

    for change in plan.get("changes") or []:
        if not isinstance(change, dict):
            continue

        manifest_path = _canonical_manifest_path(
            str(change.get("path") or ""),
            project_root,
            required_paths,
        )

        if manifest_path not in allowed_paths:
            continue

        changes.append({
            **change,
            "path": manifest_path,
        })

    return {
        **plan,
        "changes": changes,
    }


async def _complete_code_plan_manifest(
    state: AgentState,
    plan: dict,
    files: dict[str, str],
) -> tuple[dict, dict]:
    """
    LLM이 많은 required 파일을 한 번의 JSON 응답에 모두 담지 못하는 경우를
    대비해 누락 파일을 작은 배치로 반복 생성합니다.

    기존 v5.161은 보강 요청을 단 한 번만 수행했기 때문에, 20~30개 파일을
    계획한 Agent에서 일부만 반환되면 CODE_PLAN_INCOMPLETE로 즉시 종료됐습니다.
    """
    required_paths = _required_manifest_paths(state)
    plan = _normalize_patch_plan(
        plan,
        state["project_root"],
        required_paths,
    )
    validation = _validate_code_plan_manifest(
        state,
        plan,
    )

    initial_missing = list(
        validation.get("missing_required_paths") or []
    )
    attempts: list[dict] = []

    if validation.get("ok"):
        return plan, {
            **validation,
            "initial_missing_count": 0,
            "supplement_rounds": 0,
            "supplement_attempts": [],
        }

    estimated_rounds = (
        len(initial_missing) + CODE_PLAN_SUPPLEMENT_BATCH_SIZE - 1
    ) // CODE_PLAN_SUPPLEMENT_BATCH_SIZE
    max_rounds = min(
        CODE_PLAN_SUPPLEMENT_MAX_ROUNDS,
        max(6, estimated_rounds + 4),
    )
    no_progress_rounds = 0

    for round_no in range(1, max_rounds + 1):
        missing_before = list(
            validation.get("missing_required_paths") or []
        )
        if not missing_before:
            break

        # 직전 보강이 진전이 없었다면 한 파일씩 집중 생성합니다.
        batch_size = (
            1
            if no_progress_rounds > 0
            else CODE_PLAN_SUPPLEMENT_BATCH_SIZE
        )
        targets = missing_before[:batch_size]
        target_rows = _file_plan_rows_for_paths(
            state,
            targets,
        )

        supplement_request = (
            state["request"]
            + "\n\n[Code Plan 자동 보강 - 현재 배치]\n"
            + json.dumps(
                target_rows,
                ensure_ascii=False,
                indent=2,
            )
            + "\n\n[이번 배치에서 반드시 생성할 정확한 상대경로]\n"
            + json.dumps(
                targets,
                ensure_ascii=False,
                indent=2,
            )
            + "\n\n[확정 Agent Architecture]\n"
            + json.dumps(
                state.get("agent_architecture") or {},
                ensure_ascii=False,
                indent=2,
            )
            + "\n\n[확정 Tool/MCP Plan]\n"
            + json.dumps(
                state.get("tool_mcp_plan") or {},
                ensure_ascii=False,
                indent=2,
            )
            + "\n\n"
            "이번 응답은 위 정확한 상대경로만 changes[]에 반환하십시오. "
            "각 target path마다 정확히 하나의 change를 포함하고, "
            "아직 존재하지 않는 파일은 create_file=true와 전체 content를 작성하십시오. "
            "실행 가능한 구현이어야 하며 TODO/placeholder/stub를 남기지 마십시오. "
            "이미 Code Plan에 들어 있는 다른 파일은 반복 생성하거나 수정하지 마십시오."
        )

        try:
            supplement = await create_patch(
                supplement_request,
                files,
                state.get("provider"),
                project_scope=True,
            )
            supplement = _normalize_patch_plan(
                supplement,
                state["project_root"],
                required_paths,
            )
            supplement = _filter_patch_plan_paths(
                supplement,
                state["project_root"],
                set(targets),
                required_paths,
            )
        except Exception as exc:
            attempts.append({
                "round": round_no,
                "requested_paths": targets,
                "returned_paths": [],
                "added_paths": [],
                "remaining_count": len(missing_before),
                "error": str(exc),
            })
            no_progress_rounds += 1
            if (
                no_progress_rounds
                >= CODE_PLAN_SUPPLEMENT_NO_PROGRESS_LIMIT
            ):
                break
            continue

        returned_paths = sorted(
            _patch_plan_paths(
                supplement,
                state["project_root"],
                required_paths,
            )
        )

        plan = _merge_patch_plans(
            plan,
            supplement,
            state["project_root"],
            required_paths,
        )
        next_validation = _validate_code_plan_manifest(
            state,
            plan,
        )
        missing_after = list(
            next_validation.get("missing_required_paths") or []
        )
        added_paths = sorted(
            set(missing_before) - set(missing_after)
        )

        attempts.append({
            "round": round_no,
            "requested_paths": targets,
            "returned_paths": returned_paths,
            "added_paths": added_paths,
            "remaining_count": len(missing_after),
            "error": "",
        })

        validation = next_validation

        if added_paths:
            no_progress_rounds = 0
        else:
            no_progress_rounds += 1

        if validation.get("ok"):
            break

        if (
            no_progress_rounds
            >= CODE_PLAN_SUPPLEMENT_NO_PROGRESS_LIMIT
        ):
            break

    # LLM이 .env.example 같은 hidden support file 하나만 끝까지 누락하는 경우
    # 실행 코드와 무관한 안전한 파일에 한해서 결정적 fallback을 적용합니다.
    remaining_before_fallback = list(
        validation.get("missing_required_paths") or []
    )
    deterministic_changes = []
    for missing_path in remaining_before_fallback:
        change = _deterministic_support_file_change(
            state,
            missing_path,
        )
        if change is not None:
            deterministic_changes.append(change)

    if deterministic_changes:
        fallback_plan = _normalize_patch_plan(
            {"changes": deterministic_changes},
            state["project_root"],
            required_paths,
        )
        plan = _merge_patch_plans(
            plan,
            fallback_plan,
            state["project_root"],
            required_paths,
        )
        next_validation = _validate_code_plan_manifest(
            state,
            plan,
        )
        missing_after = list(
            next_validation.get("missing_required_paths") or []
        )
        added_paths = sorted(
            set(remaining_before_fallback) - set(missing_after)
        )
        attempts.append({
            "round": "deterministic",
            "strategy": "support_file_fallback",
            "requested_paths": remaining_before_fallback,
            "returned_paths": [
                str(item.get("path") or "")
                for item in deterministic_changes
            ],
            "added_paths": added_paths,
            "remaining_count": len(missing_after),
            "error": "",
        })
        validation = next_validation

    return plan, {
        **validation,
        "initial_missing_count": len(initial_missing),
        "supplement_rounds": len(attempts),
        "supplement_attempts": attempts,
        "supplement_completed": bool(validation.get("ok")),
        "supplement_no_progress_rounds": no_progress_rounds,
    }


def _validate_stdio_code_plan(
    state: AgentState,
    plan: dict,
) -> dict:
    """
    stdio 확정 요구인데 Code Plan 자체에 Flask/requests/localhost HTTP 구현이
    들어 있으면 실제 파일 적용 전에 중단합니다.
    """
    contracts = _requirement_contracts(state)
    if not contracts.get("stdio"):
        return {"ok": True, "violations": []}

    forbidden = [
        "from flask",
        "import flask",
        "requests.post",
        "requests.get",
        "localhost:5000",
        "127.0.0.1:5000",
        "app.run(",
    ]

    violations = []

    for change in plan.get("changes") or []:
        if not isinstance(change, dict):
            continue

        path = str(change.get("path") or "").replace("\\", "/").casefold()
        if not (
            "mcp" in path
            or path.endswith("server.py")
        ):
            continue

        content = str(
            change.get("content")
            or change.get("new_content")
            or change.get("replacement")
            or ""
        ).casefold()

        found = [
            token
            for token in forbidden
            if token in content
        ]

        if found:
            violations.append({
                "path": path,
                "forbidden": found,
                "message": (
                    "MCP stdio 확정 요구와 충돌하는 HTTP/Flask 구현이 "
                    "Code Plan에 포함되어 있습니다."
                ),
            })

    return {
        "ok": not violations,
        "violations": violations,
    }


def _repair_targets_from_validation(
    state: AgentState,
) -> dict:
    artifact = state.get("build_artifact_validation") or {}
    root = Path(state["project_root"]).resolve()

    def rel(path: str) -> str:
        try:
            return Path(path).resolve().relative_to(root).as_posix()
        except Exception:
            return str(path).replace("\\", "/")

    missing = [
        rel(path)
        for path in artifact.get("missing_files") or []
    ]

    architecture = [
        {
            **item,
            "relative_path": rel(str(item.get("path") or "")),
        }
        for item in artifact.get("architecture_errors") or []
        if isinstance(item, dict)
    ]

    placeholders = [
        rel(path)
        for path in artifact.get("placeholder_files") or []
    ]

    placeholder_details = []
    for item in artifact.get("placeholder_details") or []:
        if not isinstance(item, dict):
            continue
        placeholder_details.append({
            "relative_path": rel(str(item.get("path") or "")),
            "findings": list(item.get("findings") or []),
        })

    style = [
        {
            **item,
            "relative_path": rel(str(item.get("path") or "")),
        }
        for item in artifact.get("coding_style_errors") or []
        if isinstance(item, dict)
    ]
    documentation = [
        {
            **item,
            "relative_path": rel(str(item.get("path") or "")),
        }
        for item in artifact.get("code_documentation_errors") or []
        if isinstance(item, dict)
    ]

    return {
        "missing_files": missing,
        "architecture_errors": architecture,
        "placeholder_files": placeholders,
        "placeholder_details": placeholder_details,
        "coding_style_errors": style,
        "code_documentation_errors": documentation,
    }


def _repair_required_paths(
    targets: dict,
) -> set[str]:
    result = set(
        str(path).replace("\\", "/").casefold()
        for path in targets.get("missing_files") or []
    )

    for key in (
        "architecture_errors",
        "coding_style_errors",
        "code_documentation_errors",
    ):
        for item in targets.get(key) or []:
            path = str(item.get("relative_path") or "").replace("\\", "/").casefold()
            if path:
                result.add(path)

    result.update(
        str(path).replace("\\", "/").casefold()
        for path in targets.get("placeholder_files") or []
    )

    return result



_TEST_REPAIR_SUFFIXES = (
    ".py", ".js", ".jsx", ".ts", ".tsx", ".vue", ".svelte", ".astro", ".dart", ".razor", ".cshtml", ".json", ".html", ".css", ".scss", ".sass", ".less", ".md", ".txt",
)


def _latest_debug_entry(state: AgentState) -> dict:
    history = state.get("debug_history") or []
    if history and isinstance(history[-1], dict):
        return history[-1]
    return {}


def _debug_history_count(state: AgentState, kind: str) -> int:
    return sum(
        1
        for item in state.get("debug_history") or []
        if isinstance(item, dict) and str(item.get("type") or "") == kind
    )


def _candidate_code_paths_from_text(text: str) -> list[str]:
    """테스트/디버그 로그에서 명시된 소스 경로를 보수적으로 추출합니다."""
    value = str(text or "")
    result: list[str] = []
    seen: set[str] = set()

    patterns = (
        # Windows/Unix 상대·절대 경로. 공백이 거의 없는 소스 경로를 대상으로 합니다.
        re.compile(r"(?i)([A-Za-z]:[\\/][^\r\n\"'<>|]+?\.(?:py|jsx?|tsx?|vue|svelte|astro|dart|razor|cshtml|json|html|css|scss|sass|less|md|txt))"),
        re.compile(r"(?i)((?:\.?\.?[\\/])?(?:[A-Za-z0-9_.-]+[\\/])+[A-Za-z0-9_.-]+\.(?:py|jsx?|tsx?|vue|svelte|astro|dart|razor|cshtml|json|html|css|scss|sass|less|md|txt))"),
        # Python compileall / traceback가 basename만 주는 경우.
        re.compile(r"(?i)\(([A-Za-z0-9_.-]+\.py),\s*line\s*\d+\)"),
    )

    for pattern in patterns:
        for match in pattern.finditer(value):
            raw = str(match.group(1) or "").strip().strip("`'\"")
            if not raw:
                continue
            key = raw.replace("\\", "/").casefold()
            if key in seen:
                continue
            seen.add(key)
            result.append(raw)

    return result


def _test_repair_target_paths(state: AgentState, analysis: dict) -> list[str]:
    """
    테스트 실패 로그/Debug 지시에서 실제 수정 대상 파일을 찾습니다.

    basename만 있는 경우 File Plan 또는 현재 프로젝트에서 유일하게 일치하는 파일만 선택하여
    엉뚱한 파일을 수정하지 않습니다.
    """
    project_root = str(state.get("project_root") or "")
    root = Path(project_root).resolve()
    file_plan = state.get("file_plan") or {}
    planned = []
    for item in file_plan.get("new_files") or []:
        raw = item if isinstance(item, str) else str((item or {}).get("path") or "")
        if raw:
            planned.append(str(raw).replace("\\", "/").lstrip("./"))

    source_text = "\n".join([
        str(analysis.get("request_for_patch") or ""),
        str(analysis.get("diagnosis") or ""),
        str(analysis.get("local_log_triage") or ""),
        str((state.get("test_result") or {}).get("output") or ""),
    ])
    candidates = _candidate_code_paths_from_text(source_text)
    result: list[str] = []
    seen: set[str] = set()

    def add(relative: str) -> None:
        rel = str(relative or "").replace("\\", "/").lstrip("./")
        if not rel or _is_runtime_artifact_path(project_root, rel):
            return
        if Path(rel).suffix.casefold() not in _TEST_REPAIR_SUFFIXES:
            return
        # File Plan의 원래 대소문자를 우선 보존합니다.
        rel = _canonical_planned_path(file_plan, rel)
        key = rel.casefold()
        if key in seen:
            return
        target = root / rel
        if target.is_file():
            seen.add(key)
            result.append(rel)

    for raw in candidates:
        raw_slash = str(raw or "").replace("\\", "/").strip()
        normalized = _normalize_relative_path(raw, project_root)
        if normalized and not re.match(r"^[a-z]:/", normalized):
            # Traceback/compileall commonly emits `.\main.py`.  That is an
            # explicit project-root path and must win over a File Plan entry such
            # as backend/app/main.py that merely shares the same basename.
            exact_root_candidate = (root / normalized).is_file()
            explicitly_relative = raw_slash.startswith("./")
            if "/" in normalized or explicitly_relative or exact_root_candidate:
                before_count = len(result)
                add(normalized)
                if len(result) > before_count:
                    continue

        basename = Path(raw_slash).name.casefold()
        if not basename:
            continue
        matches = [path for path in planned if Path(path).name.casefold() == basename]
        if len(matches) == 1:
            add(matches[0])
            continue

        disk_matches = []
        try:
            for path in root.rglob("*"):
                if not path.is_file() or path.name.casefold() != basename:
                    continue
                try:
                    relative = path.relative_to(root).as_posix()
                except ValueError:
                    continue
                if _is_runtime_artifact_path(project_root, relative):
                    continue
                disk_matches.append(relative)
        except OSError:
            disk_matches = []
        if len(disk_matches) == 1:
            add(disk_matches[0])

    return result[:3]


def _materialize_focused_repair_change(change: dict, current_content: str) -> dict | None:
    """Focused Repair가 replacements를 반환해도 안전하게 전체 파일 내용으로 승격합니다.

    v5.359은 ``content``가 있는 replace_entire_file 응답만 허용했기 때문에,
    모델이 유효한 replacements를 반환한 경우에도 "수정 대상 파일을 완전하게 포함하지 못함"으로
    조기 종료될 수 있었습니다. PatchService와 동일한 안전 치환 규칙으로 메모리에서만 적용한 뒤
    전체 파일 교체 형태로 정규화합니다.
    """
    row = dict(change or {})
    direct = str(row.get("content") or "")
    if direct.strip():
        row["content"] = direct
        row["create_file"] = False
        row["replace_entire_file"] = True
        row["replacements"] = []
        return row

    replacements = list(row.get("replacements") or [])
    if not replacements:
        return None

    content = str(current_content or "")
    for rep in replacements:
        old = str((rep or {}).get("old") or "")
        new = str((rep or {}).get("new") or "")
        if not old:
            return None
        applied = _safe_replacement(content, old, new)
        if applied is None:
            return None
        content, _strategy = applied

    if content == str(current_content or ""):
        return None

    row["content"] = content
    row["create_file"] = False
    row["replace_entire_file"] = True
    row["replacements"] = []
    return row


def _matching_focused_repair_change(
    normalized: dict,
    canonical_target: str,
    current_content: str,
    project_root: str,
    manifest_paths: set[str],
) -> dict | None:
    matches: list[dict] = []
    for change in normalized.get("changes") or []:
        change_path = _canonical_manifest_path(
            str(change.get("path") or ""),
            project_root,
            manifest_paths,
        )
        if change_path.casefold() != canonical_target.casefold():
            continue
        row = _materialize_focused_repair_change(change, current_content)
        if row is None:
            continue
        row["path"] = canonical_target
        matches.append(row)
    return matches[0] if len(matches) == 1 else None


async def _focused_test_failure_repair_plan(
    state: AgentState,
    analysis: dict,
) -> tuple[dict, dict]:
    """
    TEST_FAILED 후에는 이전 Build Placeholder Repair를 재사용하지 않고,
    테스트 로그가 지목한 파일만 현재 내용 기준으로 전체 파일 복구합니다.
    """
    root = Path(state["project_root"]).resolve()
    targets = _test_repair_target_paths(state, analysis)
    validation = {
        "ok": False,
        "repair_type": "test_failure",
        "targets": targets,
        "target_count": len(targets),
        "missing_repair_targets": [],
    }
    if not targets:
        validation["error"] = "테스트 로그에서 안전하게 특정할 수 있는 수정 대상 파일을 찾지 못했습니다."
        return {"changes": []}, validation

    combined_changes: list[dict] = []
    missing: list[str] = []
    test_output = str((state.get("test_result") or {}).get("output") or "")[-12_000:]

    for relative in targets:
        target = (root / relative).resolve()
        if root != target and root not in target.parents:
            missing.append(relative)
            continue
        if not target.is_file():
            missing.append(relative)
            continue

        current_content = await read_file(str(target))
        request = (
            str(state.get("request") or "")
            + "\n\n[AgentStudio Test Failure Focused Repair]\n"
            + f"대상 파일: {relative}\n"
            + f"실패 진단: {analysis.get('diagnosis') or ''}\n"
            + f"구체적 수정 지시: {analysis.get('request_for_patch') or ''}\n\n"
            + "테스트 실패 로그:\n"
            + test_output
            + "\n\n[절대 규칙]\n"
              "1. changes에는 위 대상 파일 하나만 반환합니다.\n"
              "2. 현재 파일 전체를 읽고 테스트 오류를 실제로 해결한 완전한 코드를 작성합니다.\n"
              "3. replace_entire_file=true와 content에 수정 완료된 전체 파일을 반환합니다.\n"
              "4. replacements 기반 부분 패치보다 전체 파일 교체를 사용합니다.\n"
              "5. Python이면 들여쓰기/문법/import를 포함해 파일 단위 문법이 유효해야 합니다.\n"
              "6. TODO/placeholder/stub를 남기지 않습니다.\n"
              "7. 다른 파일은 수정하지 않습니다.\n"
            + _code_documentation_instruction(state)
            + _user_coding_style_instruction(state)
        )
        raw_plan = await create_patch(
            request,
            {str(target): current_content},
            state.get("provider"),
            project_scope=True,
        )
        normalized = _normalize_patch_plan(
            raw_plan,
            state["project_root"],
            _required_manifest_paths(state),
        )
        manifest_paths = _required_manifest_paths(state)
        canonical_target = _canonical_manifest_path(
            relative,
            state["project_root"],
            manifest_paths,
        )
        matched = _matching_focused_repair_change(
            normalized,
            canonical_target,
            current_content,
            state["project_root"],
            manifest_paths,
        )

        # 첫 응답이 경로를 누락하거나 content 대신 불완전한 형식으로 왔을 때
        # 한 번만 더 좁은 Recovery Prompt로 재시도합니다. 전체 개발을 즉시 실패시키지 않습니다.
        if matched is None:
            recovery_request = (
                request
                + "\n\n[Focused Patch Recovery]\n"
                  "이전 응답은 AgentStudio가 적용 가능한 완전한 수정 파일을 만들지 못했습니다. "
                  f"changes 배열에 정확히 '{canonical_target}' 한 파일만 넣고, "
                  "replace_entire_file=true, content에는 수정 완료된 전체 파일을 반드시 반환하십시오. "
                  "replacements만 반환하지 마십시오."
            )
            try:
                retry_plan = await create_patch(
                    recovery_request,
                    {canonical_target: current_content},
                    state.get("provider"),
                    project_scope=True,
                )
                retry_normalized = _normalize_patch_plan(
                    retry_plan,
                    state["project_root"],
                    manifest_paths,
                )
                matched = _matching_focused_repair_change(
                    retry_normalized,
                    canonical_target,
                    current_content,
                    state["project_root"],
                    manifest_paths,
                )
            except Exception as _retry_exc:
                matched = None

        if matched is None:
            missing.append(relative)
            continue
        combined_changes.append(matched)

    validation["missing_repair_targets"] = missing
    validation["planned_repair_count"] = len(combined_changes)
    # 일부 안전한 수정이라도 확보했으면 우선 적용 후 테스트를 다시 실행합니다.
    # 다음 TEST_FAILED 반복에서 남은 실제 원인만 다시 추적하는 편이, 호출 스택의 모든
    # 파일을 한 번에 수정하라고 강제해 개발 전체를 조기 실패시키는 것보다 안전합니다.
    validation["partial"] = bool(combined_changes) and bool(missing)
    validation["ok"] = bool(combined_changes)
    if validation["partial"]:
        validation["warning"] = (
            "일부 Focused Repair 대상만 안전하게 생성되었습니다. 우선 적용 후 테스트를 재실행하고 "
            "남은 실패가 실제 원인으로 확인될 때 다음 Debug 반복에서 추가 수정합니다."
        )
    return {"changes": combined_changes}, validation


def _clip_generation_context(value: str, limit: int = 12_000) -> str:
    """Code Generation에 필요한 인터뷰 원문은 확정 요구사항을 보조하는 범위로 제한합니다."""
    text = str(value or "")
    if len(text) <= limit:
        return text

    marker = (
        "\n\n... [AgentStudio v5.166: 인터뷰 원문 중간 축약 / "
        f"원본 {len(text):,}자] ...\n\n"
    )
    usable = max(0, limit - len(marker))
    head = usable // 3
    tail = usable - head
    return text[:head] + marker + text[-tail:]


def _compact_coding_style_context(state: AgentState) -> dict:
    """
    Coding Style 전체 rule 본문은 patch_service가 다시 선택해서 Prompt에 적용합니다.
    Agent Factory 설계 Context에는 태그/Rule ID만 넣어 동일 규칙이 두 번 들어가는 것을 막습니다.
    """
    style = state.get("coding_style_context") or {}
    rules = style.get("rules") or []
    return {
        "tags": list(style.get("tags") or []),
        "rule_ids": [
            str(item.get("id") or "")
            for item in rules
            if isinstance(item, dict) and item.get("id")
        ],
    }


async def _read_repair_context(state: AgentState, targets: dict) -> dict[str, str]:
    """Repair 단계에서는 실패 대상 파일만 LLM Context에 넣어 재생성 범위를 좁힙니다."""
    root = Path(state["project_root"]).resolve()
    paths: list[str] = []

    for raw in targets.get("missing_files") or []:
        paths.append(str(raw))
    for raw in targets.get("placeholder_files") or []:
        paths.append(str(raw))
    for key in ("architecture_errors", "coding_style_errors"):
        for item in targets.get(key) or []:
            if isinstance(item, dict) and item.get("relative_path"):
                paths.append(str(item.get("relative_path")))

    result: dict[str, str] = {}
    seen: set[str] = set()
    for raw in paths:
        relative = _normalize_relative_path(raw, state["project_root"])
        if not relative or relative in seen:
            continue
        seen.add(relative)
        target = (root / relative).resolve()
        if root != target and root not in target.parents:
            continue
        if not target.is_file():
            continue
        try:
            result[str(target)] = target.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    return result




def _normalize_generated_fastapi_imports(project_root: str) -> dict:
    """생성된 표준 backend/app FastAPI 패키지의 내부 import를 실행 위치와 일치시킵니다.

    Generated SYSTEM_ADMIN은 backend 폴더를 WorkingDirectory로 두고
    ``uvicorn app.main:app``을 실행합니다. 따라서 backend/app 내부 모듈은
    ``app.*`` 또는 상대 import를 사용해야 합니다. 이전 생성본의
    ``from routers import ...`` / ``from backend.app...`` 혼용을 결정적으로 정리합니다.
    """
    root = Path(project_root).resolve()
    backend_dir = root / "backend"
    app_dir = backend_dir / "app"
    if not app_dir.is_dir():
        return {"ok": True, "changed_files": [], "created_package_files": [], "reason": "backend/app 없음"}

    changed_files: list[str] = []
    created_package_files: list[str] = []
    patch_rows: list[dict] = []

    # 표준 패키지 경계를 명확히 하여 Windows/Python 환경별 namespace package 차이를 제거합니다.
    package_dirs = [app_dir]
    for name in ("routers", "services", "schemas", "core", "mcp"):
        candidate = app_dir / name
        if candidate.is_dir():
            package_dirs.append(candidate)
    for directory in package_dirs:
        init_file = directory / "__init__.py"
        if not init_file.exists():
            init_file.write_text("", encoding="utf-8", newline="\n")
            rel = init_file.relative_to(root).as_posix()
            created_package_files.append(rel)
            patch_rows.append({
                "path": str(init_file),
                "changed": True,
                "created": True,
                "verified": True,
                "reason": "FastAPI Python package 경계 자동 생성",
            })

    bare_prefixes = "routers|services|schemas|core|mcp"
    from_bare = re.compile(
        rf"(?m)^(?P<indent>\s*)from\s+(?P<module>(?:{bare_prefixes})(?:\.[A-Za-z_][A-Za-z0-9_\.]*)?)\s+import\s+"
    )
    from_backend = re.compile(r"(?m)^(?P<indent>\s*)from\s+backend\.app(?P<rest>(?:\.[A-Za-z_][A-Za-z0-9_\.]*)?)\s+import\s+")

    for path in sorted(app_dir.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            original = path.read_text(encoding="utf-8-sig", errors="replace")

        updated = from_backend.sub(
            lambda m: f"{m.group('indent')}from app{m.group('rest')} import ",
            original,
        )
        updated = from_bare.sub(
            lambda m: f"{m.group('indent')}from app.{m.group('module')} import ",
            updated,
        )

        if updated != original:
            path.write_text(updated, encoding="utf-8", newline="\n")
            rel = path.relative_to(root).as_posix()
            changed_files.append(rel)
            patch_rows.append({
                "path": str(path),
                "changed": True,
                "created": False,
                "verified": True,
                "reason": "Generated FastAPI 내부 import를 backend cwd + app.* 기준으로 정규화",
            })

    # main.py의 대표적인 위험 import가 남아 있으면 COMPLETED로 진행하지 않습니다.
    violations: list[dict] = []
    for path in sorted(app_dir.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if re.match(rf"^from\s+(?:{bare_prefixes})(?:\.|\s)", stripped):
                violations.append({"path": path.relative_to(root).as_posix(), "line": line_no, "snippet": stripped})
            if re.match(r"^from\s+backend\.app(?:\.|\s)", stripped):
                violations.append({"path": path.relative_to(root).as_posix(), "line": line_no, "snippet": stripped})

    return {
        "ok": not violations,
        "changed_files": changed_files,
        "created_package_files": created_package_files,
        "violations": violations,
        "patch_rows": patch_rows,
        "uvicorn_target": "app.main:app",
        "working_directory": str(backend_dir),
    }

def _blender_3d_generation_instruction(build_context: dict, *, editor_mode: bool = False) -> str:
    plan = build_context.get("three_d_agent_plan") or {}
    if not isinstance(plan, dict) or str(plan.get("type") or "").upper() != "BLENDER_3D":
        return ""
    base = (
        " [Blender MCP 3D Agent 필수 계약] "
        "Blender MCP는 실행 Tool 계층으로만 사용하고, Agent가 Intent Router → 3D Schema Router → "
        "Structured Extraction(Pydantic SceneSpec) → Validator → LangGraph Scene State → Blender MCP → "
        "Viewport/Render Vision QA → bounded repair → Render/Export를 책임지게 구현하십시오. "
        "Scene State에는 scene_objects, selected_objects, materials, textures, camera, lights, current_step, "
        "completed_steps, failed_steps, render_status, output_files를 유지하십시오. "
        "MCP success만으로 완료 처리하지 말고 실제 Scene 상태와 Viewport/Render 결과를 검증하십시오. "
        "Blender MCP Tool은 Registry의 name/description/inputSchema/capability/risk를 분석해 선택하고, "
        "임의 Python/Script 실행은 고위험 Tool로 분류하여 승인 정책을 적용하십시오. "
        "stdio/streamable_http Transport는 Adapter에서 분리하고 Output/Asset 허용 Root 밖의 파일 작업을 금지하십시오. "
        "필수 테스트는 SceneSpec Validator, Blender MCP 계약, 3D Workflow, Regression을 포함하십시오. "
    )
    if editor_mode:
        base += (
            "Agent Editor 증분 수정에서는 현재 Agent 소스/Architecture/Workflow를 먼저 기준으로 삼고, "
            "변경 요구의 영향 범위와 수정 파일만 계산해 부분 수정하십시오. 기존 SceneSpec/MCP/Scene State/Render 계약과 "
            "변경 무관 기능을 보존하고, 수정 후 기존 3D 핵심 기능 Regression Test와 As-Built 검증을 반드시 수행하십시오. "
            "전체 프로젝트를 재생성하거나 정상 파일을 대량 교체하지 마십시오. "
        )
    return base


def _incremental_revision_info(state: AgentState) -> dict:
    runtime = (_bundle(state).get("design_runtime") or {}) if isinstance(_bundle(state), dict) else {}
    value = runtime.get("incremental_revision") or {}
    return value if isinstance(value, dict) else {}


def _incremental_focus_paths(state: AgentState, revision: dict) -> set[str]:
    root = Path(state["project_root"]).resolve()
    groups = {str(x or "").casefold() for x in revision.get("changed_groups") or []}
    affected = {str(x or "") for x in revision.get("affected_sections") or []}
    paths: set[str] = set()

    def add(raw):
        rel = _normalize_relative_path(str(raw or ""), state["project_root"])
        if rel and not re.match(r"^[a-z]:/", rel):
            paths.add(rel)

    for raw in state.get("target_files") or []:
        add(raw)

    file_plan = state.get("file_plan") or {}
    planned = []
    for item in file_plan.get("new_files") or []:
        if isinstance(item, str):
            rel = item
        elif isinstance(item, dict):
            rel = str(item.get("path") or "")
        else:
            continue
        rel = rel.replace("\\", "/").lstrip("./")
        if not rel:
            continue
        planned.append(rel)
        if not (root / rel).is_file():
            add(rel)

    def add_matching(tokens):
        for rel in planned:
            low = rel.casefold()
            if any(token in low for token in tokens):
                add(rel)

    if "ui" in groups:
        add_matching(("frontend/", "ui", "page", "component"))
    if "backend" in groups:
        add_matching(("backend/", "api", "router", "service"))
    if "llm" in groups:
        add_matching(("llm", "provider", "model", "config", "settings"))
    if "mcp" in groups or "tool_mcp_plan" in affected:
        add_matching(("mcp", "tool"))
    if "agent_specialization" in groups or "three_d_agent_plan" in affected:
        add_matching(("blender", "scene", "3d", "viewport", "render", "asset", "mcp", "workflow", "validator"))
    if "database" in groups or "database_plan" in affected:
        add_matching(("database", "db", "repository", "model", "schema", "migration"))
    if "auth" in groups:
        add_matching(("auth", "user", "role", "security", "permission"))
    if "settings_plan" in affected:
        for group in ("backend", "frontend"):
            for raw in (state.get("settings_plan") or {}).get(group, {}).values():
                add(raw)
    if "test_environment_plan" in affected:
        test_plan = state.get("test_environment_plan") or _bundle(state).get("test_environment_plan") or {}
        for group in ("backend", "frontend"):
            for raw in (test_plan.get(group) or {}).values():
                add(raw)
        for raw in test_plan.get("tests") or []:
            add(raw)

    # Keep incremental edits bounded. Missing required files are never dropped.
    required = _required_manifest_paths(state)
    existing = _existing_project_manifest_paths(state)
    paths.update(required - existing)
    return set(sorted(paths))


async def code_generation_node(state: AgentState):
    files = await _read_existing_context(state)

    design_bundle = state.get("design_bundle") or {}
    build_context = {
        "requirement_spec": state.get("requirement_spec", {}),
        "capability_plan": state.get("capability_plan", {}),
        "tool_mcp_plan": state.get("tool_mcp_plan", {}),
        "agent_architecture": state.get("agent_architecture", {}),
        "database_plan": state.get("database_plan", {}) or design_bundle.get("database_plan", {}),
        "target_agent_workflow": state.get("target_agent_workflow", {}),
        "development_stage_plan": state.get("development_stage_plan", {}) or design_bundle.get("development_stage_plan", {}),
        "development_workflow": state.get("development_workflow", {}) or design_bundle.get("development_workflow", {}),
        "active_development_stage": state.get("active_development_stage", {}) or design_bundle.get("active_development_stage", {}),
        "code_documentation": _code_documentation_policy(state),
        "user_coding_style": _user_coding_style_policy(state),
        "file_plan": state.get("file_plan", {}),
        "settings_plan": state.get("settings_plan", {}),
        "test_environment_plan": state.get("test_environment_plan", {}) or design_bundle.get("test_environment_plan", {}),
        "three_d_agent_plan": state.get("three_d_agent_plan", {}) or design_bundle.get("three_d_agent_plan", {}),
        "settings_schema": state.get("settings_schema", {}),
        "settings_ui_plan": state.get("settings_ui_plan", {}),
        # 전체 Coding Style rule/prompt는 create_patch()가 한 번만 주입합니다.
        "coding_style": _compact_coding_style_context(state),
        "confirmed_requirements": design_bundle.get("confirmed_requirements") or {},
        # 확정 요구사항이 있으므로 인터뷰 전체 원문은 보조 Context만 유지합니다.
        "interview_context": _clip_generation_context(
            design_bundle.get("interview_context") or ""
        ),
        "new_files_absolute": _absolute_new_file_plan(
            state["project_root"],
            state.get("file_plan") or {},
        ),
    }

    development_workflow = build_context.get("development_workflow") or {}
    development_stage_instruction = ""
    if development_workflow.get("stages"):
        development_stage_instruction = (
            "\n\n[사용자 승인 개발 Stage Workflow - 반드시 준수]\n"
            + json.dumps(development_workflow, ensure_ascii=False, indent=2)
            + "\nStage 순서를 무시해 한 번에 범위를 섞지 마십시오. 파일의 development_stage_id를 보존하고, 각 Stage의 deliverables/validation 경계를 지키십시오. "
            "완료된 Stage 기능을 이후 Stage에서 불필요하게 다시 작성하지 말고, 실패 시 해당 Stage 범위만 수정할 수 있도록 변경 경계를 유지하십시오."
        )

    three_d_generation_instruction = _blender_3d_generation_instruction(build_context, editor_mode=False)
    three_d_editor_instruction = _blender_3d_generation_instruction(build_context, editor_mode=True)
    code_documentation_instruction = _code_documentation_instruction(state)
    user_coding_style_instruction = _user_coding_style_instruction(state)

    latest_debug = _latest_debug_entry(state)
    test_repair_mode = (
        state.get("status") == "DEBUG_PATCH_READY"
        and str(latest_debug.get("type") or "") == "test_failure"
    )
    repair_mode = (
        state.get("status") == "DEBUG_PATCH_READY"
        and not test_repair_mode
        and bool(state.get("build_artifact_validation"))
        and not bool((state.get("build_artifact_validation") or {}).get("ok"))
    )
    architecture_repair_mode = state.get("status") == "ARCHITECTURE_REPAIR_READY"
    revision = _incremental_revision_info(state)
    revision_mode = str(revision.get("mode") or "")
    _existing_manifest = _existing_project_manifest_paths(state)
    _required_manifest = _required_manifest_paths(state)
    incremental_reuse_mode = (
        revision_mode == "FULL_REUSE"
        and bool(_existing_manifest)
        and _required_manifest.issubset(_existing_manifest)
    )
    incremental_partial_mode = (
        revision_mode == "PARTIAL_REVISE"
        and bool(_existing_project_manifest_paths(state))
    )
    repair_validation: dict = {}

    if architecture_repair_mode:
        conformance = state.get("architecture_conformance") or {}
        as_built = state.get("as_built_architecture") or {}
        root = Path(state["project_root"]).resolve()
        focused_paths: list[str] = []
        for row in (state.get("file_plan") or {}).get("component_file_map") or []:
            if isinstance(row, dict):
                focused_paths.extend(str(x or "") for x in row.get("files") or [])
        for row in conformance.get("mismatches") or []:
            if isinstance(row, dict) and row.get("path"):
                focused_paths.append(str(row.get("path") or ""))
        for row in (state.get("file_plan") or {}).get("new_files") or []:
            if isinstance(row, dict) and row.get("required", True):
                focused_paths.append(str(row.get("path") or ""))

        for raw in focused_paths[:80]:
            rel = str(raw or "").replace("\\", "/").strip().lstrip("./")
            if not rel:
                continue
            path = (root / rel).resolve()
            try:
                path.relative_to(root)
            except ValueError:
                continue
            if path.is_file() and path.stat().st_size <= 512_000:
                try:
                    files[rel] = path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    pass

        compact_as_built = {
            key: as_built.get(key)
            for key in ("components", "interfaces", "persistence", "security", "state", "frameworks", "required_files", "analysis_provider")
        }
        patch_request = (
            state["request"]
            + "\n\n[Design Architecture - source of truth]\n"
            + json.dumps(state.get("agent_architecture") or {}, ensure_ascii=False, indent=2)
            + "\n\n[As-Built Architecture - actual code evidence]\n"
            + json.dumps(compact_as_built, ensure_ascii=False, indent=2)
            + "\n\n[Architecture Conformance mismatches]\n"
            + json.dumps(conformance.get("mismatches") or [], ensure_ascii=False, indent=2)
            + "\n\n[File Plan]\n"
            + json.dumps(state.get("file_plan") or {}, ensure_ascii=False, indent=2)
            + "\n\nDesign과 실제 구현의 차이만 보정하십시오. "
            "missing_required_file은 반드시 create_file=true로 생성하고, missing_component는 component_file_map의 실제 파일에 구현하십시오. "
            "이미 검증된 기능을 삭제하거나 전체 프로젝트를 불필요하게 재작성하지 마십시오. "
            "Workflow/LangGraph/DB/MCP 계약은 확정 설계를 유지하십시오. 수정 후 정적 As-Built 분석에서 증거가 확인되도록 실제 코드를 구현하십시오."
            + three_d_editor_instruction
            + code_documentation_instruction
            + user_coding_style_instruction
        )
        try:
            plan = await create_patch(
                patch_request,
                files,
                state.get("provider"),
                project_scope=True,
            )
        except Exception as exc:
            return {
                "plan": {"changes": []},
                "repair_plan_validation": {
                    "ok": False,
                    "repair_type": "architecture_conformance",
                    "error": f"{type(exc).__name__}: {exc}",
                },
                "status": "ARCHITECTURE_REPAIR_PLAN_FAILED",
                "error": f"{type(exc).__name__}: {exc}",
            }
        plan = _normalize_patch_plan(
            plan,
            state["project_root"],
            _required_manifest_paths(state),
        )
        changes = list(plan.get("changes") or []) if isinstance(plan, dict) else []
        repair_validation = {
            "ok": bool(changes),
            "repair_type": "architecture_conformance",
            "mismatch_count": len(conformance.get("mismatches") or []),
            "planned_change_count": len(changes),
            "score_before": conformance.get("score"),
        }
        if not changes:
            return {
                "plan": plan,
                "repair_plan_validation": repair_validation,
                "status": "ARCHITECTURE_REPAIR_PLAN_INCOMPLETE",
                "error": "Architecture Conformance Repair가 필요한 코드 변경을 제안하지 못했습니다.",
            }
        code_plan_validation = {
            "ok": True,
            "repair_type": "architecture_conformance",
            "planned_change_count": len(changes),
        }

    elif test_repair_mode:
        try:
            plan, repair_validation = await _focused_test_failure_repair_plan(
                state,
                latest_debug,
            )
        except Exception as exc:
            return {
                "plan": {"changes": []},
                "repair_plan_validation": {
                    "ok": False,
                    "repair_type": "test_failure",
                    "error": f"{type(exc).__name__}: {exc}",
                },
                "status": "TEST_REPAIR_PLAN_FAILED",
                "error": f"{type(exc).__name__}: {exc}",
            }

        if not repair_validation.get("ok"):
            return {
                "plan": plan,
                "repair_plan_validation": repair_validation,
                "status": "TEST_REPAIR_PLAN_INCOMPLETE",
                "error": str(
                    repair_validation.get("error")
                    or "테스트 실패 Focused Repair Plan이 수정 대상 파일을 완전하게 포함하지 못했습니다."
                ),
            }

        code_plan_validation = state.get("code_plan_validation") or _validate_code_plan_manifest(
            state,
            plan,
        )

    elif repair_mode:
        targets = _repair_targets_from_validation(state)
        focused_files = await _read_repair_context(state, targets)
        if focused_files:
            files = focused_files

        repair_attempt = int(state.get("debug_iteration") or 0)
        emergency_repair_instruction = (
            "동일 Placeholder가 이전 Repair 후에도 남아 있습니다. "
            "부분 치환이 아니라 대상 파일의 관련 함수/컴포넌트를 완전한 구현으로 다시 작성하십시오. "
            if repair_attempt >= 2
            else ""
        )

        patch_request = (
            state["request"]
            + "\\n\\n[Agent Factory 확정 설계]\\n"
            + json.dumps(
                build_context,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\\n\\n[이번 Repair 대상만 수정]\\n"
            + json.dumps(
                targets,
                ensure_ascii=False,
                indent=2,
            )
            + "\\n\\n"
            + emergency_repair_instruction
            + "이전 전체 Code Plan을 반복하지 마십시오. "
            "위 missing_files는 반드시 create_file=true로 생성하고, "
            "architecture_errors / placeholder_files / coding_style_errors / code_documentation_errors는 "
            "해당 파일만 실제 수정하십시오. code_documentation_errors는 사용자 선택 설명 주석 정책의 누락이므로 기존 기능을 바꾸지 말고 문서화만 보완하십시오. "
            "placeholder_details의 line/reason/snippet은 검증기가 실제로 발견한 미구현 근거입니다. "
            "해당 미구현 로직을 동작 가능한 구현으로 교체하고 같은 marker가 남지 않게 하십시오. "
            "React/HTML의 placeholder= 속성은 정상 입력 힌트이므로 제거하거나 미구현 코드로 취급하지 마십시오. "
            "이번 Repair 대상에 없는 파일은 changes[]에 포함하지 마십시오. "
            "MCP stdio 요구에서는 Flask/requests/localhost HTTP 서버를 사용하지 마십시오. "
            "기본 LLM은 설정에서 gpt-4o-mini를 읽고 Ollama로 전환 가능해야 하며 "
            "gpt-4를 소스에 직접 하드코딩하지 마십시오. "
            "React + Vite, FastAPI + Uvicorn, MCP stdio 계약을 확정 요구사항 그대로 유지하십시오. "
            "React + TypeScript 요구이면 App.tsx/main.tsx와 분리된 Layout/Header/Sidebar/Footer/Page 구조를 유지하고 .jsx/.js로 후퇴하지 마십시오. "
            "UI Layout Runtime 정책이 있으면 메뉴/탭 이동으로 Agent run을 중단하지 말고 session_id/run_id 기반 Backend Runtime 유지, Frontend 상태 복원, WebSocket/SSE 재연결·run 재조회를 보존하십시오. "
            "Generated Agent Test Environment 정책이 있으면 테스트 데이터 격리, 권한별 테스트 계정, 관리자 impersonation, production 거부 계약을 삭제하거나 약화하지 마십시오."
            + three_d_editor_instruction
            + code_documentation_instruction
            + user_coding_style_instruction
        )

        try:
            plan = await create_patch(
                patch_request,
                files,
                state.get("provider"),
                project_scope=True,
            )
        except Exception as exc:
            return {
                "plan": {"changes": []},
                "status": "CODE_GENERATION_FAILED",
                "error": f"{type(exc).__name__}: {exc}",
                "code_generation_error_type": type(exc).__name__,
            }
        required_paths = _required_manifest_paths(state)
        plan = _normalize_patch_plan(
            plan,
            state["project_root"],
            required_paths,
        )

        required_repair = _repair_required_paths(targets)
        plan = _filter_patch_plan_paths(
            plan,
            state["project_root"],
            required_repair,
            required_paths,
        )
        repair_plan_paths = _patch_plan_paths(
            plan,
            state["project_root"],
        )
        missing_repair = sorted(
            required_repair - repair_plan_paths
        )

        repair_validation = {
            "ok": not missing_repair,
            "repair_target_count": len(required_repair),
            "planned_repair_count": len(repair_plan_paths),
            "missing_repair_targets": missing_repair,
            "targets": targets,
        }

        if missing_repair:
            return {
                "plan": plan,
                "repair_plan_validation": repair_validation,
                "status": "REPAIR_PLAN_INCOMPLETE",
                "error": (
                    "Repair Plan이 실패 원인의 모든 대상 파일을 포함하지 않습니다."
                ),
            }

        code_plan_validation = _validate_code_plan_manifest(
            state,
            plan,
        )

    elif incremental_reuse_mode:
        # No requirement/design change: do not spend another code-generation LLM call.
        # Existing artifacts are still validated, As-Built analyzed and tested below.
        plan = {"changes": []}
        code_plan_validation = _validate_code_plan_manifest(state, plan)
        fastapi_import_validation = _normalize_generated_fastapi_imports(state["project_root"])
        return {
            "plan": plan,
            "patch_result": list(fastapi_import_validation.get("patch_rows") or []),
            "code_plan_validation": {**code_plan_validation, "incremental_mode": "FULL_REUSE", "llm_called": False},
            "fastapi_import_validation": fastapi_import_validation,
            "file_apply_validation": {"ok": True, "verified_count": 0, "incremental_reuse": True},
            "status": "CODE_GENERATED",
        }

    elif incremental_partial_mode:
        focus_paths = _incremental_focus_paths(state, revision)
        root = Path(state["project_root"]).resolve()
        focused_files: dict[str, str] = {}
        for rel in sorted(focus_paths)[:24]:
            path = (root / rel).resolve()
            try:
                path.relative_to(root)
            except ValueError:
                continue
            if path.is_file() and path.stat().st_size <= 768_000:
                focused_files[rel] = path.read_text(encoding="utf-8", errors="replace")
        if focused_files:
            files = focused_files
        change_request = str(revision.get("change_request") or state["request"])
        affected_sections = {
            key: build_context.get(key)
            for key in revision.get("affected_sections") or []
            if key in build_context
        }
        patch_request = (
            "[증분 재작업 - 이번 변경분만]\n" + change_request
            + "\n\n[변경된 요구사항]\n" + json.dumps(revision.get("changed_values") or {}, ensure_ascii=False, indent=2)
            + "\n\n[영향받은 설계 section]\n" + json.dumps(affected_sections, ensure_ascii=False, indent=2)
            + "\n\n[수정 허용/우선 파일]\n" + json.dumps(sorted(focus_paths), ensure_ascii=False, indent=2)
            + "\n\n전체 프로젝트를 처음부터 다시 생성하지 마십시오. 기존 정상 파일은 보존하고 이번 변경에 영향받은 파일만 수정하십시오. "
            "새 설계에서 추가된 required 파일은 생성할 수 있습니다. 변경과 무관한 파일은 changes[]에 넣지 마십시오. "
            "ui_layout 변경분에 실행/상태 유지 설정이 포함되면 기존 Agent Runtime을 UI component lifecycle에 종속시키지 말고, 상태 store·복원·실행 상태 표시·알림·WebSocket/SSE 재연결 정책만 필요한 파일에 증분 반영하십시오. "
            "ui_layout.theme가 custom이면 theme_id/theme_name/theme_tokens/component_rules/layout_rules를 보존하고 기존 Frontend 기술에 맞는 native Theme 방식으로 증분 스타일링하십시오. component_rules.menu.normal/hover/active가 있으면 메뉴 기본·마우스 오버·활성 상태를 반영하고, transition/transform/opacity/filter/boxShadow/textDecoration/fontWeight/padding/borderBottom 및 motionTransition 같은 동작 속성도 존재하는 범위에서 실제 interaction으로 구현하십시오. 원본 animation keyframe 이름 자체를 복제하지 말고 감지된 duration/timing/transform/opacity를 해당 Frontend의 안전한 transition/animation으로 재현하십시오. submenu/user_menu/button/input/card의 hover/focus/open 상태 규칙도 존재하는 범위에서 그대로 반영하십시오. layout_rules.layoutContract.navigation.presentation.mode가 icon_text이거나 sourceNavigationPresentation.mode가 icon_text이면 메뉴를 '아이콘 + 텍스트' 구조로 구현하고 감지된 icon_side/icon_size/gap을 최대한 유지하십시오. 원본 사이트의 독점 SVG path를 복제하지 말고 해당 Frontend의 표준 아이콘 라이브러리 또는 의미상 동등한 일반 아이콘을 사용하십시오. ui_layout.sidebar_menu_icons=true이면 Sidebar와 모바일 Drawer의 각 Navigation 항목을 반드시 '의미상 맞는 표준 아이콘 + 텍스트'로 구현하고, false이면 Theme의 명시적 icon_text 근거가 없는 한 아이콘을 강제하지 마십시오. ui_layout.header_icons=true이면 Header의 상단 Navigation 및 검색·알림·설정 등 주요 Action에 의미상 맞는 표준 아이콘을 배치하고 Hover/Active Theme 상태도 동일하게 적용하십시오. React/Vue/Angular/Svelte/Next/Nuxt/Astro/HTML/Streamlit/Gradio/NiceGUI/Blazor/React Native/Flutter 등 특정 Framework 하나로 강제하지 마십시오. 참조 사이트의 로고·콘텐츠는 복제하지 마십시오. "
            "auth/role/permission/database/상품/주문 변경으로 test_environment_plan이 바뀌면 Seed Data·권한별 테스트 계정·시나리오·관리자 Test-as-user 관련 파일만 함께 증분 반영하십시오."
            + three_d_editor_instruction
            + code_documentation_instruction
            + user_coding_style_instruction
        )
        try:
            plan = await create_patch(patch_request, files, state.get("provider"), project_scope=True)
        except Exception as exc:
            return {
                "plan": {"changes": []},
                "status": "CODE_GENERATION_FAILED",
                "error": f"{type(exc).__name__}: {exc}",
                "code_generation_error_type": type(exc).__name__,
            }
        required_paths = _required_manifest_paths(state)
        plan = _normalize_patch_plan(plan, state["project_root"], required_paths)
        allowed = set(focus_paths) | (required_paths - _existing_project_manifest_paths(state))
        plan = _filter_patch_plan_paths(plan, state["project_root"], allowed, required_paths)
        code_plan_validation = _validate_code_plan_manifest(state, plan)
        code_plan_validation["incremental_mode"] = "PARTIAL_REVISE"
        code_plan_validation["focus_path_count"] = len(focus_paths)
        if not code_plan_validation.get("ok"):
            return {
                "plan": plan,
                "code_plan_validation": code_plan_validation,
                "status": "CODE_PLAN_INCOMPLETE",
                "error": "증분 Code Plan에서 새로 필요한 필수 파일이 누락되었습니다.",
            }

    else:
        patch_request = (
            state["request"]
            + "\\n\\n[Agent Factory 설계 결과]\\n"
            + json.dumps(
                build_context,
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\\n\\n[필수 Code Plan 계약]\\n"
            "file_plan.new_files에서 required=true인 모든 파일을 이번 changes[]에 포함하십시오. "
            "대상 프로젝트에 이미 존재하는 파일은 필요한 경우 수정하고, "
            "존재하지 않는 required 파일은 모두 create_file=true로 생성하십시오. "
            "한두 파일만 생성하고 종료하지 마십시오. "
            "React + Vite가 요구되면 Frontend 전체 실행 골격을 생성하십시오. "
            "React + TypeScript가 확정되면 frontend/src는 .tsx/.ts를 사용하고 App.jsx/main.jsx/api.js를 만들지 마십시오. "
            "package.json에는 TypeScript/Vite/@types/react/@types/react-dom과 build 스크립트를 포함하십시오. "
            "App.tsx에는 화면 전체 구현을 몰아넣지 말고 Route/Page/Layout 조립만 두며, "
            "AppLayout, TopHeader, Sidebar, Footer, pages, services, types, styles로 기능을 분리하십시오. "
            "FastAPI가 요구되면 main/router/schema/service/config/dependency/test 골격을 생성하십시오. "
            "backend/app 구조에서는 SYSTEM_ADMIN이 backend 폴더에서 uvicorn app.main:app을 실행하므로 내부 import는 from app.routers..., from app.services...처럼 app.* 또는 올바른 상대 import를 사용하고 from routers... 또는 from backend.app...를 혼용하지 마십시오. "
            "MCP stdio 요구에서는 Flask/requests 기반 localhost HTTP 서버로 대체하지 마십시오. "
            "기본 모델/Provider는 환경설정에서 읽고 gpt-4를 직접 하드코딩하지 마십시오. "
            "10MB/120초/Chunking 등 인터뷰 확정값도 구현하십시오. "
            "AgentStudio Coding Style Registry의 선택 규칙을 생성 코드에 적용하십시오. "
            "confirmed_requirements.ui_layout이 선택되어 있으면 메뉴/탭/Route 전환과 Frontend View/Component lifecycle이 Agent run의 cancel/stop과 연결되지 않게 하십시오. "
            "custom Theme이 선택되어 있으면 ui_layout.theme_tokens/component_rules/layout_rules를 canonical Design Token으로 유지한 뒤 확정된 Frontend Framework의 native Theme 방식으로 변환하여 Header/Navigation/Card/Button/Form/Table/Modal 등 공통 UI에 일관되게 적용하십시오. component_rules.menu.normal/hover/active가 있으면 메뉴 기본·마우스 오버·활성 상태를 모두 구현하고 transition/transform/opacity/filter/boxShadow/textDecoration/fontWeight/padding/borderBottom/motionTransition을 실제 interaction CSS/컴포넌트 상태에 반영하십시오. 원본 사이트의 animation keyframe 이름을 그대로 복제하지 말고 감지된 duration/timing/transform/opacity를 프로젝트의 native transition/animation으로 재현하십시오. submenu/user_menu/button/input/card의 상태 규칙도 존재하는 경우 실제 interaction CSS/컴포넌트 상태로 구현하십시오. layout_rules.layoutContract.navigation.presentation.mode가 icon_text이거나 sourceNavigationPresentation.mode가 icon_text이면 Navigation/Sidebar/모바일 Drawer의 항목을 '아이콘 + 텍스트' 구조로 생성하고 감지된 icon_side/icon_size/gap을 반영하십시오. 원본의 고유 SVG artwork는 복사하지 말고 프로젝트에서 사용하는 표준 아이콘 세트 또는 의미상 동등한 일반 아이콘으로 매핑하십시오. ui_layout.sidebar_menu_icons=true이면 Sidebar/모바일 Drawer Navigation에 아이콘+텍스트를 반드시 생성하고 아이콘은 메뉴 의미에 맞게 매핑하십시오. ui_layout.header_icons=true이면 Header Navigation과 검색·알림·설정 등 주요 Header Action에 표준 아이콘을 생성하십시오. 두 옵션이 false이면 Theme에 명시된 icon_text 근거가 없는 영역에는 아이콘을 임의로 강제하지 마십시오. React 전용 Theme Provider나 CSS 변수 방식으로 고정하지 마십시오. "
            + frontend_theme_generation_instruction((state.get("request") or "") + "\n" + json.dumps(build_context, ensure_ascii=False)) + " "
            "Agent Runtime은 Backend session_id/run_id 기반으로 UI lifecycle과 분리하고, Frontend는 실행 상태 store와 상태 재조회/재연결로 복원하십시오. "
            "restore_screen_state/restore_scroll_position/restore_draft_input/restore_selection_state/screen_restore_mode와 show_running_tasks/runtime_status_position/알림 설정을 실제 UI 코드에 반영하십시오. "
            "WebSocket/SSE가 끊겼다가 다시 연결되면 현재 run 상태를 재조회하고 누락된 진행 이벤트를 재동기화하도록 구현하십시오. "
            "test_environment_plan.enabled=true이면 생성 Agent의 관리자 기능에 DEV/TEST 전용 테스트 환경을 실제 구현하십시오. "
            "Seed Data 생성/초기화/삭제, 데이터 현황, 수량 변경, 시나리오 실행, 결과/로그를 제공하고 is_test/test_batch_id로 운영 데이터와 격리하십시오. "
            "로그인/회원 기능이 있으면 기본 테스트 회원 10명을 지원하고 Role/Permission이 있으면 plan.role_test_accounts의 모든 Role별 테스트 계정과 허용/거부 Permission 검증을 구현하십시오. "
            "관리자는 각 테스트 계정의 '이 권한으로 테스트' 기능으로 short-lived impersonation을 시작/종료할 수 있어야 하며 모든 전환을 감사 로그에 남기고 TEST 배너를 표시하십시오. "
            "production에서는 seed/reset/delete/impersonation을 Backend에서 반드시 거부하고 테스트 비밀번호를 소스에 하드코딩하지 마십시오. "
            "상품 도메인이 있으면 기본 상품 50개 및 카테고리/재고, 주문 기능이 있으면 주문 Seed를 plan 수량대로 연계 생성하십시오."
            + development_stage_instruction
            + three_d_generation_instruction
            + code_documentation_instruction
            + user_coding_style_instruction
        )

        try:
            plan = await create_patch(
                patch_request,
                files,
                state.get("provider"),
                project_scope=True,
            )
        except Exception as exc:
            return {
                "plan": {"changes": []},
                "status": "CODE_GENERATION_FAILED",
                "error": f"{type(exc).__name__}: {exc}",
                "code_generation_error_type": type(exc).__name__,
            }
        plan = _normalize_patch_plan(
            plan,
            state["project_root"],
            _required_manifest_paths(state),
        )

        # v5.162: required 파일 수가 많아도 한 번의 거대한 LLM 응답에 의존하지 않고
        # 작은 배치로 반복 보강하여 Code Plan을 완성합니다.
        plan, code_plan_validation = await _complete_code_plan_manifest(
            state,
            plan,
            files,
        )

        if not code_plan_validation["ok"]:
            remaining = len(
                code_plan_validation.get("missing_required_paths") or []
            )
            rounds = int(
                code_plan_validation.get("supplement_rounds") or 0
            )
            return {
                "plan": plan,
                "code_plan_validation": code_plan_validation,
                "status": "CODE_PLAN_INCOMPLETE",
                "error": (
                    "Code Generation Plan 자동 보강 후에도 "
                    f"required 파일 {remaining}개가 누락되어 있습니다. "
                    f"자동 보강 {rounds}회 수행 후 파일 적용을 중단했습니다."
                ),
            }

    stdio_plan_validation = _validate_stdio_code_plan(
        state,
        plan,
    )

    if not stdio_plan_validation["ok"]:
        return {
            "plan": plan,
            "code_plan_validation": code_plan_validation,
            "stdio_plan_validation": stdio_plan_validation,
            "status": "CODE_PLAN_ARCHITECTURE_FAILED",
            "error": (
                "MCP stdio 확정 요구와 충돌하는 Flask/HTTP 구현이 "
                "Code Plan에 포함되어 실제 파일 적용을 중단했습니다."
            ),
        }

    patch_apply_recoveries: list[dict] = []
    try:
        # v5.170: exact old 문자열이 stale해졌더라도 즉시 전체 Workflow를 실패시키지 않고
        # 안전한 whitespace/idempotent 적용 후, 필요한 경우 해당 파일만 focused recovery합니다.
        result, patch_apply_recoveries = await _apply_patch_with_focused_recovery(
            state,
            plan,
            max_recoveries=2,
        )
    except PatchApplyError as exc:
        return {
            "plan": plan,
            "patch_result": list(exc.partial_results or []),
            "code_plan_validation": code_plan_validation,
            "file_apply_validation": {
                "ok": False,
                "error": str(exc),
                "failure": exc.to_dict(),
                "focused_recoveries": patch_apply_recoveries,
            },
            "status": "FILE_APPLY_FAILED",
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "plan": plan,
            "patch_result": [],
            "code_plan_validation": code_plan_validation,
            "file_apply_validation": {
                "ok": False,
                "error": str(exc),
                "focused_recoveries": patch_apply_recoveries,
            },
            "status": "FILE_APPLY_FAILED",
            "error": str(exc),
        }

    # v5.174: FastAPI 내부 import를 Generated SYSTEM_ADMIN 실행 계약과 일치시킵니다.
    # backend cwd + uvicorn app.main:app을 기준으로 app.* import를 사용하도록 정규화합니다.
    fastapi_import_validation = _normalize_generated_fastapi_imports(state["project_root"])
    result.extend(fastapi_import_validation.get("patch_rows") or [])
    if not fastapi_import_validation.get("ok"):
        return {
            "plan": plan,
            "patch_result": result,
            "code_plan_validation": code_plan_validation,
            "fastapi_import_validation": fastapi_import_validation,
            "status": "FASTAPI_IMPORT_CONTRACT_FAILED",
            "error": "FastAPI 내부 import 경로가 SYSTEM_ADMIN 실행 계약과 일치하지 않습니다.",
        }

    unverified = [
        row
        for row in result
        if not row.get("verified")
    ]

    if unverified:
        return {
            "plan": plan,
            "patch_result": result,
            "code_plan_validation": code_plan_validation,
            "file_apply_validation": {
                "ok": False,
                "unverified": unverified,
            },
            "status": "FILE_APPLY_FAILED",
            "error": "Patch 결과 중 실제 파일 검증에 실패한 항목이 있습니다.",
        }

    return {
        "plan": plan,
        "patch_result": result,
        "code_plan_validation": code_plan_validation,
        "repair_plan_validation": (
            repair_validation
            if (architecture_repair_mode or repair_mode or test_repair_mode)
            else {}
        ),
        "fastapi_import_validation": fastapi_import_validation,
        "architecture_repair_iteration": (
            int(state.get("architecture_repair_iteration") or 0) + 1
            if architecture_repair_mode
            else int(state.get("architecture_repair_iteration") or 0)
        ),
        "file_apply_validation": {
            "ok": True,
            "verified_count": len(result),
            "focused_recoveries": patch_apply_recoveries,
            "recovery_count": len(patch_apply_recoveries),
            "replacement_strategies": [
                {
                    "path": row.get("path"),
                    "strategies": row.get("replacement_strategies") or [],
                }
                for row in result
                if row.get("replacement_strategies")
            ],
        },
        "status": "CODE_GENERATED",
    }



def route_after_code_generation(
    state: AgentState,
) -> Literal["settings_generator", "end"]:
    return (
        "settings_generator"
        if state.get("status") == "CODE_GENERATED"
        else "end"
    )


async def settings_generator_node(state: AgentState):
    try:
        result = await generate_settings_artifacts(
            project_root=state["project_root"],
            request=state["request"],
            settings_plan=state.get("settings_plan") or {},
            file_plan=state.get("file_plan") or {},
            provider=state.get("provider"),
        )
    except Exception as exc:
        return {
            "settings_generation_result": {
                "enabled": bool((state.get("settings_plan") or {}).get("enabled")),
                "changes": [],
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            },
            "status": "SETTINGS_GENERATION_FAILED",
            "error": f"{type(exc).__name__}: {exc}",
        }

    existing_changes = list(state.get("patch_result") or [])
    settings_changes = list(result.get("changes") or [])

    return {
        "settings_generation_result": result,
        "patch_result": existing_changes + settings_changes,
        "status": "SETTINGS_GENERATED",
    }


def route_after_settings_generator(
    state: AgentState,
) -> Literal["settings_validation", "end"]:
    return (
        "settings_validation"
        if state.get("status") == "SETTINGS_GENERATED"
        else "end"
    )


async def settings_validation_node(state: AgentState):
    result = await validate_settings_artifacts(
        project_root=state["project_root"],
        settings_plan=state.get("settings_plan") or {},
    )

    return {
        "settings_validation_result": result,
        "status": (
            "SETTINGS_VALIDATED"
            if result.get("ok")
            else "SETTINGS_VALIDATION_FAILED"
        ),
    }


def route_after_settings_validation(
    state: AgentState,
) -> Literal["environment_configuration", "debug"]:
    return (
        "environment_configuration"
        if state.get("status") == "SETTINGS_VALIDATED"
        else "debug"
    )


def _planned_required_paths(
    project_root: str,
    file_plan: dict,
) -> list[Path]:
    root = Path(project_root).resolve()
    result = []

    for item in file_plan.get("new_files") or []:
        if isinstance(item, str):
            relative = item
            required = True
        elif isinstance(item, dict):
            relative = str(item.get("path") or "")
            required = bool(item.get("required", True))
        else:
            continue

        if not required or not relative.strip():
            continue

        target = (root / relative).resolve()
        if root != target and root not in target.parents:
            continue
        result.append(target)

    return result


def _placeholder_findings(content: str, suffix: str = "") -> list[dict]:
    """
    실제 미구현 흔적만 Placeholder로 판정합니다.

    v5.168까지는 소스 어디에든 ``placeholder``라는 단어가 있으면 실패했기 때문에
    React의 ``<input placeholder="..." />`` 같은 정상 UI 속성도 미완성 코드로
    오인했습니다. 이제는 주석/미구현 예외/빈 함수처럼 실행 의미가 있는 흔적과
    명시적인 구현 대기 문구만 검출합니다.
    """
    text = str(content or "")
    ext = str(suffix or "").casefold()
    findings: list[dict] = []
    seen: set[tuple[int, str]] = set()

    def add(line_no: int, reason: str, snippet: str) -> None:
        key = (int(line_no), reason)
        if key in seen:
            return
        seen.add(key)
        findings.append({
            "line": int(line_no),
            "reason": reason,
            "snippet": str(snippet).strip()[:240],
        })

    # 언어와 관계없이 명시적인 구현 대기 주석/문구를 찾습니다.
    comment_patterns = (
        (re.compile(r"\bTODO\s*:", re.IGNORECASE), "TODO marker"),
        (re.compile(r"\bFIXME\s*:", re.IGNORECASE), "FIXME marker"),
        (re.compile(r"여기에\s*구현|구현\s*예정|추후\s*구현", re.IGNORECASE), "implementation pending marker"),
        (re.compile(r"implement(?:ation)?\b.{0,40}\bhere\b", re.IGNORECASE), "implementation pending marker"),
        (re.compile(r"placeholder\s+(?:for|implementation|logic|code|actual)", re.IGNORECASE), "placeholder implementation marker"),
        (re.compile(r"summary of the file content", re.IGNORECASE), "stub summary marker"),
    )

    for line_no, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        lowered = stripped.casefold()

        # JSX/HTML의 placeholder= 속성은 정상 UI 입력 힌트이므로 제외합니다.
        if re.search(r"\bplaceholder\s*=", stripped, flags=re.IGNORECASE):
            # 같은 줄에 TODO/FIXME 같은 별도 미구현 주석이 있으면 아래에서 다시 잡힙니다.
            ui_placeholder_only = True
        else:
            ui_placeholder_only = False

        for pattern, reason in comment_patterns:
            if ui_placeholder_only and reason == "placeholder implementation marker":
                continue
            if pattern.search(stripped):
                add(line_no, reason, stripped)

        if "notimplementederror" in lowered:
            add(line_no, "NotImplementedError", stripped)

    # Python은 AST로 함수/메서드 본문 자체가 pass 또는 ...뿐인 진짜 stub도 검출합니다.
    if ext == ".py":
        try:
            import ast

            tree = ast.parse(text)
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                body = list(node.body or [])
                if len(body) != 1:
                    continue
                stmt = body[0]
                is_stub = isinstance(stmt, ast.Pass)
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                    is_stub = is_stub or stmt.value.value is Ellipsis
                if is_stub:
                    add(
                        int(getattr(stmt, "lineno", getattr(node, "lineno", 1))),
                        "empty function body",
                        f"def {getattr(node, 'name', '<function>')}(...): <stub>",
                    )
        except (SyntaxError, ValueError, TypeError):
            # 문법 오류는 이후 compile/test 단계에서 정확히 진단합니다.
            pass

    return findings


def _looks_like_placeholder(content: str, suffix: str = "") -> bool:
    return bool(_placeholder_findings(content, suffix))


async def build_artifact_validation_node(state: AgentState):
    # v5.370: React + TypeScript 계약에서는 App.jsx/main.jsx/api.js가 내용이 비어 있어도
    # 존재 자체가 Architecture 오류입니다. LLM Repair가 빈 파일로 만드는 우회 대신
    # 검증 전에 legacy entry를 결정적으로 삭제합니다.
    react_ts_cleanup = _cleanup_react_typescript_legacy_sources(state)

    # v5.174: Settings Generator까지 끝난 최종 backend/app 코드도 다시 정규화합니다.
    fastapi_import_validation = _normalize_generated_fastapi_imports(state["project_root"])
    existing_patch_rows = list(state.get("patch_result") or [])
    seen_patch_keys = {
        (str(row.get("path") or "").casefold(), str(row.get("reason") or ""))
        for row in existing_patch_rows
        if isinstance(row, dict)
    }
    for row in react_ts_cleanup.get("patch_rows") or []:
        key = (str(row.get("path") or "").casefold(), str(row.get("reason") or ""))
        if key not in seen_patch_keys:
            existing_patch_rows.append(row)
            seen_patch_keys.add(key)
    for row in fastapi_import_validation.get("patch_rows") or []:
        key = (str(row.get("path") or "").casefold(), str(row.get("reason") or ""))
        if key not in seen_patch_keys:
            existing_patch_rows.append(row)
            seen_patch_keys.add(key)

    file_plan = state.get("file_plan") or {}
    required_paths = _planned_required_paths(
        state["project_root"],
        file_plan,
    )

    missing = []
    placeholder_files = []
    placeholder_details = []
    style_failures = []
    style_warnings = []
    code_documentation_errors = []
    code_documentation_warnings = []
    documentation_policy = _code_documentation_policy(state)
    user_coding_style_policy = _user_coding_style_policy(state)
    checked = []

    for path in required_paths:
        if not path.is_file():
            missing.append(str(path))
            continue

        suffix = path.suffix.casefold()
        if suffix not in {
            ".py", ".js", ".jsx", ".ts", ".tsx", ".cs", ".java", ".vue", ".svelte", ".astro", ".dart", ".razor", ".cshtml",
            ".md", ".json", ".txt", ".html", ".css", ".scss", ".sass", ".less", ".yml", ".yaml",
        }:
            continue

        try:
            content = path.read_text(
                encoding="utf-8",
                errors="replace",
            )
        except OSError:
            continue

        checked.append(str(path))

        if suffix in {".py", ".js", ".jsx", ".ts", ".tsx"}:
            placeholder_findings = _placeholder_findings(content, suffix)
            if placeholder_findings:
                placeholder_files.append(str(path))
                placeholder_details.append({
                    "path": str(path),
                    "findings": placeholder_findings,
                })

            validation = validate_code_style(
                code=content,
                request=state["request"],
                path=str(path),
                project_scope=True,
            )

            for item in validation.get("violations") or []:
                row = {
                    **item,
                    "path": str(path),
                }
                if str(item.get("severity") or "").casefold() == "error":
                    style_failures.append(row)
                else:
                    style_warnings.append(row)

        if documentation_policy.get("enabled") and suffix in {".py", ".js", ".jsx", ".ts", ".tsx", ".cs", ".java"}:
            findings = _code_documentation_findings(content, suffix)
            if findings.get("missing_symbols"):
                code_documentation_errors.append({
                    "path": str(path),
                    "message": "사용자가 설명 주석 생성을 선택했지만 공개 클래스/함수/메소드 설명이 누락되었습니다.",
                    "missing_symbols": list(findings.get("missing_symbols") or [])[:30],
                })
            if findings.get("missing_variables"):
                code_documentation_warnings.append({
                    "path": str(path),
                    "message": "주요 상수/변수 설명 주석을 추가하면 유지보수성이 좋아집니다.",
                    "missing_variables": list(findings.get("missing_variables") or [])[:30],
                })

    architecture_errors = []
    for violation in fastapi_import_validation.get("violations") or []:
        architecture_errors.append({
            "path": str(Path(state["project_root"]) / str(violation.get("path") or "")),
            "message": (
                "FastAPI 내부 import 경로가 Generated SYSTEM_ADMIN 실행 계약과 일치하지 않습니다: "
                + str(violation.get("snippet") or "")
            ),
            "line": violation.get("line"),
        })
    contracts = _requirement_contracts(state)
    root = Path(state["project_root"]).resolve()

    if not react_ts_cleanup.get("ok", True):
        architecture_errors.append({
            "path": str(react_ts_cleanup.get("path") or root / "frontend/src"),
            "message": (
                "React + TypeScript legacy JavaScript entry 자동 정리에 실패했습니다: "
                + str(react_ts_cleanup.get("error") or "unknown cleanup error")
            ),
        })

    source_suffixes = {
        ".py", ".js", ".jsx", ".ts", ".tsx", ".cs", ".java", ".vue", ".svelte", ".astro", ".dart", ".razor", ".cshtml",
        ".json", ".md", ".txt", ".html", ".css", ".scss", ".sass", ".less",
    }

    actual_source_files = []
    if root.exists():
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                relative = path.relative_to(root)
            except ValueError:
                continue
            if relative.parts and relative.parts[0].casefold() in {
                "reports", "debug", "logs", "venv", ".venv",
                "node_modules", ".git",
            }:
                continue
            if path.suffix.casefold() in source_suffixes:
                actual_source_files.append(path)

    if contracts["stdio"]:
        stdio_forbidden = [
            "from flask",
            "import flask",
            "requests.post",
            "requests.get",
            "localhost:5000",
            "127.0.0.1:5000",
            "app.run(",
        ]

        for path in actual_source_files:
            relative = path.relative_to(root).as_posix().casefold()
            if not (
                "mcp" in relative
                or relative.endswith("server.py")
            ):
                continue

            text = path.read_text(
                encoding="utf-8",
                errors="replace",
            ).casefold()

            found = [
                token
                for token in stdio_forbidden
                if token in text
            ]

            if found:
                architecture_errors.append({
                    "path": str(path),
                    "message": (
                        "MCP stdio 요구인데 HTTP/Flask 구현이 감지되었습니다: "
                        + ", ".join(found)
                    ),
                })

    if contracts["gpt_4o_mini"]:
        hardcoded_gpt4_patterns = [
            "model_name='gpt-4'",
            'model_name="gpt-4"',
            "model='gpt-4'",
            'model="gpt-4"',
        ]

        for path in actual_source_files:
            if path.suffix.casefold() != ".py":
                continue

            text = path.read_text(
                encoding="utf-8",
                errors="replace",
            ).casefold()

            found = [
                pattern
                for pattern in hardcoded_gpt4_patterns
                if pattern in text
            ]

            if found:
                architecture_errors.append({
                    "path": str(path),
                    "message": (
                        "확정 기본 모델은 gpt-4o-mini이고 Provider/Model은 설정값이어야 합니다. "
                        "gpt-4 직접 하드코딩이 감지되었습니다."
                    ),
                })

    if contracts["fastapi"]:
        fastapi_required = [
            root / "backend/app/main.py",
            root / "backend/app/routers/summary.py",
            root / "backend/app/schemas/summary.py",
            root / "backend/app/services/summary_service.py",
            root / "backend/app/services/llm_service.py",
            root / "backend/app/core/config.py",
        ]

        for path in fastapi_required:
            if not path.is_file() and str(path) not in missing:
                missing.append(str(path))

    if contracts["react"]:
        ext = "tsx" if contracts["react_typescript"] else "jsx"
        service_ext = "ts" if contracts["react_typescript"] else "js"
        react_required = [
            root / "frontend/package.json",
            root / "frontend/index.html",
            root / f"frontend/src/main.{ext}",
            root / f"frontend/src/App.{ext}",
            root / f"frontend/src/layouts/AppLayout.{ext}",
            root / f"frontend/src/components/layout/TopHeader.{ext}",
            root / f"frontend/src/components/layout/Sidebar.{ext}",
            root / f"frontend/src/components/layout/Footer.{ext}",
            root / f"frontend/src/pages/HomePage.{ext}",
            root / f"frontend/src/services/api.{service_ext}",
            root / "frontend/src/styles/global.css",
        ]
        if contracts["react_typescript"]:
            react_required.extend([
                root / "frontend/tsconfig.json",
                root / "frontend/vite.config.ts",
                root / "frontend/src/types/index.ts",
            ])

        for path in react_required:
            if not path.is_file() and str(path) not in missing:
                missing.append(str(path))

        app_entry = root / f"frontend/src/App.{ext}"
        if app_entry.is_file():
            app_text = app_entry.read_text(encoding="utf-8", errors="replace")
            app_lines = len(app_text.splitlines())
            if app_lines > 220:
                architecture_errors.append({
                    "path": str(app_entry),
                    "message": (
                        f"App.{ext}가 {app_lines}줄입니다. App은 Route/Layout 조립만 담당하고 "
                        "Header/Sidebar/Footer/Page/Feature UI는 별도 파일로 분리해야 합니다."
                    ),
                })
            required_import_tokens = ("AppLayout", "HomePage")
            missing_imports = [token for token in required_import_tokens if token not in app_text]
            if missing_imports:
                architecture_errors.append({
                    "path": str(app_entry),
                    "message": (
                        "App 진입 파일이 분리된 Layout/Page를 조립하지 않습니다: "
                        + ", ".join(missing_imports)
                    ),
                })

        if contracts["react_typescript"]:
            forbidden = [
                root / "frontend/src/App.jsx",
                root / "frontend/src/main.jsx",
                root / "frontend/src/services/api.js",
            ]
            for path in forbidden:
                if path.is_file():
                    architecture_errors.append({
                        "path": str(path),
                        "message": "React + TypeScript 확정 요구에서 .jsx/.js Frontend entry가 생성되었습니다.",
                    })

            package_path = root / "frontend/package.json"
            if package_path.is_file():
                try:
                    package = json.loads(package_path.read_text(encoding="utf-8", errors="replace"))
                except Exception as exc:
                    architecture_errors.append({
                        "path": str(package_path),
                        "message": f"package.json 파싱 실패: {type(exc).__name__}: {exc}",
                    })
                else:
                    deps = {**(package.get("dependencies") or {}), **(package.get("devDependencies") or {})}
                    required_packages = {"typescript", "@types/react", "@types/react-dom", "vite"}
                    missing_packages = sorted(required_packages - set(deps))
                    if missing_packages:
                        architecture_errors.append({
                            "path": str(package_path),
                            "message": (
                                "React + TypeScript build 의존성이 누락되었습니다: "
                                + ", ".join(missing_packages)
                            ),
                        })
                    scripts = package.get("scripts") or {}
                    if not scripts.get("build"):
                        architecture_errors.append({
                            "path": str(package_path),
                            "message": "React + TypeScript Agent는 npm run build 스크립트가 필요합니다.",
                        })


    ok = (
        not missing
        and not placeholder_files
        and not style_failures
        and not architecture_errors
        and not code_documentation_errors
    )

    result = {
        "ok": ok,
        "required_count": len(required_paths),
        "checked_files": checked,
        "missing_files": missing,
        "placeholder_files": placeholder_files,
        "placeholder_details": placeholder_details,
        "coding_style_errors": style_failures,
        "coding_style_warnings": style_warnings,
        "code_documentation_policy": documentation_policy,
        "user_coding_style_policy": user_coding_style_policy,
        "code_documentation_errors": code_documentation_errors,
        "code_documentation_warnings": code_documentation_warnings,
        "architecture_errors": architecture_errors,
        "react_typescript_legacy_cleanup": react_ts_cleanup,
        "fastapi_import_validation": fastapi_import_validation,
        "selected_rule_ids": [
            rule.get("id")
            for rule in (
                state.get("coding_style_context", {}).get("rules") or []
            )
        ],
    }

    if ok:
        return {
            "build_artifact_validation": result,
            "fastapi_import_validation": fastapi_import_validation,
            "patch_result": existing_patch_rows,
            "status": "BUILD_ARTIFACTS_VALIDATED",
        }

    iteration = int(state.get("debug_iteration") or 0) + 1
    history = list(state.get("debug_history") or [])
    history.append({
        "type": "build_artifact_validation",
        "diagnosis": "계획된 Agent 산출물 또는 Coding Style 검증이 완료되지 않았습니다.",
        "missing_files": missing,
        "placeholder_files": placeholder_files,
        "placeholder_details": placeholder_details,
        "coding_style_errors": style_failures,
        "coding_style_warnings": style_warnings,
        "code_documentation_errors": code_documentation_errors,
        "code_documentation_warnings": code_documentation_warnings,
        "architecture_errors": architecture_errors,
        "should_retry": True,
    })

    def _signature(row: dict) -> str:
        return json.dumps(
            {
                "missing_files": sorted(row.get("missing_files") or []),
                "placeholder_files": sorted(row.get("placeholder_files") or []),
                "placeholder_details": row.get("placeholder_details") or [],
                "coding_style_errors": [
                    {
                        "path": item.get("path"),
                        "rule_id": item.get("rule_id"),
                        "message": item.get("message"),
                    }
                    for item in row.get("coding_style_errors") or []
                ],
                "architecture_errors": [
                    {
                        "path": item.get("path"),
                        "message": item.get("message"),
                    }
                    for item in row.get("architecture_errors") or []
                ],
                "code_documentation_errors": [
                    {
                        "path": item.get("path"),
                        "message": item.get("message"),
                        "missing_symbols": item.get("missing_symbols") or [],
                    }
                    for item in row.get("code_documentation_errors") or []
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    current_signature = _signature(history[-1])
    previous_same = sum(
        1
        for row in history[:-1]
        if isinstance(row, dict)
        and row.get("type") == "build_artifact_validation"
        and _signature(row) == current_signature
    )

    # v5.169: 정확한 줄 근거를 전달하는 focused repair를 최대 2회 허용합니다.
    # 같은 실패가 3번째 검증까지 유지될 때만 stall로 중단합니다.
    if previous_same >= 2:
        return {
            "build_artifact_validation": result,
            "fastapi_import_validation": fastapi_import_validation,
            "patch_result": existing_patch_rows,
            "debug_iteration": iteration,
            "debug_history": history,
            "status": "BUILD_ARTIFACT_STALLED",
            "error": (
                "동일한 산출물 검증 실패가 반복되었습니다. "
                "동일 Repair를 무한 반복하지 않고 중단합니다. "
                "실패 진단의 placeholder_details에서 실제 미구현 줄을 확인하십시오."
            ),
        }

    return {
        "build_artifact_validation": result,
        "fastapi_import_validation": fastapi_import_validation,
        "patch_result": existing_patch_rows,
        "debug_iteration": iteration,
        "debug_history": history,
        "status": "DEBUG_PATCH_READY",
    }


def route_after_build_artifact_validation(
    state: AgentState,
) -> Literal["as_built_architecture", "code_generation", "end"]:
    if state.get("status") == "BUILD_ARTIFACTS_VALIDATED":
        return "as_built_architecture"

    if (
        state.get("status") == "DEBUG_PATCH_READY"
        and int(state.get("debug_iteration") or 0)
        <= get_settings().max_debug_iterations
    ):
        return "code_generation"

    return "end"


async def environment_configuration_node(state: AgentState):
    """
    환경 파일 자체의 생성/수정은 code_generation에서 file_plan에 따라 처리합니다.
    이 Node는 생성 대상 Agent의 환경 요구가 State에 명시적으로 남았는지 확인합니다.
    """
    environment = (
        _bundle(state).get("environment_plan")
        or state.get("environment_plan")
        or {}
    )

    return {
        "environment_plan": environment,
        "status": "ENVIRONMENT_CONFIGURED",
    }


_PRETEST_SOURCE_SUFFIXES = {'.py', '.js', '.jsx', '.ts', '.tsx', '.vue', '.svelte', '.astro', '.dart', '.razor', '.cshtml', '.json', '.sql', '.sh', '.ps1', '.html', '.css', '.scss', '.sass', '.less'}


async def _repair_wrapped_generated_source_files(project_root: str) -> list[dict]:
    """Deterministically repair source files accidentally saved as Markdown blocks.

    This runs immediately before validation, so both newly generated files and a
    partially failed project from an earlier AgentStudio version can recover
    without spending another Debug LLM iteration.
    """
    root = Path(project_root).resolve()
    rows: list[dict] = []
    if not root.exists():
        return rows
    for path in root.rglob('*'):
        if not path.is_file() or path.suffix.casefold() not in _PRETEST_SOURCE_SUFFIXES:
            continue
        try:
            relative = path.relative_to(root).as_posix()
        except ValueError:
            continue
        if _is_runtime_artifact_path(project_root, relative):
            continue
        try:
            current = await read_file(str(path))
            repaired, changed = _strip_outer_markdown_fence_for_source(path, current)
            if not changed:
                continue
            await write_file(str(path), repaired)
            verified = await read_file(str(path))
            if verified != repaired:
                continue
            rows.append({
                'path': str(path),
                'changed': True,
                'created': False,
                'verified': True,
                'bytes': path.stat().st_size,
                'reason': '소스 전체를 감싼 Markdown 코드 펜스를 테스트 전에 결정적으로 제거했습니다.',
                'replacement_strategies': ['pretest_outer_markdown_fence_removed'],
            })
        except Exception:
            continue
    return rows


async def test_node(state: AgentState):
    environment = state.get("environment_plan") or {}

    commands = list(environment.get("validation_commands") or [])
    cmd = state.get("test_command")

    if not cmd and commands:
        cmd = str(commands[0])

    cmd = cmd or "python -m compileall ."

    pretest_repairs = await _repair_wrapped_generated_source_files(state["project_root"])
    result = await run_command(
        cmd,
        state["project_root"],
    )

    update = {
        "test_result": result,
        "pretest_source_repair": pretest_repairs,
        "status": (
            "TEST_PASSED"
            if result.get("returncode") == 0
            else "TEST_FAILED"
        ),
    }
    if pretest_repairs:
        update["patch_result"] = list(state.get("patch_result") or []) + pretest_repairs
    return update


def route_after_test(
    state: AgentState,
) -> Literal["package_completion", "debug", "end"]:
    if state.get("status") == "TEST_PASSED":
        return "package_completion"

    # Build Artifact Repair 횟수와 실제 Test Debug 횟수를 분리합니다.
    # 이전 Placeholder 복구가 debug_iteration을 소비해도 테스트 수정 기회는 별도로 보장합니다.
    test_debug_count = _debug_history_count(state, "test_failure")

    if test_debug_count < get_settings().max_debug_iterations:
        return "debug"

    return "end"


async def _collect_validation_fallback(state: AgentState) -> dict:
    """Collect deterministic local evidence when AI debug tooling is unavailable.

    v5.392 intentionally separates provider/sandbox infrastructure failures from
    generated-project failures.  The fallback never edits source files: it lists
    the workspace, records Codex runtime diagnostics, and runs conservative local
    validation commands so DEBUG/Repair can use a real traceback when possible.
    """
    root = Path(state.get("project_root") or "").expanduser().resolve()
    collected_at = __import__("datetime").datetime.now().astimezone().isoformat()
    files: list[str] = []
    if root.exists():
        excluded = {".git", ".venv", "venv", "node_modules", "logs", "reports", "debug", "__pycache__"}
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                rel = path.relative_to(root)
            except ValueError:
                continue
            if any(part.casefold() in excluded for part in rel.parts[:-1]):
                continue
            files.append(rel.as_posix())
            if len(files) >= 5000:
                break

    commands: list[str] = []
    requested = str(state.get("test_command") or "").strip()
    environment = state.get("environment_plan") or {}
    if not requested:
        validation_commands = [str(x).strip() for x in (environment.get("validation_commands") or []) if str(x).strip()]
        requested = validation_commands[0] if validation_commands else ""
    if requested:
        commands.append(requested)

    has_python = any(path.casefold().endswith(".py") for path in files)
    if has_python and all("compileall" not in cmd.casefold() for cmd in commands):
        commands.append("python -m compileall .")

    package_json = root / "package.json"
    if package_json.is_file() and all("npm run build" not in cmd.casefold() for cmd in commands):
        # --if-present is read-only with respect to source and does not install packages.
        commands.append("npm run build --if-present")

    # Keep fallback bounded; the original requested command has priority.
    commands = commands[:3]
    command_results: list[dict] = []
    for command in commands:
        try:
            result = await run_command(command, str(root))
            command_results.append({
                "command": command,
                "cwd": str(root),
                "returncode": result.get("returncode"),
                "output": str(result.get("output") or "")[-20000:],
                "execution_error": "",
            })
        except Exception as exc:
            command_results.append({
                "command": command,
                "cwd": str(root),
                "returncode": None,
                "output": "",
                "execution_error": f"{type(exc).__name__}: {exc}",
                "winerror": getattr(exc, "winerror", None),
                "errno": getattr(exc, "errno", None),
            })

    git_status: dict = {}
    if (root / ".git").exists():
        try:
            result = await run_command("git status --short", str(root))
            git_status = {
                "returncode": result.get("returncode"),
                "output": str(result.get("output") or "")[-12000:],
            }
        except Exception as exc:
            git_status = {
                "returncode": None,
                "output": "",
                "execution_error": f"{type(exc).__name__}: {exc}",
                "winerror": getattr(exc, "winerror", None),
            }

    codex_status: dict = {}
    try:
        codex_status = codex_app_server_manager.status()
    except Exception as exc:
        codex_status = {"status_error": f"{type(exc).__name__}: {exc}"}

    codex_runtime_error = dict(codex_status.get("last_runtime_error") or {})
    sandbox_blocked = bool(codex_runtime_error.get("sandbox_infrastructure_failure"))
    if not sandbox_blocked:
        probe = " ".join([
            str(codex_runtime_error.get("message") or ""),
            " ".join(str(x) for x in (codex_status.get("stderr_tail") or [])),
        ]).casefold()
        sandbox_blocked = any(token in probe for token in (
            "codex-windows-sandbox-setup", "windows sandbox helper", "sandbox helper",
        ))

    primary = next((row for row in command_results if row.get("returncode") not in (None, 0)), None)
    if primary is None and command_results:
        primary = command_results[0]

    return {
        "collected_at": collected_at,
        "project_root": str(root),
        "project_exists": root.exists(),
        "actual_file_count": len(files),
        "sample_files": files[:200],
        "commands": command_results,
        "primary_result": primary or {},
        "git_status": git_status,
        "codex": {
            "path": codex_status.get("path"),
            "version": codex_status.get("version"),
            "last_command": codex_status.get("last_command") or [],
            "last_error": codex_status.get("last_error") or "",
            "last_runtime_error": codex_runtime_error,
            "stderr_tail": codex_status.get("stderr_tail") or [],
        },
        "sandbox_infrastructure_blocked": sandbox_blocked,
    }


async def debug_node(state: AgentState):
    iteration = int(state.get("debug_iteration") or 0) + 1
    source_status = str(state.get("status") or "")
    debug_type = (
        "test_failure"
        if source_status == "TEST_FAILED"
        else "settings_validation_failure"
        if source_status == "SETTINGS_VALIDATION_FAILED"
        else "workflow_failure"
    )
    source_iteration = _debug_history_count(state, debug_type) + 1

    fallback: dict = {}
    if not (state.get("test_result") or {}) or source_status == "SETTINGS_VALIDATION_FAILED":
        fallback = await _collect_validation_fallback(state)

    primary_fallback = fallback.get("primary_result") or {}
    effective_test_output = str((state.get("test_result") or {}).get("output") or "")
    if not effective_test_output:
        effective_test_output = str(primary_fallback.get("output") or primary_fallback.get("execution_error") or "")
    if source_status == "SETTINGS_VALIDATION_FAILED":
        settings_detail = json.dumps(state.get("settings_validation_result") or {}, ensure_ascii=False, indent=2)
        effective_test_output = (
            effective_test_output
            + "\n\n[AgentStudio Settings Validation]\n"
            + settings_detail
        ).strip()

    try:
        analysis = await analyze_failure(
            original_request=state["request"],
            test_output=effective_test_output,
            previous_patch=state.get("plan") or {},
            iteration=source_iteration,
            provider=state.get("provider"),
        )
        analysis["type"] = debug_type
        analysis["source_status"] = source_status
        analysis["repair_attempt"] = source_iteration
        if fallback:
            analysis["validation_fallback"] = fallback
    except Exception as exc:
        blocked = bool(fallback.get("sandbox_infrastructure_blocked"))
        return {
            "debug_iteration": iteration,
            "validation_fallback": fallback,
            "status": "VALIDATION_BLOCKED" if blocked else "DEBUG_ANALYSIS_FAILED",
            "error": (
                "Agent 코드 실패로 판정하지 않았습니다. Codex/검증 인프라가 차단되어 로컬 fallback 진단까지만 수행했습니다. "
                if blocked else
                "로컬 로그 분석/Ollama 연결 실패가 원래 검증 실패를 WORKFLOW_EXCEPTION으로 덮어쓰지 않도록 중단했습니다. "
            ) + f"{type(exc).__name__}: {exc}",
        }

    history = list(state.get("debug_history") or [])
    history.append(analysis)

    if not analysis.get("should_retry", True):
        infrastructure_blocked = bool(fallback.get("sandbox_infrastructure_blocked"))
        fallback_commands = fallback.get("commands") or []
        fallback_execution_blocked = bool(fallback_commands) and all(
            row.get("returncode") is None and bool(row.get("execution_error"))
            for row in fallback_commands
            if isinstance(row, dict)
        )
        blocked = infrastructure_blocked or fallback_execution_blocked
        status = "VALIDATION_BLOCKED" if blocked else "DEBUG_STOPPED"
        error = analysis.get("diagnosis", "디버그 에이전트가 중단을 결정했습니다.")
        if blocked:
            error = (
                "Agent 생성 파일은 존재하지만 생성 후 검증이 완료되지 않았습니다. "
                "프로젝트 코드 결함과 검증 인프라 문제를 분리하여 VALIDATION_BLOCKED로 종료합니다. "
                + str(error or "")
            )
        return {
            "debug_iteration": iteration,
            "debug_history": history,
            "validation_fallback": fallback,
            "status": status,
            "error": error,
        }

    return {
        "debug_iteration": iteration,
        "debug_history": history,
        "validation_fallback": fallback,
        "status": "DEBUG_PATCH_READY",
    }


def route_after_debug(
    state: AgentState,
) -> Literal["code_generation", "end"]:
    return (
        "code_generation"
        if state.get("status") == "DEBUG_PATCH_READY"
        else "end"
    )


def _generated_system_admin_cmd() -> str:
    return '@echo off\nsetlocal EnableExtensions\nchcp 65001 >nul\ntitle THEANOVA Generated Agent - System Manager\n\ncd /d "%~dp0"\n\npowershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0SYSTEM_ADMIN.ps1"\nset "EXITCODE=%ERRORLEVEL%"\n\necho.\necho ============================================================\nif "%EXITCODE%"=="0" (\n    echo [COMPLETED] Agent program started successfully.\n) else if "%EXITCODE%"=="2" (\n    echo [SETUP_REQUIRED] Initial settings are not complete.\n    echo Review the opened .env.example guide. AgentStudio does not create or modify .env.\n    echo Put real values in your existing .env or environment variables, then run SYSTEM_ADMIN.cmd again.\n) else (\n    echo [FAILED] SYSTEM_ADMIN failed. ExitCode=%EXITCODE%\n)\necho ============================================================\necho.\necho This window will remain open.\necho.\npause\n\nendlocal\nexit /b %EXITCODE%\n'


def _generated_system_admin_ps1() -> str:
    return r'''$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeRoot = Join-Path $Root ".agentstudio"
$RuntimeDir = Join-Path $RuntimeRoot "runtime"
$LogDir = Join-Path $RuntimeRoot "logs"
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$VenvDir = Join-Path $Root ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$BackendPidFile = Join-Path $RuntimeDir "backend.pid"
$FrontendPidFile = Join-Path $RuntimeDir "frontend.pid"
$SystemLog = Join-Path $LogDir "system_admin.log"
$BackendOut = Join-Path $LogDir "backend.out.log"
$BackendErr = Join-Path $LogDir "backend.err.log"
$BackendImportOut = Join-Path $LogDir "backend_import.out.log"
$BackendImportErr = Join-Path $LogDir "backend_import.err.log"
$FrontendOut = Join-Path $LogDir "frontend.out.log"
$FrontendErr = Join-Path $LogDir "frontend.err.log"
$SetupManifest = Join-Path $RuntimeRoot "setup_requirements.json"
$EnvFile = Join-Path $Root ".env"
$BackendEnvFile = Join-Path $BackendDir ".env"
$EnvExample = Join-Path $Root ".env.example"

New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Log {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"), $Message
    Add-Content -Path $SystemLog -Value $line -Encoding UTF8
}

function Write-Step {
    param([string]$Message)
    Write-Host "[진행] $Message"
    Write-Log "진행: $Message"
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[완료] $Message" -ForegroundColor Green
    Write-Log "완료: $Message"
}

function Read-EnvValues {
    param([string[]]$Paths)
    $values = @{}
    foreach ($path in $Paths) {
        if (-not (Test-Path $path)) { continue }
        foreach ($line in Get-Content $path -ErrorAction SilentlyContinue) {
            $trimmed = [string]$line
            if ([string]::IsNullOrWhiteSpace($trimmed)) { continue }
            $trimmed = $trimmed.Trim()
            if ($trimmed.StartsWith("#") -or -not $trimmed.Contains("=")) { continue }
            $parts = $trimmed.Split("=", 2)
            $key = $parts[0].Trim()
            if (-not $key) { continue }
            $value = if ($parts.Count -gt 1) { $parts[1].Trim().Trim('"').Trim("'") } else { "" }
            $values[$key] = $value
        }
    }
    return $values
}

function Test-SetupValueReady {
    param([string]$Value)
    $v = [string]$Value
    if ([string]::IsNullOrWhiteSpace($v)) { return $false }
    $normalized = $v.Trim().ToLowerInvariant()
    return -not ($normalized -in @(
        "your-key-here", "change-me", "changeme", "todo", "null", "none",
        "your-password", "your-token", "replace-me", "<required>"
    ))
}

function Get-EnvExampleValue {
    param([string]$Key)
    $upper = ([string]$Key).ToUpperInvariant()
    switch -Regex ($upper) {
        '^DATABASE_URL$' { return 'postgresql://postgres:YOUR_PASSWORD@127.0.0.1:5432/YOUR_DATABASE' }
        '^POSTGRES_URL$' { return 'postgresql://postgres:YOUR_PASSWORD@127.0.0.1:5432/YOUR_DATABASE' }
        '^REDIS_URL$' { return 'redis://127.0.0.1:6379/0' }
        '^OLLAMA_BASE_URL$' { return 'http://127.0.0.1:11434' }
        '^OPENAI_API_KEY$' { return 'YOUR_OPENAI_API_KEY' }
        'API_KEY$' { return 'YOUR_API_KEY' }
        'PASSWORD$' { return 'YOUR_PASSWORD' }
        'TOKEN$' { return 'YOUR_TOKEN' }
        '^APP_HOST$' { return '127.0.0.1' }
        '^APP_PORT$' { return '8000' }
        default { return '<REQUIRED_VALUE>' }
    }
}

function Ensure-EnvExampleRequirements {
    param([string]$Path, [object[]]$Required)
    if (-not (Test-Path $Path)) {
        $initial = @(
            '# THEANOVA Generated Agent environment guide',
            '# 이 파일은 예시/설명용입니다. 실제 비밀번호/API Key를 저장하지 마세요.',
            '# 실제 값은 사용자가 직접 만든 .env 또는 OS 환경변수에 설정하세요.',
            '# SYSTEM_ADMIN.cmd는 .env 파일을 생성하거나 수정하지 않습니다.',
            ''
        )
        [System.IO.File]::WriteAllLines($Path, $initial, $Utf8NoBom)
    }

    $lines = @(Get-Content $Path -ErrorAction SilentlyContinue)
    $known = @{}
    foreach ($line in $lines) {
        if ([string]$line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=') {
            $known[$matches[1].ToUpperInvariant()] = $true
        }
    }

    $result = New-Object System.Collections.Generic.List[string]
    foreach ($line in $lines) { $result.Add([string]$line) }
    if ($result.Count -gt 0 -and -not [string]::IsNullOrWhiteSpace([string]$result[$result.Count - 1])) { $result.Add('') }

    foreach ($item in $Required) {
        $key = ([string]$item.key).Trim()
        if (-not $key) { continue }
        $upper = $key.ToUpperInvariant()
        if ($known.ContainsKey($upper)) { continue }
        $label = [string]$item.label
        $reason = [string]$item.reason
        if (-not $label) { $label = $key }
        $example = Get-EnvExampleValue $upper
        $result.Add(('# {0} ({1})' -f $label, $key))
        if ($reason) { $result.Add(('# 용도: {0}' -f $reason)) }
        if ($upper -eq 'DATABASE_URL' -or $upper -eq 'POSTGRES_URL') {
            $result.Add('# 형식: postgresql://사용자:비밀번호@호스트:포트/데이터베이스명')
            $result.Add('# 로컬 예시: postgresql://postgres:YOUR_PASSWORD@127.0.0.1:5432/YOUR_DATABASE')
        }
        elseif ($upper -eq 'REDIS_URL') {
            $result.Add('# 형식: redis://호스트:포트/DB번호')
            $result.Add('# 로컬 예시: redis://127.0.0.1:6379/0')
        }
        elseif ($upper -eq 'OPENAI_API_KEY') {
            $result.Add('# 예시: OPENAI_API_KEY=YOUR_OPENAI_API_KEY')
        }
        $result.Add(('{0}={1}' -f $key, $example))
        $result.Add('')
        $known[$upper] = $true
    }
    [System.IO.File]::WriteAllLines($Path, $result, $Utf8NoBom)
}

function Ensure-EnvSetupGuides {
    param([string]$Path)
    if (-not (Test-Path $Path)) { return }
    $lines = @(Get-Content $Path -ErrorAction SilentlyContinue)
    if ($lines.Count -eq 0) { return }

    $dbGuideMarker = '# DATABASE_URL 입력 방법 (PostgreSQL)'
    if (($lines -contains $dbGuideMarker) -or -not ($lines -match '^\s*DATABASE_URL\s*=')) {
        return
    }

    $result = New-Object System.Collections.Generic.List[string]
    $inserted = $false
    foreach ($line in $lines) {
        if (-not $inserted -and ([string]$line -match '^\s*DATABASE_URL\s*=')) {
            $result.Add($dbGuideMarker)
            $result.Add('# 형식: postgresql://사용자:비밀번호@호스트:포트/데이터베이스명')
            $result.Add('# 로컬 예시: postgresql://postgres:YOUR_PASSWORD@127.0.0.1:5432/YOUR_DATABASE')
            $result.Add('# 실제 값은 .env.example이 아니라 사용자가 관리하는 .env 또는 OS 환경변수에 설정하세요.')
            $inserted = $true
        }
        $result.Add([string]$line)
    }
    [System.IO.File]::WriteAllLines($Path, $result, $Utf8NoBom)
}

function Test-InitialConfiguration {
    if (-not (Test-Path $SetupManifest)) {
        Write-Ok "초기 설정 Manifest 없음 - 별도 필수 설정 없이 실행 가능"
        return $true
    }

    try {
        $manifest = Get-Content $SetupManifest -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        throw "초기 설정 Manifest를 읽을 수 없습니다: $SetupManifest"
    }

    $required = @($manifest.required_env)
    if ($required.Count -eq 0) {
        Write-Ok "필수 초기 설정 항목 없음"
        return $true
    }

    # v5.377: 사용자의 .env는 AgentStudio가 절대 생성/수정하지 않습니다.
    # 필요한 Key와 입력 예시는 .env.example에만 보강하고, 실제 값은 기존 .env,
    # backend/.env 또는 OS 환경변수에서 읽습니다.
    Ensure-EnvExampleRequirements $EnvExample $required
    Ensure-EnvSetupGuides $EnvExample

    $values = Read-EnvValues @($EnvFile, $BackendEnvFile)
    $missing = @()
    foreach ($item in $required) {
        $key = [string]$item.key
        if (-not $key) { continue }
        $value = if ($values.ContainsKey($key)) { [string]$values[$key] } else { "" }
        if (-not (Test-SetupValueReady $value)) {
            $processValue = [Environment]::GetEnvironmentVariable($key, "Process")
            if (-not (Test-SetupValueReady $processValue)) {
                $userValue = [Environment]::GetEnvironmentVariable($key, "User")
                if (Test-SetupValueReady $userValue) { $value = $userValue }
            }
            else { $value = $processValue }
        }
        if (-not (Test-SetupValueReady $value)) {
            $missing += $item
        }
    }

    if ($missing.Count -eq 0) {
        Write-Ok "초기 설정 확인"
        return $true
    }

    Write-Host ""
    Write-Host "[SETUP_REQUIRED] Agent 실행 전 기본 설정이 필요합니다." -ForegroundColor Yellow
    Write-Host "FastAPI/Frontend를 시작하거나 app.main을 import하지 않습니다." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "미설정 필수 항목:"
    foreach ($item in $missing) {
        $label = [string]$item.label
        $key = [string]$item.key
        if (-not $label) { $label = $key }
        Write-Host (" - {0} ({1})" -f $label, $key)
    }
    $missingKeys = @($missing | ForEach-Object { ([string]$_.key).ToUpperInvariant() })
    if ($missingKeys -contains "DATABASE_URL") {
        Write-Host ""
        Write-Host "DATABASE_URL 입력 가이드:" -ForegroundColor Cyan
        Write-Host " - 형식: postgresql://사용자:비밀번호@호스트:포트/데이터베이스명"
        Write-Host " - 로컬 예시: postgresql://postgres:YOUR_PASSWORD@127.0.0.1:5432/postgres"
        Write-Host " - YOUR_PASSWORD와 DB 이름을 실제 PostgreSQL 환경에 맞게 변경하세요."
    }
    Write-Host ""
    Write-Host "설정 가이드: $EnvExample" -ForegroundColor Cyan
    Write-Host "실제 설정: 사용자가 관리하는 .env / backend\.env / OS 환경변수" -ForegroundColor Cyan
    Write-Host "AgentStudio는 .env 파일을 생성하거나 수정하지 않습니다." -ForegroundColor Yellow
    Write-Host ".env.example의 예시를 참고해 실제 값을 설정한 후 SYSTEM_ADMIN.cmd를 다시 실행하세요."
    Write-Log ("SETUP_REQUIRED: " + (($missing | ForEach-Object { $_.key }) -join ", "))

    try { Start-Process notepad.exe -ArgumentList @($EnvExample) | Out-Null } catch { }
    return $false
}

function Stop-PidFileProcess {
    param([string]$PidFile)
    if (-not (Test-Path $PidFile)) { return }
    try {
        $SavedPid = [int](Get-Content $PidFile -ErrorAction Stop | Select-Object -First 1)
        if ($SavedPid -gt 0) {
            & taskkill.exe /PID $SavedPid /T /F 2>$null | Out-Null
        }
    }
    catch { }
    Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
}

function Test-Port {
    param([int]$Port)
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iar = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne(700, $false)
        if ($ok -and $client.Connected) {
            $client.EndConnect($iar)
            $client.Close()
            return $true
        }
        $client.Close()
    }
    catch { }
    return $false
}

function Wait-Port {
    param([int]$Port, [int]$Retry = 40)
    for ($i = 0; $i -lt $Retry; $i++) {
        if (Test-Port $Port) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return $false
}

function Ensure-Python312 {
    if (Test-Path $VenvPython) { return }

    Write-Step "Python 3.12 가상환경(.venv) 생성"
    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) {
        & $py.Source -3.12 -c "import sys; assert sys.version_info[:2] == (3, 12)"
        if ($LASTEXITCODE -eq 0) {
            & $py.Source -3.12 -m venv $VenvDir
            if ($LASTEXITCODE -eq 0) { return }
        }
    }

    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        & $python.Source -c "import sys; assert sys.version_info[:2] == (3, 12)"
        if ($LASTEXITCODE -eq 0) {
            & $python.Source -m venv $VenvDir
            if ($LASTEXITCODE -eq 0) { return }
        }
    }

    throw "Python 3.12를 찾을 수 없습니다. Python 3.12 설치 후 다시 실행하세요."
}

function Ensure-BackendDependencies {
    $Req = Join-Path $BackendDir "requirements.txt"
    if (-not (Test-Path $Req)) { $Req = Join-Path $Root "requirements.txt" }
    if (-not (Test-Path $Req)) { return }

    $hash = (Get-FileHash $Req -Algorithm SHA256).Hash
    $marker = Join-Path $RuntimeDir "backend_requirements.sha256"
    $old = if (Test-Path $marker) { Get-Content $marker -ErrorAction SilentlyContinue | Select-Object -First 1 } else { "" }
    if ($old -eq $hash) {
        Write-Ok "Backend 패키지 확인"
        return
    }

    Write-Step "Backend 패키지 설치"
    & $VenvPython -m pip install -r $Req
    if ($LASTEXITCODE -ne 0) { throw "Backend 패키지 설치 실패" }
    Set-Content -Path $marker -Value $hash -Encoding ASCII
    Write-Ok "Backend 패키지 설치"
}

function Ensure-FrontendDependencies {
    $PackageJson = Join-Path $FrontendDir "package.json"
    if (-not (Test-Path $PackageJson)) { return }
    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $npm) { throw "Node.js/npm을 찾을 수 없습니다." }

    $hash = (Get-FileHash $PackageJson -Algorithm SHA256).Hash
    $marker = Join-Path $RuntimeDir "frontend_package.sha256"
    $old = if (Test-Path $marker) { Get-Content $marker -ErrorAction SilentlyContinue | Select-Object -First 1 } else { "" }
    $modules = Join-Path $FrontendDir "node_modules"
    if ((Test-Path $modules) -and $old -eq $hash) {
        Write-Ok "Frontend 패키지 확인"
        return
    }

    Write-Step "Frontend 패키지 설치"
    $p = Start-Process -FilePath $npm.Source -ArgumentList @("install") -WorkingDirectory $FrontendDir -Wait -PassThru -NoNewWindow
    if ($p.ExitCode -ne 0) { throw "Frontend npm install 실패" }
    Set-Content -Path $marker -Value $hash -Encoding ASCII
    Write-Ok "Frontend 패키지 설치"
}

function Test-BackendImport {
    $Main = Join-Path $BackendDir "app\main.py"
    if (-not (Test-Path $Main)) { return }

    Write-Step "FastAPI import 경로 사전 검증 (app.main:app)"
    Remove-Item $BackendImportOut, $BackendImportErr -Force -ErrorAction SilentlyContinue
    $probe = Start-Process -FilePath $VenvPython -ArgumentList @(
        "-c",
        "import importlib; m=importlib.import_module('app.main'); assert hasattr(m, 'app'), 'FastAPI app instance missing'"
    ) -WorkingDirectory $BackendDir -Wait -PassThru -NoNewWindow -RedirectStandardOutput $BackendImportOut -RedirectStandardError $BackendImportErr
    if ($probe.ExitCode -ne 0) {
        throw "FastAPI import 검증 실패(app.main:app). 생성 코드의 app.* import를 확인하세요. 로그: $BackendImportErr"
    }
    Write-Ok "FastAPI import 경로 검증"
}

function Start-Backend {
    $Main = Join-Path $BackendDir "app\main.py"
    if (-not (Test-Path $Main)) { return $false }

    Stop-PidFileProcess $BackendPidFile
    $BackendPort = 8000
    Write-Step "FastAPI Backend 시작 (127.0.0.1:$BackendPort)"
    $p = Start-Process -FilePath $VenvPython -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort") -WorkingDirectory $BackendDir -RedirectStandardOutput $BackendOut -RedirectStandardError $BackendErr -PassThru
    Set-Content -Path $BackendPidFile -Value $p.Id -Encoding ASCII
    if (-not (Wait-Port $BackendPort 40)) { throw "Backend가 시작되지 않았습니다. 로그: $BackendErr" }
    Write-Ok "FastAPI Backend 시작"
    return $true
}

function Test-McpReady {
    $McpServer = Join-Path $Root "mcp_server\server.py"
    if (-not (Test-Path $McpServer)) { return }
    Write-Step "MCP stdio Server 준비 상태 확인"
    & $VenvPython -m py_compile $McpServer
    if ($LASTEXITCODE -ne 0) { throw "MCP Server 문법 검증 실패: $McpServer" }
    Write-Ok "MCP stdio Server 준비 완료 (필요할 때 Agent가 stdio로 실행)"
}

function Start-Frontend {
    $PackageJson = Join-Path $FrontendDir "package.json"
    if (-not (Test-Path $PackageJson)) { return $false }
    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $npm) { throw "Node.js/npm을 찾을 수 없습니다." }

    Stop-PidFileProcess $FrontendPidFile
    $FrontendPort = 5173
    Write-Step "React/Vite Frontend 시작 (127.0.0.1:$FrontendPort)"
    $p = Start-Process -FilePath $npm.Source -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "$FrontendPort") -WorkingDirectory $FrontendDir -RedirectStandardOutput $FrontendOut -RedirectStandardError $FrontendErr -PassThru
    Set-Content -Path $FrontendPidFile -Value $p.Id -Encoding ASCII
    if (-not (Wait-Port $FrontendPort 60)) { throw "Frontend가 시작되지 않았습니다. 로그: $FrontendErr" }
    Write-Ok "React/Vite Frontend 시작"
    return $true
}

try {
    Write-Host ""
    Write-Host "============================================================"
    Write-Host "THEANOVA Generated Agent 시작"
    Write-Host "============================================================"
    Write-Host "프로젝트: $Root"
    Write-Host ""
    Write-Log "SYSTEM_ADMIN 시작"

    # v5.345: Configuration gate comes before dependency install/import/runtime.
    # A generated Agent with DB/Redis/LLM secrets not configured must never import
    # app.main just to discover a connection/config error.
    if (-not (Test-InitialConfiguration)) {
        exit 2
    }

    Ensure-Python312
    Ensure-BackendDependencies
    Ensure-FrontendDependencies
    Test-BackendImport
    Test-McpReady

    $backendStarted = Start-Backend
    $frontendStarted = Start-Frontend

    if (-not $backendStarted -and -not $frontendStarted) {
        throw "실행 가능한 Backend 또는 Frontend entrypoint를 찾지 못했습니다."
    }

    if ($frontendStarted) {
        Start-Process "http://127.0.0.1:5173"
        Write-Host "[URL] http://127.0.0.1:5173" -ForegroundColor Cyan
    }
    elseif ($backendStarted) {
        Start-Process "http://127.0.0.1:8000/docs"
        Write-Host "[URL] http://127.0.0.1:8000/docs" -ForegroundColor Cyan
    }

    Write-Host ""
    Write-Host "[COMPLETED] 전체 프로그램 실행이 완료되었습니다." -ForegroundColor Green
    Write-Host "로그 폴더: $LogDir"
    Write-Log "SYSTEM_ADMIN 완료"
    exit 0
}
catch {
    Write-Host ""
    Write-Host "[FAILED] $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "로그 폴더: $LogDir"
    Write-Log "실패: $($_.Exception.ToString())"
    exit 1
}
'''

def _build_generated_setup_manifest(
    project_root: str,
    settings_plan: dict | None = None,
    database_plan: dict | None = None,
    environment_plan: dict | None = None,
    requirement_spec: dict | None = None,
) -> dict:
    settings_plan = settings_plan if isinstance(settings_plan, dict) else {}
    database_plan = database_plan if isinstance(database_plan, dict) else {}
    environment_plan = environment_plan if isinstance(environment_plan, dict) else {}
    requirement_spec = requirement_spec if isinstance(requirement_spec, dict) else {}
    required: dict[str, dict] = {}

    def add(key: str, label: str = "", category: str = "", secret: bool = False, reason: str = ""):
        key = str(key or "").strip()
        if not key:
            return
        required[key] = {
            "key": key,
            "label": str(label or key),
            "category": str(category or "runtime"),
            "secret": bool(secret),
            "reason": str(reason or "Agent 실행 전 필요한 초기 설정"),
        }

    for category in settings_plan.get("categories") or []:
        if not isinstance(category, dict):
            continue
        category_label = str(category.get("label") or category.get("id") or "settings")
        for field in category.get("fields") or []:
            if not isinstance(field, dict):
                continue
            if not field.get("required"):
                continue
            if str(field.get("storage") or "env").casefold() != "env":
                continue
            default = field.get("default")
            if default not in (None, "", []):
                continue
            add(
                field.get("key"),
                field.get("label"),
                category_label,
                bool(field.get("secret")),
                field.get("description") or "필수 Settings 값",
            )

    for item in environment_plan.get("env_vars") or []:
        if isinstance(item, str):
            continue
        if not isinstance(item, dict) or not item.get("required"):
            continue
        if item.get("default") not in (None, "", []):
            continue
        add(
            item.get("key") or item.get("name"),
            item.get("label") or item.get("name") or item.get("key"),
            "environment",
            bool(item.get("secret")),
            item.get("description") or "필수 환경변수",
        )

    # If the DB is part of the finalized architecture but the LLM omitted a required
    # settings field, use an existing .env.example DB connection key as a safe gate.
    root = Path(project_root).resolve()
    env_example = root / ".env.example"
    example_keys: list[str] = []
    if env_example.is_file():
        for line in env_example.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = stripped.split("=", 1)
            if not value.strip():
                example_keys.append(key.strip())

    if database_plan.get("enabled") and not any(
        any(token in key.upper() for token in ("DATABASE", "POSTGRES", "PG"))
        for key in required
    ):
        db_candidates = [
            key for key in example_keys
            if (
                key.upper() in {
                    "DATABASE_URL", "POSTGRES_URL", "PG_DSN", "PGHOST", "PGPORT",
                    "PGDATABASE", "PGUSER", "PGPASSWORD", "DB_HOST", "DB_PORT",
                    "DB_NAME", "DB_USER", "DB_PASSWORD",
                }
                or key.upper().startswith("POSTGRES_")
            )
        ]
        preferred = [key for key in db_candidates if key.upper() in {"DATABASE_URL", "POSTGRES_URL", "PG_DSN"}]
        if preferred:
            add(preferred[0], "PostgreSQL 연결", "database", False, "DB 사용 Agent의 초기 연결 설정")
        elif db_candidates:
            for key in db_candidates:
                add(
                    key,
                    "PostgreSQL " + key,
                    "database",
                    any(token in key.upper() for token in ("PASSWORD", "SECRET")),
                    "DB 사용 Agent의 초기 연결 설정",
                )
        else:
            # The design finalized a DB but the generated .env.example omitted a key.
            # Force a setup stop instead of importing FastAPI with an unknown DB state.
            add(
                "DATABASE_URL",
                "PostgreSQL 연결 URL",
                "database",
                True,
                "DB 사용 Agent는 첫 Runtime 전에 연결 정보를 설정해야 합니다.",
            )

    runtime_requirement_text = json.dumps(
        {
            "environment": environment_plan,
            "requirements": requirement_spec,
            "settings": settings_plan,
            "database": database_plan,
        },
        ensure_ascii=False,
    ).casefold()
    if "redis" in runtime_requirement_text and not any("REDIS" in key.upper() for key in required):
        redis_candidates = [key for key in example_keys if "REDIS" in key.upper()]
        preferred = [key for key in redis_candidates if "URL" in key.upper() or "DSN" in key.upper()]
        if preferred:
            add(preferred[0], "Redis 연결", "redis", False, "Redis 사용 Agent의 초기 연결 설정")
        elif redis_candidates:
            for key in redis_candidates:
                add(
                    key,
                    "Redis " + key,
                    "redis",
                    any(token in key.upper() for token in ("PASSWORD", "SECRET", "TOKEN")),
                    "Redis 사용 Agent의 초기 연결 설정",
                )
        else:
            add(
                "REDIS_URL",
                "Redis 연결 URL",
                "redis",
                True,
                "Redis 사용 Agent는 첫 Runtime 전에 연결 정보를 설정해야 합니다.",
            )

    # If an OpenAI-backed target explicitly appears but the design omitted a key field,
    # keep the first-run setup safe rather than failing later during app import/start.
    if "openai" in runtime_requirement_text and not any("OPENAI_API_KEY" == key.upper() for key in required):
        openai_candidates = [key for key in example_keys if key.upper() == "OPENAI_API_KEY"]
        if openai_candidates or "api" in runtime_requirement_text:
            add(
                "OPENAI_API_KEY",
                "OpenAI API Key",
                "llm",
                True,
                "OpenAI 사용 Agent의 필수 인증 값",
            )

    return {
        "version": 1,
        "mode": "CONFIG_BEFORE_RUNTIME",
        "required_env": list(required.values()),
        "database_enabled": bool(database_plan.get("enabled")),
        "instructions": [
            "SYSTEM_ADMIN.cmd는 이 필수값이 준비되기 전 FastAPI app.main을 import/start하지 않습니다.",
            "AgentStudio는 .env를 생성/수정하지 않으며, .env.example의 가이드를 참고해 사용자가 직접 .env 또는 OS 환경변수에 값을 설정합니다.",
        ],
    }


def _ensure_generated_system_admin(
    project_root: str,
    settings_plan: dict | None = None,
    database_plan: dict | None = None,
    environment_plan: dict | None = None,
    requirement_spec: dict | None = None,
) -> dict:
    root = Path(project_root).resolve()
    cmd_path = root / "SYSTEM_ADMIN.cmd"
    ps1_path = root / "SYSTEM_ADMIN.ps1"
    cmd_existed = cmd_path.exists()
    ps1_existed = ps1_path.exists()
    setup_manifest_path = root / ".agentstudio" / "setup_requirements.json"
    setup_manifest_existed = setup_manifest_path.exists()
    setup_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    setup_manifest = _build_generated_setup_manifest(
        project_root=project_root,
        settings_plan=settings_plan,
        database_plan=database_plan,
        environment_plan=environment_plan,
        requirement_spec=requirement_spec,
    )
    setup_manifest_path.write_text(
        json.dumps(setup_manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    cmd_path.write_text(
        _generated_system_admin_cmd(),
        encoding="utf-8",
        newline="\r\n",
    )
    ps1_path.write_text(
        _generated_system_admin_ps1(),
        encoding="utf-8-sig",
        newline="\r\n",
    )

    cmd_check = cmd_path.read_text(encoding="utf-8", errors="replace")
    ps1_check = ps1_path.read_text(encoding="utf-8-sig", errors="replace")
    checks = {
        "cmd_exists": cmd_path.is_file(),
        "ps1_exists": ps1_path.is_file(),
        "utf8_codepage": "chcp 65001" in cmd_check.casefold(),
        "cmd_calls_ps1": "SYSTEM_ADMIN.ps1" in cmd_check,
        "ps1_utf8_bom": ps1_path.read_bytes().startswith(b"\xef\xbb\xbf"),
        "venv_dot_name": '".venv"' in ps1_check,
        "backend_start": "uvicorn" in ps1_check.casefold(),
        "setup_before_runtime": "Test-InitialConfiguration" in ps1_check and ps1_check.index("Test-InitialConfiguration") < ps1_check.index("Test-BackendImport"),
        "setup_exit_code": "exit 2" in ps1_check and "SETUP_REQUIRED" in ps1_check,
        "backend_import_preflight": "FastAPI import 경로 사전 검증" in ps1_check and "importlib.import_module('app.main')" in ps1_check,
        "backend_working_directory": '-WorkingDirectory $BackendDir' in ps1_check and '"app.main:app"' in ps1_check,
        "frontend_start": "npm" in ps1_check.casefold(),
        "mcp_ready_check": "MCP stdio Server" in ps1_check,
        "browser_open": 'Start-Process "http://127.0.0.1:' in ps1_check,
    }
    return {
        "ok": all(checks.values()),
        "files": [str(cmd_path), str(ps1_path), str(setup_manifest_path)],
        "setup_manifest": setup_manifest,
        "setup_manifest_path": str(setup_manifest_path),
        "checks": checks,
        "primary_entrypoint": str(cmd_path),
        "patch_rows": [
            {
                "path": str(cmd_path),
                "changed": True,
                "created": not cmd_existed,
                "verified": True,
                "reason": "AgentStudio 표준 단일 실행 진입점 생성",
            },
            {
                "path": str(ps1_path),
                "changed": True,
                "created": not ps1_existed,
                "verified": True,
                "reason": "SYSTEM_ADMIN Windows 실행 관리자 생성",
            },
            {
                "path": str(setup_manifest_path),
                "changed": True,
                "created": not setup_manifest_existed,
                "verified": True,
                "reason": "FastAPI 실행 전 초기 설정 Gate Manifest 생성",
            },
        ],
    }


async def package_completion_node(state: AgentState):
    changes = list(state.get("patch_result") or [])

    try:
        launcher_result = _ensure_generated_system_admin(
            state["project_root"],
            settings_plan=state.get("settings_plan") or {},
            database_plan=state.get("database_plan") or {},
            environment_plan=state.get("environment_plan") or {},
            requirement_spec=state.get("requirement_spec") or {},
        )
    except Exception as exc:
        return {
            "launcher_generation_result": {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            },
            "status": "LAUNCHER_GENERATION_FAILED",
            "error": f"SYSTEM_ADMIN 생성 실패: {type(exc).__name__}: {exc}",
        }

    if not launcher_result.get("ok"):
        return {
            "launcher_generation_result": launcher_result,
            "status": "LAUNCHER_GENERATION_FAILED",
            "error": "SYSTEM_ADMIN 실행 계약 검증에 실패했습니다.",
        }

    changes.extend(launcher_result.get("patch_rows") or [])

    created = [
        row.get("path")
        for row in changes
        if row.get("created")
    ]

    modified = [
        row.get("path")
        for row in changes
        if row.get("changed") and not row.get("created")
    ]

    package_result = {
        "ok": True,
        "created_files": created,
        "modified_files": modified,
        "test_command": (
            state.get("test_command")
            or "python -m compileall ."
        ),
        "test_returncode": (
            state.get("test_result") or {}
        ).get("returncode"),
        "target_agent_workflow": state.get(
            "target_agent_workflow",
            {},
        ),
        "development_stage_plan": state.get("development_stage_plan", {}),
        "development_workflow": state.get("development_workflow", {}),
        "database_plan": state.get(
            "database_plan",
            {},
        ),
        "environment_plan": state.get(
            "environment_plan",
            {},
        ),
        "settings_plan": state.get(
            "settings_plan",
            {},
        ),
        "test_environment_plan": state.get(
            "test_environment_plan",
            {},
        ),
        "settings_validation": state.get(
            "settings_validation_result",
            {},
        ),
        "build_artifact_validation": state.get(
            "build_artifact_validation",
            {},
        ),
        "design_architecture": state.get("agent_architecture", {}),
        "as_built_architecture": state.get("as_built_architecture", {}),
        "architecture_conformance": state.get("architecture_conformance", {}),
        "launcher_generation": launcher_result,
        "fastapi_import_validation": state.get("fastapi_import_validation", {}),
        "coding_style": {
            "selected_rule_ids": [
                rule.get("id")
                for rule in (
                    state.get("coding_style_context", {}).get("rules") or []
                )
            ],
            "user_preferences": _user_coding_style_policy(state),
            "validation": state.get(
                "build_artifact_validation",
                {},
            ),
        },
    }

    return {
        "package_result": package_result,
        "launcher_generation_result": launcher_result,
        "patch_result": changes,
        "status": "PACKAGE_COMPLETED",
    }


async def review_node(state: AgentState):
    artifact = state.get("build_artifact_validation") or {}
    launcher = state.get("launcher_generation_result") or {}

    if not launcher.get("ok"):
        return {
            "review": "SYSTEM_ADMIN.cmd 자동 실행 진입점 생성/검증이 완료되지 않았습니다.",
            "status": "INCOMPLETE",
            "error": "SYSTEM_ADMIN 실행 진입점 검증 미완료",
        }

    import_contract = state.get("fastapi_import_validation") or {}
    if _requirement_contracts(state).get("fastapi") and not import_contract.get("ok", False):
        return {
            "review": "FastAPI 내부 import 경로 검증이 완료되지 않았습니다.",
            "status": "INCOMPLETE",
            "error": "FastAPI app.* import 실행 계약 검증 미완료",
        }

    if not artifact.get("ok"):
        return {
            "review": (
                "Agent Factory 산출물 검증이 완료되지 않아 "
                "COMPLETED 처리하지 않습니다."
            ),
            "status": "INCOMPLETE",
            "error": "계획 파일/Coding Style 검증 미완료",
        }

    conformance = state.get("architecture_conformance") or {}
    if not conformance.get("ok"):
        return {
            "review": (
                "생성된 실제 Agent의 As-Built Architecture가 Design Architecture와 "
                "일치하지 않아 COMPLETED 처리하지 않습니다."
            ),
            "status": "INCOMPLETE",
            "error": "Architecture Conformance Gate 미통과",
        }

    return {
        "review": (
            "Agent Factory 제작 Workflow가 완료되었습니다. "
            f"생성/수정 파일 {len(state.get('patch_result') or [])}개, "
            f"필수 산출물 {artifact.get('required_count', 0)}개 검증, "
            "SYSTEM_ADMIN.cmd 단일 실행 진입점 생성 완료, "
            f"디버그 반복 {int(state.get('debug_iteration') or 0)}회입니다."
        ),
        "status": "COMPLETED",
    }


_RESUMABLE_WORKFLOW_NODES = {
    "requirement_analysis", "analyze_project", "capability_design",
    "tool_mcp_decision", "agent_architecture", "database_design",
    "target_workflow_design", "project_file_plan", "requirement_coverage_gate",
    "settings_requirement_analysis", "settings_schema_design", "settings_ui_design",
    "checkpoint", "approval", "code_generation", "settings_generator",
    "settings_validation", "build_artifact_validation", "as_built_architecture",
    "architecture_conformance", "environment_configuration", "test", "debug",
    "package_completion", "review",
}


async def resume_entry_router_node(state: AgentState):
    # No state mutation is required. This explicit node makes START routing
    # compatible with both fresh builds and failed-build redevelopment.
    return {}


def route_workflow_entry(state: AgentState) -> str:
    if state.get("resume_mode"):
        node = str(state.get("resume_from_node") or "").strip()
        if node in _RESUMABLE_WORKFLOW_NODES:
            return node
    return "requirement_analysis"


def build_workflow(checkpointer=None):
    graph = StateGraph(AgentState)

    # v5.370: fresh builds and failed-build redevelopment share one graph.
    # A resumed build skips already-completed requirement/design nodes.
    graph.add_node("resume_entry_router", resume_entry_router_node)

    # AgentStudio 제작 Workflow
    graph.add_node(
        "requirement_analysis",
        requirement_analysis_node,
    )
    graph.add_node(
        "analyze_project",
        analyze_project_node,
    )
    graph.add_node(
        "capability_design",
        capability_design_node,
    )
    graph.add_node(
        "tool_mcp_decision",
        tool_mcp_decision_node,
    )
    graph.add_node(
        "agent_architecture",
        agent_architecture_node,
    )
    graph.add_node(
        "database_design",
        database_design_node,
    )
    graph.add_node(
        "target_workflow_design",
        target_workflow_design_node,
    )
    graph.add_node(
        "project_file_plan",
        project_file_plan_node,
    )
    graph.add_node(
        "requirement_coverage_gate",
        requirement_coverage_gate_node,
    )
    graph.add_node(
        "settings_requirement_analysis",
        settings_requirement_analysis_node,
    )
    graph.add_node(
        "settings_schema_design",
        settings_schema_design_node,
    )
    graph.add_node(
        "settings_ui_design",
        settings_ui_design_node,
    )
    graph.add_node(
        "checkpoint",
        checkpoint_node,
    )
    graph.add_node(
        "approval",
        approval_node,
    )
    graph.add_node(
        "code_generation",
        code_generation_node,
    )
    graph.add_node(
        "settings_generator",
        settings_generator_node,
    )
    graph.add_node(
        "settings_validation",
        settings_validation_node,
    )
    graph.add_node(
        "build_artifact_validation",
        build_artifact_validation_node,
    )
    graph.add_node(
        "as_built_architecture",
        as_built_architecture_node,
    )
    graph.add_node(
        "architecture_conformance",
        architecture_conformance_node,
    )
    graph.add_node(
        "environment_configuration",
        environment_configuration_node,
    )
    graph.add_node(
        "test",
        test_node,
    )
    graph.add_node(
        "debug",
        debug_node,
    )
    graph.add_node(
        "package_completion",
        package_completion_node,
    )
    graph.add_node(
        "review",
        review_node,
    )

    graph.add_edge(START, "resume_entry_router")
    graph.add_conditional_edges(
        "resume_entry_router",
        route_workflow_entry,
        {node: node for node in sorted(_RESUMABLE_WORKFLOW_NODES)},
    )
    graph.add_edge(
        "requirement_analysis",
        "analyze_project",
    )
    graph.add_edge(
        "analyze_project",
        "capability_design",
    )
    graph.add_edge(
        "capability_design",
        "tool_mcp_decision",
    )
    graph.add_edge(
        "tool_mcp_decision",
        "agent_architecture",
    )
    graph.add_edge(
        "agent_architecture",
        "database_design",
    )
    graph.add_edge(
        "database_design",
        "target_workflow_design",
    )
    graph.add_edge(
        "target_workflow_design",
        "project_file_plan",
    )
    graph.add_edge(
        "project_file_plan",
        "requirement_coverage_gate",
    )
    graph.add_conditional_edges(
        "requirement_coverage_gate",
        route_after_requirement_coverage,
        {
            "settings_requirement_analysis": "settings_requirement_analysis",
            "end": END,
        },
    )
    graph.add_edge(
        "settings_requirement_analysis",
        "settings_schema_design",
    )
    graph.add_edge(
        "settings_schema_design",
        "settings_ui_design",
    )
    graph.add_edge(
        "settings_ui_design",
        "checkpoint",
    )
    graph.add_edge(
        "checkpoint",
        "approval",
    )

    graph.add_conditional_edges(
        "approval",
        route_after_approval,
        {
            "code_generation": "code_generation",
            "end": END,
        },
    )

    graph.add_conditional_edges(
        "code_generation",
        route_after_code_generation,
        {
            "settings_generator": "settings_generator",
            "end": END,
        },
    )
    graph.add_conditional_edges(
        "settings_generator",
        route_after_settings_generator,
        {
            "settings_validation": "settings_validation",
            "end": END,
        },
    )
    graph.add_conditional_edges(
        "settings_validation",
        route_after_settings_validation,
        {
            "environment_configuration": "build_artifact_validation",
            "debug": "debug",
        },
    )
    graph.add_conditional_edges(
        "build_artifact_validation",
        route_after_build_artifact_validation,
        {
            "as_built_architecture": "as_built_architecture",
            "code_generation": "code_generation",
            "end": END,
        },
    )
    graph.add_edge(
        "as_built_architecture",
        "architecture_conformance",
    )
    graph.add_conditional_edges(
        "architecture_conformance",
        route_after_architecture_conformance,
        {
            "environment_configuration": "environment_configuration",
            "code_generation": "code_generation",
            "end": END,
        },
    )
    graph.add_edge(
        "environment_configuration",
        "test",
    )

    graph.add_conditional_edges(
        "test",
        route_after_test,
        {
            "package_completion": "package_completion",
            "debug": "debug",
            "end": END,
        },
    )

    graph.add_conditional_edges(
        "debug",
        route_after_debug,
        {
            "code_generation": "code_generation",
            "end": END,
        },
    )

    graph.add_edge(
        "package_completion",
        "review",
    )
    graph.add_edge(
        "review",
        END,
    )

    return graph.compile(
        checkpointer=checkpointer,
    )
