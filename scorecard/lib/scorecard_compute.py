#!/usr/bin/env python3
"""
Benefit Services Scorecard — unified compute.

Reads the team's dashboard source files in this folder and emits
scorecard_data.json = { "MO":[...], "CATS":[...], "M":[...] } that the two
render templates (scorecard_grid.html / scorecard_chart.html) inject and show.

Period: set CUR_MONTHS (current year, e.g. 2026-01..2026-07) and PRIOR_MONTHS
(same window prior year, for YoY). Everything is anchored per §1 of SKILL.md.

Run all at once:      python3 scorecard_compute.py
Run one source only:  python3 scorecard_compute.py <part>
  parts: bo adv byb bt avail email csat ready   (each appends to _sc_parts.json)
  then: python3 scorecard_compute.py assemble    (builds scorecard_data.json)
Running with no arg does every part + assemble in one process.

The big CSVs + the 132MB email embed can exceed a ~45s sandbox cap in one shot;
if so, run the parts individually then `assemble`.
"""
import csv, glob, os, sys, json, gzip, base64, io, re
csv.field_size_limit(10**7)
HERE = os.path.dirname(os.path.abspath(__file__))
Q = os.path.join(HERE, "queries")
PARTS = os.path.join(HERE, "_sc_parts.json")

# ---- PERIOD (edit these to reslice) ----------------------------------------
CUR_MONTHS   = ["2026-01","2026-02","2026-03","2026-04","2026-05","2026-06","2026-07","2026-08","2026-09"]
PRIOR_MONTHS = ["2025-01","2025-02","2025-03","2025-04","2025-05","2025-06","2025-07","2025-08","2025-09"]
MO_LABELS    = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep"]   # Sep = full month (as of 2026-09-30)

# ---- helpers ---------------------------------------------------------------
def flg(x):
    s=(x or "").strip().lower()
    return 1 if s in("1","1.0","true") else (0 if s in("0","0.0","false") else None)
def num(x):
    s=(x or "").strip()
    try: return float(s)
    except: return None
def ent(x): return num(x) is not None
def nz(x):
    v=num(x); return v if v is not None else 0.0
def mo(x):
    s=(x or "").strip(); return s[:7] if len(s)>=7 else None
def rows(p):
    with open(p,newline="",encoding="utf-8",errors="replace") as f:
        for r in csv.DictReader(f): yield r
def newest(pat):
    g=sorted(glob.glob(os.path.join(Q,pat))); return g[-1] if g else None
def load_parts():
    return json.load(open(PARTS)) if os.path.exists(PARTS) else {}
def save_parts(d): json.dump(d, open(PARTS,"w"))
def A(months): return {m:[0.0,0.0] for m in months}
def pct(a,months): return [round(100*a[m][0]/a[m][1]) if a[m][1] else None for m in months]
def rate(a,months,nd=2): return [round(a[m][0]/a[m][1],nd) if a[m][1] else None for m in months]

