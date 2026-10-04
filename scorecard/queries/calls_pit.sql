with roster as (
  select cxone_agent_id::varchar agent_id, effect_start_dt, effect_end_dt,
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
  select distinct r.team, r.agent_id, ph.conversation_id, ph.orig_direction, ph.sum_voice_ttalkcomplete_secs,
    pc.abandoned_count,
    case when pc.acd_queue_name ilike '%remove from queue%' or pc.acd_orig_queue_name ilike '%remove from queue%' then 1 else 0 end rfq,
    to_date(ph.conversation_start_date) call_date
  from bi.phone_user_metrics ph
  join roster r on ph.user_id::varchar = r.agent_id
   and to_date(ph.conversation_start_date) between r.effect_start_dt and r.effect_end_dt
  left join bi.phone_calls pc on pc.conversation_id = ph.conversation_id
  where ph.conversation_start_date between date_trunc('month', dateadd(month,-12,current_date)) and current_date
    and r.team is not null
)
select team, agent_id, call_date,
  sum(case when orig_direction='inbound' then 1 else 0 end) inbound_ct,
  sum(case when orig_direction='outbound' then 1 else 0 end) outbound_ct,
  sum(coalesce(abandoned_count,0)) abandoned_ct,
  sum(case when rfq=1 then 0 else coalesce(abandoned_count,0) end) abandoned_mod_ct,
  sum(case when orig_direction='inbound' then coalesce(nullif(sum_voice_ttalkcomplete_secs,0),0) else 0 end) in_talk_secs,
  sum(case when orig_direction='inbound' and nullif(sum_voice_ttalkcomplete_secs,0) is not null then 1 else 0 end) in_talk_n,
  sum(case when orig_direction='outbound' then coalesce(nullif(sum_voice_ttalkcomplete_secs,0),0) else 0 end) out_talk_secs,
  sum(case when orig_direction='outbound' and nullif(sum_voice_ttalkcomplete_secs,0) is not null then 1 else 0 end) out_talk_n
from rd group by team, agent_id, call_date
