#!/usr/bin/env python3
"""IC-level scorecard — metrics keyed by the benefit-order / opp OWNER (the IC),
grouped IC → PE (team lead = OWNER_PE_NAME_CURRENT) → leader (PEPE = OWNER_PEPE_CURRENT).
THIS QUARTER ONLY (Q2 FY27 = Aug–Oct 2026) QTD. Owned-work keys off the record owner;
phone/email attach to each IC by name/email/agent. Output: scorecard_ic_data.json.
Usage: python3 scorecard_ic_compute.py [--window 2026-08,2026-09,2026-10]"""
import os,sys,json,csv,io,gzip,base64,re,glob
from collections import defaultdict,Counter
csv.field_size_limit(10**7)
HERE=os.path.dirname(os.path.abspath(__file__)); Q=os.path.join(HERE,"queries")
WIN=["2026-08","2026-09","2026-10"]
if "--window" in sys.argv: WIN=sys.argv[sys.argv.index("--window")+1].split(",")
WS=set(WIN)
LEADERS=["Micah Sanchez","Lynne Petre","Lee Ann Volosin","Aman Bhatia","Martin Ribas"]
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

# ---- IC identity: owner name -> (display, pe, leader). Built from owned-work current fields ----
IC={}        # norm(name) -> {"disp","pe","leader"}
NAME2=set()  # norm names
def reg(nm,pe,leader):
    nm=(nm or "").strip()
    if not nm or leader not in LEADERS: return
    k=norm(nm)
    if k not in IC: IC[k]={"disp":nm,"pe":(pe or "").strip(),"leader":leader}; NAME2.add(k)
SRC=[("queries/advising_opp_data_latest.csv","OWNER_NAME","PE_NAME","PEPE_NAME","CLOSE_DATE_COMPUTED"),
     ("bo_sla_v11_clean.csv","BENEFIT_ORDER_OWNER","OWNER_PE_NAME_CURRENT","OWNER_PEPE_CURRENT","FIRST_END_MONTH"),
     (newest("byb_data_2024-01-01_to_*.csv"),"BENEFIT_ORDER_OWNER","OWNER_PE_NAME_CURRENT","OWNER_PEPE_CURRENT","FIRST_END_MONTH"),
     (newest("bt_data_2024-01-01_to_*.csv"),"BENEFIT_ORDER_OWNER","OWNER_PE_NAME_CURRENT","OWNER_PEPE_CURRENT","FIRST_END_MONTH")]
for p,own,pe,pp,dt in SRC:
    pth=p if os.path.isabs(p) else os.path.join(HERE,p)
    for r in rows(pth):
        if mo(r.get(dt)) in WS: reg(r.get(own),r.get(pe),(r.get(pp) or '').strip())
def cic(nm):
    k=norm(nm); return k if k in IC else None

# phone/email resolvers -> IC key
AGENT2=None; EMAIL2={}
def build_resolvers():
    global AGENT2
    AGENT2={}
    for r in rows(os.path.join(HERE,"_data_v2","roster_calls.csv")):
        k=norm(r.get("NAME"))
        if k in IC: AGENT2[(r.get("AGENT_ID") or '').strip()]=k
    try:
        for e in json.load(open(os.path.join(HERE,"oa_dash","data","roster.json"))):
            k=norm(e.get("NAME"))
            if k in IC and e.get("EMAIL"): EMAIL2[e["EMAIL"].strip().lower()]=k
    except Exception: pass
    # collapsed-name index for email localpart fallback
    global COLL
    COLL={collapse(IC[k]["disp"]):k for k in IC}
build_resolvers()
def email_ic(em):
    em=(em or '').strip().lower()
    if em in EMAIL2: return EMAIL2[em]
    lp=em.split('@')[0]; lp=re.sub(r'\d+$','',lp); toks=[t for t in re.split(r'[._]+',lp) if len(t)>1]
    return COLL.get(collapse(" ".join(toks)))

def acc(): return defaultdict(lambda:[0.0,0.0])
def add(a,k,den,nmr):
    if k is None: return
    a[k][0]+=nmr; a[k][1]+=den

