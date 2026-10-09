#!/usr/bin/env python3
"""PE-level (leadership-layer) scorecard compute.

Same metric definitions as scorecard_team_compute.py, but every metric is keyed by the
IC's CURRENT leadership (PEPE) bucket instead of team. Buckets = Aman's directs:
  Micah Sanchez / Lynne Petre (Benefits Advising),
  Lee Ann Volosin / Aman Bhatia (NP&R Onboarding — Aman = ex-Rehana leads Adrienne/Kelly/Alex/Brooke),
  Martin Ribas (BYB + BT).
The reorg (Adrienne/Kelly/Alex/Brooke -> Aman) is already reflected in OWNER_PEPE_CURRENT.

Owned-work metrics key off the source's PEPE field directly.
Phone & email key off a name/email/agent -> current-PEPE resolver (rosters + owned-work),
so each IC rolls to their current PE. Unmapped rows go to an "Unmapped" bucket; coverage reported.

Output: scorecard_pe_data.json. Usage: python3 scorecard_pe_compute.py --through YYYY-MM [--start YYYY-MM]
"""
import os,sys,json,csv,io,gzip,base64,re,glob
from collections import Counter,defaultdict
csv.field_size_limit(10**7)
HERE=os.path.dirname(os.path.abspath(__file__)); Q=os.path.join(HERE,"queries")

def _arg(f,d=None):
    a=sys.argv; return a[a.index(f)+1] if f in a else d
THROUGH=_arg("--through")
if not THROUGH: raise SystemExit("need --through YYYY-MM")
_ty,_tm=int(THROUGH[:4]),int(THROUGH[5:7]); _fy=_ty if _tm>=5 else _ty-1
START=_arg("--start","%04d-11"%(_fy-1))
def mrange(a,b):
    y,m=int(a[:4]),int(a[5:7]); out=[]
    while "%04d-%02d"%(y,m)<=b:
        out.append("%04d-%02d"%(y,m)); m+=1
        if m==13:y+=1;m=1
    return out
MONTHS=mrange(START,THROUGH); NM=len(MONTHS); MIDX={m:i for i,m in enumerate(MONTHS)}

def flg(x):
    s=(x or "").strip().lower(); return 1 if s in("1","1.0","true") else (0 if s in("0","0.0","false") else None)
def num(x):
    s=(x or "").strip()
    try:return float(s)
    except:return None
def nz(x):
    v=num(x);return v if v is not None else 0.0
def mo(x):
    s=(x or "").strip();return s[:7] if len(s)>=7 else None
def rows(p):
    with open(p,newline="",encoding="utf-8",errors="replace") as f:
        for r in csv.DictReader(f): yield r
def newest(pat):
    g=sorted(glob.glob(os.path.join(Q,pat)));return g[-1] if g else None
def norm(n): return re.sub(r'\s+',' ',(n or '').strip()).lower()
def collapse(n): return re.sub(r'[^a-z]','',(n or '').lower())

# ---- PE buckets ----
PES=["Micah Sanchez","Lynne Petre","Lee Ann Volosin","Aman Bhatia","Martin Ribas"]
PETEAM={"Micah Sanchez":"Benefits Advising","Lynne Petre":"Benefits Advising",
        "Lee Ann Volosin":"NP&R Onboarding","Aman Bhatia":"NP&R Onboarding","Martin Ribas":"BYB & BT Onboarding"}
def canon_pe(p):
    p=(p or "").strip()
    return p if p in PES else None

