-- Abandon (modified) (bi.phone_user_metrics, bi.phone_calls) — Broker (BYB+BT)
-- Params: {{start_date}} / {{end_date}}
with roster as (select name,cxone_agent_id::varchar agent_id,effect_start_dt,effect_end_dt from bi.gusto_employees
  where cxone_agent_id is not null and team='Benefits Onboarding' and sub_team in ('Bring Your Broker','Benefits Transfers')),
rd as (select distinct r.name,ph.conversation_id,ph.orig_direction,pc.abandoned_count,
  case when pc.acd_queue_name ilike '%remove from queue%' or pc.acd_orig_queue_name ilike '%remove from queue%' then 1 else 0 end rfq,
  to_date(ph.conversation_start_date) call_date
 from bi.phone_user_metrics ph join roster r on ph.user_id::varchar=r.agent_id
   and to_date(ph.conversation_start_date) between r.effect_start_dt and r.effect_end_dt
 left join bi.phone_calls pc on pc.conversation_id=ph.conversation_id
 where ph.conversation_start_date between '{{start_date}}' and '{{end_date}}')
select date_trunc('month',call_date)::date as MONTH, name as ADVISOR_NAME,
  sum(case when rfq=1 then 0 else coalesce(abandoned_count,0) end) as ABANDONED_MODIFIED,
  sum(case when orig_direction='inbound' then 1 else 0 end) as INBOUND_CALLS
from rd group by 1,2 order by 1,2
