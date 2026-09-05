-- ═══════════════════════════════════════════════════════════════════════════════
-- TICKET SLA FOR ADVISING / OA — Detail Query
-- ═══════════════════════════════════════════════════════════════════════════════
-- Redash ID:    148704
-- Version:      v3 (2026-05-30)
-- Grain:        One row per SFDC_TICKET_ID (ticket-level detail)
-- Author:       Aman (BenOps Analytics)
-- Last updated: 2026-05-30
--
-- ═══════════════════════════════════════════════════════════════════════════════
-- PURPOSE
-- ═══════════════════════════════════════════════════════════════════════════════
-- Produces a ticket-level dataset for analyzing SLA performance across
-- inter-team ticket routing flows within Benefits Operations. Each row
-- represents one closed ticket with its routing metadata, ownership chain,
-- time-to-close, and associated benefit order + opportunity context.
--
-- Primary consumers:
--   • Ticket SLA by Flow Dashboard (HTML, v7+) — CSV upload, client-side analysis
--   • Ad-hoc Redash analysis on ticket routing patterns and TTC distributions
--
-- The dashboard segments tickets into routing flows based on
-- TICKET_REPORTING_TEAM → TICKET_TEAM/TICKET_SUBTEAM combinations:
--
--   Flow 1:  Fulfillment → Implementation Advocate (SLA: 2 days)
--   Flow 2:  Fulfillment → Fulfillment, with OA longest held (SLA: 2 days)
--   Flow 3:  Implementation Advocate → New Plan Sales (SLA: 5 days)
--   Flow 4a: Implementation Advocate → Benefits Advising (SLA: 5 days)
--   Flow 4b: Implementation Advocate → Advising Fulfillment (SLA: 5 days)
--   Flow 5:  Fulfillment → Fulfillment, no OA (SLA: 2 days)
--
--   Note: dashboard v10+ merges Flow 1 + Flow 2 into "Ful → OA" attributed to
--   OA_LONGEST_OWNER_NAME, and drops Flow 4b. The SQL still emits all rows;
--   flow segmentation happens downstream in the dashboard.
--
-- ═══════════════════════════════════════════════════════════════════════════════
-- PARAMETERS (Redash)
-- ═══════════════════════════════════════════════════════════════════════════════
--   {{Date Range Start}}   DATE   Start of ticket closed date range (inclusive)
--   {{Date Range End}}     DATE   End of ticket closed date range (inclusive)
--
-- Filter applied on: TICKET_CLOSED_TS_MT::DATE (Mountain Time)
-- Note: This query does NOT pre-filter by reporting team, ticket team, or
-- record type — all tickets closed in the date range are returned. Flow
-- segmentation is done downstream in the dashboard.
--
-- ═══════════════════════════════════════════════════════════════════════════════
-- DATA SOURCES
-- ═══════════════════════════════════════════════════════════════════════════════
--   BI.SFDC_TICKETS (tix)
--     Primary ticket table. Contains ticket metadata, ownership, routing
--     fields (REPORTING_TEAM, TEAM, SUB_TEAM), escalation reasons,
--     OA longest-held ownership, and time-to-close.
--     Timestamps: CREATED_TS and CLOSED_TS are in UTC.
--
--   BI_REPORTING.BENEFIT_ORDERS (bo)
--     Benefit order reporting table. Provides RECORD_TYPE_NAME (New Plan,
--     Renewal, Change), BENEFIT_ORDER_OWNER, and SFDC_BENEFIT_ORDER_OWNER_ID.
--     INNER JOIN — only tickets linked to a benefit order are included.
--     NOTE: This reporting view EXCLUDES ~6,099 BOs marked as "Duplicate",
--     "Accidental Sign", or "Closed Admin/Other" via an upstream dbt filter.
--     Tickets attached to those BOs (~708 in 2024-01-01 → 2026-05-30) silently
--     drop from this dataset. To include them, switch to BI.BENEFIT_ORDERS (raw)
--     and apply your own status filter. Left as-is intentionally for v3.
--
--   BI_REPORTING.ADVISING_OPPORTUNITIES (oppt)
--     Advising opportunity table. Provides OWNER_NAME and SFDC_OWNER_ID for
--     the opportunity linked to the ticket.
--     LEFT JOIN — not all tickets have an associated opportunity.
--
--   BI.SFDC_USERS_GUSTO_EMPLOYEES_VIEW (v1, in IC_EE_ID CTE)
--     Maps SFDC user IDs to employee IDs. An employee may have multiple
--     historical SFDC user IDs across different stints/roles.
--
--   BI.GUSTO_EMPLOYEES (v2, in IC_EE_ID CTE)
--     Employee dimension table. LEFT JOINED with current_flag = TRUE
--     condition so terminated employees flow through (with NULL v2 fields).
--
-- ═══════════════════════════════════════════════════════════════════════════════
-- CTE PIPELINE
-- ═══════════════════════════════════════════════════════════════════════════════
--   IC_EE_ID (v3 redesign)
--     Employee identity resolution CTE. Returns one row per HISTORICAL
--     SFDC user ID (v1.sfdc_user_id) → owner name pair.
--
--     • Joins SFDC_USERS_GUSTO_EMPLOYEES_VIEW (v1) LEFT to GUSTO_EMPLOYEES (v2)
--       on SFDC_EE_ID. The current_flag=TRUE condition is on the JOIN clause,
--       NOT a WHERE filter — so terminated employees (with no current_flag=TRUE
--       row) still flow through with NULL v2 columns.
--
--     • Name resolution: COALESCE(v2.name, v1.name) — prefers the current name
--       from gusto_employees when available, falls back to the historical name
--       from sfdc_users_gusto_employees_view. Handles preferred-name updates
--       (e.g., "Idalis Anderson" → "Dallas Anderson") and marriage/legal-name
--       changes.
--
--     • Join key in final SELECT: v1.sfdc_user_id (historical). Resolves
--       OA_LONGEST_HELD_OWNER_ID values that reference user IDs an employee
--       had BEFORE any SFDC migration/role change — fixes the case where
--       active or terminated employees with mid-career user-ID changes were
--       previously appearing as NULL.
--
--     • Known exclusion: EE_ID 111883 (Lameriah Smith duplicate employee record).
--
--     • DEDUP: QUALIFY ROW_NUMBER() OVER (PARTITION BY v1.sfdc_user_id ORDER BY
--       CASE WHEN v2.name IS NOT NULL THEN 0 ELSE 1 END, v1.sfdc_ee_id) = 1.
--       Picks one row per join key, preferring rows that found a v2 match
--       (so the current name wins) and breaking ties deterministically on EE_ID.
--
-- ═══════════════════════════════════════════════════════════════════════════════
-- JOINS
-- ═══════════════════════════════════════════════════════════════════════════════
--   tix → bo     INNER JOIN on SFDC_BENEFIT_ORDER_ID
--                 Only tickets with a linked benefit order are included.
--                 Tickets without a BO (e.g., general inquiry tickets) are
--                 excluded by design.
--
--   tix → oppt   LEFT JOIN on SFDC_OPPORTUNITY_ID = SFDC_OBJECT_ID
--                 Many tickets don't have an associated opportunity, especially
--                 Fulfillment-originated tickets. NULL OPPT_OWNER_NAME is
--                 expected and normal for these flows.
--
--   tix → ee     LEFT JOIN on OA_LONGEST_HELD_OWNER_ID = ee.sfdc_user_id (v3)
--                 Resolves the OA who held the ticket longest into a name.
--                 v3: join on HISTORICAL sfdc_user_id (was current_sfdc_user_id
--                 in v1/v2) — fixes terminated-employee blanks and mid-career
--                 user-ID-change blanks. NULL only when the ticket was never
--                 held by an OA (no OA ownership touchpoints).
--
-- ═══════════════════════════════════════════════════════════════════════════════
-- COLUMN DICTIONARY
-- ═══════════════════════════════════════════════════════════════════════════════
-- Naming conventions:
--   _MT            Mountain Time (America/Denver) converted from UTC
--   _TS            Timestamp (datetime)
--   _ID            Salesforce 18-char ID
--   _NAME          Human-readable name
--   _MIN           Duration in minutes
--
-- GROUP 1: TICKET IDENTITY & LINKS
--   TICKET_NAME                    Human-readable ticket name (e.g., Ticket-00833484)
--   TICKET_LINK_LIGHTNING          Clickable Salesforce lightning URL for the ticket
--   SFDC_TICKET_ID                 Salesforce 18-char ticket ID (primary key)
--   SFDC_OWNER_ID                  Salesforce user ID of the current ticket owner
--
-- GROUP 2: TIMESTAMPS
--   TICKET_CREATED_TS_MT           Ticket creation timestamp, Mountain Time
--                                  Source: BI.SFDC_TICKETS.CREATED_TS (UTC) →
--                                  CONVERT_TIMEZONE('UTC','America/Denver',...)
--   TICKET_CLOSED_TS_MT            Ticket close timestamp, Mountain Time
--                                  Used as the date filter (WHERE clause) and
--                                  for weekly/monthly bucketing in the dashboard.
--
-- GROUP 3: TICKET ROUTING & CLASSIFICATION
--   CREAATED_BY_ROLE               Role of the person who created the ticket
--                                  (note: column has a typo in source — double 'A')
--   SFDC_BENEFIT_ORDER_ID          Linked benefit order Salesforce ID
--   BENEFIT_ORDER_RECORD_TYPE_NAME Record type of the linked BO (New Plan,
--                                  Renewal, Change). From BI_REPORTING.BENEFIT_ORDERS.
--   TICKET_STATUS                  Current ticket status (e.g., Closed)
--   TICKET_TEAM                    Destination team the ticket was routed TO
--   TICKET_SUBTEAM                 Destination subteam within TICKET_TEAM
--   TICKET_REPORTING_TEAM          Reporting team of the ticket creator — used
--                                  as the "FROM" field in flow segmentation.
--   SFDC_OPPORTUNITY_ID            Linked opportunity Salesforce ID (may be NULL)
--   TICKET_REASON                  Primary escalation/ticket reason
--   TICKET_REASON_DETAIL           Sub-detail under TICKET_REASON
--   FALSE_POSITIVE                 Boolean flag. Downstream consumers should
--                                  filter FALSE_POSITIVE = FALSE or IS NULL.
--                                  (Not applied in this query or dashboard today.)
--
-- GROUP 4: TICKET OWNERSHIP (current ticket owner)
--   TICKET_OWNER_NAME              Full name of the current ticket owner
--   TICKET_OWNER_PE_NAME           PE (manager) of the ticket owner at time of assignment
--   TICKET_OWNER_PEPE_NAME         PEPE (skip-level) of the ticket owner at assignment
--   TICKET_OWNER_PE_NAME_CURRENT   PE of the ticket owner as of today
--   TICKET_OWNER_PEPE_NAME_CURRENT PEPE of the ticket owner as of today
--   COMPANY_ID                     Gusto company ID associated with the ticket
--
-- GROUP 5: OA OWNERSHIP (longest-held OA)
--   OA_LONGEST_HELD_OWNER_ID       SFDC user ID of the OA who held the ticket longest.
--                                  NULL if no OA ownership touchpoints exist.
--   TOTAL_OA_HELD_TIME_MIN         Total minutes the ticket was held by OA(s).
--                                  NULL if no OA ownership touchpoints.
--   OA_LONGEST_OWNER_NAME          Human-readable name of the longest-held OA.
--                                  v3 resolution: IC_EE_ID joined on historical
--                                  v1.sfdc_user_id, with COALESCE(v2.name, v1.name).
--                                  Resolves both: (a) terminated employees still
--                                  showing on their historical tickets, and
--                                  (b) preferred-name display (e.g., "Dallas
--                                  Anderson" instead of legacy "Idalis Anderson").
--                                  NULL only when no OA held the ticket.
--
-- GROUP 6: TIME TO CLOSE
--   TIME_TO_CLOSE_MIN              Pre-computed TTC in minutes from BI.SFDC_TICKETS.
--
-- GROUP 7: BENEFIT ORDER CONTEXT
--   BENEFIT_ORDER_OWNER            Name of the benefit order owner (the assigned OA).
--                                  From BI_REPORTING.BENEFIT_ORDERS. Note: this column
--                                  may resolve to a different name string than
--                                  OA_LONGEST_OWNER_NAME for the same SFDC OwnerId
--                                  (different upstream name attributes per source).
--   SFDC_BENEFIT_ORDER_OWNER_ID    SFDC user ID of the benefit order owner.
--
-- GROUP 8: OPPORTUNITY CONTEXT
--   OPPT_OWNER_NAME                Name of the opportunity owner (Sales rep or Advisor).
--                                  From BI_REPORTING.ADVISING_OPPORTUNITIES.
--                                  NULL for tickets without a linked opportunity.
--   OPPT_OWNER_ID                  SFDC user ID of the opportunity owner.
--
-- ═══════════════════════════════════════════════════════════════════════════════
-- DASHBOARD ATTRIBUTION MODEL (for reference)
-- ═══════════════════════════════════════════════════════════════════════════════
-- v10+ dashboard groups Owner Performance by a PRIMARY field and shows a
-- SECONDARY field in the ticket detail drilldown:
--
--   Flow            | Primary (grouped by)       | Secondary (in detail)
--   ────────────────┼────────────────────────────┼──────────────────────────
--   Ful → OA        | OA_LONGEST_OWNER_NAME      | TICKET_OWNER_NAME
--   OA → NPS        | TICKET_OWNER_NAME          | OPPT_OWNER_NAME
--   OA → BenAdv     | TICKET_OWNER_NAME          | OPPT_OWNER_NAME
--   Ful → Ful       | TICKET_OWNER_NAME          | BENEFIT_ORDER_OWNER
--
-- ═══════════════════════════════════════════════════════════════════════════════
-- TIMEZONE NOTES
-- ═══════════════════════════════════════════════════════════════════════════════
-- • SFDC_TICKETS.CREATED_TS and CLOSED_TS are stored in UTC. Both are converted
--   to Mountain Time (America/Denver) in this query.
-- • The WHERE filter uses the Mountain Time converted value.
-- • Dashboard v9+ extracts YYYY-MM-DD directly from the raw MT string to avoid
--   browser-local timezone drift on bucketing.
--
-- ═══════════════════════════════════════════════════════════════════════════════
-- KNOWN ISSUES & EDGE CASES
-- ═══════════════════════════════════════════════════════════════════════════════
-- 1. CREAATED_BY_ROLE has a typo (double 'A') in the source table. Preserved
--    as-is to match BI.SFDC_TICKETS column name.
--
-- 2. OPPT_OWNER_NAME is NULL for most Fulfillment-originated tickets and for
--    some OA → NPS tickets where the opportunity link is missing. Expected.
--
-- 3. OA_LONGEST_OWNER_NAME is NULL when no OA ownership touchpoints exist.
--    This is the distinguishing field between Flow 2 (Ful→Ful+OA, NOT NULL)
--    and Flow 5 (Ful→Ful, NULL).
--
-- 4. EE_ID 111883 (Lameriah Smith) is hardcoded out of IC_EE_ID due to a
--    known duplicate employee record in the source system.
--
-- 5. The INNER JOIN to BENEFIT_ORDERS excludes tickets that are not linked
--    to a benefit order. This is intentional.
--
-- 6. BI_REPORTING.BENEFIT_ORDERS upstream filter: ~6,099 BOs flagged as
--    Duplicate / Accidental Sign / Closed Admin are filtered out before this
--    query joins to them. This silently drops ~708 attached tickets per the
--    2024-01-01 → 2026-05-30 window. Acceptable for SLA analysis; flagged
--    here for awareness.
--
-- 7. BENEFIT_ORDER_OWNER vs OA_LONGEST_OWNER_NAME can return different name
--    strings for the same SFDC OwnerId (e.g., legal name vs preferred name).
--    v3's COALESCE(v2.name, v1.name) closes most of this gap on the
--    OA_LONGEST_OWNER_NAME side, but BENEFIT_ORDER_OWNER comes from a different
--    upstream resolution and is not touched by this query.
--
-- ═══════════════════════════════════════════════════════════════════════════════
-- VERSION HISTORY
-- ═══════════════════════════════════════════════════════════════════════════════
-- v1  (2026-02-22)  Initial query. Used CREAATED_BY_ROLE for flow segmentation.
--                   No BENEFIT_ORDER_RECORD_TYPE_NAME column.
--
-- v2  (2026-05-05)  Added BENEFIT_ORDER_RECORD_TYPE_NAME from benefit_orders.
--                   Fixed duplicate rows (5,156 tickets appearing 2x) caused by
--                   IC_EE_ID CTE fan-out: employees with multiple historical
--                   SFDC user IDs in sfdc_users_gusto_employees_view produced
--                   multiple rows per current_sfdc_user_id in GROUP BY ALL.
--                   Fix A: QUALIFY dedup in IC_EE_ID on current_sfdc_user_id.
--                   Fix B: Defensive QUALIFY on final SELECT by SFDC_TICKET_ID.
--                   Row count: 146,257 → 141,101 (exact duplicates removed).
--                   Added comprehensive documentation header.
--
-- v3  (2026-05-30)  Fixed OA name resolution for two distinct issues:
--                   (a) Terminated employees losing attribution on historical
--                       tickets because the CTE filtered to current_flag=TRUE
--                       in the JOIN (not the predicate).
--                   (b) Mid-career SFDC user-ID changes leaving historical
--                       tickets unresolved because the join used the CURRENT
--                       user ID instead of the historical one.
--                   Fixes:
--                     - IC_EE_ID redesigned: LEFT JOIN gusto_employees, drop
--                       all unused columns, use COALESCE(v2.name, v1.name) so
--                       current name preferred, historical name as fallback.
--                     - Final join changed from ee.current_sfdc_user_id to
--                       ee.sfdc_user_id (historical), so any user ID the
--                       employee ever had resolves.
--                     - QUALIFY dedup partitions on v1.sfdc_user_id with
--                       deterministic tiebreaker preferring v2-matched rows.
--                   Impact (2024-01-01 → 2026-05-30):
--                     - 875 previously-blank OA names recover (Khelsea Hamilton
--                       397, Danica McMullen 372, William Alvaracio 178, …)
--                     - 3,909 tickets re-label to current name (Idalis → Dallas
--                       Anderson 1,076, Valerie Walker → Valerie Gorman 759, …)
--                     - 0 regressions (no resolved → blank).
--                   Also added KNOWN ISSUES #6 (bi_reporting BO filter) and
--                   #7 (BO_OWNER vs OA_LONGEST_OWNER_NAME name divergence)
--                   for awareness.
--
-- ═══════════════════════════════════════════════════════════════════════════════

WITH ic_ee_id AS (
  -- v3 redesign: resolve any historical SFDC user ID → owner name.
  -- LEFT JOIN gusto_employees so terminated employees still flow through.
  -- COALESCE prefers current name (v2) over historical (v1) for preferred-name
  -- and marriage/legal-name updates.
  SELECT
    v1.sfdc_user_id,
    COALESCE(v2.name, v1.name) AS name
  FROM bi.sfdc_users_gusto_employees_view v1
  LEFT JOIN bi.gusto_employees v2
    ON v2.sfdc_ee_id = v1.sfdc_ee_id
   AND v2.current_flag = TRUE
  WHERE v1.sfdc_ee_id <> 111883  -- Lameriah Smith duplicate employee record
  -- Dedup: one row per historical sfdc_user_id (the final join key).
  -- Prefer rows that found a v2 match (so current name wins); break ties
  -- deterministically on sfdc_ee_id.
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY v1.sfdc_user_id
    ORDER BY CASE WHEN v2.name IS NOT NULL THEN 0 ELSE 1 END, v1.sfdc_ee_id
  ) = 1
)

