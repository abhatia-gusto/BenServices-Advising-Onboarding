# Benefits Advising Hub — advisor & PE guide

One place to see your whole renewal book, refreshed every morning. This guide walks through every part: the tabs, each column group (what you see in the table), what opens when you click a customer (the drill-down), and how things change across Open, Pending Fulfillment, and Closed.

---

## The tabs

- **Overview** — your book at a glance (opens here). Switch IC / PE / Team-wide at the top.
- **Open** — renewals you're actively working. Most of your day is here.
- **Pending Fulfillment (PF)** — customer has picked a plan; the order is being finalized.
- **Closed** — renewals that landed (won or lost); a frozen snapshot to look back on.
- **Customer Positioning** — a ready-made call script for any customer (search their name).

At the top of each tab: **tiles** (how many opps, total MRR, how many at risk), **filters** (advisor, PE, priority, risk, cohort), and **search** by company. Click any row to open that customer's full detail.

---

## Overview — your triage screen
- **Stage tiles** — Open / PF / Closed counts, dollars, and how many are at risk. Click one to focus the page on that stage.
- **Book insights** — quick reads on Outreach, Contact recency (share reached ≤21d), Recommendation & SLA, Premium increases, and Flags. The **RFD / ERC / ALT / Ticket / Email** lines show **% outside SLA** — the share that missed the target — with the raw miss/eligible count on its own line beneath. The **PREMIUM ≥15% / ≥20%** lines are **% of the whole live book** (all Open+PF), not only customers with a rate change.
- **Contact ≤21d** — for each channel (emailed out, customer reply in, connected by call), the share of live opps reached within the last 21 days, with the median age beneath. These are the positive mirror of the three "gone quiet" risk signals.
- **Risk boxes** — High / Medium / Low counts and the top reasons driving them. Click through to the exact list of customers.
- **PE / IC roll-up** — in PE view, each advisor under you; in Team view, each PE team; plus a compact **OUTSIDE SLA %** cell (RFD·ERC·ALT·Ticket·Email). Click a row to drill in.

---

## What you see in the table (by column group)

### Customer
- **Company** (links to the Salesforce opp; small icons open Hippo, Salesforce, and the Benefit Order), **Advisor**, **PE**.

### Outreach priority — "who to call first"
- **Priority (P1–P5)** — the single most urgent reason to reach out: **P1 Default Automation** (recs auto-sent, no advisor contact — customer-outreach priority) · P2 level-funded available · P3 above-market rate · P4 missing coverage/data · P5 selection deadline.
- **Open:** live, color-coded. **PF & Closed:** greyed (archived).

### Risk — "who's likely to slip"
- **Risk** — High / Medium / Low. Click the customer to read *why* in plain words.
- **Open:** live weighted advising-cycle signals **plus a "gone quiet" floor**. **PF:** fulfillment signals. **Closed:** greyed.
- **"Gone quiet" sets a floor on Open risk.** Three contact signals: **no outbound email in 21+ days**, **no customer reply in 21+ days**, **no live call connect in 21+ days** (a channel we've *never* logged counts as quiet). **All 3** quiet → at least **High**; **1–2** → at least **Medium**; **0** → no floor. It's a floor, so real problems (rate, deadline, term/BoR, tickets) can still push higher, but a customer we've lost touch with won't hide at Low.

### Customer Contact — "are we in touch"
- **Intro / Intro Connect**, **Last email out / in** (days since), **Last call + connect** (with attempt / voicemail / connect), **Received** (unanswered customer email), **Email due**.
- Email attribution matches the Email SLA dashboard: inbound counts as advising's only while advising owns the work (opp owner, BO status With Advising / With Sales); once the order moves on it belongs to the benefit-order owner's team.

### Flags
- **LF** savings band (+ Recommended-in-Alt in the drill), **Recert**, **SEP**, **BoR/Term**, **Auto-renewal** (customer confirmed the default and skipped the flow — Snowplow), **Default automation** (system auto-finalized the default).

### Premium / General / Sentiment / Recommendation / Benefit order / Closed-only
- Premium Δ (Projected on Open/PF, Final on Closed); renewal/cohort, stage, deadlines, lead days, funding, enrolled; CSAT/in-app; default sent + time in RFD/ERC + alternates; tickets→advising + BO status; Won/Lost + MRR before/after on Closed.

---

## How the three stages differ
- **Open** — everything live: Priority and Risk active (Risk includes the gone-quiet floor), Premium **Projected**, MRR current.
- **Pending Fulfillment** — Priority archived; **Risk live** on fulfillment signals.
- **Closed** — frozen: Priority and Risk greyed, Premium **Final**, MRR before → after.

---

## Good to know
- **Updates every morning** — the numbers reflect the prior day.
- **IC / PE / Team** — advisors see their own book; PEs roll up their team or drill into any advisor; leadership sees all teams.
- **Everything's clickable** — tiles, priority tiers, and risk factors jump to the matching filtered list.

Questions or something looks off? Flag it to the BenOps team.
