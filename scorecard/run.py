#!/usr/bin/env python3
"""
Benefit Services Scorecard — portable end-to-end runner.

  materialize live (fetch_live.py)  →  run the bundled compute+render scripts verbatim  →
  emit the three view fragments (team / PE / IC) + standalone HTML, all under --workdir.

The compute/render scripts in lib/ are byte-for-byte the ones that produced the published
scorecard; we only stage them into the workdir next to the freshly-materialized inputs and run
them, so the output is identical to the published views on any machine.

Usage:
  python3 run.py --through 2026-10 [--start 2025-11] [--workdir _run]
                 [--views team,pe,ic] [--skip-fetch] [--creds snowflake_pat.env]
                 [--window 2026-08,2026-09,2026-10]   # IC quarter; default = latest FY quarter

Outputs in <workdir>:
  team : scorecard_team_data.json, _scorecard_combined_widget.html (tables+cancel charts),
         BenOps_Scorecard_TeamView_<Mon><Yr>.html
  pe   : scorecard_pe2_data.json, _scorecard_pe2_combined.html, _scorecard_pe2_sbs.html,
         BenOps_Scorecard_PEbyLead_<Mon><Yr>.html   (team-lead / PE layer)
  pepe : scorecard_pe_data.json, _scorecard_pe_combined.html,
         BenOps_Scorecard_PE_<Mon><Yr>.html          (leadership / PEPE layer: Micah/Lynne/Lee Ann/Aman/Martin)
  ic   : scorecard_ic_data.json, _scorecard_ic_sbs.html, BenOps_Scorecard_IC_<Q>.html
         (recent hires flagged ** and sectioned right)
"""
import os, sys, shutil, subprocess, argparse, glob
HERE = os.path.dirname(os.path.abspath(__file__))
LIB = os.path.join(HERE, "lib")
PY = sys.executable

def stage(workdir):
    os.makedirs(workdir, exist_ok=True)
    for f in glob.glob(os.path.join(LIB, "*")):
        shutil.copy(f, os.path.join(workdir, os.path.basename(f)))

def step(workdir, script, *extra):
    cmd = [PY, os.path.join(workdir, script), *extra]
    print(">>", " ".join(os.path.basename(x) for x in cmd))
    r = subprocess.run(cmd, cwd=workdir)
    if r.returncode != 0:
        sys.exit("step failed: %s" % script)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--through", required=True, help="YYYY-MM (last month in view)")
    ap.add_argument("--start", help="YYYY-MM first month (default: Q3 of prior FY)")
    ap.add_argument("--window", help="IC quarter months, comma list (default: latest FY quarter)")
    ap.add_argument("--workdir", default=os.path.join(HERE, "_run"))
    ap.add_argument("--views", default="team,pe,pepe,ic",
                    help="team=4-team view; pe=team-lead (PE) layer; pepe=leadership (PEPE) layer; ic=per-IC")
    ap.add_argument("--skip-fetch", action="store_true", help="reuse inputs already in workdir")
    ap.add_argument("--creds", default=os.path.join(HERE, "snowflake_pat.env"))
    a = ap.parse_args()
    views = set(v.strip() for v in a.views.split(",") if v.strip())
    wd = os.path.abspath(a.workdir)

    stage(wd)
    if not a.skip_fetch:
        r = subprocess.run([PY, os.path.join(HERE, "fetch_live.py"),
                            "--workdir", wd, "--through", a.through, "--creds", a.creds])
        if r.returncode != 0:
            sys.exit("fetch_live failed")

    tcompute = ["--through", a.through] + (["--start", a.start] if a.start else [])
    if "team" in views:
        step(wd, "scorecard_team_compute.py", *tcompute)
        step(wd, "scorecard_team_render.py")
        step(wd, "scorecard_cancel_render.py", "--through", a.through)
    if "pe" in views:
        step(wd, "scorecard_pe2_compute.py", *tcompute)
        step(wd, "scorecard_pe2_render.py")
        step(wd, "scorecard_pe2_sidebyside.py")
    if "pepe" in views:
        step(wd, "scorecard_pe_compute.py", *tcompute)
        step(wd, "scorecard_pe_render.py")
    if "ic" in views:
        step(wd, "scorecard_ic_compute.py", *(["--window", a.window] if a.window else []))
        step(wd, "scorecard_ic_sidebyside.py")

    print("\nOutputs in", wd)
    for p in ["_scorecard_combined_widget.html", "_scorecard_pe2_combined.html",
              "_scorecard_pe2_sbs.html", "_scorecard_pe_combined.html", "_scorecard_ic_sbs.html"]:
        fp = os.path.join(wd, p)
        if os.path.exists(fp):
            print("  %-36s %d bytes" % (p, os.path.getsize(fp)))

if __name__ == "__main__":
    main()
