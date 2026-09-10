with boopp as (
  select distinct sfdc_benefit_order_id, sfdc_opportunity_id
  from data_warehouse_rc1.bi_reporting.benefit_orders
  where sfdc_benefit_order_id is not null
    and sfdc_opportunity_id in (select sfdc_object_id from data_warehouse_rc1.bi_reporting.advising_opportunities where renewal_date in ({{cohort_dates}}))
)
select b.sfdc_opportunity_id, t.sfdc_ticket_id, t.escalation_reason, t.escalation_reason_detail, t.status
from data_warehouse_rc1.bi.sfdc_tickets t
join boopp b on b.sfdc_benefit_order_id=t.sfdc_benefit_order_id
where t.team='Benefits Advising';