# ---- build resolver maps (lead->pepe, name->pepe, agent->pepe, email->pepe) ----
def build_maps():
    lead2=defaultdict(Counter)
    srcs=[("queries/advising_opp_data_latest.csv","PE_NAME","PEPE_NAME","CLOSE_DATE_COMPUTED"),
          ("bo_sla_v11_clean.csv","OWNER_PE_NAME_CURRENT","OWNER_PEPE_CURRENT","FIRST_END_MONTH"),
          (newest("byb_data_2024-01-01_to_*.csv"),"OWNER_PE_NAME_CURRENT","OWNER_PEPE_CURRENT","FIRST_END_MONTH"),
          (newest("bt_data_2024-01-01_to_*.csv"),"OWNER_PE_NAME_CURRENT","OWNER_PEPE_CURRENT","FIRST_END_MONTH")]
    for p,pe,pp,dt in srcs:
        for r in rows(p if os.path.isabs(p) else os.path.join(HERE,p)):
            if (r.get(dt) or '')[:10] < '2026-05-01': continue
            L=(r.get(pe) or '').strip(); P=canon_pe(r.get(pp))
            if L and P: lead2[L][P]+=1
    lead2pepe={L:c.most_common(1)[0][0] for L,c in lead2.items()}
    for t in PES: lead2pepe[t]=t
    name2={}; namec={}
    def addn(nm,pp):
        if nm and pp: name2[norm(nm)]=pp; namec[collapse(nm)]=pp
    for p,own,pp,dt in [("queries/advising_opp_data_latest.csv","OWNER_NAME","PEPE_NAME","CLOSE_DATE_COMPUTED"),
          ("bo_sla_v11_clean.csv","BENEFIT_ORDER_OWNER","OWNER_PEPE_CURRENT","FIRST_END_MONTH"),
          (newest("byb_data_2024-01-01_to_*.csv"),"BENEFIT_ORDER_OWNER","OWNER_PEPE_CURRENT","FIRST_END_MONTH"),
          (newest("bt_data_2024-01-01_to_*.csv"),"BENEFIT_ORDER_OWNER","OWNER_PEPE_CURRENT","FIRST_END_MONTH")]:
        for r in rows(p if os.path.isabs(p) else os.path.join(HERE,p)):
            if (r.get(dt) or '')[:10] < '2026-05-01': continue
            addn(r.get(own),canon_pe(r.get(pp)))
    agent2={}
    for r in rows(os.path.join(HERE,"_data_v2","roster_calls.csv")):
        pp=lead2pepe.get((r.get("LAST_PE") or '').strip())
        if pp:
            agent2[(r.get("AGENT_ID") or '').strip()]=pp; addn(r.get("NAME"),pp)
    email2={}
    try:
        for e in json.load(open(os.path.join(HERE,"oa_dash","data","roster.json"))):
            pp=lead2pepe.get((e.get("MANAGER") or '').strip())
            if pp:
                if e.get("EMAIL"): email2[e["EMAIL"].strip().lower()]=pp
                addn(e.get("NAME"),pp)
    except Exception: pass
    return lead2pepe,name2,namec,agent2,email2
LEAD2,NAME2,NAMEC,AGENT2,EMAIL2=build_maps()
def en(em):
    lp=(em or '').split('@')[0].lower(); lp=re.sub(r'\d+$','',lp)
    toks=[t for t in re.split(r'[._]+',lp) if t]
    toks=[t for t in toks if len(t)>1]  # drop middle initials
    return " ".join(toks)
def email_pe(em):
    em=(em or '').strip().lower()
    return EMAIL2.get(em) or NAME2.get(en(em)) or NAMEC.get(collapse(en(em)))
def name_pe(nm):
    return NAME2.get(norm(nm)) or NAMEC.get(collapse(nm))

# ---- per-PE accumulators ----
def acc(): return {pe:[[0.0,0.0] for _ in MONTHS] for pe in PES+["Unmapped"]}
def add(a,pe,m,den,nmr):
    if pe is None: pe="Unmapped"
    if pe not in a: return
    i=MIDX[m]; a[pe][i][1]+=den; a[pe][i][0]+=nmr
COV={}

