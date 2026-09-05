-- Level AI QA per IC × month — CANONICAL (derived from queries/level_ai_qa.sql).
-- Change vs prior q_qa: joins bi.cases + applies the record-type filter (Benefits
-- case types + 'Call'), and scores with POOLED qa_score/max_qa_score (not AVG of
-- QA_SCORE_PERCENT). NPR/OA roster, point-in-time (effect dates). Full June 2026.
-- Output: IC, MONTH, QA (pooled %), N_QA (eval count) — build_data3 reads QA + N_QA.
with src as (
  select ee.name as ic,
    to_char(date_trunc('month', convert_timezone('UTC','America/Denver', a.conversation_ts)),'YYYY-MM') as mo,
    a.qa_score, a.max_qa_score
  from bi.fct_level_ai_conversation_asr_log a
  left join bi.cases b on a.case_number = b.casenumber
  join bi.gusto_employees ee
    on convert_timezone('UTC','America/Denver', a.conversation_ts)::date between ee.effect_start_dt and ee.effect_end_dt
   and a.user_email = ee.email
   and ee.sub_team in ('New Plan & Renewal Onboarding','Onboarding Advocacy')
   and ee.is_pe = false
  where a.qa_score is not null
    and nvl(b.record_type_name,'Call') in ('Benefits Renewal Case','Benefits BYB','Benefits New Plan Case','MF NHE','MF Member/Group Updates','Call')
    and convert_timezone('UTC','America/Denver', a.conversation_ts)::date between '2026-01-01' and CURRENT_DATE()
)
select ic as IC, mo as MONTH,
  round(100.0 * sum(qa_score) / nullif(sum(max_qa_score),0), 2) as QA,
  count(*) as N_QA
from src group by 1,2 order by 1,2
