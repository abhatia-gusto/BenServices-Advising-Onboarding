# Benefits Advising Hub — Risk Profile (definition)

The hub's per-opp **Risk** score: a hub-native port of EYO 2's weighted additive model, computed entirely in the builder (client-side, JavaScript) from fields already present in `advising_vnext_data.json`. It complements the Outreach priority (P): **P = the single most-actionable lever; Risk = composite likelihood of the renewal going badly.**

---

## How it works, in one line

Each signal contributes `weight × severity(0–1)`; sum, normalize to **0–100** as `round(100 × Σ(w·sev) / WTOTAL)`, then tier **High ≥ 35 / Medium ≥ 18 / Low** (same thresholds as EYO 2, so the two tools agree). Where a field is null the signal contributes 0, so the score degrades gracefully. It recomputes on every refresh for Open/PF (a live health read) and is archived/frozen on Closed.

## Which model runs, by stage

- **Open → `riskOpen`** — the EYO 2 pre-selection advising-cycle model. `WTOTAL = 150`. Tickets are intentionally excluded here (they belong to fulfillment).
- **Pending Fulfillment → `riskPF`** — the 5-factor fulfillment model. `WTOTAL = 130`.
- **Closed → `riskPF`, marked archived** — the last PF-style score on the frozen values, shown greyed.

In code: `riskOf(r)` selects the model by `tabOf(r)`, returns `{score, tier, reasons, firing, archived}`; `riskCached(r)` memoizes it per row. The `risk` grid column and the drill's "why at risk" sentence both read this.

## Open model — signals, weights, severity (WTOTAL = 150)

| Signal (key) | Wt | Field(s) | Severity rule |
|---|---|---|---|
| Unworked near renewal (`unworked`) | 15 | `stage`, `days_to_renewal` | early stage × (dtr≤30→1, ≤45→.8, ≤60→.5, else .2); mid stage ×0.5; else 0 |
| Term / BoR away (`termbor`) | 15 | `blocked_reason` | "Pending Termination / BoR Away"→1; "BoR Incomplete"→.7 |
| We've gone quiet (`silence`) | 12 | `last_outbound_email_date` | null→.75; >14d→1; >7→.5; >4→.25 |
| Rate increase (`rate`) | 12 | `rate_increase_pct` | ≥30→1; ≥20→.6; ≥15→.3 |
| Customer gone quiet (`noresp`) | 10 | `last_inbound_email_date` | >21→1; >14→.6; >7→.3; null→.8 if we've emailed else .4 |
| Late-generated opp (`lategen`) | 10 | `lead_days` | <60→1; <75→.5; else 0 (negative counts as <60) |
| Stagnant in stage (`stagnant`) | 10 | `days_in_stage` | >21→1; >14→.66; >7→.33 |
| Intro not complete (`nointro`) | 10 | `intro_call` | not done→1 |
| Selection deadline (`deadline`) | 10 | `selection_deadline` | passed→1; ≤7d→.6; ≤14d→.3 |
| Submission deadline (`subdl`) | 10 | `submission_deadline` | passed→1; ≤7d→.6; ≤14d→.3 |
| Renewal packet missing (`packet`) | 8 | `blocked_reason`, `packets_files`, `packet_carriers` | "Packet Needed"→1; else (0/null packets & carriers listed)→.4 |
| Alternates requested >3d (`altsla`) | 8 | `alt_requested_date`, `alt_published_date`, `days_to_alt` | gap >3d→1; =3→.5 |
| Recertification (`recert`) | 8 | `recert_lateness_days`, `recert_ticket`/`recert_status`, `blocked_reason` | late >60→1 / >30→.7 / >14→.4 / else .25; flagged only→.5 |
| Level-funded quote pending (`lfpend`) | 6 | `lf_savings_band`, `lf_in_alt` | positive band & not in an alt: High→1 / Medium→.7 / Low→.4 |
| SEP / GR (`sepgr`) | 6 | `sep` | SEP→1 |

`score = round(100 × Σ(w·sev) / 150)`.

## PF model — 5 factors (WTOTAL = 130)

| Factor (key) | Wt | Field(s) | Severity rule |
|---|---|---|---|
| Negative in-app sentiment (`sentiment`) | 30 | `inapp_current`, `in_app_comment`, `in_app_date` vs `cycle_open` | only if in-app is this-cycle: rating ≤2→1; ≤3→.7; else comment-only→.7 |
| OA→Advising tickets (`ticket`) | 30 | `tickets_to_advising` | ≥3→1; 2→.7; 1→.4 |
| Recert still open (`recert`) | 20 | `recert_status` | set and ≠ "Recert Approved"→1 |
| Within 1 wk fulfillment (`within1wk`) | 30 | `submission_deadline` | 0–7d out→1; 8–14d→.5 |
| Auto-renewing into increase (`autoren`) | 20 | `auto_renewal`, `rate_increase_pct` | auto_renewal=Y: inc≥20→1; ≥14→.6; else .3 |

`score = round(100 × Σ(w·sev) / 130)`.

## Tiers

`score ≥ 35 → High` · `≥ 18 → Med` · else `Low`. Same thresholds for Open and PF (and the frozen Closed value).

## UI integration

- **Risk column** in the Outreach-priority group — score chip color-tiered High/Med/Low, sortable; on Closed it renders greyed/archived.
- **"Why at risk"** sentence at the top of the drill: Open groups firing signals into four clusters (Customer connection / Minimal SF update / Recommendation / Flags); PF and Closed render a flat "Driven by …" sentence (Closed prefixed "Archived — ").
- **Risk filter** (High / Medium / Low multi-select) alongside the other grid filters.
- **Overview** risk boxes count High/Med/Low and rank the firing factors per stage, each click-through to the matching filtered list.

## Freeze interaction (daily refresh)

Risk recomputes on Open/PF each run from fields already refreshed; it is frozen/archived on Closed. No extra data dependency, so it adds ~0 cost to the daily job.

---

*Companion to `data_dictionary.md`, `default_automation.md`, and `auto_renewal.md`. The scoring functions are reproduced verbatim in `build/REBUILD.md` §6 and mirrored by the refresh verifier's node scorer.*
