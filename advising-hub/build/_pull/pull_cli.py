#!/usr/bin/env python3
"""
Advising Hub — Phase A SF pull, CLI edition (replaces the Salesforce-MCP subagent pull).

Pulls the 4 live field groups (intro / recert / packets / sep) that are NOT in the
Snowflake SF mirror, writes them as the SAME raw `{"records":[...]}` dumps the MCP
subagents produced, then runs the UNCHANGED `build_csvs.py` parser to emit the 4
`sf_mcp_*.csv` files. Metric/field/parse logic is untouched — only the data source
moves from the MCP to the `sf` CLI (sf_pull.soql_all).

Verbatim SOQL is identical to gen_soql.py (the footguns stay visible):
  intro  : Case aggregate (MIN CreatedDate), Benefits Renewal Case + Intro_Call_Completed__c
  recert : Ticket__c where Recert_Status__c != null
  pk     : ContentDocumentLink, Title LIKE '%Renewal Packet%' (metadata only)
  sep    : Opportunity Id + SEP_Risk_Level__c (no aliases — org rejects non-agg aliasing)

Writes everything under a SHADOW dir ($HUB_SHADOW, default /tmp/hub_cli) so the live
Phase-A outputs are never touched during the parallel/validation run.
"""
import json, os, shutil, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
import sf_pull as S  # noqa: E402

BEN = os.environ.get("BEN", "/sessions/practical-affectionate-galileo/mnt/BenOps Dashboard Co-Work")
LIVE_PULL = os.path.join(BEN, "_renewal_vnext", "out", "_pull")
UNIVERSE = os.environ.get("HUB_UNIVERSE", os.path.join(LIVE_PULL, "_openpf_ids.json"))
BUILD_CSVS = os.path.join(LIVE_PULL, "build_csvs.py")
SHADOW = os.environ.get("HUB_SHADOW", "/tmp/hub_cli")
WORKERS = int(os.environ.get("HUB_WORKERS", "10"))
# Production (cutover) mode: write the raw {"records":[...]} dumps straight into the live
# _pull/raw dir and STOP — the scheduled task's existing Steps 5-7 (coverage, atomic
# build_csvs, status file) then run exactly as before. Shadow mode (default) also runs
# build_csvs itself for standalone validation.
RAW_ONLY = os.environ.get("HUB_RAW_ONLY", "") == "1"
RAW_DIR = os.environ.get("HUB_RAW_DIR", os.path.join(LIVE_PULL, "raw"))

def inlist(xs): return ",".join("'%s'" % i for i in xs)

def q_intro(chunk):
    return ("SELECT Opportunity__c oid, MIN(CreatedDate) mind FROM Case "
            "WHERE RecordType.Name='Benefits Renewal Case' AND Intro_Call_Completed__c=true "
            "AND Opportunity__c IN (" + inlist(chunk) + ") GROUP BY Opportunity__c")

def q_recert(chunk):
    return ("SELECT Opportunity__c, Recert_Status__c, CreatedDate FROM Ticket__c "
            "WHERE Recert_Status__c != null AND Opportunity__c IN (" + inlist(chunk) + ")")

def q_pk(chunk):
    return ("SELECT LinkedEntityId, ContentDocument.Title, ContentDocument.CreatedDate "
            "FROM ContentDocumentLink WHERE ContentDocument.Title LIKE '%Renewal Packet%' "
            "AND LinkedEntityId IN (" + inlist(chunk) + ")")

def q_sep(chunk):
    return ("SELECT Id, SEP_Risk_Level__c FROM Opportunity WHERE Id IN (" + inlist(chunk) + ")")

