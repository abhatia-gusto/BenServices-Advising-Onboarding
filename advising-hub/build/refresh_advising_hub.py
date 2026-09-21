#!/usr/bin/env python3
"""Benefits Advising Hub (v-next, 3-tab) — end-to-end refresh + publish (one command).

Mirrors refresh_advising_performance.py: find_mount(), chained steps, --no-publish.

Chain:
  1. venv         — ensure /tmp/snowvenv + snowflake-connector-python.
  2. pull         — run every hub_queries/*.sql (live cohort window) via Snowflake,
                    writing CSVs exactly where assemble_vnext.py + patches expect them
                    (_renewal_full/out, _renewal_vnext/out) per hub_queries/catalog.json.
  3. assemble     — run _renewal_vnext/assemble_vnext.py (now TODAY=date.today()); it reads
                    the base _renewal_full/advising_hub_full_data.json + the fresh CSVs and
                    (over)writes _renewal_vnext/advising_vnext_data.json. Prior JSON is backed
                    up (timestamped) BEFORE this step so it can be used as the freeze source.
  4. merge/freeze — overlay the freshly-assembled data onto the prior published dataset:
                    OPEN / Pending-Fulfillment opps are fully refreshed (per-line enrollment &
                    MRR recomputed from the MRR-dash price book, rating/survey/in-app/tickets/
                    case-activity, time_in_erc, open_tickets); CLOSED opps carry forward their
                    frozen snapshot (final premium d_fin/pr_fin, MRR before/after, enrolled
                    before->after, close date, outcome, funding_after) and only refresh
                    CSAT / in-app / status. Builder-only fields with no saved query (see
                    hub_queries/catalog.json -> carry_forward_not_reconstructed) are carried
                    forward per-opp so the built HTML always has every field it reads.
  5. build        — run build_advising_hub.py -> advising_hub_vnext.html.
  6. verify       — node --check the app <script>; PII scan (email/phone/ssn) must be 0;
                    opp count > 15000; embedded HUB JSON parses; compute at_risk_high (High
                    tier via the builder's exact riskOf logic, run under node) + mrr_total.
                    Any failure => DO NOT publish; raise.
  7. publish      — push_html.py advising_hub_vnext.html benefits-advising-hub <SHARESOME_PUBLISH_TOKEN from env>
                    (skipped with --no-publish).
  8. status       — print + write advising_hub_refresh_status.json for the scheduler DM.

Run:  python3 refresh_advising_hub.py [--no-publish]
"""
import os, sys, re, json, time, shutil, datetime, subprocess, pathlib, traceback

# ----------------------------------------------------------------- paths / config
def find_mount():
    for p in pathlib.Path('/sessions').glob('*/mnt/BenOps Dashboard Co-Work'):
        return str(p)
    return os.path.dirname(os.path.abspath(__file__))

HERE   = find_mount()
FULL   = os.path.join(HERE, "_renewal_full")
VNEXT  = os.path.join(HERE, "_renewal_vnext")
HQ     = os.path.join(HERE, "hub_queries")
DATA   = os.path.join(VNEXT, "advising_vnext_data.json")
HTML   = os.path.join(HERE, "advising_hub_vnext.html")
BUILDER= os.path.join(HERE, "build_advising_hub.py")
STATUS = os.path.join(HERE, "advising_hub_refresh_status.json")
PATENV = os.path.join(HERE, "snowflake_pat.env")
VENV_PY= "/tmp/snowvenv/bin/python3"

# Rolling cohort window (LF-parity): FIXED trailing anchor + rolling end = current month + 5.
# Keeps recent closed history (nothing is dropped) AND always covers the next 5 months of
# upcoming renewals. Recomputed every run, so it rolls forward automatically on the 1st.
# (Mirrors lf_pipeline/lf_daily_refresh.py's WIN_START anchor + _win_end() pattern.)
COHORT_ANCHOR = "2026-07-01"        # dataset floor; advance later if the window grows too large
COHORT_MONTHS_AHEAD = 5
def _cohort_window(anchor=COHORT_ANCHOR, months_ahead=COHORT_MONTHS_AHEAD):
    a = datetime.date.fromisoformat(anchor)
    t = datetime.date.today()
    em = t.month - 1 + months_ahead; ey = t.year + em // 12; emm = em % 12 + 1
    end = datetime.date(ey, emm, 1)
    out = []; y, m = a.year, a.month
    while (y, m) <= (end.year, end.month):
        out.append(f"{y}-{m:02d}-01")
        m += 1
        if m > 12: m = 1; y += 1
    return out
COHORT_WINDOW = _cohort_window()
COHORT_DATES = ",".join(f"'{d}'" for d in COHORT_WINDOW)

CLOSED_TABS = {"Closed"}
# Builder-consistent stage->tab classification (build_advising_hub.py TAB_CLOSED / tabOf).
CLOSED_STAGES = {"Closed Won", "Closed Lost", "Order Lost", "Closed Admin"}
CLOSED_LOSS   = {"Closed Lost", "Order Lost", "Closed Admin"}
def _tab_of(stage):
    s = stage or ""
    return "Closed" if s in CLOSED_STAGES else ("Pending Fulfillment" if s == "Pending Fulfillment" else "Open")
def _truthy(x):
    return str(x).strip().lower() in ("true", "1", "y", "yes", "t")
# benefit-type -> label for the carriers_enrolled summary (mirrors assemble_full BT_ORDER labels)
BT_LABEL = {"medical":"Medical","dental":"Dental","vision":"Vision","life":"Life",
            "long_term_disability":"LTD","short_term_disability":"STD","fsa":"FSA","dca":"DCA","hsa":"HSA",
            "voluntary_life":"VLife","voluntary_long_term_disability":"VLTD","voluntary_short_term_disability":"VSTD"}
# MRR-dash price book (per enrolled EE / mo) — mirrors _renewal_vnext/repull_patch.py
PRICE = {'dental':6.58,'vision':1.20,'life':1.21,'long_term_disability':1.65,
         'short_term_disability':1.82,'fsa':4.00,'dca':4.00,'hsa':2.50,'voluntary_life':5.28}
MED_FI, MED_LF = 33.24, 46.53
BT10 = set(PRICE) | {'medical'}

# fields assemble_vnext.py (re)computes for every opp — overlaid fresh
OVERLAY = ["sf_opp_url","hippo_url","company","contribution","bo_url","bo_status",
           "tab","outcome","closed_on","rating_region","survey_answered","survey_answers",
           "alt_requested","alt_req_date","alt_pub_count","alt_pub_first","alt_pub_last",
           "alt_pub_carriers","alt_created","in_app","in_app_comment","in_app_date","surveys_12mo",
           "tickets_to_advising","tickets_list","mrr_before","mrr_after","intro_call",
           "intro_call_date","intro_connect","connect_date","last_update",
           "last_call_date","last_connect_date","last_call_disp","case_summary",
           "csat_comment"]
# closed = frozen: restore these from the prior published snapshot after the overlay
# DEPRECATED (2026-09): Closed opps now refresh their Snowflake-warehouse value fields daily
# (mrr/enrollees/lines etc. are re-sourced live). FROZEN_CLOSED is retained only for reference;
# it is no longer applied. See SF_FROZEN_FIELDS below for what actually stays frozen on Closed.
FROZEN_CLOSED = ["mrr","mrr_before","mrr_after","enrollees","funding_after","closed_on",
                 "outcome","inferred_close_date","lines"]

# The ONLY fields that stay frozen at close for Closed opps: every Salesforce-sourced field.
# Snowflake-warehouse fields all refresh daily; these never auto-update once an opp is Closed
# (they carry forward the prior published value). Two families:
#   - SF-MCP (pulled from the Salesforce MCP by Phase A): intro_call, recert_status,
#     sep_risk_level, packets.
#   - SF activity (sf_activity.sql / cases.sql — Salesforce data, even though it arrives via
#     the Snowflake SF mirror): last_update/contact/call/connect fields + case_summary narrative.
# Keyed on the LIVE tab each run, so a Closed opp that reopens (-> Open/PF) drops the freeze and
# these refresh again automatically (SF-MCP catches up on the next Phase A pull).
SF_FROZEN_FIELDS = [
    # SF-MCP
    "intro_call", "intro_call_date", "recert_status", "sep_risk_level",
    "packets_files", "packet_carriers",
    # SF activity (+ derived mirrors)
    "intro_connect", "intro_connect_date", "connect_date",
    "last_update", "last_update_date", "last_call_date", "last_connect_date",
    "last_call_disp", "last_contact_date", "case_summary",
]

STEPS = []
# queries that MUST succeed; everything else, on failure, carries forward from the
# prior published dataset (a resilient daily refresh must survive upstream SF-mirror
# schema drift without going dark).
CRITICAL_Q = {"cohort", "mrr", "premium_lines"}
FAILED_PATH = os.path.join(HERE, "hub_queries", ".pull_failed.json")
# query id -> the assemble_vnext OVERLAY fields it feeds (skip overlay when it fails)
Q_OVERLAY = {
    "rating_region": ["rating_region"],
    "survey_answers": ["survey_answered","survey_answers"],
    "surveys_12mo": ["surveys_12mo"],
    "inapp": ["in_app","in_app_comment","in_app_date"],
    "tickets": ["tickets_to_advising","tickets_list"],
    "alt": ["alt_requested","alt_req_date","alt_pub_count","alt_pub_first","alt_pub_last","alt_pub_carriers","alt_created"],
    "sf_activity": ["last_update","intro_connect","connect_date","last_call_date","last_connect_date","last_call_disp","case_summary","intro_call","intro_call_date"],
    "cases": ["case_summary"],
    "mrr": ["mrr_before","mrr_after"],
}