# ============ OWNED-WORK METRICS ============
def do_adv():
    out={"RFD":acc(),"ER":acc(),"ALT":acc()}
    for r in rows(os.path.join(Q,"advising_opp_data_latest.csv")):
        m=mo(r.get("CLOSE_DATE_COMPUTED_MONTH"))
        if m not in MIDX: continue
        pe=canon_pe(r.get("PEPE_NAME"))
        for key,col in (("RFD","RDP_SLO_MET"),("ER","ER_SLO_MET"),("ALT","ALT_SLO_MET")):
            v=flg(r.get(col))
            if v is not None: add(out[key],pe,m,1,v)
    return out

def do_bo():
    oa=acc(); e2e=acc(); e2np=acc(); e2ren=acc(); npc=acc(); trnp=acc(); trren=acc(); oaadv=acc()
    oecol={"OE Prep":"SLA_READY_OE_PREP_MET","OE Verif":"SLA_OE_VERIF_MET","ER Outreach":"SLA_ER_OUTREACH_MET","Await Routing":"SLA_AWAIT_ROUTING_MET","Approved":"SLA_APPROVED_MET"}
    oa_subs={k:acc() for k in oecol}
    for r in rows(os.path.join(HERE,"bo_sla_v11_clean.csv")):
        rt=(r.get("RECORD_TYPE_NAME") or "").strip(); m=mo(r.get("FIRST_END_MONTH"))
        if m not in MIDX: continue
        pe=canon_pe(r.get("OWNER_PEPE_CURRENT"))
        npren=rt in("New Plan","Renewal")
        if npren:
            v=flg(r.get("SLA_BUCKET_WITH_OA_MET")); e=flg(r.get("FULFILLED_IN_30D_MET"))
            if v is not None: add(oa,pe,m,1,v)
            if e is not None:
                add(e2e,pe,m,1,e)
                add(e2np if rt=="New Plan" else e2ren,pe,m,1,e)
            for lbl,col in oecol.items():
                fv=flg(r.get(col))
                if fv is not None: add(oa_subs[lbl],pe,m,1,fv)
        if rt=="New Plan":
            c=flg(r.get("CANCEL_FLAG"))
            if c is not None: add(npc,pe,m,1,c)
        if str(r.get("FIRST_FULFILLED_TS_MT") or "").strip():
            t=num(r.get("TICKETS_BO_OA_MAPPED"))
            if t is not None:
                if rt=="New Plan": add(trnp,pe,m,1,t)
                elif rt=="Renewal": add(trren,pe,m,1,t)
            if rt=="Renewal":
                adv_pe=canon_pe(r.get("RENEWAL_ADV_OPP_OWNER_PEPE_AT_CLOSE"))
                ta=num(r.get("TICKETS_TBL_OA_TO_BENADV")) or 0.0
                add(oaadv,adv_pe,m,1,ta)
    return {"OA":oa,"E2E":e2e,"E2NP":e2np,"E2REN":e2ren,"NPC":npc,"TRNP":trnp,"TRREN":trren,"OAADV":oaadv,"OA_SUBS":oa_subs}

def do_byb():
    path=newest("byb_data_2024-01-01_to_*.csv")
    ri=acc(); im=acc(); tr=acc(); e2=acc(); cn=acc()
    subcols=[("Ready Impl Plans","READY_IMPL_PLANS_SLA_MET"),("Plans Confirmed","PLANS_CONFIRMED_SLA_MET"),
             ("OE Verif","OE_VERIF_SLA_MET"),("OE Submission","OE_SUBMISSION_SLA_MET"),("Fulfillment Prep","FULFILLMENT_PREP_SLA_MET")]
    subs={l:acc() for l,_ in subcols}
    for r in rows(path):
        m=mo(r.get("FIRST_END_MONTH"))
        if m not in MIDX: continue
        pe=canon_pe(r.get("OWNER_PEPE_CURRENT"))
        for col,dcol,a in (("READY_INTRO_SLA_MET_BUCKET","READY_INTRO_TOTAL_DAYS",ri),("IMPLEMENTATION_SLA_MET_BUCKET","IMPLEMENTATION_TOTAL_DAYS",im),("TRANSITION_SLA_MET","TRANSITION_TOTAL_DAYS",tr),("E2E_SLA_MET",None,e2),("CANCEL_FLAG",None,cn)):
            v=flg(r.get(col))
            if dcol and not ((num(r.get(dcol)) or 0)>0): continue
            if v is not None: add(a,pe,m,1,v)
        for l,col in subcols:
            v=flg(r.get(col)); dc=col.replace("_SLA_MET","_DAYS")
            if dc in r and not ((num(r.get(dc)) or 0)>0): continue
            if v is not None: add(subs[l],pe,m,1,v)
    return {"RI":ri,"IM":im,"TR":tr,"E2":e2,"CN":cn,"SUBS":subs}

