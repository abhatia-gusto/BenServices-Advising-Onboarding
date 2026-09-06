#!/usr/bin/env python3
"""Broker Onboarding Performance v2 — MULTI-MONTH (Jan–May 2026), raw components for client scoring.
Month-aware: BO Status, E2E, Cancel, Quality (per-month). Static period rollups: Phone Avail, Abandon."""
import csv, json, os
QDIR=os.path.join(os.path.dirname(os.path.abspath(__file__)),"queries")
TMP="/tmp"
import datetime as _dt
_END=os.environ.get("PERF_END") or _dt.date.today().isoformat()   # through today (auto-advances)
def _mrange(start_y,start_m,end_y,end_m):
    out=[]; y,m=start_y,start_m
    while (y<end_y) or (y==end_y and m<=end_m):
        out.append(f"{y}-{m:02d}"); m+=1
        if m>12: m=1; y+=1
    return out
MONTHS=_mrange(2026,1,int(_END[:4]),int(_END[5:7]))
MONTHKEYS={m:m+"-01" for m in MONTHS}        # FIRST_END_MONTH value -> label
KEY2LAB={v:k for k,v in MONTHKEYS.items()}
TRAIL={m+"-01" for m in MONTHS}
E2E_DAY_TGT={"BYB":60,"BT":35}   # per-team flat end-to-end day target (no order-type / carrier tiers)
# BYB BO Status never-entered handling. Default OFF = legacy (count raw *_SLA_MET_BUCKET flag, which
# reads "1" for 0-day never-entered buckets). Set env BYB_EXCLUDE_NEVER_ENTERED=1 to match the Broker
# SLA dashboard: a BYB bucket with TOTAL_DAYS<=0 (never meaningfully entered) is excluded, not credited.
_BYB_BUCKET_DAYS={"READY_INTRO_SLA_MET_BUCKET":"READY_INTRO_TOTAL_DAYS",
                  "IMPLEMENTATION_SLA_MET_BUCKET":"IMPLEMENTATION_TOTAL_DAYS",
                  "TRANSITION_SLA_MET":"TRANSITION_TOTAL_DAYS"}
_EXCL_NE=os.environ.get("BYB_EXCLUDE_NEVER_ENTERED","1")!="0"   # default ON (BYB never-entered excluded, matches SLA dash)

def load(fn):
    with open(os.path.join(QDIR,fn)) as f: return list(csv.DictReader(f))
def loadtmp(fn):
    with open(os.path.join(TMP,fn)) as f: return list(csv.DictReader(f))
def roster(subteam):
    return {r["NAME"]:r["PE"] for r in loadtmp("roster.csv") if r["SUB_TEAM"]==subteam and r["IS_PE"]=="False"}
def roster_status(subteam):
    return {r["NAME"]:(r.get("STATUS") or "") for r in loadtmp("roster.csv") if r["SUB_TEAM"]==subteam and r["IS_PE"]=="False"}
def fnum(x):
    try: return float(x)
    except: return None

# LAI per (name, month-label)
LAI={}
for r in loadtmp("lai_janmay.csv"):
    lab=KEY2LAB.get(r["CONVO_MONTH"])
    if lab: LAI[(r["FULL_NAME"],lab)]=(float(r["QA_EARNED"]),float(r["QA_POSSIBLE"]))
# month-aware phone: (name, month-label) -> (numerator, denominator)
AVAIL={}  # avail: (sla_days_met, eligible_days)
for r in loadtmp("bo_avail_month.csv"):
    lab=KEY2LAB.get(r["MONTH"])
    if lab: AVAIL[(r["NAME"],lab)]=(int(fnum(r["SLA_DAYS_MET"]) or 0),int(fnum(r["ELIGIBLE_DAYS"]) or 0))
ABAND={}  # abandon: (abandoned_modified, inbound_calls)
for r in loadtmp("bo_abandon_month.csv"):
    lab=KEY2LAB.get(r["MONTH"])
    if lab: ABAND[(r["ADVISOR_NAME"],lab)]=(int(fnum(r["ABANDONED_MODIFIED"]) or 0),int(fnum(r["INBOUND_CALLS"]) or 0))
# report rollups (full period): per-IC call counts + durations, and LAI evals + channels
def gnum(d,k):
    try: return float(d.get(k,"") or 0)
    except: return 0.0
