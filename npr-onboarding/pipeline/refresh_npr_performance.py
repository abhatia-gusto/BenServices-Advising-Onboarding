#!/usr/bin/env python3
"""NPR (New Plan & Renewal Onboarding) Performance — end-to-end refresh + publish.

Chain (run from oa_dash/):
  1. run_sql.py q_<x>.sql data/<x>.json   for all 10 inputs (windows auto-advance: SQLs end at CURRENT_DATE())
  2. build_data3.py                        -> oa_data.json (MONTHS now dynamic through today)
  3. gen8.py                               -> np_renewal_onboarding_performance_dashboard_v6.html (dynamic footer)
  4. STALENESS GUARD: abort publish if the freshest month with order volume didn't reach last month
  5. ../share_npr_onboarding_performance.py --file <oa_dash v6.html>   (publish the FRESH oa_dash file,
        NOT the stale root copy the script defaults to)

Run:  python3 refresh_npr_performance.py [--no-publish]
"""
import os, sys, subprocess, json, datetime, pathlib

HERE = pathlib.Path(__file__).resolve().parent          # oa_dash/
ROOT = HERE.parent                                        # BenOps Dashboard Co-Work/
V6   = HERE / "np_renewal_onboarding_performance_dashboard_v6.html"

# data/<json>  <-  q_<sql>.sql   (bo=v2, ticketsla=v4 canonical)
PULLS = [
    ("q_roster.sql",       "data/roster.json"),
    ("q_bo_v2.sql",        "data/bo.json"),
    ("q_ticketsla_v4.sql", "data/ticketsla.json"),
    ("q_qa.sql",           "data/qa.json"),
    ("q_abandon.sql",      "data/abandon.json"),
    ("q_avail.sql",        "data/avail.json"),
    ("q_abandon_ic.sql",   "data/abandon_ic.json"),
    ("q_csat_rows.sql",    "data/csat_rows.json"),
    ("q_email_ic.sql",     "data/email_ic.json"),
    ("q_maestro_ic.sql",   "data/maestro_ic.json"),
]

def sh(args, cwd=HERE):
    env = os.environ.copy()
    env["PATH"] = f"{os.path.expanduser('~')}/.local/bin:" + env.get("PATH", "")
    print(f"\n$ {' '.join(str(a) for a in args)}", flush=True)
    r = subprocess.run([sys.executable] + [str(a) for a in args], cwd=str(cwd), env=env)
    if r.returncode != 0:
        raise SystemExit(f"step failed: {args}")

def staleness_guard():
    """Fail loudly if the pull didn't advance (e.g. a query silently re-locked to an old window)."""
    data = json.load(open(HERE / "oa_data.json"))
    months = data.get("months", [])
    tot = {m: 0 for m in months}
    for ic in data.get("ics", []):
        for m, md in (ic.get("months") or {}).items():
            tot[m] = tot.get(m, 0) + (md.get("ord", 0) or 0)
    with_data = [m for m in months if tot.get(m, 0) > 0]
    latest = max(with_data) if with_data else None
    today = datetime.date.today()
    prev_month = (today.replace(day=1) - datetime.timedelta(days=1)).strftime("%Y-%m")
    print(f"  guard: latest month with volume = {latest}; require >= {prev_month}")
    if latest is None or latest < prev_month:
        raise SystemExit(f"STALENESS GUARD FAILED: data only reaches {latest}, expected >= {prev_month}. "
                         f"A source query likely didn't advance — NOT publishing.")
    print("  guard OK")

def main():
    publish = "--no-publish" not in sys.argv
    for sql, out in PULLS:
        sh(["run_sql.py", sql, out])
    sh(["build_data3.py"])
    sh(["gen8.py"])
    staleness_guard()
    # gen8 does NOT emit the Excel export — re-inject it (payload built from the just-built
    # data already embedded in v6, so no extra data pull). Without this it drops every rebuild.
    sh([ROOT / "add_npr_export.py", V6], cwd=ROOT)
    # sanity: footer + export survived
    s = V6.read_text(encoding="utf-8")
    assert "Data updated as of</b>" in s and "Last published</b>" in s, "dynamic footer missing in built v6"
    assert 'id="benopsXlsxBtn"' in s and '__EXPORT_DATA__' in s, "Excel export missing after inject"
    # sanity: Data Resources SQL catalog rendered (advising-style segment cards)
    assert s.count('class="dr-card') >= 10, "Data Resources SQL catalog missing/incomplete in built v6"
    assert 'data-seg="level_ai_qa"' in s and 'data-seg="email_sla"' in s, "Data Resources segments missing in built v6"
    if publish:
        sh([ROOT / "share_npr_onboarding_performance.py", "--file", V6], cwd=ROOT)
        print("\nPublished npr-onboarding-performance from the FRESH oa_dash v6.html.")
    else:
        print("\n--no-publish: built locally only.")
    print("DONE")

if __name__ == "__main__":
    main()
