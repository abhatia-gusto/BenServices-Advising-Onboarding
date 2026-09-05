-- Per-IC call counts + durations (bi.phone_user_metrics) — Broker (BYB+BT)
-- Params: {{start_date}} / {{end_date}}
with roster as (select name,cxone_agent_id::varchar agent_id,effect_start_dt,effect_end_dt from bi.gusto_employees
  where cxone_agent_id is not null and team='Benefits Onboarding' and sub_team in ('Bring Your Broker','Benefits Transfers')),
rd as (select distinct r.name,ph.conversation_id,ph.orig_direction,ph.sum_voice_ttalkcomplete_secs
 from bi.phone_user_metrics ph join roster r on ph.user_id::varchar=r.agent_id
   and to_date(ph.conversation_start_date) between r.effect_start_dt and r.effect_end_dt
 where ph.conversation_start_date between '{{start_date}}' and '{{end_date}}')
select name as ADVISOR_NAME,
  sum(case when orig_direction='inbound' then 1 else 0 end) as INBOUND_CALL_CT,
  sum(case when orig_direction='outbound' then 1 else 0 end) as OUTBOUND_CALL_CT,
  count(conversation_id) as PHONE_CALL_COUNT,
  round(avg(case when orig_direction='inbound' then nullif(sum_voice_ttalkcomplete_secs,0)/60.0 end),2) as INBOUND_AVG_CALL_DURATION_MINS,
  round(median(case when orig_direction='inbound' then nullif(sum_voice_ttalkcomplete_secs,0)/60.0 end),2) as INBOUND_MEDIAN_CALL_DURATION_MINS,
  round(avg(case when orig_direction='outbound' then nullif(sum_voice_ttalkcomplete_secs,0)/60.0 end),2) as OUTBOUND_AVG_CALL_DURATION_MINS,
  round(median(case when orig_direction='outbound' then nullif(sum_voice_ttalkcomplete_secs,0)/60.0 end),2) as OUTBOUND_MEDIAN_CALL_DURATION_MINS
from rd group by 1 order by 1
