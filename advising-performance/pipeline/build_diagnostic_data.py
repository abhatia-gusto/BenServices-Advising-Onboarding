#!/usr/bin/env python3
"""Build per-advisor × month diagnostic data for v11.

Outputs diagnostic_data.json with:
  { advisor_name: {
      csat: { 'YYYY-MM': {sum, n, comments:[{date,score,text}, ...]} },
      inapp: { 'YYYY-MM': {sum, n, comments:[{date,rating,text}, ...]} },
      email: { 'YYYY-MM': {met, total} }   # populated separately by Snowflake pull
    }, ... }

Sources:
- CSAT: queries/csat_data_2025-01-01_to_2026-05-31.csv (assignee_name, score, comment)
- InApp: queries/inapp_data_2025-01-01_to_2026-05-31.csv (advising_owner_name, rating, comment)
- Email SLA: pulled fresh via Snowflake snow CLI
"""
import csv
import glob
import json
import os
import re
import sys
import subprocess
import datetime as _dt
from collections import defaultdict
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
SNOW = os.path.expanduser("~/.local/bin/snow")

# Period of interest — auto-advances to align with v11's active months
# (fixed start 2026-01 through the current pull month). Snowflake data lags a day,
# but the query window end = today captures everything available.
_END = _dt.date.fromisoformat(os.environ.get("PERF_END") or _dt.date.today().isoformat())
WIN_START = "2026-01-01"
WIN_END = _END.isoformat()
_WIN_START_MO = "2026-01"
_WIN_END_MO = f"{_END.year:04d}-{_END.month:02d}"


def newest_csv(prefix):
    """Pick the freshest queries/<prefix>_2025-01-01_to_YYYY-MM-DD.csv by end date."""
    cands = glob.glob(os.path.join(HERE, "queries", f"{prefix}_2025-01-01_to_*.csv"))
    dated = []
    for p in cands:
        m = re.search(r"_to_(\d{4}-\d{2}-\d{2})\.csv$", p)
        if m:
            dated.append((m.group(1), p))
    if not dated:
        raise FileNotFoundError(f"no {prefix} CSV found in queries/")
    return max(dated)[1]


def month_key(date_str):
    """Extract YYYY-MM from a YYYY-MM-DD or full timestamp string."""
    if not date_str:
        return None
    return date_str[:7]


def in_window(month):
    return month and _WIN_START_MO <= month <= _WIN_END_MO


def aggregate_csat():
    """Per opp-owner × month for RENEWAL CSAT (Renewed Benefits Feedback survey).
    Attribution: OPP_OWNER_NAME (the advisor on the renewal opp). ASSIGNEE_NAME is
    usually the case handler (OA), not the advisor — so we use OPP_OWNER_NAME here.
    Returns: { advisor_name: { 'YYYY-MM': {sum, n, comments[]} } }.
    """
    out = defaultdict(lambda: defaultdict(lambda: {"sum": 0, "n": 0, "comments": []}))
    path = newest_csv("csat_data")
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Filter to Renewed Benefits Feedback only
            if row.get("SURVEY_NAME") != "Renewed Benefits Feedback":
                continue
            name = (row.get("OPP_OWNER_NAME") or "").strip()
            if not name:
                continue
            score_raw = row.get("SURVEY_CSAT_SCORE", "").strip()
            if not score_raw:
                continue
            try:
                score = int(score_raw)
            except ValueError:
                continue
            date = row.get("SURVEY_SUBMITTED_DATE", "")
            mk = month_key(date)
            if not in_window(mk):
                continue
            bucket = out[name][mk]
            bucket["sum"] += score
            bucket["n"] += 1
            comment = (row.get("CSAT_SURVEY_COMMENT") or "").strip()
            if comment:
                bucket["comments"].append({"d": date, "s": score, "t": comment})
    # Trim each month's comments to 5 most recent
    for name in out:
        for mk in out[name]:
            cs = out[name][mk]["comments"]
            cs.sort(key=lambda c: c["d"], reverse=True)
            out[name][mk]["comments"] = cs[:5]
    return {n: dict(months) for n, months in out.items()}


def aggregate_inapp():
    """Per-advising_owner × month: sum of rating, n, comments (top 5 by date desc)."""
    out = defaultdict(lambda: defaultdict(lambda: {"sum": 0, "n": 0, "comments": []}))
    path = newest_csv("inapp_data")
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("ADVISING_OPPORTUNITY_OWNER_NAME") or "").strip()
            if not name:
                continue
            rating_raw = (row.get("RATING") or "").strip()
            if not rating_raw:
                continue
            try:
                rating = int(rating_raw)
            except ValueError:
                continue
            date = row.get("SURVEY_DATE", "")
            mk = month_key(date)
            if not in_window(mk):
                continue
            bucket = out[name][mk]
            bucket["sum"] += rating
            bucket["n"] += 1
            comment = (row.get("USER_COMMENT") or "").strip()
            if comment:
                bucket["comments"].append({"d": date, "s": rating, "t": comment})
    for name in out:
        for mk in out[name]:
            cs = out[name][mk]["comments"]
            cs.sort(key=lambda c: c["d"], reverse=True)
            out[name][mk]["comments"] = cs[:5]
    return {n: dict(months) for n, months in out.items()}


