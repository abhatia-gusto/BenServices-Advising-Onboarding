-- Ticket SLA — v12 attribution (per Aman 2026-06-16). Ful-reporting tickets that TOUCHED an OA,
-- attributed to the BENEFIT-ORDER OWNER (always populated -> no longest-held lag), SLA = 5 days.
-- OA-touch (HAS_OA_TOUCH) = (a) sub_team='Implementation Advocate', OR
--   (b) sub_team='Fulfillment' AND oa_longest_held_owner_id populated, OR
--   (c) sub_team='Fulfillment' AND a name in list_of_owner_change was an OA at the ticket's close date (SCD2).
-- Output per IC (current BO-owner name via bridge) x close-month: N_TICKETS, CLOSED_5D (=within 5d), CLOSED_N.
WITH oa_role_periods AS (
  SELECT ge.sfdc_ee_id, ge.effect_start_dt, COALESCE(ge.effect_end_dt, CURRENT_DATE) AS effect_end_dt
  FROM bi.gusto_employees ge
  WHERE ge.job_title ILIKE '%Onboarding Advoc%' OR ge.job_title ILIKE '%Benefits Onboarding%'
     OR ge.sub_team IN ('Onboarding Advocacy','New Plan & Renewal Onboarding')
),
ic_ee_id AS (
  SELECT v1.sfdc_user_id, v1.sfdc_ee_id, COALESCE(v2.name,v1.name) AS name
  FROM bi.sfdc_users_gusto_employees_view v1
  LEFT JOIN bi.gusto_employees v2 ON v2.sfdc_ee_id=v1.sfdc_ee_id AND v2.current_flag=TRUE
  WHERE v1.sfdc_ee_id <> 111883
  QUALIFY ROW_NUMBER() OVER (PARTITION BY v1.sfdc_user_id ORDER BY CASE WHEN v2.name IS NOT NULL THEN 0 ELSE 1 END, v1.sfdc_ee_id)=1
),
oa_name_to_ee AS (
  SELECT ic.name, ic.sfdc_ee_id FROM ic_ee_id ic
  WHERE EXISTS (SELECT 1 FROM oa_role_periods op WHERE op.sfdc_ee_id=ic.sfdc_ee_id)
  QUALIFY ROW_NUMBER() OVER (PARTITION BY ic.name ORDER BY ic.sfdc_ee_id)=1
),
target_tickets AS (
  SELECT t.sfdc_ticket_id, t.time_to_close_min,
    CONVERT_TIMEZONE('UTC','America/Denver', t.closed_ts)::date AS closed_dt_mt,
    t.sub_team, t.reporting_team, t.oa_longest_held_owner_id, t.list_of_owner_change,
    bo.sfdc_benefit_order_owner_id AS bo_owner_id
  FROM bi.sfdc_tickets t
  JOIN bi_reporting.benefit_orders bo ON t.sfdc_benefit_order_id = bo.sfdc_benefit_order_id
  WHERE t.reporting_team = 'Fulfillment'
    AND (t.false_positive = FALSE OR t.false_positive IS NULL)
    AND CONVERT_TIMEZONE('UTC','America/Denver', t.closed_ts)::date BETWEEN '2026-01-01' AND CURRENT_DATE()
  QUALIFY ROW_NUMBER() OVER (PARTITION BY t.sfdc_ticket_id ORDER BY 1)=1
),
chain_flat AS (
  SELECT t.sfdc_ticket_id, t.closed_dt_mt, TRIM(f.value::string) AS owner_name
  FROM target_tickets t, LATERAL FLATTEN(input => SPLIT(t.list_of_owner_change, ',')) f
  WHERE t.list_of_owner_change IS NOT NULL AND t.sub_team='Fulfillment' AND t.oa_longest_held_owner_id IS NULL
),
chain_oa_check AS (
  SELECT DISTINCT cf.sfdc_ticket_id
  FROM chain_flat cf
  JOIN oa_name_to_ee ne ON ne.name = cf.owner_name
  JOIN oa_role_periods op ON op.sfdc_ee_id = ne.sfdc_ee_id
   AND cf.closed_dt_mt BETWEEN op.effect_start_dt AND op.effect_end_dt
),
oa_touch AS (
  SELECT t.*,
    CASE
      WHEN t.sub_team='Implementation Advocate' THEN 1
      WHEN t.sub_team='Fulfillment' AND t.oa_longest_held_owner_id IS NOT NULL THEN 1
      WHEN t.sub_team='Fulfillment' AND coc.sfdc_ticket_id IS NOT NULL THEN 1
      ELSE 0
    END AS has_oa_touch
  FROM target_tickets t
  LEFT JOIN chain_oa_check coc ON coc.sfdc_ticket_id = t.sfdc_ticket_id
)
SELECT ee.name AS IC,
  TO_CHAR(DATE_TRUNC('month', ot.closed_dt_mt),'YYYY-MM') AS MONTH,
  COUNT(*) AS N_TICKETS,
  SUM(IFF(ot.time_to_close_min <= 5*1440, 1, 0)) AS CLOSED_5D,
  COUNT(*) AS CLOSED_N
FROM oa_touch ot
JOIN ic_ee_id ee ON ot.bo_owner_id = ee.sfdc_user_id
WHERE ot.has_oa_touch = 1
GROUP BY 1,2
ORDER BY 1,2
