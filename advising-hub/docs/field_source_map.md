# Advising Hub — Field → Data Source Map

Every field in `advising_vnext_data.json` (129 top-level + 20 per-line), its data source, the system it's pulled through, and whether it refreshes live in the daily pipeline. Built from `hub_queries/catalog.json` (authoritative for live pulls). **As of the Sept 10 full-coverage reconstruction, every field now refreshes live daily** (Open/PF), via Snowflake or the Salesforce MCP; Closed opps stay frozen by design. The remaining ⚪ items are computed in the builder/assembler from live fields (no source pull of their own).

## Legend — refresh status
- 🟢 **Live daily** — re-pulled fresh every morning on Open/PF (Closed frozen). Has a query in `hub_queries/`.
- 🧊 **Closed-frozen (by design)** — snapshot fields locked at close; only CSAT/in-app re-checked.
- ⚪ **Derived** — computed in the builder/assembler from other fields; no source pull of its own.
- 🟡 **Carried-forward → Snowflake-reconstructable** — not yet live; source is in Snowflake, can be wired next.
- 🟠 **Carried-forward → Salesforce MCP** — not yet live; not in the Snowflake SF-mirror, but queryable via the Salesforce MCP (runs unattended, same as the LF dashboard).

## Legend — "Via"
- **Snowflake** — `DATA_WAREHOUSE_RC1` via the `snow`/connector (headless in the python pipeline).
- **Salesforce MCP** — live SOQL against Salesforce objects (`Ticket__c`, `Case`, `ContentDocumentLink`), run from the scheduled-task prompt like the LF dashboard does.
- **Local** — computed on this machine (e.g. the LF-signal classifier); not portable.
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
| days_in_stage_approx | (stage dates) | Derived | ⚪ |
| queue_tier | Outreach-priority logic | Derived (builder) | ⚪ |
| sf_opp_url, hippo_url, bo_url | opp/company/BO ids | Derived | ⚪ |

> **`queue_tier` and `tab` are computed live in the builder** (`build_advising_hub.py`) from live fields and are **NOT persisted in the dataset** (`advising_vnext_data.json`).

## Enrollment & MRR — 🟢 live Open/PF · 🧊 Closed (`mrr.sql`, `premium_lines.sql`, Snowflake)
| Field | Source | Via | Status |
|---|---|---|---|
| mrr, mrr_before, mrr_after | bi invoices / MRR price book | Snowflake | 🟢 / 🧊 |
| enrollees, carriers_enrolled, num_lines | HEALTH_SUBSCRIPTION_DETAILS + package offerings | Snowflake | 🟢 |
| contribution | (contribution calc) | Snowflake/derived | 🟢 |
| lines[].enr_before/after | HEALTH_SUBSCRIPTION_DETAILS | Snowflake | 🟢 / 🧊 |
| lines[].mrr_before/after | MRR price book (recomputed) | Snowflake | 🟢 / 🧊 |
| lines[].carrier, carrier_after, state | package offerings / plan dim | Snowflake | 🟢 |
| funding, funding_after | med_funding (extras) / premium_lines | Snowflake | 🟢 |

## Premium change — 🟢 live (`premium_lines_delta.sql`, Snowflake) · except rate index
| Field | Source | Via | Status |
|---|---|---|---|
| lines[].pr_exp_e, pr_exp_n | FCT_HEALTH_INSURANCE_RENEWAL_LIFECYCLE (expiring, eligible/enrolled avg) | Snowflake | 🟢 |
| lines[].pr_succ | FCT_..._RECOMMENDATION on successor plan | Snowflake | 🟢 |
| lines[].pr_dflt, pr_sel | FCT_..._RECOMMENDATION (default/selected flag) | Snowflake | 🟢 |
| lines[].pr_fin | lifecycle selected (enrolled avg) | Snowflake | 🟢 / 🧊 |
| lines[].d_succ, d_dflt, d_sel, d_fin | ratios of the above | Derived | 🟢 |
| lines[].rate_pct | (rate change per line) | Snowflake/derived | 🟢 |
| rating_region | GROUP_LEVEL_PLAN_RATES / plan dim | Snowflake | 🟢 (`rating_region.sql`) |
| rate_structure | plan rate structure (Age-banded/Composite) (`rate_index.sql`) | Snowflake | 🟢 |
| rate_increase_pct, rate_status | EYO2 carrier×state benchmark ladder (`rate_index.sql`) | Snowflake | 🟢 (drives P3 rate + risk) |

