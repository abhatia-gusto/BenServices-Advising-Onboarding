WITH
-- Distinct employees with at least one OA-titled row (anywhere in their history).
-- We carry effect_start_dt/effect_end_dt so we can do point-in-time membership check.
oa_role_periods AS (
  SELECT
    ge.sfdc_ee_id,
    ge.effect_start_dt,
    COALESCE(ge.effect_end_dt, CURRENT_DATE) AS effect_end_dt
  FROM bi.gusto_employees ge
  WHERE ge.job_title ILIKE '%Onboarding Advoc%'
     OR ge.job_title ILIKE '%Benefits Onboarding%'
     OR ge.sub_team IN ('Onboarding Advocacy','New Plan & Renewal Onboarding')
),

-- Map historical SFDC user IDs -> employee + name. (kept v3 logic)
ic_ee_id AS (
  SELECT
    v1.sfdc_user_id,
    v1.sfdc_ee_id,
    COALESCE(v2.name, v1.name) AS name
  FROM bi.sfdc_users_gusto_employees_view v1
  LEFT JOIN bi.gusto_employees v2
    ON v2.sfdc_ee_id = v1.sfdc_ee_id AND v2.current_flag = TRUE
  WHERE v1.sfdc_ee_id <> 111883
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY v1.sfdc_user_id
    ORDER BY CASE WHEN v2.name IS NOT NULL THEN 0 ELSE 1 END, v1.sfdc_ee_id
  ) = 1
),

-- Distinct names that point to ever-OA employees. We dedupe by name to avoid
-- fan-out on chain joins (rare two-OAs-with-same-name case picks lower sfdc_ee_id).
oa_name_to_ee AS (
  SELECT
    ic.name,
    ic.sfdc_ee_id
  FROM ic_ee_id ic
  WHERE EXISTS (SELECT 1 FROM oa_role_periods op WHERE op.sfdc_ee_id = ic.sfdc_ee_id)
  QUALIFY ROW_NUMBER() OVER (PARTITION BY ic.name ORDER BY ic.sfdc_ee_id) = 1
),

-- Pre-filter target tickets (Ful + Impl Adv reporting only, matches v11 cohort).
target_tickets AS (
  SELECT
    t.sfdc_ticket_id,
    t.ticket_name,
    t.created_ts,
    t.closed_ts,
    -- For closed: closed date in MT. For open: still closed_ts::date = NULL, we compute AGE_DAYS_OPEN separately.
    CONVERT_TIMEZONE('UTC','America/Denver', t.closed_ts)::date AS closed_dt_mt,
    t.status,
    t.team,
    t.sub_team,
    t.reporting_team,
    t.escalation_reason,
    t.escalation_reason_detail,
    t.sfdc_owner_id,
    t.owner_full_name,
    t.owner_current_pe_name,
    t.oa_longest_held_owner_id,
    t.list_of_owner_change,
    t.er_outreach_count,
    t.sfdc_benefit_order_id,
    t.sfdc_opportunity_id,
    -- Flag + age
    CASE WHEN t.closed_ts IS NULL AND t.status <> 'Closed' THEN TRUE ELSE FALSE END AS is_open,
    CASE WHEN t.closed_ts IS NULL AND t.status <> 'Closed'
         THEN DATEDIFF('day', t.created_ts, CURRENT_DATE) ELSE NULL END AS age_days_open
  FROM bi.sfdc_tickets t
  JOIN bi_reporting.benefit_orders bo_chk
    ON t.sfdc_benefit_order_id = bo_chk.sfdc_benefit_order_id
  WHERE (
    -- Closed cohort — same window as before (broader reporting-team filter)
    (t.closed_ts IS NOT NULL
     AND t.status = 'Closed'
     AND t.reporting_team IN ('Fulfillment','Implementation Advocate')
     AND CONVERT_TIMEZONE('UTC','America/Denver', t.closed_ts)::date
         BETWEEN '{{Date Range Start}}' AND '{{Date Range End}}')
    OR
    -- Open backlog — the 4 tracked flows, created since 2024.
    -- OA→NPS / OA→Advising are scoped by TEAM regardless of reporting_team:
    -- reporting_team is stamped late (at/after close) on Advising tickets, so
    -- requiring reporting_team='Implementation Advocate' would miss ~625 open
    -- Advising tickets that currently carry a blank reporting_team (per Aman
    -- 2026-07-04 assessment). NPS reporting_team is reliable, so this only
    -- materially changes Advising. Fulfillment flows keep reporting_team scoping
    -- (that field IS populated while open on the Fulfillment side).
    (t.closed_ts IS NULL
     AND t.status <> 'Closed'
     AND t.created_ts >= '2024-01-01'
     AND (
       (t.reporting_team = 'Fulfillment' AND t.sub_team IN ('Implementation Advocate','Fulfillment'))
       OR (t.team IN ('New Plan Sales','Benefits Advising'))
     ))
  )
),

-- For Ful → Ful tickets with no stored OA Longest, parse list_of_owner_change
-- and check if any name in the chain was an OA on the ticket's close date (SCD2).
chain_flat AS (
  SELECT
    t.sfdc_ticket_id,
    t.closed_dt_mt,
    TRIM(f.value::string) AS owner_name
  FROM target_tickets t,
       LATERAL FLATTEN(input => SPLIT(t.list_of_owner_change, ',')) f
  WHERE t.list_of_owner_change IS NOT NULL
    AND t.reporting_team = 'Fulfillment'
    AND t.sub_team = 'Fulfillment'
    AND t.oa_longest_held_owner_id IS NULL
),
chain_oa_check AS (
  SELECT DISTINCT cf.sfdc_ticket_id
  FROM chain_flat cf
  JOIN oa_name_to_ee ne ON ne.name = cf.owner_name
  JOIN oa_role_periods op
    ON op.sfdc_ee_id = ne.sfdc_ee_id
   AND cf.closed_dt_mt BETWEEN op.effect_start_dt AND op.effect_end_dt
)

