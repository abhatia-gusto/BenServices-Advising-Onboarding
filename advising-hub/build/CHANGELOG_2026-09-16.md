# Advising Hub — 2026-09-16: Closed opps refresh Snowflake fields daily

## What changed
Closed opportunities no longer freeze their entire close-time snapshot. Every
**Snowflake-warehouse** field now refreshes **daily** for Closed opps (same as Open/PF):
mrr / mrr_before / mrr_after, `lines[].enr_before/enr_after`, enrollees, bo_status,
ticket_sla / email_sla, time_in_erc / days_to_default, rate_index, lf_*, rec_timing,
auto_renewal, sf_open_signals, open_tickets / open_cases.

This fixes closed cards that showed a **blank "after" enrollment** and **missing
recommendation/cycle dates** because the benefit order finalized *after* the opp closed
(e.g. College of Hair Design Careers Inc — enr_after was blank, now shows the fulfilled count).

## What stays frozen
Only **Salesforce-sourced** fields freeze for Closed (carry forward the close-time value),
defined in `SF_FROZEN_FIELDS` in `refresh_advising_hub.py`:
- SF-MCP: intro_call, recert_status, sep_risk_level, packets
- SF activity: last_update / last_contact / last_call / connect, case_summary

`outcome` tracks the LIVE stage. Each Closed row is stamped `data_asof` (today) and
`close_snapshot_date`.

## UI (build_advising_hub.py)
Same grid + drill-down. In the Closed drill:
- point-in-time renewal-cycle values (enrolled-before census, LF quote/savings, rate
  increase, rec-cycle dates, alt dates) render **grayed** with an `as of close` pill;
- frozen Salesforce fields get an `SF` pill;
- a one-line banner explains: "Snowflake fields refreshed <date>; cycle values & SF fields as of close".

## Reopen handling
The freeze/refresh decision is keyed on the **live tab each run** (no persisted "closed"
latch). A Closed opp that reopens (→ Open/PF) automatically re-enters full refresh; its
SF-MCP fields repopulate on the next Phase A pull (one-day lag on those four fields only).

## Verification (2026-09-16, --skip-pull --no-publish)
- node verify OK, PII=0, opps=15310.
- 8,841 closed opps: **0** SF-field drift; 8,791 had a Snowflake field refresh vs the frozen
  prior; 474 had enr_after go blank→value.

## Files
- `advising-hub/build/refresh_advising_hub.py` — SF_FROZEN_FIELDS; value-refresh runs for all
  tabs; SF-MCP gated to Open/PF; data_asof / close_snapshot_date stamps.
- `advising-hub/build/build_advising_hub.py` — decClosed() + as-of-close/SF pills + banner.
- `advising-hub/catalog.json` — closed_opp_refresh_policy note.

Note: this PR also syncs local source-of-truth changes that were ahead of the backup
(rolling cohort window batch), so the repo matches what runs locally.
