#!/usr/bin/env python3
"""All-metrics verification: for the latest quarter, tie the PE/leadership layer back to the
team view for EVERY metric. For each metric prints PASS / FAIL (owned-work: Σ leadership must
equal the team value within tolerance) or INFO (phone/email are IC->current-PE resolved and
coverage-bounded, so Σ runs slightly below the owner-agnostic team total — reported with the
mapped-coverage % instead of a hard pass/fail).

Reads scorecard_team_data.json + scorecard_pe_data.json from the workdir (written by the
team + pepe computes). Runs automatically at the end of run.py when both exist; also runnable
standalone. Tolerance: 0.6pp for %, 0.02 for rates/scores.
"""
import os,json,sys
HERE=os.path.dirname(os.path.abspath(__file__))
def load(n):
    p=os.path.join(HERE,n)
    return json.load(open(p)) if os.path.exists(p) else None
team=load("scorecard_team_data.json"); pe=load("scorecard_pe_data.json")
if not team or not pe:
    print("[reconcile] skipped — need both scorecard_team_data.json and scorecard_pe_data.json"); sys.exit(0)

QIDX=team["quarters"][-1]["idx"]; QID=team["quarters"][-1]["id"]
COVERAGE={"Phone availability (80–105%)","Phone abandon rate","Email SLO (≤4h)"}
def norm(n): return n.replace(" †","").strip()
# BYB/BT team tables use bare stage names; PE view prefixes them. Map by team table.
def tkey(teamname,n):
    n=norm(n)
    if teamname=="BYB Onboarding" and n in ("Ready Intro (≤3d)","Implementation (≤5d)","Transition (≤2d/stg)"): return "BYB — "+n
    if teamname=="BT Onboarding" and n in ("Qualification (≤5d)","Implementation (≤5d)","Transition (≤2d/stg)"): return "BT — "+n
    return n
def qsum(c):
    nu=de=0.0
    for i in QIDX:
        if i<len(c) and c[i] and c[i][1]: nu+=c[i][0]; de+=c[i][1]
    return nu,de
def val(nu,de,k): return None if not de else (nu/de if k in("s","r") else 100*nu/de)

# team totals: sum counts across all team tables per normalized key
tt={}
for tm in team["teams"]:
    for r in tm["rows"]:
        key=tkey(tm["name"],r["n"]); nu,de=qsum(r["c"])
        a=tt.setdefault(key,{"nu":0.0,"de":0.0,"k":r["k"]}); a["nu"]+=nu; a["de"]+=de
# pe (leadership) Σ across all leaders per metric
pp={}
for p in pe["pes"]:
    for r in p["rows"]:
        key=norm(r["n"]); nu,de=qsum(r["c"])
        a=pp.setdefault(key,{"nu":0.0,"de":0.0,"k":r["k"]}); a["nu"]+=nu; a["de"]+=de

def fmt(v,k):
    if v is None: return "–"
    return "%d"%round(v) if k=="p" else ("%.1f"%v if k=="p1" else "%.2f"%v)
def within(a,b,k):
    if a is None or b is None: return False
    return abs(a-b)<=(0.6 if k in("p","p1") else 0.02)

rows=[]; npass=nfail=ninfo=0
for key in pp:
    if key not in tt: continue
    k=pp[key]["k"]
    pv=val(pp[key]["nu"],pp[key]["de"],k); tv=val(tt[key]["nu"],tt[key]["de"],k)
    cov=round(100*pp[key]["de"]/tt[key]["de"],1) if tt[key]["de"] else None
    if key in COVERAGE:
        status="INFO (cov %.0f%%)"%cov if cov is not None else "INFO"; ninfo+=1
    elif within(pv,tv,k):
        status="PASS"; npass+=1
    else:
        status="FAIL"; nfail+=1
    rows.append((status,key,fmt(tv,k),fmt(pv,k),cov))
order={"FAIL":0,"INFO":1,"PASS":2}
rows.sort(key=lambda x:(order[x[0].split()[0]],x[1]))
print("\n==== All-metrics verification — %s QTD : Σ leadership vs team ===="%QID)
print("%-18s %-42s %8s %8s %6s"%("status","metric","team","Σ lead","cov%"))
for st,m,tv,pv,cov in rows:
    print("%-18s %-42s %8s %8s %6s"%(st,m[:42],tv,pv,("" if cov is None else "%.0f"%cov)))
print("---- %d PASS / %d FAIL / %d INFO(coverage-bounded phone&email) ----"%(npass,nfail,ninfo))
if nfail: print("NOTE: FAIL = Σ leadership != team beyond tol; investigate attribution/definition drift.")
