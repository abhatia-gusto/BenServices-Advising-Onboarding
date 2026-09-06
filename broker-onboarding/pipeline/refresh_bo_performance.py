#!/usr/bin/env python3
"""Broker Onboarding Performance — end-to-end refresh + publish (one command).

Chains the full pipeline so BO Perf is reproducible from the folder:
  1. bootstrap snow CLI config from snowflake_pat.env (self-heals across sessions)
  2. refresh_june.py roster|lai|byb|bt   -> /tmp/roster.csv, /tmp/lai_janmay.csv,
                                            queries/{byb,bt}_data_2025-09-01_to_<END>.csv
  3. run_bo_phone.py                     -> /tmp/bo_{avail,abandon}_month.csv (shared Call-Dashboard
                                            method, BO 70-105 band), /tmp/bo_{phone,lai}_rollup.csv
  4. bo_diag_pull.py                     -> /tmp/bo_{email,csat}_month.csv, bo_csat_comments.csv,
                                            bo_qc_month.csv, bo_qc_detail.csv (canonical bo_qc_errors.sql)
  5. build_bo_perf_v2.py                 -> /tmp/varD2.json
  6. add_diagnostics.py                  -> /tmp/varD3.json
  7. inject varD3 into bo_perf_v3_template.html -> broker_onboarding_performance_dashboard_v3.html
  8. publish to the main slug only: share_bo_performance.py (broker-onboarding-performance). The -oa skin was retired 2026-08-17 (no longer built/published).

Window is FULLY DYNAMIC — no manual date bumping. END defaults to today (override via PERF_END env)
in refresh_june.py / run_bo_phone.py / bo_diag_pull.py / build_bo_perf_v2.py; build_bo_perf_v2 derives
its MONTHS via _mrange(2026-01 .. END-month); add_diagnostics derives MONTHS from varD2.json["months"]
(so email/csat/qc always match the core window incl. the current partial month); the email SQL end-date
is parameterized via {{PERF_END}} in queries/bo_email_month.sql (substituted in bo_diag_pull.py).
Footer is stamped "Data as of {today-1 = T-1} · Last published {today}" (DATA_ASOF / REFRESHED_ON).
Level AI is canonical (bi.cases record-type filter). Availability band = 70-105 (BO floor, per Aman 2026-07-06).
Run:  python3 refresh_bo_performance.py            (build + publish)
      python3 refresh_bo_performance.py --no-publish
"""
import os, sys, subprocess, json
HERE=os.path.dirname(os.path.abspath(__file__)); HOME=os.path.expanduser("~")

def sh(args):
    env=os.environ.copy(); env["PATH"]=f"{HOME}/.local/bin:"+env.get("PATH","")
    print(f"\n$ {' '.join(args)}")
    r=subprocess.run(["python3"]+args, cwd=HERE, env=env)
    if r.returncode!=0: raise SystemExit(f"step failed: {args}")

def bootstrap_snow():
    """Write ~/.config/snowflake/config.toml from snowflake_pat.env if missing."""
    cfg=os.path.expanduser("~/.config/snowflake/config.toml")
    if os.path.exists(cfg): return
    env={}
    for line in open(os.path.join(HERE,"snowflake_pat.env")):
        line=line.strip()
        if line and not line.startswith("#") and "=" in line:
            k,v=line.split("=",1); env[k]=v
    os.makedirs(os.path.dirname(cfg),exist_ok=True)
    open(cfg,"w").write(
f'''[connections.default]
account = "{env["SNOWFLAKE_ACCOUNT"]}"
user = "{env["SNOWFLAKE_USER"]}"
authenticator = "PROGRAMMATIC_ACCESS_TOKEN"
token = "{env["SNOWFLAKE_PAT"]}"
role = "{env["SNOWFLAKE_ROLE"]}"
warehouse = "{env["SNOWFLAKE_WAREHOUSE"]}"
database = "{env["SNOWFLAKE_DATABASE"]}"
schema = "{env["SNOWFLAKE_SCHEMA"]}"
''')
    os.chmod(cfg,0o600); print("bootstrapped snow config from snowflake_pat.env")

def main():
    publish = "--no-publish" not in sys.argv
    bootstrap_snow()
    for step in ("roster","lai","byb","bt"):
        sh(["refresh_june.py", step])
    sh(["run_bo_phone.py"])
    sh(["bo_diag_pull.py"])
    sh(["build_bo_perf_v2.py"])
    sh(["add_diagnostics.py"])
    # inject varD3 -> v3 html
    tpl=open(os.path.join(HERE,"bo_perf_v3_template.html")).read()
    d=open("/tmp/varD3.json").read()
    assert "var D=__DATA__" in tpl, "template placeholder missing"
    import datetime
    refreshed=datetime.date.today().strftime("%B %-d, %Y")
    # Snowflake loads T-1, so the newest complete data date is the day before the run.
    asof=(datetime.date.today()-datetime.timedelta(days=1)).strftime("%B %-d, %Y")
    out=os.path.join(HERE,"broker_onboarding_performance_dashboard_v3.html")
    open(out,"w").write(tpl.replace("var D=__DATA__","var D="+d)
                        .replace("__DATA_ASOF__",asof).replace("__REFRESHED__",refreshed))
    print(f"wrote {out} ({os.path.getsize(out)} bytes)")
    # re-inject the Excel export (payload regenerated from fresh D + static JS blocks);
    # lives here, not in the template, so it always carries current data and survives rebuilds.
    import add_bo_export
    add_bo_export.inject(out)
    if publish:
        sh(["share_bo_performance.py"])     # main slug broker-onboarding-performance (-oa skin retired 2026-08-17)
        print("\nPublished to broker-onboarding-performance (main).")
    else:
        print("\n--no-publish: built locally only.")
    print("DONE")

if __name__=="__main__":
    main()