# ---- per-source computes; each returns {label: {"v":[cur],"p":[prior]}} -----
def do_bo():
    path=os.path.join(HERE,"bo_sla_v11_clean.csv")
    OA={},;
    out={}
    for tag,MON in (("v",CUR_MONTHS),("p",PRIOR_MONTHS)):
        oa=A(MON); e2e=A(MON); npc=A(MON); trnp=A(MON); trren=A(MON); oaadv=A(MON)
        oe_subs={k:A(MON) for k in ["OE Prep","OE Verif","ER Outreach","Await Routing","Approved"]}
        oecol={"OE Prep":"SLA_READY_OE_PREP_MET","OE Verif":"SLA_OE_VERIF_MET","ER Outreach":"SLA_ER_OUTREACH_MET","Await Routing":"SLA_AWAIT_ROUTING_MET","Approved":"SLA_APPROVED_MET"}
        e2np=A(MON); e2ren=A(MON)
        for r in rows(path):
            rt=(r.get("RECORD_TYPE_NAME") or "").strip(); m=mo(r.get("FIRST_END_MONTH"))
            npren=rt in("New Plan","Renewal")
            if npren and m in MON:
                v=flg(r.get("SLA_BUCKET_WITH_OA_MET")); e=flg(r.get("FULFILLED_IN_30D_MET"))
                if v is not None: oa[m][1]+=1; oa[m][0]+=v
                if e is not None:
                    e2e[m][1]+=1; e2e[m][0]+=e
                    if rt=="New Plan": e2np[m][1]+=1; e2np[m][0]+=e
                    else: e2ren[m][1]+=1; e2ren[m][0]+=e
                for lbl,col in oecol.items():
                    fv=flg(r.get(col))
                    if fv is not None: oe_subs[lbl][m][1]+=1; oe_subs[lbl][m][0]+=fv
            if rt=="New Plan" and m in MON:
                c=flg(r.get("CANCEL_FLAG"))
                if c is not None: npc[m][1]+=1; npc[m][0]+=c
            if m in MON and str(r.get("FIRST_FULFILLED_TS_MT") or "").strip():
                t=num(r.get("TICKETS_BO_OA_MAPPED"))
                if t is not None:
                    if rt=="New Plan": trnp[m][1]+=1; trnp[m][0]+=t
                    elif rt=="Renewal": trren[m][1]+=1; trren[m][0]+=t
                if rt=="Renewal":
                    ta=num(r.get("TICKETS_TBL_OA_TO_BENADV")) or 0.0
                    oaadv[m][0]+=ta; oaadv[m][1]+=1
        out.setdefault("% BO meeting all OA status (≤1d/stg)",{})[tag]=pct(oa,MON)
        out.setdefault("Benefit Order — NP+Renewal (≤30d)",{})[tag]=pct(e2e,MON)
        out.setdefault("New Plan (close month)",{})[tag]=pct(npc,MON)
        out.setdefault("Ful→OA — New Plan",{})[tag]=rate(trnp,MON)
        out.setdefault("Ful→OA — Renewal",{})[tag]=rate(trren,MON)
        out.setdefault("OA→Advising — Renewal",{})[tag]=rate(oaadv,MON)
        out.setdefault("_det_BO_OA",{})[tag]={lbl:pct(oe_subs[lbl],MON) for lbl in oecol}
        out.setdefault("_det_BO_E2E",{})[tag]={"New Plan":pct(e2np,MON),"Renewal":pct(e2ren,MON)}
    return out

def do_adv():
    path=os.path.join(Q,"advising_opp_data_latest.csv")
    out={}
    for tag,MON in (("v",CUR_MONTHS),("p",PRIOR_MONTHS)):
        rdp=A(MON); er=A(MON); alt=A(MON)
        for r in rows(path):
            m=mo(r.get("CLOSE_DATE_COMPUTED_MONTH"))
            if m not in MON: continue
            for col,a in (("RDP_SLO_MET",rdp),("ER_SLO_MET",er),("ALT_SLO_MET",alt)):
                v=flg(r.get(col))
                if v is not None: a[m][1]+=1; a[m][0]+=v
        out.setdefault("Advising — RFD (≤5d)",{})[tag]=pct(rdp,MON)
        out.setdefault("Advising — ER Confirm (≤5d)",{})[tag]=pct(er,MON)
        out.setdefault("Advising — Alt Requested (≤5d)",{})[tag]=pct(alt,MON)
    return out