## Default automation / auto-renewal
| Field | Source | Via | Status |
|---|---|---|---|
| default_automation | RENEWAL_AUTO_FINALIZE_RECORDS (extras) | Snowflake | 🟢 |
| default_automation_date | RENEWAL_AUTO_FINALIZE_RECORDS | Snowflake | 🟢 |
| auto_renewal | SNOWPLOW_FACTS.GA_TRACK_365_DAYS — event `CATEGORY='Renewals' AND ACTION='ConfirmDefaultAndSkipFlow'`, keyed `COMPANY_ID=zp_company_id` within [renewal_date−120d, +31d) (`auto_renewal.sql`) | Snowflake | 🟢 |
| automation_eligible, rate_parse_success | RENEWAL_AUTO_FINALIZE_RECORDS + RATE_PARSING_RECORDS (`auto_finalize.sql`) | Snowflake | 🟢 |

> **auto_renewal is the CUSTOMER auto-renewal** — the customer *confirmed the default package and skipped* the renewal flow (Snowplow `ConfirmDefaultAndSkipFlow`). This is **DISTINCT from `default_automation`**, which is the *system* auto-finalize flag from RENEWAL_AUTO_FINALIZE_RECORDS. It replaced the old ADVISING_OPPORTUNITIES.REASON_FOR_ADVISING derivation (unreliable, broke at FY26 Q2).

## Recommendation / SLA / timing
| Field | Source | Via | Status |
|---|---|---|---|
| rfd_sla, erc_sla, alt_sla | sfdc_opportunity_history stage SLOs (`sla.sql`) | Snowflake | 🟢 |
| time_in_erc | sfdc_opportunity_history 'ER Confirm' dwell (`time_in_erc.sql`) | Snowflake | 🟢 |
| days_to_default (Time in RFD) | sfdc_opportunity_history 'Ready for Default Package' dwell (`time_in_rfd.sql`) | Snowflake | 🟢 |
| default_rec_sent, default_rec_built | first_recommendation_sent_ts / MEDICAL_PACKAGE_OFFERINGS (`rec_timing.sql`) | Snowflake | 🟢 |
| days_to_rec_cycle, time_to_default_rec_days, rfd_to_rec_sent_days | recommendation timing (from cycle_open + default_rec_sent + rfd) | Derived | 🟢 |
| alt_requested, alt_req_date, alt_pub_count/first/last/carriers | RENEWAL_PLAN_RECOMMENDATIONS published alts (`alt.sql`) | Snowflake | 🟢 |
| alt_created/date/days, alt_published/date/days/basis, alt_requested_date/days, days_to_alt | alt.sql + timing derivations | Snowflake/derived | 🟢 / ⚪ |

## Alternates / Level-Funded
| Field | Source | Via | Status |
|---|---|---|---|
| lf_savings_pct | GROUP_LEVEL_PLAN_RATES enrolled-avg vs default rec (`lf.sql`) | Snowflake | 🟢 (LF reason-code classifier is optional/local, not needed for this field) |
| lf_savings_band | (band of lf_savings_pct) | Derived | ⚪ |
| lf_in_alt | published alt contains the LF plan (LF-dash defn) (`lf.sql`) | Snowflake | 🟢 |
| lf_quote | LF quote available (`lf.sql`) | Snowflake | 🟢 |

## Customer Contact
| Field | Source | Via | Status |
|---|---|---|---|
| last_outbound_email_date, last_inbound_email_date | BENEFIT_ORDER_TOUCHPOINTS (`email_recency.sql`) | Snowflake | 🟢 |
| intro_connect, connect_date, intro_connect_date | BI.CASES + task activity (`sf_activity.sql`) | Snowflake | 🟢 |
| last_update, last_update_date, last_contact_date | task activity (`sf_activity.sql`) | Snowflake | 🟢 |
| intro_call, intro_call_date | Case.Intro_Call_Completed__c (+ Case CreatedDate proxy) | **Salesforce MCP** (daily task) | 🟢 |
| email_due, email_due_hoop_days/hrs/status, email_pending/date/days, email_received_date | BENEFIT_ORDER_TOUCHPOINTS HOOP calc (`email_due.sql`) | Snowflake | 🟢 |
| email_sla | inbound answered ≤240 HOOP-min, any-late=Missed (`email_sla.sql`) | Snowflake | 🟢 |
| last_contact_date | SF activity last outbound touch — field kept; no longer shown in Overview insights (superseded by Last SF update) | Snowflake | 🟢 |

## Flags
| Field | Source | Via | Status |
|---|---|---|---|
| sep | ADVISING_OPPORTUNITIES.SPECIAL_ENROLLMENT (`sf_open_signals`) | Snowflake | 🟢 (all false in cohort) |
| bor_term | ADVISING_OPPORTUNITIES.ADVISING_BLOCKED_REASON | Snowflake | 🟢 |
| blocked_reason | ADVISING_OPPORTUNITIES (`cohort.sql`) | Snowflake | 🟢 |
| selection_deadline, submission_deadline | OFFERING_SELECTION_DEADLINE / CASE2 submission deadline | Snowflake | 🟢 |
| recert_ticket, recert_flag_date, recert_lateness_days | BI.SFDC_TICKETS open recert ticket | Snowflake | 🟢 |
| recert_status | Ticket__c.Recert_Status__c (latest recert ticket) | **Salesforce MCP** (daily task) | 🟢 |
| packets_files, packet_carriers | ContentDocumentLink (Title ~ 'Renewal Packet', linked to Opp) | **Salesforce MCP** (daily task) | 🟢 |
| lead_days | DATEDIFF(create → renewal) (`sf_open_signals`) | Snowflake | 🟢 |

