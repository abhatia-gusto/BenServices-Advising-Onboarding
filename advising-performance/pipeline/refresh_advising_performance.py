#!/usr/bin/env python3
"""Advising Performance dashboard — end-to-end refresh + publish (one command).

Chain (mirrors refresh_bo_performance.py):
  1. pull_v11_core_data.py     -> v11_core_data.json     (opps/BOs/tickets/quality + availability + abandon, through PERF_END/today)
  2. pull_v11_period_data.py   -> v11_period_data.json   (calls + Level-AI channels by month)
  3. build_diagnostic_data.py  -> diagnostic_data.json   (CSAT/InApp from CSVs + Email SLA pulled fresh via snow)
  4. inject_v11_core_data.py       (rebuilds D.advisors/icDetail/availData/abandonData in advising_performance_dashboard_v11.html)
  5. inject_v11_period_data.py     (adds D.callsByMo, D.levelAiChannelsByMo)
  6. inject_diagnostic_v11.py      (adds D.csatData, D.inappData, D.emailSlaData)
  7. share_advising_performance.py (publish slug advising-performance-dashboard)

The inject_* steps patch the D object in place, so the export button and the dynamic
"Data through {month} / Refreshed {date}" footer edits are preserved on rebuild.

Windows auto-advance: pull scripts read PERF_END or default to today.
NOTE: refresh_diagnostic_csvs.py now re-pulls CSAT + In-App Sentiment fresh from
Snowflake each run (window end = PERF_END/today), and build_diagnostic_data.py reads
the newest CSV with a dynamic month window — so CSAT/InApp, Email SLA, scored opp
metrics, and availability are all fresh through the current (partial) month.

Run:  python3 refresh_advising_performance.py [--no-publish]
"""
import os, sys, subprocess, pathlib

def find_mount():
    for p in pathlib.Path('/sessions').glob('*/mnt/BenOps Dashboard Co-Work'):
        return str(p)
    return os.path.dirname(os.path.abspath(__file__))

HERE = find_mount()

def sh(args):
    env = os.environ.copy()
    env["PATH"] = f"{os.path.expanduser('~')}/.local/bin:" + env.get("PATH", "")
    print(f"\n$ {' '.join(args)}", flush=True)
    r = subprocess.run(["python3"] + args, cwd=HERE, env=env)
    if r.returncode != 0:
        raise SystemExit(f"step failed: {args}")

def main():
    publish = "--no-publish" not in sys.argv
    for step in ("pull_v11_core_data.py", "pull_v11_period_data.py",
                 "refresh_diagnostic_csvs.py", "build_diagnostic_data.py",
                 "inject_v11_core_data.py", "inject_v11_period_data.py", "inject_diagnostic_v11.py",
                 "inject_data_resources.py"):
        sh([step])
    # verify the built HTML still carries the export + dynamic date
    html = os.path.join(HERE, "advising_performance_dashboard_v11.html")
    s = open(html, encoding="utf-8").read()
    assert 'id="benopsXlsxBtn"' in s, "export button missing after rebuild"
    assert 'class="perfDT"' in s and 'class="perfRE"' in s, "dynamic status spans missing"
    assert "July 16, 2026" not in s, "stale hardcoded date reappeared"
    # Current-PE guard: advisors[*].pe (drives the PE filter/grouping) must match peMap.
    import json as _json
    def _extract(src, key):
        i = src.find('"%s"' % key); j = src.find(":", i) + 1
        while src[j] in " \n": j += 1
        oc = src[j]; cc = "]" if oc == "[" else "}"; depth = 0; k = j; instr = False; esc = False
        while k < len(src):
            c = src[k]
            if instr:
                if esc: esc = False
                elif c == "\\": esc = True
                elif c == '"': instr = False
            else:
                if c == '"': instr = True
                elif c == oc: depth += 1
                elif c == cc:
                    depth -= 1
                    if depth == 0: return src[j:k+1]
            k += 1
    _adv = _json.loads(_extract(s, "advisors")); _pem = _json.loads(_extract(s, "peMap"))
    _mismatch = [a["name"] for a in _adv if a.get("pe") != _pem.get(a["name"])]
    assert not _mismatch, f"advisors[*].pe out of sync with current peMap: {_mismatch[:10]}"
    print(f"verify OK: export button + dynamic date spans present, no stale date; PE in sync ({len(_adv)} advisors)")
    if publish:
        sh(["share_advising_performance.py"])
        print("\nPublished to advising-performance-dashboard.")
    else:
        print("\n--no-publish: built locally only.")
    print("DONE")

if __name__ == "__main__":
    main()