def step(name):
    """decorator-ish context: time a step, record ok/ms/error, re-raise on failure."""
    class _S:
        def __enter__(self):
            self.t0 = time.time(); print(f"\n=== {name} ===", flush=True); return self
        def __exit__(self, et, ev, tb):
            ms = int((time.time()-self.t0)*1000)
            rec = {"name": name, "ok": et is None, "ms": ms}
            if et is not None:
                rec["error"] = "".join(traceback.format_exception_only(et, ev)).strip()
            STEPS.append(rec)
            print(f"--- {name}: {'ok' if et is None else 'FAILED'} ({ms} ms)", flush=True)
            return False
    return _S()

def _rm(p):
    try: os.remove(p)
    except Exception: pass

def med_price(fund):
    return MED_LF if (fund and 'level' in str(fund).lower()) else MED_FI

def fnum(x):
    try: return float(x)
    except: return None

def _dparse(s):
    if not s or str(s) in ("None","null",""): return None
    s = str(s).split("T")[0].split(" ")[0]
    try: return datetime.date.fromisoformat(s)
    except Exception: return None

def _daysbetween(a, b):
    da, db = _dparse(a), _dparse(b)
    if not da or not db: return None
    return (db - da).days

# rate ACT/EST/STS -> (rate_increase_pct, rate_status)  [verbatim _renewal_full/assemble_full.py logic]
def _rate_map(rr):
    if not rr: return (None, "no medical")
    act = fnum(rr.get("ACT")); est = fnum(rr.get("EST")); sts = rr.get("STS") or ""
    if act is not None: return (round(act*100,1), "computed")
    if est is not None: return (round(est*100,1), "estimate ("+(sts or "no successor")+")")
    return (None, (sts or "no medical"))

def _lf_band(p):   # repull_patch.py bands (p is a fraction)
    if p is None: return None
    if p > 0.10: return "High"
    if p >= 0.05: return "Medium"
    if p > 0: return "Low"
    return "No"

def _lf_quote_txt(x):
    if not x: return None
    rp = int(fnum(x.get("HAS_RATE_PDF")) or 0); rec = int(fnum(x.get("HAS_LF_REC")) or 0)
    if rp and rec: return "LF plan available — rate PDF + recommendation"
    if rp: return "LF plan available — rate PDF"
    if rec: return "LF plan available — recommendation"
    return None

