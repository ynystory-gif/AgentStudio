-- THEANOVA AgentStudio v5.442
-- LLM 학습 센터 > 3. PC별 학습 적용 관리 리스트 진단 조회
SELECT
    a.id                              AS application_id,
    a.pc_name                         AS pc_name,
    a.dataset_id                      AS dataset_id,
    d.source_case_id                  AS source_case_id,
    c.id                              AS misjudgment_id,
    d.status                          AS dataset_status,
    d.problem_count                   AS problem_count,
    a.model_name                      AS model_name,
    a.base_model                      AS base_model,
    a.installed                       AS installed,
    a.enabled                         AS enabled,
    a.status                          AS application_status,
    a.last_error                      AS last_error,
    a.applied_at                      AS applied_at,
    a.updated_at                      AS updated_at,
    a.metadata_json                   AS application_metadata,
    CASE
      WHEN c.id IS NULL THEN 'SOURCE_CASE_MISSING'
      WHEN c.id = d.source_case_id THEN 'SOURCE_ID_OK'
      ELSE 'SOURCE_ID_MISMATCH'
    END                               AS source_id_check
FROM llm_learning_pc_applications a
JOIN llm_learning_datasets d
  ON d.id = a.dataset_id
LEFT JOIN llm_misjudgment_cases c
  ON c.id = d.source_case_id
ORDER BY a.pc_name, a.updated_at DESC, a.dataset_id;
