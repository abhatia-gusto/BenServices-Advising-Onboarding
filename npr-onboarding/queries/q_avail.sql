-- OA PHONE AVAILABILITY per IC × month — shared source of truth.
-- Derived from queries/av_pit_icmonth.sql (Call Dashboard point-in-time band method
-- for OA). Point-in-time roster (no current_flag gate); denom = Workday paid-minus-meal
-- (fallback CXOne aux); eligible day = denom>=120; SLA = availability BETWEEN 80 AND 105.
-- Filtered to team = 'Onboarding Advocacy' (covers NPR + OA sub_teams). Full June 2026.
-- Output: IC, MONTH, ELIG_DAYS, SLA_MET_DAYS  (build_data3 reads SLA_MET_DAYS / ELIG_DAYS).
with roster as (
  select name, email, effect_start_dt, effect_end_dt,
    case when sub_team in ('New Plan & Renewal Onboarding','Onboarding Advocacy') then 'Onboarding Advocacy' end team
  from bi.gusto_employees
  where is_pe=false and email is not null
    and sub_team in ('New Plan & Renewal Onboarding','Onboarding Advocacy')
),
aux as (
  select r.name, r.email, aux.gusto_employee_id, aux.activity_start_ts::date aux_date,
    sum(case when lower(activity_nm_standardized) in ('call','outbound call','outboundcontact','outbound') then activity_length_mins end) phone_mins,
    sum(case when lower(activity_nm) in ('lunch','break') then activity_length_mins end) lunch_break_mins,
    sum(activity_length_mins)::float total_aux_mins
  from (
    select * from bi.wfm_agent_activity_log_details
    where source_system='CXOne-API' and activity_start_ts::date between '2026-01-01' and CURRENT_DATE()
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
  where reported_date::date between '2026-01-01' and CURRENT_DATE() and in_time is not null
    and (primary_position ilike '%Onboarding Advoca%' or primary_position ilike '%New Plan%' or primary_position ilike '%Benefit%Services%')
  group by all
),
j as (
  select a.*, nvl(c.paid_mins, a.total_aux_mins) band_denom
  from aux a left join clock c on a.gusto_employee_id::bigint=c.employee_id::bigint and c.reported_date::date=a.aux_date
),
d as (
  select name, aux_date reported_date,
    case when band_denom<120 then null when (nvl(phone_mins,0)/nullif(band_denom,0)*100) between 80 and 105 then 1 else 0 end sla
  from j
)
select name as IC, to_char(date_trunc('month', reported_date),'YYYY-MM') as MONTH,
  count(case when sla is not null then 1 end) as ELIG_DAYS,
  sum(sla) as SLA_MET_DAYS
from d group by 1,2 order by 1,2
