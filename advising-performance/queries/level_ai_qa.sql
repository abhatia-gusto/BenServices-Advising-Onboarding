-- ═══════════════════════════════════════════════════════════════════════════════
-- LEVEL AI QA — Per-Conversation Detail Query
-- ═══════════════════════════════════════════════════════════════════════════════
-- Source:   bi.fct_level_ai_conversation_asr_log
-- Grain:    One row per QA-scored Benefits Operations conversation
-- Powers:   Advising Performance Dashboard v8+ → metric `quality` (Level AI QA)
-- Filter:   QA_SCORE IS NOT NULL  +  RECORD_TYPE_NAME / channel restricted to
--           Benefits ops case types  +  date window on convo_dt (MT)
--
-- PARAMETERS
--   {{ start_date }}   DATE   inclusive
--   {{ end_date }}     DATE   inclusive
--
-- AGGREGATION TO EMBED IN var D
--   Per advisor (a.user_email → full_name), per month (convo_month):
--       quality.{month}.sum   = SUM(qa_points_earned)
--       quality.{month}.count = SUM(qa_points_possible)   -- so % = sum/count
--   Then in the dashboard: r.quality = sum/count → 0–100 score.
--   NOTE: confirm the sum/count convention matches what v8 already expects.
--         v7's cmAll sums `quality[mo].sum` and `quality[mo].count` and divides
--         — so use SUM(qa_score) / SUM(max_qa_score) per advisor × month.
-- ═══════════════════════════════════════════════════════════════════════════════
WITH temp AS (
  SELECT
    convert_timezone('UTC','America/Denver', a.conversation_ts)::date  AS convo_dt,
    DATE_TRUNC('month',
      convert_timezone('UTC','America/Denver', a.conversation_ts))::date AS convo_month,
    a.convo_id,
    a.user_id,
    a.external_user_id,
    a.user_email,
    ee.name                                                            AS full_name,
    a.qa_status_name,
    lower(a.channel_name)                                              AS channel,
    ee.team,
    ee.sub_team,
    b.record_type_name,
    b.casenumber,
    b.ownerid,
    a.qa_score                                                         AS qa_points_earned,
    a.max_qa_score                                                     AS qa_points_possible,
    a.qa_score::float / NULLIF(a.max_qa_score::float, 0)               AS evaluation_score,
    CASE WHEN a.qa_status_name = 'Accepted' THEN 1 ELSE 0 END          AS qa_evaluation_flag,
    a.icsat_score,
    CASE WHEN a.icsat_score IS NOT NULL THEN 1 ELSE 0 END              AS icsat_interactions,
    a.sentiment_score,
    a.resolution_score,
    a.customer_effort_score
  FROM bi.fct_level_ai_conversation_asr_log a
  LEFT JOIN bi.cases b
    ON a.case_number = b.casenumber
  JOIN bi.gusto_employees ee
    ON convert_timezone('UTC','America/Denver', a.conversation_ts)::date
         BETWEEN ee.effect_start_dt AND ee.effect_end_dt
   AND a.user_email = ee.email
   AND ee.team IN ('Benefits Operations', 'Benefits Advising', 'Benefits Support', 'Benefits Onboarding')
  WHERE a.qa_score IS NOT NULL
    AND NVL(b.record_type_name, 'Call') IN (
          'Benefits Renewal Case',
          'Benefits BYB',
          'Benefits New Plan Case',
          'MF NHE',
          'MF Member/Group Updates',
          'Call'
        )
    AND convert_timezone('UTC','America/Denver', a.conversation_ts)::date >= '{{ start_date }}'::date
    AND convert_timezone('UTC','America/Denver', a.conversation_ts)::date <= '{{ end_date }}'::date
)
SELECT *
FROM temp
ORDER BY convo_dt, user_email
;