SELECT
  -- GROUP 1: TICKET IDENTITY & LINKS
  tix.ticket_name,
  'https://gusto.lightning.force.com/lightning/r/Ticket__c/' || tix.sfdc_ticket_id || '/view' AS ticket_link_lightning,
  tix.sfdc_ticket_id,
  tix.sfdc_owner_id,

  -- GROUP 2: TIMESTAMPS (UTC → Mountain Time)
  CONVERT_TIMEZONE('UTC', 'America/Denver', tix.created_ts) AS ticket_created_ts_mt,
  CONVERT_TIMEZONE('UTC', 'America/Denver', tix.closed_ts)  AS ticket_closed_ts_mt,

  -- GROUP 3: TICKET ROUTING & CLASSIFICATION
  tix.creaated_by_role,
  tix.sfdc_benefit_order_id,
  bo.record_type_name                       AS benefit_order_record_type_name,
  tix.status                                AS ticket_status,
  tix.team                                  AS ticket_team,
  tix.sub_team                              AS ticket_subteam,
  tix.reporting_team                        AS ticket_reporting_team,
  tix.sfdc_opportunity_id,
  tix.escalation_reason                     AS ticket_reason,
  tix.escalation_reason_detail              AS ticket_reason_detail,
  tix.false_positive,

  -- GROUP 4: TICKET OWNERSHIP (current owner + PE chain)
  -- Resolve owner to canonical gusto/HR name via sfdc_owner_id bridge (fallback
  -- to raw for system accounts). Fixes nickname/legal-name mismatches. Mirrors v12.
  COALESCE(ee_tix.name, tix.owner_full_name) AS ticket_owner_name,
  tix.owner_pe_name                         AS ticket_owner_pe_name,
  tix.owner_pepe_name                       AS ticket_owner_pepe_name,
  tix.owner_current_pe_name                 AS ticket_owner_pe_name_current,
  tix.owner_current_pepe_name               AS ticket_owner_pepe_name_current,
  tix.company_id,

  -- GROUP 5: OA OWNERSHIP (longest-held OA)
  tix.oa_longest_held_owner_id,
  tix.total_oa_held_time_min,
  ee.name                                   AS oa_longest_owner_name,

  -- GROUP 6: TIME TO CLOSE
  tix.time_to_close_min,

  -- GROUP 7: BENEFIT ORDER CONTEXT
  bo.benefit_order_owner,
  bo.sfdc_benefit_order_owner_id,

  -- GROUP 8: OPPORTUNITY CONTEXT
  oppt.owner_name                           AS oppt_owner_name,
  oppt.sfdc_owner_id                        AS oppt_owner_id