def do_byb():
    path=newest("byb_data_2024-01-01_to_*.csv"); out={}
    tr_subs_cols=[("Ready Impl Plans","READY_IMPL_PLANS_SLA_MET"),("Plans Confirmed","PLANS_CONFIRMED_SLA_MET"),
                  ("OE Verif","OE_VERIF_SLA_MET"),("OE Submission","OE_SUBMISSION_SLA_MET"),("Fulfillment Prep","FULFILLMENT_PREP_SLA_MET")]
    for tag,MON in (("v",CUR_MONTHS),("p",PRIOR_MONTHS)):
        ri=A(MON); im=A(MON); tr=A(MON); e2=A(MON); cn=A(MON)
        subs={lbl:A(MON) for lbl,_ in tr_subs_cols}
        for r in rows(path):
            m=mo(r.get("FIRST_END_MONTH"))
            if m not in MON: continue
            # status buckets count ONLY orders that entered the stage (total days>0) — matches benefits_transition_sla_dashboard_v5 (applyBucketMet nulls zero-day buckets)
            for col,dcol,a in (("READY_INTRO_SLA_MET_BUCKET","READY_INTRO_TOTAL_DAYS",ri),("IMPLEMENTATION_SLA_MET_BUCKET","IMPLEMENTATION_TOTAL_DAYS",im),("TRANSITION_SLA_MET","TRANSITION_TOTAL_DAYS",tr),("E2E_SLA_MET",None,e2),("CANCEL_FLAG",None,cn)):
                v=flg(r.get(col))
                if dcol and not ((num(r.get(dcol)) or 0)>0): continue
                if v is not None: a[m][1]+=1; a[m][0]+=v
            for lbl,col in tr_subs_cols:
                v=flg(r.get(col))
                dc=col.replace("_SLA_MET","_DAYS")
                if dc in r and not ((num(r.get(dc)) or 0)>0): continue
                if v is not None: subs[lbl][m][1]+=1; subs[lbl][m][0]+=v
        out.setdefault("BYB — Ready Intro (≤3d)",{})[tag]=pct(ri,MON)
        out.setdefault("BYB — Implementation (≤5d)",{})[tag]=pct(im,MON)
        out.setdefault("BYB — Transition (≤2d/stg)",{})[tag]=pct(tr,MON)
        out.setdefault("BYB (≤60d)",{})[tag]=pct(e2,MON)
        out.setdefault("BYB (close month)",{})[tag]=pct(cn,MON)
        out.setdefault("_det_BYB_TRANS",{})[tag]={lbl:pct(subs[lbl],MON) for lbl,_ in tr_subs_cols}
    return out

def do_bt():
    path=newest("bt_data_2024-01-01_to_*.csv"); out={}
    ent0=lambda x:(num(x) or 0)>0   # 'entered stage' = days>0 (dashboard treats 0-day as not entered)
    QUAL=["READY_QUALIF_DAYS","QUALIFICATION_DAYS","READY_DOC_COLLECT_DAYS"]
    IP=["READY_IMPL_PLANS_DAYS","IMPL_PLANS_DAYS","READY_PLAN_REVIEW_DAYS"]
    EE=["PLANS_CONFIRMED_DAYS","ENROLL_REVIEW_ENTRY_DAYS","READY_SEND_ENROLL_DAYS"]
    TR=["ENROLL_CONFIRMED_DAYS","BLOCKED_PLAN_REVIEW_DAYS","READY_TADA_DOC_COLLECT_DAYS","UNBLOCK_PLAN_REVIEW_DAYS"]
    qsub=[("Ready for Qualif","READY_QUALIF_SLA_MET"),("Qualification","QUALIFICATION_SLA_MET"),("Ready for Doc Collect","READY_DOC_COLLECT_SLA_MET")]
    isub=[("Ready Impl Plans","READY_IMPL_PLANS_SLA_MET"),("Impl Plans","IMPL_PLANS_SLA_MET"),("Ready Send Plan Review","READY_PLAN_REVIEW_SLA_MET"),("Plans Confirmed","PLANS_CONFIRMED_SLA_MET"),("Enroll Review Entry","ENROLL_REVIEW_ENTRY_SLA_MET"),("Ready Send Enroll Rev","READY_SEND_ENROLL_SLA_MET"),("Impl TAdA Plans","IMPL_TADA_PLANS_SLA_MET")]
    tsub=[("Enroll Confirmed","ENROLL_CONFIRMED_SLA_MET"),("Blocked Plan Review","BLOCKED_PLAN_REVIEW_SLA_MET"),("Ready TAdA Doc Collect","READY_TADA_DOC_COLLECT_SLA_MET"),("Unblock Plan Review","UNBLOCK_PLAN_REVIEW_SLA_MET")]
    for tag,MON in (("v",CUR_MONTHS),("p",PRIOR_MONTHS)):
        q=A(MON); i=A(MON); t=A(MON); e=A(MON); c=A(MON)
        dq={l:A(MON) for l,_ in qsub}; di={l:A(MON) for l,_ in isub}; dt={l:A(MON) for l,_ in tsub}
        for r in rows(path):
            m=mo(r.get("FIRST_END_MONTH"))
            if m not in MON: continue
            _dd=num(r.get("DAYS_CREATED_TO_FIRST_FULFILLED"))
            if _dd is not None and _dd>1000: continue  # exclude admin closes of legacy (2018-19) records stamped fulfilled in a batch (Sep-2026: 11 BT orders)
            if any(ent0(r.get(x)) for x in QUAL): q[m][1]+=1; q[m][0]+= 1 if sum(nz(r.get(x)) for x in QUAL)<=5 else 0
            ipe=any(ent0(r.get(x)) for x in IP); eee=any(ent0(r.get(x)) for x in EE); tae=ent0(r.get("IMPL_TADA_PLANS_DAYS"))
            if ipe or eee or tae:
                ok=True
                if ipe and sum(nz(r.get(x)) for x in IP)>5: ok=False
                if eee and sum(nz(r.get(x)) for x in EE)>5: ok=False
                if tae and nz(r.get("IMPL_TADA_PLANS_DAYS"))>5: ok=False
                i[m][1]+=1; i[m][0]+= 1 if ok else 0
            et=[x for x in TR if ent0(r.get(x))]
            if et: t[m][1]+=1; t[m][0]+= 1 if all(nz(r.get(x))<=2 for x in et) else 0
            d=num(r.get("DAYS_CREATED_TO_FIRST_FULFILLED"))
            if d is not None: e[m][1]+=1; e[m][0]+= 1 if d<=35 else 0
            cf=flg(r.get("CANCEL_FLAG"))
            if cf is not None: c[m][1]+=1; c[m][0]+=cf
            for grp,cols in ((dq,qsub),(di,isub),(dt,tsub)):
                for l,col in cols:
                    fv=flg(r.get(col))
                    dc=col.replace("_SLA_MET","_DAYS")
                    if dc in r and not ent0(r.get(dc)): continue
                    if fv is not None: grp[l][m][1]+=1; grp[l][m][0]+=fv
        out.setdefault("BT — Qualification (≤5d)",{})[tag]=pct(q,MON)
        out.setdefault("BT — Implementation (≤5d)",{})[tag]=pct(i,MON)
        out.setdefault("BT — Transition (≤2d/stg)",{})[tag]=pct(t,MON)
        out.setdefault("BT (≤35d)",{})[tag]=pct(e,MON)
        out.setdefault("BT (close month)",{})[tag]=pct(c,MON)
        out.setdefault("_det_BT_QUAL",{})[tag]={l:pct(dq[l],MON) for l,_ in qsub}
        out.setdefault("_det_BT_IMPL",{})[tag]={l:pct(di[l],MON) for l,_ in isub}
        out.setdefault("_det_BT_TRANS",{})[tag]={l:pct(dt[l],MON) for l,_ in tsub}
    return out

