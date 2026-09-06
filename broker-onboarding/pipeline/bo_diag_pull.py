#!/usr/bin/env python3
"""BO Performance diagnostics inputs (Email SLA + CSAT + comments) → /tmp for add_diagnostics.py.
Email = canonical queries/bo_email_month.sql (BYB/BT owners). CSAT = ces_csat_data→benefit_orders.
QC (bo_qc_month/detail) is optional in add_diagnostics and pulled separately once schema confirmed."""
import os, subprocess, sys
HOME=os.path.expanduser("~"); HERE=os.path.dirname(os.path.abspath(__file__))
import datetime as _dt
S,E="2026-01-01",(os.environ.get("PERF_END") or _dt.date.today().isoformat())
SUBT="('Bring Your Broker','Benefits Transfers')"

def run_sql(sql,out,required=True):
    env=os.environ.copy(); env["PATH"]=f"{HOME}/.local/bin:"+env.get("PATH","")
    p=subprocess.run(["snow","sql","-q",sql,"--format","csv","--enable-templating","NONE"],
                     env=env,capture_output=True,text=True,timeout=600)
    if p.returncode!=0:
        print(f"WARN: {out} failed:",p.stderr[-600:])
        if required: raise SystemExit("required pull failed: "+out)
        return
    chunks=[c.strip() for c in p.stdout.split("\n\n") if c.strip()]
    open(out,"w").write(chunks[-1]+"\n")
    print(f"wrote {out}: {chunks[-1].count(chr(10))} rows incl header")

EMAIL=open(os.path.join(HERE,"queries","bo_email_month.sql")).read().replace("{{PERF_END}}",E)

CSAT=f"""with roster as (select name from bi.gusto_employees where current_flag=true
  and team='Benefits Onboarding' and sub_team in {SUBT}),
c as (select sfdc_onboarding_object_id, csat_score, typeform_submitted_at
      from bi_reporting.ces_csat_data
      where typeform_submitted_at between '{S}' and '{E} 23:59:59' and csat_score is not null)
select r.name as IC, date_trunc('month', c.typeform_submitted_at)::date as MONTH,
  sum(c.csat_score) as SCORE_SUM, count(*) as RESPONSES
from c join bi_reporting.benefit_orders bo on bo.sfdc_benefit_order_id=c.sfdc_onboarding_object_id
join roster r on r.name=bo.benefit_order_owner group by 1,2 order by 1,2"""

CMT=f"""with roster as (select name from bi.gusto_employees where current_flag=true
  and team='Benefits Onboarding' and sub_team in {SUBT}),
c as (select sfdc_onboarding_object_id, csat_score, typeform_submitted_at, coalesce(comment, byb_csat_verbatim) as cmt
      from bi_reporting.ces_csat_data
      where typeform_submitted_at between '{S}' and '{E} 23:59:59' and csat_score is not null and coalesce(comment, byb_csat_verbatim) is not null)
select r.name as IC, to_char(c.typeform_submitted_at::date) as DT, c.csat_score as SCORE, c.cmt as CMT
from c join bi_reporting.benefit_orders bo on bo.sfdc_benefit_order_id=c.sfdc_onboarding_object_id
join roster r on r.name=bo.benefit_order_owner order by 1, c.typeform_submitted_at desc"""

# QC — wraps the canonical BYB/BT QC query (queries/bo_qc_errors.sql). Severity = Primary
# if error_type is one of the CX QC Error Guide primary types, else Secondary.
_QCSRC=open(os.path.join(HERE,"queries","bo_qc_errors.sql")).read()\
    .replace("{{ Date Range Start }}",S).replace("{{ Date Range End }}",E).rstrip().rstrip(";")
_PRIM="lower(error_type) in ('missed ee enrollment','missed participation','group set up issue','coverage terminated')"

QC_MONTH=f"""with base as (
{_QCSRC}
)
select owner_name as IC, date_trunc('month',system_created_ts)::date as MONTH,
  count(*) as TOTAL, sum(iff({_PRIM},1,0)) as PRIMARY, sum(iff({_PRIM},0,1)) as SECONDARY
from base where owner_name is not null group by 1,2 order by 1,2"""

QC_DETAIL=f"""with base as (
{_QCSRC}
)
select owner_name as IC, qa_error_name as QCSHORT, system_created_ts::date as DT,
  date_trunc('month',system_created_ts)::date as MONTH, error_type as ETYPE,
  iff({_PRIM},'Primary','Secondary') as SEVERITY, error_type_detail as GUIDE_REASON,
  coalesce(from_sub_team, sub_function) as ORIGIN, sfdc_qa_error_id as QID,
  sfdc_benefit_order_id as BOID, sfdc_carrier_order_id as COID, sfdc_ticket_id as TID,
  qa_reviewer_name as CREATED_BY, '' as CUSTOMER
from base where owner_name is not null order by owner_name, system_created_ts desc"""

if __name__=="__main__":
    run_sql(EMAIL,"/tmp/bo_email_month.csv",required=True)
    run_sql(CSAT,"/tmp/bo_csat_month.csv",required=True)
    run_sql(CMT,"/tmp/bo_csat_comments.csv",required=False)
    run_sql(QC_MONTH,"/tmp/bo_qc_month.csv",required=False)
    run_sql(QC_DETAIL,"/tmp/bo_qc_detail.csv",required=False)
    print("DONE")
