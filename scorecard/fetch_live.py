#!/usr/bin/env python3
"""
Benefit Services Scorecard — LIVE materializer (portable).

Runs every canonical source query in scorecard/queries/ live against Snowflake and writes the
EXACT input artifacts that the bundled compute scripts (lib/) already consume. Nothing here depends
on a specific machine or on any pre-refreshed CSV — give it Snowflake creds and it reproduces the
same inputs that produced the published scorecard, on any computer.

The compute scripts are run verbatim (lib/), so once these artifacts exist the numbers are identical
to the ones scorecard_live_audit.py already ties to live Snowflake at the team grain.

Usage:
  python3 fetch_live.py --workdir _run [--through 2026-10] [--only bo,byb,...] [--creds snowflake_pat.env]

Creds (first found wins):
  1. env vars SNOWFLAKE_ACCOUNT / SNOWFLAKE_USER / SNOWFLAKE_PAT (+ optional ROLE/WAREHOUSE/DATABASE/SCHEMA)
  2. a key=value file passed with --creds (same keys; PAT line may be bare or SNOWFLAKE_PAT=...)
The PAT is passed as token= with authenticator=PROGRAMMATIC_ACCESS_TOKEN and region=us-west-2
(NOT password=) — the one connector gotcha for this account.
"""
import os, sys, csv, json, gzip, base64, datetime, argparse
csv.field_size_limit(10**7)
HERE = os.path.dirname(os.path.abspath(__file__))
QDIR = os.path.join(HERE, "queries")
TODAY = datetime.date.today().isoformat()

# ---------------- connection ----------------
def _load_creds(credfile):
    env = {k: os.environ[k] for k in
           ("SNOWFLAKE_ACCOUNT","SNOWFLAKE_USER","SNOWFLAKE_PAT","SNOWFLAKE_ROLE",
            "SNOWFLAKE_WAREHOUSE","SNOWFLAKE_DATABASE","SNOWFLAKE_SCHEMA") if k in os.environ}
    if credfile and os.path.exists(credfile):
        for line in open(credfile):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
            elif line.startswith("ghp_") is False and len(line) > 20 and "SNOWFLAKE_PAT" not in env:
                env["SNOWFLAKE_PAT"] = line  # bare-token file
    missing = [k for k in ("SNOWFLAKE_ACCOUNT","SNOWFLAKE_USER","SNOWFLAKE_PAT") if not env.get(k)]
    if missing:
        sys.exit("Missing Snowflake creds: %s (set env vars or pass --creds)" % ", ".join(missing))
    return env

def connect(env):
    try:
        import snowflake.connector as sfc
    except ImportError:
        sys.exit("pip install snowflake-connector-python  (or: pip install --target=/tmp/sfpkg snowflake-connector-python && export PYTHONPATH=/tmp/sfpkg)")
    c = sfc.connect(
        account=env["SNOWFLAKE_ACCOUNT"], user=env["SNOWFLAKE_USER"],
        authenticator="PROGRAMMATIC_ACCESS_TOKEN", token=env["SNOWFLAKE_PAT"],
        region=env.get("SNOWFLAKE_REGION", "us-west-2"),
        role=env.get("SNOWFLAKE_ROLE"), warehouse=env.get("SNOWFLAKE_WAREHOUSE"),
        database=env.get("SNOWFLAKE_DATABASE"), schema=env.get("SNOWFLAKE_SCHEMA"),
        login_timeout=30)
    c.cursor().execute("alter session set timezone='America/Denver'")
    return c

BATCH = 5000  # stream rows in batches so a wide pull never loads the whole result set into memory

def run(c, sql):
    """Return an executed cursor; callers stream rows with fetchmany (never fetchall)."""
    cur = c.cursor(); cur.execute(sql)
    return cur

def prep(name, subs):
    s = open(os.path.join(QDIR, name)).read().strip().rstrip(";")
    for a, b in subs:
        s = s.replace(a, b)
    return s

