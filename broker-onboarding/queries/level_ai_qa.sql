-- Level AI QA score / month (bi.fct_level_ai_conversation_asr_log, bi.cases) — Broker (BYB+BT)
-- Params: {{start_date}} / {{end_date}}
with roster as (select name,email from bi.gusto_employees where current_flag=true
  and team='Benefits Onboarding'
  and sub_team in ('Bring Your Broker','Benefits Transfers') and is_pe=false)
select r.name as FULL_NAME,
  date_trunc('month', convert_timezone('UTC','America/Denver', a.conversation_ts))::date as CONVO_MONTH,
  sum(a.qa_score) as QA_EARNED, sum(a.max_qa_score) as QA_POSSIBLE
from roster r join bi.fct_level_ai_conversation_asr_log a on a.user_email=r.email
  and convert_timezone('UTC','America/Denver', a.conversation_ts)::date between '{{start_date}}' and '{{end_date}}'
left join bi.cases b on a.case_number=b.casenumber
where a.qa_score is not null
  and nvl(b.record_type_name,'Call') in ('Benefits Renewal Case','Benefits BYB','Benefits New Plan Case','MF NHE','MF Member/Group Updates','Call')
group by 1,2 order by 1,2
