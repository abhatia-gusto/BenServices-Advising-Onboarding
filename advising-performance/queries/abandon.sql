-- ════════════════════════════════════════════════════════════════════════════
-- PHONE CALLS / ABANDON — POINT-IN-TIME, per IC × MONTH  (shared source of truth)
-- ════════════════════════════════════════════════════════════════════════════
-- Rolls the Call Dashboard's q_calls_pit.sql logic up to name × month so the 3
-- Performance dashboards compute abandon EXACTLY like the Call Dashboard:
--   * point-in-time roster (effect dates; no current_flag gate; cxone_agent_id + job_title fallback)
--   * per-agent abandon; MODIFIED = excludes "remove from queue"; denom = inbound calls
-- Output grain: one row per (team, name, month) with inbound_ct + abandoned_mod_ct +
-- abandon_mod_pct. Each dashboard filters to its own active roster by name downstream.
-- Params: {{start_date}} / {{end_date}} (inclusive, YYYY-MM-DD).
-- ════════════════════════════════════════════════════════════════════════════
with roster as (
  select name, cxone_agent_id::varchar agent_id, effect_start_dt, effect_end_dt,
    case
      when sub_team in ('Benefits Advising','Customer Advising') then 'Benefits Advising'
      when sub_team in ('New Plan & Renewal Onboarding','Onboarding Advocacy') then 'Onboarding Advocacy'
      when sub_team='Bring Your Broker' then 'BYB'
      when sub_team='Benefits Transfers' then 'BT'
      when sub_team='Broker Onboarding' then 'Broker Onboarding'
      when job_title in ('Onboarding Advocacy','Onboarding Advocacy - Captain','Benefits Onboarding','Onboarding Advocacy - Learning and Development') then 'Onboarding Advocacy'
    end team
  from bi.gusto_employees
  where cxone_agent_id is not null
    and (sub_team in ('Benefits Advising','Customer Advising','New Plan & Renewal Onboarding','Onboarding Advocacy','Bring Your Broker','Benefits Transfers','Broker Onboarding')
      or job_title in ('Onboarding Advocacy','Onboarding Advocacy - Captain','Benefits Onboarding','Onboarding Advocacy - Learning and Development'))
),
rd as (
  select distinct r.team, r.name, r.agent_id, ph.conversation_id, ph.orig_direction,
    pc.abandoned_count,
    case when pc.acd_queue_name ilike '%remove from queue%' or pc.acd_orig_queue_name ilike '%remove from queue%' then 1 else 0 end rfq,
    to_date(ph.conversation_start_date) call_date
  from bi.phone_user_metrics ph
  join roster r on ph.user_id::varchar = r.agent_id
   and to_date(ph.conversation_start_date) between r.effect_start_dt and r.effect_end_dt
  left join bi.phone_calls pc on pc.conversation_id = ph.conversation_id
  where ph.conversation_start_date between '{{start_date}}' and '{{end_date}}'
    and r.team is not null
),
m as (
  select team, name, to_char(date_trunc('month', call_date),'YYYY-MM') as month,
    sum(case when orig_direction='inbound' then 1 else 0 end) inbound_ct,
    sum(case when orig_direction='outbound' then 1 else 0 end) outbound_ct,
    sum(coalesce(abandoned_count,0)) abandoned_ct,
    sum(case when rfq=1 then 0 else coalesce(abandoned_count,0) end) abandoned_mod_ct
  from rd group by 1,2,3
)
select team, name, month, inbound_ct, outbound_ct, abandoned_ct, abandoned_mod_ct,
  case when inbound_ct>0 then round(100.0*abandoned_mod_ct/inbound_ct,2) end abandon_mod_pct
from m order by 1,2,3
