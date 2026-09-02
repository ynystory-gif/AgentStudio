from __future__ import annotations

"""Build SQL downloads from the exact Learning Center list snapshot.

v5.448 invariant:
- The UI list decides which row identities are visible.
- SQL export receives those exact IDs and creates a one-row-per-visible-item query.
- Shared Dataset rows are never filtered by source PC.
- Only per-PC learning application state is filtered by the current PC name.

This deliberately avoids maintaining a second, hand-written approximation of the
Learning Center filtering/grouping logic.  The misjudgment screen contains Python-side
family grouping and current-PC learned-state rules that cannot be reproduced reliably by
a static SQL string.  Exporting the exact visible ID snapshot guarantees that executing
the downloaded SQL returns the same list row count as the screen at download time.
"""

from app.core.machine_identity import current_pc_name


def _sql_literal(value: str) -> str:
    return "'" + str(value or "").replace("'", "''") + "'"


def _unique_ids(values: list[str] | None) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in list(values or []):
        item = str(value or "").strip()
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result


def _values_cte(name: str, column: str, ids: list[str]) -> str:
    if not ids:
        return f"{name}({column}, display_order) AS (SELECT NULL::varchar, NULL::integer WHERE FALSE)"
    rows = ",\n        ".join(f"({_sql_literal(item)}, {index})" for index, item in enumerate(ids, 1))
    return f"{name}({column}, display_order) AS (\n    VALUES\n        {rows}\n)"