PHONE={}
for r in loadtmp("bo_phone_rollup.csv"):
    PHONE[r["ADVISOR_NAME"]]={"inb":int(gnum(r,"INBOUND_CALL_CT")),"outb":int(gnum(r,"OUTBOUND_CALL_CT")),
        "total":int(gnum(r,"PHONE_CALL_COUNT")),"inbAvg":round(gnum(r,"INBOUND_AVG_CALL_DURATION_MINS"),2),
        "inbMed":round(gnum(r,"INBOUND_MEDIAN_CALL_DURATION_MINS"),2),"outbAvg":round(gnum(r,"OUTBOUND_AVG_CALL_DURATION_MINS"),2),
        "outbMed":round(gnum(r,"OUTBOUND_MEDIAN_CALL_DURATION_MINS"),2)}
LAIR={}
for r in loadtmp("bo_lai_rollup.csv"):
    LAIR[r["FULL_NAME"]]={"evals":int(float(r["N_EVALS"])),"email":int(float(r["EMAIL_CT"])),"call":int(float(r["CALL_CT"]))}

def _f(x):
    try: return float(x)
    except: return 0.0
# Transition sub-statuses with Ready-for-Implementing-Plans REMOVED (it moves into the Implementation combo).
_BYB_TR_NORIP=("PLANS_CONFIRMED_SLA_MET","OE_VERIF_SLA_MET","OE_SUBMISSION_SLA_MET","FULFILLMENT_PREP_SLA_MET")
_BT_TR_NORIP=("READY_QUALIF_SLA_MET","READY_DOC_COLLECT_SLA_MET","READY_PLAN_REVIEW_SLA_MET","READY_TADA_DOC_COLLECT_SLA_MET","UNBLOCK_PLAN_REVIEW_SLA_MET","PLANS_CONFIRMED_SLA_MET","ENROLL_REVIEW_ENTRY_SLA_MET","READY_SEND_ENROLL_SLA_MET","ENROLL_CONFIRMED_SLA_MET")
def _combo_tr(r, team):
    # Transition (combo): rip pulled out; entered statuses only; miss if any entered missed
    cols=_BYB_TR_NORIP if team=="BYB" else _BT_TR_NORIP
    any_=False; miss=False
    for c in cols:
        v=(r.get(c,"") or "").strip()
        if v=="0": any_=True; miss=True
        elif v=="1": any_=True
    return "" if not any_ else ("0" if miss else "1")
def _combo_im(r, team):
    # Implementation (combo): Ready-for-Implementing-Plans + Implementing-Plans days summed.
    #   BYB: <=5d (10d for 'New to BYB - No OE', census dependency).
    #   BT:  flat 5d; Implementing TAdA Plans kept separate (<=5d via its own SLA_MET flag) — bucket needs all entered parts to pass.
    rip=(r.get("READY_IMPL_PLANS_DAYS","") or "").strip(); ip=(r.get("IMPL_PLANS_DAYS","") or "").strip()
    if team=="BYB":
        if rip=="" and ip=="": return ""
        tgt=10 if r.get("ORDER_TYPE","")=="New to BYB - No OE" else 5
        return "1" if (_f(r.get("READY_IMPL_PLANS_DAYS",0))+_f(r.get("IMPL_PLANS_DAYS",0)))<=tgt else "0"
    itp=(r.get("IMPL_TADA_PLANS_DAYS","") or "").strip()
    if rip=="" and ip=="" and itp=="": return ""
    ok=True
    if (rip!="" or ip!="") and (_f(r.get("READY_IMPL_PLANS_DAYS",0))+_f(r.get("IMPL_PLANS_DAYS",0)))>5: ok=False
    if itp!="" and (r.get("IMPL_TADA_PLANS_SLA_MET","") or "").strip()=="0": ok=False
    return "1" if ok else "0"

# BT synthetic BO Status (Martin 2026-07): aggregate day-sums scored as one status; blank when none entered.
_QUAL_SYN=("READY_QUALIF_DAYS","QUALIFICATION_DAYS","READY_DOC_COLLECT_DAYS")
_IMPL_SYN=("READY_IMPL_PLANS_DAYS","IMPL_PLANS_DAYS","READY_PLAN_REVIEW_DAYS")
_ENR_SYN=("PLANS_CONFIRMED_DAYS","ENROLL_REVIEW_ENTRY_DAYS","READY_SEND_ENROLL_DAYS")
_TR_SYN=("ENROLL_CONFIRMED_DAYS","BLOCKED_PLAN_REVIEW_DAYS","READY_TADA_DOC_COLLECT_DAYS","UNBLOCK_PLAN_REVIEW_DAYS")
def _sent(r,cols): return any((r.get(c,"") or "").strip()!="" for c in cols)
def _sdays(r,cols): return sum(_f(r.get(c,0)) for c in cols)
def _syn_qt(r):  # Qualification synthetic <=5d
    return "" if not _sent(r,_QUAL_SYN) else ("1" if _sdays(r,_QUAL_SYN)<=5 else "0")
