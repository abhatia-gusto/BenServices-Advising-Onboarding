# Advising Hub — Changelog 2026-09-15 (batch 3: LF column semantics + Open/PF-only steady state)

Live on `benefits-advising-hub`; verified (PII=0, opp sanity, closed-snapshot integrity, risk/tiers unchanged: at_risk_high 2031 before & after).

## 1. "LF" column now = LF savings dashboard population
`build_advising_hub.py` (display-only): the **LF** column reads **Yes** only when a savings is computable
(`lf_savings_pct` is not null = the certified LF savings dashboard's population). The adjacent **LF savings**
column shows the dashboard's 3-way band from the matched pct: **High** (>10%) / **Low** (>0%) / **No** (0%),
with the % vs current. Barney / Traxyl (LF quote exists but no default recommendation → no savings) now read
**—**, exactly matching who's in the LF dashboard. Drill mirrors both. The table's LF **filter** now keys on
savings-available too.

**Unchanged on purpose:** the internal fields (`lf_quote`, `lf_savings_band` 4-band, `lf_in_alt`,
`lf_savings_pct`) are untouched, so **P2 priority, the LF risk signal, risk scores, and all tiers are
identical** (at_risk_high held at 2031). This was a pure display change.

## 2. Steady-state freeze policy: Open/PF-live, Closed frozen
`refresh_advising_hub.py` `merge_freeze`: the per-cycle **value** fields — LF savings/quote and email-SLA
met/missed counts — now refresh **Open/PF only**; **Closed carries them forward frozen** (the recent all-tabs
publishes backfilled Closed, so the freeze preserves correct values). Premium/MRR/enrollment/survey were
already Closed-frozen. **Classification** (stage/tab/closed) + identity scalars (pe, advisor, blocked, sep,
renewal, days, cohort) still compute for **every** opp each run — cheap (from cohort.csv), terminal-stable for
Closed, and required so tabs never go stale and PF→Closed transitions land.

## Files changed
- `build/build_advising_hub.py` — LF column + LF-savings band render/selectors, drill rows, LF filter (byte-safe git sync pending)
- `build/refresh_advising_hub.py` — LF + email counts moved to Open/PF-only branch; Closed carry-forward note (byte-safe git sync pending)
- `build/Advising_Hub_README.md` — LF column description

> The two large `build/*.py` files are updated and live in the BenOps working folder (verified + published);
> sync them into this repo via a byte-fidelity git commit from that folder.
