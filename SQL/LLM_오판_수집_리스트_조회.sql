-- THEANOVA AgentStudio v5.442
-- LLM 학습 센터 > 1. 오판 수집 리스트 진단 조회
-- AgentStudio Runtime DB의 현재 search_path(theanova_agentstudio 등)를 기준으로 실행합니다.
SELECT
    c.id                              AS misjudgment_id,
    c.group_id                        AS group_id,
    c.status                          AS status,
    c.confidence                      AS confidence,
    c.source_pc_name                  AS source_pc_name,
    c.provider                        AS provider,
    c.model                           AS model,
    c.task                            AS task,
    c.detection_reason                AS detection_reason,
    c.user_request                    AS user_request,
    c.wrong_output                    AS wrong_output,
    c.correction_evidence             AS correction_evidence,
    c.expected_output                 AS expected_output,
    c.error_type                      AS error_type,
    c.error_reason                    AS error_reason,
    c.domain                          AS domain,
    c.topic                           AS topic,
    c.training_eligible               AS training_eligible,
    c.created_at                      AS created_at,
    c.updated_at                      AS updated_at,
    d.id                              AS dataset_id,
    d.source_case_id                  AS dataset_source_case_id,
    a.pc_name                         AS applied_pc_name,
    a.status                          AS pc_learning_status,
    a.enabled                         AS pc_learning_enabled,
    a.model_name                      AS pc_learning_model
FROM llm_misjudgment_cases c
LEFT JOIN llm_learning_datasets d
       ON d.source_case_id = c.id
LEFT JOIN llm_learning_pc_applications a
       ON a.dataset_id = d.id
WHERE c.status <> 'rejected'
ORDER BY c.updated_at DESC, c.id;
