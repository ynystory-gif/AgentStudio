from __future__ import annotations

import json
from pathlib import Path


POLICY_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "coding_style"
    / "agent_factory_policy.json"
)


def load_agent_factory_policy() -> dict:
    """AgentStudio의 Agent Factory 제작 기본 방향을 UTF-8로 읽습니다."""
    if not POLICY_PATH.exists():
        return {}
    return json.loads(POLICY_PATH.read_text(encoding="utf-8"))


def format_agent_factory_policy_for_prompt() -> str:
    """프로젝트 단위 Agent 생성 프롬프트에 넣을 제작 정책을 구성합니다."""
    policy = load_agent_factory_policy()
    if not policy:
        return "(Agent Factory 정책 없음)"

    workflow = " → ".join(policy.get("studio_workflow") or [])
    designers = ", ".join(policy.get("required_designers") or [])
    principles = "\n".join(
        f"- {item}" for item in (policy.get("principles") or [])
    )

    return (
        f"정체성: {policy.get('identity', '')}\n"
        f"제작 Workflow: {workflow}\n"
        f"핵심 역할: {designers}\n"
        f"제작 원칙:\n{principles}"
    )
