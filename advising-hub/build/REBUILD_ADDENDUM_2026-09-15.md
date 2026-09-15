# REBUILD addendum — changes since base REBUILD.md (2026-09-14 / 09-15)

This addendum layers on top of `REBUILD.md`. Where the two disagree, **this file wins** for behavior dated
2026-09-14 and later. All changes are live on slug `benefits-advising-hub` and verified (node app-script check,
PII=0, opp-count sanity, closed-snapshot integrity, LF reconciliation vs the certified dashboard).

> Source of truth for execution: the daily Phase A (4:00a) + Phase B (8:30a) tasks run the scripts from the
> **BenOps working folder** (`cd "$BEN" && python3 refresh_advising_hub.py`) — NOT from this repo. This repo is
> the reproduce-anywhere reference (the dash skill fetches `queries/*.sql`) + rebuild spec.

## 1. Rolling cohort window (was: fixed 6 dates)
`refresh_advising_hub.py`: `COHORT_DATES` is no longer a hardcoded 6-date literal. It's computed each run by
`_cohort_window(anchor=COHORT_ANCHOR='2026-07-01', months_ahead=5)` = a **fixed trailing anchor + rolling end
(current month + 5)**, e.g. on 2026-09-xx it yields `2026-07-01 … 2027-02-01`. Keeps recent closed history and
always covers the next 5 months; nothing is dropped. All 28 `queries/*.sql` already template `{{cohort_dates}}`,
so the whole Snowflake pull rolls with it. The computed window is written to `advising_hub_refresh_status.json`
as `cohort_window` (surfaced in the Phase B digest DM). Opps newly in-window but absent from the prior dataset
are created from `cohort.csv` in merge_freeze (schema-safe rows: list fields → [], dict → {}, scalars → None).

## 2. Stage/tab de-freeze (the core bug fix) — classification computed for EVERY opp daily
`refresh_advising_hub.py` `merge_freeze`: `stage`, `tab`, `closed`, and the cohort identity scalars
(`pe`, `advisor`, `blocked_reason`/`bor_term`, `sep`, `renewal_date`, `days_to_renewal`, `days_in_stage`,
`cohort`) are re-sourced LIVE from today's Snowflake `cohort.csv` for **every** opp (Open/PF/Closed), replacing
the old behavior of reading `stage` from the frozen Sept-1 base. `outcome` is recomputed from the live stage.
Stage→tab uses the builder-consistent set `{Closed Won, Closed Lost, Order Lost, Closed Admin}`; PF = stage
`Pending Fulfillment`; else Open. This fixed ~1,787 mis-tabbed opps (928 Open→PF, 728 PF→Closed, 127 Open→Closed).

## 3. Steady-state freeze policy: Open/PF-live, Closed frozen
The per-cycle **value** fields — LF savings/quote, email-SLA met/missed counts, premium Δ, MRR, enrollment,
survey/CSAT — refresh **Open/PF only**; **Closed carries them forward frozen** (close-time snapshot). Only the
classification + identity scalars in §2 keep computing for all opps (cheap, terminal-stable for Closed, and
required so tabs stay correct and PF→Closed transitions land). `FROZEN_CLOSED` = mrr, mrr_before, mrr_after,
enrollees, funding_after, closed_on, outcome*, inferred_close_date, lines (*outcome is re-derived from live stage
after the frozen restore).

## 4. Level-Funded savings aligned 1:1 with the certified LF dashboard
`queries/lf.sql`: the savings engine changed from **enrolled-only, per-opp** `avg(iff(is_enrolled=1,sav,null))`
(+`HAVING avg_sav IS NOT NULL`) to the certified `queries/lf_dashboard_data_v1.sql` engine: **census `AVG(sav)`
at `company_id` + `renewal` grain**, mapped onto the opp via its company_id+renewal. So `LF_SAVINGS_PCT` equals
the dashboard's `avg_sav` opp-for-opp (reconciled: 1,836/1,837 certified opps match ≤0.0001 on one snapshot).
Note: the LF rate table (`GROUP_LEVEL_PLAN_RATES`) has **no renewal_id** — both the hub and the certified
dashboard match the rate to the opp on **company_id + effective_date (= renewal date)**, not renewal_id.

## 5. "LF" column semantics (display) + High/Low/No band
`build_advising_hub.py` (display only — internal fields unchanged, so P2/risk/tiers are identical):
- **LF** column reads **Yes** only when `lf_savings_pct` is not null (= the LF savings dashboard population).
  Opps with a quote but no computable savings (no default recommendation — e.g. Barney, Traxyl) read `—`,
  matching who's in the dashboard.
- **LF savings** column = dashboard 3-way band from the matched pct: **High** (>10%) / **Low** (>0%) / **No** (0%),
  with the %. (The internal `lf_savings_band` remains 4-way High/Medium/Low/No and still drives P2 + the LF risk
  signal — unchanged.)
- Drill mirrors both; the table LF filter keys on savings-available.

## 6. "Emails met SLA" count (new)
`queries/email_sla.sql`: added `n_met` (Responded Within SLA) and `n_missed` (Responded Past SLA + Pending
Missed-aging), same advising-attribution ladder + 240-HOOP-min (4 business-hour) target as the Met/Missed/na
rollup. `refresh_advising_hub.py` carries `email_sla_met`/`email_sla_missed` (Open/PF live; Closed frozen).
`build_advising_hub.py`: new **Emails met SLA** column (`m/e met`, colored by status) + a Customer-Contact drill
line (`m met · x missed of e advising-attributed · target 4 business-hrs`).

## 7. "Days in PF" column (new)
`build_advising_hub.py`: new PF-tab column **Days in PF** = days in the Pending Fulfillment stage (from
`days_in_stage`), aging color green ≤7d / gold 8–21d / red >21d, + a General drill line. Builder-only.

## 8. 15% = single premium/rate threshold
PF auto-renewal risk severity floor changed `inc>=14` → `inc>=15` in both `build_advising_hub.py` (riskPF) and the
`refresh_advising_hub.py` RISK_JS copy, plus the risk legend `≥14%`→`≥15%`. Now consistent with the open rate-risk
floor, P3 (≥15%), and the premium-Δ gold band — all ≥15%.

## Byte-sync the source files into this repo (do from a clone)
The canonical scripts live in the BenOps folder; mirror them here with a real git commit (paste-based API can't
guarantee byte-fidelity for files this size):
```
git clone https://github.com/abhatia-gusto/BenServices-Advising-Onboarding && cd BenServices-Advising-Onboarding
cp "$BENOPS/refresh_advising_hub.py"      advising-hub/build/refresh_advising_hub.py
cp "$BENOPS/build_advising_hub.py"        advising-hub/build/build_advising_hub.py
cp "$BENOPS/hub_queries/email_sla.sql"    advising-hub/queries/email_sla.sql
git add -A && git commit -m "advising-hub: sync build/refresh + email_sla to live (2026-09-15)" && git push
```
(`queries/lf.sql` is already synced and verified byte-identical.)