FROM bi.sfdc_tickets tix

-- INNER JOIN: only BO-linked tickets (excludes general inquiry tickets)
JOIN bi_reporting.benefit_orders bo
  ON tix.sfdc_benefit_order_id = bo.sfdc_benefit_order_id

-- LEFT JOIN: not all tickets have an associated opportunity
LEFT JOIN bi_reporting.advising_opportunities oppt
  ON oppt.sfdc_object_id = tix.sfdc_opportunity_id

-- LEFT JOIN: v3 — joins on HISTORICAL sfdc_user_id (was current_sfdc_user_id
-- in v1/v2). Resolves terminated employees and mid-career user-ID changes.
LEFT JOIN ic_ee_id ee
  ON ee.sfdc_user_id = tix.oa_longest_held_owner_id

-- LEFT JOIN: resolve current ticket owner's SFDC user id -> gusto name
LEFT JOIN ic_ee_id ee_tix
  ON ee_tix.sfdc_user_id = tix.sfdc_owner_id

WHERE CONVERT_TIMEZONE('UTC', 'America/Denver', tix.closed_ts)::date
      BETWEEN '{{Date Range Start}}' AND '{{Date Range End}}'

-- Defensive dedup on final output (safety guard, should be a no-op).
QUALIFY ROW_NUMBER() OVER (PARTITION BY tix.sfdc_ticket_id ORDER BY 1) = 1
;
