-- CSAT score/responses per IC x month (bi_reporting.ces_csat_data -> benefit_orders) — Broker (BYB+BT)
-- Params: {{start_date}} / {{end_date}}
with roster as (select name from bi.gusto_employees where current_flag=true
  and team='Benefits Onboarding' and sub_team in ('Bring Your Broker','Benefits Transfers')),
c as (select sfdc_onboarding_object_id, csat_score, typeform_submitted_at
      from bi_reporting.ces_csat_data
      where typeform_submitted_at between '{{start_date}}' and '{{end_date}} 23:59:59' and csat_score is not null)
select r.name as IC, date_trunc('month', c.typeform_submitted_at)::date as MONTH,
  sum(c.csat_score) as SCORE_SUM, count(*) as RESPONSES
from c join bi_reporting.benefit_orders bo on bo.sfdc_benefit_order_id=c.sfdc_onboarding_object_id
join roster r on r.name=bo.benefit_order_owner group by 1,2 order by 1,2
