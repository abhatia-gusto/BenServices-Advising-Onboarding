# Benefits Advising Hub — Risk Profile

How the hub scores renewal risk. Open uses a weighted advising-cycle model plus a "gone quiet" contact floor; Pending Fulfillment uses a fulfillment-signal model; Closed is frozen.

---

## Open risk — weighted score + gone-quiet floor

**Weighted additive score:** each signal contributes `weight × severity(0–1)`; sum, normalize to **0–100** over Σwt = **128**; tier from the score **High ≥35 / Medium ≥18 / Low**.

### Signal spec (weights + severity)

| Signal | Wt | Hub field(s) | Severity rule |
|---|---|---|---|
| Unworked near renewal | 15 | `stage`, `days_to_renewal` | early stage × (dtr≤30→1, ≤45→.8, ≤60→.5, else .2); mid stage ×0.5 |
| Term / BoR away | 15 | `blocked_reason` | "Pending Termination/BoR Away"→1; "BoR Incomplete"→.7 |
| Rate increase | 12 | `rate_increase_pct` | ≥30→1; ≥20→.6; ≥15→.3 |
| Late-generated opp | 10 | `lead_days` | <60→1; <75→.5 |
| Stagnant in stage | 10 | `days_in_stage` | >21→1; >14→.66; >7→.33 |
| Intro not complete | 10 | `intro_call` | not done→1 |
| Selection deadline | 10 | `selection_deadline` | passed→1; ≤7d→.6; ≤14d→.3 |
| Submission deadline | 10 | `submission_deadline` | passed→1; ≤7d→.6; ≤14d→.3 |
| Packet missing | 8 | `packets_files`, `packet_carriers` | "Packet Needed"→1; else shortfall→.4 |
| Alt requested >3d | 8 | `alt_requested_date`, `days_to_alt` | >3d→1; =3→.5 |
| Recertification | 8 | `recert_lateness_days`, `recert_status`, `blocked_reason` | late→up to 1; flagged→.5 |
| LF quote pending | 6 | `lf_savings_band`, `lf_in_alt` | band present, not yet in an alt → .4–1 by band |
| SEP / GR | 6 | `sep` | SEP→1 |
| **No recent email outreach** *(gone-quiet #1)* | **0** | `last_outbound_email_date` | **binary: fires if >21 days or null.** Weight 0 — drives the tier via the floor override below. |
| **No recent customer response** *(gone-quiet #2)* | **0** | `last_inbound_email_date` | **binary: fires if >21 days or null.** Weight 0. |
| **No recent call connects** *(gone-quiet #3)* | **0** | `last_connect_date` | **binary: fires if >21 days or null.** Weight 0. |

The three gone-quiet signals carry weight 0 so they don't inflate the numeric score; they still appear in the drill's "why at risk" list when they fire.

### Gone-quiet floor override (Open only) — the watched contact signal

The three "gone quiet" signals (no outbound email in 21d+, no customer reply in 21d+, no live call connect in 21d+; **a channel never logged counts as quiet**) set a **floor** on the Open tier by how many fire:

- **3 of 3 quiet → at least High**
- **1–2 of 3 quiet → at least Medium**
- **0 of 3 → no floor**

It's a floor (`tier = max(score-tier, gone-quiet-tier)`): a customer with real problems — big rate increase, deadline passed, term/BoR, open tickets — can still be pushed higher by the weighted score, but a customer we've simply lost touch with can't hide at Low. The drill names which channels are quiet and notes when "gone quiet" set the tier.

On the current book this puts Open at roughly **High ~38% / Medium ~57% / Low ~6%**; ~37% of Open is quiet on all three channels.

*Rationale for 21 days + null-fires:* longer thresholds barely move the count because ~65% of Open has never logged a live connect and most never got an inbound reply — those nulls fire at any threshold. 21 days is the point where a real (non-null) gap is unambiguously "quiet," and null-fires is deliberate: an untouched renewal *is* a contact risk. The count-based floor (3→High, 1-2→Med) keeps it interpretable.

---

## Pending Fulfillment risk — 5-factor fulfillment model (Σwt 130)

| Signal | Wt | Severity |
|---|---|---|
| In-app sentiment (this cycle) | 30 | ≤2→1; ≤3→.7; negative comment→.7 |
| Open OA→advising tickets | 30 | ≥3→1; 2→.7; 1→.4 |
| Within 1 week of fulfillment | 30 | ≤7d→1; 8–14d→.5 |
| Recert still open | 20 | not "Recert Approved"→1 |
| Auto-renewing into an increase | 20 | auto-renewal × (rate ≥20→1; ≥14→.6; else .3) |

Tier: High ≥35 / Medium ≥18 / Low. No gone-quiet floor on PF (fulfillment-stage signals govern).

---

## Closed

Risk is frozen at its last computed value (greyed in the UI). Signals are advising-process states that no longer apply once the renewal lands.

---

## UI

- **Risk** column in the Outreach-priority group — color-tiered High/Med/Low, sortable.
- **"Why at risk"** sentence at the top of the drill lists the firing signals, grouped (Customer connection / Minimal SF update / Recommendation / Flags), and calls out when "gone quiet" set the tier.
- Recomputes live on Open/PF each daily run; no new data dependency, so ~0 added cost to the daily job.