def build_learning_list_sql(
    kind: str,
    *,
    case_ids: list[str] | None = None,
    dataset_ids: list[str] | None = None,
    provider: str = "",
) -> dict:
    normalized_kind = str(kind or "").strip().lower()
    pc_name = current_pc_name()
    cases = _unique_ids(case_ids)
    datasets = _unique_ids(dataset_ids)
    provider_note = str(provider or "").strip() or "전체"

    if normalized_kind == "cases":
        cte = _values_cte("visible_cases", "misjudgment_id", cases)
        sql = f"""-- THEANOVA AgentStudio v5.448
-- LLM 학습 센터 > 1. 오판 수집 > 화면 조회 SQL
-- 다운로드 시점 화면 행 수: {len(cases)}건
-- 화면 Provider 필터: {provider_note}
-- 현재 PC: {pc_name}
-- 중요: 오판 목록은 Python에서 유사 오판 그룹화 + 현재 PC 학습 이력 제외를 수행합니다.
--       아래 visible_cases는 화면이 실제 표시한 대표 오판 ID 스냅샷이므로 결과 건수가 화면과 동일합니다.
WITH {cte}
SELECT
    v.display_order                    AS display_order,
    c.id                               AS misjudgment_id,
    c.group_id                         AS group_id,
    c.status                           AS status,
    c.confidence                       AS confidence,
    c.source_pc_name                   AS source_pc_name,
    c.provider                         AS provider,
    c.model                            AS model,
    c.task                             AS task,
    c.detection_reason                 AS detection_reason,
    c.user_request                     AS user_request,
    c.wrong_output                     AS wrong_output,
    c.correction_evidence              AS correction_evidence,
    c.expected_output                  AS expected_output,
    c.error_type                       AS error_type,
    c.error_reason                     AS error_reason,
    c.domain                           AS domain,
    c.topic                            AS topic,
    c.training_eligible                AS training_eligible,
    c.created_at                       AS created_at,
    c.updated_at                       AS updated_at,
    (SELECT COUNT(*)
       FROM llm_learning_datasets d0
      WHERE d0.source_case_id = c.id)  AS exact_dataset_count,
    EXISTS (
        SELECT 1
          FROM llm_learning_datasets d1
          JOIN llm_learning_pc_applications a1
            ON a1.dataset_id = d1.id
           AND a1.pc_name = {_sql_literal(pc_name)}
         WHERE d1.source_case_id = c.id
           AND a1.installed = TRUE
           AND a1.enabled = TRUE
    )                                  AS current_pc_exact_learning_applied
FROM visible_cases v
JOIN llm_misjudgment_cases c
  ON c.id = v.misjudgment_id
ORDER BY v.display_order;
"""
        return {
            "ok": True,
            "kind": "cases",
            "file_name": "LLM_오판_수집_화면_조회.sql",
            "sql": sql,
            "expected_count": len(cases),
            "current_pc_name": pc_name,
            "scope": "exact_visible_snapshot",
        }

    if normalized_kind == "datasets":
        cte = _values_cte("visible_datasets", "dataset_id", datasets)
        sql = f"""-- THEANOVA AgentStudio v5.448
-- LLM 학습 센터 > 2. 수집 문제 / Dataset > 화면 조회 SQL
-- 다운로드 시점 화면 행 수: {len(datasets)}건
-- Dataset은 모든 PC의 공용 학습 데이터이므로 source_pc_name으로 WHERE 필터하지 않습니다.
-- '현재 PC 학습 적용 여부'만 아래 LEFT JOIN의 pc_name={pc_name} 조건으로 판정합니다.
WITH {cte}
SELECT
    v.display_order                    AS display_order,
    d.id                               AS dataset_id,
    d.source_case_id                   AS dataset_source_case_id,
    c.id                               AS misjudgment_id,
    c.source_pc_name                   AS misjudgment_source_pc,
    d.source_pc_name                   AS dataset_source_pc,
    d.status                           AS dataset_status,
    d.provider                         AS teacher_provider,
    d.source_provider                  AS source_provider,
    d.source_model                     AS source_model,
    d.problem_count                    AS dataset_problem_count,
    (SELECT COUNT(*)
       FROM llm_learning_problems p0
      WHERE p0.dataset_id = d.id)      AS problem_row_count,
    d.scope_json                       AS learning_scope,
    COALESCE(a.pc_name, {_sql_literal(pc_name)}) AS current_pc_name,
    COALESCE(a.status, 'not_applied')  AS current_pc_learning_status,
    COALESCE(a.installed, FALSE)       AS current_pc_installed,
    COALESCE(a.enabled, FALSE)         AS current_pc_enabled,
    COALESCE(a.model_name, '')         AS current_pc_model,
    CASE
      WHEN c.id IS NULL THEN 'SOURCE_CASE_MISSING'
      WHEN EXISTS (
          SELECT 1
            FROM llm_learning_problems p1
           WHERE p1.dataset_id = d.id
             AND COALESCE(p1.source_case_id, '') <> COALESCE(d.source_case_id, '')
      ) THEN 'PROBLEM_SOURCE_ID_MISMATCH'
      ELSE 'SOURCE_ID_OK'
    END                                AS source_id_check,
    d.created_at                       AS dataset_created_at,
    d.updated_at                       AS dataset_updated_at
FROM visible_datasets v
JOIN llm_learning_datasets d
  ON d.id = v.dataset_id
LEFT JOIN llm_misjudgment_cases c
  ON c.id = d.source_case_id
LEFT JOIN llm_learning_pc_applications a
  ON a.dataset_id = d.id
 AND a.pc_name = {_sql_literal(pc_name)}
ORDER BY v.display_order;
"""
        return {
            "ok": True,
            "kind": "datasets",
            "file_name": "LLM_수집_문제_Dataset_화면_조회.sql",
            "sql": sql,
            "expected_count": len(datasets),
            "current_pc_name": pc_name,
            "scope": "shared_datasets_current_pc_application",
        }

    if normalized_kind == "training":
        cte = _values_cte("visible_datasets", "dataset_id", datasets)
        sql = f"""-- THEANOVA AgentStudio v5.448
-- LLM 학습 센터 > 3. PC별 학습 적용 관리 > 화면 조회 SQL
-- 다운로드 시점 화면 행 수: {len(datasets)}건
-- Dataset 자체는 공용 전체 조회이며, 학습 적용 상태만 현재 PC({pc_name}) 조건으로 조회합니다.
WITH {cte}
SELECT
    v.display_order                    AS display_order,
    d.id                               AS dataset_id,
    d.source_case_id                   AS source_case_id,
    d.source_pc_name                   AS dataset_source_pc,
    d.status                           AS dataset_status,
    d.problem_count                    AS problem_count,
    {_sql_literal(pc_name)}            AS current_pc_name,
    COALESCE(a.id, '')                 AS application_id,
    COALESCE(a.model_name, '')         AS model_name,
    COALESCE(a.base_model, '')         AS base_model,
    COALESCE(a.installed, FALSE)       AS installed,
    COALESCE(a.enabled, FALSE)         AS enabled,
    COALESCE(a.status, 'not_applied')  AS application_status,
    COALESCE(a.last_error, '')         AS last_error,
    a.applied_at                       AS applied_at,
    a.updated_at                       AS application_updated_at,
    (SELECT COUNT(*)
       FROM llm_learning_pc_applications ax
      WHERE ax.dataset_id = d.id)      AS all_pc_application_count
FROM visible_datasets v
JOIN llm_learning_datasets d
  ON d.id = v.dataset_id
LEFT JOIN llm_learning_pc_applications a
  ON a.dataset_id = d.id
 AND a.pc_name = {_sql_literal(pc_name)}
ORDER BY v.display_order;
"""
        return {
            "ok": True,
            "kind": "training",
            "file_name": "LLM_PC별_학습_적용_관리_화면_조회.sql",
            "sql": sql,
            "expected_count": len(datasets),
            "current_pc_name": pc_name,
            "scope": "shared_datasets_current_pc_application",
        }

    raise ValueError("지원하지 않는 학습 SQL 종류입니다. cases, datasets, training 중 하나를 사용하세요.")
