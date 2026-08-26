from __future__ import annotations

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.agent_factory_policy import format_agent_factory_policy_for_prompt
from app.services.agent_factory_policy_planner import (
    format_factory_policies_for_prompt,
    infer_fastapi_factory_plan,
)
from app.services.model_router import LLMTask, model_for_task
from app.services.database_schema_design import build_database_plan


SYSTEM = """당신은 THEANOVA AgentStudio의 Agent Factory 설계 엔진입니다.

사용자의 자연어 요구사항을 실행 가능한 Agent 프로그램 제작 계획으로 변환합니다.

반드시 JSON 하나만 반환하세요.

형식:
{
  "requirement_spec": {
    "goal": "...",
    "users": [],
    "inputs": [],
    "outputs": [],
    "constraints": [],
    "acceptance_criteria": []
  },
  "capability_plan": {
    "capabilities": [],
    "external_dependencies": [],
    "data_needs": []
  },
  "tool_mcp_plan": {
    "decisions": [
      {
        "capability": "...",
        "execution_type": "internal_function|tool|mcp|api_client|db_service|none",
        "reason": "..."
      }
    ]
  },
  "agent_architecture": {
    "components": [],
    "state": [],
    "interfaces": [],
    "persistence": [],
    "security": []
  },
  "database_plan": {
    "enabled": true,
    "schema_name": "public",
    "module_suggestions": ["CORE", "CONVERSATION", "RAG"],
    "custom_tables": [
      {
        "name": "업무 전용 snake_case 테이블명",
        "purpose": "업무 Entity 책임",
        "columns": [
          {
            "name": "컬럼명",
            "type": "TEXT|BIGINT|INTEGER|BOOLEAN|NUMERIC(18,2)|TIMESTAMPTZ|JSONB|UUID",
            "nullable": true,
            "primary_key": false,
            "unique": false,
            "default": "",
            "references": "other_table.id"
          }
        ],
        "indexes": [["컬럼명"]]
      }
    ],
    "custom_design_notes": []
  },
  "target_agent_workflow": {
    "name": "...",
    "steps": [
      {
        "name": "machine_readable_step_name",
        "label": "사용자에게 보일 단계명",
        "description": "이 단계가 실제로 수행하는 일",
        "type": "input|validation|mcp_client|transport|mcp_server|tool|llm|ui|storage|decision|complete"
      }
    ],
    "branches": [
      {
        "from": "분기 단계",
        "condition": "조건",
        "yes": "이동 단계",
        "no": "이동 단계"
      }
    ],
    "retry_policy": [
      {
        "target": "재시도 대상",
        "condition": "재시도 조건",
        "strategy": "bounded retry/backoff 등"
      }
    ],
    "failure_policy": [
      {
        "target": "실패 대상",
        "action": "안전한 오류 반환/로그/중단 등"
      }
    ],
    "requirement_coverage": [
      {
        "requirement": "확정 요구사항",
        "covered_by": ["step_name"],
        "status": "covered|missing"
      }
    ]
  },
  "file_plan": {
    "existing_files_to_modify": [],
    "new_files": [
      {
        "path": "프로젝트 루트 기준 상대경로",
        "purpose": "이 파일의 책임",
        "required": true,
        "component": "architecture component 이름"
      }
    ],
    "component_file_map": [
      {
        "component": "Agent Architecture component",
        "files": ["상대경로"],
        "status": "planned"
      }
    ]
  },
  "settings_plan": {
    "enabled": true,
    "reason": "왜 설정 화면이 필요한지",
    "categories": [
      {
        "id": "llm",
        "label": "AI 모델",
        "fields": [
          {
            "key": "LLM_PROVIDER",
            "label": "LLM Provider",
            "type": "select|string|number|boolean|password|path",
            "default": "",
            "required": true,
            "secret": false,
            "description": "",
            "options": [],
            "validation": {},
            "storage": "env|config|database"
          }
        ]
      }
    ],
    "backend": {
      "settings_model": "app/core/settings.py",
      "schema": "app/schemas/settings.py",
      "router": "app/routers/settings.py",
      "service": "app/services/settings_service.py"
    },
    "frontend": {
      "page": "frontend/src/pages/SettingsPage.jsx",
      "api_client": "frontend/src/services/settingsApi.js"
    },
    "security": {
      "mask_secrets": true,
      "never_return_secret_plaintext": true
    },
    "tests": [
      "GET settings",
      "UPDATE settings",
      "secret masking",
      "invalid value rejection"
    ]
  },
  "environment_plan": {
    "env_vars": [],
    "dependencies": [],
    "services": [],
    "startup": [],
    "validation_commands": []
  }
}

절대 원칙:
- AgentStudio 자체 제작 Workflow와 생성 대상 Agent의 업무 Workflow를 구분합니다.
- 기능을 무조건 MCP/Tool로 만들지 말고 필요성을 판단합니다.
- 기존 프로젝트라면 기존 구조를 최대한 유지합니다.
- 신규 파일은 필요한 경우에만 계획합니다.
- 실행, 테스트, 실패 복구까지 고려합니다.
- 교육 예제의 특정 모델/포트/제한값을 근거 없이 고정하지 않습니다.
- 인터뷰에서 이미 확정된 요구사항을 다시 질문하거나 무시하지 않습니다.
- target_agent_workflow는 단순 요약이 아니라 실제 실행 가능한 업무 단계로 설계합니다.
- 보안 검증, 입력 검증, MCP Client/Transport/Server/Tool, Provider 선택, 결과 분기처럼 실행상 중요한 단계를 생략하지 않습니다.
- 결과 경로가 여러 개인 경우 branches에 분기 조건을 명시합니다.
- 외부 호출 실패 가능성이 있으면 retry_policy와 failure_policy를 구체적으로 작성합니다.
- 요구사항이 복합적인데 target_agent_workflow.steps가 5개 이하가 되도록 지나치게 축약하지 않습니다.
- 인터뷰에서 확정된 요구사항 각각을 target_agent_workflow.requirement_coverage에 기록하고 어떤 step이 구현하는지 연결합니다.
- requirement_coverage에 missing이 하나라도 있으면 Workflow 설계를 완료된 것으로 반환하지 말고 누락 단계를 steps/branches에 추가합니다.
- 파일 접근 Root 제한이 있으면 반드시 별도 validation 단계와 거부 branch를 만듭니다.
- 허용 확장자 제한이 있으면 반드시 별도 validation 단계와 거부 branch를 만듭니다.
- MCP 사용이 확정되었으면 최소한 MCP Client → Transport → MCP Server → Tool 호출의 책임이 Workflow에서 식별 가능해야 합니다. 단, 실제 구현이 합쳐지는 경우에도 description에 각 책임을 명시합니다.
- LLM Provider 변경 가능 요구가 있으면 Provider/Model 설정 확인 또는 선택 단계를 별도로 둡니다.
- 결과 저장이 선택 사항이면 저장 여부 decision branch를 만들고, 저장 형식과 허용 Output 경로 검증을 표현합니다.
- UI 표시가 요구되면 UI 결과 표시 단계를 별도로 둡니다.
- React + TypeScript가 확정되면 Frontend src 파일은 .tsx/.ts를 사용하고 App.jsx/main.jsx/api.js를 계획하지 않습니다. App.tsx는 Route/Page/Layout 조립만 담당해야 합니다.
- React Frontend는 App 한 파일에 UI를 몰아넣지 않습니다. 최소한 layouts/AppLayout, components/layout/TopHeader, Sidebar, Footer, pages, services, styles를 분리하고 TypeScript이면 types도 분리합니다.
- 업무 화면이 여러 개이면 각 본문 화면을 pages 또는 features 하위 파일로 나누고, 공통 메뉴/헤더/푸터와 API Client를 Page 내부에 중복 구현하지 않습니다.
- validation/decision 실패 경로는 failure_policy만 적지 말고 branches에서도 사용자가 이해할 수 있게 연결합니다.
- 생성 대상 Agent에서 런타임 변경이 필요한 값이 있으면 settings_plan을 반드시 설계합니다.
- AgentStudio 설정 화면을 복사하지 않고 대상 Agent에 필요한 설정만 생성합니다.
- 사용하지 않는 DB가 요구사항에 없으면 DB 설정 Section을 만들지 않습니다.
- DB가 필요한 Agent라면 database_plan에 업무 Entity를 제안하되, Agent 공통/기능별 표준 테이블은 Backend Module Registry가 보강하므로 custom_tables에는 해당 Agent에만 필요한 업무 Entity를 우선 제안합니다.
- DB 설계는 Agent 시스템 데이터와 고객/상품/주문 등 업무 데이터를 분리하고, 기능 설정/metadata는 JSONB를 사용할 수 있지만 검색/JOIN/집계가 필요한 핵심 값은 정규 컬럼으로 설계합니다.
- custom_tables의 이름/컬럼은 snake_case를 사용하고 FK references는 table.column 형식으로 명시합니다.
- database_plan.finalized=true인 경우 사용자가 확인한 DB 계약이므로 이후 코드 생성은 해당 Table/Column/FK와 Migration DDL을 임의 변경하지 않습니다.
- API Key/Password/Token은 secret=true로 표시하고 GET 응답에서 평문 노출하지 않습니다.
- 설정 UI가 필요한 경우 file_plan.new_files에 Backend Settings API/Schema/Service와 React Settings UI/API Client를 포함합니다.
- Agent Architecture의 모든 component는 file_plan.component_file_map에서 최소 1개 이상의 실제 파일과 연결되어야 합니다.
- 생성 대상이 웹 Agent라면 실행 가능한 Backend entrypoint, Frontend entrypoint/package 설정, API client, README, 환경 예제, 의존성 파일, 테스트 파일까지 계획합니다.
- 모든 생성 대상 Agent는 프로젝트 루트의 SYSTEM_ADMIN.cmd를 사용자 단일 실행 진입점으로 제공하며, CMD는 UTF-8(chcp 65001) 기준으로 SYSTEM_ADMIN.ps1 관리 스크립트를 호출합니다. SYSTEM_ADMIN.ps1은 Windows PowerShell 5.1 호환을 위해 UTF-8 BOM으로 저장합니다.
- SYSTEM_ADMIN은 최초 실행 시 .venv와 필요한 의존성을 준비하고, 기존 PID 기반 중복 프로세스를 정리한 뒤 Backend/Frontend를 시작하고 MCP stdio 준비 상태를 확인하며, 웹 UI가 있으면 브라우저를 자동으로 엽니다.
- FastAPI 표준 구조가 backend/app이면 SYSTEM_ADMIN은 backend를 WorkingDirectory로 하여 uvicorn app.main:app을 실행합니다. backend/app 내부 import는 from app.routers..., from app.services... 같은 app.* 또는 올바른 상대 import로 통일하고 from routers... / from backend.app...를 혼용하지 않습니다.
- README의 기본 실행 방법은 개별 uvicorn/npm 명령보다 SYSTEM_ADMIN.cmd를 먼저 안내합니다.
- MCP가 필요하면 MCP Client, Transport, MCP Server, 실제 Tool 구현 파일을 file_plan에 분리해 계획합니다.
- "service.py 한 파일" 같은 축약 구현으로 전체 Agent를 대체하지 않습니다.
- file_plan에 등록된 required 파일은 실제 동작 가능한 구현으로 생성되어야 하며 TODO/placeholder/stub 문자열만 남긴 파일은 완료로 인정하지 않습니다.
- 테스트는 최소 문법/Import 검증뿐 아니라 핵심 Workflow 계약(Root 제한, 확장자, MCP 호출, LLM Provider, 저장 정책 등)을 확인하도록 계획합니다.
- .env.example에는 필요한 Key만 기록하고 실제 Secret은 절대 넣지 않습니다.
"""


