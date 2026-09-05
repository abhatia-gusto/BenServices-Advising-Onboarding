-- ════════════════════════════════════════════════════════════════════════════
-- PHONE AVAILABILITY — POINT-IN-TIME, per IC × MONTH  (shared source of truth)
-- ════════════════════════════════════════════════════════════════════════════
-- Rolls the Call Dashboard's q_av_pit.sql logic up to name × month so the 3
-- Performance dashboards compute availability EXACTLY like the Call Dashboard:
--   * point-in-time roster (effect dates; no current_flag gate)
--   * DUAL method: Benefits Advising -> hybrid-hours ('adv'); OA/BYB/BT/Broker -> 80-105 band
--   * denom = Workday paid-minus-meal, fallback CXOne total aux; eligible day = denom>=120
-- Output grain: one row per (team, name, month). elig_days / sla_met_days feed the
-- dashboards' availability metric (attainment = met/elig). Each dashboard filters
-- to its own active roster by name downstream.
-- Params: {{start_date}} / {{end_date}} (inclusive, YYYY-MM-DD).
-- ════════════════════════════════════════════════════════════════════════════
with roster as (
  select name, email, effect_start_dt, effect_end_dt,
    case when sub_team in ('Benefits Advising','Customer Advising') then 'Benefits Advising'
         when sub_team in ('New Plan & Renewal Onboarding','Onboarding Advocacy') then 'Onboarding Advocacy'
         when sub_team='Bring Your Broker' then 'BYB' when sub_team='Benefits Transfers' then 'BT'
         when sub_team='Broker Onboarding' then 'Broker Onboarding' end team
  from bi.gusto_employees
  where is_pe=false and email is not null
    and sub_team in ('Benefits Advising','Customer Advising','New Plan & Renewal Onboarding','Onboarding Advocacy','Bring Your Broker','Benefits Transfers','Broker Onboarding')
),
aux as (
  select r.team, r.name, r.email, aux.gusto_employee_id, aux.activity_start_ts::date aux_date,
    sum(case when lower(activity_nm_standardized) in ('call','outbound call','outboundcontact','outbound') then activity_length_mins end) phone_mins,
    sum(case when lower(activity_nm_standardized)='call' then activity_length_mins end) inbound_mins,
    sum(case when lower(activity_nm_standardized)='outbound call' then activity_length_mins end) outbound_mins,
    sum(case when lower(activity_nm) in ('lunch','break') then activity_length_mins end) lunch_break_mins,
    sum(activity_length_mins)::float total_aux_mins
  from (
    select * from bi.wfm_agent_activity_log_details
    where source_system='CXOne-API' and activity_start_ts::date between '{{start_date}}' and '{{end_date}}'
    qualify row_number() over (partition by sor_agent_external_id, activity_start_ts, activity_nm order by sor_acd_id)=1
  ) aux
  join roster r on r.email=aux.sor_agent_external_id and aux.business_dt_mt::date between r.effect_start_dt and r.effect_end_dt
  where r.team is not null
  group by all
),
clock as (
  select employee_id, reported_date,
    sum(case when calculation_tags ilike '%regular%' and calculation_tags not ilike '%meal%' then reported_quantity_min end)
      + coalesce(sum(case when calculation_tags ilike '%overtime%' then reported_quantity_min end),0) paid_mins
  from bi.people_analytics_workday_time_tracking
  where reported_date::date between '{{start_date}}' and '{{end_date}}' and in_time is not null
    and (primary_position ilike '%Advis%' or primary_position ilike '%Onboarding Advoca%' or primary_position ilike '%New Plan%'
      or primary_position ilike '%Bring Your Broker%' or primary_position ilike '%Benefits Transfers%'
      or primary_position ilike '%Broker Onboarding%' or primary_position ilike '%Benefit%Services%')
  group by all
),
j as (
  select a.*, c.paid_mins,
    greatest(least(a.total_aux_mins,540)-nvl(a.lunch_break_mins,0),0) core_mins,
    nvl(c.paid_mins, a.total_aux_mins) band_denom
  from aux a left join clock c on a.gusto_employee_id::bigint=c.employee_id::bigint and c.reported_date::date=a.aux_date
),
d as (
  select team, name, aux_date reported_date,
    round(nvl(phone_mins,0)/60.0,2) phone_hrs,
    case when team='Benefits Advising'
         then (case when core_mins<120 then null when core_mins>=420 then (case when nvl(phone_mins,0)>=390 then 1 else 0 end) else (case when nvl(phone_mins,0)>=core_mins*0.8 then 1 else 0 end) end)
         else (case when band_denom<120 then null when (nvl(phone_mins,0)/nullif(band_denom,0)*100) between 80 and 105 then 1 else 0 end) end sla
  from j
)
select team, name, to_char(date_trunc('month', reported_date),'YYYY-MM') as month,
  count(case when sla is not null then 1 end) as elig_days,
  sum(sla) as sla_met_days,
  round(sum(sla)::float / nullif(count(case when sla is not null then 1 end),0) * 100.0, 1) as sla_attainment_perc,
  round(sum(phone_hrs),1) as phone_hrs
from d
group by 1,2,3
order by 1,2,3