def do_bt():
    path=newest("bt_data_2024-01-01_to_*.csv")
    ent0=lambda x:(num(x) or 0)>0
    QUAL=["READY_QUALIF_DAYS","QUALIFICATION_DAYS","READY_DOC_COLLECT_DAYS"]
    IP=["READY_IMPL_PLANS_DAYS","IMPL_PLANS_DAYS","READY_PLAN_REVIEW_DAYS"]
    EE=["PLANS_CONFIRMED_DAYS","ENROLL_REVIEW_ENTRY_DAYS","READY_SEND_ENROLL_DAYS"]
    TR=["ENROLL_CONFIRMED_DAYS","BLOCKED_PLAN_REVIEW_DAYS","READY_TADA_DOC_COLLECT_DAYS","UNBLOCK_PLAN_REVIEW_DAYS"]
    qsub=[("Ready for Qualif","READY_QUALIF_SLA_MET"),("Qualification","QUALIFICATION_SLA_MET"),("Ready for Doc Collect","READY_DOC_COLLECT_SLA_MET")]
    isub=[("Ready Impl Plans","READY_IMPL_PLANS_SLA_MET"),("Impl Plans","IMPL_PLANS_SLA_MET"),("Ready Send Plan Review","READY_PLAN_REVIEW_SLA_MET"),("Plans Confirmed","PLANS_CONFIRMED_SLA_MET"),("Enroll Review Entry","ENROLL_REVIEW_ENTRY_SLA_MET"),("Ready Send Enroll Rev","READY_SEND_ENROLL_SLA_MET"),("Impl TAdA Plans","IMPL_TADA_PLANS_SLA_MET")]
    tsub=[("Enroll Confirmed","ENROLL_CONFIRMED_SLA_MET"),("Blocked Plan Review","BLOCKED_PLAN_REVIEW_SLA_MET"),("Ready TAdA Doc Collect","READY_TADA_DOC_COLLECT_SLA_MET"),("Unblock Plan Review","UNBLOCK_PLAN_REVIEW_SLA_MET")]
    q=acc(); i=acc(); t=acc(); e=acc(); c=acc()
    dq={l:acc() for l,_ in qsub}; di={l:acc() for l,_ in isub}; dt={l:acc() for l,_ in tsub}
    for r in rows(path):
        m=mo(r.get("FIRST_END_MONTH"))
        if m not in MIDX: continue
        _dd=num(r.get("DAYS_CREATED_TO_FIRST_FULFILLED"))
        if _dd is not None and _dd>1000: continue
        pe=canon_pe(r.get("OWNER_PEPE_CURRENT"))
        if any(ent0(r.get(x)) for x in QUAL): add(q,pe,m,1,1 if sum(nz(r.get(x)) for x in QUAL)<=5 else 0)
        ipe=any(ent0(r.get(x)) for x in IP); eee=any(ent0(r.get(x)) for x in EE); tae=ent0(r.get("IMPL_TADA_PLANS_DAYS"))
        if ipe or eee or tae:
            ok=True
            if ipe and sum(nz(r.get(x)) for x in IP)>5: ok=False
            if eee and sum(nz(r.get(x)) for x in EE)>5: ok=False
            if tae and nz(r.get("IMPL_TADA_PLANS_DAYS"))>5: ok=False
            add(i,pe,m,1,1 if ok else 0)
        et=[x for x in TR if ent0(r.get(x))]
        if et: add(t,pe,m,1,1 if all(nz(r.get(x))<=2 for x in et) else 0)
        d=num(r.get("DAYS_CREATED_TO_FIRST_FULFILLED"))
        if d is not None: add(e,pe,m,1,1 if d<=35 else 0)
        cf=flg(r.get("CANCEL_FLAG"))
        if cf is not None: add(c,pe,m,1,cf)
        for grp,cols in ((dq,qsub),(di,isub),(dt,tsub)):
            for l,col in cols:
                fv=flg(r.get(col)); dc=col.replace("_SLA_MET","_DAYS")
                if dc in r and not ent0(r.get(dc)): continue
                if fv is not None: add(grp[l],pe,m,1,fv)
    return {"Q":q,"I":i,"T":t,"E":e,"C":c,"DQ":dq,"DI":di,"DT":dt}

