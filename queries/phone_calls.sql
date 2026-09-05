with adv_base as (
  select name, cxone_agent_id, pe
  from bi.gusto_employees
  where sub_team in ('Benefits Advising','Customer Advising')
    and current_flag = TRUE and terminated_at is null
),
rd as (
  select distinct
    adv.name,
    to_char(date_trunc('month', ph.conversation_start_date), 'YYYY-MM') as month_key,
    ph.conversation_id,
    ph.sum_voice_ttalkcomplete_secs,
    ph.orig_direction
  from bi.phone_user_metrics ph
  join adv_base adv on ph.user_id::varchar = adv.cxone_agent_id::varchar
  where ph.conversation_start_date between '{{start_date}}' and '{{end_date}}'
)
select
  name as advisor_name, month_key,
  count(conversation_id) as total,
  sum(case when orig_direction='inbound' then 1 else 0 end) as inbound,
  sum(case when orig_direction='outbound' then 1 else 0 end) as outbound,
  round(avg(case when orig_direction='inbound' then nullif(sum_voice_ttalkcomplete_secs,0)/60.0 end), 2) as inbound_avg_min,
  round(percentile_cont(0.5) within group (
    order by case when orig_direction='inbound' then nullif(sum_voice_ttalkcomplete_secs,0)/60.0 end), 2) as inbound_median_min,
  round(avg(case when orig_direction='outbound' then nullif(sum_voice_ttalkcomplete_secs,0)/60.0 end), 2) as outbound_avg_min,
  round(percentile_cont(0.5) within group (
    order by case when orig_direction='outbound' then nullif(sum_voice_ttalkcomplete_secs,0)/60.0 end), 2) as outbound_median_min
from rd
group by 1, 2
order by advisor_name, month_key
