-- open_tickets / open_tickets_past_sla: count of open OA->Benefits-Advising tickets
-- for each opp, via its benefit order(s). past_sla = created more than 5 days ago.
-- Source: BI.SFDC_TICKETS joined BI_REPORTING.BENEFIT_ORDERS on SFDC_BENEFIT_ORDER_ID.
-- Grain: one row per opp (SFDC_OBJECT_ID). Feeds JSON: open_tickets, open_tickets_past_sla.
with boopp as (
  select distinct sfdc_benefit_order_id, sfdc_opportunity_id
  from data_warehouse_rc1.bi_reporting.benefit_orders
  where sfdc_benefit_order_id is not null
    and sfdc_opportunity_id in (
      select sfdc_object_id from data_warehouse_rc1.bi_reporting.advising_opportunities
      where renewal_date in ({{cohort_dates}})
    )
)
select b.sfdc_opportunity_id opp,
  count(*) open_tickets,
  count(case when datediff(day, t.created_ts, current_timestamp()) > 5 then 1 end) open_tickets_past_sla
from data_warehouse_rc1.bi.sfdc_tickets t
join boopp b on b.sfdc_benefit_order_id = t.sfdc_benefit_order_id
where t.team = 'Benefits Advising'
  and t.status not in ('Closed','Resolved','Cancelled')
group by 1;