def do_csat():
    TYPES={"Renewed Benefits Feedback":("Renewal CSAT","BO_OWNER_PEPE_NAME"),
           "New Benefits Feedback":("New Benefits CSAT","BO_OWNER_PEPE_NAME"),
           "BYB Onboarding Feedback":("BYB CSAT","BO_OWNER_PEPE_NAME"),
           "Benefits Transfers Feedback":("BT CSAT","BO_OWNER_PEPE_NAME")}
    out={v[0]:acc() for v in TYPES.values()}; out["In-App Sentiment survey"]=acc()
    for r in rows(newest("csat_data_2025-01-01_to_*.csv")):
        t=TYPES.get((r.get("SURVEY_NAME") or "").strip())
        if not t: continue
        m=mo(r.get("SURVEY_SUBMITTED_DATE")); sco=num(r.get("SURVEY_CSAT_SCORE"))
        if m in MIDX and sco is not None:
            pe=canon_pe(r.get(t[1])) or canon_pe(r.get("OPP_OWNER_PEPE_NAME"))
            add(out[t[0]],pe,m,1,sco)
    for r in rows(newest("inapp_data_2025-01-01_to_*.csv")):
        m=mo(r.get("SURVEY_DATE")); sco=num(r.get("RATING"))
        if m in MIDX and sco is not None:
            pe=canon_pe(r.get("OPPORTUNITY_OWNER_PEPE_NAME"))
            add(out["In-App Sentiment survey"],pe,m,1,sco)
    return out

def do_mrr():
    path=sorted(glob.glob(os.path.join(HERE,"advising_mrr_cohort*.csv")))[-1]
    RES={"Closed Won","Closed Lost","Order Lost"}
    won={pe:[0.0]*NM for pe in PES+["Unmapped"]}; chn={pe:[0.0]*NM for pe in PES+["Unmapped"]}; stk={pe:[0.0]*NM for pe in PES+["Unmapped"]}
    for r in rows(path):
        st=(r.get("STATUS") or "").strip()
        if st not in RES: continue
        m=mo(r.get("INFERRED_CLOSE_DATE"))
        if m not in MIDX: continue
        pe=LEAD2.get((r.get("PE") or "").strip()); pe=pe if pe in PES else "Unmapped"
        i=MIDX[m]; b=nz(r.get("MRR_TOTAL_BEFORE")); a=nz(r.get("MRR_TOTAL_AFTER"))
        stk[pe][i]+=b
        if st=="Closed Won": won[pe][i]+=(a-b)
        else: chn[pe][i]+=b
    # store as [stake+net, stake] so render computes pct like team view (p1)
    out={pe:[[stk[pe][i]+won[pe][i]-chn[pe][i], stk[pe][i]] for i in range(NM)] for pe in PES+["Unmapped"]}
    return out, os.path.basename(path)

