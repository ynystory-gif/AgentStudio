from __future__ import annotations

from app.services.coding_style_registry import load_template_registry


def list_code_templates() -> list[dict]:
    return list(load_template_registry().get("templates") or [])


def select_code_templates(tags: list[str]) -> list[dict]:
    wanted = {
        str(tag).strip().casefold()
        for tag in (tags or [])
        if str(tag).strip()
    }

    result = []

    for template in list_code_templates():
        template_tags = {
            str(tag).strip().casefold()
            for tag in (template.get("tags") or [])
        }

        if not wanted or wanted.intersection(template_tags):
            result.append(template)

    return result
