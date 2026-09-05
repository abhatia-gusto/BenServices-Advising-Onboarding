-- ════════════════════════════════════════════════════════════════════════════
-- Advising SLA Detail — v6.0 (One Row Per Opportunity, Open + Closed)
-- ════════════════════════════════════════════════════════════════════════════
--
-- CHANGES vs v5.3:
--   • Includes OPEN opps (non-terminal statuses) with create_date >= date_start,
--     so the dashboard can render an Open Backlog tab.
--   • Adds 'Closed Admin' as a 5th closed status (was previously excluded).
--   • Fixes the 9999-12-31 sentinel end-date via LEAST(effect_end_dt, NOW())
--     so open-opp cycle-time totals reflect actual time-so-far, not 7000 years.
--   • New columns:  is_open, age_days, days_in_current_status, overdue_days,
--                   create_date_month, refresh_date
--   • RDP_SLO_TARGET and ALT_SLO_TARGET set to 5 (v5.3 change carried forward).
--   • Closed opps' cycle-time / SLO-met / DIFOT / TTC behavior unchanged.
--
-- ════════════════════════════════════════════════════════════════════════════
--
-- PARAMETERS (Redash)
-- -------------------
--   {{date_start}}   DATE   Start of window (used by BOTH close_date_computed
--                            filter for closed opps AND create_date filter for
--                            open opps).
--   {{date_end}}     DATE   End of close_date_computed range for closed opps
--                            (open opps don't have a close_date).
--
-- ════════════════════════════════════════════════════════════════════════════
-- STATUS CLASSIFICATION
-- ════════════════════════════════════════════════════════════════════════════
--
--   is_open = FALSE (Closed, 5 buckets)
--     Closed Won              — first entry into 'Closed Won'
--     Closed Lost             — first entry into 'Closed Lost'
--     Order Lost              — first CW entry (won-then-lost) or first OL
--     Pending Fulfillment     — first entry into 'Pending Fulfillment'
--     Closed Admin            — first entry into 'Closed Admin'
--
--   is_open = TRUE (Open, all other statuses)
--     SAL, Engaged, ER Confirm, Alignment In Progress, Ready for Default
--     Package, Alternates Requested, Open, Recommendation Sent, In Escalation,
--     Alignment Complete, Attempting Contact
--
-- ════════════════════════════════════════════════════════════════════════════
-- KEY DERIVED COLUMNS
-- ════════════════════════════════════════════════════════════════════════════
--   age_days                = DATEDIFF(day, create_date, COALESCE(close_date_computed, refresh_date))
--                             — for open: today − created; for closed: closed − created
--   days_in_current_status  = DATEDIFF(day, latest_hist_stage_entry, refresh_date)
--                             — open only; NULL for closed
--   overdue_days            = DATEDIFF(day, sla_date, refresh_date)
--                             — positive means past SLA; negative means N days remaining
--   refresh_date            = CURRENT_DATE() at query time (locked into every row so
--                             the browser doesn't need TODAY to compute age)
--
-- ════════════════════════════════════════════════════════════════════════════

WITH advising_base AS (
  SELECT
      sfdc_object_id,
      status AS current_status,
      ignore_flag,
      create_date,
      CASE
        WHEN status IN ('Closed Won','Closed Lost','Order Lost',
                        'Pending Fulfillment','Closed Admin') THEN FALSE
        ELSE TRUE
      END AS is_open
  FROM bi_reporting.advising_opportunities
  WHERE ignore_flag = FALSE
    AND (
      status IN ('Closed Won','Closed Lost','Order Lost',
                 'Pending Fulfillment','Closed Admin')
      OR (
        status NOT IN ('Closed Won','Closed Lost','Order Lost',
                       'Pending Fulfillment','Closed Admin')
        AND create_date >= '{{date_start}}'::timestamp
      )
    )
),
hist_first_closed_won AS (
  SELECT oh.opportunity_id, oh.effect_start_dt AS first_closed_won_dt
  FROM bi.sfdc_opportunity_history oh
  INNER JOIN advising_base a ON oh.opportunity_id = a.sfdc_object_id
  WHERE oh.stagename = 'Closed Won'
  QUALIFY ROW_NUMBER() OVER (
      PARTITION BY oh.opportunity_id ORDER BY oh.effect_start_dt ASC) = 1
),
hist_first_closed_lost AS (
  SELECT oh.opportunity_id, oh.effect_start_dt AS first_closed_lost_dt
  FROM bi.sfdc_opportunity_history oh
  INNER JOIN advising_base a ON oh.opportunity_id = a.sfdc_object_id
  WHERE oh.stagename = 'Closed Lost'
  QUALIFY ROW_NUMBER() OVER (
      PARTITION BY oh.opportunity_id ORDER BY oh.effect_start_dt ASC) = 1
),
hist_first_order_lost AS (
  SELECT oh.opportunity_id, oh.effect_start_dt AS first_order_lost_dt
  FROM bi.sfdc_opportunity_history oh
  INNER JOIN advising_base a ON oh.opportunity_id = a.sfdc_object_id
  WHERE oh.stagename = 'Order Lost'
  QUALIFY ROW_NUMBER() OVER (
      PARTITION BY oh.opportunity_id ORDER BY oh.effect_start_dt ASC) = 1
),
hist_first_pending_fulfillment AS (
  SELECT oh.opportunity_id, oh.effect_start_dt AS first_pending_fulfillment_dt
  FROM bi.sfdc_opportunity_history oh
  INNER JOIN advising_base a ON oh.opportunity_id = a.sfdc_object_id
  WHERE oh.stagename = 'Pending Fulfillment'
  QUALIFY ROW_NUMBER() OVER (
      PARTITION BY oh.opportunity_id ORDER BY oh.effect_start_dt ASC) = 1
),
hist_first_closed_admin AS (
  SELECT oh.opportunity_id, oh.effect_start_dt AS first_closed_admin_dt
  FROM bi.sfdc_opportunity_history oh
  INNER JOIN advising_base a ON oh.opportunity_id = a.sfdc_object_id
  WHERE oh.stagename = 'Closed Admin'
  QUALIFY ROW_NUMBER() OVER (
      PARTITION BY oh.opportunity_id ORDER BY oh.effect_start_dt ASC) = 1
),
-- Latest stage row for OPEN opps (the one with effect_end_dt = 9999-12-31).
-- Gives us "when did the current status start" for time-in-current-status.
hist_current_open_stage AS (
  SELECT oh.opportunity_id,
         oh.stagename            AS current_stage_hist,
         oh.effect_start_dt      AS current_stage_started_ts
  FROM bi.sfdc_opportunity_history oh
  INNER JOIN advising_base a ON oh.opportunity_id = a.sfdc_object_id
  WHERE a.is_open = TRUE
    AND oh.effect_end_dt >= '9999-12-31'::timestamp
  QUALIFY ROW_NUMBER() OVER (
      PARTITION BY oh.opportunity_id ORDER BY oh.effect_start_dt DESC) = 1
),
opp_with_close_date AS (
  SELECT
      a.sfdc_object_id,
      a.current_status,
      a.is_open,
      a.create_date,
      CASE
        WHEN a.current_status = 'Closed Won'          THEN 'Closed Won'
        WHEN a.current_status = 'Closed Lost'         THEN 'Closed Lost'
        WHEN a.current_status = 'Order Lost'
             AND cw.first_closed_won_dt IS NOT NULL   THEN 'Closed Won'
        WHEN a.current_status = 'Order Lost'          THEN 'Order Lost'
        WHEN a.current_status = 'Pending Fulfillment' THEN 'Pending Fulfillment'
        WHEN a.current_status = 'Closed Admin'        THEN 'Closed Admin'
        WHEN a.is_open                                THEN 'Open'
      END AS close_stage_source,
      CASE
        WHEN a.current_status = 'Closed Won'          THEN cw.first_closed_won_dt
        WHEN a.current_status = 'Closed Lost'         THEN cl.first_closed_lost_dt
        WHEN a.current_status = 'Order Lost'
          THEN COALESCE(cw.first_closed_won_dt, ol.first_order_lost_dt)
        WHEN a.current_status = 'Pending Fulfillment' THEN pf.first_pending_fulfillment_dt
        WHEN a.current_status = 'Closed Admin'        THEN ca.first_closed_admin_dt
        -- Open opps: NULL close_date_computed
      END AS close_date_computed,
      CASE
        WHEN a.current_status = 'Order Lost'
             AND cw.first_closed_won_dt IS NULL THEN TRUE
        ELSE FALSE
      END AS order_lost_no_prior_closed_won
  FROM advising_base a
  LEFT JOIN hist_first_closed_won           cw ON a.sfdc_object_id = cw.opportunity_id
  LEFT JOIN hist_first_closed_lost          cl ON a.sfdc_object_id = cl.opportunity_id
  LEFT JOIN hist_first_order_lost           ol ON a.sfdc_object_id = ol.opportunity_id
  LEFT JOIN hist_first_pending_fulfillment  pf ON a.sfdc_object_id = pf.opportunity_id
  LEFT JOIN hist_first_closed_admin         ca ON a.sfdc_object_id = ca.opportunity_id
),
in_window_opps AS (
  SELECT *,
      DATE_TRUNC('month', close_date_computed)::date
        AS close_date_computed_month,
      DATE_TRUNC('month', COALESCE(close_date_computed, create_date))::date
        AS close_or_create_month,
      DATE_TRUNC('month', create_date)::date
        AS create_date_month
  FROM opp_with_close_date
  WHERE
    (is_open = FALSE
      AND close_date_computed IS NOT NULL
      AND close_date_computed
          BETWEEN '{{date_start}}'::timestamp AND '{{date_end}}'::timestamp)
    OR
    (is_open = TRUE
      AND create_date >= '{{date_start}}'::timestamp)
),
-- Stage totals cap the current stint at NOW so open opps get real numbers.
rdp_totals AS (
  SELECT oh.opportunity_id,
      ROUND(SUM(
        DATEDIFF(minute, oh.effect_start_dt,
                 LEAST(oh.effect_end_dt, CURRENT_TIMESTAMP()))::FLOAT / 1440
      ), 3) AS total_days_in_rdp
  FROM bi.sfdc_opportunity_history oh
  INNER JOIN in_window_opps c ON oh.opportunity_id = c.sfdc_object_id
  WHERE oh.stagename = 'Ready for Default Package'
    AND DATEDIFF(minute, oh.effect_start_dt,
                 LEAST(oh.effect_end_dt, CURRENT_TIMESTAMP())) > 0
  GROUP BY oh.opportunity_id
),
er_totals AS (
  SELECT oh.opportunity_id,
      ROUND(SUM(
        DATEDIFF(minute, oh.effect_start_dt,
                 LEAST(oh.effect_end_dt, CURRENT_TIMESTAMP()))::FLOAT / 1440
      ), 3) AS total_days_in_er_confirm
  FROM bi.sfdc_opportunity_history oh
  INNER JOIN in_window_opps c ON oh.opportunity_id = c.sfdc_object_id
  WHERE oh.stagename = 'ER Confirm'
    AND DATEDIFF(minute, oh.effect_start_dt,
                 LEAST(oh.effect_end_dt, CURRENT_TIMESTAMP())) > 0
  GROUP BY oh.opportunity_id
),
alt_totals AS (
  SELECT oh.opportunity_id,
      ROUND(SUM(
        DATEDIFF(minute, oh.effect_start_dt,
                 LEAST(oh.effect_end_dt, CURRENT_TIMESTAMP()))::FLOAT / 1440
      ), 3) AS total_days_in_alt_requested
  FROM bi.sfdc_opportunity_history oh
  INNER JOIN in_window_opps c ON oh.opportunity_id = c.sfdc_object_id
  WHERE oh.stagename = 'Alternates Requested'
    AND DATEDIFF(minute, oh.effect_start_dt,
                 LEAST(oh.effect_end_dt, CURRENT_TIMESTAMP())) > 0
  GROUP BY oh.opportunity_id
),
opp_sla AS (
  SELECT
      c.sfdc_object_id,
      c.current_status,
      c.close_stage_source,
      c.close_date_computed,
      c.close_date_computed_month,
      c.close_or_create_month,
      c.create_date_month,
      c.order_lost_no_prior_closed_won,
      c.is_open,
      c.create_date,
      CURRENT_DATE() AS refresh_date,
      -- Age (open: today − created; closed: closed − created)
      DATEDIFF(day, c.create_date,
               COALESCE(c.close_date_computed, CURRENT_TIMESTAMP())) AS age_days,
      -- Time in current status: OPEN only; NULL for closed
      CASE WHEN c.is_open
           THEN DATEDIFF(day, curr.current_stage_started_ts, CURRENT_TIMESTAMP())
           ELSE NULL END AS days_in_current_status,
      -- Overdue relative to sla_date: positive = past, negative = remaining
      DATEDIFF(day, a.sla_date, CURRENT_DATE()) AS overdue_days,
      -- TTC (only meaningful for closed opps)
      CASE WHEN c.is_open THEN NULL
           ELSE DATEDIFF(day, a.create_date, c.close_date_computed) END
        AS time_to_close_computed,
      r.total_days_in_rdp,
      5 AS rdp_slo_target,
      CASE WHEN c.is_open THEN NULL
           WHEN r.total_days_in_rdp IS NULL THEN NULL
           WHEN r.total_days_in_rdp <= 5   THEN TRUE ELSE FALSE END AS rdp_slo_met,
      e.total_days_in_er_confirm,
      5 AS er_slo_target,
      CASE WHEN c.is_open THEN NULL
           WHEN e.total_days_in_er_confirm IS NULL THEN NULL
           WHEN e.total_days_in_er_confirm <= 5   THEN TRUE ELSE FALSE END AS er_slo_met,
      alt.total_days_in_alt_requested,
      5 AS alt_slo_target,
      CASE WHEN c.is_open THEN NULL
           WHEN alt.total_days_in_alt_requested IS NULL THEN NULL
           WHEN alt.total_days_in_alt_requested <= 5   THEN TRUE ELSE FALSE END AS alt_slo_met,
      CASE
        WHEN c.is_open THEN NULL
        WHEN r.total_days_in_rdp IS NOT NULL
             AND e.total_days_in_er_confirm IS NOT NULL THEN 'Hit RFD'
        WHEN r.total_days_in_rdp IS NULL
             AND e.total_days_in_er_confirm IS NOT NULL THEN 'Skipped RFD'
        WHEN e.total_days_in_er_confirm IS NULL          THEN 'Skipped ERC'
        ELSE 'Other'
      END AS pipeline_path
  FROM in_window_opps c
  JOIN bi_reporting.advising_opportunities a ON c.sfdc_object_id = a.sfdc_object_id
  LEFT JOIN rdp_totals              r    ON c.sfdc_object_id = r.opportunity_id
  LEFT JOIN er_totals               e    ON c.sfdc_object_id = e.opportunity_id
  LEFT JOIN alt_totals              alt  ON c.sfdc_object_id = alt.opportunity_id
  LEFT JOIN hist_current_open_stage curr ON c.sfdc_object_id = curr.opportunity_id
)
SELECT
    /* Identity + link */
    s.sfdc_object_id,
    a.sfdc_object_name_or_num,
    a.zp_company_id,
    'https://gusto.my.salesforce.com/' || LEFT(s.sfdc_object_id, 15) AS opp_link,
    /* Cohort + close */
    a.create_date,
    TO_CHAR(s.create_date_month, 'YYYY-MM')            AS create_date_month,
    s.close_date_computed,
    TO_CHAR(s.close_date_computed_month, 'YYYY-MM')    AS close_date_computed_month,
    TO_CHAR(s.close_or_create_month, 'YYYY-MM')        AS close_or_create_month,
    s.time_to_close_computed,
    s.current_status,
    s.close_stage_source,
    s.pipeline_path,
    s.order_lost_no_prior_closed_won,
    /* Open-backlog specific */
    s.is_open,
    s.age_days,
    s.days_in_current_status,
    s.overdue_days,
    s.refresh_date,
    /* Stage totals + SLO flags */
    s.total_days_in_rdp,
    s.rdp_slo_target,
    s.rdp_slo_met,
    s.total_days_in_er_confirm,
    s.er_slo_target,
    s.er_slo_met,
    s.total_days_in_alt_requested,
    s.alt_slo_target,
    s.alt_slo_met,
    /* Complexity + owner */
    a.funding_type,
    a.is_multi_ein,
    a.needs_recertification,
    a.owner_name,
    a.owner_role,
    a.opportunity_owner_pe_name             AS pe_name,
    a.opportunity_owner_pepe_name           AS pepe_name,
    a.opportunity_owner_pe_name_at_close    AS pe_name_at_close,
    a.opportunity_owner_pepe_name_at_close  AS pepe_name_at_close,
    a.last_time_owner_assigned_date,
    a.team,
    a.org,
    a.record_type,
    /* Status flags */
    a.completed_flag,
    a.cancel_flag,
    a.difot_flag,
    a.advising_blocked_reason,
    a.stage_detail                          AS current_stage_detail,
    a.reason_for_advising,
    a.status_on_eom_prior_effective_date,
    /* Dates */
    a.close_date,
    a.first_close_date,
    a.renewal_date,
    a.sla_date,
    a.recommendation_sla_date,
    a.first_health_sla_date,
    a.month_prior_effective_date,
    a.eom_prior_effective_date,
    a.offering_selection_deadline,
    a.last_status_change_ts,
    a.first_ready_for_default_package_dt,
    a.last_ready_for_default_package_dt,
    a.first_recommendation_sent_ts,
    a.first_er_confirm_dt,
    a.last_er_confirm_dt,
    a.answering_survey_start_dt,
    a.answering_survey_end_dt,
    a.time_to_impl_days,
    a.owner_time_to_close_days
FROM opp_sla s
JOIN bi_reporting.advising_opportunities a ON s.sfdc_object_id = a.sfdc_object_id
ORDER BY s.is_open DESC, s.age_days DESC, s.sfdc_object_id;