def _extract_json(text: str) -> dict:
    value = (text or "").strip()

    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.I)
        value = re.sub(r"\s*```$", "", value)

    start = value.find("{")
    end = value.rfind("}")

    if start >= 0 and end > start:
        value = value[start:end + 1]

    return json.loads(value)


def _primary_user_goal(request: str) -> str:
    """Return a short user-facing goal, never the serialized interview state."""
    value = str(request or "").replace("\\n", "\n").strip()
    marker = "[현재 사용자의 개발 요청]"
    if marker in value:
        value = value.split(marker, 1)[1]
        next_section = re.search(r"\n\s*\[[^\]]+\]", value)
        if next_section:
            value = value[:next_section.start()]
    value = re.sub(r"(?im)^\s*(USER|ASSISTANT|SYSTEM)\s*:\s*", "", value).strip()
    value = re.sub(r"\s+", " ", value)
    if not value:
        return "신규 Agent 요구사항"
    # Internal state markers must never become an architecture heading/summary.
    if any(token in value for token in (
        'original_request', 'user_answers', 'confirmed_requirements',
        'latest_analysis', 'attachment_summary', '"backend"', '"llm"',
    )):
        first = re.split(r"[.!?。]", value, maxsplit=1)[0].strip()
        value = first or "신규 Agent 요구사항"
    return value[:240].rstrip()


