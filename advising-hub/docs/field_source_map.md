# Advising Hub — Field → Data Source Map

Every field in `advising_vnext_data.json`, its data source, the system it's pulled through, and whether it refreshes live in the daily pipeline. Built from `hub_queries/catalog.json` (authoritative for live pulls). **As of the Sept 10 full-coverage reconstruction, every field refreshes live daily** (Open/PF), via Snowflake or the Salesforce MCP; Closed opps stay frozen by design. ⚪ items are computed in the builder/assembler from live fields.

## Legend — refresh status
- 🟢 **Live daily** — re-pulled fresh every morning on Open/PF (Closed frozen). Has a query in `hub_queries/`.
- 🧊 **Closed-frozen (by design)** — snapshot fields locked at close; only CSAT/in-app re-checked.
- ⚪ **Derived** — computed in the builder/assembler from other fields; no source pull of its own.

## Legend — "Via"
- **Snowflake** — `DATA_WAREHOUSE_RC1` via the `snow`/connector (headless in the python pipeline).
- **Salesforce MCP** — live SOQL against Salesforce objects, run from the scheduled-task prompt.
- **Derived** — computed in `build_advising_hub.py` / `assemble_vnext.py`.

---

## Customer / identity — 🟢 live (`cohort.sql`, Snowflake)
| Field | Source | Via | Status |
|---|---|---|---|
| opp_id15, opp_id18 | ADVISING_OPPORTUNITIES.SFDC_OBJECT_ID | Snowflake | 🟢 |
| company | ADVISING_OPPORTUNITIES | Snowflake | 🟢 |
| advisor, pe | ADVISING_OPPORTUNITIES (owner / PE map) | Snowflake | 🟢 |
| renewal_date, cohort | ADVISING_OPPORTUNITIES.RENEWAL_DATE | Snowflake | 🟢 |
| stage, days_in_stage, days_to_renewal | ADVISING_OPPORTUNITIES + sfdc_opportunity_history | Snowflake | 🟢 |
| closed, tab | (stage) | Derived | ⚪ |
| queue_tier | Outreach-priority logic | Derived (builder) | ⚪ |
| sf_opp_url, hippo_url, bo_url | opp/company/BO ids | Derived | ⚪ |

> **`queue_tier` and `tab` are computed live in the builder** from live fields and are **NOT persisted** in the dataset.

## Enrollment & MRR — 🟢 live Open/PF · 🧊 Closed (`mrr.sql`, `premium_lines.sql`)
| Field | Source | Via | Status |
|---|---|---|---|
| mrr, mrr_before, mrr_after | bi invoices / MRR price book | Snowflake | 🟢 / 🧊 |
| enrollees, carriers_enrolled, num_lines | HEALTH_SUBSCRIPTION_DETAILS + package offerings | Snowflake | 🟢 |
| lines[].enr/mrr/carrier/state | subscription details / MRR price book / plan dim | Snowflake | 🟢 / 🧊 |
| funding, funding_after | med_funding / premium_lines | Snowflake | 🟢 |

## Premium change — 🟢 live (`premium_lines_delta.sql`, `rate_index.sql`)
| Field | Source | Via | Status |
|---|---|---|---|
| lines[].pr_* / d_* / rate_pct | FCT_HEALTH_INSURANCE_RENEWAL_LIFECYCLE + RECOMMENDATION | Snowflake / derived | 🟢 |
| rating_region | GROUP_LEVEL_PLAN_RATES / plan dim | Snowflake | 🟢 |
| rate_structure | plan rate structure (Age-banded/Composite) | Snowflake | 🟢 |
| rate_increase_pct, rate_status | EYO2 carrier×state benchmark ladder | Snowflake | 🟢 (drives P3 rate + risk) |

## Default automation / auto-renewal
| Field | Source | Via | Status |
|---|---|---|---|
| default_automation, default_automation_date | RENEWAL_AUTO_FINALIZE_RECORDS | Snowflake | 🟢 |
| auto_renewal | SNOWPLOW_FACTS.GA_TRACK_365_DAYS — `CATEGORY='Renewals' AND ACTION='ConfirmDefaultAndSkipFlow'`, keyed `COMPANY_ID=zp_company_id` (`auto_renewal.sql`) | Snowflake | 🟢 |
| automation_eligible, rate_parse_success | RENEWAL_AUTO_FINALIZE_RECORDS + RATE_PARSING_RECORDS (`auto_finalize.sql`) | Snowflake | 🟢 |

> **auto_renewal = CUSTOMER auto-renewal** (customer confirmed the default and skipped the flow, Snowplow). Distinct from `default_automation` (system auto-finalize). P1 "Default Automation" fires on `default_automation`.

