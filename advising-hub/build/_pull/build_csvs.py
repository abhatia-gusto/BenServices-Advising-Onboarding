#!/usr/bin/env python3
# Central parser: reads raw JSON dumps produced by the SF-MCP pull subagents
# and writes the 3 CSVs the pipeline reads.
import json, re, csv, collections, datetime, os, glob, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT  = os.path.abspath(os.path.join(HERE, ".."))   # _renewal_vnext/out
RAW  = os.path.join(HERE, "raw")

# --- run isolation without deletion ---------------------------------------
# The cowork mount blocks `rm` (Operation not permitted), so stale raw dumps
# from a prior run cannot be removed. Instead the prep step `touch`es a marker
# and we only ingest raw files modified at/after it, so leftovers are ignored.
# (Overwritten files get a fresh mtime, so re-pulled batches are still picked up.)
MARKER = os.path.join(HERE, ".run_start")
_CUTOFF = (os.path.getmtime(MARKER) - 2) if os.path.exists(MARKER) else 0.0  # 2s slack

def rawfiles(pat):
    fs = [f for f in glob.glob(os.path.join(RAW, pat)) if os.path.getmtime(f) >= _CUTOFF]
    return sorted(fs)

def load_records(path):
    """Accept either a full query response {records:[...]} or a bare list."""
    d = json.load(open(path))
    if isinstance(d, dict):
        return d.get("records", []) or []
    return d

def dpart(s): return str(s).split("T")[0]

# universe of queried Open/PF opps (all 7390)
universe = json.load(open(os.path.join(OUT, "_openpf_ids.json")))

# ---------------- INTRO ----------------
intro_min = {}
for f in rawfiles("intro_*.json"):
    for r in load_records(f):
        oid = r.get("oid") or r.get("Opportunity__c")
        d   = dpart(r.get("mind") or r.get("expr0"))
        if oid and (oid not in intro_min or d < intro_min[oid]):
            intro_min[oid] = d
with open(os.path.join(OUT, "sf_mcp_intro.csv"), "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["opp_id18","intro_call","intro_call_date"])
    yv=0
    for oid in universe:
        if oid in intro_min:
            w.writerow([oid,"Y",intro_min[oid]]); yv+=1
        else:
            w.writerow([oid,"N",""])
print(f"INTRO: universe={len(universe)} Y={yv} N={len(universe)-yv}")

# ---------------- RECERT ----------------
rec_latest = {}   # oid -> (status, createddate)
for f in rawfiles("recert_*.json"):
    for r in load_records(f):
        oid = r.get("Opportunity__c"); st = r.get("Recert_Status__c"); cd = r.get("CreatedDate")
        if not oid or st is None: continue
        if oid not in rec_latest or (cd or "") > rec_latest[oid][1]:
            rec_latest[oid] = (st, cd or "")
with open(os.path.join(OUT, "sf_mcp_recert.csv"), "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["opp_id18","recert_status"])
    for oid,(st,cd) in sorted(rec_latest.items()):
        w.writerow([oid, st])
print(f"RECERT: opps_with_ticket={len(rec_latest)}")

# ---------------- PACKETS ----------------
DATE_RE = re.compile(r'\d{4}-?\d{1,2}-?\d{1,2}')
def parse_carrier(title):
    t=title.strip(); low=t.lower(); idx=low.rfind("renewal packet")
    pre=t[:idx].rstrip() if idx>=0 else t
    dm=None
    for m in DATE_RE.finditer(pre): dm=m
    if dm:
        after=pre[dm.end():].strip(" ._,-")
        if after: return after
    return pre.strip(" ._,-")

pk_files = collections.defaultdict(list)  # oid -> [(carrier, date)]
for f in rawfiles("pk_*.json"):
    for r in load_records(f):
        oid = r.get("LinkedEntityId") or r.get("e")
        # title / date may be nested under ContentDocument
        cd = r.get("ContentDocument") or {}
        title = r.get("Title") or (cd.get("Title") if isinstance(cd,dict) else None) or r.get("t")
        cdate = r.get("CreatedDate") or (cd.get("CreatedDate") if isinstance(cd,dict) else None) or r.get("d")
        if not oid or not title: continue
        pk_files[oid].append((parse_carrier(title), datetime.date.fromisoformat(dpart(cdate))))
with open(os.path.join(OUT, "sf_mcp_packets.csv"), "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["opp_id18","packets_files","packet_carriers"])
    for oid in sorted(pk_files):
        rows = pk_files[oid]
        latest={}
        for c,d in rows:
            if c not in latest or d>latest[c]: latest[c]=d
        carriers=sorted(latest.keys(), key=lambda c:(latest[c],c))
        detail=" · ".join(f"{c} ({latest[c].isoformat()})" for c in carriers)
        w.writerow([oid, len(rows), detail])
print(f"PACKETS: opps_with_packets={len(pk_files)}  total_files={sum(len(v) for v in pk_files.values())}")

# ---------------- SEP ----------------
sep_val = {}   # oid -> sep_risk_level
for f in rawfiles("sep_*.json"):
    for r in load_records(f):
        oid = r.get("oid") or r.get("Id")
        val = r.get("sep") or r.get("SEP_Risk_Level__c")
        if not oid or val in (None, ""): continue
        sep_val[oid] = val
with open(os.path.join(OUT, "sf_mcp_sep.csv"), "w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["opp_id18","sep_risk_level"])
    for oid, val in sorted(sep_val.items()):
        w.writerow([oid, val])
print(f"SEP: opps_with_value={len(sep_val)}")

# raw-file inventory for sanity: fresh (this run) vs total on disk (incl. stale leftovers)
inv = {g: (len(rawfiles(g+'*.json')), len(glob.glob(os.path.join(RAW, g+'*.json'))))
       for g in ('intro_','recert_','pk_')}
print("RAW files (fresh_this_run, total_on_disk):", inv)
if _CUTOFF == 0.0:
    print("  NOTE: no .run_start marker found -> ingested ALL raw files (touch _pull/.run_start before a pull to isolate the run)")
