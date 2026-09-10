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
  7. publish      — push_html.py advising_hub_vnext.html benefits-advising-hub $HUB_PUBLISH_TOKEN
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

COHORT_DATES = "'2026-07-01','2026-08-01','2026-09-01','2026-10-01','2026-11-01','2026-12-01'"

CLOSED_TABS = {"Closed"}
# MRR-dash price book (per enrolled EE / mo) — mirrors _renewal_vnext/repull_patch.py
PRICE = {'dental':6.58,'vision':1.20,'life':1.21,'long_term_disability':1.65,
         'short_term_disability':1.82,'fsa':4.00,'dca':4.00,'hsa':2.50,'voluntary_life':5.28}
MED_FI, MED_LF = 33.24, 46.53
BT10 = set(PRICE) | {'medical'}

# fields assemble_vnext.py (re)computes for every opp — overlaid fresh
OVERLAY = ["tab","outcome","closed_on","rating_region","survey_answered","survey_answers",
           "alt_requested","alt_req_date","alt_pub_count","alt_pub_first","alt_pub_last",
           "alt_pub_carriers","in_app","in_app_comment","in_app_date","surveys_12mo",
           "tickets_to_advising","tickets_list","mrr_before","mrr_after","intro_call",
           "intro_call_date","intro_connect","connect_date","last_update","case_summary",
           "csat_comment"]
