from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.entities import MCPServer, ToolRecord

from langchain_core.messages import HumanMessage, SystemMessage

from app.services.model_router import LLMTask, model_for_task
from app.services.prompt_tool_studio_executor import execute_studio_tool, preview_database_sql

_SYSTEM = """당신은 THEANOVA AgentStudio의 Prompt & Tool Studio 분석기입니다.
사용자 메시지를 Agent 설계 관점에서 구조화합니다.
반드시 JSON 객체만 반환하세요.

규칙:
1. utterance type은 multi-label입니다. 가능한 값: QUESTION, ANSWER, REQUEST, COMMAND, STATEMENT, CONFIRMATION, REJECTION, CORRECTION, SELECTION, FEEDBACK, GREETING, UNKNOWN.
2. intent와 utterance type을 분리합니다.
3. 한 메시지의 복합 요구를 semantic_units로 분리합니다.
4. extraction은 사용자가 실제로 말했거나 문맥상 높은 신뢰도로 추론할 수 있는 값만 냅니다.
5. 사용자가 확정한 기존 State를 임의로 덮어쓰지 않습니다. 변경 요청이면 status=CHANGED로 표시합니다.
6. source는 USER, INFERRED, DEFAULT, RECOMMENDED, SYSTEM 중 하나입니다.
7. context_relations에 pending question 답변 여부, 수정, 추가 요구, 확인 등을 표시합니다.
8. validation에 valid, missing, conflicts, warnings, confidence를 반환합니다.
9. response_plan은 반영 → 사용자 질문 답변 → 안내 → 다음 핵심 질문 1개의 순서를 지킵니다.
10. response_preview에는 내부 분석 용어를 노출하지 않습니다.

출력 스키마:
{
  "types": ["..."],
  "intents": ["..."],
  "semantic_units": [{"text":"...","types":["..."],"intents":["..."]}],
  "extraction": [{"key":"database.primary","label":"Database / Primary","value":"PostgreSQL","status":"CONFIRMED","source":"USER","confidence":0.98}],
  "context_relations": ["..."],
  "validation": {"valid":true,"missing":[],"conflicts":[],"warnings":[],"confidence":0.95},
  "response_plan": ["..."],
  "response_preview": "..."
}
"""


def _json_object(text: str) -> dict[str, Any]:
    raw = str(text or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.I)
    raw = re.sub(r"\s*```$", "", raw)
    try:
        value = json.loads(raw)
        return value if isinstance(value, dict) else {}
    except Exception:
        start, end = raw.find("{"), raw.rfind("}")
        if start >= 0 and end > start:
            try:
                value = json.loads(raw[start : end + 1])
                return value if isinstance(value, dict) else {}
            except Exception:
                pass
    return {}


async def analyze_prompt_tool_input(
    message: str,
    *,
    pending_question: dict[str, Any] | None = None,
    state: list[dict[str, Any]] | None = None,
    provider: str | None = None,
) -> dict[str, Any]:
    text = str(message or "").strip()
    if not text:
        return {"ok": False, "error": "분석할 사용자 메시지가 없습니다."}

    compact_state = []
    for row in list(state or [])[:80]:
        if not isinstance(row, dict):
            continue
        compact_state.append(
            {
                "key": str(row.get("key") or ""),
                "value": str(row.get("value") or ""),
                "status": str(row.get("status") or ""),
                "source": str(row.get("source") or ""),
            }
        )

    payload = {
        "message": text[:12000],
        "pending_question": pending_question or None,
        "current_state": compact_state,
    }
    try:
        llm = model_for_task(LLMTask.REQUIREMENTS_ANALYSIS, provider or None)
        result = await asyncio.wait_for(
            llm.ainvoke(
                [
                    SystemMessage(content=_SYSTEM),
                    HumanMessage(content=json.dumps(payload, ensure_ascii=False)),
                ]
            ),
            timeout=60.0,
        )
        data = _json_object(str(result.content or ""))
        if not data:
            return {"ok": False, "error": "LLM 구조화 응답을 JSON으로 해석하지 못했습니다."}
        return {"ok": True, "analysis": data}
    except asyncio.TimeoutError:
        return {"ok": False, "error": "AI 구조 분석 시간이 초과되었습니다. 로컬 분석 결과를 사용합니다."}
    except Exception as exc:
        return {"ok": False, "error": f"AI 구조 분석 실패: {exc}"}