## Recommendation / SLA / timing / alternates / LF
| Field | Source | Via | Status |
|---|---|---|---|
| rfd_sla, erc_sla, alt_sla | sfdc_opportunity_history stage SLOs (`sla.sql`) | Snowflake | 🟢 |
| time_in_erc, days_to_default | opp-history dwell (`time_in_erc.sql`, `time_in_rfd.sql`) | Snowflake | 🟢 |
| default_rec_sent, default_rec_built | first_recommendation_sent_ts / MEDICAL_PACKAGE_OFFERINGS (`rec_timing.sql`) | Snowflake | 🟢 |
| alt_* (requested/created/published/days) | RENEWAL_PLAN_RECOMMENDATIONS (`alt.sql`) + timing | Snowflake / derived | 🟢 |
| lf_savings_pct, lf_in_alt, lf_quote | GROUP_LEVEL_PLAN_RATES vs default rec (`lf.sql`) | Snowflake | 🟢 |
| lf_savings_band | (band of lf_savings_pct) | Derived | ⚪ |

## Customer Contact
| Field | Source | Via | Status |
|---|---|---|---|
| last_outbound_email_date, last_inbound_email_date | BENEFIT_ORDER_TOUCHPOINTS, **advising-attributed** (`email_recency.sql`) | Snowflake | 🟢 (gone-quiet #1 & #2) |
| last_call_date, last_connect_date, last_call_disp | SF `task` (type ilike '%call%') joined to Benefits Renewal Case; connect = Status 'Connect', else VM/Attempt (`sf_activity.sql`) | Snowflake | 🟢 (last_connect_date = gone-quiet #3) |
| intro_connect, connect_date, intro_connect_date | BI.CASES + task activity (`sf_activity.sql`) | Snowflake | 🟢 |
| last_update, last_update_date | task activity (`sf_activity.sql`) | Snowflake | 🟢 |
| intro_call, intro_call_date | Case.Intro_Call_Completed__c (+ CreatedDate proxy) | **Salesforce MCP** | 🟢 |
| email_due, email_due_hoop_*, email_pending*, email_received_date | BENEFIT_ORDER_TOUCHPOINTS HOOP calc, **advising-attributed + case-open-now** (`email_due.sql`) | Snowflake | 🟢 |
| email_sla | inbound answered ≤240 HOOP-min, any-late=Missed — **advising-attributed** (ownership ladder) (`email_sla.sql`) | Snowflake | 🟢 |

## Flags / Sentiment / Tickets / Cases
| Field | Source | Via | Status |
|---|---|---|---|
| sep, bor_term, blocked_reason | ADVISING_OPPORTUNITIES (`sf_open_signals`, `cohort.sql`) | Snowflake | 🟢 |
| selection_deadline, submission_deadline | OFFERING_SELECTION_DEADLINE / CASE2 | Snowflake | 🟢 |
| recert_ticket, recert_lateness_days | BI.SFDC_TICKETS open recert ticket | Snowflake | 🟢 |
| recert_status | Ticket__c.Recert_Status__c | **Salesforce MCP** | 🟢 |
| packets_files, packet_carriers | ContentDocumentLink (Title ~ 'Renewal Packet') | **Salesforce MCP** | 🟢 |
| lead_days | DATEDIFF(create → renewal) | Snowflake | 🟢 |
| csat*, in_app*, survey* | surveys / in-app sentiment (`inapp.sql`, `survey_answers.sql`, `surveys_12mo.sql`) | Snowflake | 🟢 |
| tickets_to_advising, open_tickets, open_tickets_past_sla | BI.SFDC_TICKETS (`tickets.sql`, `open_tickets.sql`) | Snowflake | 🟢 |
| ticket_sla | OA→Advising resolution ≤5d, any-late=Missed (`ticket_sla.sql`) | Snowflake | 🟢 |
| bo_status, open_cases_*, case_summary | benefit order / BI.CASES (`open_cases_by_type.sql`, `cases.sql`) | Snowflake | 🟢 |

## Closed-only / timeline / risk
| Field | Source | Via | Status |
|---|---|---|---|
| outcome, closed_on, inferred_close_date | opp close + MRR-method inference | Snowflake/derived | 🧊 |
| cycle_open, tl_* | RENEWALS.created_at + timeline derivations | Snowflake / derived | 🟢 / ⚪ |
| risk | Open = weighted score (Σwt 128) + **gone-quiet floor override** (3 recency signals >21d/null: 3→High, 1-2→Med, 0→none); PF = 5-factor model; Closed = frozen | Derived (builder) | ⚪ |

---

## Summary
**Every field refreshes live daily on Open/PF.** Snowflake (headless in `refresh_advising_hub.py`) covers identity, stage, MRR/enrollment, premium deltas, rate index, default automation + auto-renewal, SLA, timing, alternates, LF, email recency/due/SLA, call recency (last_call/connect/disp), recert ticket, deadlines, flags, sentiment, tickets, cases. Salesforce MCP (pulled by the daily task before the python step) covers intro_call, recert_status, packets. Closed snapshot values frozen by design (only CSAT/in-app re-checked). `queue_tier`, `tab`, `risk`, `lf_savings_band`, `tl_*` are derived in the builder and (queue_tier/tab) not persisted.
