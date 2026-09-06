#!/usr/bin/env python3
"""Refresh BO Performance source data through END (dynamic: PERF_END or today). Run one step at a time:
   python3 refresh_june.py roster|lai|byb|bt
Writes roster.csv + lai_janmay.csv to /tmp; byb/bt CSVs to the queries dir."""
import os, sys, subprocess
HOME=os.path.expanduser("~")
QDIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),"queries")
import datetime as _dt
END=os.environ.get("PERF_END") or _dt.date.today().isoformat()   # dynamic: through today (auto-advances)
START_BYBBT="2025-09-01"   # only recent months are scored; narrow window = fast pull
START_LAI="2026-01-01"

def run_sql(sql, out_csv):
    env=os.environ.copy(); env["PATH"]=f"{HOME}/.local/bin:"+env.get("PATH","")
    p=subprocess.run(["snow","sql","-q",sql,"--format","csv"],
                     env=env,capture_output=True,text=True,timeout=600)
    if p.returncode!=0:
        print("STDERR:",p.stderr[-1500:]); raise SystemExit("snow failed")
    chunks=[c.strip() for c in p.stdout.split("\n\n") if c.strip()]
    open(out_csv,"w").write(chunks[-1]+"\n")
    print(f"wrote {out_csv}: {chunks[-1].count(chr(10))} rows incl header")

def roster():
    sql=("select name as NAME, pe as PE, sub_team as SUB_TEAM, is_pe as IS_PE, status as STATUS "
         "from bi.gusto_employees where current_flag=true "
         "and team='Benefits Onboarding' and sub_team in ('Bring Your Broker','Benefits Transfers')")
    run_sql(sql,"/tmp/roster.csv")

def lai():
    sql=("with roster as (select name,email from bi.gusto_employees where current_flag=true "
         "and team='Benefits Onboarding' "
         "and sub_team in ('Bring Your Broker','Benefits Transfers') and is_pe=false) "
         "select r.name as FULL_NAME, "
         "date_trunc('month', convert_timezone('UTC','America/Denver', a.conversation_ts))::date as CONVO_MONTH, "
         "sum(a.qa_score) as QA_EARNED, sum(a.max_qa_score) as QA_POSSIBLE "
         "from roster r join bi.fct_level_ai_conversation_asr_log a on a.user_email=r.email "
         "and convert_timezone('UTC','America/Denver', a.conversation_ts)::date between '"+START_LAI+"' and '"+END+"' "
         "left join bi.cases b on a.case_number=b.casenumber "
         "where a.qa_score is not null "
         "and nvl(b.record_type_name,'Call') in ('Benefits Renewal Case','Benefits BYB','Benefits New Plan Case','MF NHE','MF Member/Group Updates','Call') "
         "group by 1,2 order by 1,2")
    run_sql(sql,"/tmp/lai_janmay.csv")

def pull(sqlfile, out):
    sql=open(os.path.join(QDIR,sqlfile)).read()
    sql=sql.replace("{{Date Range Start}}",START_BYBBT).replace("{{Date Range End}}",END)
    assert "{{" not in sql, "unreplaced placeholder in "+sqlfile
    run_sql(sql, os.path.join(QDIR,out))

if __name__=="__main__":
    s=sys.argv[1]
    if s=="roster": roster()
    elif s=="lai": lai()
    elif s=="byb": pull("byb_bo_sla_v7.sql", f"byb_data_{START_BYBBT}_to_{END}.csv")
    elif s=="bt":  pull("bt_bo_sla_v8.sql",  f"bt_data_{START_BYBBT}_to_{END}.csv")
    else: raise SystemExit("unknown step")

def csat():
    sql=("with roster as (select name, sub_team from bi.gusto_employees where current_flag=true "
         "and team='Benefits Onboarding' "
         "and sub_team in ('Bring Your Broker','Benefits Transfers')), "
         "c as (select sfdc_onboarding_object_id, csat_score, typeform_submitted_at "
         "from bi_reporting.ces_csat_data "
         "where typeform_submitted_at between '"+START_LAI+"' and '"+END+"' and csat_score is not null) "
         "select r.name as IC, r.sub_team as SUB_TEAM, "
         "date_trunc('month', c.typeform_submitted_at)::date as MONTH, "
         "sum(case when c.csat_score in (4,5) then 1 else 0 end) as TOPBOX, count(*) as RESPONSES "
         "from c join bi_reporting.benefit_orders bo on bo.sfdc_benefit_order_id=c.sfdc_onboarding_object_id "
         "join roster r on r.name=bo.benefit_order_owner group by 1,2,3 order by 1,3")
    run_sql(sql,"/tmp/bo_csat_month.csv")

if __name__=="__main__" and len(sys.argv)>1 and sys.argv[1]=="csat": csat()