# ============ metrics (Q2 only), keyed by IC ============
M={}  # metric_key -> accumulator dict IC->[num,den]
def do():
    adv={"RFD":acc(),"ER":acc(),"ALT":acc()}
    for r in rows(os.path.join(Q,"advising_opp_data_latest.csv")):
        if mo(r.get("CLOSE_DATE_COMPUTED_MONTH")) not in WS: continue
        k=cic(r.get("OWNER_NAME"))
        for key,col in (("RFD","RDP_SLO_MET"),("ER","ER_SLO_MET"),("ALT","ALT_SLO_MET")):
            v=flg(r.get(col))
            if v is not None: add(adv[key],k,1,v)
    M.update({"Advising — RFD (≤5d)":adv["RFD"],"Advising — ER Confirm (≤5d)":adv["ER"],"Advising — Alt Requested (≤5d)":adv["ALT"]})
    oa=acc(); e2e=acc(); npc=acc(); trnp=acc(); trren=acc()
    for r in rows(os.path.join(HERE,"bo_sla_v11_clean.csv")):
        if mo(r.get("FIRST_END_MONTH")) not in WS: continue
        rt=(r.get("RECORD_TYPE_NAME") or '').strip(); k=cic(r.get("BENEFIT_ORDER_OWNER"))
        if rt in("New Plan","Renewal"):
            v=flg(r.get("SLA_BUCKET_WITH_OA_MET")); e=flg(r.get("FULFILLED_IN_30D_MET"))
            if v is not None: add(oa,k,1,v)
            if e is not None: add(e2e,k,1,e)
        if rt=="New Plan":
            c=flg(r.get("CANCEL_FLAG"))
            if c is not None: add(npc,k,1,c)
        if str(r.get("FIRST_FULFILLED_TS_MT") or '').strip():
            t=num(r.get("TICKETS_BO_OA_MAPPED"))
            if t is not None:
                if rt=="New Plan": add(trnp,k,1,t)
                elif rt=="Renewal": add(trren,k,1,t)
    M.update({"% BO all-OA (≤1d/stg)":oa,"Benefit Order ≤30d":e2e,"New Plan cancel":npc,
              "Ful→OA rate — New Plan":trnp,"Ful→OA rate — Renewal":trren})
    # BYB
    ri=acc();im=acc();tr=acc();be=acc();bc=acc()
    for r in rows(newest("byb_data_2024-01-01_to_*.csv")):
        if mo(r.get("FIRST_END_MONTH")) not in WS: continue
        k=cic(r.get("BENEFIT_ORDER_OWNER"))
        for col,dcol,a in (("READY_INTRO_SLA_MET_BUCKET","READY_INTRO_TOTAL_DAYS",ri),("IMPLEMENTATION_SLA_MET_BUCKET","IMPLEMENTATION_TOTAL_DAYS",im),("TRANSITION_SLA_MET","TRANSITION_TOTAL_DAYS",tr),("E2E_SLA_MET",None,be),("CANCEL_FLAG",None,bc)):
            v=flg(r.get(col))
            if dcol and not ((num(r.get(dcol)) or 0)>0): continue
            if v is not None: add(a,k,1,v)
    M.update({"BYB Ready Intro (≤3d)":ri,"BYB Implementation (≤5d)":im,"BYB Transition (≤2d)":tr,"BYB E2E (≤60d)":be,"BYB cancel":bc})
    # BT (synthetic)
    ent0=lambda x:(num(x) or 0)>0
    QU=["READY_QUALIF_DAYS","QUALIFICATION_DAYS","READY_DOC_COLLECT_DAYS"]
    IP=["READY_IMPL_PLANS_DAYS","IMPL_PLANS_DAYS","READY_PLAN_REVIEW_DAYS"]
    EE=["PLANS_CONFIRMED_DAYS","ENROLL_REVIEW_ENTRY_DAYS","READY_SEND_ENROLL_DAYS"]
    TR=["ENROLL_CONFIRMED_DAYS","BLOCKED_PLAN_REVIEW_DAYS","READY_TADA_DOC_COLLECT_DAYS","UNBLOCK_PLAN_REVIEW_DAYS"]
    q=acc();i=acc();t=acc();e=acc();c=acc()
    for r in rows(newest("bt_data_2024-01-01_to_*.csv")):
        if mo(r.get("FIRST_END_MONTH")) not in WS: continue
        if (num(r.get("DAYS_CREATED_TO_FIRST_FULFILLED")) or 0)>1000: continue
        k=cic(r.get("BENEFIT_ORDER_OWNER"))
        if any(ent0(r.get(x)) for x in QU): add(q,k,1,1 if sum(nz(r.get(x)) for x in QU)<=5 else 0)
        ipe=any(ent0(r.get(x)) for x in IP); eee=any(ent0(r.get(x)) for x in EE); tae=ent0(r.get("IMPL_TADA_PLANS_DAYS"))
        if ipe or eee or tae:
            ok=True
            if ipe and sum(nz(r.get(x)) for x in IP)>5: ok=False
            if eee and sum(nz(r.get(x)) for x in EE)>5: ok=False
            if tae and nz(r.get("IMPL_TADA_PLANS_DAYS"))>5: ok=False
            add(i,k,1,1 if ok else 0)
        et=[x for x in TR if ent0(r.get(x))]
        if et: add(t,k,1,1 if all(nz(r.get(x))<=2 for x in et) else 0)
        d=num(r.get("DAYS_CREATED_TO_FIRST_FULFILLED"))
        if d is not None: add(e,k,1,1 if d<=35 else 0)
        cf=flg(r.get("CANCEL_FLAG"))
        if cf is not None: add(c,k,1,cf)
    M.update({"BT Qualification (≤5d)":q,"BT Implementation (≤5d)":i,"BT Transition (≤2d)":t,"BT E2E (≤35d)":e,"BT cancel":c})
    # CSAT / In-App / MRR
    TYPES={"Renewed Benefits Feedback":"Renewal CSAT","New Benefits Feedback":"New Benefits CSAT","BYB Onboarding Feedback":"BYB CSAT","Benefits Transfers Feedback":"BT CSAT"}
    cs={v:acc() for v in TYPES.values()}; ia=acc()
    for r in rows(newest("csat_data_2025-01-01_to_*.csv")):
        kk=TYPES.get((r.get("SURVEY_NAME") or '').strip())
        if not kk or mo(r.get("SURVEY_SUBMITTED_DATE")) not in WS: continue
        sco=num(r.get("SURVEY_CSAT_SCORE"))
        if sco is None: continue
        k=cic(r.get("BENEFIT_ORDER_OWNER")) or cic(r.get("OPP_OWNER_NAME"))
        add(cs[kk],k,1,sco)
    for r in rows(newest("inapp_data_2025-01-01_to_*.csv")):
        if mo(r.get("SURVEY_DATE")) not in WS: continue
        sco=num(r.get("RATING"))
        if sco is None: continue
        add(ia,cic(r.get("ADVISING_OPPORTUNITY_OWNER_NAME")) or cic(r.get("OPPORTUNITY_OWNER_NAME")),1,sco)
    M.update({"Renewal CSAT (1–5)":cs["Renewal CSAT"],"New Benefits CSAT (1–5)":cs["New Benefits CSAT"],"BYB CSAT (1–5)":cs["BYB CSAT"],"BT CSAT (1–5)":cs["BT CSAT"],"In-App Sentiment (1–5)":ia})
    mrrp=sorted(glob.glob(os.path.join(HERE,"advising_mrr_cohort*.csv")))[-1]
    won=defaultdict(float);chn=defaultdict(float);stk=defaultdict(float)
    for r in rows(mrrp):
        st=(r.get("STATUS") or '').strip()
        if st not in ("Closed Won","Closed Lost","Order Lost") or mo(r.get("INFERRED_CLOSE_DATE")) not in WS: continue
        k=cic(r.get("OWNER_NAME"))
        if k is None: continue
        b=nz(r.get("MRR_TOTAL_BEFORE")); a=nz(r.get("MRR_TOTAL_AFTER")); stk[k]+=b
        if st=="Closed Won": won[k]+=(a-b)
        else: chn[k]+=b
    mrr=acc()
    for k in stk: mrr[k]=[stk[k]+won[k]-chn[k], stk[k]]
    M["Net MRR Retention %"]=mrr
    # phone + email
    av=acc(); ab=acc()
    for r in rows(os.path.join(HERE,"_data_v2","av_pit.csv")):
        if mo(r.get("REPORTED_DATE")) not in WS: continue
        v=flg(r.get("SLA"))
        if v is None: continue
        add(av,email_ic(r.get("EMAIL")),1,v)
    for r in rows(os.path.join(HERE,"_data_v2","calls_pit.csv")):
        if mo(r.get("CALL_DATE")) not in WS: continue
        inb=num(r.get("INBOUND_CT")); abd=num(r.get("ABANDONED_CT"))
        add(ab,AGENT2.get((r.get("AGENT_ID") or '').strip()),(inb or 0),(abd or 0))
    M["Phone availability (80–105%)"]=av; M["Phone abandon rate"]=ab
    em=acc()
    html=open(os.path.join(HERE,"email-sla-dashboard-v10.html"),encoding="utf-8",errors="replace").read()
    s=html.find(">",html.find('id="__EMBED__"'))+1; e2=html.find("</",s)
    raw=gzip.decompress(base64.b64decode(html[s:e2].strip())).decode("utf-8",errors="replace")
    for r in csv.DictReader(io.StringIO(raw)):
        if mo(r.get("TOUCHPOINT_START_TS_MT")) not in WS: continue
        st=(r.get("INBOUND_EMAIL_RESPONSE_STATUS") or '')
        if "Within SLA" not in st and "Past SLA" not in st: continue
        add(em,cic(r.get("CASE_OWNER_NAME_AT_TP")),1,1 if "Within SLA" in st else 0)
    M["Email SLO (≤4h)"]=em