def _syn_im(r):  # Implementation = Impl-Plan synth + Enroll-Entry synth + Implementing TAdA Plans, each <=5d
    ipE=_sent(r,_IMPL_SYN); enE=_sent(r,_ENR_SYN); itpE=(r.get("IMPL_TADA_PLANS_DAYS","") or "").strip()!=""
    if not (ipE or enE or itpE): return ""
    ok=True
    if ipE and _sdays(r,_IMPL_SYN)>5: ok=False
    if enE and _sdays(r,_ENR_SYN)>5: ok=False
    if itpE and _f(r.get("IMPL_TADA_PLANS_DAYS",0))>5: ok=False
    return "1" if ok else "0"
def _syn_tr(r):  # Transition = Enrollment Confirmed + Blocked Plan Review + Ready TAdA Doc + Unblock Plan Review, each <=2d
    if not _sent(r,_TR_SYN): return ""
    return "0" if any((r.get(c,"") or "").strip()!="" and _f(r.get(c,0))>2 for c in _TR_SYN) else "1"

def build(csv_fn, subteam, status_buckets, day_tgt, combo=False, team=None, synth=False):
    rmap=roster(subteam); stat=roster_status(subteam)
    rows=[r for r in load(csv_fn) if r["FIRST_END_MONTH"] in MONTHKEYS.values() and r["BENEFIT_ORDER_OWNER"] in rmap]
    # per IC -> per month accumulators
    A={}
    for n,pe in rmap.items():
        A[n]={"name":n,"pe":pe,"bs":{},"e":{},"c":{}}
        for m in MONTHS:
            A[n]["bs"][m]={"met":0,"total":0}; A[n]["e"][m]={"met":0,"total":0}
            A[n]["c"][m]={"cancels":0,"total":0}
    for r in rows:
        a=A[r["BENEFIT_ORDER_OWNER"]]; mo=KEY2LAB[r["FIRST_END_MONTH"]]
        bs=a["bs"][mo]; e=a["e"][mo]; c=a["c"][mo]
        for col in status_buckets:
            if synth and col=="QUALIFICATION_SLA_MET_BUCKET": v=_syn_qt(r)
            elif synth and col=="IMPLEMENTATION_SLA_MET_BUCKET": v=_syn_im(r)
            elif synth and col=="TRANSITION_SLA_MET": v=_syn_tr(r)
            elif combo and col=="TRANSITION_SLA_MET": v=_combo_tr(r, team)
            elif combo and col=="IMPLEMENTATION_SLA_MET_BUCKET": v=_combo_im(r, team)
            else:
                v=r.get(col,"")
                if _EXCL_NE and team=="BYB" and col in _BYB_BUCKET_DAYS:
                    _dd=r.get(_BYB_BUCKET_DAYS[col],"")
                    try: _entered=float(_dd)>0
                    except (TypeError,ValueError): _entered=False
                    if not _entered: v=""   # never-entered BYB bucket -> exclude (match Broker SLA dash)
            if v=="1": bs["met"]+=1; bs["total"]+=1
            elif v=="0": bs["total"]+=1
        # E2E: flat per-team day target (no order-type / carrier tiers)
        d=r.get("DAYS_CREATED_TO_FIRST_FULFILLED","")
        if d not in ("",None):
            e["total"]+=1
            if float(d)<=day_tgt: e["met"]+=1
        # Cancel: single team-wide target (no order-type / carrier tiers)
        c["total"]+=1
        c["cancels"]+=1 if r["CANCEL_FLAG"]=="True" else 0
    advisors=[]
    for n,a in A.items():
        q={};av={};ab={}
        for m in MONTHS:
            lai=LAI.get((n,m))
            q[m]={"sum":lai[0] if lai else None,"count":lai[1] if lai else None}
            sm,ed=AVAIL.get((n,m),(0,0)); av[m]={"met":sm,"total":ed}
            am,ic=ABAND.get((n,m),(0,0)); ab[m]={"met":am,"total":ic}
        _hd=(any(a["bs"][m]["total"] or a["e"][m]["total"] or a["c"][m]["total"] for m in MONTHS)
             or bool(LAIR.get(n)) or bool(PHONE.get(n)) or any(q[m]["count"] for m in MONTHS)
             or any(av[m]["total"] for m in MONTHS) or any(ab[m]["total"] for m in MONTHS))
        if stat.get(n,"") not in ("Active","On Leave") and not _hd: continue
        advisors.append({"name":n,"pe":a["pe"],"rpt":{"calls":PHONE.get(n,{}),"lai":LAIR.get(n,{})},"raw":{
            "boStatus":{"m":a["bs"]},"e2e":{"m":a["e"]},"cancel":{"m":a["c"]},
            "quality":{"m":q},"avail":{"m":av},"abandon":{"m":ab}}})
    advisors.sort(key=lambda x:x["name"])
    pes=sorted(set(a["pe"] for a in advisors if a["pe"]))
    return {"advisors":advisors,"pes":pes}

