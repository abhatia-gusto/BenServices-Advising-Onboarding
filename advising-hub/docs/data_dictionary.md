# Advising Hub — Field Guide

Plain-language reference: what each column means and how to read it. Written for advisors, not analysts. One line each; no SQL. This is the content behind the hub's Read Me pane.

---

## Customer
- **Company** — the group. Click the name to open the Salesforce opp; the little icons open Hippo, Salesforce, and the Benefit Order.
- **Advisor / PE** — who owns it.

## Outreach priority (the "P")
The single most important reason to reach out. Lowest number = most urgent. Blank/archived once the opp leaves Open.
- **P1 Recommendation ready** — the default recommendation has been sent; customer has real numbers in hand.
- **P2 Level-funded** — a level-funded option with real savings is available.
- **P3 Above-market rate** — the medical increase is 14%+.
- **P4 Data gap** — no enrollment / $0 on record; the question is whether they have coverage at all.
- **P5 Selection deadline** — the floor; every open opp qualifies, nearest deadline first.
- Small tags may also appear (SEP, recertification, renewal packet needed, estimate-only rate) — context, they don't change the number.

## General
- **Renewal date / Cohort** — when it renews.
- **Stage / Days in stage** — where it sits and how long it's been there.
- **Selection / Submission deadline · Days to renewal / submission** — key dates and countdowns; red = past or close.
- **Funding** — how they're funded today (Fully insured / Level funded / Self funded).

## Premium change (medical is the headline)
- **Premium Δ** — how the medical premium is moving. The header tells you the basis:
  - **Open / PF = "Projected"** — today's rate vs. the plan they'd land on if nothing changes (the successor). Best estimate before they enroll.
  - **Closed = "Final"** — today's rate vs. what they actually enrolled in.
  - Colors: gold ≥15%, orange ≥20%, red ≥30%.
- **In the drill** you'll see each benefit line (medical, dental, vision, etc.), current premium, and the options. Note: the "default" and "selected" figures are an **average of the offered menu** (customers are usually shown several plans), so treat them as a range, not one plan's price. Dental/vision/life show only when they have a real premium; HSA/FSA/DCA show "—".

## Enrollment & MRR (in the drill / header)
- **Enrolled before → after** — how many employees are on each line, before vs. after the renewal.
- **MRR before → after** — Gusto's fee (not the customer's premium); moves with headcount. Counted the same way as the Advising MRR dashboard, so the two always agree.

## Recommendation
- **Default sent** — date the default recommendation went to the customer.
- **Time to rec sent** — days from when the opp opened to that send.
- **Time in RFD** — how long it sat in "Ready for Default Package" before the rec went out (the turnaround SLO; 5-day target).
- **Time in ERC** — days in the "ER Confirm" stage (5-day target).

## Alternates
- **Alt requested / created / published / days to alt** — whether alternates were asked for, how many were built, when the first one published, and how long that took.

## Flags
- **Default automation** — ● if the default was auto-finalized by the system (roughly half of renewals), — if not. In the drill: the completion date, plus small dots for whether it was *eligible* to automate and whether rate-parsing succeeded. (Definition: `default_automation.md`.)
- **LF** — level-funded savings band: High (>10%) / Medium (5–10%) / Low (0–5%) / No (≤0%). Flagged for priority on any positive savings. In the drill, **Recommended in Alt: Yes/No** = whether the LF plan was actually put in a published alternate package (same definition as the LF dashboard).
- **Recert · SEP · BoR/Term · Auto-renewal · Intro done · Intro connect** — the usual advising flags. (Auto-renewal vs default automation: `auto_renewal.md`.)
- **We've gone quiet / Customer gone quiet** — days since our last email out and since their last reply (in the drill; feeds the health read).
- **Email due / received** — an unanswered customer email and when it came in (open/PF only).
- **Funding change** — shows FI→LF etc. only once closed (before then the plan isn't final).

## Sentiment
- **Surveys / In-app / CSAT** — recent feedback, newest first.

## Benefit order (PF / Closed)
- **Tickets → Advising · Open tickets · Open >5d · BO status** — support tickets routed in (total and currently-open, and how many are past the 5-day SLA), and where the order stands.

## Closed-only
- **Outcome · Closed on · MRR before / MRR after** — how it landed (both MRR values shown as columns and tiles). Closed opps are frozen except a daily status re-check (see the refresh pipeline).

## Risk (next to Outreach priority)
A 0–100 health score with a High / Med / Low tier and a plain-English "why it's at risk" in the drill. Scored differently by stage:
- **Open** — the advising-cycle model: customer connection (intro/quiet), minimal SF update, recommendation (rate, alternates, LF-not-yet-in-alt), and flags (SEP, recert, packet, term/BoR, deadlines).
- **PF** — the fulfillment model: negative in-app sentiment (this cycle), OA→advising tickets, recert still open, within 1 week of fulfillment, auto-renewing into an increase.
- **Closed** — the last score, greyed/archived.
Reasons read grouped (Open) or as a short sentence; the score sorts and filters like any column. Full spec: `risk_profile.md`.

## At-a-glance tiles (top of each tab)
Each tab shows: **Opps** (after filters) · **MRR** (before on Open/PF; before *and* after on Closed) · **At risk (High)**.

## Archived on later stages
- **Outreach priority** shows the live P on Open; on **PF and Closed** it shows the last value greyed (archived).
- **Risk** is live on Open and PF; on **Closed** it's greyed (archived).

---

*Companion to `risk_profile.md`, `default_automation.md`, and `auto_renewal.md`.*

---

## Sept 10 update
- **`salesforce_production_no_pii.case2` schema drift.** `case2` was stripped of `opportunity__c`, `record_type_name__c`, `isclosed`, and `reason`. `sf_activity` and `cases` were re-pointed to **`BI.CASES`** (Benefits Renewal Case), joined to `task`, so case activity and renewal-case counts are unaffected (output columns unchanged).
- **New live daily signals.** Three previously carried-forward areas are now reconstructed from Snowflake and refreshed daily on Open/PF opps (Closed stays frozen): (1) **email recency** — last outbound / last inbound email date; (2) **SF open-signals** — `auto_renewal`, selection/submission deadlines, recert ticket, BoR/term, SEP, `lead_days`; (3) **per-line premium deltas** — successor / default / selected / finalized premium tiers and their % deltas.
- **Still carried-forward.** Sourced next via **Salesforce MCP**: `recert_status` (`Ticket__c.Recert_Status__c`), `intro_call` / `intro_call_date` (`Case.Intro_Call_Completed__c`), `packets_files` / `packet_carriers` (`ContentDocumentLink`). Snowflake-reconstructable next: `rate_increase_pct` / `rate_status`, `days_to_default`, `lf_*`, `email_due*`, `cycle_open`, `default_rec_*`, `automation_eligible`.
