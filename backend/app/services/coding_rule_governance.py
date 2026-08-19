from __future__ import annotations

from copy import deepcopy
from difflib import SequenceMatcher

from app.services.coding_style_registry import list_rules


CATEGORY_FAMILY = {
    "prompt_strategy": "prompt",
    "model": "llm",
    "portability": "environment",
    "version_control": "maintainability",
}


def _normalize(text: str) -> str:
    return " ".join(
        str(text or "")
        .casefold()
        .replace("`", "")
        .replace('"', "")
        .replace("'", "")
        .split()
    )


def _family(category: str) -> str:
    normalized = str(category or "").strip().casefold()
    return CATEGORY_FAMILY.get(normalized, normalized)


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(
        None,
        _normalize(a),
        _normalize(b),
    ).ratio()


def compare_rule_candidate(
    candidate: dict,
    existing_rules: list[dict] | None = None,
) -> dict:
    """
    후보 규칙을 기존 Registry와 비교해 다음 중 하나로 판정합니다.

    new         : 의미상 새로운 규칙
    strengthen  : 기존 규칙을 더 구체적/강하게 만드는 후보
    merge       : 기존 규칙과 사실상 동일하여 병합 권장
    conditional : 기존 규칙과 관련되지만 특정 상황에서만 적용
    exclude     : 코딩 규칙이 아니라 교육 설명/참고 정보
    """
    existing = existing_rules or list_rules()

    classification = str(
        candidate.get("classification")
        or candidate.get("level")
        or ""
    ).strip().casefold()

    if classification == "reference_only":
        return {
            "decision": "exclude",
            "reason": "reference_only 자료는 Registry 규칙으로 추가하지 않습니다.",
            "matched_rule_id": None,
            "similarity": 0.0,
        }

    if classification == "template_candidate":
        return {
            "decision": "conditional",
            "reason": "코딩 규칙보다 Template Registry 후보로 처리하는 편이 적합합니다.",
            "matched_rule_id": None,
            "similarity": 0.0,
        }

    cand_category = _family(
        str(candidate.get("category") or "")
    )

    cand_text = " ".join([
        str(candidate.get("name") or ""),
        str(candidate.get("rule") or ""),
    ])

    best = None
    best_score = 0.0

    for rule in existing:
        rule_category = _family(
            str(rule.get("category") or "")
        )

        if cand_category and rule_category and cand_category != rule_category:
            continue

        rule_text = " ".join([
            str(rule.get("name") or ""),
            str(rule.get("rule") or ""),
        ])

        score = _similarity(cand_text, rule_text)

        if score > best_score:
            best_score = score
            best = rule

    if best is None or best_score < 0.42:
        decision = (
            "conditional"
            if classification == "conditional"
            else "new"
        )

        return {
            "decision": decision,
            "reason": "기존 Registry에서 의미상 충분히 유사한 규칙을 찾지 못했습니다.",
            "matched_rule_id": None,
            "similarity": round(best_score, 3),
        }

    if best_score >= 0.82:
        return {
            "decision": "merge",
            "reason": "기존 규칙과 의미가 사실상 동일합니다. 새 ID 생성보다 병합을 권장합니다.",
            "matched_rule_id": best.get("id"),
            "similarity": round(best_score, 3),
        }

    candidate_rule = _normalize(candidate.get("rule") or "")
    existing_rule = _normalize(best.get("rule") or "")

    if (
        len(candidate_rule) > len(existing_rule) * 1.15
        or classification == "required"
        and str(best.get("level") or "") != "required"
    ):
        return {
            "decision": "strengthen",
            "reason": "기존 규칙보다 구체적이거나 더 높은 강도로 적용할 수 있습니다.",
            "matched_rule_id": best.get("id"),
            "similarity": round(best_score, 3),
        }

    return {
        "decision": (
            "conditional"
            if classification == "conditional"
            else "merge"
        ),
        "reason": "기존 규칙과 관련성이 높아 별도 신규 규칙보다 기존 규칙과의 통합이 적합합니다.",
        "matched_rule_id": best.get("id"),
        "similarity": round(best_score, 3),
    }


def classify_candidates(
    candidates: list[dict],
) -> list[dict]:
    existing = list_rules()
    results = []

    for candidate in candidates:
        decision = compare_rule_candidate(
            candidate,
            existing_rules=existing,
        )

        results.append({
            "candidate": deepcopy(candidate),
            **decision,
        })

    return results
