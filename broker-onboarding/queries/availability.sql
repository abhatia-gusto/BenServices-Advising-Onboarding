-- Phone availability 70-105 band (bi.wfm_agent_activity_log_details, Workday, bi.gusto_employees) — Broker (BYB+BT)
-- Params: {{start_date}} / {{end_date}}
with roster as (select name,email,effect_start_dt,effect_end_dt from bi.gusto_employees
  where is_pe=false and email is not null and team='Benefits Onboarding' and sub_team in ('Bring Your Broker','Benefits Transfers')),
aux as (select r.name,r.email,aux.gusto_employee_id,aux.activity_start_ts::date aux_date,
  sum(case when lower(activity_nm_standardized) in ('call','outbound call','outboundcontact','outbound') then activity_length_mins end) phone_mins,
  sum(activity_length_mins)::float total_aux_mins
 from (select * from bi.wfm_agent_activity_log_details where source_system='CXOne-API'
       and activity_start_ts::date between '{{start_date}}' and '{{end_date}}'
       qualify row_number() over (partition by sor_agent_external_id,activity_start_ts,activity_nm order by sor_acd_id)=1) aux
 join roster r on r.email=aux.sor_agent_external_id and aux.business_dt_mt::date between r.effect_start_dt and r.effect_end_dt
 group by all),
clock as (select employee_id,reported_date,
  sum(case when calculation_tags ilike '%regular%' and calculation_tags not ilike '%meal%' then reported_quantity_min end)
  +coalesce(sum(case when calculation_tags ilike '%overtime%' then reported_quantity_min end),0) paid_mins
 from bi.people_analytics_workday_time_tracking where reported_date::date between '{{start_date}}' and '{{end_date}}' and in_time is not null
   and (primary_position ilike '%Bring Your Broker%' or primary_position ilike '%Benefits Transfers%'
     or primary_position ilike '%Broker Onboarding%' or primary_position ilike '%Benefit%Services%')
 group by all),
j as (select a.*,nvl(c.paid_mins,a.total_aux_mins) band_denom from aux a
  left join clock c on a.gusto_employee_id::bigint=c.employee_id::bigint and c.reported_date::date=a.aux_date),
d as (select name,aux_date reported_date,
  case when band_denom<120 then null when (nvl(phone_mins,0)/nullif(band_denom,0)*100) between 70 and 105 then 1 else 0 end sla
 from j)
select date_trunc('month',reported_date)::date as MONTH, name as NAME,
  sum(sla) as SLA_DAYS_MET, count(case when sla is not null then 1 end) as ELIGIBLE_DAYS
from d group by 1,2 order by 1,2