def main():
    S.assert_fresh_clock()
    ids = json.load(open(UNIVERSE))
    print(f"[hub] universe (Open/PF) = {len(ids)} opps; shadow={SHADOW}; workers={WORKERS}")

    if RAW_ONLY:
        # cutover: STAGE raw+soql in /tmp; commit into the live _pull/{raw,soql} only after
        # ALL groups succeed, so a mid-pull failure leaves the live dir untouched (clean MCP
        # fallback — no double-counted packets). Live Steps 5-7 then build the CSVs.
        import tempfile as _tf
        stage = _tf.mkdtemp(prefix="hubraw_")
        raw = os.path.join(stage, "raw")
        os.makedirs(raw, exist_ok=True)
        print(f"[hub] RAW_ONLY mode -> staging raw dumps in {stage}; commit to {RAW_DIR} on success")
    else:
        raw = os.path.join(SHADOW, "_pull", "raw")
        soqldir = os.path.join(SHADOW, "_pull", "soql")
        os.makedirs(raw, exist_ok=True); os.makedirs(soqldir, exist_ok=True)
        # universe file where build_csvs.py expects it (parent of _pull)
        shutil.copy(UNIVERSE, os.path.join(SHADOW, "_openpf_ids.json"))
        # run marker BEFORE writing raw, so build_csvs ingests only this run
        open(os.path.join(SHADOW, "_pull", ".run_start"), "w").close()
        time.sleep(1)

    groups = [("intro", q_intro, 500, True), ("recert", q_recert, 500, False),
              ("pk", q_pk, 100, False), ("sep", q_sep, 500, False)]
    counts = {}
    for name, qf, bs, is_agg in groups:
        t0 = time.time()
        # write one raw file per batch (matches the subagent output contract)
        idlist = list(ids)
        tasks = [idlist[i:i+bs] for i in range(0, len(idlist), bs)]
        # pull with concurrency, but persist per-batch so we keep the raw contract
        from concurrent.futures import ThreadPoolExecutor
        soqldir = os.path.join(os.path.dirname(raw), "soql")  # _pull/soql
        os.makedirs(soqldir, exist_ok=True)
        def do(args):
            j, chunk = args
            # pk must preserve the nested ContentDocument{Title,CreatedDate} object
            # that build_csvs.py reads; others are scalar-only (flatten is harmless).
            recs = S.soql_all(qf, chunk, batch=bs, label=f"hub_{name}",
                              outdir=SHADOW, aggregate_max=(bs if is_agg else None),
                              flatten=(name != "pk"))
            with open(os.path.join(raw, f"{name}_0_{j}.json"), "w") as fh:
                json.dump({"records": recs}, fh)
            # write the batch SOQL too, so the task's Step 5 pk coverage check sees this-run ids
            with open(os.path.join(soqldir, f"{name}_0_{j}.sql"), "w") as fh:
                fh.write(qf(chunk))
            return len(recs)
        with ThreadPoolExecutor(max_workers=WORKERS) as ex:
            rc = list(ex.map(do, list(enumerate(tasks))))
        counts[name] = sum(rc)
        print(f"[hub] {name}: {sum(rc)} rows across {len(tasks)} batches in {time.time()-t0:.0f}s")

    cap = S.cap_summary()
    print("[hub] 50K-cap events:", cap if cap else "none ✅")
    if RAW_ONLY:
        # commit: all groups succeeded — copy staged raw+soql into the live _pull dirs
        live_soql = os.path.join(os.path.dirname(RAW_DIR), "soql")
        os.makedirs(RAW_DIR, exist_ok=True); os.makedirs(live_soql, exist_ok=True)
        stage_soql = os.path.join(os.path.dirname(raw), "soql")
        n = 0
        for src_dir, dst_dir in ((raw, RAW_DIR), (stage_soql, live_soql)):
            for fn in os.listdir(src_dir):
                shutil.copy(os.path.join(src_dir, fn), os.path.join(dst_dir, fn)); n += 1
        print(f"[hub] RAW_ONLY committed {n} files to live _pull (raw+soql); task Steps 5-7 build the CSVs.")
        return
    # shadow/standalone: reuse the UNCHANGED parser against the shadow raw dir
    tmp_build = os.path.join(SHADOW, "_pull", "build_csvs.py")
    if os.path.abspath(tmp_build) != os.path.abspath(BUILD_CSVS):
        shutil.copy(BUILD_CSVS, tmp_build)
    print("[hub] running unchanged build_csvs.py on shadow raw ...")
    r = subprocess.run([sys.executable, tmp_build], capture_output=True, text=True)
    print(r.stdout); print(r.stderr, file=sys.stderr)
    print("[hub] CSVs written to", SHADOW)

if __name__ == "__main__":
    main()
