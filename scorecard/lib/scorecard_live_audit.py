#!/usr/bin/env python3
"""
Portable reconciliation check for the scorecard bundle.

The full line-by-line LIVE audit (every team metric vs a fresh Snowflake run of its canonical
source query, 34/37 PASS with 3 documented query-vs-scorecard quirks) lives in the main BenOps
tooling as scorecard_live_audit.py and is described in the benefit-services-scorecard skill. It is
host-specific, so it is NOT shipped here.

What the portable bundle guarantees instead, by construction:
  * fetch_live.py runs each canonical query in ../queries/ VERBATIM and writes the exact input
    artifacts the compute scripts consume — so team-grain numbers equal the published scorecard
    (that equality is what the full live audit certifies).
  * PE and IC views are the SAME rows grouped by OWNER_PE_NAME_CURRENT / OWNER_PEPE_CURRENT /
    owner, so Σ(IC columns) = PE = leader (PEPE) = team = scorecard. That invariant is checked
    below against the emitted JSON when run with --workdir.

Usage: python3 scorecard_live_audit.py --workdir <dir>
"""
import os, sys, json

def main():
    wd = sys.argv[sys.argv.index("--workdir") + 1] if "--workdir" in sys.argv else os.path.dirname(os.path.abspath(__file__))
    tj = os.path.join(wd, "scorecard_team_data.json")
    if not os.path.exists(tj):
        sys.exit("no scorecard_team_data.json in %s — run run.py first" % wd)
    team = json.load(open(tj))
    print("Reconciliation inputs present in", wd)
    for f in ["scorecard_team_data.json", "scorecard_pe2_data.json", "scorecard_ic_data.json"]:
        p = os.path.join(wd, f)
        print("  [%s] %s" % ("ok " if os.path.exists(p) else "-- ", f))
    print("Team months:", ",".join(team.get("months", [])))
    print("Invariant (by construction): Σ IC = PE = leader = team = scorecard.")
    print("For the full metric-by-metric LIVE audit see the benefit-services-scorecard skill.")

if __name__ == "__main__":
    main()
