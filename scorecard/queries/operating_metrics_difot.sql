-- DIFOT source query — cohort range fixed start 2024-01-01, dynamic end = last day of (today + 1 month)
-- Drives the BenServices Operating Metrics embedded dashboard. Refreshed daily.
WITH per_bo AS (
  SELECT
      h.sfdc_object_id,
      DATE_TRUNC('month', h.cvg_effective_dt)::date AS cohort_month,
      h.bo_create_dt::date AS bo_create_date,
      MAX(h.record_type) AS record_type,
      BOOLOR_AGG(b.difot_flag)  AS difot_flag,
      BOOLOR_AGG(b.cancel_flag) AS cancel_flag,
      BOOLOR_AGG(h.completed_flag) AS completed_flag,
      BOOLOR_AGG(b.revised_difot_flag) AS revised_difot_flag,
      MAX(b.full_process_cycle_time_min) AS full_cycle_time_min,
      MAX(b.total_tickets) AS total_tickets,
      MAX(b.total_benefits_advising_tickets) AS total_benefits_advising_tickets,
      MAX(b.total_new_plan_sales_tickets) AS total_new_plan_sales_tickets,
      MAX(b.total_implementation_advocate_tickets) AS total_implementation_advocate_tickets,
      MAX(b.total_er_outreach_tickets) AS total_er_outreach_tickets,
      BOOLOR_AGG(b.oe_by_5th_flag)  AS oe_by_5th_flag,
      BOOLOR_AGG(b.rsp_by_15th_flag) AS rsp_by_15th_flag,
      BOOLOR_AGG(b.submitted_within_3d_flag) AS submitted_within_3d_flag,
      BOOLOR_AGG(b.rfc_by_20th_flag) AS rfc_by_20th_flag,
      MAX(b.funding_type) AS funding_type
  FROM bi.benefit_order_status_change_history h
  LEFT JOIN bi.benefit_orders b
    ON b.sfdc_benefit_order_id = h.sfdc_object_id
  WHERE DATE_TRUNC('month', h.cvg_effective_dt)
        BETWEEN TO_DATE('2024-01-01') AND LAST_DAY(DATEADD('month', 1, CURRENT_DATE()))
    AND h.record_type IN ('Renewal','New Plan')
  GROUP BY 1,2,3
),
with_prior AS (
  SELECT
      sfdc_object_id,
      record_type,
      cohort_month,
      bo_create_date,
      CASE WHEN difot_flag THEN 1 ELSE 0 END AS difot_flag,
      CASE WHEN cancel_flag THEN 1 ELSE 0 END AS cancel_flag,
      CASE WHEN completed_flag THEN 1 ELSE 0 END AS completed_flag,
      CASE WHEN revised_difot_flag THEN 1 ELSE 0 END AS revised_difot_flag,
      full_cycle_time_min,
      total_tickets,
      total_benefits_advising_tickets,
      total_new_plan_sales_tickets,
      total_implementation_advocate_tickets,
      total_er_outreach_tickets,
      CASE WHEN oe_by_5th_flag THEN 1 ELSE 0 END AS oe_by_5th_flag,
      CASE WHEN rsp_by_15th_flag THEN 1 ELSE 0 END AS rsp_by_15th_flag,
      CASE WHEN submitted_within_3d_flag THEN 1 ELSE 0 END AS submitted_within_3d_flag,
      CASE WHEN rfc_by_20th_flag THEN 1 ELSE 0 END AS rfc_by_20th_flag,
      funding_type,
      ADD_MONTHS(cohort_month, -1)::date AS prior_month_1st
  FROM per_bo
),
agg_by_type AS (
  SELECT
      cohort_month,
      record_type,
      COUNT(DISTINCT sfdc_object_id) AS total_orders,
      COUNT(DISTINCT CASE WHEN bo_create_date <= prior_month_1st THEN sfdc_object_id END)
          AS created_by_prior_month_1st,
      ROUND(
        COUNT(DISTINCT CASE WHEN bo_create_date <= prior_month_1st THEN sfdc_object_id END)::float /
        NULLIF(COUNT(DISTINCT sfdc_object_id),0) * 100 ,1
      ) AS pct_created_by_prior_month_1st,
      COUNT(DISTINCT CASE WHEN bo_create_date <= LAST_DAY(ADD_MONTHS(cohort_month,-2)) THEN sfdc_object_id END)
          AS ready_by_eom_prior,
      ROUND(
        COUNT(DISTINCT CASE WHEN bo_create_date <= LAST_DAY(ADD_MONTHS(cohort_month,-2)) THEN sfdc_object_id END)::float /
        NULLIF(COUNT(DISTINCT sfdc_object_id),0) * 100 ,1
      ) AS pct_ready_by_eom_prior,
      SUM(CASE WHEN cancel_flag = 0 AND oe_by_5th_flag=1 THEN 1 END) AS orders_oe_by_5th,
      ROUND(
        SUM(CASE WHEN cancel_flag=0 AND oe_by_5th_flag=1 THEN 1 END)::float /
        NULLIF((COUNT(*) - SUM(cancel_flag)),0) * 100 ,1
      ) AS pct_oe_by_5th,
      SUM(CASE WHEN cancel_flag = 0 AND rsp_by_15th_flag=1 THEN 1 END) AS orders_rsp_by_15th,
      ROUND(
        SUM(CASE WHEN cancel_flag=0 AND rsp_by_15th_flag=1 THEN 1 END)::float /
        NULLIF((COUNT(*) - SUM(cancel_flag)),0) * 100 ,1
      ) AS pct_rsp_by_15th,
      SUM(CASE WHEN cancel_flag = 0 AND submitted_within_3d_flag=1 THEN 1 END) AS orders_submitted_within_3d,
      ROUND(
        SUM(CASE WHEN cancel_flag=0 AND submitted_within_3d_flag=1 THEN 1 END)::float /
        NULLIF((COUNT(*) - SUM(cancel_flag)),0) * 100 ,1
      ) AS pct_submitted_within_3d,
      SUM(CASE WHEN cancel_flag = 0 AND rfc_by_20th_flag=1 THEN 1 END) AS orders_rfc_by_20th,
      ROUND(
        SUM(CASE WHEN cancel_flag=0 AND rfc_by_20th_flag=1 THEN 1 END)::float /
        NULLIF((COUNT(*) - SUM(cancel_flag)),0) * 100 ,1
      ) AS pct_rfc_by_20th,
      COUNT(DISTINCT CASE WHEN total_tickets >=1 THEN sfdc_object_id END) AS orders_with_tickets,
      ROUND(
        COUNT(DISTINCT CASE WHEN total_tickets>=1 THEN sfdc_object_id END)::float /
        NULLIF(COUNT(*),0) * 100 ,1
      ) AS pct_orders_with_tickets,
      COUNT(DISTINCT CASE WHEN total_tickets>=2 THEN sfdc_object_id END) AS orders_with_2plus_tix,
      ROUND(
        COUNT(DISTINCT CASE WHEN total_tickets>=2 THEN sfdc_object_id END)::float /
        NULLIF(COUNT(*),0) * 100 ,1
      ) AS pct_orders_with_2plus_tix,
      ROUND(SUM(COALESCE(total_tickets,0))::float / NULLIF(COUNT(*),0),2) AS avg_tickets_per_order,
      ROUND(SUM(COALESCE(total_benefits_advising_tickets,0))::float / NULLIF(COUNT(*),0),2)
          AS advising_tix_per_order,
      ROUND(SUM(COALESCE(total_new_plan_sales_tickets,0))::float / NULLIF(COUNT(*),0),2)
          AS new_plan_sales_tix_per_order,
      ROUND(SUM(COALESCE(total_implementation_advocate_tickets,0))::float / NULLIF(COUNT(*),0),2)
          AS impl_advocate_tix_per_order,
      ROUND(SUM(COALESCE(total_er_outreach_tickets,0))::float / NULLIF(COUNT(*),0),2)
          AS er_outreach_tix_per_order,
      SUM(difot_flag) AS difot_count,
      ROUND(SUM(difot_flag)::float /
            NULLIF((COUNT(*) - SUM(cancel_flag)),0) * 100 ,1) AS pct_difot,
      SUM(revised_difot_flag) AS revised_difot_count,
      ROUND(
        SUM(revised_difot_flag)::float /
        NULLIF((COUNT(*) - SUM(cancel_flag)),0) * 100 ,1
      ) AS pct_revised_difot,
      SUM(cancel_flag) AS cancel_count,
      ROUND(SUM(cancel_flag)::float / NULLIF(COUNT(*),0) * 100 ,1) AS pct_canceled,
      SUM(completed_flag) AS completed_count,
      ROUND(((COUNT(*) - SUM(cancel_flag) - SUM(completed_flag))::float /
            NULLIF((COUNT(*) - SUM(cancel_flag)),0)) * 100 ,1) AS pct_pending,
      ROUND(AVG(full_cycle_time_min)/1440,1) AS avg_full_cycle_time_days,
      ROUND(AVG(CASE WHEN funding_type ILIKE '%Fully%' THEN full_cycle_time_min END)/1440,1)
        AS avg_cycle_time_fully_insured_days,
      ROUND(AVG(CASE WHEN funding_type ILIKE '%Level%' THEN full_cycle_time_min END)/1440,1)
        AS avg_cycle_time_level_funded_days,
      SUM(CASE WHEN funding_type ILIKE '%Fully%' THEN 1 END) AS fully_insured_orders,
      SUM(CASE WHEN funding_type ILIKE '%Level%' THEN 1 END) AS level_funded_orders
  FROM with_prior
  GROUP BY 1,2
),
agg_total AS (
  SELECT
      cohort_month,
      'Total' AS record_type,
      COUNT(DISTINCT sfdc_object_id) AS total_orders,
      COUNT(DISTINCT CASE WHEN bo_create_date <= prior_month_1st THEN sfdc_object_id END)
        AS created_by_prior_month_1st,
      ROUND(
        COUNT(DISTINCT CASE WHEN bo_create_date <= prior_month_1st THEN sfdc_object_id END)::float /
        NULLIF(COUNT(DISTINCT sfdc_object_id),0) * 100 ,1
      ) AS pct_created_by_prior_month_1st,
      COUNT(DISTINCT CASE WHEN bo_create_date <= LAST_DAY(ADD_MONTHS(cohort_month,-2)) THEN sfdc_object_id END)
          AS ready_by_eom_prior,
      ROUND(
        COUNT(DISTINCT CASE WHEN bo_create_date <= LAST_DAY(ADD_MONTHS(cohort_month,-2)) THEN sfdc_object_id END)::float /
        NULLIF(COUNT(DISTINCT sfdc_object_id),0) * 100 ,1
      ) AS pct_ready_by_eom_prior,
      SUM(CASE WHEN cancel_flag = 0 AND oe_by_5th_flag=1 THEN 1 END) AS orders_oe_by_5th,
      ROUND(
        SUM(CASE WHEN cancel_flag=0 AND oe_by_5th_flag=1 THEN 1 END)::float /
        NULLIF((COUNT(*) - SUM(cancel_flag)),0) * 100 ,1
      ) AS pct_oe_by_5th,
      SUM(CASE WHEN cancel_flag = 0 AND rsp_by_15th_flag=1 THEN 1 END) AS orders_rsp_by_15th,
      ROUND(
        SUM(CASE WHEN cancel_flag=0 AND rsp_by_15th_flag=1 THEN 1 END)::float /
        NULLIF((COUNT(*) - SUM(cancel_flag)),0) * 100 ,1
      ) AS pct_rsp_by_15th,
      SUM(CASE WHEN cancel_flag = 0 AND submitted_within_3d_flag=1 THEN 1 END) AS orders_submitted_within_3d,
      ROUND(
        SUM(CASE WHEN cancel_flag=0 AND submitted_within_3d_flag=1 THEN 1 END)::float /
        NULLIF((COUNT(*) - SUM(cancel_flag)),0) * 100 ,1
      ) AS pct_submitted_within_3d,
      SUM(CASE WHEN cancel_flag = 0 AND rfc_by_20th_flag=1 THEN 1 END) AS orders_rfc_by_20th,
      ROUND(
        SUM(CASE WHEN cancel_flag=0 AND rfc_by_20th_flag=1 THEN 1 END)::float /
        NULLIF((COUNT(*) - SUM(cancel_flag)),0) * 100 ,1
      ) AS pct_rfc_by_20th,
      COUNT(DISTINCT CASE WHEN total_tickets>=1 THEN sfdc_object_id END) AS orders_with_tickets,
      ROUND(
        COUNT(DISTINCT CASE WHEN total_tickets>=1 THEN sfdc_object_id END)::float /
        NULLIF(COUNT(*),0) * 100 ,1
      ) AS pct_orders_with_tickets,
      COUNT(DISTINCT CASE WHEN total_tickets>=2 THEN sfdc_object_id END) AS orders_with_2plus_tix,
      ROUND(
        COUNT(DISTINCT CASE WHEN total_tickets>=2 THEN sfdc_object_id END)::float /
        NULLIF(COUNT(*),0) * 100 ,1
      ) AS pct_orders_with_2plus_tix,
      ROUND(SUM(COALESCE(total_tickets,0))::float / NULLIF(COUNT(*),0),2) AS avg_tickets_per_order,
      ROUND(SUM(COALESCE(total_benefits_advising_tickets,0))::float / NULLIF(COUNT(*),0),2)
        AS advising_tix_per_order,
      ROUND(SUM(COALESCE(total_new_plan_sales_tickets,0))::float / NULLIF(COUNT(*),0),2)
        AS new_plan_sales_tix_per_order,
      ROUND(SUM(COALESCE(total_implementation_advocate_tickets,0))::float / NULLIF(COUNT(*),0),2)
        AS impl_advocate_tix_per_order,
      ROUND(SUM(COALESCE(total_er_outreach_tickets,0))::float / NULLIF(COUNT(*),0),2)
        AS er_outreach_tix_per_order,
      SUM(difot_flag) AS difot_count,
      ROUND(
        SUM(difot_flag)::float /
        NULLIF((COUNT(*) - SUM(cancel_flag)),0) * 100 ,1
      ) AS pct_difot,
      SUM(revised_difot_flag) AS revised_difot_count,
      ROUND(
        SUM(revised_difot_flag)::float /
        NULLIF((COUNT(*) - SUM(cancel_flag)),0) * 100 ,1
      ) AS pct_revised_difot,
      SUM(cancel_flag) AS cancel_count,
      ROUND(SUM(cancel_flag)::float / NULLIF(COUNT(*),0) * 100 ,1) AS pct_canceled,
      SUM(completed_flag) AS completed_count,
      ROUND(
        ((COUNT(*) - SUM(cancel_flag) - SUM(completed_flag))::float /
         NULLIF((COUNT(*) - SUM(cancel_flag)),0)) * 100 ,1
      ) AS pct_pending,
      ROUND(AVG(full_cycle_time_min)/1440,1) AS avg_full_cycle_time_days,
      ROUND(AVG(CASE WHEN funding_type ILIKE '%Fully%' THEN full_cycle_time_min END)/1440,1)
        AS avg_cycle_time_fully_insured_days,
      ROUND(AVG(CASE WHEN funding_type ILIKE '%Level%' THEN full_cycle_time_min END)/1440,1)
        AS avg_cycle_time_level_funded_days,
      SUM(CASE WHEN funding_type ILIKE '%Fully%' THEN 1 END) AS fully_insured_orders,
      SUM(CASE WHEN funding_type ILIKE '%Level%' THEN 1 END) AS level_funded_orders
  FROM with_prior
  GROUP BY 1
)
SELECT *
FROM (
  SELECT * FROM agg_by_type
  UNION ALL
  SELECT * FROM agg_total
) final
ORDER BY final.cohort_month,
         CASE final.record_type
           WHEN 'Renewal' THEN 1
           WHEN 'New Plan' THEN 2
           WHEN 'Total' THEN 3
         END;