def _cell(v):
    if v is None: return ""
    if isinstance(v, (datetime.datetime,)): return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, (datetime.date,)): return v.strftime("%Y-%m-%d")
    return str(v)

def _stream_rows(cur, writer):
    """Pump the cursor through a csv.writer in batches; return row count."""
    n = 0
    while True:
        batch = cur.fetchmany(BATCH)
        if not batch:
            break
        for r in batch:
            writer.writerow([_cell(v) for v in r]); n += 1
    return n

def write_csv(path, cur):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    cols = [d[0] for d in cur.description]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(cols)
        return _stream_rows(cur, w)

# wide windows (bucketing happens downstream by close/end month) -------------
DR  = [("{{Date Range Start}}", "2024-01-01"), ("{{Date Range End}}", TODAY)]
DRc = [("{{record_type_filter}}", "")]                                   # comment-only placeholder
OPP = [("{{date_start}}", "2024-01-01"), ("{{date_end}}", TODAY), ("{{ date_start }}", "2024-01-01"), ("{{ date_end }}", TODAY)]
MRR = [("{{Close Start}}", "2023-05-01"), ("{{Close End}}", TODAY), ("{{ Close Start }}", "2023-05-01"), ("{{ Close End }}", TODAY)]
EM  = [("{{ TP Date Range Start }}", "2024-01-01"), ("{{ TP Date Range End }}", TODAY)]
CS  = [("{{Date Start}}", "2025-01-01"), ("{{Date End}}", TODAY), ("{{ Date Start }}", "2025-01-01"), ("{{ Date End }}", TODAY)]
IA  = [("{{survey_start_date}}", "2025-01-01"), ("{{survey_end_date}}", TODAY), ("{{workflow_status}}", "'Completed','Abandoned'")]

def emit_embed(path, tag, cur, gz=False):
    """Reproduce a dashboard HTML embed the compute reads: a <script id=TAG>…</script> whose body is
    the CSV (gz=True → gzip+base64, as email-sla-dashboard-v10). Streamed, so wide pulls stay low-memory.
    No newline between > and body: compute slices from the first '>' after the id to the next '</'."""
    import io as _io
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    cols = [d[0] for d in cur.description]
    open_tag = '<script type="application/octet-stream" id="%s">' % tag
    if not gz:
        with open(path, "w", newline="", encoding="utf-8") as f:
            f.write(open_tag)
            w = csv.writer(f); w.writerow(cols)
            n = _stream_rows(cur, w)
            f.write("</script>")
        return n
    # gz: stream CSV → gzip temp file, then base64 that file in 3-byte-aligned chunks into the html
    tmp = path + ".csv.gz"
    with gzip.open(tmp, "wt", newline="", encoding="utf-8") as gzf:
        w = csv.writer(gzf); w.writerow(cols)
        n = _stream_rows(cur, w)
    with open(path, "w", encoding="utf-8") as f, open(tmp, "rb") as raw:
        f.write(open_tag)
        while True:
            chunk = raw.read(57 * 1024)  # multiple of 3 → base64 chunks concatenate cleanly
            if not chunk:
                break
            f.write(base64.b64encode(chunk).decode("ascii"))
        f.write("</script>")
    try: os.remove(tmp)
    except OSError: pass
    return n

