#!/usr/bin/env python3
"""
sf_pull.py — shared Salesforce-CLI pull library for the BenOps dashboard rewire.

Replaces the Salesforce *MCP / in-subagent* data-access layer of the three
dashboards (Advising Hub Phase A, Renewal Stage Gate Phase A, LF pre-pull) with
read-only SOQL run through the `sf` CLI (`sf_cli.sh` + `salesforce_auth.env`).
No metric / definition / classifier logic lives here — this module only *moves
data*. The drivers own the verbatim SOQL (so the SOQL footguns stay visible).

Design rules encoded here (see SF_CLI_REWIRE_PLAN.md §7/§7b/§9):
  * Every read goes through `fetch()` / `soql_all()`, which run `sf data query
    --result-format json` and **assert done==True** on every result.
  * 50K CAP GUARD — `sf data query` silently caps at 50,000 rows / done:False.
    If any query returns totalSize>50000 or done==False, we DO NOT drop rows:
    we automatically re-run it via `sf data export bulk` (Bulk API 2.0, no cap)
    AND write a `SF_50K_CAP_HIT.flag` + print a loud `⚠️ 50K cap hit …` line so
    the pipeline's Slack/DM surfaces it and Aman is told. Callers can also
    pre-empt the cap by id-batching (the 3 pipelines already do).
  * Long SOQL is passed via a temp FILE (`--file`), never a shell arg, so a
    big IN() list can't blow the arg/length limit.
  * `date -u` clock guard so a frozen VM snapshot can't compute a stale window.
  * Results go to disk / returned as dicts — never streamed through model context.

Read-only. Never DML.
"""
import csv
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

SF_ORG = os.environ.get("SF_ORG", "gusto")
SF_HOME = os.environ.get("SF_HOME", "/tmp/sfhome")
SF_CAP = 50000  # sf data query hard cap (rows) -> done:False beyond this
FLAG_NAME = "SF_50K_CAP_HIT.flag"

# collected so a driver / scheduled task can relay them to Slack/DM
CAP_EVENTS = []


def _env():
    e = dict(os.environ)
    e["HOME"] = SF_HOME
    return e


def _run(args, timeout=1800):
    return subprocess.run(args, capture_output=True, text=True, env=_env(), timeout=timeout)


# ---------------------------------------------------------------- clock guard
def assert_fresh_clock(max_skew_min=90):
    """Abort if the VM clock is implausibly behind real UTC (frozen snapshot)."""
    r = _run(["date", "-u", "+%s"])
    vm = int(r.stdout.strip())
    now = int(time.time())
    skew = abs(now - vm) / 60.0
    if skew > max_skew_min:
        raise RuntimeError(f"clock skew {skew:.0f}min > {max_skew_min}min — refusing to run on a stale VM clock")
    return datetime.now(timezone.utc)


# ------------------------------------------------------------------ 50K flag
def flag_50k(query, label, outdir, got, total):
    msg = (f"⚠️ 50K cap hit on [{label}] — sf data query returned {got} of {total} "
           f"rows (done:False). Falling back to `sf data export bulk` (no cap). "
           f"Query: {query[:160].replace(chr(10),' ')}…")
    print(msg, file=sys.stderr)
    CAP_EVENTS.append(msg)
    try:
        os.makedirs(outdir, exist_ok=True)
        with open(os.path.join(outdir, FLAG_NAME), "a") as fh:
            fh.write(f"{datetime.now(timezone.utc).isoformat()}\t{label}\t{got}/{total}\n")
    except Exception as e:  # flagging must never crash the pull
        print(f"(could not write {FLAG_NAME}: {e})", file=sys.stderr)


def cap_summary():
    """One-line status for a pipeline's DM: '' if clean, else the warnings."""
    return "" if not CAP_EVENTS else " | ".join(CAP_EVENTS)


# --------------------------------------------------------------- core query
def _query_json(soql):
    """Run one SOQL via `sf data query --file` (arg-length safe). Returns the
    parsed `result` dict: {records, totalSize, done, ...}."""
    with tempfile.NamedTemporaryFile("w", suffix=".soql", delete=False) as tf:
        tf.write(soql)
        qf = tf.name
    try:
        r = _run(["sf", "data", "query", "--target-org", SF_ORG,
                  "--file", qf, "--result-format", "json"])
        if r.returncode != 0:
            raise RuntimeError(f"sf data query failed: {r.stderr.strip()[:500]}")
        return json.loads(r.stdout)["result"]
    finally:
        os.unlink(qf)


