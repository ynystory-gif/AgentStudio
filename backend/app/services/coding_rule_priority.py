from __future__ import annotations

import json
from pathlib import Path


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "coding_style"
POLICY_PATH = DATA_DIR / "rule_policy.json"


def load_rule_policy() -> dict:
    if not POLICY_PATH.exists():
        return {}
    return json.loads(
        POLICY_PATH.read_text(encoding="utf-8")
    )


def rule_priority_score(rule: dict) -> int:
    policy = load_rule_policy()

    level_map = policy.get("level_priority") or {}
    category_map = policy.get("category_priority") or {}

    level = str(rule.get("level") or "").strip().casefold()
    category = str(rule.get("category") or "").strip().casefold()

    return int(level_map.get(level, 0)) + int(
        category_map.get(category, 0)
    )


def resolve_rule_conflicts(
    rules: list[dict],
) -> dict:
    """
    현재 요청에 선택된 규칙들의 우선순위를 정렬합니다.
    실제 삭제보다는 적용 순서를 결정하고,
    required + security/correctness 규칙을 최상단에 둡니다.
    """
    sorted_rules = sorted(
        rules,
        key=rule_priority_score,
        reverse=True,
    )

    return {
        "rules": sorted_rules,
        "scores": {
            str(rule.get("id")): rule_priority_score(rule)
            for rule in sorted_rules
        },
    }