def _sanitize_requirement_spec(design: dict, request: str) -> None:
    spec = design.setdefault("requirement_spec", {})
    goal = str(spec.get("goal") or "").replace("\\n", "\n").strip()
    raw_markers = (
        'original_request', 'user_answers', 'confirmed_requirements',
        'latest_analysis', 'attachment_summary', '[인터뷰 전체 대화]',
        'ASSISTANT:', 'USER:',
    )
    if (
        not goal
        or len(goal) > 500
        or any(marker in goal for marker in raw_markers)
        or goal.count("{") + goal.count("[") > 8
    ):
        spec["goal"] = _primary_user_goal(request)
    else:
        spec["goal"] = re.sub(r"\s+", " ", goal)[:300].rstrip()


def _fallback_design(request: str) -> dict:
    plan = infer_fastapi_factory_plan(
        request=request,
        project_scope=True,
    )

    return {
        "requirement_spec": {
            "goal": _primary_user_goal(request),
            "users": [],
            "inputs": [],
            "outputs": [],
            "constraints": [],
            "acceptance_criteria": [
                "사용자 요구사항이 실제 코드에 반영되어야 합니다.",
                "실행 및 테스트 가능한 상태여야 합니다.",
            ],
        },
        "capability_plan": {
            "capabilities": [],
            "external_dependencies": [],
            "data_needs": [],
        },
        "tool_mcp_plan": {
            "decisions": [],
        },
        "agent_architecture": {
            "components": [],
            "state": [],
            "interfaces": [],
            "persistence": [],
            "security": [],
            "factory_policy_plan": plan,
        },
        "database_plan": {},
        "target_agent_workflow": {
            "name": "Generated Agent Workflow",
            "steps": [],
            "branches": [],
            "retry_policy": [],
            "failure_policy": [],
        },
        "file_plan": {
            "existing_files_to_modify": [],
            "new_files": [],
        },
        "settings_plan": {
            "enabled": False,
            "reason": "설계 LLM 실패로 자동 설정 계획을 생성하지 못했습니다.",
            "categories": [],
            "backend": {},
            "frontend": {},
            "security": {
                "mask_secrets": True,
                "never_return_secret_plaintext": True,
            },
            "tests": [],
        },
        "environment_plan": {
            "env_vars": [],
            "dependencies": [],
            "services": [],
            "startup": [],
            "validation_commands": [],
        },
    }


def _workflow_text(workflow: dict) -> str:
    return json.dumps(workflow or {}, ensure_ascii=False).lower()


