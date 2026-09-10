-- email_recency (B): per-opp last outbound / last inbound EMAIL touchpoint date.
-- Drives the "we've gone quiet" (last_outbound_email_date) and "customer gone
-- quiet" (last_inbound_email_date) risk signals. Source per the app's docs:
-- DATA_WAREHOUSE_RC1.BI.BENEFIT_ORDER_TOUCHPOINTS (channel='Email', direction in/out),
-- keyed to the opp via BO_OPP_ID. Grain: one row per opp. No PII (dates only).
select bo_opp_id opp,
  to_char(max(case when direction='Outbound' then touchpoint_start_ts end)::date) last_outbound_email_date,
  to_char(max(case when direction='Inbound'  then touchpoint_start_ts end)::date) last_inbound_email_date
from data_warehouse_rc1.bi.benefit_order_touchpoints
where lower(channel)='email'
  and bo_opp_id in (select sfdc_object_id from data_warehouse_rc1.bi_reporting.advising_opportunities
                    where renewal_date in ({{cohort_dates}}))
group by bo_opp_id;
