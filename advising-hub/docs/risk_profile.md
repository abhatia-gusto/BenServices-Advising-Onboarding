# Benefits Advising Hub — Risk Profile

How the hub scores renewal risk. Open uses a 3-equal-domain model; Pending Fulfillment (and Closed, frozen) a 4-equal-domain fulfillment model. Every signal is `weight × severity`, where severity is graded 0–1 and **scales above 1 (to ×2)** for durations/magnitudes that keep worsening. Score = round(Σ weight·sev), capped at 100. **Tiers: High ≥30 · Med 21–29 · Low ≤20** for both models.

Helpers: `_durScale(d)= d>90?2 : d>45?1.5 : 1`; `_slaScale(dwell,thr,a,b)= dwell>b?2 : dwell>a?1.5 : dwell>thr?1 : 0`; `_survAvg` = mean of `surveys_12mo` ratings excluding "App: NPS Survey"; `EARLY_SET = {SAL, Ready for Default Package, Open}`.

---

## Open risk — 3 equal domains (33.3 pts each)

### Customer contact — 5 signals × 6.7
| Signal | Field(s) | Severity |
|---|---|---|
| No customer reply | `last_inbound_email_date` (+ `last_outbound_email_date`) | fires **only if we have an outbound** AND (no inbound OR inbound >21d); `_durScale` by days silent. *(Corrected: does not fire when we never emailed.)* |
| No email outbound | `last_outbound_email_date` | >21d or null → `_durScale` |
| No live call connect | `last_connect_date` | >21d or null → `_durScale` |
| Days in stage | `days_in_stage` | >21 → `_durScale`; >14 → .66; >7 → .33 |
| Intro call not completed | `intro_call` | not Y → 1 |

### Plan & cost — 5 signals × 6.7
| Signal | Field(s) | Severity |
|---|---|---|
| Rate increase | `rate_increase_pct` | ≥60→2; ≥45→1.5; ≥30→1; ≥20→.6; ≥15→.3 |
| LF savings not in an alt | `lf_savings_band`, `lf_in_alt` | High1/Med.7/Low.4 if band present and not in an alt |
| Term / BoR-away | `blocked_reason` | Pending Termination/BoR Away→1; BoR Incomplete→.7 |
| Recert lateness | `recert_lateness_days`, `recert_status` | >120→2, >90→1.5, >60→1, >30→.7, >14→.4, >0→.25; else flagged→.5 |
| SEP / GR | `sep` | SEP→1 |

### Timeline & SLA — 8 signals × 4.2
| Signal | Field(s) | Severity |
|---|---|---|
| Submission deadline | `submission_deadline` | passed ≥14d→2; passed ≥7d→1.5; passed→1; ≤7d→.7; ≤21d→.4 |
| RFD SLA breach | `days_to_default` (RFD dwell) | `_slaScale(,5,15,30)`; else `rfd_sla`=="Missed"→1 |
| ERC SLA breach | `time_in_erc` | `_slaScale(,5,15,30)`; else `erc_sla`=="Missed"→1 |
| Alternates SLA breach | `alt_requested_date`/`days_to_alt` | gap >21→2, >10→1.5, >3→1, ==3→.5 |
| Low survey | `surveys_12mo` (NPS excluded) | avg ≤1.5→2; ≤2→1.5; ≤3→1 |
| Early stage near renewal | `stage`, `days_to_renewal` | stage∈EARLY_SET AND dtr≤45 → 1 |
| Short lead time | `lead_days` | <60→1; <75→.5 |
| Renewal packet missing | `blocked_reason`, `packets_files`, `packet_carriers` | Packet Needed→1; else shortfall→.4 |

### Contact floor (Open only)
`goneQuiet` = count of the three contact-recency signals firing (reply / outbound / connect; a channel never logged counts as quiet). `floor = goneQuiet>=3?"High" : goneQuiet>=2?"Med" : "Low"`, applied as `tier = max(score-tier, floor)`. A fully silent customer is guaranteed at least High; substantive weighted risk can still raise the tier, never lower it.

---

## Pending Fulfillment risk — 4 equal domains (25 pts each)

- **Sentiment (25):** in-app rating this cycle ≤1→1, ≤2→.85, ≤3→.6; comment-only→.6.
- **Service load (3 × 8.3):** `ticket` (`tickets_to_advising` ≥5→1.5, ≥3→1, 2→.7, 1→.4); `ticketsla` (`ticket_sla`=="Missed"→1); `recert` (status ≠ "Recert Approved" → lateness >90→2, >60→1.5, else 1).
- **Cost (25):** `autoren` — `isY(auto_renewal)` × rate ≥45→2, ≥30→1.5, ≥20→1, ≥14→.6, else .3.
- **Timeline (25):** `within1wk` — submission passed ≥14d→2, ≥7d→1.5, passed→1; else ≤7d→1, ≤14d→.5.

Same tiers (High ≥30 / Med 21–29 / Low ≤20). No contact floor on PF (fulfillment signals govern). PF is bimodal — most opps are on-track (Low) with a clear problem tail.

---

## Closed
Re-scored once on the new scale at close, then **frozen** (greyed in the UI); advising-process states no longer apply once the renewal lands.

## UI
- **Risk** column (Outreach-priority group) — colored High/Med/Low, sortable.
- **"Why at risk"** sentence at the top of the drill lists firing signals by domain and flags when the contact floor set the tier.
- Recomputes live on Open/PF each daily run (no new data dependency). The mirror in `refresh_advising_hub.py` (`RISK_JS`) counts at-risk-High during verify — keep the two in sync.