# closed = frozen: restore these from the prior published snapshot after the overlay
FROZEN_CLOSED = ["mrr","mrr_before","mrr_after","enrollees","funding_after","closed_on",
                 "outcome","inferred_close_date","lines"]

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
    "alt": ["alt_requested","alt_req_date","alt_pub_count","alt_pub_first","alt_pub_last","alt_pub_carriers"],
    "sf_activity": ["last_update","intro_connect","connect_date","case_summary","intro_call","intro_call_date"],
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
    return sf.connect(account="GUSTO-WAREHOUSE", user=os.environ.get("SNOWFLAKE_USER",""),
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
            raise SystemExit(f"critical query/queries failed: {crit}")
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
        raise SystemExit("assemble_vnext.py failed")

def _rd(path):
    import csv; csv.field_size_limit(10**7)
    return list(csv.DictReader(open(path)))

def merge_freeze(prior_path):
    import csv, collections
    prior = {r["opp_id18"]: r for r in json.load(open(prior_path))}
    assembled = json.load(open(DATA))
    failed = json.load(open(FAILED_PATH)) if os.path.exists(FAILED_PATH) else []
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
    eslav = {} if esla_failed else {r["OPP"]: (r.get("EMAIL_SLA")  or "na") for r in _rd(os.path.join(VNEXT,"out","email_sla.csv"))}

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
    sfmcp_pk = {r["opp_id18"]: ((r.get("packets_files") or None), (r.get("packet_carriers") or None))
                for r in _rd_opt(os.path.join(OUTV, "sf_mcp_packets.csv"))}
    if sfmcp_intro or sfmcp_recert or sfmcp_pk:
        print(f"  SF-MCP live fields: intro={len(sfmcp_intro)} recert={len(sfmcp_recert)} "
              f"packets={len(sfmcp_pk)}", flush=True)
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
        if p is None:
            out.append(a); stat["carried_new"] += 1; continue
        row = dict(p)                                   # inherit ALL prior fields (carry-forward)
        for k in OVERLAY:                               # fresh assembler overlay (skip failed pulls)
            if k in skip_fields: continue               # keep prior value
            row[k] = a.get(k)
        row["stage"] = a.get("stage") or p.get("stage")
        tab = a.get("tab") or p.get("tab")
        row["tab"] = tab
        # in-app numeric mirror the builder reads (derive from whatever in_app resolved to)
        row["inapp_current"] = fnum(row.get("in_app"))

        if tab not in CLOSED_TABS:                      # OPEN / PF — fully refresh
            stat["open_pf"] += 1
            has_sel = bool(selany.get(oid,0))
            lines = [dict(l) for l in (p.get("lines") or [])]
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
            if not sigs_failed:
                s = sigs.get(oid) or {}
                row["auto_renewal"]       = s.get("AUTO_RENEWAL") or "N"
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
            if not rfd_failed:
                row["days_to_default"] = rfdv.get(oid)   # Time in RFD dwell (None if never RFD)
            if not lf_failed:                            # P2 LF (savings % = Snowflake, no classifier)
                x = lfv.get(oid)
                p = fnum(x.get("LF_SAVINGS_PCT")) if x else None
                row["lf_savings_pct"] = p
                row["lf_savings_band"] = _lf_band(p)
                row["lf_quote"] = _lf_quote_txt(x)
                row["lf_in_alt"] = ("Y" if (x and int(fnum(x.get("HAS_LF_ALT")) or 0)) else "N")
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
            if not edue_failed:                          # HOOP email-due (Open/PF only) + pending
                x = eduev.get(oid)
                st = (x.get("EMAIL_STATUS") if x else None) or None
                row["email_due_status"] = st
                row["email_due"] = "Y" if st in EMAIL_DUE_PENDING else "N"
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
            if not esla_failed: row["email_sla"]  = eslav.get(oid, "na")
            # --- Salesforce-MCP live fields (Open/PF refresh; Closed frozen). Carry forward
            #     the prior/assembler value when the opp is absent from the CSV. ---
            if oid in sfmcp_intro:
                ic, icd = sfmcp_intro[oid]
                row["intro_call"] = ic or "N"
                row["intro_call_date"] = icd
            if oid in sfmcp_recert:
                row["recert_status"] = sfmcp_recert[oid]
            if oid in sfmcp_pk:
                pf, pc = sfmcp_pk[oid]
                row["packets_files"] = int(fnum(pf) or 0)
                row["packet_carriers"] = pc
        else:                                           # CLOSED — frozen snapshot
            stat["closed"] += 1
            for k in FROZEN_CLOSED: row[k] = p.get(k)   # restore frozen numerics/premium
            # refresh only in-app / csat / status (status set above); freeze the rest
            for k in ("time_in_erc","open_tickets","open_tickets_past_sla",
                      "open_cases_by_type","open_cases_total"):
                row[k] = p.get(k)
        out.append(row)

    json.dump(out, open(DATA,"w"), separators=(",",":"), default=str)
    print(f"  merged {len(out)} opps  open/pf={stat['open_pf']} closed={stat['closed']} "
          f"new={stat['carried_new']} lines={stat['lines_recomputed']}", flush=True)
    return len(out)

def run_build():
    r = subprocess.run([VENV_PY, BUILDER], cwd=HERE)
    if r.returncode != 0:
        raise SystemExit("build_advising_hub.py failed")

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
const EARLY=new Set(["Open","SAL","Attempting Contact","New","Working","Nurturing"]);
const MID=new Set(["Engaged","ER Confirm"]);
const _daysSince=s=>{const d=dUntil(s);return d==null?null:-d;};
function riskOpen(r){const bl=(r.blocked_reason||"");const sigs=[];
 const early=EARLY.has(r.stage)?1:MID.has(r.stage)?0.5:0;const dtr=r.days_to_renewal;
 const unwSev=early*(dtr==null?0.2:dtr<=30?1:dtr<=45?0.8:dtr<=60?0.5:0.2);sigs.push({w:15,sev:unwSev});
 const tbSev=/Pending Termination|BoR Away/i.test(bl)?1:/BoR Incomplete/i.test(bl)?0.7:0;sigs.push({w:15,sev:tbSev});
 const so=_daysSince(r.last_outbound_email_date);const siSev=so==null?0.75:so>14?1:so>7?0.5:so>4?0.25:0;sigs.push({w:12,sev:siSev});
 const inc=r.rate_increase_pct;const rtSev=inc==null?0:inc>=30?1:inc>=20?0.6:inc>=15?0.3:0;sigs.push({w:12,sev:rtSev});
 const si=_daysSince(r.last_inbound_email_date);const nrSev=si==null?(r.last_outbound_email_date?0.8:0.4):si>21?1:si>14?0.6:si>7?0.3:0;sigs.push({w:10,sev:nrSev});
 const ld=r.lead_days;const lgSev=ld==null?0:ld<60?1:ld<75?0.5:0;sigs.push({w:10,sev:lgSev});
 const dis=r.days_in_stage;const stSev=dis==null?0:dis>21?1:dis>14?0.66:dis>7?0.33:0;sigs.push({w:10,sev:stSev});
 sigs.push({w:10,sev:isY(r.intro_call)?0:1});
 const dd=dUntil(r.selection_deadline);const dlSev=dd==null?0:dd<0?1:dd<=7?0.6:dd<=14?0.3:0;sigs.push({w:10,sev:dlSev});
 const sd=dUntil(r.submission_deadline);const sdSev=sd==null?0:sd<0?1:sd<=7?0.6:sd<=14?0.3:0;sigs.push({w:10,sev:sdSev});
 const pkSev=/Packet Needed/i.test(bl)?1:((r.packets_files==0||r.packets_files==null)&&r.packet_carriers)?0.4:0;sigs.push({w:8,sev:pkSev});
 let asSev=0;if(r.alt_requested_date){let gap=r.alt_published_date?(r.days_to_alt):_daysSince(r.alt_requested_date);gap=gap==null?0:gap;asSev=gap>3?1:gap==3?0.5:0;}sigs.push({w:8,sev:asSev});
 const rl=r.recert_lateness_days;const rcSev=(rl>0)?(rl>60?1:rl>30?0.7:rl>14?0.4:0.25):((r.recert_ticket||r.recert_status||/recert/i.test(bl))?0.5:0);sigs.push({w:8,sev:rcSev});
 {const band=r.lf_savings_band;const posit=(band==="High"||band==="Medium"||band==="Low");const inAlt=(r.lf_in_alt==="Y");const sev=(posit&&!inAlt)?(band==="High"?1:band==="Medium"?0.7:0.4):0;sigs.push({w:6,sev:sev});}
 sigs.push({w:6,sev:isY(r.sep)?1:0});
 const WTOTAL_OPEN=150;let acc=0;sigs.forEach(s=>{acc+=s.w*s.sev;});return Math.round(100*acc/WTOTAL_OPEN);}
function riskPF(r){const sigs=[];
 const cur=(r.in_app_date&&r.cycle_open&&r.in_app_date>=r.cycle_open);const ia=parseFloat(r.inapp_current);const cmt=!!r.in_app_comment;
 const seSev=(cur&&(!isNaN(ia)||cmt))?(ia<=2?1:ia<=3?0.7:(cmt?0.7:0)):0;sigs.push({w:30,sev:seSev});
 const tk=r.tickets_to_advising||0;const tkSev=tk>=3?1:tk==2?0.7:tk==1?0.4:0;sigs.push({w:30,sev:tkSev});
 const rcSev=(r.recert_status&&r.recert_status!=="Recert Approved")?1:0;sigs.push({w:20,sev:rcSev});
 const dd=dUntil(r.submission_deadline);const w1Sev=(dd!=null&&dd>=0&&dd<=7)?1:(dd!=null&&dd>=8&&dd<=14)?0.5:0;sigs.push({w:30,sev:w1Sev});
 const inc=r.rate_increase_pct;const arSev=isY(r.auto_renewal)?(inc>=20?1:inc>=14?0.6:0.3):0;sigs.push({w:20,sev:arSev});
 const WTOTAL_PF=130;let acc=0;sigs.forEach(s=>{acc+=s.w*s.sev;});return Math.round(100*acc/WTOTAL_PF);}
function riskOf(r){const t=tabOf(r);let score;if(t==="open")score=riskOpen(r);else score=riskPF(r);
 return score>=35?"High":score>=18?"Med":"Low";}
// active at-risk (High) = Open + Pending Fulfillment; Closed risk is archived/frozen in the builder.
let hi=0;for(const r of HUB){const t=tabOf(r);if(t!=="closed"&&riskOf(r)==="High")hi++;}
console.log(hi);
"""

def verify(n_opps):
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

def publish():
    r = subprocess.run([VENV_PY, os.path.join(HERE,"push_html.py"), HTML,
                        "benefits-advising-hub", os.environ.get("HUB_PUBLISH_TOKEN","")], cwd=HERE)
    if r.returncode != 0:
        raise SystemExit("push_html.py failed")

# ----------------------------------------------------------------- main
def main():
    do_publish = "--no-publish" not in sys.argv
    status = {"ok": False, "data_date": datetime.date.today().isoformat(), "opps": None,
              "at_risk_high": None, "mrr_total": None,
              "version_note": "v-next Advising Hub daily refresh (Open/PF full refresh, Closed frozen)",
              "steps": STEPS, "warnings": [], "error": None}
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
        with step("backup"):      prior_bak = backup_prior()
        with step("assemble"):    run_assemble()
        if os.path.exists(FAILED_PATH):
            try: status["warnings"] = json.load(open(FAILED_PATH))
            except Exception: pass
        with step("merge_freeze"):n_opps = merge_freeze(prior_bak)
        with step("build"):       run_build()
        with step("verify"):
            vr = verify(n_opps)
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
