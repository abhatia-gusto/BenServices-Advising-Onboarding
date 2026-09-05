with src as (
  select
    convert_timezone('UTC','America/Denver', a.conversation_ts)::date as convo_dt,
    to_char(date_trunc('month',
      convert_timezone('UTC','America/Denver', a.conversation_ts)), 'YYYY-MM') as month_key,
    ee.name as advisor_name,
    lower(a.channel_name) as channel
  from bi.fct_level_ai_conversation_asr_log a
  left join bi.cases b on a.case_number = b.casenumber
  join bi.gusto_employees ee
    on convert_timezone('UTC','America/Denver', a.conversation_ts)::date
         between ee.effect_start_dt and ee.effect_end_dt
   and a.user_email = ee.email
   and ee.team in ('Benefits Operations', 'Benefits Advising', 'Benefits Support', 'Benefits Onboarding')
  where a.qa_score is not null
    and nvl(b.record_type_name, 'Call') in (
          'Benefits Renewal Case', 'Benefits BYB', 'Benefits New Plan Case',
          'MF NHE', 'MF Member/Group Updates', 'Call'
        )
    and convert_timezone('UTC','America/Denver', a.conversation_ts)::date >= '{{start_date}}'
    and convert_timezone('UTC','America/Denver', a.conversation_ts)::date <= '{{end_date}}'
)
select advisor_name, month_key, channel, count(*) as n
from src
where advisor_name is not null
group by 1, 2, 3
order by advisor_name, month_key, channel