# ---------------- source → artifact map ----------------
def fetch(c, keys, workdir):
    Q = os.path.join(workdir, "queries"); DV = os.path.join(workdir, "_data_v2")
    OA = os.path.join(workdir, "oa_dash", "data")
    def do(key): return (not keys) or (key in keys)
    log = []

    if do("bo"):
        log.append(("bo_sla_v11_clean.csv", write_csv(os.path.join(workdir, "bo_sla_v11_clean.csv"), run(c, prep("bo_grain_sla_v11.sql", DR + DRc)))))
    if do("adv"):
        log.append(("queries/advising_opp_data_latest.csv", write_csv(os.path.join(Q, "advising_opp_data_latest.csv"), run(c, prep("advising_opp_sla.sql", OPP)))))
    if do("byb"):
        log.append(("queries/byb_data_2024-01-01_to_%s.csv" % TODAY, write_csv(os.path.join(Q, "byb_data_2024-01-01_to_%s.csv" % TODAY), run(c, prep("byb_bo_sla_v7.sql", DR)))))
    if do("bt"):
        log.append(("queries/bt_data_2024-01-01_to_%s.csv" % TODAY, write_csv(os.path.join(Q, "bt_data_2024-01-01_to_%s.csv" % TODAY), run(c, prep("bt_bo_sla_v8.sql", DR)))))
    if do("mrr"):
        log.append(("advising_mrr_cohort_%s.csv" % TODAY, write_csv(os.path.join(workdir, "advising_mrr_cohort_%s.csv" % TODAY), run(c, prep("mrr_cohort.sql", MRR)))))
    if do("csat"):
        log.append(("queries/csat_data_2025-01-01_to_%s.csv" % TODAY, write_csv(os.path.join(Q, "csat_data_2025-01-01_to_%s.csv" % TODAY), run(c, prep("csat.sql", CS)))))
    if do("inapp"):
        log.append(("queries/inapp_data_2025-01-01_to_%s.csv" % TODAY, write_csv(os.path.join(Q, "inapp_data_2025-01-01_to_%s.csv" % TODAY), run(c, prep("inapp.sql", IA)))))
    if do("avail"):
        log.append(("_data_v2/av_pit.csv", write_csv(os.path.join(DV, "av_pit.csv"), run(c, prep("av_pit.sql", [])))))
        log.append(("_data_v2/calls_pit.csv", write_csv(os.path.join(DV, "calls_pit.csv"), run(c, prep("calls_pit.sql", [])))))
    if do("roster"):
        log.append(("_data_v2/roster_calls.csv", write_csv(os.path.join(DV, "roster_calls.csv"), run(c, prep("roster_calls.sql", [])))))
        cur = run(c, prep("roster_npr.sql", [])); cols = [d[0] for d in cur.description]
        os.makedirs(OA, exist_ok=True)
        recs = [dict(zip(cols, [_cell(v) for v in r])) for r in cur.fetchall()]  # NP&R roster is small
        json.dump(recs, open(os.path.join(OA, "roster.json"), "w"))
        log.append(("oa_dash/data/roster.json", len(recs)))
    if do("email"):
        log.append(("email-sla-dashboard-v10.html (embed)", emit_embed(os.path.join(workdir, "email-sla-dashboard-v10.html"), "__EMBED__", run(c, prep("email_sla_attp.sql", EM)), gz=True)))
    if do("ticket"):
        log.append(("ticket_sla_by_flow_v12.html (embed)", emit_embed(os.path.join(workdir, "ticket_sla_by_flow_v12.html"), "__EMBED__", run(c, prep("ticket_sla_v12.sql", DR)), gz=False)))
    if do("ready"):  # operating-metrics embed: Ready-by-1st AND New Plan cohort cancel
        log.append(("benservices_operating_metrics_dashboard_v1.html (embed)", emit_embed(os.path.join(workdir, "benservices_operating_metrics_dashboard_v1.html"), "embeddedData", run(c, prep("operating_metrics_difot.sql", [])), gz=False)))
    return log

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", default=os.path.join(HERE, "_run"))
    ap.add_argument("--through")           # accepted for symmetry; windows are wide regardless
    ap.add_argument("--only", default="")  # comma list of source keys
    ap.add_argument("--creds", default=os.path.join(HERE, "snowflake_pat.env"))
    a = ap.parse_args()
    keys = set(x.strip() for x in a.only.split(",") if x.strip())
    env = _load_creds(a.creds)
    c = connect(env)
    os.makedirs(a.workdir, exist_ok=True)
    print("materializing live → %s" % a.workdir)
    for name, n in fetch(c, keys, a.workdir):
        print("  wrote %-55s %s rows" % (name, n))
    print("done.")

if __name__ == "__main__":
    main()
