# Advising Hub — Field → Data Source Map

Every field in `advising_vnext_data.json`, its data source, the system it's pulled through, and whether it refreshes live in the daily pipeline. Built from `hub_queries/catalog.json`.

## Legend — refresh status
- 🟢 **Live daily** — re-pulled every morning on Open/PF (Closed frozen). Has a query in `hub_queries/`.
- 🧊 **Closed-frozen (by design)** — snapshot fields locked at close; only CSAT/in-app re-checked.
- ⚪ **Derived** — computed in the builder/assembler from other fields.

## Customer / identity — 🟢 live (`cohort.sql`)
| Field | Source | Via | Status |
|---|---|---|---|
| opp_id15/18, company, advisor, pe, renewal_date, cohort | ADVISING_OPPORTUNITIES | Snowflake | 🟢 |
| stage, days_in_stage, days_to_renewal | ADVISING_OPPORTUNITIES.STATUS + history | Snowflake | 🟢 |
| closed, tab, queue_tier | derived from stage / P1–P5 flags (builder) | Derived | ⚪ |

> **`queue_tier`, `tab`, and `risk` are computed live in `build_advising_hub.py`** and are NOT persisted in the dataset.

## Enrollment / MRR / Premium — 🟢 live Open/PF · 🧊 Closed
| Field | Source | Via | Status |
|---|---|---|---|
| mrr/before/after, enrollees, per-line enr/mrr/carrier | mrr.sql, premium_lines.sql | Snowflake | 🟢 / 🧊 |
| lines[].pr_*/d_*, rate_pct | premium_lines_delta.sql | Snowflake | 🟢 |
| rate_increase_pct, rate_status, rate_structure, rating_region | rate_index.sql, rating_region.sql (EYO2 carrier×state ladder) | Snowflake | 🟢 |

## Default automation / auto-renewal
| Field | Source | Via | Status |
|---|---|---|---|
| default_automation(+date) | RENEWAL_AUTO_FINALIZE_RECORDS | Snowflake | 🟢 |
| auto_renewal | SNOWPLOW GA_TRACK `ConfirmDefaultAndSkipFlow` (`auto_renewal.sql`) — CUSTOMER confirm-default-and-skip, distinct from default_automation | Snowflake | 🟢 |
| automation_eligible, rate_parse_success | auto_finalize.sql | Snowflake | 🟢 |

## Recommendation / SLA / alternates / LF
| Field | Source | Via | Status |
|---|---|---|---|
| rfd_sla/erc_sla/alt_sla, time_in_erc, days_to_default | sla.sql / time_in_erc.sql / time_in_rfd.sql | Snowflake | 🟢 |
| default_rec_sent/built, alt_* | rec_timing.sql, alt.sql | Snowflake | 🟢 |
| lf_savings_pct/band/in_alt/quote | lf.sql | Snowflake | 🟢 |

## Customer Contact
| Field | Source | Via | Status |
|---|---|---|---|
| last_outbound_email_date, last_inbound_email_date | BENEFIT_ORDER_TOUCHPOINTS, **advising-attributed** (`email_recency.sql`) | Snowflake | 🟢 (gone-quiet #1 & #2) |
| last_call_date, last_connect_date, last_call_disp | SF `task` (type ilike '%call%') joined to Benefits Renewal Case (`sf_activity.sql`). **True connect** = `STATUS='Connect'` AND disposition not voicemail/disconnect AND (real disposition OR, when blank, `calldurationinseconds`>45) — voicemails mis-stamped 'Connect' are excluded. last_connect_date = latest true connect; last_call_disp = Connect/VM/Attempt of the latest call | Snowflake | 🟢 (last_connect_date = gone-quiet #3) |
| intro_connect, connect_date | BI.CASES + task activity, true-connect based (`sf_activity.sql`) | Snowflake | 🟢 |
| intro_call, intro_call_date | Case.Intro_Call_Completed__c (+ CreatedDate proxy) | **Salesforce MCP** | 🟢 |
| email_due(+hoop/status/pending), email_received_date | BENEFIT_ORDER_TOUCHPOINTS HOOP, advising-attributed + case-open-now (`email_due.sql`) | Snowflake | 🟢 |
| email_sla | inbound answered ≤240 HOOP-min, advising-attributed (`email_sla.sql`) | Snowflake | 🟢 |

## Flags / Sentiment / Tickets
| Field | Source | Via | Status |
|---|---|---|---|
| sep, bor_term, blocked_reason, selection/submission_deadline, recert_ticket/lateness, lead_days | cohort.sql / sf_open_signals.sql | Snowflake | 🟢 |
| recert_status, packets_files, packet_carriers | Ticket__c / ContentDocumentLink | **Salesforce MCP** | 🟢 |
| csat*, in_app*, survey* | surveys / inapp.sql | Snowflake | 🟢 |
| tickets_to_advising, open_tickets(+past_sla), ticket_sla, bo_status, open_cases_* | tickets.sql / open_tickets.sql / ticket_sla.sql / open_cases_by_type.sql | Snowflake | 🟢 |

## Closed-only / timeline / risk
| Field | Source | Via | Status |
|---|---|---|---|
| outcome, closed_on, inferred_close_date | opp close + MRR-method | Snowflake/derived | 🧊 |
| cycle_open, tl_* | rec_timing.sql + timeline derivations | Snowflake / Derived | 🟢 / ⚪ |
| risk | Open = weighted score (Σwt 128) + **gone-quiet floor** (3 recency signals >21d/null: 3→High, 1-2→Med, 0→none); PF = 5-factor; Closed = frozen | Derived (builder) | ⚪ |

---

## Notes
- **Stage/tab** come from the live `cohort.sql` STATUS. (Known issue under repair: the assembler currently reads stage from a base snapshot rather than the fresh cohort pull — fix pending.)
- **A connect = actually reached someone.** `STATUS='Connect'` alone over-counts (voicemails get stamped Connect); the true-connect rule above (disposition + 45s duration guard) is the source of truth for intro_connect, "Connected ≤21d", and the gone-quiet call signal.
- Salesforce-MCP fields (intro_call, recert_status, packets) are pulled by the daily task orchestrator before the Python step; carry forward if a pull is missing. Closed opps frozen by design.
