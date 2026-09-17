# Advising Hub — Changelog 2026-09-16 (batch 4: merge Received into Email due)

Live on `benefits-advising-hub`; verified (node ok, PII=0, opps=15315). Pure display change — risk engine, tiers, and all underlying fields unchanged (at_risk_high reflects same-day time-based signals only).

## 1. "Received" folded into the "Email due" column
`build_advising_hub.py` (display-only): the standalone **Received** column (`emailrecv`) is removed and its
date is now rendered **inside the Email due cell** — the days-waited value stays the colored anchor
(red + ⚠ when SLA missed/aging, amber aging, plain when fresh) and the latest-unanswered-inbound **received
date shows in light gray** (`var(--g5)`) immediately after it. Not-due rows still show `N`; missing date shows
nothing after the days.

- **Sort unchanged:** the merged **Email due** column keeps its existing sort key
  (`isY(email_due) ? email_due_hoop_hrs : -1`), so it still orders by days waited, longest-pending first.
- **No data change:** the underlying fields (`email_due`, `email_due_hoop_days/hrs`, `email_due_status`,
  `email_received_date`, `email_pending*`) are all untouched — only the render/column list changed. The drill
  "Email awaiting reply" row is unaffected.

## 2. Advisor guide updated
`advising-hub/README.md` — Customer Contact group now describes the single **Email due** column (days waited +
muted received date) instead of separate **Received** / **Email due** entries.

## Files changed
- `advising-hub/README.md` — column description (committed).
- `build/build_advising_hub.py` — removed `emailrecv` column def; `emaildue` cell renderer now appends the
  received date in `var(--g5)` (updated + live + published from the BenOps working folder; **byte-safe git
  sync of this 176 KB file pending**, per the batch-2/3 convention).

> The large `build/build_advising_hub.py` is updated, verified, and published from the BenOps working folder.
> Sync it into this repo via a byte-fidelity git commit from that folder — it is not pushed through the API to
> avoid corrupting the canonical builder (template literals + non-ASCII glyphs).
