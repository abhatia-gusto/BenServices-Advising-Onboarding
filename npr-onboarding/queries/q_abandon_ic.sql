-- OA PHONE ABANDON per IC × month — shared source of truth.
-- Derived from queries/calls_pit_icmonth.sql (Call Dashboard: per-agent, MODIFIED
-- abandon excludes 'remove from queue', denom = inbound calls). Point-in-time roster
-- (cxone_agent_id + job_title fallback). Filtered to team='Onboarding Advocacy'
-- (covers NPR + OA sub_teams). Full June 2026.
-- Output: IC, MONTH, INBOUND_CT, ABANDONED_MOD  (build_data3 reads INBOUND_CT / ABANDONED_MOD).
with roster as (
  select name, cxone_agent_id::varchar agent_id, effect_start_dt, effect_end_dt
  from bi.gusto_employees
  where cxone_agent_id is not null
    and (sub_team in ('New Plan & Renewal Onboarding','Onboarding Advocacy')
      or job_title in ('Onboarding Advocacy','Onboarding Advocacy - Captain','Benefits Onboarding','Onboarding Advocacy - Learning and Development'))
),
rd as (
  select distinct r.name, ph.conversation_id, ph.orig_direction,
    pc.abandoned_count,
    case when pc.acd_queue_name ilike '%remove from queue%' or pc.acd_orig_queue_name ilike '%remove from queue%' then 1 else 0 end rfq,
    to_date(ph.conversation_start_date) call_date
  from bi.phone_user_metrics ph
  join roster r on ph.user_id::varchar = r.agent_id
   and to_date(ph.conversation_start_date) between r.effect_start_dt and r.effect_end_dt
  left join bi.phone_calls pc on pc.conversation_id = ph.conversation_id
  where ph.conversation_start_date between '2026-01-01' and CURRENT_DATE()
)
select name as IC, to_char(date_trunc('month', call_date),'YYYY-MM') as MONTH,
  sum(case when orig_direction='inbound' then 1 else 0 end) as INBOUND_CT,
  sum(case when rfq=1 then 0 else coalesce(abandoned_count,0) end) as ABANDONED_MOD
from rd group by 1,2 order by 1,2
