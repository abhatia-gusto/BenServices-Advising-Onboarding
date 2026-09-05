-- Level AI call vs email (bi.fct_level_ai_conversation_asr_log, bi.cases) — Broker (BYB+BT)
-- Params: {{start_date}} / {{end_date}}
with roster as (select name,email from bi.gusto_employees where current_flag=true
  and team='Benefits Onboarding' and sub_team in ('Bring Your Broker','Benefits Transfers') and is_pe=false)
select r.name as FULL_NAME, count(*) as N_EVALS,
  sum(case when lower(a.channel_name)='email' then 1 else 0 end) as EMAIL_CT,
  sum(case when lower(a.channel_name)='call' then 1 else 0 end) as CALL_CT
from roster r join bi.fct_level_ai_conversation_asr_log a on a.user_email=r.email
  and convert_timezone('UTC','America/Denver', a.conversation_ts)::date between '{{start_date}}' and '{{end_date}}'
left join bi.cases b on a.case_number=b.casenumber
where a.qa_score is not null and nvl(b.record_type_name,'Call') in ('Benefits Renewal Case','Benefits BYB','Benefits New Plan Case','MF NHE','MF Member/Group Updates','Call')
group by 1 order by 1