# ----------------------------------------------------------------- steps
def ensure_venv():
    if not os.path.exists(VENV_PY):
        subprocess.run(["python3","-m","venv","/tmp/snowvenv"], check=True)
        subprocess.run([VENV_PY,"-m","ensurepip"], check=True)
    try:
        subprocess.run([VENV_PY,"-c","import snowflake.connector"], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        subprocess.run([VENV_PY,"-m","pip","install","-q","snowflake-connector-python"], check=True)

def _connect():
    sys.path.insert(0, "/tmp/snowvenv/lib/python3.10/site-packages")
    import snowflake.connector as sf
    raw = open(PATENV).read()
    tok = re.search(r'(?:SNOWFLAKE_PAT|PAT)\s*=\s*(\S+)', raw).group(1).strip().strip('"').strip("'")
    return sf.connect(account="GUSTO-WAREHOUSE", user="aman.bhatia@gusto.com",
        authenticator="PROGRAMMATIC_ACCESS_TOKEN", token=tok, region="us-west-2",
        warehouse="GUSTIE_ADHOC_WH", database="DATA_WAREHOUSE_RC1")

def run_queries(resume=False):
    import csv
    cat = json.load(open(os.path.join(HQ, "catalog.json")))
    # non-resume (daily) always re-runs every query, so stale .done markers are ignored
    # by the skip check below; we do not delete them (this mount forbids unlink).
    con = None; cur = None; failed = []
    try:
        for q in cat["queries"]:
            out = os.path.join(HERE, q["out_csv"]); os.makedirs(os.path.dirname(out), exist_ok=True)
            if resume and os.path.exists(out+".done") and os.path.exists(out) and os.path.getsize(out) > 0:
                print(f"  {q['id']:20s} -> SKIP (done)", flush=True); continue
            if con is None:
                con = _connect(); cur = con.cursor()
            sql = open(os.path.join(HQ, q["file"])).read().replace("{{cohort_dates}}", COHORT_DATES)
            try:
                t0 = time.time(); cur.execute(sql)
                cols = [d[0] for d in cur.description]
                n = 0
                # write directly to out (truncate-in-place); this mount forbids unlink,
                # so a .tmp->rename-over-existing would fail on a daily overwrite.
                with open(out,"w",newline="") as fh:
                    w = csv.writer(fh); w.writerow(cols)
                    while True:
                        rows = cur.fetchmany(5000)
                        if not rows: break
                        for r in rows: w.writerow(["" if x is None else str(x) for x in r]); n += 1
                try: open(out+".done","w").close()
                except Exception: pass
                print(f"  {q['id']:20s} -> {q['out_csv']:36s} {n:>7d} rows  ({int((time.time()-t0)*1000)} ms)", flush=True)
            except Exception as e:
                failed.append(q["id"])
                msg = "".join(traceback.format_exception_only(type(e), e)).strip().splitlines()[-1]
                print(f"  {q['id']:20s} -> WARN failed ({'CRITICAL' if q['id'] in CRITICAL_Q else 'carry-forward'}): {msg}", flush=True)
                if not os.path.exists(out): open(out,"w").close()   # placeholder so assemble won't crash
                # a dropped cursor after an error can poison the session; reconnect
                try: cur.close(); con.close()
                except Exception: pass
                con = None; cur = None
        json.dump(failed, open(FAILED_PATH,"w"))
        crit = [f for f in failed if f in CRITICAL_Q]
        if crit:
            raise RuntimeError(f"critical query/queries failed: {crit}")
        if failed:
            print(f"  NOTE: {len(failed)} non-critical query(ies) failed -> carried forward: {failed}", flush=True)
    finally:
        if cur:
            try: cur.close()
            except Exception: pass
        if con:
            try: con.close()
            except Exception: pass

def lf_classifier():
    """OPTIONAL, NOT-PORTABLE: refresh the local LF-signal classifier (reason codes for the
    separate LF-conversion dashboard), mirroring lf_refresh.py. The four hub LF fields
    (lf_savings_pct/band/quote/in_alt) are Snowflake-derived and DO NOT need this. Runs only
    when ANTHROPIC_API_KEY + Salesforce creds + the classifier's id list are present on this
    machine; otherwise it is skipped. Never fatal to the hub refresh."""
    clf  = os.path.join(HERE, "lf_signal_classifier.py")
    ids  = os.path.join(HERE, "all_ids.txt")
    have_creds = bool(os.environ.get("ANTHROPIC_API_KEY")) and (
        os.environ.get("SF_SESSION_ID") or os.environ.get("SF_USERNAME"))
    if not (os.path.exists(clf) and os.path.exists(ids) and have_creds):
        print("  LF classifier: SKIP (headless / no ANTHROPIC_API_KEY+SF creds). "
              "Hub LF fields are Snowflake-derived and unaffected.", flush=True)
        return
    try:
        subprocess.run([sys.executable, clf, "--ids", ids], cwd=HERE, check=False, timeout=1800)
        print("  LF classifier: ran (signal_enrich.json refreshed).", flush=True)
    except Exception as e:
        print(f"  LF classifier: WARN non-fatal ({e}); continuing.", flush=True)

def backup_prior():
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = DATA + f".bak_refresh_{ts}"
    shutil.copy2(DATA, bak)
    print("  prior backed up ->", os.path.basename(bak), flush=True)
    return bak

def run_assemble():
    env = os.environ.copy()
    r = subprocess.run([VENV_PY, os.path.join(VNEXT, "assemble_vnext.py")], cwd=HERE, env=env)
    if r.returncode != 0:
        raise RuntimeError("assemble_vnext.py failed")

def run_base_rebuild():
    """Phase-1 durability: rebuild the FULL base (_renewal_full/advising_hub_full_data.json) over the
    rolling cohort window EVERY run, so opps newly entering the window (future renewal months) are
    present in the base with all base-static fields instead of being blank-seeded by merge_freeze.
    Re-pulls the self-rolling base-only queries (contrib, bo) fresh, then re-assembles the base.
    Resilient by design: a failed base-only pull keeps the prior CSV; a failed base rebuild restores
    the prior base JSON and lets the pipeline continue on it (never crashes the daily refresh)."""
    import shutil
    env = os.environ.copy(); env["PATENV"] = os.path.join(HERE, "snowflake_pat.env")
    for name in ("contrib", "bo"):
        sqlp = os.path.join(FULL, "sql", f"{name}.sql")
        outp = os.path.join(FULL, "out", f"{name}.csv"); tmpp = outp + ".tmp"
        try:
            r = subprocess.run([VENV_PY, os.path.join(FULL, "q.py"), sqlp, tmpp], cwd=HERE, env=env)
            if r.returncode == 0 and os.path.exists(tmpp) and os.path.getsize(tmpp) > 0:
                os.replace(tmpp, outp); print(f"  base pull {name}: ok", flush=True)
            else:
                print(f"  WARN base pull {name} rc={r.returncode}; keeping prior {name}.csv", flush=True)
        except Exception as e:
            print(f"  WARN base pull {name}: {e}; keeping prior {name}.csv", flush=True)
    base = os.path.join(FULL, "advising_hub_full_data.json"); safe = base + ".prerebuild"
    try:
        if os.path.exists(base): shutil.copyfile(base, safe)
        r = subprocess.run([VENV_PY, os.path.join(FULL, "assemble_full.py")], cwd=HERE, env=env)
        if r.returncode != 0: raise RuntimeError(f"assemble_full rc={r.returncode}")
        print("  base rebuild: ok", flush=True)
    except Exception as e:
        if os.path.exists(safe): shutil.copyfile(safe, base)
        print(f"  WARN base rebuild failed ({e}); restored prior base — continuing on prior base", flush=True)

def _rd(path):
    import csv; csv.field_size_limit(10**7)
    return list(csv.DictReader(open(path)))

def merge_freeze(prior_path):
    import csv, collections
    prior = {r["opp_id18"]: r for r in json.load(open(prior_path))}
    assembled = json.load(open(DATA))
    failed = json.load(open(FAILED_PATH)) if os.path.exists(FAILED_PATH) else []
    # --- LF-parity de-freeze: stage/tab + cohort SCALARS re-sourced LIVE from today's
    # Snowflake cohort.csv for EVERY opp (Open / PF / Closed), instead of the frozen base.
    # This is the fix for the "stage frozen at base-build" bug (opps stuck on a stale tab).
    # Mirrors _renewal_full/assemble_full.py derivations exactly. Closed still keeps its
    # close-time SNAPSHOT (FROZEN_CLOSED below); only classification + cheap Snowflake
    # scalars refresh. If cohort.csv lacks an opp (out of window), prior value carries forward.
    cohort_fresh = {}
    try:
        for r in _rd(os.path.join(FULL, "out", "cohort.csv")):
            k = r.get("SFDC_OBJECT_ID")
            if k: cohort_fresh[k] = r
    except Exception as e:
        print(f"  WARN cohort.csv unreadable for live stage refresh ({e}); stage carries forward.", flush=True)
    print(f"  live stage/scalars source: cohort.csv has {len(cohort_fresh)} opps", flush=True)
    skip_fields = set()
    for qid in failed: skip_fields.update(Q_OVERLAY.get(qid, []))
    cases_failed = "open_cases_by_type" in failed
    erc_failed   = "time_in_erc" in failed
    otk_failed   = "open_tickets" in failed
    prem_failed  = "premium_lines" in failed   # critical; won't reach here if so
    if skip_fields:
        print(f"  carry-forward fields (failed pulls {failed}): {sorted(skip_fields)}", flush=True)

    # fresh reproducible pulls
    enr = {}; selany = {}; medfund = {}
    for e in _rd(os.path.join(VNEXT,"out","premium_lines.csv")):
        oid = e["OPP"]; bt = e["BENEFIT_TYPE"]
        enr[(oid,bt)] = e
        selany[oid] = selany.get(oid,0) or int(fnum(e.get("HAS_ANY_SELECTED")) or 0)
        if bt == "medical": medfund[oid] = e.get("AFTER_FUND") or None
    erc = {r["OPP"]: fnum(r.get("TIME_IN_ERC")) for r in _rd(os.path.join(VNEXT,"out","time_in_erc.csv"))}
    otk = {r["OPP"]: (int(fnum(r.get("OPEN_TICKETS")) or 0), int(fnum(r.get("OPEN_TICKETS_PAST_SLA")) or 0))
           for r in _rd(os.path.join(VNEXT,"out","open_tickets.csv"))}
    cases = collections.defaultdict(dict)
    for r in _rd(os.path.join(VNEXT,"out","opencases_bytype.csv")):
        ct = int(fnum(r.get("OPEN_CT")) or 0)
        if ct > 0: cases[r["OPP"]][r["RTS"]] = cases[r["OPP"]].get(r["RTS"],0) + ct

    # reconstructed live pulls (B/C/D/E). On failure -> carry forward (skip overlay).
    email_failed = "email_recency" in failed
    sigs_failed  = "sf_open_signals" in failed
    premd_failed = "premium_lines_delta" in failed
    emailr = {} if email_failed else {r["OPP"]:r for r in _rd(os.path.join(VNEXT,"out","email_recency.csv"))}
    sigs   = {} if sigs_failed  else {r["OPP"]:r for r in _rd(os.path.join(VNEXT,"out","sf_open_signals.csv"))}
    premd  = {}
    if not premd_failed:
        for r in _rd(os.path.join(VNEXT,"out","premium_delta.csv")):
            premd[(r["OPP"], r["BENEFIT_TYPE"])] = r

    # Sept-10 reconstruction: rate index, RFD dwell, LF, auto-finalize, rec timing, email due.
    # All Open/PF-live, Closed-frozen (carry forward on pull failure).
    rate_failed = "rate_index"    in failed
    rfd_failed  = "time_in_rfd"   in failed
    lf_failed   = "lf"            in failed
    auto_failed = "auto_finalize" in failed
    rect_failed = "rec_timing"    in failed
    edue_failed = "email_due"     in failed
    ratev = {} if rate_failed else {r["OPP"]: r for r in _rd(os.path.join(VNEXT,"out","rate_index.csv"))}
    pyoy_failed = "premium_yoy" in failed
    pyoyv = {} if pyoy_failed else {r["OPP"]: r for r in _rd(os.path.join(VNEXT,"out","premium_yoy.csv"))}
    rfdv  = {} if rfd_failed  else {r["OPP"]: fnum(r.get("TIME_IN_RFD")) for r in _rd(os.path.join(VNEXT,"out","time_in_rfd.csv"))}
    lfv   = {} if lf_failed   else {r["OPP"]: r for r in _rd(os.path.join(VNEXT,"out","lf.csv"))}
    autov = {} if auto_failed else {r["OPP"]: r for r in _rd(os.path.join(VNEXT,"out","auto_finalize.csv"))}
    rectv = {} if rect_failed else {r["OPP"]: r for r in _rd(os.path.join(VNEXT,"out","rec_timing.csv"))}
    eduev = {} if edue_failed else {r["OPP"]: r for r in _rd(os.path.join(VNEXT,"out","email_due.csv"))}

    # Per-opp SLA fields (Met/Missed/na), Open/PF-live, Closed-frozen (carry forward on fail).
    # ticket_sla -> OA->Benefits-Advising ticket resolution SLA (perf-dash Flow-4a 5-day).
    # email_sla  -> inbound-email response SLA (perf-dash AB Email SLA v8, 240 HOOP-min).
    tsla_failed = "ticket_sla" in failed
    esla_failed = "email_sla"  in failed
    tslav = {} if tsla_failed else {r["OPP"]: (r.get("TICKET_SLA") or "na") for r in _rd(os.path.join(VNEXT,"out","ticket_sla.csv"))}
    eslav = {} if esla_failed else {r["OPP"]: r for r in _rd(os.path.join(VNEXT,"out","email_sla.csv"))}

    # canonical CUSTOMER auto-renewal from Snowplow (confirm-default-and-skip). Open/PF-live,
    # Closed frozen (carry forward). Replaces the old REASON_FOR_ADVISING derivation.
    arv_failed = "auto_renewal" in failed
    arv = {} if arv_failed else {r["OPP"]: r for r in _rd(os.path.join(VNEXT,"out","auto_renewal.csv"))}
    # fresh base-derived pulls that used to be carry-forward-only (went stale/null): extras + sla.
    def _rd_safe(p):
        try: return _rd(p) if os.path.exists(p) and os.path.getsize(p) > 0 else []
        except Exception: return []
    extrasv = {r.get("SFDC_OBJECT_ID"): r for r in _rd_safe(os.path.join(FULL,"out","extras.csv"))}
    slav    = {r.get("SFDC_OBJECT_ID"): r for r in _rd_safe(os.path.join(FULL,"out","sla.csv"))}
    def _slam(v): return v if v in ("Met","Missed") else "na"

    # --- Salesforce MCP live fields (NOT in the Snowflake mirror) ---
    # intro_call/intro_call_date (SF Case.Intro_Call_Completed__c), recert_status
    # (SF Ticket__c.Recert_Status__c), packets_files/packet_carriers (SF ContentDocumentLink
    # renewal packets). These 3 CSVs are produced each morning by the TASK ORCHESTRATOR via
    # the Salesforce MCP (see sf_mcp_pull_spec.md / hub_queries/catalog.json -> salesforce_mcp),
    # NOT by this python. Open/PF opps present in a CSV are refreshed live; anything absent
    # (incl. a headless python-only run with no CSVs) carries forward the prior value, and
    # Closed opps always stay frozen.
    def _rd_opt(p):
        return _rd(p) if (os.path.exists(p) and os.path.getsize(p) > 0) else []
    OUTV = os.path.join(VNEXT, "out")
    sfmcp_intro = {r["opp_id18"]: ((r.get("intro_call") or None), (r.get("intro_call_date") or None))
                   for r in _rd_opt(os.path.join(OUTV, "sf_mcp_intro.csv"))}
    sfmcp_recert = {r["opp_id18"]: (r.get("recert_status") or None)
                    for r in _rd_opt(os.path.join(OUTV, "sf_mcp_recert.csv"))}
    sfmcp_sep = {r["opp_id18"]: (r.get("sep_risk_level") or None)
                 for r in _rd_opt(os.path.join(OUTV, "sf_mcp_sep.csv"))}
    sfmcp_pk = {r["opp_id18"]: ((r.get("packets_files") or None), (r.get("packet_carriers") or None))
                for r in _rd_opt(os.path.join(OUTV, "sf_mcp_packets.csv"))}
    if sfmcp_intro or sfmcp_recert or sfmcp_sep or sfmcp_pk:
        print(f"  SF-MCP live fields: intro={len(sfmcp_intro)} recert={len(sfmcp_recert)} "
              f"sep={len(sfmcp_sep)} packets={len(sfmcp_pk)}", flush=True)
    else:
        print("  SF-MCP live fields: no CSVs present -> all 3 groups carry forward (Open/PF)", flush=True)

    TODAY_ISO = datetime.date.today().isoformat()
    EMAIL_DUE_PENDING = ("Pending response", "Pending (Missed SLA - aging)")
    def _iround(x):
        v = fnum(x); return int(round(v)) if v is not None else None
    PR_INT = [("pr_exp_e","PR_EXP_E"),("pr_exp_n","PR_EXP_N"),("pr_succ","PR_SUCC"),
              ("pr_dflt","PR_DFLT"),("pr_sel","PR_SEL"),("pr_fin","PR_FIN")]
    PR_DEC = [("d_succ","D_SUCC"),("d_dflt","D_DFLT"),("d_sel","D_SEL"),("d_fin","D_FIN")]

    def cross_sentence(d):
        if not d: return None
        items = sorted(d.items(), key=lambda kv:(-kv[1], kv[0]))
        return "Account open cases (all types): " + " + ".join(
            f"{c} {rts[:-5] if rts.endswith(' Case') else rts}" for rts,c in items) + "."

    stat = {"open_pf":0, "closed":0, "carried_new":0, "lines_recomputed":0}
    out = []
    for a in assembled:
        oid = a["opp_id18"]
        p = prior.get(oid)
        # Never-enriched opps — brand-new to the dataset, OR previously blank-seeded when they first
        # entered the rolling window (identified by a missing data_asof) — have no real prior row to
        # carry forward. Build them from the freshly-assembled base row `a` so static/identity fields
        # (sf_opp_url, hippo_url, company, lines, etc.) are populated instead of inherited-blank.
        # Established opps (incl. Closed) keep their prior row so carry-forward / close-time freeze holds.
        hollow = (p is None) or (not p.get("data_asof"))
        if hollow: stat["carried_new"] += 1
        p = p or {}
        row = dict(a) if hollow else dict(p)            # inherit fresh base (hollow) or prior (carry-forward)
        for k in OVERLAY:                               # fresh assembler overlay (skip failed pulls)
            if k in skip_fields: continue               # keep prior value
            row[k] = a.get(k)
        # alt_published (COUNT) + alt_published_date were base-only / carry-forward -> went stale/stuck
        # (e.g. an opp that publishes alternates AFTER the base build shows alt_published=0 next to a real
        # alt_published_date). Sync BOTH to the FRESH alt query fields (alt_pub_count / alt_pub_first,
        # refreshed in OVERLAY above) so the count and date always agree and can't drift.
        row["alt_published"] = int(fnum(row.get("alt_pub_count")) or 0)
        if row.get("alt_pub_first"):
            row["alt_published_date"] = row["alt_pub_first"]
        # --- stage/tab + cohort scalars: LIVE from today's cohort.csv for every opp ---
        cf = cohort_fresh.get(oid)
        if cf:
            stg = cf.get("STATUS") or a.get("stage") or p.get("stage")
            row["stage"]   = stg
            row["closed"]  = stg in CLOSED_STAGES
            row["pe"]      = (cf.get("PE") or None)
            row["advisor"] = (cf.get("OWNER_NAME") or None)
            rd_ = (cf.get("RENEWAL_DATE") or "")[:10]
            if rd_: row["renewal_date"] = rd_
            dtr = fnum(cf.get("DAYS_TO_RENEWAL")); row["days_to_renewal"] = int(dtr) if dtr is not None else row.get("days_to_renewal")
            dis = fnum(cf.get("DAYS_IN_STAGE"));   row["days_in_stage"]  = int(dis) if dis is not None else row.get("days_in_stage")
            blk = (cf.get("ADVISING_BLOCKED_REASON") or "") or None
            row["blocked_reason"] = blk
            row["bor_term"] = "Y" if re.search(r"terminat|bor|broker of record", blk or "", re.I) else "N"
            row["sep"]      = "Y" if _truthy(cf.get("SPECIAL_ENROLLMENT")) else "N"
            if cf.get("COHORT"): row["cohort"] = cf.get("COHORT")
            tab = _tab_of(stg)
        else:
            row["stage"] = a.get("stage") or p.get("stage")
            tab = _tab_of(row.get("stage"))
        row["tab"] = tab
        # in-app numeric mirror the builder reads (derive from whatever in_app resolved to)
        row["inapp_current"] = fnum(row.get("in_app"))
        # Derive builder-read fields that have no direct query column from FRESH fields (all opps) so
        # they can't sit stuck on the base value: survey count, timeline dates, contact-date mirrors.
        row["all_survey_count"] = len(row.get("surveys_12mo") or [])
        if row.get("renewal_date"):  row["tl_renewal"]       = row["renewal_date"]
        if row.get("alt_pub_first"): row["tl_alt_published"] = row["alt_pub_first"]
        if row.get("alt_req_date"):  row["tl_alt_requested"] = row["alt_req_date"]
        if row.get("selection_deadline"): row["tl_selection"] = row["selection_deadline"]
        if row.get("connect_date"):  row["intro_connect_date"] = row["connect_date"]
        if row.get("last_update"):   row["last_update_date"]   = row["last_update"]
        # ALT SLA is a requested->published turnaround; with no alternate request it does not
        # apply -> force 'na' (never 'Missed'). alt_requested is refreshed in the OVERLAY above.
        if (row.get("alt_requested") or "N") != "Y":
            row["alt_sla"] = "na"

        # Snowflake value-refresh now runs for EVERY opp (Open / PF / Closed). Closed opps refresh
        # their Snowflake-warehouse fields daily; Salesforce-sourced fields are frozen for Closed in
        # the post-block below (SF_FROZEN_FIELDS). Decision keyed on the LIVE tab each run, so a
        # Closed opp that reopens re-enters full refresh automatically (no persisted "closed" latch).
        is_open_pf = tab not in CLOSED_TABS
        stat["open_pf" if is_open_pf else "closed"] += 1
        if True:                                        # value refresh for all opps (kept indented)
            # LF savings/quote — Open/PF only; Closed keeps its frozen close snapshot (carry forward
            # the value it had when it closed). Dashboard-aligned census engine (queries/lf.sql).
            if not lf_failed:
                _lfx = lfv.get(oid)
                _lfp = fnum(_lfx.get("LF_SAVINGS_PCT")) if _lfx else None
                row["lf_savings_pct"] = _lfp
                row["lf_savings_band"] = _lf_band(_lfp)
                row["lf_quote"] = _lf_quote_txt(_lfx)
                row["lf_in_alt"] = ("Y" if (_lfx and int(fnum(_lfx.get("HAS_LF_ALT")) or 0)) else "N")
            has_sel = bool(selany.get(oid,0))
            # Line skeletons (benefit types + carrier/state): Open/PF take them FRESH from the
            # freshly-assembled base row (`a`), so opps newly entering the rolling window (e.g. a
            # future renewal month) get their lines built — and thus MRR / enrollment / carrier —
            # instead of inheriting the prior row's empty lines[]. Closed keep the prior frozen
            # close-time lines (carry forward); their behavior is unchanged. The per-line enrollment
            # + MRR below are still recomputed from today's premium_lines.csv for whatever lines exist.
            _lsrc = a if (is_open_pf or hollow) else p
            lines = [dict(l) for l in (_lsrc.get("lines") or [])]
            mrr_b = 0.0; mrr_a = 0.0; med_enr_b = None
            for l in lines:
                bt = l.get("benefit_type")
                if bt not in BT10:
                    if l.get("mrr_before") is not None: mrr_b += l["mrr_before"]
                    if has_sel and l.get("mrr_after") is not None: mrr_a += l["mrr_after"]
                    continue
                e = enr.get((oid,bt))
                if e:
                    eb = int(fnum(e.get("ENR_BEFORE")) or 0); ea = int(fnum(e.get("ENR_AFTER")) or 0)
                    hb = bool(int(fnum(e.get("HAS_BEFORE")) or 0)); ha = bool(int(fnum(e.get("HAS_AFTER")) or 0))
                    bf = e.get("BEFORE_FUND") or None; af = e.get("AFTER_FUND") or None
                else:
                    eb = ea = 0; hb = ha = False; bf = af = None
                pb = med_price(bf) if bt=="medical" else PRICE[bt]
                pa = med_price(af) if bt=="medical" else PRICE[bt]
                l["enr_before"] = eb
                l["mrr_before"] = round(eb*pb,2) if hb else 0.0
                l["enr_after"]  = ea
                l["mrr_after"]  = (round(ea*pa,2) if ha else 0.0) if has_sel else None
                mrr_b += l["mrr_before"]
                if has_sel and l["mrr_after"] is not None: mrr_a += l["mrr_after"]
                if bt=="medical": med_enr_b = eb if e else None
                stat["lines_recomputed"] += 1
            row["lines"] = lines
            row["num_lines"] = len(lines)
            # carriers_enrolled summary (was base-only / stuck) derived from the FRESH per-line carriers
            _ce = []
            for _l in lines:
                _c = _l.get("carrier")
                if not _c: continue
                _st = _l.get("state"); _n = _l.get("enr_after")
                if _n is None: _n = _l.get("enr_before")
                _lab = BT_LABEL.get(_l.get("benefit_type"), (_l.get("benefit_type") or "").title())
                _ce.append(f"{_lab}: {_c}{' ('+_st+')' if _st else ''} n={_n if _n is not None else 0}")
            row["carriers_enrolled"] = " · ".join(_ce) or None
            row["mrr"] = round(mrr_b,2); row["mrr_before"] = round(mrr_b,2)
            row["mrr_after"] = round(mrr_a,2) if has_sel else None
            row["enrollees"] = med_enr_b
            if oid in medfund: row["funding_after"] = medfund[oid]
            # fresh derived pulls (carry forward if the pull failed)
            if not erc_failed: row["time_in_erc"] = erc.get(oid)
            if not otk_failed:
                ot = otk.get(oid, (0,0)); row["open_tickets"] = ot[0]; row["open_tickets_past_sla"] = ot[1]
            if not cases_failed:
                od = collections.OrderedDict(sorted(cases.get(oid,{}).items(), key=lambda kv:(-kv[1], kv[0])))
                row["open_cases_by_type"] = od; row["open_cases_total"] = sum(od.values())
                cs = cross_sentence(od); ex = row.get("case_summary")
                if cs: row["case_summary"] = (ex.rstrip()+" "+cs) if ex else cs
            # --- reconstructed LIVE fields (Open/PF refresh; Closed stays frozen) ---
            if not email_failed:
                e = emailr.get(oid)
                row["last_outbound_email_date"] = (e.get("LAST_OUTBOUND_EMAIL_DATE") or None) if e else None
                row["last_inbound_email_date"]  = (e.get("LAST_INBOUND_EMAIL_DATE")  or None) if e else None
            if not arv_failed:                          # canonical customer auto-renewal (Snowplow)
                x = arv.get(oid)
                row["auto_renewal"]      = (x.get("AUTO_RENEWAL") or "N") if x else "N"
                row["auto_renewal_date"] = (x.get("AUTO_RENEWAL_DATE") or None) if x else None
            if not sigs_failed:
                s = sigs.get(oid) or {}
                ld = fnum(s.get("LEAD_DAYS")); row["lead_days"] = int(ld) if ld is not None else None
                row["selection_deadline"] = s.get("SELECTION_DEADLINE") or None
                row["submission_deadline"]= s.get("SUBMISSION_DEADLINE") or None
                row["bor_term"]           = s.get("BOR_TERM") or "N"
                row["sep"]                = s.get("SEP") or "N"
                row["recert_ticket"]      = s.get("RECERT_TICKET") or "N"
                row["recert_flag_date"]   = s.get("RECERT_FLAG_DATE") or None
                rl = fnum(s.get("RECERT_LATENESS_DAYS")); row["recert_lateness_days"] = int(rl) if rl is not None else None
            if not premd_failed:
                for l in row["lines"]:
                    pr = premd.get((oid, l.get("benefit_type")))
                    for jf,cf in PR_INT: l[jf] = _iround(pr.get(cf)) if pr else None
                    for jf,cf in PR_DEC: l[jf] = fnum(pr.get(cf)) if pr else None
            # --- Sept-10 reconstructed LIVE fields (Open/PF refresh; Closed frozen) ---
            if not rate_failed:                          # rate index -> P3 rate signal + risk
                rr = ratev.get(oid)
                pct, rstatus = _rate_map(rr)
                row["rate_increase_pct"] = pct
                row["rate_status"] = rstatus
                row["rate_structure"] = (rr.get("RATE_STRUCTURE") or None) if rr else None
                for l in row.get("lines") or []:         # medical line mirrors opp rate_pct
                    if l.get("benefit_type") == "medical": l["rate_pct"] = pct
            if not pyoy_failed:                          # CLEAN Hippo-matching premium change (all opps, daily)
                py = pyoyv.get(oid)
                row["prem_ee_pct"]       = fnum(py.get("PREM_EE_PCT")) if py else None
                row["prem_dep_pct"]      = fnum(py.get("PREM_DEP_PCT")) if py else None
                row["prem_book_cur"]     = fnum(py.get("PREM_BOOK_CUR")) if py else None
                row["prem_book_proj"]    = fnum(py.get("PREM_BOOK_PROJ")) if py else None
                row["prem_enr"]          = int(fnum(py.get("PREM_ENR"))) if (py and py.get("PREM_ENR") not in (None,"")) else None
                row["prem_fin_elig_pct"] = fnum(py.get("PREM_FIN_ELIG_PCT")) if py else None
            if not rfd_failed:
                row["days_to_default"] = rfdv.get(oid)   # Time in RFD dwell (None if never RFD)
            if not auto_failed:
                x = autov.get(oid)
                row["automation_eligible"] = ("Y" if (x and int(fnum(x.get("ELIGIBLE_RENEWAL_FLAG")) or 0)) else "N")
                if x and str(x.get("PARSE_RECORD_COUNT")) not in ("", "None", "0", "0.0"):
                    sr = fnum(x.get("PARSE_SUCCESS_RATE"))
                    row["rate_parse_success"] = "Y" if (sr is not None and sr >= 1.0) else "N"
                else:
                    row["rate_parse_success"] = None
            if not rect_failed:                          # recommendation-cycle dates + derived timing
                x = rectv.get(oid) or {}
                cycle_open   = x.get("CYCLE_OPEN") or None
                create_date  = x.get("CREATE_DATE") or None
                rec_sent     = x.get("DEFAULT_REC_SENT") or None
                rfd_date     = x.get("RFD_DATE") or None
                default_built= x.get("DEFAULT_BUILT") or None
                base_open    = cycle_open or create_date
                row["cycle_open"]    = cycle_open
                row["tl_cycle_open"] = cycle_open or create_date
                row["default_rec_sent"]  = rec_sent
                row["default_rec_built"] = default_built
                row["tl_rec_sent"]     = rec_sent
                row["tl_default_built"]= default_built
                row["days_to_rec_cycle"]        = _daysbetween(base_open, rec_sent)
                row["time_to_default_rec_days"] = _daysbetween(base_open, rec_sent)
                row["rfd_to_rec_sent_days"]     = _daysbetween(rfd_date, rec_sent) if rfd_date else None
            # --- fields that were base-only / carry-forward (went stale or null) -> now sourced LIVE ---
            _ex = extrasv.get(oid)
            if _ex:                                       # default_automation drives P1; bo_status + csat + funding
                row["default_automation"] = "Y" if _truthy(_ex.get("DEFAULT_AUTOMATION")) else "N"
                row["bo_status"]    = (_ex.get("BO_STATUS") or None)
                row["csat_current"] = (_ex.get("BO_CSAT") or _ex.get("CES_CSAT") or None)
                if _ex.get("MED_FUNDING"): row["funding"] = _ex.get("MED_FUNDING")
            _sl = slav.get(oid)
            if _sl:                                       # RFD/ERC/ALT SLA (Met/Missed/na) — fresh from sla.csv
                row["rfd_sla"] = _slam(_sl.get("RFD_MET"))
                row["erc_sla"] = _slam(_sl.get("ERC_MET"))
                row["alt_sla"] = (_slam(_sl.get("ALT_MET"))
                                  if (row.get("alt_requested")=="Y" or row.get("alt_req_date")) else "na")
            # alt-timing derived from the FRESH alt dates + cycle_open (these were base-only and went null,
            # same class as alt_published_date). Feeds the Alt-SLA risk signal + "Days to alt" + drill.
            _req = row.get("alt_req_date"); _pub = row.get("alt_pub_first"); _co = row.get("cycle_open")
            row["alt_requested_date"] = _req
            row["alt_requested_days"] = _daysbetween(_co, _req) if (_co and _req) else None
            if _pub and _req:
                row["days_to_alt"] = _daysbetween(_req, _pub)
                row["alt_published_days"] = _daysbetween(_req, _pub)
                row["alt_published_basis"] = "from request"
            elif _pub:
                row["days_to_alt"] = 0
                row["alt_published_days"] = _daysbetween(_co, _pub) if _co else None
                row["alt_published_basis"] = "from cycle open"
            if not edue_failed:                          # HOOP email-due (Open/PF only) + pending
                x = eduev.get(oid)
                st = (x.get("EMAIL_STATUS") if x else None) or None
                # email_due.sql now attributes each inbound to a subteam via the dashboard
                # ownership ladder and emits only the LATEST advising-attributed inbound.
                # CASE_CLOSED=1 => that inbound's case is Closed NOW => not "due" even if pending.
                closed_now = (str(x.get("CASE_CLOSED")).strip() in ("1","1.0","True","true")) if x else False
                row["email_due_status"] = st
                row["email_due"] = "Y" if (st in EMAIL_DUE_PENDING and not closed_now) else "N"
                hh = fnum(x.get("HOOP_HRS")) if x else None
                row["email_due_hoop_hrs"]  = round(hh, 1) if hh is not None else None
                row["email_due_hoop_days"] = round(hh / 9.0, 1) if hh is not None else None
                la = (x.get("LAST_AWAITING") if x else None) or None
                row["email_pending"]      = "Y" if la else "N"
                row["email_pending_date"] = la
                row["email_pending_days"] = _daysbetween(la, TODAY_ISO) if la else None
                row["email_received_date"]= la if (row["email_due"] == "Y" and la) else None
            # per-opp SLA fields (default 'na' when the opp is absent from the CSV)
            if not tsla_failed: row["ticket_sla"] = tslav.get(oid, "na")
            if not esla_failed:
                _es = eslav.get(oid) or {}
                row["email_sla"]        = (_es.get("EMAIL_SLA") or "na")
                row["email_sla_met"]    = int(fnum(_es.get("N_MET")) or 0)
                row["email_sla_missed"] = int(fnum(_es.get("N_MISSED")) or 0)
            # --- Salesforce-MCP live fields (Open/PF refresh; Closed frozen). Carry forward
            #     the prior/assembler value when the opp is absent from the CSV. ---
            if is_open_pf and oid in sfmcp_intro:
                ic, icd = sfmcp_intro[oid]
                row["intro_call"] = ic or "N"
                row["intro_call_date"] = icd
            if is_open_pf and oid in sfmcp_recert:
                row["recert_status"] = sfmcp_recert[oid]
            if is_open_pf and oid in sfmcp_sep:
                row["sep_risk_level"] = sfmcp_sep[oid]
            if is_open_pf and oid in sfmcp_pk:
                pf, pc = sfmcp_pk[oid]
                row["packets_files"] = int(fnum(pf) or 0)
                row["packet_carriers"] = pc
        if not is_open_pf:                              # CLOSED — Snowflake fields already refreshed above
            # Freeze ONLY the Salesforce-sourced fields: carry forward the prior published value so
            # they stay pinned to the close-time snapshot. Everything else (Snowflake) stays live.
            for k in SF_FROZEN_FIELDS:
                if k in p: row[k] = p.get(k)
            # outcome tracks the LIVE stage (so opps that closed since last run, or flipped
            # Won<->Lost, land correctly).
            row["outcome"] = ("Won" if row.get("stage") == "Closed Won"
                              else ("Lost" if row.get("stage") in CLOSED_LOSS else None))
            # as-of-close date for the builder's grayed 'as of close' labels on point-in-time values.
            row["close_snapshot_date"] = (p.get("closed_on") or p.get("inferred_close_date")
                                          or row.get("closed_on") or row.get("renewal_date"))
        row["data_asof"] = TODAY_ISO                    # last daily-refresh date (all opps)
        out.append(row)

    # --- NEW opps entering the rolling window (in today's cohort.csv but not in the prior
    #     dataset or the frozen base). Build a schema-safe row from cohort.csv so far-out
    #     future-month renewals appear; live/enrichment fields populate on subsequent runs as
    #     their data lands. Types are cloned from an existing row (list->[], dict->{}, else None)
    #     so the builder never hits a missing key or wrong type. ---
    present = {r["opp_id18"] for r in out}
    tmpl = out[0] if out else {}
    def _blank(v):
        if isinstance(v, list): return []
        if isinstance(v, dict): return {}
        return None
    new_win = 0
    for oid, cf in cohort_fresh.items():
        if oid in present: continue
        stg = cf.get("STATUS") or ""
        row = {k: _blank(v) for k, v in tmpl.items()}
        row["opp_id18"] = oid; row["opp_id15"] = oid[:15]
        row["company"] = re.sub(r" - Benefits Renewal.*$", "", cf.get("SFDC_OBJECT_NAME_OR_NUM") or "").strip() or None
        row["stage"] = stg; row["closed"] = stg in CLOSED_STAGES; row["tab"] = _tab_of(stg)
        row["pe"] = cf.get("PE") or None; row["advisor"] = cf.get("OWNER_NAME") or None
        row["renewal_date"] = (cf.get("RENEWAL_DATE") or "")[:10] or None
        dtr = fnum(cf.get("DAYS_TO_RENEWAL")); row["days_to_renewal"] = int(dtr) if dtr is not None else None
        dis = fnum(cf.get("DAYS_IN_STAGE"));   row["days_in_stage"]  = int(dis) if dis is not None else None
        blk = (cf.get("ADVISING_BLOCKED_REASON") or "") or None
        row["blocked_reason"] = blk
        row["bor_term"] = "Y" if re.search(r"terminat|bor|broker of record", blk or "", re.I) else "N"
        row["sep"] = "Y" if _truthy(cf.get("SPECIAL_ENROLLMENT")) else "N"
        row["cohort"] = cf.get("COHORT")
        row["outcome"] = ("Won" if stg == "Closed Won" else ("Lost" if stg in CLOSED_LOSS else None))
        if isinstance(row.get("lines"), list): row["lines"] = []
        row["mrr"] = 0.0; row["mrr_before"] = 0.0; row["mrr_after"] = None
        out.append(row); new_win += 1
    if new_win:
        print(f"  new in-window opps created (not in prior/base): {new_win}", flush=True)

    # Drop builder-recomputed-decorative fields so a STALE persisted value can't leak into the UI:
    #   queue_tier -> recomputed live in build_advising_hub.py (Min of P1..P5 flags) every load.
    #   tab        -> build_advising_hub.py tabOf(r) recomputes it from r.stage; stored tab is unused.
    # (merge_freeze already consumed tab above for Open/PF-vs-Closed classification; the builder
    #  never reads the persisted value.)
    for r in out:
        r.pop("queue_tier", None)
        r.pop("tab", None)
        # Data-only fields consumed by digests/exports (NOT the dashboard builder) — kept fresh so every
        # surface agrees, instead of sitting stuck on the base snapshot:
        #   csat -> mirror the fresh csat_current; survey_summary -> re-derive from fresh survey_answers;
        #   last_contact_date -> most recent of the fresh contact dates.
        r["csat"] = r.get("csat_current")
        _sa = {a.get("q"): a.get("a") for a in (r.get("survey_answers") or [])}
        _ss = [f"{lab}: {_sa[q]}" for q, lab in (("medical_priorities","priority"),
               ("carrier_options","carrier"),("network_flexibility","network"))
               if _sa.get(q) and _sa.get(q) != "unanswered"]
        r["survey_summary"] = " · ".join(_ss) or None
        _cd = [r.get(k) for k in ("last_call_date","last_connect_date","last_inbound_email_date",
               "last_outbound_email_date","last_update") if r.get(k)]
        r["last_contact_date"] = max(_cd) if _cd else None

    json.dump(out, open(DATA,"w"), separators=(",",":"), default=str)
    print(f"  merged {len(out)} opps  open/pf={stat['open_pf']} closed={stat['closed']} "
          f"new={stat['carried_new']} lines={stat['lines_recomputed']}", flush=True)
    return len(out)

def run_build():
    r = subprocess.run([VENV_PY, BUILDER], cwd=HERE)
    if r.returncode != 0:
        raise RuntimeError("build_advising_hub.py failed")

# ----------------------------------------------------------------- verify
def _extract_hub_json(src):
    m = re.search(r'<script id="hubdata"[^>]*>(.*?)</script>', src, re.S)
    if not m: raise AssertionError("hubdata script block not found in HTML")
    return m.group(1)

# node scorer: verbatim copy of the builder's risk engine + helpers, counts High.
RISK_JS = r"""
const fs=require('fs');
const HUB=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
const TODAY=new Date(new Date().toISOString().slice(0,10)+"T00:00:00");
const TAB_CLOSED=new Set(["Closed Won","Closed Lost","Order Lost","Closed Admin"]);
const D=s=>s?new Date(String(s).slice(0,10)+"T00:00:00"):null;
const dayDiff=(a,b)=>Math.round((a-b)/86400000);
const dUntil=s=>s?dayDiff(D(s),TODAY):null;
const isY=v=>v==="Y";
const tabOf=r=>{const s=r.stage||"";return TAB_CLOSED.has(s)?"closed":(s==="Pending Fulfillment"?"pf":"open");};
/* ============================================================ risk engine
   Per-tab risk profile computed client-side from existing row fields.
   Open  -> riskOpen  (3 equal domains @ 33.3: contact / plan&cost / timeline&SLA)
   PF    -> riskPF    (4 equal domains @ 25: sentiment / service / cost / timeline)
   Closed-> riskPF but marked archived.
   Scaling: duration/magnitude signals scale up to x2 as they worsen (marked in reasons).
   Tiers: score>=30 High · >=21 Med · else Low.
   Contact floor (Open only): 3 of 3 contact signals -> at least High; 2 of 3 -> at least Med. */
const EARLY_SET = new Set(["SAL","Ready for Default Package","Open"]);
function _daysSince(s){ const d=dUntil(s); return d==null?null:-d; }   // days since a past date
function _durScale(d){ return d>90?2.0 : d>45?1.5 : 1.0; }            // recency / dwell escalator
function _slaScale(dw,thr,a,b){ return dw>b?2.0 : dw>a?1.5 : dw>thr?1.0 : 0; }
function _num(x){ const v=parseFloat(x); return isNaN(v)?null:v; }
function _survAvg(r){ const a=r.surveys_12mo; if(!Array.isArray(a)) return null;
  let s=0,n=0; a.forEach(it=>{ if(it && it.survey!=="App: NPS Survey"){ const v=parseFloat(it.rating); if(!isNaN(v)){ s+=v; n++; } } });
  return n? s/n : null; }
const WC=100/3/5, WT=100/3/8, WPF=25, WSVC=25/3;
function riskOpen(r){
  const bl=(r.blocked_reason||""); const sigs=[];
  const so=_daysSince(r.last_outbound_email_date), si=_daysSince(r.last_inbound_email_date), sc=_daysSince(r.last_connect_date);
  const haveOut = r.last_outbound_email_date!=null;
  // ---- Customer contact (5 x 6.7) ----
  const replyFire = haveOut && (si==null || si>21);
  sigs.push({key:"reply", w:WC, sev: replyFire? _durScale(si!=null?si:(so!=null?so:22)) : 0, reason:(si==null?`No customer reply since we reached out`:`No customer reply in ${si} days`)});
  const silFire = (so==null || so>21);
  sigs.push({key:"silence", w:WC, sev: silFire? _durScale(so!=null?so:22) : 0, reason:(so==null?`No outbound email logged`:`No outbound email in ${so} days`)});
  const connFire = (sc==null || sc>21);
  sigs.push({key:"callconnect", w:WC, sev: connFire? _durScale(sc!=null?sc:22) : 0, reason:(sc==null?`No live call connect logged`:`No live call connect in ${sc} days`)});
  const dis=r.days_in_stage;
  const stSev = dis==null?0 : dis>21?_durScale(dis) : dis>14?0.66 : dis>7?0.33 : 0;
  sigs.push({key:"stagnant", w:WC, sev:stSev, reason:`${r.days_in_stage} days in ${r.stage}`});
  sigs.push({key:"nointro", w:WC, sev:isY(r.intro_call)?0:1, reason:`intro call not completed`});
  // ---- Plan & cost attributes (5 x 6.7) ----
  const inc=r.rate_increase_pct;
  const rtSev = inc==null?0 : inc>=60?2 : inc>=45?1.5 : inc>=30?1 : inc>=20?0.6 : inc>=15?0.3 : 0;
  sigs.push({key:"rate", w:WC, sev:rtSev, reason:`rate increase ${r.rate_increase_pct}%`});
  { const band=r.lf_savings_band; const posit=(band==="High"||band==="Medium"||band==="Low"); const inAlt=(r.lf_in_alt==="Y");
    const sev=(posit&&!inAlt)?(band==="High"?1:band==="Medium"?0.7:0.4):0;
    sigs.push({key:"lfpend", w:WC, sev:sev, reason:`level-funded savings (${band}) not in an alt`}); }
  const tbSev=/Pending Termination|BoR Away/i.test(bl)?1:/BoR Incomplete/i.test(bl)?0.7:0;
  sigs.push({key:"termbor", w:WC, sev:tbSev, reason:`term / BoR-away — ${bl}`});
  const rl=r.recert_lateness_days;
  const rcSev=(rl>0)?(rl>120?2:rl>90?1.5:rl>60?1:rl>30?0.7:rl>14?0.4:0.25):((r.recert_ticket||r.recert_status||/recert/i.test(bl))?0.5:0);
  sigs.push({key:"recert", w:WC, sev:rcSev, reason:(rl>0?`recertification ${rl} days late`:`recertification flagged`)});
  sigs.push({key:"sepgr", w:WC, sev:isY(r.sep)?1:0, reason:`SEP / GR flagged`});
  // ---- Timeline & SLA (8 x 4.2) ----
  const sd=dUntil(r.submission_deadline);
  const sdSev = sd==null?0 : sd<0?( -sd>=14?2 : -sd>=7?1.5 : 1) : sd<=7?0.7 : sd<=21?0.4 : 0;
  sigs.push({key:"subdl", w:WT, sev:sdSev, reason:(sd<0?`submission deadline passed ${-sd}d ago`:`submission deadline in ${sd}d`)});
  const rfd=_num(r.days_to_default);
  const rfdSev = rfd!=null? _slaScale(rfd,5,15,30) : (r.rfd_sla==="Missed"?1:0);
  sigs.push({key:"rfdsla", w:WT, sev:rfdSev, reason:(rfd!=null?`${Math.round(rfd)} days in Ready-for-Default (SLA 5)`:`RFD SLA missed`)});
  const erc=_num(r.time_in_erc);
  const ercSev = erc!=null? _slaScale(erc,5,15,30) : (r.erc_sla==="Missed"?1:0);
  sigs.push({key:"ercsla", w:WT, sev:ercSev, reason:(erc!=null?`${Math.round(erc)} days in ER Confirm (SLA 5)`:`ERC SLA missed`)});
  let asSev=0, agap=null;
  if (r.alt_requested_date){ let gap = r.alt_published_date ? r.days_to_alt : _daysSince(r.alt_requested_date); gap=gap==null?0:gap; agap=gap;
    asSev = gap>3?(gap>21?2:gap>10?1.5:1) : gap==3?0.5 : 0; }
  sigs.push({key:"altsla", w:WT, sev:asSev, reason:(agap!=null?`alternates ${agap}d unpublished (SLA 3)`:`alternates SLA`)});
  const sa=_survAvg(r);
  const svSev = (sa!=null && sa<=3)?(sa<=1.5?2:sa<=2?1.5:1):0;
  sigs.push({key:"survey", w:WT, sev:svSev, reason:(sa!=null?`avg survey ${sa.toFixed(1)} over 12 months`:`low survey`)});
  const dtr=r.days_to_renewal;
  const esSev=(EARLY_SET.has(r.stage) && dtr!=null && dtr<=45)?1:0;
  sigs.push({key:"early", w:WT, sev:esSev, reason:`early stage (${r.stage}), ${dtr}d to renewal`});
  const ld=r.lead_days;
  sigs.push({key:"lategen", w:WT, sev: ld==null?0:ld<60?1:ld<75?0.5:0, reason:`short lead time (${r.lead_days}d)`});
  const pkSev=/Packet Needed/i.test(bl)?1:((r.packets_files==0||r.packets_files==null)&&r.packet_carriers)?0.4:0;
  sigs.push({key:"packet", w:WT, sev:pkSev, reason:`renewal packet missing`});
  let acc=0; sigs.forEach(s=>{ acc += s.w*s.sev; });
  const score=Math.min(100, Math.round(acc));
  const goneQuiet=["reply","silence","callconnect"].reduce((n,k)=>{const s=sigs.find(x=>x.key===k);return n+(s&&s.sev>0?1:0);},0);
  const firing=sigs.filter(s=>s.sev>0).sort((a,b)=>(b.w*b.sev)-(a.w*a.sev));
  return {score, reasons:firing.map(s=>s.reason), firing, goneQuiet};
}
function riskPF(r){
  const sigs=[];
  // ---- Sentiment (25) ----
  const cur=(r.in_app_date && r.cycle_open && r.in_app_date>=r.cycle_open);
  const ia=parseFloat(r.inapp_current); const cmt=!!r.in_app_comment;
  const seSev = cur ? (!isNaN(ia)?(ia<=1?1:ia<=2?0.85:ia<=3?0.6:0):(cmt?0.6:0)) : 0;
  sigs.push({key:"sentiment", w:WPF, sev:seSev, reason:`in-app sentiment ${r.inapp_current} this cycle`});
  // ---- Service load (3 x 8.3) ----
  const tk=r.tickets_to_advising||0;
  const tkSev = tk>=5?1.5 : tk>=3?1 : tk==2?0.7 : tk==1?0.4 : 0;
  sigs.push({key:"ticket", w:WSVC, sev:tkSev, reason:`${r.tickets_to_advising} open OA→advising ticket${r.tickets_to_advising==1?"":"s"}`});
  sigs.push({key:"ticketsla", w:WSVC, sev:(r.ticket_sla==="Missed"?1:0), reason:`a ticket is past its SLA`});
  const rl=r.recert_lateness_days;
  const rcSev=(r.recert_status && r.recert_status!=="Recert Approved")?((rl>90)?2:(rl>60)?1.5:1):0;
  sigs.push({key:"recert", w:WSVC, sev:Math.min(rcSev,2), reason:`recert still open (${r.recert_status})`});
  // ---- Cost (25) ----
  const inc=r.rate_increase_pct;
  const arSev=isY(r.auto_renewal)?(inc>=45?2:inc>=30?1.5:inc>=20?1:inc>=15?0.6:0.3):0;
  sigs.push({key:"autoren", w:WPF, sev:Math.min(arSev,2), reason:(inc!=null?`auto-renewing into a ${inc}% increase`:"auto-renewal")});
  // ---- Timeline (25) ----
  const dd=dUntil(r.submission_deadline);
  const w1Sev = dd==null?0 : dd<0?(-dd>=14?2:-dd>=7?1.5:1) : dd<=7?1 : dd<=14?0.5 : 0;
  sigs.push({key:"within1wk", w:WPF, sev:w1Sev, reason:(dd!=null?`fulfillment in ${dd} day${dd==1?"":"s"}`:"fulfillment deadline")});
  let acc=0; sigs.forEach(s=>{ acc += s.w*s.sev; });
  const score=Math.min(100, Math.round(acc));
  const firing=sigs.filter(s=>s.sev>0).sort((a,b)=>(b.w*b.sev)-(a.w*a.sev));
  return {score, reasons:firing.map(s=>s.reason), firing};
}
function riskOf(r){
  const t=tabOf(r); let base, archived=false;
  if (t==="open") base=riskOpen(r);
  else if (t==="pf") base=riskPF(r);
  else { base=riskPF(r); archived=true; }
  const score=base.score;
  let tier = score>=30?"High" : score>=21?"Med" : "Low";
  if (t==="open" && base.goneQuiet!=null){
    const floor = base.goneQuiet>=3?"High" : base.goneQuiet>=2?"Med" : "Low";
    const RANK={Low:0,Med:1,High:2};
    if (RANK[floor] > RANK[tier]) tier=floor;
  }
  return {score, tier, reasons:base.reasons, firing:base.firing||[], archived, goneQuiet:base.goneQuiet};
}
// active at-risk (High) = Open + Pending Fulfillment; Closed risk is archived/frozen in the builder.
let hi=0;for(const r of HUB){const t=tabOf(r);if(t!=="closed"&&riskOf(r).tier==="High")hi++;}
console.log(hi);
"""

# Builder-critical fields that must not silently collapse to null between runs. The coverage
# guard in verify() compares live-opp coverage vs the prior published dataset and FAILS the publish
# if any of these drops by >75% (a carry-forward/blank regression, e.g. the alt_published_date bug).
COVERAGE_WATCH = ["stage","renewal_date","mrr","rate_increase_pct","lf_savings_pct","alt_published_date",
                  "alt_requested_date","days_to_alt","alt_published_days","default_automation","bo_status",
                  "csat_current","email_sla_met","intro_call","last_update","pe","advisor","packets_files",
                  "funding","all_survey_count","alt_sla","rfd_sla","erc_sla","num_lines","tl_renewal"]

def _live_coverage(rows, fields):
    live = [r for r in rows if (r.get("stage") or "") not in CLOSED_STAGES]
    return {f: sum(1 for r in live if r.get(f) not in (None, "", [], {})) for f in fields}

def verify(n_opps, prior_path=None):
    html = open(HTML, encoding="utf-8").read()
    # 1. app <script> node --check
    m = re.search(r'<script>(.*?)</script>', html, re.S)
    assert m, "no <script> block found"
    app_js = max(re.findall(r'<script>(.*?)</script>', html, re.S), key=len)
    js_path = "/tmp/_hub_app_check.js"
    open(js_path,"w").write(app_js)
    r = subprocess.run(["node","--check", js_path], capture_output=True, text=True)
    assert r.returncode == 0, f"node --check failed: {r.stderr[:400]}"
    _rm(js_path)
    # 2. PII scan on the whole HTML
    EMAIL = re.compile(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}')
    PHONE = re.compile(r'(?<!\d)(?:\+?1[\s.\-]?)?\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}(?!\d)')
    SSN   = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
    pii = len(EMAIL.findall(html)) + len(PHONE.findall(html)) + len(SSN.findall(html))
    assert pii == 0, f"PII scan found {pii} matches"
    # 3. embedded HUB JSON parses + count
    hub = json.loads(_extract_hub_json(html))
    assert len(hub) == n_opps, f"embedded HUB count {len(hub)} != data {n_opps}"
    assert n_opps > 15000, f"opp count {n_opps} <= 15000"
    # 3b. COVERAGE-REGRESSION GUARD — fail publish if a builder-critical field collapses vs the prior
    #     published dataset (catches carry-forward/blank regressions like the alt_published_date bug).
    if prior_path and os.path.exists(prior_path):
        try: prior = json.load(open(prior_path))
        except Exception: prior = None
        if prior:
            cn = _live_coverage(hub, COVERAGE_WATCH); cp = _live_coverage(prior, COVERAGE_WATCH)
            collapsed = [f for f in COVERAGE_WATCH if cp[f] >= 200 and cn[f] < 0.25 * cp[f]]
            assert not collapsed, ("COVERAGE COLLAPSE vs prior (likely a field going null/stale): "
                + "; ".join(f"{f} {cp[f]}->{cn[f]}" for f in collapsed))
            drops = [f"{f} {cp[f]}->{cn[f]}" for f in COVERAGE_WATCH if cp[f] >= 200 and 0.25*cp[f] <= cn[f] < 0.6*cp[f]]
            if drops: print("  verify NOTE: field coverage dropped >40% vs prior (review): " + "; ".join(drops), flush=True)
    # 4. at_risk_high via the builder's exact risk engine (node)
    data_tmp = "/tmp/_hub_risk_data.json"
    json.dump(hub, open(data_tmp,"w"))
    js2 = "/tmp/_hub_risk_score.js"; open(js2,"w").write(RISK_JS)
    rr = subprocess.run(["node", js2, data_tmp], capture_output=True, text=True)
    _rm(js2); _rm(data_tmp)
    assert rr.returncode == 0, f"risk scorer failed: {rr.stderr[:400]}"
    at_risk_high = int(rr.stdout.strip().splitlines()[-1])
    mrr_total = round(sum(fnum(r.get("mrr")) or 0 for r in hub), 2)
    print(f"  verify OK: node ok, PII=0, opps={n_opps}, at_risk_high={at_risk_high}, mrr_total={mrr_total}", flush=True)
    return {"pii": pii, "at_risk_high": at_risk_high, "mrr_total": mrr_total}

def _publish_token():
    """ShareSomething publish token — read from env or the gitignored snowflake_pat.env
    (never hardcoded/committed, per security policy). Set SHARESOME_PUBLISH_TOKEN there."""
    import re
    t = os.environ.get("SHARESOME_PUBLISH_TOKEN")
    if t: return t.strip()
    envp = os.path.join(HERE, "snowflake_pat.env")
    if os.path.exists(envp):
        m = re.search(r'(?:SHARESOME_PUBLISH_TOKEN|PUBLISH_TOKEN)\s*=\s*(\S+)', open(envp).read())
        if m: return m.group(1).strip().strip('"').strip("'")
    raise RuntimeError("publish token not found — set SHARESOME_PUBLISH_TOKEN in snowflake_pat.env")

def publish():
    r = subprocess.run([VENV_PY, os.path.join(HERE,"push_html.py"), HTML,
                        "benefits-advising-hub", _publish_token()], cwd=HERE)
    if r.returncode != 0:
        raise RuntimeError("push_html.py failed")

# ----------------------------------------------------------------- main
def main():
    do_publish = "--no-publish" not in sys.argv
    status = {"ok": False, "data_date": datetime.date.today().isoformat(), "opps": None,
              "at_risk_high": None, "mrr_total": None,
              "version_note": "v-next Advising Hub daily refresh (all opps: stage/scalars live from Snowflake; Closed keeps close snapshot)",
              "cohort_window": COHORT_WINDOW, "steps": STEPS, "warnings": [], "error": None}
    resume_pull = "--resume-pull" in sys.argv
    skip_pull   = "--skip-pull" in sys.argv
    pull_only   = "--pull-only" in sys.argv
    n_opps = None; prior_bak = None
    try:
        with step("venv"):        ensure_venv()
        with step("lf_classifier"): lf_classifier()
        if not skip_pull:
            with step("pull"):    run_queries(resume=resume_pull or pull_only)
        if pull_only:
            print("\n--pull-only: CSVs refreshed; exiting before assemble.")
            json.dump(status, open(STATUS,"w"), indent=2, default=str)
            return
        with step("base_rebuild"): run_base_rebuild()
        with step("backup"):      prior_bak = backup_prior()
        with step("assemble"):    run_assemble()
        if os.path.exists(FAILED_PATH):
            try: status["warnings"] = json.load(open(FAILED_PATH))
            except Exception: pass
        with step("merge_freeze"):n_opps = merge_freeze(prior_bak)
        with step("build"):       run_build()
        with step("verify"):
            vr = verify(n_opps, prior_bak)
            status["at_risk_high"] = vr["at_risk_high"]; status["mrr_total"] = vr["mrr_total"]
        status["opps"] = n_opps
        if do_publish:
            with step("publish"): publish()
            print("\nPublished to benefits-advising-hub.")
        else:
            print("\n--no-publish: built + verified locally only.")
        status["ok"] = True
    except Exception as e:
        status["error"] = "".join(traceback.format_exception_only(type(e), e)).strip()
        # if any step already recorded the failure it's in STEPS; ensure at least one
        if not any(not s["ok"] for s in STEPS):
            STEPS.append({"name":"main","ok":False,"ms":0,"error":status["error"]})
        json.dump(status, open(STATUS,"w"), indent=2, default=str)
        print("\nREFRESH FAILED:", status["error"], flush=True)
        raise
    json.dump(status, open(STATUS,"w"), indent=2, default=str)
    print("\nSTATUS ->", STATUS)
    print(json.dumps({k:status[k] for k in ("ok","data_date","opps","at_risk_high","mrr_total")}, default=str))
    print("DONE")

if __name__ == "__main__":
    main()