## Sentiment
| Field | Source | Via | Status |
|---|---|---|---|
| csat, csat_comment, csat_current | Renewed Benefits Feedback survey (extras/surveys) | Snowflake | 🟢 |
| in_app, inapp_current, in_app_comment, in_app_date | in-app sentiment survey (`inapp.sql`) | Snowflake | 🟢 |
| survey_answered, survey_answers | survey answers (`survey_answers.sql`) | Snowflake | 🟢 |
| surveys_12mo, all_survey_count | 12-mo survey history (`surveys_12mo.sql`) | Snowflake | 🟢 |
| survey_summary | (rollup) | Derived | ⚪ |

## Tickets / Benefit order / Cases
| Field | Source | Via | Status |
|---|---|---|---|
| tickets_to_advising, tickets_list | BI.SFDC_TICKETS team='Benefits Advising' (`tickets.sql`) | Snowflake | 🟢 |
| open_tickets, open_tickets_past_sla | BI.SFDC_TICKETS status+age (`open_tickets.sql`) | Snowflake | 🟢 |
| ticket_sla | OA→Advising ticket resolution ≤5d, any-late=Missed (`ticket_sla.sql`) | Snowflake | 🟢 |
| bo_status | benefit order status (extras) | Snowflake | 🟢 |
| open_cases_by_type, open_cases_total | BI.CASES by record type (`open_cases_by_type.sql`) | Snowflake | 🟢 |
| case_summary | BI.CASES + activity (`cases.sql` + `sf_activity.sql`) | Snowflake | 🟢 |

## Closed-only / timeline / risk
| Field | Source | Via | Status |
|---|---|---|---|
| outcome, closed_on, inferred_close_date | opp close + MRR-method inference | Snowflake/derived | 🧊 |
| cycle_open, tl_cycle_open | RENEWALS.created_at cycle-open (`rec_timing.sql`) | Snowflake | 🟢 |
| tl_renewal, tl_selection, tl_rec_sent, tl_default_built, tl_alt_requested, tl_alt_published, tl_outcome | timeline (from dates above) | Derived | ⚪ |
| risk | Open EYO2 / PF 5-factor model | Derived (builder) | ⚪ |

---

## Summary — full live coverage (Sept 10)
**Every field now refreshes live daily on Open/PF.** Two source systems, both run unattended by the 7:30a ET daily task:

- **Snowflake (headless, in `refresh_advising_hub.py`):** identity, stage, MRR/enrollment, per-line premium deltas, rate index (rate_increase_pct/rate_status/rate_structure), rating region, funding, default automation + automation_eligible/rate_parse_success, auto-renewal (customer confirm-default-and-skip, from Snowplow GA_TRACK_365_DAYS), SLA (RFD/ERC/Alt), time-in-ERC, days_to_default (Time in RFD), alternates, LF (savings %/band/in_alt/quote), recommendation timing (default_rec_sent/built, cycle_open), email recency + email-due/HOOP, intro-connect/activity, recert ticket, deadlines, BoR/term, SEP, lead days, tickets/open-tickets, cases, CSAT/in-app/surveys, BO status.
- **Salesforce MCP (pulled by the daily task orchestrator before the python step):** `intro_call`/`intro_call_date` (Case.Intro_Call_Completed__c + Case CreatedDate proxy), `recert_status` (Ticket__c.Recert_Status__c, latest recert ticket), `packets_files`/`packet_carriers` (ContentDocumentLink, Title ~ 'Renewal Packet', linked to the Opp). Carry-forward safety: if the SF-MCP pull is unavailable on a given run, these keep their prior values.

**⚪ Derived** (computed in builder/assembler from the live fields above): queue_tier, risk, tab, survey_summary, lf_savings_band, the `tl_*` timeline fields, the alt day-count derivations, url fields. **Note:** `queue_tier` and `tab` are computed live in `build_advising_hub.py` and are **NOT persisted** in `advising_vnext_data.json`.

**🧊 Frozen by design:** all Closed-opp snapshot values (final premium, MRR before/after, enrolled before/after, outcome, close date) — only CSAT/in-app re-check.

**Not portable (local only):** `lf_signal_classifier.py` produces LF *reason codes* for the separate LF-conversion dashboard; it is an optional, non-fatal enrichment and is **not** required for the hub's LF fields (which come purely from Snowflake).
