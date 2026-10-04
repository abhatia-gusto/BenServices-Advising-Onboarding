#!/usr/bin/env python3
"""Team-view scorecard compute: raw [num,den] counts per month (Aug-2025..Sep-2026),
so fiscal quarters (May-Apr FY; FY27 = May-26..Apr-27) aggregate as sum(num)/sum(den), never an
average of monthly percents. Reuses scorecard_compute.py source logic. Output: scorecard_team_data.json"""
import os, sys, json, csv, io, gzip, base64, importlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scorecard_compute as sc
HERE=sc.HERE
# usage: python3 scorecard_team_compute.py --through YYYY-MM [--start YYYY-MM]
# default start = first month of Q3 of the PRIOR fiscal year (FY starts May): e.g. through 2026-09 -> start 2025-11
def _arg(flag,default=None):
    a=sys.argv
    return a[a.index(flag)+1] if flag in a else default
THROUGH=_arg("--through")
if not THROUGH: raise SystemExit("need --through YYYY-MM")
_ty,_tm=int(THROUGH[:4]),int(THROUGH[5:7]); _fy_start=_ty if _tm>=5 else _ty-1
START=_arg("--start","%04d-11"%(_fy_start-1))
def _mrange(a,b):
    y,m=int(a[:4]),int(a[5:7]); out=[]
    while "%04d-%02d"%(y,m)<=b:
        out.append("%04d-%02d"%(y,m)); m+=1
        if m==13: y+=1; m=1
    return out
MONTHS=_mrange(START,THROUGH)
sc.CUR_MONTHS=MONTHS; sc.PRIOR_MONTHS=[]
sc.pct=lambda a,months:[[a[m][0],a[m][1]] for m in months]
sc.rate=sc.pct
NM=len(MONTHS)

def fq(m):
    y,mm=int(m[:4]),int(m[5:7]); idx=(mm-5)%12; q=idx//3+1; fy=y+1 if mm>=5 else y
    return "Q%d FY%02d"%(q,fy%100)

def section(n):
    if n.startswith(("Advising —","% BO","Ready Intro","Implementation","Transition","Qualification")): return "Status SLAs"
    if n.startswith(("Ready by 1st","Benefit Order","BYB E2E","BT E2E")): return "Overall SLAs (E2E)"
    if "cancel" in n: return "Cancel rate"
    if "ticket" in n.lower(): return "Tickets"
    if n.startswith(("Phone","Email")): return "Phone & email"
    if "CSAT" in n or "Sentiment" in n: return "Customer experience"
    return "Revenue retention"