def do_avail():
    teams=["Onboarding Advocacy","Benefits Advising","BYB","BT","Broker Onboarding"]; out={}
    # availability + abandon have no pre-2025-08 data → only current year (p stays None)
    av=A(CUR_MONTHS); ab=A(CUR_MONTHS)
    avt={t:A(CUR_MONTHS) for t in teams}; abt={t:A(CUR_MONTHS) for t in teams}
    for r in rows(os.path.join(HERE,"_data_v2","av_pit.csv")):
        m=mo(r.get("REPORTED_DATE")); t=(r.get("TEAM") or "").strip()
        if m not in CUR_MONTHS: continue
        v=flg(r.get("SLA"))
        if v is not None:
            av[m][1]+=1; av[m][0]+=v
            if t in teams: avt[t][m][1]+=1; avt[t][m][0]+=v
    for r in rows(os.path.join(HERE,"_data_v2","calls_pit.csv")):
        m=mo(r.get("CALL_DATE")); t=(r.get("TEAM") or "").strip()
        if m not in CUR_MONTHS: continue
        inb=num(r.get("INBOUND_CT")); abd=num(r.get("ABANDONED_CT"))
        if inb is not None: ab[m][1]+=inb
        if abd is not None: ab[m][0]+=abd
        if t in teams:
            if inb is not None: abt[t][m][1]+=inb
            if abd is not None: abt[t][m][0]+=abd
    out["Org — Phone availability (80–105%)"]={"v":pct(av,CUR_MONTHS),"p":None}
    out["Org — Abandon rate (overall)"]={"v":pct(ab,CUR_MONTHS),"p":None}
    out["_det_AVAIL"]={"v":{t:pct(avt[t],CUR_MONTHS) for t in teams}}
    out["_det_ABANDON"]={"v":{t:pct(abt[t],CUR_MONTHS) for t in teams}}
    return out

