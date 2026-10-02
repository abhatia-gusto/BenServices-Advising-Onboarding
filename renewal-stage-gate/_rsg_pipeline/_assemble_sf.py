# Assemble the SF-phase outputs from the _pull_*.json page files.
# Writes sf_cache.json, sf_last_updated.json, cohort.json (SF-only; snow block preserved from prior).
import json, os, datetime, collections
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ET = ZoneInfo("America/New_York")

def L(name):
    return json.load(open(os.path.join(HERE, name)))

opps    = L("_pull_opps.json")
pol     = L("_pull_pol.json")
qa      = L("_pull_qa.json")
recert  = L("_pull_recert.json")
atts    = L("_pull_atts.json")

cache = {"opps": opps, "policies": pol, "atts": atts, "qaSheets": qa, "recertTickets": recert}
json.dump(cache, open(os.path.join(HERE, "sf_cache.json"), "w"), default=str)

now_utc = datetime.datetime.now(datetime.timezone.utc)
now_et  = now_utc.astimezone(ET)
pull_time    = now_utc.strftime("%Y-%m-%dT%H:%M:%S+0000")
pull_time_et = now_et.strftime("%Y-%m-%d %H:%M ET")

def parse_ts(s):
    if not s: return None
    s = s.replace("Z", "+0000")
    # handle +0000 (no colon)
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%f%z")
    except Exception:
        pass
    try:
        return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z")
    except Exception:
        return None

def maxmod(records):
    best = None
    for r in records:
        t = parse_ts(r.get("SystemModstamp"))
        if t and (best is None or t > best):
            best = t
    return best

objmap = [
    ("Opportunity", opps),
    ("Policy__c", pol),
    ("QA_Sheet__c", qa),
    ("ContentDocumentLink", atts),
    ("Ticket__c", recert),
]
last = {"pull_time": pull_time, "pull_time_et": pull_time_et, "objects": {}}
maxmods = {}
for name, recs in objmap:
    m = maxmod(recs)
    maxmods[name] = m
    last["objects"][name] = {
        "max_systemmodstamp": m.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000+0000") if m else None,
        "count": len(recs),
    }
json.dump(last, open(os.path.join(HERE, "sf_last_updated.json"), "w"), indent=1)

def et_label(dt_utc):
    if dt_utc is None: return "?"
    e = dt_utc.astimezone(ET)
    if e.date() == now_et.date():
        return e.strftime("%H:%M ET")
    return e.strftime("%m-%d %H:%M ET")

# stage counts (fixed display order incl. Alternatives Requested=0)
sc = collections.Counter(o.get("StageName") for o in opps)
stage_order = ["ER Confirm", "Engaged", "Recommendation Sent", "Alternatives Requested"]
stages = [[s, sc.get(s, 0)] for s in stage_order]

# month counts (chronological)
def mkey(o):
    d = o.get("Renewal_Date__c")
    return datetime.date.fromisoformat(d) if d else None
mc = collections.Counter()
for o in opps:
    d = o.get("Renewal_Date__c")
    if d:
        dt = datetime.date.fromisoformat(d)
        mc[(dt.year, dt.month)] += 1
months = []
novdec = 0
for (y, m) in sorted(mc):
    label = datetime.date(y, m, 1).strftime("%b %Y")
    months.append([label, mc[(y, m)]])
    if (y, m) in [(2026, 11), (2026, 12)]:
        novdec += mc[(y, m)]

# preserve prior snow block if present
prior = {}
cj = os.path.join(HERE, "cohort.json")
if os.path.exists(cj):
    try: prior = json.load(open(cj))
    except Exception: prior = {}

sf_objects = [
    ["Opportunity", et_label(maxmods["Opportunity"]), "stage, renewal date, blocked reason, deadlines", "scope,2A,11A"],
    ["Policy__c", et_label(maxmods["Policy__c"]), "carrier, contribution, waiting period, eff/exp, status", "4A,5A,6A,7A,8A,9A"],
    ["Ticket__c", et_label(maxmods["Ticket__c"]), "recert status, notes (→status)", "2A"],
    ["ContentDocumentLink", et_label(maxmods["ContentDocumentLink"]), "packet & rater titles", "1A,4A,9A"],
    ["QA_Sheet__c", et_label(maxmods["QA_Sheet__c"]), "DBA, effective date", "8A,9A"],
]

# Window label must match the dynamic "+4" SOQL window the pull actually used
# (floor fixed 2026-07-01; ceiling = last day of current month + 4). Overridable via
# RSG_FLOOR / RSG_CEILING so it stays in lockstep with pull_cli.py's _window().
import calendar as _cal
_floor = os.environ.get("RSG_FLOOR", "2026-07-01")
_ceiling = os.environ.get("RSG_CEILING")
if not _ceiling:
    _t = datetime.date.today(); _y, _m = _t.year, _t.month + 4
    _y += (_m - 1) // 12; _m = (_m - 1) % 12 + 1
    _ceiling = f"{_y:04d}-{_m:02d}-{_cal.monthrange(_y, _m)[1]:02d}"

cohort = {
    "total": len(opps),
    "generated": pull_time_et,
    "stages": stages,
    "months": months,
    "novdec": novdec,
    "window": {"floor": _floor, "ceiling": _ceiling},
    "sf": {"asof": pull_time_et, "objects": sf_objects},
}
if "snow" in prior:
    cohort["snow"] = prior["snow"]  # left for Phase B to refresh
json.dump(cohort, open(cj, "w"), indent=1)

print("sf_cache.json:", {k: len(v) for k, v in cache.items()})
print("stages:", stages)
print("months:", months, "novdec:", novdec)
print("maxmods:", {k: (v.isoformat() if v else None) for k, v in maxmods.items()})