# ============ PHONE & EMAIL (IC -> current PE) ============
def do_phone():
    av=acc(); ab=acc(); cov_a=[0,0]; cov_b=[0,0]
    for r in rows(os.path.join(HERE,"_data_v2","av_pit.csv")):
        m=mo(r.get("REPORTED_DATE"))
        if m not in MIDX: continue
        v=flg(r.get("SLA"))
        if v is None: continue
        pe=email_pe(r.get("EMAIL")); cov_a[1]+=1; cov_a[0]+= 1 if pe else 0
        add(av,pe,m,1,v)
    for r in rows(os.path.join(HERE,"_data_v2","calls_pit.csv")):
        m=mo(r.get("CALL_DATE"))
        if m not in MIDX: continue
        inb=num(r.get("INBOUND_CT")); abd=num(r.get("ABANDONED_CT"))
        pe=AGENT2.get((r.get("AGENT_ID") or '').strip())
        if inb: cov_b[1]+=inb; cov_b[0]+= inb if pe else 0
        if inb is not None or abd is not None:
            add(ab,pe,m,(inb or 0),(abd or 0))
    COV["availability"]=round(100*cov_a[0]/cov_a[1],1) if cov_a[1] else None
    COV["abandon"]=round(100*cov_b[0]/cov_b[1],1) if cov_b[1] else None
    return av,ab

def do_email():
    html=open(os.path.join(HERE,"email-sla-dashboard-v10.html"),encoding="utf-8",errors="replace").read()
    s=html.find(">",html.find('id="__EMBED__"'))+1; e=html.find("</",s)
    raw=gzip.decompress(base64.b64decode(html[s:e].strip())).decode("utf-8",errors="replace")
    em=acc(); cov=[0,0]
    for r in csv.DictReader(io.StringIO(raw)):
        m=mo(r.get("TOUCHPOINT_START_TS_MT"))
        if m not in MIDX: continue
        st=(r.get("INBOUND_EMAIL_RESPONSE_STATUS") or "")
        if "Within SLA" not in st and "Past SLA" not in st: continue
        pe=name_pe(r.get("CASE_OWNER_NAME_AT_TP")); cov[1]+=1; cov[0]+= 1 if pe else 0
        add(em,pe,m,1,1 if "Within SLA" in st else 0)
    COV["email"]=round(100*cov[0]/cov[1],1) if cov[1] else None
    return em

# ============ ASSEMBLE ============
def do_ticketsla():
    from datetime import datetime
    foa=acc(); oaadv=acc()
    path=os.path.join(HERE,"ticket_sla_by_flow_v12.html")
    if not os.path.exists(path):
        COV["ticket_foa"]=None; COV["ticket_oaadv"]=None; return {"FOA":foa,"OAADV_SLA":oaadv}
    html=open(path,encoding="utf-8",errors="replace").read()
    si=html.find(">",html.find('id="__EMBED__"'))+1; ei=html.find("</",si); raw=html[si:ei]
    def pts(x):
        x=(x or "").strip()
        for f in ("%Y-%m-%dT%H:%M:%S","%Y-%m-%d %H:%M:%S","%Y-%m-%d"):
            try: return datetime.strptime(x[:19],f)
            except: pass
        return None
    cf=[0,0]; ca=[0,0]
    for r in csv.DictReader(io.StringIO(raw)):
        ct=pts(r.get("TICKET_CLOSED_TS_MT")); cr=pts(r.get("TICKET_CREATED_TS_MT"))
        if not ct or not cr: continue
        m="%04d-%02d"%(ct.year,ct.month)
        if m not in MIDX: continue
        within=1 if (ct-cr).total_seconds()/86400.0<=5 else 0
        if r.get("TICKET_REPORTING_TEAM")=="Fulfillment" and r.get("HAS_OA_TOUCH")=="true":
            pe=name_pe(r.get("BENEFIT_ORDER_OWNER")); cf[1]+=1; cf[0]+= 1 if pe else 0
            add(foa,pe,m,1,within)
        elif r.get("TICKET_REPORTING_TEAM")=="Implementation Advocate" and r.get("TICKET_TEAM")=="Benefits Advising" and r.get("IS_OPEN")!="true":
            pe=name_pe(r.get("TICKET_OWNER_NAME")); ca[1]+=1; ca[0]+= 1 if pe else 0
            add(oaadv,pe,m,1,within)
    COV["ticket_foa"]=round(100*cf[0]/cf[1],1) if cf[1] else None
    COV["ticket_oaadv"]=round(100*ca[0]/ca[1],1) if ca[1] else None
    return {"FOA":foa,"OAADV_SLA":oaadv}