def do_email():
    html=open(os.path.join(HERE,"email-sla-dashboard-v10.html"),encoding="utf-8",errors="replace").read()
    s=html.find(">",html.find('id="__EMBED__"'))+1; e=html.find("</",s)
    raw=gzip.decompress(base64.b64decode(html[s:e].strip())).decode("utf-8",errors="replace")
    acc=A(CUR_MONTHS)
    for r in csv.DictReader(io.StringIO(raw)):
        m=mo(r.get("TOUCHPOINT_START_TS_MT"))
        if m not in CUR_MONTHS: continue
        st=(r.get("INBOUND_EMAIL_RESPONSE_STATUS") or "").strip()
        if st=="Responded (Within SLA)": acc[m][1]+=1; acc[m][0]+=1
        elif st=="Responded (Past SLA)": acc[m][1]+=1
    return {"Org — Email SLO (≤4h) ★":{"v":pct(acc,CUR_MONTHS),"p":None}}

def do_csat():
    TYPES={"Renewed Benefits Feedback":"Renewal CSAT","New Benefits Feedback":"New Benefits CSAT","BYB Onboarding Feedback":"BYB CSAT","Benefits Transfers Feedback":"BT CSAT"}
    out={}
    csat=newest("csat_data_2025-01-01_to_*.csv"); ia=newest("inapp_data_2025-01-01_to_*.csv")
    for tag,MON in (("v",CUR_MONTHS),("p",PRIOR_MONTHS)):
        acc={lbl:{m:[0.0,0] for m in MON} for lbl in TYPES.values()}
        for r in rows(csat):
            k=TYPES.get((r.get("SURVEY_NAME") or "").strip())
            if not k: continue
            m=mo(r.get("SURVEY_SUBMITTED_DATE"))
            if m not in MON: continue
            sc=num(r.get("SURVEY_CSAT_SCORE"))
            if sc is None: continue
            acc[k][m][0]+=sc; acc[k][m][1]+=1
        iacc={m:[0.0,0] for m in MON}
        for r in rows(ia):
            m=mo(r.get("SURVEY_DATE"))
            if m not in MON: continue
            sc=num(r.get("RATING"))
            if sc is None: continue
            iacc[m][0]+=sc; iacc[m][1]+=1
        def av(a): return [round(a[m][0]/a[m][1],2) if a[m][1] else None for m in MON]
        for k in ["Renewal CSAT","New Benefits CSAT","BYB CSAT","BT CSAT"]:
            out.setdefault(k,{})[tag]=av(acc[k])
        out.setdefault("In-App Sentiment survey",{})[tag]=av(iacc)
    return out

def do_ready():
    # Ready by 1st = PCT_CREATED_BY_PRIOR_MONTH_1ST, Renewal, keyed COHORT_MONTH.
    # Scorecard column for calendar month M shows the NEXT month's cohort (M+1).
    html=open(os.path.join(HERE,"benservices_operating_metrics_dashboard_v1.html"),encoding="utf-8",errors="replace").read()
    i=html.find('id="embeddedData"'); s=html.find(">",i)+1; e=html.find("</script>",s)
    recs=list(csv.DictReader(io.StringIO(html[s:e].strip())))
    def nextcoh(months):
        out=[]
        for m in months:
            y,mm=int(m[:4]),int(m[5:7]); mm+=1
            if mm==13: y+=1; mm=1
            c="%04d-%02d"%(y,mm)
            row=next((r for r in recs if r["COHORT_MONTH"][:7]==c and r["RECORD_TYPE"]=="Renewal"),None)
            out.append(round(float(row["PCT_CREATED_BY_PRIOR_MONTH_1ST"])) if row and row["PCT_CREATED_BY_PRIOR_MONTH_1ST"] else None)
        return out
    return {"Ready by 1st — next cohort (Renewal)":{"v":nextcoh(CUR_MONTHS),"p":nextcoh(PRIOR_MONTHS)}}

