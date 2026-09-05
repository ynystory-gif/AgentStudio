-- THEANOVA AgentStudio v5.445
-- LLM 학습 센터 > 1. 오판 수집 > 화면 조회 SQL
-- 다운로드 시점 화면 행 수: 2건
-- 화면 Provider 필터: 전체
-- 현재 PC: DESKTOP-R0PILUB_학원
-- 중요: 오판 목록은 Python에서 유사 오판 그룹화 + 현재 PC 학습 이력 제외를 수행합니다.
--       아래 visible_cases는 화면이 실제 표시한 대표 오판 ID 스냅샷이므로 결과 건수가 화면과 동일합니다.
WITH visible_cases(misjudgment_id, display_order) AS (
    VALUES
        ('20fae3b928274a80b04042db828462b1', 1),
        ('bf05d3852843487c92c3977d1841a35b', 2)
)
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
           AND a1.pc_name = 'DESKTOP-R0PILUB_학원'
         WHERE d1.source_case_id = c.id
           AND a1.installed = TRUE
           AND a1.enabled = TRUE
    )                                  AS current_pc_exact_learning_applied
FROM visible_cases v
JOIN llm_misjudgment_cases c
  ON c.id = v.misjudgment_id
ORDER BY v.display_order;