def fq(m):
    y,mm=int(m[:4]),int(m[5:7]); idx=(mm-5)%12; q=idx//3+1; fy=y+1 if mm>=5 else y
    return "Q%d FY%02d"%(q,fy%100)

def main():
    A=do_adv(); B=do_bo(); Y=do_byb(); T=do_bt(); C=do_csat(); MRR,mrrfile=do_mrr(); AV,AB=do_phone(); EM=do_email(); TK=do_ticketsla()
    def det(d): return [{"n":l,"c":d[l]} for l in d]
    # row builder: pick this PE's series from an accumulator
    def R(n,a,k,g,dirn,sec,gr=None,am=None,detmap=None):
        return {"n":n,"a":a,"k":k,"g":g,"d":dirn,"sec":sec,"gr":gr,"am":am,"det":detmap}
    # metric catalog per team; each entry references an accumulator dict (pe->series)
    ADV=[R("Advising — RFD (≤5d)",A["RFD"],"p",60,"hi","Status SLAs"),
         R("Advising — ER Confirm (≤5d)",A["ER"],"p",70,"hi","Status SLAs"),
         R("Advising — Alt Requested (≤5d)",A["ALT"],"p",60,"hi","Status SLAs"),
         R("OA→Advising ticket rate (Renewal)",B["OAADV"],"r",0.3,"lo","Tickets"),
         R("OA→Advising Ticket SLA (≤5d) †",TK["OAADV_SLA"],"p",80,"hi","Tickets",am=70),
         R("Phone availability (80–105%)",AV,"p",80,"hi","Phone & email"),
         R("Phone abandon rate",AB,"p",30,"lo","Phone & email"),
         R("Email SLO (≤4h)",EM,"p",90,"hi","Phone & email"),
         R("In-App Sentiment survey (avg 1–5)",C["In-App Sentiment survey"],"s",4.0,"hi","Customer experience"),
         R("Net MRR Retention %",MRR,"p1",100,"hi","Revenue retention",gr=100,am=94)]
    NPR=[R("% BO meeting all OA status (≤1d/stg)",B["OA"],"p",60,"hi","Status SLAs",detmap=B["OA_SUBS"]),
         R("Benefit Order NP+Renewal (≤30d)",B["E2E"],"p",80,"hi","Overall SLAs (E2E)",gr=80,am=65,detmap={"New Plan":B["E2NP"],"Renewal":B["E2REN"]}),
         R("Ful→OA ticket rate — New Plan",B["TRNP"],"r",1.2,"lo","Tickets"),
         R("Ful→OA ticket rate — Renewal",B["TRREN"],"r",0.37,"lo","Tickets"),
         R("Ful→OA Ticket SLA (≤5d) †",TK["FOA"],"p",80,"hi","Tickets",am=70),
         R("New Plan cancel rate (close month)",B["NPC"],"p",15,"lo","Cancel rate"),
         R("Renewal CSAT (avg 1–5)",C["Renewal CSAT"],"s",4.0,"hi","Customer experience"),
         R("New Benefits CSAT (avg 1–5)",C["New Benefits CSAT"],"s",4.25,"hi","Customer experience"),
         R("Phone availability (80–105%)",AV,"p",80,"hi","Phone & email"),
         R("Phone abandon rate",AB,"p",30,"lo","Phone & email"),
         R("Email SLO (≤4h)",EM,"p",90,"hi","Phone & email")]
    BYBT=[R("BYB — Ready Intro (≤3d)",Y["RI"],"p",80,"hi","BYB status"),
          R("BYB — Implementation (≤5d)",Y["IM"],"p",80,"hi","BYB status"),
          R("BYB — Transition (≤2d/stg)",Y["TR"],"p",80,"hi","BYB status",detmap=Y["SUBS"]),
          R("BYB E2E (≤60d)",Y["E2"],"p",80,"hi","BYB overall",gr=80,am=65),
          R("BYB cancel rate (close month)",Y["CN"],"p",15,"lo","BYB cancel"),
          R("BYB CSAT (avg 1–5)",C["BYB CSAT"],"s",4.25,"hi","BYB CX"),
          R("BT — Qualification (≤5d)",T["Q"],"p",80,"hi","BT status",detmap=T["DQ"]),
          R("BT — Implementation (≤5d)",T["I"],"p",80,"hi","BT status",detmap=T["DI"]),
          R("BT — Transition (≤2d/stg)",T["T"],"p",80,"hi","BT status",detmap=T["DT"]),
          R("BT E2E (≤35d)",T["E"],"p",80,"hi","BT overall",gr=80,am=65),
          R("BT cancel rate (close month)",T["C"],"p",10,"lo","BT cancel"),
          R("BT CSAT (avg 1–5)",C["BT CSAT"],"s",4.25,"hi","BT CX"),
          R("Phone availability (80–105%)",AV,"p",80,"hi","Phone & email"),
          R("Phone abandon rate",AB,"p",30,"lo","Phone & email"),
          R("Email SLO (≤4h)",EM,"p",90,"hi","Phone & email")]
    CAT={"Micah Sanchez":ADV,"Lynne Petre":ADV,"Lee Ann Volosin":NPR,"Aman Bhatia":NPR,"Martin Ribas":BYBT}
    def serialize(pe,cat):
        out=[]
        for m in cat:
            a=m["a"]; c=a.get(pe,[[0.0,0.0]]*NM)
            row={"n":m["n"],"k":m["k"],"g":m["g"],"d":m["d"],"sec":m["sec"],"c":c}
            if m["gr"] is not None: row["gr"]=m["gr"]
            if m["am"] is not None: row["am"]=m["am"]
            if m["det"]:
                row["det"]=[{"n":l,"c":m["det"][l].get(pe,[[0.0,0.0]]*NM)} for l in m["det"]]
            out.append(row)
        return out
    pes=[{"name":pe,"team":PETEAM[pe],"rows":serialize(pe,CAT[pe])} for pe in PES]
    # quarters
    names=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    ml=[names[int(m[5:7])-1]+" '"+m[2:4] for m in MONTHS]
    qs=[]
    for i,m in enumerate(MONTHS):
        q=fq(m)
        if not qs or qs[-1]["id"]!=q: qs.append({"id":q,"idx":[]})
        qs[-1]["idx"].append(i)
    for q in qs: q["partial"]=len(q["idx"])<3
    json.dump({"months":MONTHS,"ml":ml,"quarters":qs,"pes":pes,"coverage":COV,
               "mrrfile":mrrfile,"through":THROUGH,"start":START},
              open(os.path.join(HERE,"scorecard_pe_data.json"),"w"),ensure_ascii=False)
    print("wrote scorecard_pe_data.json | PEs:",[p["name"] for p in pes],"| coverage",COV,"| quarters",[q["id"] for q in qs])
main()