def aggregate_email_sla():
    """Per-advisor × month: met/total inbound emails — pulled fresh from Snowflake.
    Attribution = OPP_OWNER_NAME_AT_TP (matches the source dashboard convention).
    'Met' = Responded (Within SLA). 'Missed' = Responded (Past SLA) or Pending past SLA.
    'Cleared' rows are excluded (no action was required).
    """
    sql_path = os.path.join(HERE, "email-sla-dashboard-source-attp.sql")
    inner = open(sql_path).read()
    inner = inner.replace("{{ TP Date Range Start }}", WIN_START)
    inner = inner.replace("{{ TP Date Range End }}", WIN_END)
    inner = inner.rstrip().rstrip(";")
    sql = f"""
    with src as (
      {inner}
    )
    select
      advisor_name,
      to_char(date_trunc('month', tpc), 'YYYY-MM') as month_key,
      count_if(st = 'Responded (Within SLA)') as met,
      count_if(st in ('Responded (Within SLA)','Responded (Past SLA)')) as total
    from (
      select
        CASE
          WHEN COALESCE(bo_record_type,'')='' THEN COALESCE(opp_owner_name_at_tp, current_opportunity_owner_name)
          WHEN benefit_order_status_at_tp_start_ts IN ('With Sales','With Advising') AND COALESCE(bo_record_type,'') NOT IN ('Benefits BYB','Benefits BoR')
               THEN COALESCE(opp_owner_name_at_tp, current_opportunity_owner_name, bo_owner_name_at_tp, current_benefit_order_owner_name)
          WHEN bo_owner_name_at_tp IS NULL AND COALESCE(benefit_order_status_at_tp_start_ts,'')='' AND COALESCE(opp_owner_name_at_tp, current_opportunity_owner_name) IS NOT NULL
               THEN COALESCE(opp_owner_name_at_tp, current_opportunity_owner_name)
          ELSE COALESCE(bo_owner_name_at_tp, current_benefit_order_owner_name, opp_owner_name_at_tp, current_opportunity_owner_name)
        END as advisor_name,
        CASE
          WHEN COALESCE(bo_record_type,'')='' THEN COALESCE(opp_owner_subteam_at_tp, opp_owner_subteam)
          WHEN benefit_order_status_at_tp_start_ts IN ('With Sales','With Advising') AND COALESCE(bo_record_type,'') NOT IN ('Benefits BYB','Benefits BoR')
               THEN CASE WHEN COALESCE(opp_owner_name_at_tp, current_opportunity_owner_name) IS NOT NULL THEN COALESCE(opp_owner_subteam_at_tp, opp_owner_subteam) ELSE COALESCE(bo_owner_subteam_at_tp, bo_owner_subteam) END
          WHEN bo_owner_name_at_tp IS NULL AND COALESCE(benefit_order_status_at_tp_start_ts,'')='' AND COALESCE(opp_owner_name_at_tp, current_opportunity_owner_name) IS NOT NULL
               THEN COALESCE(opp_owner_subteam_at_tp, opp_owner_subteam)
          ELSE COALESCE(bo_owner_subteam_at_tp, bo_owner_subteam)
        END as rsub,
        touchpoint_start_ts_mt as tpc,
        inbound_email_response_status as st
      from src
    ) r
    where rsub ilike '%Advising%'
    group by 1, 2
    having advisor_name is not null and total > 0
    order by advisor_name, month_key
    """
    qtag = ('{"qtag":{"version":"1.1.0","source":{"claude_code":'
            '{"username":"serene-sleepy-ramanujan","hostname":"claude",'
            '"source":"query-snowflake-skill"}}}}')
    full = f"ALTER SESSION SET QUERY_TAG = '{qtag}';\n{sql}"
    cmd = [SNOW, "sql", "-c", "default", "-q", full, "--format", "JSON",
           "--enable-templating", "NONE", "--warehouse", "GUSTIE_ADHOC_WH"]
    print(f"  [snowflake] pulling email SLA per-advisor × month ...", file=sys.stderr)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    if proc.returncode != 0:
        print("STDERR:", proc.stderr[-2000:], file=sys.stderr)
        raise RuntimeError(f"snow failed ({proc.returncode})")
    parsed = json.loads(proc.stdout)
    if parsed and isinstance(parsed[0], list):
        rows = parsed[-1]
    else:
        rows = parsed
    out = defaultdict(dict)
    for r in rows:
        name = (r.get("ADVISOR_NAME") or "").strip()
        mk = r.get("MONTH_KEY")
        if not name or not mk or not in_window(mk):
            continue
        out[name][mk] = {"met": int(r.get("MET") or 0), "total": int(r.get("TOTAL") or 0)}
    return dict(out)


def main():
    print("Aggregating CSAT ...")
    csat = aggregate_csat()
    print(f"  → {len(csat)} unique assignees")
    print("Aggregating In-App Sentiment ...")
    inapp = aggregate_inapp()
    print(f"  → {len(inapp)} unique owners")
    print("Aggregating Email SLA from embedded dashboard CSV ...")
    try:
        email = aggregate_email_sla()
        print(f"  → {len(email)} unique advisors")
    except Exception as e:
        print(f"  email aggregate FAILED: {e}", file=sys.stderr)
        email = {}
    # Merge all sources keyed by name
    all_names = set(csat) | set(inapp) | set(email)
    out = {}
    for name in sorted(all_names):
        rec = {}
        if name in csat:
            rec["csat"] = csat[name]
        if name in inapp:
            rec["inapp"] = inapp[name]
        if name in email:
            rec["email"] = email[name]
        out[name] = rec
    outpath = os.path.join(HERE, "diagnostic_data.json")
    with open(outpath, "w") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    print(f"\nWrote {outpath} — {len(out)} advisors")
    print(f"  with CSAT data: {sum(1 for n in out if 'csat' in out[n])}")
    print(f"  with InApp data: {sum(1 for n in out if 'inapp' in out[n])}")
    print(f"  with Email SLA data: {sum(1 for n in out if 'email' in out[n])}")


if __name__ == "__main__":
    main()
