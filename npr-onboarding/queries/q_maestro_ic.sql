-- Maestro Adherence diagnostic (non-scored), per-IC per-MONTH.
-- NEW METHOD (2026-11): matches the daily/weekly Maestro transparency report posted in #oa-pe.
--   Canonical source: skills/maestro-adherence/SKILL.md (CO-baseline + known-item exclusions + AO set-aside).
-- Cohort = benefit orders (New Plan + Renewal, non-cancelled) that have LEFT RFSP at the BO level,
--   keyed on the LAST live carrier order to hit RFSP (bi.carrier_orders, cancelled COs ignored),
--   bucketed by the PT date of that CO baseline.
-- Known-item exclusions (3): discarded-flow custom tasks, discarded-flow survey tasks, and the
--   "set open enrollment window" + "intro email" title (OAs complete it; system blocks it on ancillary-only).
-- AO (Agentic Operator) set-aside: AO-handled orders removed from denominator and buckets.
-- Denominator (MA_ELIGIBLE) = non-AO orders that have >=1 ORIGINAL task.
-- Numerator (MA_ADHERENT)   = non-AO orders that are all-complete-adjusted OR all-excluded-adherent.
-- Attribution = benefit_order_owner (matches the transparency report); PE = COALESCE(owner_pe_name_current, owner_pe_name).
-- Window = all-time from 2026-01-01 (pre-Nov approximate: carrier_orders.cancel_flag + AO enablement are current-state).
WITH rfsp_from_status AS (
  SELECT h.sfdc_object_id AS sfdc_benefit_order_id,
         MAX(CASE WHEN TRIM(LOWER(h.from_status))='ready for submission prep' THEN 1 ELSE 0 END) AS rfsp_flag,
         MIN(CASE WHEN TRIM(LOWER(h.from_status))='ready for submission prep' THEN h.start_time::date END) AS first_rfsp_dt,
         MIN(CASE WHEN TRIM(LOWER(h.from_status))='ready for submission prep' THEN h.start_time END) AS first_rfsp_ts
  FROM bi.benefit_order_status_change_history h
  WHERE DATE_TRUNC('month', h.cvg_effective_dt) BETWEEN DATE '2025-01-01' AND DATE '2027-01-01'
  GROUP BY 1
),
-- ===== Carrier-order (CO) baseline cohort (effective Nov 3 2026, last-CO-to-hit rule) =====
co AS (   -- live carrier orders only (cancelled COs ignored)
  SELECT c.sfdc_benefit_order_id AS oid, c.sfdc_carrier_order_id AS coid,
         COALESCE(ARRAY_CONTAINS('Medical'::VARIANT, SPLIT(REPLACE(c.benefit_types,'; ',';'),';')), FALSE) AS is_med,
         c.first_ready_for_submission_prep_ts AS rts
  FROM bi.carrier_orders c WHERE COALESCE(c.cancel_flag, FALSE) = FALSE
),
co1 AS (
  SELECT oid, COUNT(*) n_co, SUM(IFF(is_med,1,0)) n_med, MIN(IFF(is_med, rts, NULL)) med_first,
         MAX(rts) last_any, SUM(IFF(rts IS NULL,1,0)) n_null
  FROM co GROUP BY 1
),
co1b AS (
  SELECT *, CASE WHEN n_null = 0 THEN last_any ELSE NULL END AS base_ts
  FROM co1
),
co2 AS (
  SELECT a.oid, a.n_co, a.n_med, a.base_ts, a.base_ts::date AS base_dt,
         SUM(IFF(NOT c.is_med, 1, 0)) AS n_other,
         SUM(IFF(NOT c.is_med AND c.rts IS NOT NULL AND c.rts <= a.base_ts, 1, 0)) AS n_other_ok
  FROM co1b a JOIN co c ON c.oid = a.oid GROUP BY 1,2,3,4,5
),
bo_all AS (
  SELECT bo.sfdc_benefit_order_id, bo.benefit_order_name, bo.benefit_order_owner,
         COALESCE(bo.owner_pe_name_current, bo.owner_pe_name) AS pe,
         bo.zp_company_id, bo.hi_id AS fulfillment_id, bo.record_type_name,
         a.base_dt AS first_rfsp_dt,
         CONVERT_TIMEZONE('America/Los_Angeles','UTC', a.base_ts::TIMESTAMP_NTZ) AS first_rfsp_ts,
         IFF(a.n_med = 0 OR a.n_other_ok = a.n_other, 1, 0) AS clause_ok
  FROM bi_reporting.benefit_orders bo
  JOIN co2 a ON a.oid = bo.sfdc_benefit_order_id
  JOIN rfsp_from_status rfsp ON rfsp.sfdc_benefit_order_id = bo.sfdc_benefit_order_id AND rfsp.rfsp_flag = 1
  WHERE bo.cancel_flag = FALSE
    AND DATE_TRUNC('month', bo.coverage_effective_dt) BETWEEN DATE '2025-01-01' AND DATE '2027-01-01'
    AND a.base_dt BETWEEN DATE '2026-01-01' AND CONVERT_TIMEZONE('America/Los_Angeles', CURRENT_TIMESTAMP())::date
),
bo_companies AS (SELECT * FROM bo_all WHERE clause_ok = 1),
-- ===== Agentic Operator (AO) point-in-time classification =====
enab AS (
  SELECT APPLICATION_UUID, ENABLED, CREATED_AT AS ao_created, UPDATED_AT AS ao_updated
  FROM (SELECT APPLICATION_UUID, ENABLED, CREATED_AT, UPDATED_AT,
               ROW_NUMBER() OVER (PARTITION BY APPLICATION_UUID ORDER BY UPDATED_AT DESC, ID DESC) rn
        FROM hawaiian_ice_production_no_pii.fulfillment_agentic_operator_pilot_enablements) WHERE rn = 1
),
ao_apps AS (
  SELECT DISTINCT e.APPLICATION_UUID, e.ENABLED, e.ao_created, e.ao_updated,
         REGEXP_SUBSTR(r.APPLICATION_GLOBAL_ID,'[0-9]+$') AS renewal_id, hc.GUSTO_ID AS gusto_id
  FROM enab e
  JOIN hawaiian_ice_production_no_pii.fulfillment_requirements r ON r.APPLICATION_UUID = e.APPLICATION_UUID
  JOIN hawaiian_ice_production_no_pii.companies hc ON hc.UUID = r.COMPANY_UUID
),
bo_appid AS (
  SELECT bo.ID AS sfdc_order_id, bo.APPLICATION_ID__C AS renewal_id, bo.ZP_COMPANY_ID__C AS zp_company_id
  FROM salesforce_production_no_pii.benefit_order__c bo
  WHERE bo.ID IN (SELECT sfdc_benefit_order_id FROM bo_companies)
),
ao AS (
  SELECT c.sfdc_benefit_order_id AS order_id,
         aa.ENABLED AS ao_enabled_now,
         CASE
           WHEN aa.APPLICATION_UUID IS NULL THEN 0
           WHEN c.first_rfsp_ts >= aa.ao_created
                AND (aa.ENABLED = TRUE OR c.first_rfsp_ts < aa.ao_updated) THEN 1
           ELSE 0
         END AS ao_handled
  FROM bo_companies c
  LEFT JOIN bo_appid ba ON ba.sfdc_order_id = c.sfdc_benefit_order_id
  LEFT JOIN ao_apps aa ON aa.renewal_id = ba.renewal_id AND aa.gusto_id::VARCHAR = c.zp_company_id::VARCHAR
),
-- ORIGINAL task universe --
o_custom AS (
  SELECT tf.company_gusto_id, RIGHT(tf.source_id, CHARINDEX('/', REVERSE(tf.source_id))-1) AS fulfillment_id,
         ct.title AS task_title, ct.status AS task_status, ct.updated_at
  FROM hawaiian_ice_production_no_pii.fulfillment_task_custom_tasks ct
  JOIN hawaiian_ice_production_no_pii.fulfillment_task_flows tf ON ct.task_flow_id = tf.id
),
o_survey AS (
  SELECT company_gusto_id, RIGHT(source_id, CHARINDEX('/', REVERSE(source_id))-1) AS fulfillment_id,
         display_name AS task_title, status AS task_status, updated_at
  FROM hawaiian_ice_production_no_pii.fulfillment_task_surveys
),
o_all AS (SELECT * FROM o_survey UNION ALL SELECT * FROM o_custom),
o_mt AS (
  SELECT bo.sfdc_benefit_order_id AS order_id, bo.benefit_order_owner AS ic_name, bo.pe,
         bo.benefit_order_name, bo.record_type_name, a.task_title, a.task_status,
         RANK() OVER (PARTITION BY a.fulfillment_id, TRIM(a.task_title), a.company_gusto_id
                      ORDER BY a.task_status ASC, a.updated_at DESC) AS rk
  FROM o_all a
  JOIN bo_companies bo ON a.fulfillment_id = bo.fulfillment_id
                      AND bo.zp_company_id::BIGINT = a.company_gusto_id::BIGINT
  QUALIFY rk = 1
),
-- ADJUSTED task universe (changes 1-3) --
a_custom AS (
  SELECT tf.company_gusto_id, RIGHT(tf.source_id, CHARINDEX('/', REVERSE(tf.source_id))-1) AS fulfillment_id,
         ct.title AS task_title, ct.status AS task_status, ct.updated_at
  FROM hawaiian_ice_production_no_pii.fulfillment_task_custom_tasks ct
  JOIN hawaiian_ice_production_no_pii.fulfillment_task_flows tf ON ct.task_flow_id = tf.id
  WHERE tf.discarded_at IS NULL
),
a_survey AS (
  SELECT s.company_gusto_id, RIGHT(s.source_id, CHARINDEX('/', REVERSE(s.source_id))-1) AS fulfillment_id,
         s.display_name AS task_title, s.status AS task_status, s.updated_at
  FROM hawaiian_ice_production_no_pii.fulfillment_task_surveys s
  JOIN hawaiian_ice_production_no_pii.fulfillment_task_flows tf ON s.task_flow_id = tf.id
  WHERE tf.discarded_at IS NULL
),
a_all AS (SELECT * FROM a_survey UNION ALL SELECT * FROM a_custom),
a_mt AS (
  SELECT bo.sfdc_benefit_order_id AS order_id, a.task_title, a.task_status,
         RANK() OVER (PARTITION BY a.fulfillment_id, TRIM(a.task_title), a.company_gusto_id
                      ORDER BY a.task_status ASC, a.updated_at DESC) AS rk
  FROM a_all a
  JOIN bo_companies bo ON a.fulfillment_id = bo.fulfillment_id
                      AND bo.zp_company_id::BIGINT = a.company_gusto_id::BIGINT
  WHERE NOT (LOWER(a.task_title) LIKE '%set open enrollment window%'
             AND LOWER(a.task_title) LIKE '%intro email%')
  QUALIFY rk = 1
),
o_counts AS (SELECT order_id, COUNT(*) total_o, SUM(CASE WHEN task_status='completed' THEN 1 ELSE 0 END) done_o FROM o_mt GROUP BY 1),
a_counts AS (SELECT order_id, COUNT(*) total_a, SUM(CASE WHEN task_status='completed' THEN 1 ELSE 0 END) done_a FROM a_mt GROUP BY 1),
-- ===== per-order classification (non-AO denominator; adherent = all-complete-adj + all-excluded) =====
ord AS (
  SELECT c.benefit_order_owner AS ic_name,
         TO_CHAR(DATE_TRUNC('month', c.first_rfsp_dt),'YYYY-MM') AS month,
         COALESCE(ao.ao_handled,0) AS ao_handled,
         IFF(oc.order_id IS NOT NULL,1,0) AS has_orig,
         IFF(ac.order_id IS NOT NULL AND ac.done_a=ac.total_a,1,0) AS all_complete_adj,
         IFF(oc.order_id IS NOT NULL AND ac.order_id IS NULL,1,0) AS all_excluded_adherent
  FROM bo_companies c
  LEFT JOIN o_counts oc ON oc.order_id=c.sfdc_benefit_order_id
  LEFT JOIN a_counts ac ON ac.order_id=c.sfdc_benefit_order_id
  LEFT JOIN ao        ON ao.order_id=c.sfdc_benefit_order_id
)
SELECT ic_name AS IC,
       month   AS MONTH,
       COUNT_IF(ao_handled=0 AND has_orig=1) AS MA_ELIGIBLE,
       COUNT_IF(ao_handled=0 AND (all_complete_adj=1 OR all_excluded_adherent=1)) AS MA_ADHERENT,
       COUNT_IF(ao_handled=0 AND has_orig=1 AND all_complete_adj=0 AND all_excluded_adherent=0) AS MA_REAL_MISS,
       COUNT_IF(ao_handled=1) AS MA_AO
FROM ord
WHERE ic_name IS NOT NULL
GROUP BY 1,2
ORDER BY 1,2