do()

# ---- metric meta (goal/dir/kind) + which metrics apply per leader-team ----
META={"Advising — RFD (≤5d)":(60,"hi","p"),"Advising — ER Confirm (≤5d)":(70,"hi","p"),"Advising — Alt Requested (≤5d)":(60,"hi","p"),
 "% BO all-OA (≤1d/stg)":(60,"hi","p"),"Benefit Order ≤30d":(80,"hi","p"),"New Plan cancel":(15,"lo","p"),
 "Ful→OA rate — New Plan":(1.2,"lo","r"),"Ful→OA rate — Renewal":(0.37,"lo","r"),
 "BYB Ready Intro (≤3d)":(80,"hi","p"),"BYB Implementation (≤5d)":(80,"hi","p"),"BYB Transition (≤2d)":(80,"hi","p"),"BYB E2E (≤60d)":(80,"hi","p"),"BYB cancel":(15,"lo","p"),
 "BT Qualification (≤5d)":(80,"hi","p"),"BT Implementation (≤5d)":(80,"hi","p"),"BT Transition (≤2d)":(80,"hi","p"),"BT E2E (≤35d)":(80,"hi","p"),"BT cancel":(10,"lo","p"),
 "Renewal CSAT (1–5)":(4.0,"hi","s"),"New Benefits CSAT (1–5)":(4.25,"hi","s"),"BYB CSAT (1–5)":(4.25,"hi","s"),"BT CSAT (1–5)":(4.25,"hi","s"),"In-App Sentiment (1–5)":(4.0,"hi","s"),
 "Net MRR Retention %":(100,"hi","p1"),"Phone availability (80–105%)":(80,"hi","p"),"Phone abandon rate":(30,"lo","p"),"Email SLO (≤4h)":(90,"hi","p")}