def do_advmrr():
    # Advising Net MRR Retention % — same methodology as the Advising MRR Dashboard
    # (Redash 154070 / Advising_MRR_Model_v7 loader).
    #   Net MRR       = Won Δ − Churn MRR
    #                   Won Δ    = Σ(MRR_TOTAL_AFTER − MRR_TOTAL_BEFORE) on Closed Won
    #                   Churn    = Σ(MRR_TOTAL_BEFORE) on Closed Lost + Order Lost
    #   Retention %   = (MRR at stake + Net MRR) / MRR at stake
    #                   MRR at stake = Σ(MRR_TOTAL_BEFORE) over all resolved opps
    #   Month anchor  = INFERRED_CLOSE_DATE. Target 100% / cliff 94% (green ≥100, amber 94–99, red <94).
    # NOTE: % ONLY per Aman (2026-09-02) — the Net MRR $ figure is intentionally NOT surfaced.
    # Canonical source = the Advising MRR dashboard's trimmed cohort CSV, dropped into this
    # folder by that dashboard's refresh (candidate names below). If it isn't present the row
    # emits Nones and assemble() drops the category — it populates on the next refresh that has
    # the feed. Do NOT source from _renewal_full/out/mrr.csv (renewal-automation build, not 154070).
    cands=sorted(glob.glob(os.path.join(HERE,"advising_mrr_cohort*.csv"))
           +glob.glob(os.path.join(HERE,"*_last_trimmed.csv"))
           +glob.glob(os.path.join(Q,"advising_mrr_cohort*.csv")))
    path=cands[-1] if cands else None
    RES={"Closed Won","Closed Lost","Order Lost"}
    def series(MON):
        if not path: return [None]*len(MON)
        acc={m:[0.0,0.0,0.0] for m in MON}   # [wonΔ, churn, stake]
        for r in rows(path):
            st=(r.get("STATUS") or "").strip()
            if st not in RES: continue
            m=mo(r.get("INFERRED_CLOSE_DATE"))
            if m not in MON: continue
            b=nz(r.get("MRR_TOTAL_BEFORE")); a=nz(r.get("MRR_TOTAL_AFTER"))
            acc[m][2]+=b
            if st=="Closed Won": acc[m][0]+=(a-b)
            else: acc[m][1]+=b
        out=[]
        for m in MON:
            won,churn,stake=acc[m]; net=won-churn
            out.append(round(100*(stake+net)/stake,1) if stake else None)
        return out
    return {"Advising — Net MRR Retention %":{"v":series(CUR_MONTHS),"p":series(PRIOR_MONTHS)}}

def do_ticketsla():
    # Ticket SLA = % of tickets closed within 5 days of creation, by close month
    # (TICKET_CLOSED_TS_MT). Flow definitions MATCH the Ticket SLA by Flow dashboard's
    # own FL[] predicates (v12), NOT a simple TICKET_TEAM filter:
    #   Ful→OA  (fOA) = TICKET_REPORTING_TEAM='Fulfillment' AND HAS_OA_TOUCH='true'
    #   OA→Advising (f4a, "OA → BenAdv") = TICKET_REPORTING_TEAM='Implementation Advocate'
    #                 AND TICKET_TEAM='Benefits Advising' AND IS_OPEN != 'true'
    # SLA% = closed-within-5d ÷ all closed (tickets with TTC). 5-day threshold = dashboard sla:5.
    # Source = ticket_sla_by_flow_v12.html embed (plain-CSV in id="__EMBED__", NOT gzip).
    from datetime import datetime
    path=os.path.join(HERE,"ticket_sla_by_flow_v12.html")
    if not os.path.exists(path): return {}
    html=open(path,encoding="utf-8",errors="replace").read()
    s=html.find(">",html.find('id="__EMBED__"'))+1; e=html.find("</",s)
    raw=html[s:e]
    def pts(x):
        x=(x or "").strip()
        for f in ("%Y-%m-%dT%H:%M:%S","%Y-%m-%d %H:%M:%S","%Y-%m-%d"):
            try: return datetime.strptime(x[:19],f)
            except: pass
        return None
    def is_fOA(r): return r.get("TICKET_REPORTING_TEAM")=="Fulfillment" and r.get("HAS_OA_TOUCH")=="true"
    def is_f4a(r): return (r.get("TICKET_REPORTING_TEAM")=="Implementation Advocate"
                           and r.get("TICKET_TEAM")=="Benefits Advising" and r.get("IS_OPEN")!="true")
    FLOWS=[("Ful→OA — Ticket SLA (≤5d)",is_fOA),("OA→Advising — Ticket SLA (≤5d)",is_f4a)]
    out={}
    for tag,MON in (("v",CUR_MONTHS),("p",PRIOR_MONTHS)):
        acc={lbl:A(MON) for lbl,_ in FLOWS}
        for r in csv.DictReader(io.StringIO(raw)):
            ct=pts(r.get("TICKET_CLOSED_TS_MT")); cr=pts(r.get("TICKET_CREATED_TS_MT"))
            if not ct or not cr: continue
            m="%04d-%02d"%(ct.year,ct.month)
            if m not in MON: continue
            within=1 if (ct-cr).total_seconds()/86400.0<=5 else 0
            for lbl,fn in FLOWS:
                if fn(r): acc[lbl][m][1]+=1; acc[lbl][m][0]+=within
        for lbl,_ in FLOWS: out.setdefault(lbl,{})[tag]=pct(acc[lbl],MON)
    return out