def _ensure_step(
    workflow: dict,
    name: str,
    label: str,
    description: str,
    step_type: str,
) -> None:
    steps = workflow.setdefault("steps", [])
    names = {str(x.get("name") or "") for x in steps if isinstance(x, dict)}
    if name not in names:
        steps.append({
            "name": name,
            "label": label,
            "description": description,
            "type": step_type,
        })


def _ensure_branch(
    workflow: dict,
    from_step: str,
    condition: str,
    yes: str,
    no: str,
) -> None:
    branches = workflow.setdefault("branches", [])
    key = (from_step, condition)
    existing = {
        (str(x.get("from") or ""), str(x.get("condition") or ""))
        for x in branches
        if isinstance(x, dict)
    }
    if key not in existing:
        branches.append({
            "from": from_step,
            "condition": condition,
            "yes": yes,
            "no": no,
        })


def _enforce_workflow_requirement_coverage(
    design: dict,
    request: str,
) -> dict:
    """
    LLM이 업무 Workflow를 지나치게 축약해도 인터뷰에서 확정된 핵심 계약이
    Workflow에서 사라지지 않도록 최소 구조를 보강합니다.

    특정 테스트 Agent 이름에 의존하지 않고 요구 텍스트의 의미 신호로 판단합니다.
    """
    workflow = design.setdefault("target_agent_workflow", {})
    workflow.setdefault("name", "Generated Agent Workflow")
    workflow.setdefault("steps", [])
    workflow.setdefault("branches", [])
    workflow.setdefault("retry_policy", [])
    workflow.setdefault("failure_policy", [])
    workflow.setdefault("requirement_coverage", [])

    req = (request or "").lower()
    coverage = []

    def mark(requirement: str, covered_by: list[str]) -> None:
        coverage.append({
            "requirement": requirement,
            "covered_by": covered_by,
            "status": "covered",
        })

    # Root/path access boundary.
    root_signal = (
        ("root" in req or "프로젝트 폴더" in req or "프로젝트 root" in req)
        and any(x in req for x in ("제한", "내부", "밖", "외부", "허용"))
    )
    if root_signal:
        _ensure_step(
            workflow,
            "validate_project_root",
            "프로젝트 Root 경로 검증",
            "선택한 파일이 허용된 프로젝트 Root 내부인지 검사하고 Root 밖 접근을 거부합니다.",
            "validation",
        )
        _ensure_branch(
            workflow,
            "validate_project_root",
            "선택 파일이 프로젝트 Root 내부인가?",
            "validate_file_extension",
            "reject_file_access",
        )
        mark("프로젝트 Root 내부 파일만 접근", ["validate_project_root"])

    # Extension allow-list.
    ext_signal = any(x in req for x in (".txt", ".md", ".py")) and any(
        x in req for x in ("허용", "확장자", "제한")
    )
    if ext_signal:
        _ensure_step(
            workflow,
            "validate_file_extension",
            "파일 확장자 검증",
            "허용 확장자 목록(.txt, .md, .py 등)에 포함되는지 검사하고 지원하지 않는 파일은 거부합니다.",
            "validation",
        )
        _ensure_branch(
            workflow,
            "validate_file_extension",
            "허용된 파일 확장자인가?",
            "mcp_client_request",
            "reject_unsupported_file",
        )
        mark("허용 파일 확장자 제한", ["validate_file_extension"])

    # MCP responsibility chain.
    if "mcp" in req:
        _ensure_step(
            workflow,
            "mcp_client_request",
            "MCP Client 요청",
            "선택 파일 읽기 요청을 MCP Client가 구성하여 Transport 계층으로 전달합니다.",
            "mcp_client",
        )
        _ensure_step(
            workflow,
            "mcp_transport",
            "MCP Transport",
            "설정된 MCP Transport를 사용합니다. 로컬 stdio를 기본으로 하고 확장 가능한 Transport 계층을 유지합니다.",
            "transport",
        )
        _ensure_step(
            workflow,
            "mcp_server_dispatch",
            "MCP Server 처리",
            "MCP Server가 파일 읽기 요청을 수신하고 등록된 File Tool로 전달합니다.",
            "mcp_server",
        )
        _ensure_step(
            workflow,
            "file_read_tool",
            "File MCP Tool 실행",
            "검증된 파일 경로의 내용을 읽어 다음 AI 처리 단계에 전달합니다.",
            "tool",
        )
        mark(
            "MCP 기반 파일 읽기",
            [
                "mcp_client_request",
                "mcp_transport",
                "mcp_server_dispatch",
                "file_read_tool",
            ],
        )

    # Provider/model switching.
    provider_signal = (
        "gpt-4o-mini" in req
        or "ollama" in req
        or "provider" in req
        or "llm" in req
    )
    configurable_signal = any(
        x in req for x in ("변경 가능", "설정 파일", "환경변수", "환경 변수", "전환")
    )
    if provider_signal and configurable_signal:
        _ensure_step(
            workflow,
            "resolve_llm_provider",
            "LLM Provider / Model 확인",
            "설정 파일 또는 환경변수에서 Provider와 Model을 읽습니다. 기본 OpenAI gpt-4o-mini를 사용하고 설정에 따라 Ollama 등으로 전환합니다.",
            "decision",
        )
        _ensure_branch(
            workflow,
            "resolve_llm_provider",
            "선택된 LLM Provider",
            "generate_summary",
            "generate_summary",
        )
        mark("LLM Provider/Model 런타임 변경", ["resolve_llm_provider"])

    # UI result display.
    if "react" in req or "웹 gui" in req or "화면에 표시" in req:
        _ensure_step(
            workflow,
            "display_summary_ui",
            "요약 결과 UI 표시",
            "생성된 요약 결과를 React 웹 UI에 표시합니다.",
            "ui",
        )
        mark("React UI에 요약 결과 표시", ["display_summary_ui"])

    # Optional save, format and output path validation.
    save_signal = any(x in req for x in ("저장", "output", "txt", "md"))
    if save_signal:
        _ensure_step(
            workflow,
            "decide_save_summary",
            "요약 결과 저장 여부",
            "사용자가 요약 결과를 파일로 저장할지 선택합니다.",
            "decision",
        )
        _ensure_step(
            workflow,
            "select_save_format",
            "저장 형식 선택",
            "지원되는 저장 형식(txt 또는 md)을 선택합니다.",
            "validation",
        )
        _ensure_step(
            workflow,
            "validate_output_path",
            "Output 경로 검증",
            "저장 대상이 지정된 Output 폴더 또는 프로젝트 내부 허용 경로인지 검사합니다.",
            "validation",
        )
        _ensure_step(
            workflow,
            "save_summary",
            "요약 결과 저장",
            "검증된 경로에 선택한 txt 또는 md 형식으로 요약 결과를 저장합니다.",
            "storage",
        )
        _ensure_branch(
            workflow,
            "decide_save_summary",
            "사용자가 저장을 선택했는가?",
            "select_save_format",
            "complete",
        )
        mark(
            "선택적 txt/md 저장 및 Output 경로 제한",
            [
                "decide_save_summary",
                "select_save_format",
                "validate_output_path",
                "save_summary",
            ],
        )

    workflow["requirement_coverage"] = coverage or workflow.get(
        "requirement_coverage",
        [],
    )

    return design


