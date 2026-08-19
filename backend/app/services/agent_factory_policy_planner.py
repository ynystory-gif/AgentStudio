from __future__ import annotations

import json
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "agent_factory"

POLICY_FILES = [
    "async_strategy_policy.json",
    "dependency_lifecycle_policy.json",
    "api_contract_policy.json",
    "file_placement_policy.json",
    "api_error_security_policy.json",
    "agent_api_test_policy.json",
    "streaming_strategy_policy.json",
    "streaming_event_contract.json",
    "streaming_error_policy.json",
    "streaming_client_policy.json",
    "streaming_test_policy.json",
    "streaming_deployment_policy.json",
    "settings_requirement_policy.json",
    "settings_schema_policy.json",
    "settings_ui_policy.json",
    "settings_test_policy.json",
]


def _load(name: str) -> dict:
    path = DATA_DIR / name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_agent_factory_policies() -> dict:
    result = {}

    for filename in POLICY_FILES:
        payload = _load(filename)
        key = str(payload.get("id") or filename)
        result[key] = payload

    return result


def format_factory_policies_for_prompt() -> str:
    policies = load_agent_factory_policies()
    sections = []

    for policy_id, policy in policies.items():
        purpose = policy.get("purpose") or ""
        sections.append(
            f"[{policy_id}]\n"
            f"목적: {purpose}\n"
            f"{json.dumps(policy, ensure_ascii=False, indent=2)}"
        )

    return "\n\n".join(sections)


def infer_fastapi_factory_plan(
    request: str,
    project_scope: bool = True,
) -> dict:
    text = (request or "").casefold()

    fastapi = any(
        token in text
        for token in (
            "fastapi",
            "api",
            "backend",
            "백엔드",
            "엔드포인트",
            "http",
        )
    )

    llm = any(
        token in text
        for token in (
            "llm",
            "openai",
            "ollama",
            "agent",
            "에이전트",
            "langchain",
        )
    )

    needs_async = fastapi and (
        llm
        or "db" in text
        or "database" in text
        or "api" in text
    )

    streaming_candidate = any(
        token in text
        for token in (
            "stream",
            "streaming",
            "sse",
            "실시간",
            "스트리밍",
            "토큰 단위",
            "타이핑",
        )
    )

    return {
        "project_scope": project_scope,
        "fastapi_candidate": fastapi,
        "llm_candidate": llm,
        "async_candidate": needs_async,
        "streaming_candidate": streaming_candidate,
        "apply": [
            "FILE_PLACEMENT_POLICY",
            "API_CONTRACT_POLICY",
            "DEPENDENCY_LIFECYCLE_POLICY",
            "API_ERROR_SECURITY_POLICY",
            "AGENT_API_TEST_POLICY",
            *(
                ["ASYNC_STRATEGY_POLICY"]
                if needs_async
                else []
            ),
            *(
                [
                    "STREAMING_STRATEGY_POLICY",
                    "STREAMING_EVENT_CONTRACT",
                    "STREAMING_ERROR_POLICY",
                    "STREAMING_CLIENT_POLICY",
                    "STREAMING_TEST_POLICY",
                    "STREAMING_DEPLOYMENT_POLICY",
                ]
                if streaming_candidate
                else []
            ),
        ] if fastapi else [],
    }