ADV=["Advising — RFD (≤5d)","Advising — ER Confirm (≤5d)","Advising — Alt Requested (≤5d)","Phone availability (80–105%)","Phone abandon rate","Email SLO (≤4h)","In-App Sentiment (1–5)","Net MRR Retention %"]
NPR=["% BO all-OA (≤1d/stg)","Benefit Order ≤30d","Ful→OA rate — New Plan","Ful→OA rate — Renewal","New Plan cancel","Renewal CSAT (1–5)","New Benefits CSAT (1–5)","Phone availability (80–105%)","Phone abandon rate","Email SLO (≤4h)"]
BYBT=["BYB Ready Intro (≤3d)","BYB Implementation (≤5d)","BYB Transition (≤2d)","BYB E2E (≤60d)","BYB cancel","BYB CSAT (1–5)","BT Qualification (≤5d)","BT Implementation (≤5d)","BT Transition (≤2d)","BT E2E (≤35d)","BT cancel","BT CSAT (1–5)","Phone availability (80–105%)","Phone abandon rate","Email SLO (≤4h)"]
LEADMETRICS={"Micah Sanchez":ADV,"Lynne Petre":ADV,"Lee Ann Volosin":NPR,"Aman Bhatia":NPR,"Martin Ribas":BYBT}

# ---- assemble: leader -> PE -> ICs, each IC with its metric cells ----
def icvol(k):  # Q2 primary-status volume to order ICs
    tot=0
    for m in LEADMETRICS[IC[k]["leader"]]:
        a=M.get(m,{})
        if k in a: tot+=a[k][1]
    return tot
pes_by_leader=defaultdict(lambda:defaultdict(list))
for k,info in IC.items():
    pes_by_leader[info["leader"]][info["pe"]].append(k)
out=[]
for L in LEADERS:
    mets=LEADMETRICS[L]
    for pe,ics in sorted(pes_by_leader[L].items()):
        ics=[k for k in ics if icvol(k)>0]
        ics.sort(key=lambda k:-icvol(k))
        if not ics: continue
        cols=[]
        for k in ics:
            cells={}
            for m in mets:
                a=M.get(m,{})
                if k in a and a[k][1]: cells[m]=a[k]   # [num,den]
            cols.append({"ic":IC[k]["disp"],"cells":cells})
        out.append({"leader":L,"pe":pe,"metrics":mets,"ics":cols})
rowsmeta=[{"n":m,"g":META[m][0],"d":META[m][1],"k":META[m][2]} for m in META]
json.dump({"window":WIN,"groups":out,"meta":META},open(os.path.join(HERE,"scorecard_ic_data.json"),"w"),ensure_ascii=False)
print("wrote scorecard_ic_data.json | PE groups:",len(out),"| total ICs:",sum(len(g["ics"]) for g in out))
