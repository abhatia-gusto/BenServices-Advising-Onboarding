#!/usr/bin/env python3
"""BO Performance phone + Level-AI inputs — shared Call-Dashboard method, point-in-time
roster, full period Jan–Jun 2026. Writes 4 CSVs to /tmp for build_bo_perf_v2.py:
  bo_avail_month.csv   (MONTH,NAME,SLA_DAYS_MET,ELIGIBLE_DAYS)      band 70-105 (BO target)
  bo_abandon_month.csv (MONTH,ADVISOR_NAME,ABANDONED_MODIFIED,INBOUND_CALLS)
  bo_phone_rollup.csv  (per-IC full-period call counts + durations)
  bo_lai_rollup.csv    (FULL_NAME,N_EVALS,EMAIL_CT,CALL_CT)  canonical record-type filter
Method mirrors queries/av_pit_icmonth.sql + calls_pit_icmonth.sql; BO band = 70-105."""
import os, subprocess
import datetime as _dt
HOME=os.path.expanduser("~"); S,E="2026-01-01",(os.environ.get("PERF_END") or _dt.date.today().isoformat())
SUBT="('Bring Your Broker','Benefits Transfers')"
RT="('Benefits Renewal Case','Benefits BYB','Benefits New Plan Case','MF NHE','MF Member/Group Updates','Call')"

def run_sql(sql,out):
    env=os.environ.copy(); env["PATH"]=f"{HOME}/.local/bin:"+env.get("PATH","")
    p=subprocess.run(["snow","sql","-q",sql,"--format","csv","--enable-templating","NONE"],
                     env=env,capture_output=True,text=True,timeout=600)
    if p.returncode!=0: print("STDERR:",p.stderr[-1800:]); raise SystemExit("snow failed: "+out)
    chunks=[c.strip() for c in p.stdout.split("\n\n") if c.strip()]
    open(out,"w").write(chunks[-1]+"\n")
    print(f"wrote {out}: {chunks[-1].count(chr(10))} rows incl header")

AVAIL=f"""with roster as (select name,email,effect_start_dt,effect_end_dt from bi.gusto_employees
  where is_pe=false and email is not null and team='Benefits Onboarding' and sub_team in {SUBT}),
aux as (select r.name,r.email,aux.gusto_employee_id,aux.activity_start_ts::date aux_date,
  sum(case when lower(activity_nm_standardized) in ('call','outbound call','outboundcontact','outbound') then activity_length_mins end) phone_mins,
  sum(activity_length_mins)::float total_aux_mins
 from (select * from bi.wfm_agent_activity_log_details where source_system='CXOne-API'
       and activity_start_ts::date between '{S}' and '{E}'
       qualify row_number() over (partition by sor_agent_external_id,activity_start_ts,activity_nm order by sor_acd_id)=1) aux
 join roster r on r.email=aux.sor_agent_external_id and aux.business_dt_mt::date between r.effect_start_dt and r.effect_end_dt
 group by all),
clock as (select employee_id,reported_date,
  sum(case when calculation_tags ilike '%regular%' and calculation_tags not ilike '%meal%' then reported_quantity_min end)
  +coalesce(sum(case when calculation_tags ilike '%overtime%' then reported_quantity_min end),0) paid_mins
 from bi.people_analytics_workday_time_tracking where reported_date::date between '{S}' and '{E}' and in_time is not null
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
from d group by 1,2 order by 1,2"""

ABANDON=f"""with roster as (select name,cxone_agent_id::varchar agent_id,effect_start_dt,effect_end_dt from bi.gusto_employees
  where cxone_agent_id is not null and team='Benefits Onboarding' and sub_team in {SUBT}),
rd as (select distinct r.name,ph.conversation_id,ph.orig_direction,pc.abandoned_count,
  case when pc.acd_queue_name ilike '%remove from queue%' or pc.acd_orig_queue_name ilike '%remove from queue%' then 1 else 0 end rfq,
  to_date(ph.conversation_start_date) call_date
 from bi.phone_user_metrics ph join roster r on ph.user_id::varchar=r.agent_id
   and to_date(ph.conversation_start_date) between r.effect_start_dt and r.effect_end_dt
 left join bi.phone_calls pc on pc.conversation_id=ph.conversation_id
 where ph.conversation_start_date between '{S}' and '{E}')
select date_trunc('month',call_date)::date as MONTH, name as ADVISOR_NAME,
  sum(case when rfq=1 then 0 else coalesce(abandoned_count,0) end) as ABANDONED_MODIFIED,
  sum(case when orig_direction='inbound' then 1 else 0 end) as INBOUND_CALLS
from rd group by 1,2 order by 1,2"""

ROLLUP=f"""with roster as (select name,cxone_agent_id::varchar agent_id,effect_start_dt,effect_end_dt from bi.gusto_employees
  where cxone_agent_id is not null and team='Benefits Onboarding' and sub_team in {SUBT}),
rd as (select distinct r.name,ph.conversation_id,ph.orig_direction,ph.sum_voice_ttalkcomplete_secs
 from bi.phone_user_metrics ph join roster r on ph.user_id::varchar=r.agent_id
   and to_date(ph.conversation_start_date) between r.effect_start_dt and r.effect_end_dt
 where ph.conversation_start_date between '{S}' and '{E}')
select name as ADVISOR_NAME,
  sum(case when orig_direction='inbound' then 1 else 0 end) as INBOUND_CALL_CT,
  sum(case when orig_direction='outbound' then 1 else 0 end) as OUTBOUND_CALL_CT,
  count(conversation_id) as PHONE_CALL_COUNT,
  round(avg(case when orig_direction='inbound' then nullif(sum_voice_ttalkcomplete_secs,0)/60.0 end),2) as INBOUND_AVG_CALL_DURATION_MINS,
  round(median(case when orig_direction='inbound' then nullif(sum_voice_ttalkcomplete_secs,0)/60.0 end),2) as INBOUND_MEDIAN_CALL_DURATION_MINS,
  round(avg(case when orig_direction='outbound' then nullif(sum_voice_ttalkcomplete_secs,0)/60.0 end),2) as OUTBOUND_AVG_CALL_DURATION_MINS,
  round(median(case when orig_direction='outbound' then nullif(sum_voice_ttalkcomplete_secs,0)/60.0 end),2) as OUTBOUND_MEDIAN_CALL_DURATION_MINS
from rd group by 1 order by 1"""

LAIR=f"""with roster as (select name,email from bi.gusto_employees where current_flag=true
  and team='Benefits Onboarding' and sub_team in {SUBT} and is_pe=false)
select r.name as FULL_NAME, count(*) as N_EVALS,
  sum(case when lower(a.channel_name)='email' then 1 else 0 end) as EMAIL_CT,
  sum(case when lower(a.channel_name)='call' then 1 else 0 end) as CALL_CT
from roster r join bi.fct_level_ai_conversation_asr_log a on a.user_email=r.email
  and convert_timezone('UTC','America/Denver', a.conversation_ts)::date between '{S}' and '{E}'
left join bi.cases b on a.case_number=b.casenumber
where a.qa_score is not null and nvl(b.record_type_name,'Call') in {RT}
group by 1 order by 1"""

if __name__=="__main__":
    run_sql(AVAIL,"/tmp/bo_avail_month.csv")
    run_sql(ABANDON,"/tmp/bo_abandon_month.csv")
    run_sql(ROLLUP,"/tmp/bo_phone_rollup.csv")
    run_sql(LAIR,"/tmp/bo_lai_rollup.csv")
    print("DONE")