def do_email_team():
    """Email SLO tied EXACTLY to email-sla-dashboard-v10 (processCSV.getAttr): inbound is attributed to
    (1) opp owner when no BO at TP; (2) opp owner when BO status = With Sales/With Advising (except BYB/BoR -> BO owner);
    (2b) opp owner when BO linked now but none at TP; (3) else BO owner. Team = attributed owner's subteam at TP
    (renames normalised, e.g. Customer Advising->Benefits Advising). SLA = Met/(Met+Missed); Pending & Cleared excluded."""
    html=open(os.path.join(HERE,"email-sla-dashboard-v10.html"),encoding="utf-8",errors="replace").read()
    s=html.find(">",html.find('id="__EMBED__"'))+1; e=html.find("</",s)
    raw=gzip.decompress(base64.b64decode(html[s:e].strip())).decode("utf-8",errors="replace")
    REN={"Onboarding Advocacy":"New Plan & Renewal Onboarding","Customer Advising":"Benefits Advising","Group Operations Fulfillment":"Group Fulfillment","Premier Dedicated Care":"Premier Dedicated Service Advising","Premier Care":"Premier Dedicated Service Advising"}
    canon=lambda t:REN.get(t,t)
    MAP={"Benefits Advising":"Benefits Advising","New Plan & Renewal Onboarding":"NP&R","Bring Your Broker":"BYB","Benefits Transfers":"BT"}
    acc={t:sc.A(MONTHS) for t in ("Benefits Advising","NP&R","BYB","BT")}
    for r in csv.DictReader(io.StringIO(raw)):
        m=sc.mo(r.get("TOUCHPOINT_START_TS_MT"))
        if m not in MONTHS: continue
        g=lambda k:(r.get(k) or "").strip()
        rt=g("BO_RECORD_TYPE"); bos=g("BENEFIT_ORDER_STATUS_AT_TP_START_TS")
        boAt=g("BO_OWNER_NAME_AT_TP"); bo=boAt or g("CURRENT_BENEFIT_ORDER_OWNER_NAME")
        boSub=canon((g("BO_OWNER_SUBTEAM_AT_TP") if boAt else "") or g("BO_OWNER_SUBTEAM"))
        oppAt=g("OPP_OWNER_NAME_AT_TP"); opp=oppAt or g("CURRENT_OPPORTUNITY_OWNER_NAME")
        oppSub=canon((g("OPP_OWNER_SUBTEAM_AT_TP") if oppAt else "") or g("OPP_OWNER_SUBTEAM"))
        broker=rt in("Benefits BYB","Benefits BoR")
        if not rt: team=oppSub if opp else None
        elif bos in("With Sales","With Advising") and not broker: team=oppSub if opp else (boSub if bo else None)
        elif not boAt and not bos and opp: team=oppSub
        elif bo: team=boSub
        elif opp: team=oppSub
        else: team=None
        # Advising = Team 'Benefits Advising' + dashboard 'Stage of ownership' = Opp only (no BO record type) + BO · With Advising
        routing_adv = (not rt) or (bos=="With Advising")
        t=MAP.get(team)
        st=g("INBOUND_EMAIL_RESPONSE_STATUS")
        tgts=[]
        if t=="Benefits Advising":
            if routing_adv: tgts.append("Benefits Advising")   # Team=Benefits Advising AND Stage of ownership = Opp only + BO·With Advising (ties to hosted dashboard: 39,816 / 21,883 met / 9,082 missed, Nov25-Oct26)
        elif t: tgts.append(t)
        for tt in tgts:
            if "Within SLA" in st: acc[tt][m][1]+=1; acc[tt][m][0]+=1
            elif "Past SLA" in st: acc[tt][m][1]+=1
    return {k:sc.pct(v,MONTHS) for k,v in acc.items()}

def do_csat_c():
    TYPES={"Renewed Benefits Feedback":"Renewal CSAT","New Benefits Feedback":"New Benefits CSAT","BYB Onboarding Feedback":"BYB CSAT","Benefits Transfers Feedback":"BT CSAT"}
    acc={l:sc.A(MONTHS) for l in list(TYPES.values())+["In-App Sentiment survey"]}
    for r in sc.rows(sc.newest("csat_data_2025-01-01_to_*.csv")):
        k=TYPES.get((r.get("SURVEY_NAME") or "").strip()); m=sc.mo(r.get("SURVEY_SUBMITTED_DATE"))
        sco=sc.num(r.get("SURVEY_CSAT_SCORE"))
        if k and m in MONTHS and sco is not None: acc[k][m][0]+=sco; acc[k][m][1]+=1
    for r in sc.rows(sc.newest("inapp_data_2025-01-01_to_*.csv")):
        m=sc.mo(r.get("SURVEY_DATE")); sco=sc.num(r.get("RATING"))
        if m in MONTHS and sco is not None: acc["In-App Sentiment survey"][m][0]+=sco; acc["In-App Sentiment survey"][m][1]+=1
    return {k:sc.pct(v,MONTHS) for k,v in acc.items()}

def do_ready_c():
    h=open(os.path.join(HERE,"benservices_operating_metrics_dashboard_v1.html"),encoding="utf-8",errors="replace").read()
    i=h.find('id="embeddedData"'); s=h.find(">",i)+1; e=h.find("</script>",s)
    recs=list(csv.DictReader(io.StringIO(h[s:e].strip()))); out=[]
    for m in MONTHS:
        y,mm=int(m[:4]),int(m[5:7])+1
        if mm==13: y+=1; mm=1
        c="%04d-%02d"%(y,mm)
        row=next((r for r in recs if r["COHORT_MONTH"][:7]==c and r["RECORD_TYPE"]=="Renewal"),None)
        out.append([float(row["CREATED_BY_PRIOR_MONTH_1ST"]),float(row["TOTAL_ORDERS"])] if row and row.get("TOTAL_ORDERS") else [0,0])
    return out

