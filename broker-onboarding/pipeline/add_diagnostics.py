#!/usr/bin/env python3
"""Post-process /tmp/varD2.json: add Email + CSAT diagnostics (non-scored) -> /tmp/varD3.json.
Diagnostics are month-aware (num/den per month) and live OUTSIDE the scored order/monthAware arrays."""
import csv, json, os
TMP="/tmp"
# Derive months from the scored build (build_bo_perf_v2 -> varD2.json) so diagnostics
# (email/csat/qc) always cover the SAME window as the core metrics — incl. the current
# partial month. Previously hardcoded through 2026-07, which silently dropped Aug data.
MONTHS=json.load(open(os.path.join(TMP,"varD2.json")))["months"]
KEY2LAB={m+"-01":m for m in MONTHS}

def loadtmp(fn):
    with open(os.path.join(TMP,fn)) as f: return list(csv.DictReader(f))
def ii(x):
    try: return int(float(x))
    except: return 0

EMAIL={}  # (name,label) -> (within, answered)
for r in loadtmp("bo_email_month.csv"):
    lab=KEY2LAB.get(r["MONTH"])
    if lab: EMAIL[(r["IC"],lab)]=(ii(r["WITHIN_SLA"]),ii(r["ANSWERED"]))
CSAT={}   # (name,label) -> (topbox, responses)
for r in loadtmp("bo_csat_month.csv"):
    lab=KEY2LAB.get(r["MONTH"])
    if lab: CSAT[(r["IC"],lab)]=(ii(r["SCORE_SUM"]),ii(r["RESPONSES"]))

CMT={}
import os as _o
if _o.path.exists(_o.path.join(TMP,"bo_csat_comments.csv")):
    for r in loadtmp("bo_csat_comments.csv"):
        CMT.setdefault(r["IC"],[]).append({"d":r["DT"],"s":ii(r["SCORE"]),"c":r["CMT"]})

QC={}     # (name,label) -> (total, primary, secondary)
if _o.path.exists(_o.path.join(TMP,"bo_qc_month.csv")):
    for r in loadtmp("bo_qc_month.csv"):
        lab=KEY2LAB.get(r["MONTH"])
        if lab: QC[(r["IC"],lab)]=(ii(r["TOTAL"]),ii(r["PRIMARY"]),ii(r["SECONDARY"]))
QCD={}    # name -> [ {qc,qcshort,dt,etype,sev,reason,origin,qid,boid,coid,tid,createdby,customer}, ... ]
if _o.path.exists(_o.path.join(TMP,"bo_qc_detail.csv")):
    for r in loadtmp("bo_qc_detail.csv"):
        QCD.setdefault(r["IC"],[]).append({"qc":r["QCSHORT"],"dt":r["DT"],"mo":KEY2LAB.get(r["MONTH"],""),
            "et":r["ETYPE"],"sev":r["SEVERITY"],"rsn":r["GUIDE_REASON"],"org":r["ORIGIN"],
            "qid":r["QID"],"bo":r["BOID"],"co":r["COID"],"tk":r["TID"],"by":r["CREATED_BY"],"cust":r["CUSTOMER"]})

D=json.load(open(os.path.join(TMP,"varD2.json")))

# diagnostic config (NOT scored, NOT gated)
D["diagnostics"]=["email","csat","qc"]
D["defaults"]["diagMeta"]={
  "email":{"l":"Email SLA","sub":"% met ≤4hr SLA","fmt":"pct","d":"gte","g":90,
           "tip":"Diagnostic (not scored): % of answered inbound emails responded within SLA. num=within-SLA, den=answered (within+past). Canonical email-SLA logic; case owner at touchpoint, point-in-time sub-team."},
  "csat":{"l":"CSAT","sub":"avg 1–5","fmt":"avg","d":"gte","g":4.5,
          "tip":"Diagnostic (not scored): average CSAT score (1-5). Sparse — many IC-months have no surveys."},
  "qc":{"l":"QC Errors","sub":"count (P·S)","fmt":"count","d":"lte","g":0,
        "tip":"Diagnostic (not scored): count of QC errors created that month (Primary/Secondary per CX QC Error Guide). Source BI.SFDC_QA_ERRORS, attributed to the error owner; month = created date."},
}

def add(group):
    for a in group["advisors"]:
        n=a["name"]; em={}; cs={}
        for m in MONTHS:
            w,ans=EMAIL.get((n,m),(0,0)); em[m]={"within":w,"answered":ans}
            sm,rs=CSAT.get((n,m),(0,0)); cs[m]={"sum":sm,"responses":rs}
        a["raw"]["email"]={"m":em}
        a["raw"]["csat"]={"m":cs}
        qm={}
        for m in MONTHS:
            t,pp,ss=QC.get((n,m),(0,0,0)); qm[m]={"total":t,"primary":pp,"secondary":ss}
        a["raw"]["qc"]={"m":qm}
        a["csatc"]=CMT.get(n,[])[:7]
        a["qcd"]=QCD.get(n,[])[:25]
for t in ("BYB","BT"): add(D[t])

json.dump(D,open(os.path.join(TMP,"varD3.json"),"w"))
# coverage summary
for t in ("BYB","BT"):
    em=sum(1 for a in D[t]["advisors"] if any(a["raw"]["email"]["m"][m]["answered"]>0 for m in MONTHS))
    cs=sum(1 for a in D[t]["advisors"] if any(a["raw"]["csat"]["m"][m]["responses"]>0 for m in MONTHS))
    print(f"{t}: {len(D[t]['advisors'])} ICs | email coverage {em} | csat coverage {cs}")
print("wrote /tmp/varD3.json")