async def design_agent_factory(
    request: str,
    project_context: dict | None = None,
    provider: str | None = None,
) -> dict:
    """
    여러 Workflow Node가 공유할 Agent 설계 Bundle을 한 번의 LLM 호출로 생성합니다.

    Node를 분리하되 매 단계마다 동일한 내용을 다시 LLM에 보내는 비용은 피합니다.
    각 Node는 이 Bundle에서 자신의 책임에 해당하는 산출물만 State에 확정합니다.
    """
    llm = model_for_task(LLMTask.WORKFLOW_DESIGN, provider)

    factory_direction = format_agent_factory_policy_for_prompt()
    policy_context = format_factory_policies_for_prompt()

    try:
        result = await llm.ainvoke([
            SystemMessage(
                content=(
                    SYSTEM
                    + "\n\n[AgentStudio 제작 기본 방향]\n"
                    + factory_direction
                    + "\n\n[설계 정책]\n"
                    + policy_context
                )
            ),
            HumanMessage(
                content=(
                    "[사용자 요구]\n"
                    + request
                    + "\n\n[현재 프로젝트 분석]\n"
                    + json.dumps(
                        project_context or {},
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            ),
        ])

        parsed = _extract_json(str(result.content))

        if not isinstance(parsed, dict):
            raise ValueError("Agent Factory 설계 결과가 JSON object가 아닙니다.")

        _sanitize_requirement_spec(parsed, request)
        parsed = _enforce_workflow_requirement_coverage(parsed, request)
        parsed.setdefault("design_runtime", {})["workflow_provider"] = getattr(llm, "last_provider", "")
        parsed["design_runtime"]["workflow_task"] = LLMTask.WORKFLOW_DESIGN.value
        # target_agent_workflow contains the executable LangGraph-style steps and
        # branches, so Workflow 전체 설계와 LangGraph 분기 설계 share the same
        # high-performance provider decision instead of paying for a duplicate call.
        parsed["design_runtime"]["langgraph_branch_provider"] = getattr(llm, "last_provider", "")

        base_database_plan = build_database_plan(request, parsed)
        parsed["database_plan"] = base_database_plan
        if base_database_plan.get("enabled"):
            # DB Entity/relationship design is an architecture-critical task of its
            # own. Refine only the custom business entities with the high-performance
            # chain, then let the deterministic Module Registry + Validator rebuild
            # and verify the final plan. A DB-model failure never discards the safe
            # registry-based plan.
            db_llm = model_for_task(LLMTask.DATABASE_SCHEMA_DESIGN, provider)
            try:
                db_result = await db_llm.ainvoke([
                    SystemMessage(content=(
                        "당신은 PostgreSQL 데이터 모델링 전문가입니다. 반드시 JSON 하나만 반환하세요. "
                        "Agent 시스템 공통 테이블은 이미 Module Registry가 생성하므로 해당 Agent에만 필요한 "
                        "업무 Entity/관계만 제안하십시오. 검색/JOIN/집계 핵심 값은 정규 컬럼으로 두고, "
                        "설정/metadata만 JSONB를 사용하십시오. FK는 table.column 형식으로 명시하십시오.\n"
                        "반환 형식: {\"custom_tables\": [...], \"custom_design_notes\": [...]}"
                    )),
                    HumanMessage(content=(
                        "[사용자 요구사항]\n" + request
                        + "\n\n[확정 Requirement/Capability]\n"
                        + json.dumps({
                            "requirement_spec": parsed.get("requirement_spec") or {},
                            "capability_plan": parsed.get("capability_plan") or {},
                            "agent_architecture": parsed.get("agent_architecture") or {},
                        }, ensure_ascii=False, indent=2)
                        + "\n\n[자동 선택 DB Modules]\n"
                        + json.dumps([x.get("id") for x in base_database_plan.get("modules") or []], ensure_ascii=False)
                        + "\n\n[표준/현재 테이블명]\n"
                        + json.dumps([x.get("name") for x in base_database_plan.get("tables") or []], ensure_ascii=False)
                        + "\n\n중복 표준 테이블은 다시 제안하지 마십시오."
                    )),
                ])
                refined = _extract_json(str(db_result.content))
                if not isinstance(refined, dict):
                    raise ValueError("DB Entity 설계 결과가 JSON object가 아닙니다.")
                raw_db = dict(parsed.get("database_plan") or {})
                raw_db["custom_tables"] = refined.get("custom_tables") or []
                raw_db["custom_design_notes"] = refined.get("custom_design_notes") or []
                parsed["database_plan"] = raw_db
                parsed["database_plan"] = build_database_plan(request, parsed)
                parsed["design_runtime"]["database_provider"] = getattr(db_llm, "last_provider", "")
                parsed["design_runtime"]["database_task"] = LLMTask.DATABASE_SCHEMA_DESIGN.value
            except Exception as db_exc:
                parsed["database_plan"] = base_database_plan
                notes = list(parsed["database_plan"].get("custom_design_notes") or [])
                notes.append(f"고성능 DB Entity 보강 실패로 검증된 Module Registry 설계를 사용했습니다: {type(db_exc).__name__}")
                parsed["database_plan"]["custom_design_notes"] = notes
                parsed["design_runtime"]["database_provider"] = "deterministic_fallback"
                parsed["design_runtime"]["database_error"] = f"{type(db_exc).__name__}: {db_exc}"
        return parsed

    except Exception:
        # 설계 LLM 오류가 IDE 자체를 중단시키지 않도록 최소 안전 계획을 반환합니다.
        fallback = _enforce_workflow_requirement_coverage(
            _fallback_design(request),
            request,
        )
        _sanitize_requirement_spec(fallback, request)
        fallback["database_plan"] = build_database_plan(request, fallback)
        return fallback

# v5.345: Incremental design revision. Reuse the previous design unless the
# requirement delta is large enough to justify a full architecture rebuild.
_DESIGN_SECTION_KEYS = (
    "requirement_spec", "capability_plan", "tool_mcp_plan",
    "agent_architecture", "database_plan", "target_agent_workflow",
    "file_plan", "settings_plan", "environment_plan",
)


def _clone_json(value):
    return json.loads(json.dumps(value or {}, ensure_ascii=False))


def _preview_design_sections(previous_design: dict | None) -> dict:
    previous = previous_design if isinstance(previous_design, dict) else {}
    return {key: _clone_json(previous.get(key) or {}) for key in _DESIGN_SECTION_KEYS}


def _stable_confirmed_requirements(value: dict | None) -> dict:
    source = value if isinstance(value, dict) else {}
    ignored = {"user_answers", "latest_analysis", "attachment_summary"}
    return {
        key: _clone_json(item) if isinstance(item, (dict, list)) else item
        for key, item in source.items()
        if key not in ignored
    }


def _changed_requirement_groups(previous: dict | None, current: dict | None) -> list[str]:
    old = _stable_confirmed_requirements(previous)
    new = _stable_confirmed_requirements(current)
    keys = sorted(set(old) | set(new))
    changed = []
    for key in keys:
        if json.dumps(old.get(key), ensure_ascii=False, sort_keys=True, default=str) != json.dumps(new.get(key), ensure_ascii=False, sort_keys=True, default=str):
            changed.append(key)
    return changed


def _new_interview_messages(previous_design: dict | None, current_messages: list[dict] | None) -> list[dict]:
    previous = previous_design if isinstance(previous_design, dict) else {}
    old_messages = list(previous.get("interview_messages") or [])
    current = list(current_messages or [])
    if not old_messages:
        return current[-4:]
    prefix_ok = len(current) >= len(old_messages) and all(
        str(current[i].get("role") or "") == str(old_messages[i].get("role") or "")
        and str(current[i].get("content") or "").strip() == str(old_messages[i].get("content") or "").strip()
        for i in range(len(old_messages))
    )
    return current[len(old_messages):] if prefix_ok else current[-4:]


def _impact_sections(changed_groups: list[str], delta_text: str) -> list[str]:
    mapping = {
        "original_request": set(_DESIGN_SECTION_KEYS),
        "ui": {"requirement_spec", "agent_architecture", "target_agent_workflow", "file_plan", "settings_plan", "environment_plan"},
        "ui_layout": {"requirement_spec", "agent_architecture", "target_agent_workflow", "file_plan", "settings_plan", "environment_plan"},
        "backend": {"requirement_spec", "agent_architecture", "target_agent_workflow", "file_plan", "settings_plan", "environment_plan"},
        "llm": {"requirement_spec", "capability_plan", "agent_architecture", "target_agent_workflow", "file_plan", "settings_plan", "environment_plan"},
        "file_access": {"requirement_spec", "capability_plan", "tool_mcp_plan", "agent_architecture", "target_agent_workflow", "file_plan", "settings_plan"},
        "mcp": {"requirement_spec", "capability_plan", "tool_mcp_plan", "agent_architecture", "target_agent_workflow", "file_plan", "environment_plan"},
        "database": {"requirement_spec", "capability_plan", "agent_architecture", "database_plan", "target_agent_workflow", "file_plan", "settings_plan", "environment_plan"},
        "result": {"requirement_spec", "target_agent_workflow", "file_plan", "settings_plan"},
        "processing": {"requirement_spec", "target_agent_workflow", "settings_plan", "environment_plan"},
        "runtime": {"requirement_spec", "file_plan", "settings_plan", "environment_plan"},
        "auth": {"requirement_spec", "capability_plan", "agent_architecture", "database_plan", "target_agent_workflow", "file_plan", "settings_plan"},
        "manual_overrides": set(_DESIGN_SECTION_KEYS),
    }
    impacted: set[str] = set()
    for group in changed_groups:
        impacted.update(mapping.get(group, {"requirement_spec", "target_agent_workflow", "file_plan"}))
    lower = str(delta_text or "").casefold()
    if any(token in lower for token in ("redis", "postgres", "pgvector", "database", "db ", "테이블", "entity", "관계")):
        impacted.update({"database_plan", "agent_architecture", "target_agent_workflow", "file_plan", "settings_plan", "environment_plan"})
    if any(token in lower for token in ("mcp", "tool", "api 연동", "외부 api")):
        impacted.update({"tool_mcp_plan", "capability_plan", "agent_architecture", "target_agent_workflow", "file_plan"})
    if any(token in lower for token in ("react", "streamlit", "ui", "화면")):
        impacted.update({"agent_architecture", "target_agent_workflow", "file_plan", "settings_plan"})
    return [key for key in _DESIGN_SECTION_KEYS if key in impacted] or ["requirement_spec", "target_agent_workflow"]


def _needs_full_redesign(changed_groups: list[str], delta_text: str) -> bool:
    lower = str(delta_text or "").casefold()
    explicit = any(token in lower for token in (
        "처음부터 다시", "전체 구조 변경", "아키텍처 전체", "목적을 변경",
        "새 에이전트", "완전히 다른", "workflow 전체 변경",
    ))
    structural = {"original_request", "backend", "mcp", "database", "auth", "manual_overrides"}
    structural_count = len(structural.intersection(changed_groups))
    return explicit or structural_count >= 3


async def design_agent_factory_incremental(
    request: str,
    project_context: dict | None = None,
    provider: str | None = None,
    previous_design: dict | None = None,
    previous_confirmed_requirements: dict | None = None,
    current_confirmed_requirements: dict | None = None,
    interview_messages: list[dict] | None = None,
) -> dict:
    previous_sections = _preview_design_sections(previous_design)
    if not any(previous_sections.values()):
        result = await design_agent_factory(request, project_context, provider)
        result.setdefault("design_runtime", {})["incremental_revision"] = {
            "mode": "FULL_INITIAL",
            "llm_called": True,
            "changed_groups": [],
            "affected_sections": list(_DESIGN_SECTION_KEYS),
            "reused_sections": [],
        }
        return result

    changed_groups = _changed_requirement_groups(previous_confirmed_requirements, current_confirmed_requirements)
    delta_messages = _new_interview_messages(previous_design, interview_messages)
    delta_text = "\n".join(str(item.get("content") or "") for item in delta_messages if isinstance(item, dict)).strip()

    if not changed_groups and not delta_text:
        result = _clone_json(previous_sections)
        runtime = _clone_json((previous_design or {}).get("design_runtime") or {})
        runtime["incremental_revision"] = {
            "mode": "FULL_REUSE",
            "llm_called": False,
            "changed_groups": [],
            "affected_sections": [],
            "reused_sections": list(_DESIGN_SECTION_KEYS),
        }
        result["design_runtime"] = runtime
        return result

    if _needs_full_redesign(changed_groups, delta_text):
        result = await design_agent_factory(request, project_context, provider)
        result.setdefault("design_runtime", {})["incremental_revision"] = {
            "mode": "FULL_REDESIGN",
            "llm_called": True,
            "changed_groups": changed_groups,
            "delta_messages": len(delta_messages),
            "change_request": delta_text[:4000],
            "affected_sections": list(_DESIGN_SECTION_KEYS),
            "reused_sections": [],
        }
        return result

    affected = _impact_sections(changed_groups, delta_text)
    reused = [key for key in _DESIGN_SECTION_KEYS if key not in affected]
    llm = model_for_task(LLMTask.WORKFLOW_DESIGN, provider)
    previous_subset = {key: previous_sections.get(key) or {} for key in affected}
    change_payload = {
        "changed_requirement_groups": changed_groups,
        "changed_confirmed_requirements": {
            key: (current_confirmed_requirements or {}).get(key) for key in changed_groups
        },
        "new_interview_messages": delta_messages,
    }
    try:
        response = await llm.ainvoke([
            SystemMessage(content=(
                "당신은 THEANOVA AgentStudio의 증분 설계 수정 엔진입니다. 반드시 JSON 하나만 반환하세요. "
                "전체 Agent를 처음부터 다시 설계하지 말고, 지정된 affected_sections만 수정하십시오. "
                "변경되지 않은 구조/Workflow/DB/File Plan은 보존합니다. "
                "반환 형식: {\"updated_sections\": {\"section_name\": {...}}, \"summary\": \"...\"}. "
                "updated_sections에는 요청받은 section만 포함하십시오. 기존 요구사항과 충돌하는 변경은 최신 사용자 변경을 우선합니다."
            )),
            HumanMessage(content=(
                "[이번 변경분만]\n" + json.dumps(change_payload, ensure_ascii=False, indent=2)
                + "\n\n[수정 대상 section]\n" + json.dumps(affected, ensure_ascii=False)
                + "\n\n[기존 수정 대상 설계]\n" + json.dumps(previous_subset, ensure_ascii=False, indent=2)
                + "\n\n[현재 프로젝트 요약]\n" + json.dumps(project_context or {}, ensure_ascii=False, indent=2)
            )),
        ])
        parsed = _extract_json(str(response.content))
        updates = parsed.get("updated_sections") if isinstance(parsed, dict) else None
        if not isinstance(updates, dict):
            raise ValueError("증분 설계 결과에 updated_sections가 없습니다.")
        result = _clone_json(previous_sections)
        for key in affected:
            if isinstance(updates.get(key), dict):
                result[key] = updates[key]
        _sanitize_requirement_spec(result, request)
        result = _enforce_workflow_requirement_coverage(result, request)
        runtime = _clone_json((previous_design or {}).get("design_runtime") or {})
        if "database_plan" in affected:
            result["database_plan"] = build_database_plan(request, result)
            if result["database_plan"].get("enabled"):
                db_llm = model_for_task(LLMTask.DATABASE_SCHEMA_DESIGN, provider)
                try:
                    db_response = await db_llm.ainvoke([
                        SystemMessage(content=(
                            "당신은 PostgreSQL 증분 데이터 모델링 전문가입니다. 반드시 JSON 하나만 반환하세요. "
                            "전체 DB를 재설계하지 말고 이번 변경에 필요한 custom business Entity/관계만 수정/추가하십시오. "
                            "표준 Module 테이블은 AgentStudio가 보강하므로 중복 제안하지 마십시오. "
                            "반환 형식: {\"custom_tables\": [...], \"custom_design_notes\": [...]}"
                        )),
                        HumanMessage(content=(
                            "[이번 DB 변경분]\n" + json.dumps(change_payload, ensure_ascii=False, indent=2)
                            + "\n\n[현재 Requirement/Architecture]\n"
                            + json.dumps({
                                "requirement_spec": result.get("requirement_spec") or {},
                                "capability_plan": result.get("capability_plan") or {},
                                "agent_architecture": result.get("agent_architecture") or {},
                                "current_database_plan": result.get("database_plan") or {},
                            }, ensure_ascii=False, indent=2)
                        )),
                    ])
                    db_parsed = _extract_json(str(db_response.content))
                    raw_db = dict(result.get("database_plan") or {})
                    if isinstance(db_parsed, dict):
                        raw_db["custom_tables"] = db_parsed.get("custom_tables") or raw_db.get("custom_tables") or []
                        raw_db["custom_design_notes"] = db_parsed.get("custom_design_notes") or raw_db.get("custom_design_notes") or []
                    result["database_plan"] = raw_db
                    result["database_plan"] = build_database_plan(request, result)
                    runtime["database_provider"] = getattr(db_llm, "last_provider", "")
                    runtime["database_task"] = LLMTask.DATABASE_SCHEMA_DESIGN.value
                except Exception as db_exc:
                    runtime["database_provider"] = "deterministic_fallback"
                    runtime["database_error"] = f"{type(db_exc).__name__}: {db_exc}"
        runtime["workflow_provider"] = getattr(llm, "last_provider", "")
        runtime["incremental_revision"] = {
            "mode": "PARTIAL_REVISE",
            "llm_called": True,
            "changed_groups": changed_groups,
            "delta_messages": len(delta_messages),
            "change_request": delta_text[:4000],
            "changed_values": {key: (current_confirmed_requirements or {}).get(key) for key in changed_groups},
            "affected_sections": affected,
            "reused_sections": reused,
            "summary": str(parsed.get("summary") or ""),
        }
        result["design_runtime"] = runtime
        return result
    except Exception as exc:
        # Correctness wins over reuse when the focused revision cannot be parsed.
        result = await design_agent_factory(request, project_context, provider)
        result.setdefault("design_runtime", {})["incremental_revision"] = {
            "mode": "FULL_REDESIGN_FALLBACK",
            "llm_called": True,
            "changed_groups": changed_groups,
            "affected_sections": affected,
            "reused_sections": [],
            "error": f"{type(exc).__name__}: {exc}",
        }
        return result

