from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "coding_style"
RULES_PATH = DATA_DIR / "rules.json"
TEMPLATES_PATH = DATA_DIR / "templates.json"


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_rule_registry() -> dict:
    return _load_json(RULES_PATH)


def load_template_registry() -> dict:
    return _load_json(TEMPLATES_PATH)


def list_rules() -> list[dict]:
    return list(load_rule_registry().get("rules") or [])


def get_rule(rule_id: str) -> dict | None:
    wanted = (rule_id or "").strip().casefold()

    for rule in list_rules():
        if str(rule.get("id") or "").casefold() == wanted:
            return rule

    return None


def select_rules(
    tags: Iterable[str] | None = None,
    levels: Iterable[str] | None = None,
) -> list[dict]:
    rules = list_rules()

    requested_tags = {
        str(tag).strip().casefold()
        for tag in (tags or [])
        if str(tag).strip()
    }

    requested_levels = {
        str(level).strip().casefold()
        for level in (levels or [])
        if str(level).strip()
    }

    selected = []

    for rule in rules:
        level = str(rule.get("level") or "").casefold()

        if requested_levels and level not in requested_levels:
            continue

        applies = {
            str(item).strip().casefold()
            for item in (rule.get("applies_to") or [])
        }

        if (
            requested_tags
            and "all" not in applies
            and not requested_tags.intersection(applies)
        ):
            continue

        selected.append(rule)

    return selected


def format_rules_for_prompt(rules: Iterable[dict]) -> str:
    rows = []

    for rule in rules:
        rows.append(
            f"- [{rule.get('id')}] "
            f"({rule.get('level')}) "
            f"{rule.get('name')}: {rule.get('rule')}"
        )

    return "\n".join(rows)
