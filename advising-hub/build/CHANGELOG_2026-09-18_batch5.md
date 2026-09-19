# Advising Hub — CHANGELOG 2026-09-18 (batch 5): continuous-build fix

## Problem
Opps in future renewal months (the entire 1/1/2027 cohort, 8,806 opps, and beyond) appeared on the
dashboard as identity rows but with **blank MRR, carrier, lines, enrollment, hippo/opp links, and
contribution**. Root cause: the daily refresh was a *snapshot + overlay* on a **frozen base**
(`_renewal_full/advising_hub_full_data.json`, built once 2026-09-01, Jul–Dec window). The base never
advanced with the rolling `COHORT_WINDOW`, so opps past Dec 2026 fell through `merge_freeze`'s
"new-in-window" branch and were blank-seeded every run (never enriched).

## Changes

### build_advising_hub.py
- Removed the **"Default built" node** from the renewal-cycle timeline (it lit on the internal
  draft-built date, which is misleading before the rec is sent/priced). Timeline is now
  Cycle Open → Rec Sent → Alt Requested → Alt Published → Selection → Renewal.

### refresh_advising_hub.py
- **New `base_rebuild` pipeline step** (after `pull`, before `assemble`): re-pulls the self-rolling
  base-only queries (`contrib`, `bo`) and re-runs `assemble_full.py` so the base always covers the
  full rolling window. Resilient — a failed base-only pull keeps the prior CSV; a failed rebuild
  restores the prior base and the run continues.
- **`merge_freeze` inversion**: never-enriched opps (brand-new, or previously blank-seeded — detected
  by a missing `data_asof`) are now built from the freshly-assembled base row `a` instead of an empty
  prior row. Line skeletons for Open/PF (and hollow opps) are sourced from `a` so MRR/carrier/lines
  build for opps newly entering the window.
- **OVERLAY** now always refreshes identity/base-static fields from `a`:
  `sf_opp_url`, `hippo_url`, `company`, `contribution`, `bo_url`, `bo_status`.
- **Publish token moved out of source** into the gitignored `snowflake_pat.env`
  (`SHARESOME_PUBLISH_TOKEN`), read via `_publish_token()`. No secret is committed.

### _renewal_full/sql/contrib.sql, bo.sql (base-only queries)
- Replaced the hardcoded `renewal_date in ('2026-07-01' … '2026-12-01')` tuple with a **self-rolling**
  window: `renewal_date >= '2026-07-01' and renewal_date <= dateadd(month,5,date_trunc('month',current_date))`.

## Result (published to benefits-advising-hub, 2026-09-18)
- 1/1/2027 cohort: MRR $0 → **$1.61M**; carrier/lines 100%; hippo + opportunity links 0% → **100%**;
  contribution 0% → **97%**. Total dashboard MRR-before $2.83M → **$4.45M**.
- No regression: Jul–Sep byte-identical; Oct–Dec +0.3% (legit Open/PF freshening); Closed value-fields
  stable; `new=0` in merge_freeze.
- `bo_url`/`bo_status` remain naturally sparse for 1/1 (benefit orders don't exist this early in-cycle).

## Still TODO
- **Phase 1d**: Closed value-fields (MRR/lines) are re-sourced live each run, not yet frozen from a
  durable store — a handful of closed opps drift day-to-day. Wire the durable close-snapshot store.
- **Coverage-parity tripwire**: alert if any in-window month's MRR/carrier coverage falls far below its
  neighbors (would have caught the original 1/1 drift).
- **Rotate** the ShareSomething publish token (it was previously committed in git history).