async def run_prompt_tool_studio_test(
    message: str,
    *,
    mode: str = "FULL",
    compiled_prompt: str = "",
    routes: list[dict[str, Any]] | None = None,
    tools: list[dict[str, Any]] | None = None,
    intents: list[str] | None = None,
    provider: str | None = None,
    execute_tool: bool = False,
    tool_name: str = "",
    tool_arguments: dict[str, Any] | None = None,
    confirmation: bool = False,
    project_root: str = "",
) -> dict[str, Any]:
    """Runtime-backed Prompt & Tool Studio test.

    v5.586 uses one explicit Tool Executor contract for MCP/API/Database/Python.
    MCP is validated against the live registry, Database execution is read-only,
    and Python reuses AgentStudio's isolated worker with a project root. PROMPT/FULL
    invoke the same LLM router used by Agent design. Every stage emits a timed trace.
    """
    total_started = time.perf_counter()
    text = str(message or "").strip()
    test_mode = str(mode or "FULL").strip().upper()
    trace_steps: list[dict[str, Any]] = []

    def step(
        stage: str,
        status: str,
        detail: str,
        started: float,
        *,
        input_value: Any = None,
        output_value: Any = None,
        retry_count: int | None = None,
    ) -> None:
        row = {
            "stage": stage,
            "status": status,
            "detail": detail,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 2),
        }
        if input_value is not None:
            row["input"] = input_value
        if output_value is not None:
            row["output"] = output_value
        if retry_count is not None:
            row["retry_count"] = retry_count
        trace_steps.append(row)

    t = time.perf_counter()
    active_routes = [r for r in list(routes or []) if isinstance(r, dict) and bool(r.get("enabled", True))]
    tool_rows = [x for x in list(tools or []) if isinstance(x, dict)]
    intent_values = [str(x) for x in list(intents or []) if str(x).strip()]
    matched = [
        r for r in active_routes
        if str(r.get("intent") or "*") == "*" or str(r.get("intent") or "") in intent_values
    ]
    step("ROUTING", "PASS", f"활성 Rule {len(active_routes)}개 중 {len(matched)}개 매칭", t, input_value={"intents": intent_values}, output_value=matched)

    t = time.perf_counter()
    registry_rows: list[dict[str, Any]] = []
    try:
        async with SessionLocal() as db:
            rows = (await db.execute(select(ToolRecord))).scalars().all()
        registry_rows = [{
            "id": int(x.id),
            "server_id": int(x.mcp_server_id) if x.mcp_server_id is not None else None,
            "name": str(x.name or ""),
            "enabled": bool(x.enabled),
            "risk_level": int(x.risk_level or 0),
            "requires_confirmation": bool(x.requires_confirmation),
            "capability": str(x.capability or ""),
            "category": str(x.category or ""),
        } for x in rows]
        step("TOOL_REGISTRY", "PASS", f"실제 MCP Tool Registry {len(registry_rows)}개 조회", t)
    except Exception as exc:
        step("TOOL_REGISTRY", "CHECK", f"Registry 조회 실패: {exc}", t)

    studio_names = {str(x.get("name") or "").strip() for x in tool_rows if str(x.get("name") or "").strip()}
    registry_by_name = {x["name"]: x for x in registry_rows if x.get("name")}
    tool_errors: list[str] = []
    registry_matches: list[dict[str, Any]] = []
    t = time.perf_counter()
    for route in matched:
        if str(route.get("targetType") or route.get("target_type") or "").upper() != "TOOL":
            continue
        target = str(route.get("target") or "").strip()
        if target and target not in studio_names:
            tool_errors.append(f"Routing target Tool이 Studio Registry에 없습니다: {target}")
            continue
        row = registry_by_name.get(target)
        if row:
            registry_matches.append(row)
            if not row.get("enabled"):
                tool_errors.append(f"MCP Tool이 비활성 상태입니다: {target}")
        elif any(str(x.get("name") or "") == target and str(x.get("type") or "").upper() == "MCP" for x in tool_rows):
            tool_errors.append(f"MCP Tool이 실제 AgentStudio Registry에 없습니다: {target}")
    step("TOOL_CONTRACT", "FAIL" if tool_errors else "PASS", "; ".join(tool_errors) if tool_errors else "Studio Tool/실제 MCP Registry 계약 확인", t)

    # Compile the Studio routing definition through LangGraph itself. This is a
    # safe compile/shape validation and does not mutate the currently running Agent graph.
    graph_summary: dict[str, Any] = {}
    t = time.perf_counter()
    try:
        from langgraph.graph import END, START, StateGraph
        from typing_extensions import TypedDict

        class _StudioGraphState(TypedDict, total=False):
            message: str
            intent: str
            target: str

        builder = StateGraph(_StudioGraphState)
        builder.add_node("route", lambda state: state)
        terminal_nodes: list[str] = []
        for kind in ("tool", "workflow", "llm", "next_question"):
            name = f"target_{kind}"
            builder.add_node(name, lambda state: state)
            builder.add_edge(name, END)
            terminal_nodes.append(name)
        builder.add_edge(START, "route")
        builder.add_conditional_edges(
            "route",
            lambda state: str(state.get("target") or "llm").lower(),
            {
                "tool": "target_tool",
                "workflow": "target_workflow",
                "llm": "target_llm",
                "next_question": "target_next_question",
            },
        )
        compiled_graph = builder.compile()
        graph_summary = {
            "compiled": True,
            "nodes": ["route", *terminal_nodes],
            "active_rule_count": len(active_routes),
            "matched_rule_count": len(matched),
        }
        step("LANGGRAPH_COMPILE", "PASS", f"Routing Graph compile 완료 · Rule {len(active_routes)}개", t, input_value=active_routes, output_value=graph_summary)
        runtime_target = str((matched[0] if matched else {}).get("targetType") or (matched[0] if matched else {}).get("target_type") or "LLM").lower()
        runtime_target = runtime_target if runtime_target in {"tool", "workflow", "llm", "next_question"} else "llm"
        rt = time.perf_counter()
        graph_state = await compiled_graph.ainvoke({"message": text, "intent": intent_values[0] if intent_values else "", "target": runtime_target})
        graph_summary["runtime_target"] = runtime_target
        graph_summary["runtime_state"] = graph_state
        step("LANGGRAPH_RUNTIME", "PASS", f"StateGraph 실제 invoke · target={runtime_target}", rt, input_value={"message": text[:500], "target": runtime_target}, output_value=graph_state)
    except Exception as exc:
        graph_summary = {"compiled": False, "error": str(exc)}
        step("LANGGRAPH_COMPILE", "FAIL", str(exc), t)

    # v5.586 unified Tool Executor. Actual execution is always explicit. MCP uses
    # the live registry; API/Database/Python use the Studio Tool source contract.
    # Database execution is read-only, while Python reuses AgentStudio's isolated
    # external Python worker and requires a current project root.
    tool_execution: dict[str, Any] | None = None
    requested_tool = str(tool_name or "").strip()
    if execute_tool:
        t = time.perf_counter()
        if not requested_tool:
            tool_execution = {"ok": False, "error": "실행할 Tool 이름이 없습니다."}
            step("TOOL_EXECUTE", "FAIL", tool_execution["error"], t)
        else:
            studio_tool = next((x for x in tool_rows if str(x.get("name") or "") == requested_tool), None)
            registry = registry_by_name.get(requested_tool)
            if not studio_tool:
                tool_execution = {"ok": False, "error": "Studio에 등록된 Tool을 찾을 수 없습니다."}
                step("TOOL_EXECUTE", "FAIL", tool_execution["error"], t)
            else:
                try:
                    if str(studio_tool.get("type") or "").upper() == "DATABASE":
                        try:
                            preview = preview_database_sql(str(studio_tool.get("source") or ""), dict(tool_arguments or {}))
                            step("DB_SQL_PREVIEW", "PASS" if preview.get("read_only") else "CHECK", f"{preview.get('verb')} · read_only={preview.get('read_only')}", time.perf_counter(), input_value=preview)
                        except Exception as exc:
                            step("DB_SQL_PREVIEW", "FAIL", str(exc), time.perf_counter())
                    tool_execution = await execute_studio_tool(
                        studio_tool,
                        dict(tool_arguments or {}),
                        confirmation=confirmation,
                        project_root=str(project_root or ""),
                        registry=registry,
                    )
                    status = "CHECK" if tool_execution.get("blocked") else ("PASS" if tool_execution.get("ok") else "FAIL")
                    step("TOOL_EXECUTE", status, f"{requested_tool} · {str(studio_tool.get('type') or '').upper()} · attempt {tool_execution.get('attempts', 0)}", t, input_value=tool_arguments or {}, output_value=tool_execution, retry_count=max(0, int(tool_execution.get("attempts") or 1) - 1))
                except Exception as exc:
                    tool_execution = {"ok": False, "tool": requested_tool, "arguments": dict(tool_arguments or {}), "error": str(exc)}
                    step("TOOL_EXECUTE", "FAIL", str(exc), t)

    trace = [f"{x['stage']}={x['status']} ({x['elapsed_ms']}ms)" for x in trace_steps]
    result: dict[str, Any] = {
        "ok": (not tool_errors) and (tool_execution is None or bool(tool_execution.get("ok"))),
        "mode": test_mode,
        "matched_routes": matched,
        "tool_validation": {
            "valid": not tool_errors,
            "errors": tool_errors,
            "registered": sorted(studio_names),
            "registry_matches": registry_matches,
        },
        "trace": trace,
        "trace_steps": trace_steps,
        "response": "",
        "provider": "",
        "prompt_chars": len(str(compiled_prompt or "")),
        "graph_summary": graph_summary,
        "tool_execution": tool_execution,
    }
    if test_mode in {"TOOL", "TOOL_EXECUTE", "ROUTING", "INPUT", "EXTRACTION", "VALIDATION"}:
        result["total_elapsed_ms"] = round((time.perf_counter() - total_started) * 1000, 2)
        return result
    if test_mode == "FULL_EXECUTE" and tool_execution is not None and not bool(tool_execution.get("ok")):
        result["error"] = str(tool_execution.get("error") or "Tool 실행 실패로 Full Agent Test를 중단했습니다.")
        result["total_elapsed_ms"] = round((time.perf_counter() - total_started) * 1000, 2)
        return result
    if not text:
        result.update({"ok": False, "error": "테스트 사용자 메시지가 없습니다."})
        result["total_elapsed_ms"] = round((time.perf_counter() - total_started) * 1000, 2)
        return result

    t = time.perf_counter()
    try:
        llm = model_for_task(LLMTask.REQUIREMENTS_ANALYSIS, provider or None)
        system = str(compiled_prompt or _SYSTEM)[:30000]
        step("PROMPT_COMPILE", "PASS", f"실제 전송 System Prompt {len(system)}자", t, input_value={"prompt_chars": len(system), "message_chars": len(text)})
        t = time.perf_counter()
        human_content = text[:12000]
        if test_mode == "FULL_EXECUTE" and tool_execution and tool_execution.get("ok"):
            tool_context = json.dumps(tool_execution.get("result", tool_execution), ensure_ascii=False, default=str)[:12000]
            human_content = f"{human_content}\n\n[TOOL RESULT]\n{tool_context}"
            step("TOOL_RESULT_TO_LLM", "PASS", f"Tool 결과 {len(tool_context)}자를 LLM Runtime 입력에 연결", time.perf_counter(), input_value={"tool": requested_tool, "chars": len(tool_context)})
        reply = await asyncio.wait_for(
            llm.ainvoke([SystemMessage(content=system), HumanMessage(content=human_content)]),
            timeout=60.0,
        )
        result["response"] = str(reply.content or "")
        result["provider"] = llm.__class__.__name__
        usage = dict(getattr(reply, "usage_metadata", None) or {})
        response_meta = dict(getattr(reply, "response_metadata", None) or {})
        model_name = str(response_meta.get("model_name") or response_meta.get("model") or getattr(llm, "model_name", "") or getattr(llm, "model", "") or "")
        result["llm_usage"] = {"model": model_name, "tokens": usage, "cost": None, "cost_note": "Provider별 가격표를 추측하지 않고 실제 usage metadata만 기록합니다."}
        step("LLM_RUNTIME", "PASS", f"응답 {len(result['response'])}자 · model={model_name or result['provider']}", t, output_value={"provider": result["provider"], "model": model_name, "usage": usage, "response": result["response"]})
        result["trace_steps"] = trace_steps
        result["trace"] = [f"{x['stage']}={x['status']} ({x['elapsed_ms']}ms)" for x in trace_steps]
        result["total_elapsed_ms"] = round((time.perf_counter() - total_started) * 1000, 2)
        return result
    except asyncio.TimeoutError:
        step("LLM_RUNTIME", "FAIL", "60초 Timeout", t)
        result.update({"ok": False, "error": "실제 LLM 테스트 시간이 초과되었습니다."})
    except Exception as exc:
        step("LLM_RUNTIME", "FAIL", str(exc), t)
        result.update({"ok": False, "error": f"실제 LLM 테스트 실패: {exc}"})
    result["trace_steps"] = trace_steps
    result["trace"] = [f"{x['stage']}={x['status']} ({x['elapsed_ms']}ms)" for x in trace_steps]
    result["total_elapsed_ms"] = round((time.perf_counter() - total_started) * 1000, 2)
    return result

