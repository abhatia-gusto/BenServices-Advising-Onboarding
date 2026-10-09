# Benefit Services SLA/SLO Scorecard — portable source-of-truth

Everything needed to reproduce the **Benefit Services scorecard** (team view, PE/team-lead view,
and IC view) on **any machine** with Snowflake access — no pre-refreshed CSVs, no dependence on one
person's computer. Same pattern as the sibling dashboard folders in this repo
(`advising-performance/`, `npr-onboarding/`, `broker-onboarding/`, `advising-mrr/`).

## What's here
- `queries/` — the **canonical source SQL**, one file per source (run verbatim). These are the
  source-of-truth definitions behind every metric.
- `lib/` — the compute + render scripts (byte-for-byte the ones that produced the published
  scorecard) plus the team widget template and `new_hire_default_off.json` (the IC recent-hire
  `**` flag list; recent hires render inline with a solid divider (no shading)).
- `fetch_live.py` — **materializer**: runs each query in `queries/` live against Snowflake and
  writes the exact input artifacts `lib/` consumes.
- `run.py` — end-to-end: materialize → run compute/render → emit the three views.
- `catalog.json` — machine-readable map of source → query → params → artifact → metrics.

## Run it
```bash
# 1. deps
pip install snowflake-connector-python            # or: pip install --target=/tmp/sfpkg ... && export PYTHONPATH=/tmp/sfpkg

# 2. creds — either env vars …
export SNOWFLAKE_ACCOUNT=GUSTO-WAREHOUSE SNOWFLAKE_USER=you@gusto.com SNOWFLAKE_PAT=... \
       SNOWFLAKE_ROLE=... SNOWFLAKE_WAREHOUSE=GUSTIE_ADHOC_WH SNOWFLAKE_DATABASE=... SNOWFLAKE_SCHEMA=...
#    … or a key=value file and pass --creds path/to/snowflake_pat.env

# 3. build all three views for a month
python3 run.py --through 2026-10
#    options: --start 2025-11   --views team,pe,pepe,ic   --window 2026-08,2026-09,2026-10 (IC quarter)
#             --workdir _run     --skip-fetch (reuse already-materialized inputs)
```
Outputs land in `--workdir` (default `./_run`):
- **team**: `_scorecard_combined_widget.html` (tables + cancel charts), `BenOps_Scorecard_TeamView_<Mon><Yr>.html`
- **pe** (team-lead layer): `_scorecard_pe2_combined.html`, `_scorecard_pe2_sbs.html`, `BenOps_Scorecard_PEbyLead_<Mon><Yr>.html`
- **pepe** (leadership layer — Micah/Lynne/Lee Ann/Aman/Martin as columns): `_scorecard_pe_combined.html`, `BenOps_Scorecard_PE_<Mon><Yr>.html`
- **ic**: `_scorecard_ic_sbs.html`, `BenOps_Scorecard_IC_<Q>.html` (recent hires flagged `**` inline with a solid divider, no shading)

The `_*.html` fragments are self-contained — paste into `show_widget`, or open the standalone files.

## Connector gotcha (read this)
Pass the PAT as **`token=`** with `authenticator='PROGRAMMATIC_ACCESS_TOKEN'` and **`region='us-west-2'`** —
NOT `password=`. Wrong field or missing region returns a misleading `08001 … token is invalid`.
Use a synchronous `cur.execute()` (the async result path returns a stale 1-column description).

## How it reproduces the published numbers
`fetch_live.py` runs each query **verbatim** over a wide window (2024-01-01→today; MRR 2023-05-01→today)
and the bundled compute buckets by close/end month into fiscal quarters (May–Apr; a quarter cell is
Σnumerator ÷ Σdenominator, never an average of monthly %). Because the compute/render code is the
same code that produced the published views, the output is identical. Team-grain equality to the
live source queries is certified by the full metric-by-metric live audit (34/37 PASS, 3 documented
query-vs-scorecard quirks) described in the `benefit-services-scorecard` skill. PE and IC are the
same rows grouped by `OWNER_PE_NAME_CURRENT` / `OWNER_PEPE_CURRENT` / owner, so
**Σ IC = PE = leader = team = scorecard** by construction.

## Ownership hierarchy
IC → **PE** (`OWNER_PE_NAME_CURRENT` / `PE_NAME`, the IC's team lead) → **PEPE** (`OWNER_PEPE_CURRENT`
/ `PEPE_NAME`, the leader = a direct of the BenOps owner). The ex-Rehana NP&R leads
(Kelly / Adrienne / Alex / Brooke) roll up to the BenOps owner directly in-source.

## Guardrail
The `queries/` are the canonical dashboard definitions — run them **as written**. Change the date
window, re-slice, or enrich the *results*; do not rewrite joins/filters/CTEs. A definition change is
a dashboard change (query → pipeline → repo → skill), owned by the scorecard owner.

Access: repo is enterprise-internal on the `abhatia-gusto` Gusto EMU account — readable by any Gusto
enterprise GitHub member. A 404 means your GitHub isn't connected/authenticated as a Gusto user.

## Recent updates (Oct 2026)
- **Ticket SLA now in the PE / PEPE / IC views** (was team-only). Two rows, same v12 flow
  definition and 5-day close-month calc as the team view:
  - **OA→Advising Ticket SLA (≤5d)** under Advising — attributed by **ticket owner → current PE**
    (that flow's owner *is* the Implementation Advocate / Advising rep; ~98% mapped).
  - **Ful→OA Ticket SLA (≤5d)** under NP&R — attributed by **benefit-order owner → current PE**
    (the ticket owner is a Fulfillment rep, so the NP&R-relevant owner is the BO owner; ~99–100% mapped).
  Goal ≥80, amber ≥70. Σ PE reconciles to team (NP&R 78.7 vs 78.8; Advising 68.8 = 68.8).
- **PE-by-lead view: Σ leader-aggregate ("blended") column** — each leader's team-lead PEs, then a
  volume-weighted Σ column for that leader after a solid divider (in `scorecard_pe2_sidebyside.py`
  and Section B of `scorecard_pe2_render.py`).
- **IC view: recent hires inline** with a single solid divider (no shaded section), still `**`-flagged
  and color-coded (`scorecard_ic_sidebyside.py`).
- **All-metrics verification** (`lib/scorecard_reconcile.py`) — `run.py` runs it automatically when
  both team + pepe are built: for the latest quarter it ties Σ leadership back to the team value per
  metric (PASS/FAIL within 0.6pp / 0.02; phone & email reported as coverage-bounded INFO).
