# Renewal Stage Gate — pipeline (source of truth)

Canonical code behind the **Renewal Stage Gate** app (Gate 1, Advising → OA) — the
single-opp lookup tool published to ShareSomething at slug `renewal-stage-gating-check`
(Gusto-internal). This folder is self-contained: clone it, add your own credential
files, and it runs on any machine with no reference to anyone's local setup.

> **Data & secrets never live here.** No `.env`, no `sf_cache.json` / `rsg_bundles.json`,
> no built `*.html` with embedded rows. Those are produced locally at run time and are
> git-ignored. Only code + the query-bearing tool template are tracked.

## Layout

```
renewal-stage-gate/
├── README.md                         # this file
├── requirements.txt                  # pip deps (snowflake-connector-python)
├── sf_cli.sh                         # Salesforce CLI shim (reads salesforce_auth.env)
├── gh_cli.sh                         # GitHub shim (reads github_pat.env) — optional
├── _cli_rewire/
│   ├── common/sf_pull.py             # shared read-only SOQL library (50K-cap guard, clock guard)
│   └── renewal-stage-gate/pull_cli.py# SF phase driver: pull cohort+related, assemble, classify
└── _rsg_pipeline/
    ├── renewal-gate-check-tool.html  # the tool — SOQL + SNOW_A–F live here VERBATIM
    ├── _assemble_sf.py               # writes sf_cache.json / sf_last_updated.json / cohort.json
    ├── classify_notes.py             # recert-note classifier + sanitizer (the PII step)
    ├── build_bundles.py              # Snowflake phase: SNOW_A–F per opp → rsg_bundles.json
    ├── build_final.py                # bakes the themed renewal-stage-gating-check.html
    └── README_pipeline.md            # original pipeline notes
```

## Credential files you add (at this folder's top level — git-ignored)

| File | Purpose |
|---|---|
| `salesforce_auth.env` | sfdx auth URL (`force://…`) — mint via `sf org login web` on your Mac |
| `snowflake_pat.env`   | `SNOWFLAKE_PAT` + `SNOWFLAKE_USER` + account/role/warehouse (read by `build_bundles.py`) |
| `sharesome_publish.env` | `SHARESOME_PUBLISH_TOKEN` for publishing |
| `github_pat.env`      | bare `ghp_…` token — only if you use `gh_cli.sh` |

`build_bundles.py` reads account/user/role/warehouse from `snowflake_pat.env` (no hardcoded
identity), so each operator runs under their own Snowflake user.

## Run

```bash
export BEN="$(pwd)"                 # this folder = the pipeline root
# --- SF phase ---
source sf_cli.sh && sf_ready
RSG_SHADOW="$BEN/_rsg_pipeline" BEN="$BEN" python3 _cli_rewire/renewal-stage-gate/pull_cli.py
# --- Snowflake + bake ---
pip install -r requirements.txt
cd _rsg_pipeline
#   (fetch the 3A master list Google Sheet, tab "Medical", into scheme.txt first)
python3 build_bundles.py
python3 build_final.py
#   publish _rsg_pipeline/../renewal-stage-gating-check.html to ShareSomething
#   slug renewal-stage-gating-check, owner key zhsP7r6WEzIJ7yMe
```

Cohort window is dynamic "+4": `Renewal_Date__c` from fixed floor `2026-07-01` through the
last day of the month 4 calendar months ahead of the current month (computed at run time).

## Guardrails

- SNOW_A–F + SOQL run **verbatim** — changing them is a dashboard change (query → pipeline →
  repo → skill), owned by Aman. Enriching/joining *results* is fine; editing the SQL is not.
- No raw recert-note text and no street address ever persist past the SF phase or appear in the
  baked HTML — company-grain only. `classify_notes.py` enforces this.
- Publish only to the Gusto-internal ShareSomething page; never anywhere public.

Owner: Aman Bhatia (aman.bhatia@gusto.com).
