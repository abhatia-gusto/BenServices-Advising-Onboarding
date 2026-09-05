-- CSAT comments verbatim (bi_reporting.ces_csat_data -> benefit_orders) — Broker (BYB+BT)
-- Params: {{start_date}} / {{end_date}}
with roster as (select name from bi.gusto_employees where current_flag=true
  and team='Benefits Onboarding' and sub_team in ('Bring Your Broker','Benefits Transfers')),
c as (select sfdc_onboarding_object_id, csat_score, typeform_submitted_at, coalesce(comment, byb_csat_verbatim) as cmt
      from bi_reporting.ces_csat_data
      where typeform_submitted_at between '{{start_date}}' and '{{end_date}} 23:59:59' and csat_score is not null and coalesce(comment, byb_csat_verbatim) is not null)
select r.name as IC, to_char(c.typeform_submitted_at::date) as DT, c.csat_score as SCORE, c.cmt as CMT
from c join bi_reporting.benefit_orders bo on bo.sfdc_benefit_order_id=c.sfdc_onboarding_object_id
join roster r on r.name=bo.benefit_order_owner order by 1, c.typeform_submitted_at desc