BYB=build(f"byb_data_2025-09-01_to_{_END}.csv","Bring Your Broker",
          ["READY_INTRO_SLA_MET_BUCKET","IMPLEMENTATION_SLA_MET_BUCKET","TRANSITION_SLA_MET"], E2E_DAY_TGT["BYB"], team="BYB")
BT =build(f"bt_data_2025-09-01_to_{_END}.csv","Benefits Transfers",
          ["QUALIFICATION_SLA_MET_BUCKET","IMPLEMENTATION_SLA_MET_BUCKET","TRANSITION_SLA_MET"], E2E_DAY_TGT["BT"], synth=True, team="BT")
EW=round(100/6,2)
D={"months":MONTHS,
   "order":["boStatus","e2e","avail","abandon","cancel","quality"],
   "monthAware":["boStatus","e2e","avail","abandon","cancel","quality"],   # all six follow the Months filter
   "defaults":{
     "metrics":{
       "boStatus":{"l":"BO Status","g":80,"f":65,"d":"gte","fmt":"pct","tip":"% of bucket SLAs met — Ready Intro/Qual, Implementation, Transition. BT uses synthetic statuses (Qualification, Implementing-Plan, Enrollment-Entry aggregates ≤5d; Implementing TAdA Plans ≤5d; Transition statuses ≤2d). BYB: Implementing Plans ≤5/10d. Customer-Facing & Blocked are not scored here."},
       "e2e":{"l":"E2E SLA","g":80,"f":60,"d":"gte","fmt":"pct","tip":"% of orders fulfilled within the team end-to-end day target (BYB ≤"+str(E2E_DAY_TGT["BYB"])+"d / BT ≤"+str(E2E_DAY_TGT["BT"])+"d — single target, all order types). Scored against the team SLO (BYB ≥85% / BT ≥80%)."},
       "avail":{"l":"Phone Availability","g":70,"f":65,"d":"gte","fmt":"pct","tip":"% of eligible days at 70-105% availability (min 2h logged)"},
       "abandon":{"l":"Abandon (mod.)","g":5,"f":20,"d":"lte","fmt":"pct","tip":"Abandon rate on inbound calls, excl. Remove-from-Queue"},
       "cancel":{"l":"Cancel Rate","g":15,"f":30,"d":"lte","fmt":"rate","tip":"Cancelled / closed orders, scored vs a single team-wide target (BYB ≤15% / BT ≤10%). No order-type or carrier tiers."},
       "quality":{"l":"LAI QA","g":90,"f":80,"d":"gte","fmt":"pct","tip":"Level AI average evaluation (QA) score (sparse for BO today)"},
     },
     "weights":{"boStatus":EW,"e2e":EW,"avail":EW,"abandon":EW,"cancel":EW,"quality":EW},
     "cancelByTeam":{"BYB":{"g":15,"f":30},"BT":{"g":10,"f":25}},
     "e2eByTeam":{"BYB":{"g":85,"f":65},"BT":{"g":80,"f":60}},
     "e2eDayTarget":E2E_DAY_TGT,
     "capAtt":125
   },
   "BYB":BYB,"BT":BT}
with open(os.path.join(TMP,"varD2.json"),"w") as f: json.dump(D,f)
print("months:",MONTHS,"| E2E day target:",E2E_DAY_TGT,"| cancel BYB 15/30 BT 10/25 | E2E SLO BYB 85/65 BT 80/60 | EW:",EW)
for tag,g in (("BYB",BYB),("BT",BT)):
    av=g["advisors"]
    # total closed across all months
    tot=sum(sum(a["raw"]["cancel"]["m"][m]["total"] for m in MONTHS) for a in av)
    wav=sum(1 for a in av if any(a['raw']['avail']['m'][m]['total']>0 for m in MONTHS))
    print(f"{tag}: {len(av)} ICs, PEs={g['pes']}, total closed Jan-May={tot}, with avail={wav}")
print("wrote /tmp/varD2.json")