def do_mrr_c():
    import glob
    cands=sorted(glob.glob(os.path.join(HERE,"advising_mrr_cohort*.csv")))
    path=cands[-1]; RES={"Closed Won","Closed Lost","Order Lost"}
    acc={m:[0.0,0.0,0.0] for m in MONTHS}
    for r in sc.rows(path):
        st=(r.get("STATUS") or "").strip()
        if st not in RES: continue
        m=sc.mo(r.get("INFERRED_CLOSE_DATE"))
        if m not in MONTHS: continue
        b=sc.nz(r.get("MRR_TOTAL_BEFORE")); a=sc.nz(r.get("MRR_TOTAL_AFTER")); acc[m][2]+=b
        if st=="Closed Won": acc[m][0]+=(a-b)
        else: acc[m][1]+=b
    mx=max((sc.mo(r.get("INFERRED_CLOSE_DATE")) and (r.get("INFERRED_CLOSE_DATE") or "")[:10]) or "" for r in sc.rows(path))
    return [[acc[m][2]+acc[m][0]-acc[m][1],acc[m][2]] for m in MONTHS], (os.path.basename(path), mx)

def main():
    R={}
    for fn in (sc.do_bo,sc.do_adv,sc.do_byb,sc.do_bt,sc.do_avail,sc.do_ticketsla):
        o=fn(); R.update(o); print("done",fn.__name__,flush=True)
    em=do_email_team(); print("done email",flush=True)
    cs=do_csat_c(); rd=do_ready_c(); mrr,(mrrfile,mrrmax)=do_mrr_c()
    def V(name): return R[name]["v"]
    def D(key): return R[key]["v"]
    def row(n,c,k,g,d,gr=None,am=None,det=None):
        r={"n":n,"k":k,"g":g,"d":d,"c":c,"sec":section(n)}
        if gr is not None: r["gr"]=gr
        if am is not None: r["am"]=am
        if det: r["det"]=[{"n":a,"c":b} for a,b in det.items()]
        return r
    ph=D("_det_AVAIL"); ab=D("_det_ABANDON")
    teams=[
     {"name":"Benefits Advising","rows":[
       row("Advising — RFD (≤5d)",V("Advising — RFD (≤5d)"),"p",60,"hi"),
       row("Advising — ER Confirm (≤5d)",V("Advising — ER Confirm (≤5d)"),"p",70,"hi"),
       row("Advising — Alt Requested (≤5d)",V("Advising — Alt Requested (≤5d)"),"p",60,"hi"),
       row("Ready by 1st — next cohort (Renewal) †",rd,"p",95,"hi"),
       row("OA→Advising ticket rate (Renewal)",V("OA→Advising — Renewal"),"r",0.3,"lo"),
       row("OA→Advising Ticket SLA (≤5d) †",V("OA→Advising — Ticket SLA (≤5d)"),"p",80,"hi",am=70),
       row("Phone availability (80–105%)",ph["Benefits Advising"],"p",80,"hi"),
       row("Phone abandon rate",ab["Benefits Advising"],"p",30,"lo"),
       row("Email SLO (≤4h) †",em["Benefits Advising"],"p",90,"hi"),
       row("In-App Sentiment survey (avg 1–5)",cs["In-App Sentiment survey"],"s",4.0,"hi"),
       row("Net MRR Retention %",mrr,"p1",100,"hi",gr=100,am=94)]},
     {"name":"New Plan & Renewal Onboarding","rows":[
       row("% BO meeting all OA status (≤1d/stg)",V("% BO meeting all OA status (≤1d/stg)"),"p",60,"hi",det=D("_det_BO_OA")),
       row("Benefit Order NP+Renewal (≤30d)",V("Benefit Order — NP+Renewal (≤30d)"),"p",80,"hi",gr=80,am=65,det=D("_det_BO_E2E")),
       row("Ful→OA ticket rate — New Plan",V("Ful→OA — New Plan"),"r",1.2,"lo"),
       row("Ful→OA ticket rate — Renewal",V("Ful→OA — Renewal"),"r",0.37,"lo"),
       row("Ful→OA Ticket SLA (≤5d) †",V("Ful→OA — Ticket SLA (≤5d)"),"p",80,"hi",am=70),
       row("New Plan cancel rate (close month)",V("New Plan (close month)"),"p",15,"lo"),
       row("Renewal CSAT (avg 1–5)",cs["Renewal CSAT"],"s",4.0,"hi"),
       row("New Benefits CSAT (avg 1–5)",cs["New Benefits CSAT"],"s",4.25,"hi"),
       row("Phone availability (80–105%)",ph["Onboarding Advocacy"],"p",80,"hi"),
       row("Phone abandon rate",ab["Onboarding Advocacy"],"p",30,"lo"),
       row("Email SLO (≤4h) †",em["NP&R"],"p",90,"hi")]},
     {"name":"BYB Onboarding","rows":[
       row("Ready Intro (≤3d)",V("BYB — Ready Intro (≤3d)"),"p",80,"hi"),
       row("Implementation (≤5d)",V("BYB — Implementation (≤5d)"),"p",80,"hi"),
       row("Transition (≤2d/stg)",V("BYB — Transition (≤2d/stg)"),"p",80,"hi",det=D("_det_BYB_TRANS")),
       row("BYB E2E (≤60d)",V("BYB (≤60d)"),"p",80,"hi",gr=80,am=65),
       row("BYB cancel rate (close month)",V("BYB (close month)"),"p",15,"lo"),
       row("BYB CSAT (avg 1–5)",cs["BYB CSAT"],"s",4.25,"hi"),
       row("Phone availability (80–105%)",ph["BYB"],"p",80,"hi"),
       row("Phone abandon rate",ab["BYB"],"p",30,"lo"),
       row("Email SLO (≤4h) †",em["BYB"],"p",90,"hi")]},
     {"name":"BT Onboarding","rows":[
       row("Qualification (≤5d)",V("BT — Qualification (≤5d)"),"p",80,"hi",det=D("_det_BT_QUAL")),
       row("Implementation (≤5d)",V("BT — Implementation (≤5d)"),"p",80,"hi",det=D("_det_BT_IMPL")),
       row("Transition (≤2d/stg)",V("BT — Transition (≤2d/stg)"),"p",80,"hi",det=D("_det_BT_TRANS")),
       row("BT E2E (≤35d)",V("BT (≤35d)"),"p",80,"hi",gr=80,am=65),
       row("BT cancel rate (close month)",V("BT (close month)"),"p",10,"lo"),
       row("BT CSAT (avg 1–5)",cs["BT CSAT"],"s",4.25,"hi"),
       row("Phone availability (80–105%)",ph["BT"],"p",80,"hi"),
       row("Phone abandon rate",ab["BT"],"p",30,"lo"),
       row("Email SLO (≤4h) †",em["BT"],"p",90,"hi")]},
    ]
    names=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    ml=[names[int(m[5:7])-1]+" '"+m[2:4] for m in MONTHS]
    qs=[]
    for i,m in enumerate(MONTHS):
        q=fq(m)
        if not qs or qs[-1]["id"]!=q: qs.append({"id":q,"idx":[]})
        qs[-1]["idx"].append(i)
    for q in qs: q["partial"]=len(q["idx"])<3
    json.dump({"months":MONTHS,"ml":ml,"quarters":qs,"teams":teams,"mrrfile":mrrfile,"mrrmax":mrrmax,"through":THROUGH,"start":START},open(os.path.join(HERE,"scorecard_team_data.json"),"w"),ensure_ascii=False)
    print("wrote scorecard_team_data.json",[q["id"]+str(q["idx"]) for q in qs])
main()