SELECT
  t.ticket_name                                              AS "TICKET_NAME",
  'https://gusto.lightning.force.com/lightning/r/Ticket__c/' || t.sfdc_ticket_id || '/view' AS "TICKET_LINK_LIGHTNING",
  TO_VARCHAR(CONVERT_TIMEZONE('UTC','America/Denver', t.created_ts), 'YYYY-MM-DD"T"HH24:MI:SS') AS "TICKET_CREATED_TS_MT",
  TO_VARCHAR(CONVERT_TIMEZONE('UTC','America/Denver', t.closed_ts),  'YYYY-MM-DD"T"HH24:MI:SS') AS "TICKET_CLOSED_TS_MT",
  bo.record_type_name                                        AS "BENEFIT_ORDER_RECORD_TYPE_NAME",
  t.status                                                   AS "TICKET_STATUS",
  t.team                                                     AS "TICKET_TEAM",
  t.sub_team                                                 AS "TICKET_SUBTEAM",
  t.reporting_team                                           AS "TICKET_REPORTING_TEAM",
  t.escalation_reason                                        AS "TICKET_REASON",
  t.escalation_reason_detail                                 AS "TICKET_REASON_DETAIL",
  -- Ticket Owner: canonical HR name (COALESCE with raw for system accounts)
  COALESCE(ee_tix.name, t.owner_full_name)                   AS "TICKET_OWNER_NAME",
  t.owner_current_pe_name                                    AS "TICKET_OWNER_PE",
  -- Legacy column: stored OA Longest name (or NULL).
  ee_stored.name                                             AS "OA_LONGEST_OWNER_NAME",
  -- BO Owner: canonical HR name via ic_ee_id (fixes OOO junk + duplicate rows)
  COALESCE(ee_bo.name, bo.benefit_order_owner)               AS "BENEFIT_ORDER_OWNER",
  bo.owner_pe_name_current                                   AS "BENEFIT_ORDER_OWNER_PE",
  oppt.owner_name                                            AS "OPPT_OWNER_NAME",
  -- HAS_OA_TOUCH: TRUE per Aman's 3-condition rule for Ful-reporting tickets
  CASE
    WHEN t.reporting_team = 'Fulfillment' AND t.sub_team = 'Implementation Advocate' THEN TRUE
    WHEN t.reporting_team = 'Fulfillment' AND t.sub_team = 'Fulfillment'
         AND t.oa_longest_held_owner_id IS NOT NULL THEN TRUE
    WHEN t.reporting_team = 'Fulfillment' AND t.sub_team = 'Fulfillment'
         AND coc.sfdc_ticket_id IS NOT NULL THEN TRUE
    ELSE FALSE
  END                                                        AS "HAS_OA_TOUCH",
  -- Attribution source label (for transparency in modal)
  CASE
    WHEN t.reporting_team = 'Fulfillment' AND t.sub_team = 'Implementation Advocate' THEN 'closed_by_oa'
    WHEN t.reporting_team = 'Fulfillment' AND t.sub_team = 'Fulfillment'
         AND t.oa_longest_held_owner_id IS NOT NULL THEN 'stored_oa_longest'
    WHEN t.reporting_team = 'Fulfillment' AND t.sub_team = 'Fulfillment'
         AND coc.sfdc_ticket_id IS NOT NULL THEN 'chain_oa_scd2'
    WHEN t.reporting_team = 'Fulfillment' AND t.sub_team = 'Fulfillment' THEN 'no_oa_touch'
    ELSE 'other_flow'
  END                                                        AS "ATTRIBUTION_SOURCE",
  -- OA bucket (composition tag): IA = Implementation Advocate sub_team;
  -- ER = ER-outreach ticket not owned by an IA; Other = neither. Used by the
  -- Ful → OA bucket filter + ticket-detail Tag column. Additive; unused by other flows.
  CASE
    WHEN t.sub_team = 'Implementation Advocate' THEN 'IA'
    WHEN NVL(t.er_outreach_count, 0) > 0 THEN 'ER'
    ELSE 'Other'
  END                                                        AS "OA_BUCKET",
  t.is_open                                                  AS "IS_OPEN",
  t.age_days_open                                            AS "AGE_DAYS_OPEN"
FROM target_tickets t
JOIN bi_reporting.benefit_orders bo
  ON t.sfdc_benefit_order_id = bo.sfdc_benefit_order_id
LEFT JOIN bi_reporting.advising_opportunities oppt
  ON oppt.sfdc_object_id = t.sfdc_opportunity_id
LEFT JOIN ic_ee_id ee_stored
  ON ee_stored.sfdc_user_id = t.oa_longest_held_owner_id
LEFT JOIN ic_ee_id ee_tix
  ON ee_tix.sfdc_user_id = t.sfdc_owner_id
LEFT JOIN ic_ee_id ee_bo
  ON ee_bo.sfdc_user_id = bo.sfdc_benefit_order_owner_id
LEFT JOIN chain_oa_check coc
  ON coc.sfdc_ticket_id = t.sfdc_ticket_id
QUALIFY ROW_NUMBER() OVER (PARTITION BY t.sfdc_ticket_id ORDER BY 1) = 1
