-- ticket_sla: per-opp Met/Missed/na for the OA->Benefits-Advising ticket RESOLUTION SLA.
--
-- Population = Benefits-Advising tickets on the opp's benefit order(s) — the SAME
--   BO->ticket join as open_tickets.sql (bi_reporting.benefit_orders.sfdc_benefit_order_id
--   -> bi.sfdc_tickets, team='Benefits Advising'). Cancelled tickets are excluded (not a
--   real resolution; they are also excluded from the hub open-ticket count).
--
-- Per-ticket SLA reuses the performance dashboard's resolution logic
--   (advising-performance/queries/ticket_sla.sql — Flow 4a "OA -> Benefits Advising" carries
--   a 5-day resolution SLA, measured on BI.SFDC_TICKETS.TIME_TO_CLOSE_MIN):
--     * resolved ticket (status Closed/Resolved): MET if time_to_close_min <= 5 days
--       (5*1440 = 7200 minutes), else MISSED.
--     * still-open ticket: treated as breached once it has been open > 5 days
--       (datediff(day, created_ts, current_timestamp()) > 5) — mirrors open_tickets.sql's
--       open_tickets_past_sla; an open ticket <= 5 days old has not breached yet.
--
-- Opp roll-up (one row per opp): Missed if ANY advising ticket breached; Met if the opp has
--   >= 1 advising ticket and none breached; na if the opp has no advising ticket.
--
-- Grain: one row per opp (SFDC_OBJECT_ID). Company/plan grain only — no PII columns.
-- Feeds JSON: ticket_sla. current_timestamp() = live (evaluated at refresh time).
with c as (
  select sfdc_object_id
  from data_warehouse_rc1.bi_reporting.advising_opportunities
  where renewal_date in ({{cohort_dates}})
),
boopp as (
  select distinct sfdc_benefit_order_id, sfdc_opportunity_id
  from data_warehouse_rc1.bi_reporting.benefit_orders
  where sfdc_benefit_order_id is not null
    and sfdc_opportunity_id in (select sfdc_object_id from c)
),
tix as (
  select b.sfdc_opportunity_id opp,
    t.sfdc_ticket_id,
    case
      when t.status in ('Closed','Resolved')
        then case when t.time_to_close_min > 7200 then 1 else 0 end
      else case when datediff(day, t.created_ts, current_timestamp()) > 5 then 1 else 0 end
    end as breached
  from data_warehouse_rc1.bi.sfdc_tickets t
  join boopp b on b.sfdc_benefit_order_id = t.sfdc_benefit_order_id
  where t.team = 'Benefits Advising'
    and coalesce(t.status,'') <> 'Cancelled'
)
select c.sfdc_object_id as opp,
  case
    when count(t.sfdc_ticket_id) = 0 then 'na'
    when sum(t.breached) > 0 then 'Missed'
    else 'Met'
  end as ticket_sla
from c
left join tix t on t.opp = c.sfdc_object_id
group by c.sfdc_object_id;