def _strip_nested(obj):
    """Recursively drop SF 'attributes' envelopes but PRESERVE nesting — i.e.
    reproduce exactly what the MCP/REST query returned (e.g. ContentDocument as a
    nested {Title, CreatedDate} dict, Parent as a nested dict). Use for raw dumps
    that a downstream parser reads by nested key."""
    if isinstance(obj, list):
        return [_strip_nested(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _strip_nested(v) for k, v in obj.items() if k != "attributes"}
    return obj


def _strip(records):
    """Drop SF 'attributes' envelopes; flatten one level of nested relationship
    dicts into dotted keys (Parent.Opportunity__c -> 'Parent.Opportunity__c')."""
    out = []
    for rec in records:
        flat = {}
        for k, v in rec.items():
            if k == "attributes":
                continue
            if isinstance(v, dict):
                inner = {ik: iv for ik, iv in v.items() if ik != "attributes"}
                if len(inner) == 1:
                    flat[k] = list(inner.values())[0]
                else:
                    for ik, iv in inner.items():
                        flat[f"{k}.{ik}"] = iv
                    if not inner:
                        flat[k] = None
            else:
                flat[k] = v
        out.append(flat)
    return out


def _bulk_export(soql, label, outdir):
    """No-cap fallback: Bulk API 2.0 to a CSV on disk, parsed back to dicts."""
    out_csv = os.path.join(tempfile.gettempdir(), f"sfbulk_{label}_{int(time.time())}.csv")
    with tempfile.NamedTemporaryFile("w", suffix=".soql", delete=False) as tf:
        tf.write(soql)
        qf = tf.name
    try:
        r = _run(["sf", "data", "export", "bulk", "--target-org", SF_ORG,
                  "--query-file", qf, "--output-file", out_csv,
                  "--result-format", "csv", "--wait", "30"])
        if r.returncode != 0:
            raise RuntimeError(f"sf data export bulk failed: {r.stderr.strip()[:500]}")
        with open(out_csv, newline="") as fh:
            rows = list(csv.DictReader(fh))
        return rows
    finally:
        os.unlink(qf)
        if os.path.exists(out_csv):
            os.remove(out_csv)


def fetch(soql, label="query", outdir="."):
    """Run ONE SOQL with the done==True assertion + 50K auto-bulk fallback+flag.
    Use for non-batched queries (e.g. a cohort universe). Returns list[dict]."""
    d = _query_json(soql)
    total = d.get("totalSize", 0)
    done = d.get("done", True)
    recs = d.get("records", [])
    if total > SF_CAP or not done or len(recs) >= SF_CAP:
        flag_50k(soql, label, outdir, len(recs), total)
        return _strip(_strip_bulk(_bulk_export(soql, label, outdir)))
    return _strip(recs)


def _strip_bulk(rows):
    # bulk CSV rows are already flat dicts; wrap so _strip is a no-op-safe pass
    return [{k: v for k, v in r.items()} for r in rows]


def _run_batch(args):
    i, chunk, build_query, label, outdir, aggregate_max, flatten = args
    q = build_query(chunk)
    d = _query_json(q)
    total = d.get("totalSize", 0)
    done = d.get("done", True)
    recs = d.get("records", [])
    if total > SF_CAP or not done or len(recs) >= SF_CAP:
        flag_50k(q, f"{label}[{i}:{i+len(chunk)}]", outdir, len(recs), total)
        return _strip_bulk(_bulk_export(q, label, outdir))
    if aggregate_max is not None and len(recs) > aggregate_max:
        raise RuntimeError(f"[{label}] aggregate returned {len(recs)}>{aggregate_max} "
                           f"groups — shrink the id batch (2,000-group cap).")
    return _strip(recs) if flatten else _strip_nested(recs)


def soql_all(build_query, ids, batch=500, label="query", outdir=".",
             aggregate_max=None, workers=1, flatten=True):
    """Batch an IN()-style query over `ids`.
      build_query(id_chunk:list) -> SOQL string   (driver owns verbatim SOQL)
      batch                      -> ids per call (Hub agg=500/sel=100, RSG/LF ~120-150)
      aggregate_max              -> if set, assert rows<=aggregate_max (2k group cap guard)
      workers                    -> parallel `sf` subprocesses (I/O-bound; safe, order-independent)
    Per batch: assert done==True; on cap -> bulk fallback + flag Aman. Returns list[dict].
    """
    ids = list(ids)
    tasks = [(i, ids[i:i + batch], build_query, label, outdir, aggregate_max, flatten)
             for i in range(0, len(ids), batch)]
    out = []
    if workers <= 1:
        for t in tasks:
            out.extend(_run_batch(t))
    else:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for res in ex.map(_run_batch, tasks):
                out.extend(res)
    return out


def write_json(path, obj):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return path


def write_csv(path, rows, fieldnames):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path
