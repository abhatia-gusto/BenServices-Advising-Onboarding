-- Maestro Adherence diagnostic (non-scored), per-IC per-MONTH.
-- Cohort = BOs whose FIRST RFSP entry (MIN start_time where from_status='ready for submission prep',
--   full history, NO floor — exact first entry) falls in the window. Bucketed by that RFSP month.
-- Eligible (denominator) = those BOs that are Maestro-eligible = have >=1 Maestro task record
--   (hawaiian_ice task tables). BOs with no task records are excluded (not a miss).
-- Adherent (numerator) = eligible BOs where ALL Maestro tasks are completed.
-- Attribution = sfdc_benefit_order_owner_id -> current employee name via the same bridge as q_bo_v2.
-- Scope: New Plan + Renewal (Change has no Maestro), cancel_flag=FALSE. Window = app-wide dates.
WITH IC_EE_ID AS (
  SELECT v1.SFDC_USER_ID, COALESCE(v2.NAME, v1.NAME) AS NAME
  FROM BI.SFDC_USERS_GUSTO_EMPLOYEES_VIEW v1
  LEFT JOIN BI.GUSTO_EMPLOYEES v2 ON v2.SFDC_EE_ID=v1.SFDC_EE_ID AND v2.CURRENT_FLAG=TRUE
  WHERE v1.SFDC_EE_ID <> 111883
  QUALIFY ROW_NUMBER() OVER (PARTITION BY v1.SFDC_USER_ID ORDER BY CASE WHEN v2.NAME IS NOT NULL THEN 0 ELSE 1 END, v1.SFDC_EE_ID)=1
),
rfsp AS (
  SELECT SFDC_OBJECT_ID AS boid,
    MIN(CASE WHEN TRIM(LOWER(FROM_STATUS))='ready for submission prep' THEN START_TIME::date END) AS first_rfsp_dt
  FROM BI.BENEFIT_ORDER_STATUS_CHANGE_HISTORY
  WHERE RECORD_TYPE IN ('New Plan','Renewal')
  GROUP BY 1
),
bo AS (
  SELECT b.SFDC_BENEFIT_ORDER_ID AS boid, b.SFDC_BENEFIT_ORDER_OWNER_ID AS owner_id,
    b.HI_ID AS fulfillment_id, b.ZP_COMPANY_ID AS company_id, r.first_rfsp_dt
  FROM BI_REPORTING.BENEFIT_ORDERS b
  JOIN rfsp r ON r.boid=b.SFDC_BENEFIT_ORDER_ID
  WHERE b.CANCEL_FLAG=FALSE AND b.RECORD_TYPE_NAME IN ('New Plan','Renewal')
    AND r.first_rfsp_dt BETWEEN '2026-01-01' AND CURRENT_DATE()
),
ct AS (
  SELECT tf.company_gusto_id,
    RIGHT(tf.source_id, CHARINDEX('/', REVERSE(tf.source_id))-1) AS fulfillment_id,
    ctk.title AS task_title, ctk.status AS task_status, ctk.updated_at
  FROM hawaiian_ice_production_no_pii.fulfillment_task_custom_tasks ctk
  JOIN hawaiian_ice_production_no_pii.fulfillment_task_flows tf ON ctk.task_flow_id=tf.id
),
sv AS (
  SELECT company_gusto_id,
    RIGHT(source_id, CHARINDEX('/', REVERSE(source_id))-1) AS fulfillment_id,
    display_name AS task_title, status AS task_status, updated_at
  FROM hawaiian_ice_production_no_pii.fulfillment_task_surveys
),
allt AS (SELECT * FROM sv UNION ALL SELECT * FROM ct),
mt AS (
  SELECT bo.boid, at.task_status,
    RANK() OVER (PARTITION BY at.fulfillment_id, TRIM(at.task_title), at.company_gusto_id
                 ORDER BY at.task_status ASC, at.updated_at DESC) AS rk
  FROM allt at
  JOIN bo ON at.fulfillment_id = bo.fulfillment_id
        AND bo.company_id::BIGINT = at.company_gusto_id::BIGINT
  QUALIFY rk=1
),
base AS (
  SELECT boid, COUNT(*) AS total_tasks,
    SUM(IFF(task_status='completed',1,0)) AS completed,
    IFF(COUNT(*)=SUM(IFF(task_status='completed',1,0)),1,0) AS all_complete
  FROM mt GROUP BY boid
)
SELECT ee.NAME AS IC,
  TO_CHAR(DATE_TRUNC('month', bo.first_rfsp_dt),'YYYY-MM') AS MONTH,
  COUNT(*)               AS MA_ELIGIBLE,
  SUM(base.all_complete) AS MA_ADHERENT
FROM bo
JOIN base ON base.boid = bo.boid
JOIN IC_EE_ID ee ON bo.owner_id = ee.SFDC_USER_ID
GROUP BY 1,2
ORDER BY 1,2
