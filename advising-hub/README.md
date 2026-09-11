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
- **Book insights** — quick reads on Outreach (intros, who's gone quiet, **email SLA**), Recommendation & SLA, Premium increases, and Flags. The **RFD / ERC / ALT / Ticket / Email** lines show **% outside SLA** — the share that missed the target (5-day turnaround for RFD/ERC/ALT and OA→Advising tickets; ≤4 business-hours for email), counting only opps the SLA actually applies to (same basis as the Advising SLA dashboard), with the raw miss/eligible count beside it. Ticket SLA hides when the scope has fewer than 5 advising tickets.
- **Risk boxes** — High / Medium / Low counts and the top reasons driving them. Click through to the exact list of customers.
- **PE / IC roll-up** — in PE view, see each advisor under you; in Team view, each PE team; plus a compact **OUTSIDE SLA %** cell reading **RFD·ERC·ALT·Ticket·Email** so you can see who's slipping on turnaround at a glance (amber ≥40%, red ≥55%; `–` when there's nothing eligible to score). Click a row to drill in.

---

## What you see in the table (by column group)

### Customer
- **Company** (links to the Salesforce opp; small icons open Hippo, Salesforce, and the Benefit Order), **Advisor**, **PE**.

### Outreach priority — "who to call first"
- **Priority (P1–P5)** — the single most urgent reason to reach out: P1 recommendation ready · P2 level-funded available · P3 above-market rate · P4 missing coverage/data · P5 selection deadline.
- **Open:** live, color-coded. **PF & Closed:** shown greyed (archived) — the reason it last carried, not a live call-to-action.

### Risk — "who's likely to slip"
- **Risk** — a score with High / Medium / Low. Click the customer to read *why* in plain words.
- **Open:** live, using advising-cycle signals. **PF:** live, using fulfillment signals. **Closed:** greyed (its last score).

### General
- **Renewal date / Cohort**, **Stage** and **Days in stage**, **Selection deadline** and **Submission deadline** with day-countdowns, **Lead days** (how long from opp created to renewal), **Funding** (Fully insured / Level funded), and **Enrolled (medical)**.
- **MRR** shows on Open/PF (current). On **Closed** you instead see **MRR before** and **MRR after**.

### Premium change (medical is the headline)
- **Premium Δ** — how the medical premium is moving.
  - **Open / PF = "Projected"** — today's rate vs. the plan they'd land on if nothing changes.
  - **Closed = "Final"** — today's rate vs. what they actually enrolled in.
  - Color: gold ≥15%, orange ≥20%, red ≥30%.
- **In the drill:** the change **by line** (medical, dental, vision, life…), with the current premium and the options.

### Lines / Enrollment (in the drill)
- Each benefit line with **carrier** (and carrier change if they switched), **enrolled before → after**, and **packet** status.

### Customer Contact — "are we in touch"
- **Intro (done)** and **Intro Connect** (did we actually reach a live person), **Last email out** and **Last email in** (days since), **Received** (an unanswered customer email) and **Email due**, **Last Update**.
- **In the drill:** the same, with dates and "N days ago." Use this to spot who's gone quiet.
- **Email attribution matches the Email SLA dashboard:** an inbound email only counts as *yours* (advising) while advising owns the work — the opp owner, and the benefit order status is "With Advising" or "With Sales." Once the order moves on (BO status "Ready for Confirmation," fulfillment, etc.), its emails belong to the **benefit-order owner's** team (e.g. New Plan & Renewal), not advising. Carrier-Submission and closed-at-arrival cases are excluded. So "Email due" and "Email outside SLA" reflect only advising-owned emails, opp-for-opp with the dashboard.

### Flags
- **LF** (level-funded savings band: High / Medium / Low / No) — and in the drill, **Recommended in Alt** (did we actually put the LF option in front of them).
- **Recert**, **SEP**, **BoR/Term**, **Auto-renewal**, **Default automation**.
  - **Auto-renewal** — the *customer* confirmed the default and skipped the flow (from Snowplow). This is different from **Default automation**, which means the *system* auto-finalized the default; its drill shows the completion date.

### Sentiment
- **Surveys / In-app / CSAT** — recent feedback, newest first; the drill shows the comment.

### Recommendation & Alt (in the drill, plus a few columns)
- **Default sent** date and **Time to rec sent**, **Time in RFD** and **Time in ERC** (how long each step took vs. the 5-day targets), and **Alternates** — requested / created / published, days-to-alt, and how many packages.

### Benefit order (PF & Closed)
- **Tickets → Advising** (support tickets routed to you), **BO status** (where the order stands). *(Open-ticket and past-SLA counts coming.)*

### Closed-only
- **Outcome** (Won/Lost), **Closed on** date, **MRR before / MRR after**.

---

## The drill-down (click any customer)
Opening a customer shows everything for that opp in one place:
- **Why it's at risk** — a plain sentence with the drivers.
- **General** — funding, deadlines, stage, lead time.
- **Premium** — the change by line (medical/dental/vision…), current → option.
- **Enrollment** — headcount by line, before → after, carriers.
- **Customer Contact** — intro/connect, last email out/in, last update, email awaiting reply.
- **Recommendation & Alt** — default sent, time in each step, alternates.
- **Flags** — LF (+ recommended-in-alt), recert, SEP, auto-renewal (customer confirmed the default and skipped the flow), default automation (system auto-finalized).
- **Sentiment** — CSAT / in-app with the verbatim comment.
- **Benefit order & tickets** — status and open items.
- A **Customer Positioning →** button jumps to that customer's call script.

---

## How the three stages differ
- **Open** — everything live: Priority and Risk both active, Premium shown as **Projected**, MRR is current. Work these.
- **Pending Fulfillment** — Priority is archived (they've decided); **Risk stays live** on fulfillment signals (recert open, tickets, deadline near). Watch for stuck orders.
- **Closed** — frozen snapshot: Priority and Risk both greyed (their last values), Premium shown as **Final** (what they enrolled in), and **MRR before → after**. A few things still settle for a short window after closing (final enrollment, survey scores).

---

## Good to know
- **Updates every morning** — the numbers reflect the prior day.
- **IC / PE / Team** — advisors see their own book; PEs roll up their team or drill into any advisor; leadership sees all teams.
- **Everything's clickable** — tiles, priority tiers, and risk factors on the Overview all jump to the matching filtered list.

Questions or something looks off? Flag it to the BenOps team.
