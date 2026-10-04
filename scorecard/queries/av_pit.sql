with roster as (
  select email, effect_start_dt, effect_end_dt,
    case when sub_team in ('Benefits Advising','Customer Advising') then 'Benefits Advising'
         when sub_team in ('New Plan & Renewal Onboarding','Onboarding Advocacy') then 'Onboarding Advocacy'
         when sub_team='Bring Your Broker' then 'BYB' when sub_team='Benefits Transfers' then 'BT'
         when sub_team='Broker Onboarding' then 'Broker Onboarding' end team
  from bi.gusto_employees
  where is_pe=false and email is not null
    and sub_team in ('Benefits Advising','Customer Advising','New Plan & Renewal Onboarding','Onboarding Advocacy','Bring Your Broker','Benefits Transfers','Broker Onboarding')
),
aux as (
  select r.team, r.email, aux.gusto_employee_id, aux.activity_start_ts::date aux_date,
    sum(case when lower(activity_nm_standardized) in ('call','outbound call','outboundcontact','outbound') then activity_length_mins end) phone_mins,
    sum(case when lower(activity_nm_standardized)='call' then activity_length_mins end) inbound_mins,
    sum(case when lower(activity_nm_standardized) in ('outbound call','outboundcontact','outbound') then activity_length_mins end) outbound_mins,
    sum(case when lower(activity_nm) in ('lunch','break') then activity_length_mins end) lunch_break_mins,
    sum(activity_length_mins)::float total_aux_mins
  from (
    select * from bi.wfm_agent_activity_log_details
    where source_system='CXOne-API' and activity_start_ts::date between date_trunc('month', dateadd(month,-12,current_date)) and current_date
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
  where reported_date::date between date_trunc('month', dateadd(month,-12,current_date)) and current_date and in_time is not null
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
)
select team, email, aux_date reported_date,
  case when team='Benefits Advising' then 'adv' else 'band' end method,
  round(total_aux_mins/60.0,2) logged_hrs, round(core_mins/60.0,2) core_hrs,
  round(nvl(phone_mins,0)/60.0,2) phone_hrs, round(nvl(inbound_mins,0)/60.0,2) inbound_hrs, round(nvl(outbound_mins,0)/60.0,2) outbound_hrs,
  round(band_denom/60.0,2) denom_hrs, case when paid_mins is not null then 'Workday' else 'CXOne' end denom_source,
  case when team='Benefits Advising' then (case when core_mins<120 then null when core_mins>=420 then 6.5 else round(core_mins*0.8/60.0,2) end) end adv_target_hrs,
  case when total_aux_mins>540 then 1 else 0 end over9,
  case when team='Benefits Advising' then (case when core_mins>=120 then round(least(nvl(phone_mins,0),core_mins)/nullif(core_mins,0)*100,1) end)
       else (case when band_denom>=120 then round(nvl(phone_mins,0)/nullif(band_denom,0)*100,1) end) end avail_pct,
  case when team!='Benefits Advising' and band_denom>=120 and (nvl(phone_mins,0)/nullif(band_denom,0)*100)>105 then 1 else 0 end over105,
  case when team='Benefits Advising' then (case when core_mins<120 then null when core_mins>=420 then (case when nvl(phone_mins,0)>=390 then 1 else 0 end) else (case when nvl(phone_mins,0)>=core_mins*0.8 then 1 else 0 end) end)
       else (case when band_denom<120 then null when (nvl(phone_mins,0)/nullif(band_denom,0)*100) between (case when team in ('BYB','BT','Broker Onboarding') then 70 else 80 end) and 105 then 1 else 0 end) end sla
from j order by team, email, reported_date