PARTMAP={"bo":do_bo,"adv":do_adv,"byb":do_byb,"bt":do_bt,"avail":do_avail,"email":do_email,"csat":do_csat,"ready":do_ready,"advmrr":do_advmrr,"ticketsla":do_ticketsla}

# ---- assembly: metadata (order/goals/units) defined ONCE -------------------
def assemble():
    d=load_parts()
    def g(name,key="v"): return d.get(name,{}).get(key)
    def row(name,**kw):
        r={"n":name,"u":kw.get("u","%")}
        for k in ("g","d","gr","am"):
            if k in kw: r[k]=kw[k]
        r["v"]=g(name);
        if g(name,"p") is not None: r["p"]=g(name,"p")
        return r
    def det(key):
        dd=d.get(key,{}).get("v",{})
        return [{"n":k,"v":dd[k]} for k in dd]
    status=[row("Advising — RFD (≤5d)",g=60,d="hi"),row("Advising — ER Confirm (≤5d)",g=70,d="hi"),
            row("Advising — Alt Requested (≤5d)",g=60,d="hi")]
    oa=row("% BO meeting all OA status (≤1d/stg)",g=60,d="hi"); oa["det"]=det("_det_BO_OA"); status.append(oa)
    status+=[row("BYB — Ready Intro (≤3d)",g=80,d="hi"),row("BYB — Implementation (≤5d)",g=80,d="hi")]
    bybt=row("BYB — Transition (≤2d/stg)",g=80,d="hi"); bybt["det"]=det("_det_BYB_TRANS"); status.append(bybt)
    for nm,key in (("BT — Qualification (≤5d)","_det_BT_QUAL"),("BT — Implementation (≤5d)","_det_BT_IMPL"),("BT — Transition (≤2d/stg)","_det_BT_TRANS")):
        rr=row(nm,g=80,d="hi"); rr["det"]=det(key); status.append(rr)
    ready=row("Ready by 1st — next cohort (Renewal)",g=95,d="hi")
    bo=row("Benefit Order — NP+Renewal (≤30d)",g=80,d="hi",gr=80,am=65); bo["det"]=det("_det_BO_E2E")
    e2e=[ready,bo,row("BYB (≤60d)",g=80,d="hi",gr=80,am=65),row("BT (≤35d)",g=80,d="hi",gr=80,am=65)]
    cancel=[row("New Plan (close month)",g=15,d="lo"),row("BYB (close month)",g=15,d="lo"),row("BT (close month)",g=10,d="lo")]
    ticket=[row("Ful→OA — New Plan",g=1.2,d="lo",u="r"),row("Ful→OA — Renewal",g=0.37,d="lo",u="r"),row("OA→Advising — Renewal",g=0.3,d="lo",u="r")]
    # Ticket SLA — % closed within 5 days (dashboard editable target = 5d). Goal 80% is PROVISIONAL
    # (no official % attainment target defined on the Ticket SLA dashboard).
    ticketsla=[row("Ful→OA — Ticket SLA (≤5d)",g=80,d="hi",am=70),row("OA→Advising — Ticket SLA (≤5d)",g=80,d="hi",am=70)]
    have_tsla=any(v is not None for v in (ticketsla[0].get("v") or []))
    av=row("Org — Phone availability (80–105%)",g=80,d="hi"); av["det"]=det("_det_AVAIL")
    ab=row("Org — Abandon rate (overall)",g=30,d="lo"); ab["det"]=det("_det_ABANDON")
    avail=[av,ab,row("Org — Email SLO (≤4h) ★",g=90,d="hi")]
    csat=[row("Renewal CSAT",g=4.0,d="hi",u="s"),row("New Benefits CSAT",g=4.25,d="hi",u="s"),row("In-App Sentiment survey",g=4.0,d="hi",u="s"),row("BYB CSAT",g=4.25,d="hi",u="s"),row("BT CSAT",g=4.25,d="hi",u="s")]
    # Advising Net MRR — Retention % ONLY (no $ per Aman). Target 100 / cliff 94 → gr=100, am=94.
    netmrr=[row("Advising — Net MRR Retention %",g=100,d="hi",gr=100,am=94)]
    have_netmrr=any(v is not None for v in (netmrr[0].get("v") or []))
    CATS=[{"c":"Status SLAs","rows":status},{"c":"Overall SLAs — E2E","rows":e2e},
          {"c":"Cancel Rate","rows":cancel},{"c":"Ticket Rate","rows":ticket}]
    if have_tsla: CATS.append({"c":"Ticket SLA (≤5d)","rows":ticketsla})
    CATS+=[{"c":"Availability / Response","rows":avail},
           {"c":"CSAT / In-App Sentiment  ·  avg score (1–5)","rows":csat}]
    if have_netmrr: CATS.append({"c":"Advising Net MRR","rows":netmrr})
    # chart list M: headline rows (with category tag) + detail sub-series as own groups
    M=[]
    def push(cat,r): M.append({**{k:r[k] for k in r if k not in ("det",)},"c":cat})
    for r in status: push("Status SLAs",r)
    for r in e2e: push("Overall E2E",r)
    for r in cancel: push("Cancel Rate",r)
    for r in ticket: push("Ticket Rate",r)
    if have_tsla:
        for r in ticketsla: push("Ticket SLA (≤5d)",r)
    for r in avail: push("Avail / Response",r)
    for r in csat: push("CSAT / Sentiment · avg (1–5)",r)
    if have_netmrr:
        for r in netmrr: push("Advising Net MRR",r)
    # sub-series groups for the picker
    subgroups=[("BO OA · sub-status","_det_BO_OA",60,"hi"),("Benefit Order E2E · split","_det_BO_E2E",80,"hi"),
               ("BYB Transition · sub-status","_det_BYB_TRANS",80,"hi"),("BT Qualification · sub-status","_det_BT_QUAL",80,"hi"),
               ("BT Implementation · sub-status","_det_BT_IMPL",80,"hi"),("BT Transition · sub-status","_det_BT_TRANS",80,"hi"),
               ("Phone availability · team","_det_AVAIL",80,"hi"),("Phone abandon · team","_det_ABANDON",30,"lo")]
    for cat,key,gg,dd in subgroups:
        block=d.get(key,{}).get("v",{})
        for lbl in block:
            M.append({"c":cat,"n":lbl,"g":gg,"d":dd,"u":"%","v":block[lbl]})
    json.dump({"MO":MO_LABELS,"CATS":CATS,"M":M}, open(os.path.join(HERE,"scorecard_data.json"),"w"), ensure_ascii=False)
    print("wrote scorecard_data.json  (%d cats, %d chart metrics)"%(len(CATS),len(M)))

def run_part(name):
    d=load_parts(); d.update(PARTMAP[name]()); save_parts(d); print("part",name,"done")

if __name__=="__main__":
    arg=sys.argv[1] if len(sys.argv)>1 else None
    if arg in PARTMAP: run_part(arg)
    elif arg=="assemble": assemble()
    else:
        if os.path.exists(PARTS): os.remove(PARTS)
        for p in PARTMAP: run_part(p)
        assemble()
