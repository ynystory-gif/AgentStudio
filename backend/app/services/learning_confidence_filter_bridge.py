from __future__ import annotations

"""Filter the LLM Learning Center misjudgment list to confirmed-confidence items.

The learning workflow auto-confirms cases at confidence >= 0.75.  The visible
misjudgment queue should use the same threshold so operators see only items
that are eligible to become learning topics.  Lower-confidence candidates
remain stored in the shared DB for diagnostics/history, but are not returned
in the Learning Center list.
"""

from app.services import learning_collection_service as collection

MIN_VISIBLE_CONFIDENCE = 0.75
_original_list_aggregated_misjudgment_cases = collection.list_aggregated_misjudgment_cases


async def list_aggregated_misjudgment_cases_75_plus(
    provider: str = "",
    status: str = "",
    limit: int = 500,
) -> dict:
    # Ask the underlying service for enough rows before applying the visibility
    # threshold so the requested page size still has the best chance of being full.
    raw_limit = max(1, min(max(int(limit or 500) * 2, 500), 2000))
    result = await _original_list_aggregated_misjudgment_cases(provider, status, raw_limit)
    items = list(result.get("items") or [])

    visible = [
        item
        for item in items
        if float(item.get("confidence") or 0.0) >= MIN_VISIBLE_CONFIDENCE
    ]
    visible = visible[: max(1, min(int(limit or 500), 2000))]

    providers: dict[str, int] = {}
    for row in visible:
        key = f"{row.get('provider', 'unknown')}::{row.get('model', 'unknown')}"
        providers[key] = providers.get(key, 0) + int(row.get("occurrence_count") or 1)

    result["items"] = visible
    result["total"] = len(visible)
    result["providers"] = providers
    result["visible_confidence_min"] = MIN_VISIBLE_CONFIDENCE
    result["hidden_low_confidence_count"] = len(items) - len(visible)
    return result


collection.list_aggregated_misjudgment_cases = list_aggregated_misjudgment_cases_75_plus
