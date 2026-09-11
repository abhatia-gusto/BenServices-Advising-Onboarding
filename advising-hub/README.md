# Benefits Advising Hub — advisor & PE guide

One place to see your whole renewal book, refreshed every morning. This guide walks through every part: the tabs, each column group, the drill-down, and how things change across Open, Pending Fulfillment, and Closed.

---

## The tabs
- **Overview** — your book at a glance (opens here). Switch IC / PE / Team-wide at the top.
- **Open** — renewals you're actively working.
- **Pending Fulfillment (PF)** — customer has picked a plan; the order is being finalized.
- **Closed** — renewals that landed (won or lost); a frozen snapshot.
- **Customer Positioning** — a ready-made call script for any customer.

At the top of each tab: tiles (opps, MRR, at-risk), filters (advisor, PE, priority, risk, cohort), and search. Click any row for full detail.

---

## Overview — triage screen
- **Stage tiles** — Open / PF / Closed counts, dollars, at-risk. Click to focus.
- **Book insights** — Outreach, Contact ≤21d (share reached per channel), Recommendation & SLA (% outside SLA, na-excluded, count on its own line), Premium (≥15%/≥20% as **% of the whole live book**), Flags.
- **Risk boxes** — High / Medium / Low with top drivers, click-through.
- **PE / IC roll-up** — per advisor / PE team, with a compact OUTSIDE SLA % cell (RFD·ERC·ALT·Ticket·Email).

---

## Columns (by group)

### Outreach priority — "who to call first"
- **P1 Default Automation** (recs auto-sent, no advisor contact — a customer-outreach priority) · P2 level-funded available · P3 above-market rate · P4 missing coverage/data · P5 selection deadline. Live on Open; greyed on PF/Closed.

### Risk — "who's likely to slip"
- **Open:** weighted advising-cycle signals **plus a "gone quiet" floor** — no outbound email 21d+, no customer reply 21d+, no live call connect 21d+ (a channel never logged counts as quiet). All 3 quiet → at least High; 1–2 → at least Medium; 0 → no floor. **PF:** fulfillment signals. **Closed:** greyed.

### Customer Contact — "are we in touch"
- **Intro / Intro Connect**, **Last email out / in**, **Last call** (with attempt / voicemail / connect), **Received** (unanswered customer email), **Email due**.
- **A "connect" means we actually reached someone — not a voicemail.** Salesforce stamps `STATUS='Connect'` on plenty of voicemails, so a call counts as a connect only when its disposition is a real one ("Call completed"/"Transferred") or, when the disposition is blank, the call ran longer than 45 seconds. "Left voicemail" (or blank + ≤45s) does **not** count. Feeds Intro Connect, "Connected ≤21d", and the no-recent-call-connect risk signal.
- **Email attribution matches the Email SLA dashboard:** an inbound counts as advising's only while advising owns the work (opp owner; BO status With Advising / With Sales). Once the order moves on it belongs to the benefit-order owner's team.

### Flags
- **LF** savings band (+ recommended-in-alt in drill), **Recert**, **SEP**, **BoR/Term**, **Auto-renewal** (customer confirmed default + skipped, Snowplow), **Default automation** (system auto-finalized).

### Premium / General / Sentiment / Recommendation / Benefit order / Closed-only
- Premium Δ (Projected on Open/PF, Final on Closed; gold ≥15 / orange ≥20 / red ≥30); renewal/cohort, stage, deadlines, lead days, funding, enrolled; CSAT/in-app; default sent + time in RFD/ERC + alternates; tickets→advising + BO status; Won/Lost + MRR before/after on Closed.

---

## How the three stages differ
- **Open** — Priority + Risk live (Risk includes the gone-quiet floor), Premium Projected, MRR current.
- **Pending Fulfillment** — Priority archived; Risk live on fulfillment signals.
- **Closed** — frozen: Priority + Risk greyed, Premium Final, MRR before → after.

---

## Good to know
- **Updates every morning** — numbers reflect the prior day.
- **IC / PE / Team** — advisors see their own book; PEs roll up; leadership sees all.
- Everything on the Overview is clickable through to the filtered list.

Questions or something looks off? Flag it to the BenOps team.
