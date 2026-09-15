# Advising Hub — Changelog 2026-09-14 (batch 2: LF alignment + email-SLA counts + Days in PF)

Live on slug `benefits-advising-hub`; verified (node app-script check, PII=0, opp-count sanity, closed-snapshot integrity, LF reconciliation).

## 1. LF savings aligned 1:1 with the certified LF dashboard
`queries/lf.sql`: the savings engine was **enrolled-only, per-opp** (`avg(iff(is_enrolled=1,sav,null))` +
`HAVING avg_sav IS NOT NULL`). Replaced with the certified dashboard engine from
`queries/lf_dashboard_data_v1.sql`: **census `AVG(sav)` at `company_id` + `renewal` grain**, mapped onto the
opp via its company_id+renewal. `LF_SAVINGS_PCT` now equals the dashboard's `avg_sav` opp-for-opp.
**Reconciliation on one snapshot: 1,836 / 1,837 certified opps match hub `lf_savings_pct` exactly (≤0.0001).**
Applied across **all 3 tabs** (Open/PF/Closed) — `refresh_advising_hub.py` `merge_freeze` now sets LF fields for
every opp, not just Open/PF (`lf_savings` is not in FROZEN_CLOSED, so it stands for Closed too).
`build_advising_hub.py`: LF savings column shows `n/a` (not blank) when a quote exists but savings can't be
quantified.

## 2. "Emails met SLA" count at the opp/customer level
`queries/email_sla.sql`: added `n_met` / `n_missed` (advising-attributed inbounds meeting / breaching the
240-HOOP-min = 4-business-hour SLA) alongside the existing Met/Missed/na roll-up. `refresh_advising_hub.py`
carries `email_sla_met`/`email_sla_missed` (Open/PF live; Closed carries forward). `build_advising_hub.py`:
new "Emails met SLA" column (`m/e met`, colored by status) + a Customer-Contact drill line
(`m met · x missed of e advising-attributed`).

## 3. "Days in PF" column
`build_advising_hub.py`: new PF-tab column `Days in PF` (= days in the Pending Fulfillment stage, from
`days_in_stage`) + a General drill line. Builder-only; no query change.

## Files changed
- `queries/lf.sql` — census / company+renewal savings engine (pushed here)
- `queries/email_sla.sql` — + `n_met`, `n_missed` (byte-safe git sync pending)
- `build/refresh_advising_hub.py` — LF all-tabs, email counts read, (byte-safe git sync pending)
- `build/build_advising_hub.py` — emailmet + dinpf columns/drill, LF n/a fallback (byte-safe git sync pending)

> The two large `build/*.py` files and the 40KB `email_sla.sql` are updated and live in the BenOps working
> folder (verified + published); sync them into this repo via a byte-fidelity git commit from that folder.
