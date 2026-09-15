# Advising Hub — Changelog 2026-09-14 (daily-refresh remediation, LF-parity)

Live on slug `benefits-advising-hub`; verified each publish (node app-script check, PII scan = 0, opp-count sanity, closed-snapshot integrity).

## 1. De-freeze stage/tab + Snowflake scalars for EVERY opp (fixes opps stuck on a stale tab)
`build/refresh_advising_hub.py` `merge_freeze` now re-sources `stage`, `tab`, `closed`, `pe`, `advisor`,
`blocked_reason`/`bor_term`, `sep`, `renewal_date`, `days_to_renewal`, `days_in_stage`, `cohort` **LIVE from
today's Snowflake `cohort.csv` for every opp (Open / PF / Closed)** instead of the frozen base snapshot.
`outcome` tracks the live stage. Closed still keeps its close-time SNAPSHOT (MRR before/after, `lines`, `closed_on`).
Stage→tab uses the builder-consistent set `{Closed Won, Closed Lost, Order Lost, Closed Admin}`.

Cutover golden-diff (frozen-base vs de-frozen): stage-vs-live-Snowflake mismatches **2,963 → 0**; tab moves
**928 Open→PF, 728 PF→Closed, 127 Open→Closed** (+4 minor reverse); **0 drift** on already-closed MRR snapshots.

## 2. Rolling cohort window — current month + next 5, trailing history kept (LF-parity)
`build/refresh_advising_hub.py`: hardcoded 6-date `COHORT_DATES` replaced with `_cohort_window()` =
fixed trailing anchor `COHORT_ANCHOR = '2026-07-01'` + rolling end (current month + 5), recomputed every run.
All 28 `queries/*.sql` are already templated on `{{cohort_dates}}`, so the whole Snowflake pull rolls with it.
Opps newly in-window but absent from the prior dataset are created from `cohort.csv` (schema-safe rows).
The computed window is written to `advising_hub_refresh_status.json` as `cohort_window` for the daily DM.
Nothing is dropped; cutover added **+69** opps (incl. Jan/Feb 2027 and opps created since the base build).

## 3. 15% = the single programmed premium/rate threshold
`build/build_advising_hub.py` + `build/refresh_advising_hub.py`: PF auto-renewal severity floor `inc>=14` → `inc>=15`
(now matches Open rate-risk, P3 "above-market rate", and the premium-Δ gold band — all ≥15). Risk legend
updated `≥14%` → `≥15%`. `build/Advising_Hub_README.md` documents 15% as the single threshold.

## Files changed
- `build/refresh_advising_hub.py` — `_cohort_window()`, `merge_freeze` live stage/scalars de-freeze, new-opp creation, `status.cohort_window`, PF autoren 14→15 (verify copy)
- `build/build_advising_hub.py` — PF autoren `inc>=14`→`inc>=15` + risk legend `≥14%`→`≥15%`
- `build/Advising_Hub_README.md` — 15% documentation

> The two `build/*.py` files are updated and live in the BenOps working folder (verified + published). They
> should be synced into this repo via a byte-fidelity git commit from that folder rather than an inline paste,
> to avoid any risk of altering the large canonical pipeline files.
