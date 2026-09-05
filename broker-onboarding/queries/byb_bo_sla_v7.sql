-- ============================================================================
-- BYB BO-GRAIN SLA DETAIL QUERY — v7
-- ============================================================================
-- One row per Benefits BYB benefit order with BO attributes, stint-derived
-- SLA metrics for 7 statuses across 3 buckets (Transition / Ready for Intro /
-- Implementation), Customer Facing bucket, and SFDC opportunity owner.
--
-- Filtered on FIRST_END_DT (Mountain Time) — fulfilled or cancelled orders.
--
-- Parameters: {{Date Range Start}} and {{Date Range End}} (TIMESTAMP).
--
-- v7 additions vs v6:
--   • Transition statuses SLA 1d → 2d (5 statuses)
--   • Implementation SLA differentiated: 10d for 'New to BYB - No OE', 5d others
--   • ORDER_TYPE_TIER ('Fast' / 'Standard' / 'Complex' / 'N/A')
--   • E2E_SLA_TARGET (15 / 45 / 50) and E2E_SLA_MET
--
-- v7.1 (2026-07-02) — in-place updates, still v7 filename:
--   • New BLOCKED bucket = Blocked + With Sales + With Advising (30d soft target).
--   • Cust Facing additions: OE Prep (5d), Pending ER Signature (5d), OE Extended (5d).
--   • Canonicalized FROM_STATUS casing: 'Plans confirmed' → 'Plans Confirmed',
--     'Fulfillment Prep' → 'Fulfillment prep' (matches actual DB STATUS column).
-- v7.3 (2026-07-03) — in-place, still v7 filename:
--   • CURRENT_STATUS_SYNTH CTE — manufactures a synthetic in-progress stint for each open
--     order so its current-status time is counted in per-status + per-bucket totals and
--     SLA_MET flags. Fixes silent under-counting of open orders that have been sitting in
--     a status but haven't transitioned yet (SFDC only writes a history row on transition-out).
-- ============================================================================
WITH
IC_EE_ID AS (
  SELECT DISTINCT
      V1.SFDC_EE_ID,
      V1.SFDC_USER_ID,
      MAX(V1.NAME)                AS NAME,
      CASE
        WHEN SUM(CASE WHEN V2.CURRENT_FLAG = TRUE AND V2.PE = V1.PE
                      THEN 1 ELSE 0 END) > 0
        THEN TRUE ELSE FALSE
      END                         AS CURRENT_FLAG,
      V2.PE                       AS CURRENT_PE,
      V2.NAME                     AS CURRENT_NAME,
      V2.SFDC_USER_ID             AS CURRENT_SFDC_USER_ID,
      V2.CXONE_AGENT_ID,
      V2.CXONE_USER_ID,
      V2.STATUS
  FROM BI.SFDC_USERS_GUSTO_EMPLOYEES_VIEW  V1
  JOIN BI.GUSTO_EMPLOYEES                  V2
    ON V2.SFDC_EE_ID = V1.SFDC_EE_ID
   AND V2.CURRENT_FLAG = TRUE
  WHERE V1.SFDC_EE_ID <> 111883
  GROUP BY ALL
),
BO_ATTRS AS (
  SELECT
      SFDC_BENEFIT_ORDER_ID,
      BENEFIT_ORDER_NAME,
      RECORD_TYPE_NAME,
      ORDER_TYPE,
      ZP_COMPANY_ID,
      SFDC_OPPORTUNITY_ID,
      SFDC_BENEFIT_ORDER_OWNER_ID,
      BENEFIT_ORDER_OWNER,
      OWNER_PE_NAME_CURRENT,
      OWNER_PEPE_CURRENT,
      COVERAGE_EFFECTIVE_DT,
      ORIGINAL_EFFECTIVE_DT,
      OPEN_ENROLLMENT_START_DT,
      OPEN_ENROLLMENT_END_DT,
      CREATED_TS,
      FIRST_FULFILLED_TS,
      LAST_FULFILLED_TS,
      FIRST_CANCEL_TS,
      LAST_CANCEL_TS,
      CASE
        WHEN FULFILLED_FLAG = TRUE  THEN FIRST_FULFILLED_TS
        WHEN CANCEL_FLAG = TRUE     THEN FIRST_CANCEL_TS
      END AS FIRST_END_DT,
      ORDER_STATUS,
      ORDER_STATUS_DETAIL,
      CASE
        WHEN ORDER_STATUS_DETAIL IN ('Non-Responsive Employer', '[NP] Non-Responsive Employer')
          OR ORDER_STATUS_DETAIL ILIKE '%non-responsive%'
        THEN 'Non-responsive ER'
        WHEN ORDER_STATUS_DETAIL IN ('Participation: Medical Participation Not Met',
             '[NP+R] Participation: Medical Participation Not Met', 'Participation - 0 enrollees')
          OR ORDER_STATUS_DETAIL ILIKE '%participation%'
        THEN 'Participation Issue'
        WHEN ORDER_STATUS_DETAIL IN ('Ineligible: Company not authorized in state',
             'Ineligible: Not enough EEs in state', 'Ineligible: Owner only',
             'Ineligible: Insufficient Payroll', 'Ineligible: No workers'' compensation',
             'Benefit Application Dismissed', '[NP] Ineligible: No eligible employees',
             '[NP+R] Denied', '[NP] Ineligible: Husband/Wife Only',
             'Ineligible: No eligible employees', 'Existing Group Coverage/BOR')
          OR ORDER_STATUS_DETAIL ILIKE '%ineligible%'
        THEN 'Group is ineligible'
        WHEN ORDER_STATUS_DETAIL IN ('Post-Signature Cancel: Did Not Become Gusto Customer',
             'Post-Signature Cancel: Too Expensive',
             '[NP+R] Post-Signature Cancel: No Longer Interested',
             '[NP] Post-Signature Cancel: Too Expensive')
          OR ORDER_STATUS_DETAIL ILIKE '%Post-Signature Cancel%'
        THEN 'Post-Signature Cancel'
        WHEN ORDER_STATUS_DETAIL ILIKE '%Other%'
        THEN 'Ambiguous - Other'
        ELSE 'Null'
      END AS CANCELLATION_CAUSE_CATEGORY,
      CANCEL_FLAG,
      CLOSED_FLAG,
      FULFILLED_FLAG,
      DIFOT_FLAG,
      REVISED_DIFOT_FLAG,
      MEDICAL_REVISED_DIFOT_FLAG,
      SPECIAL_ENROLLMENT_FLAG,
      PUSH_FLAG,
      FUNDING_TYPE,
      MEDDICAL_CARRIER_INFORMATION_STATE
  FROM BI_REPORTING.BENEFIT_ORDERS
  WHERE (
      CONVERT_TIMEZONE('UTC', 'America/Denver',
        CASE
          WHEN FULFILLED_FLAG = TRUE  THEN FIRST_FULFILLED_TS
          WHEN CANCEL_FLAG = TRUE     THEN FIRST_CANCEL_TS
        END)
        BETWEEN '{{Date Range Start}}'::TIMESTAMP AND '{{Date Range End}}'::TIMESTAMP
      OR CONVERT_TIMEZONE('UTC', 'America/Denver', CREATED_TS)
        BETWEEN '{{Date Range Start}}'::TIMESTAMP AND '{{Date Range End}}'::TIMESTAMP
    )
    AND RECORD_TYPE_NAME = 'Benefits BYB'
),
HIST_BASE AS (
  -- Real completed status transitions from the status_change_history table.
  -- FROM_STATUS = the status the order transitioned OUT OF; DURATION_IN_MINS = how long it sat there.
  SELECT
      H.SFDC_OBJECT_ID,
      H.RECORD_TYPE,
      -- v7.1: canonicalize FROM_STATUS casing so PIVOTED doesn't fragment on
      -- 'Plans confirmed' vs 'Plans Confirmed' etc. Keep the winning casing consistent
      -- with what the DB currently shows in the STATUS column ('Plans Confirmed', 'Fulfillment prep').
      CASE
        WHEN H.FROM_STATUS IN ('Plans confirmed','Plans Confirmed') THEN 'Plans Confirmed'
        WHEN H.FROM_STATUS IN ('Fulfillment Prep','Fulfillment prep') THEN 'Fulfillment prep'
        ELSE H.FROM_STATUS
      END AS STATUS_NAME,
      H.START_TIME,
      COALESCE(H.END_TIME, CURRENT_DATE) AS END_TIME,
      COALESCE(H.DURATION_IN_MINS, 0)  AS DURATION_IN_MINS
  FROM BI.BENEFIT_ORDER_STATUS_CHANGE_HISTORY  H
  INNER JOIN BO_ATTRS                          A
    ON H.SFDC_OBJECT_ID = A.SFDC_BENEFIT_ORDER_ID
  WHERE H.FROM_STATUS IN (
          -- Transition (both casings; canonicalized above)
          'Ready for Implementing Plans','Plans confirmed','Plans Confirmed',
          'OE Verification/Checking Participation',
          'OE Submission','Fulfillment Prep','Fulfillment prep',
          -- Ready Intro + Implementation
          'Ready for Intro','Implementing Plans',
          -- Customer Facing (v7.1: added OE Prep, Pending ER Signature, OE Extended)
          'Collecting Documents','Plan Review Sent','Plan & enrollment review sent','OE','Balance Collection',
          'OE Prep','Pending ER Signature','OE Extended',
          -- Blocked bucket (v7.1 new)
          'Blocked','With Sales','With Advising'
        )
),
-- v7.3 (2026-07-03): synthetic "in-progress" stint for each open order's current status.
-- SFDC only writes a history row when a status ENDS, so an order still sitting in Collecting
-- Documents right now would have zero recorded days there — bucket totals + SLA_MET would miss
-- the current stint. We manufacture one row per open order that carries duration from "last
-- transition end (or CREATED_TS)" → NOW so the downstream STINTS → PIVOTED math picks it up naturally.
-- Only fires when ORDER_STATUS is one of our tracked statuses (same list as HIST_BASE FROM_STATUS).
LAST_HIST_END AS (
  SELECT H.SFDC_OBJECT_ID,
         MAX(H.END_TIME) AS MAX_END
  FROM BI.BENEFIT_ORDER_STATUS_CHANGE_HISTORY H
  WHERE H.STATUS IS NOT NULL
    AND H.END_TIME IS NOT NULL
  GROUP BY H.SFDC_OBJECT_ID
),
CURRENT_STATUS_SYNTH AS (
  SELECT
      A.SFDC_BENEFIT_ORDER_ID AS SFDC_OBJECT_ID,
      'Benefits BYB' AS RECORD_TYPE,
      -- Same canonicalization as HIST_BASE so downstream sees a single casing per status.
      CASE
        WHEN A.ORDER_STATUS IN ('Plans confirmed','Plans Confirmed') THEN 'Plans Confirmed'
        WHEN A.ORDER_STATUS IN ('Fulfillment Prep','Fulfillment prep') THEN 'Fulfillment prep'
        ELSE A.ORDER_STATUS
      END AS STATUS_NAME,
      COALESCE(L.MAX_END, A.CREATED_TS) AS START_TIME,
      CURRENT_TIMESTAMP()               AS END_TIME,
      GREATEST(
        DATEDIFF('MINUTE', COALESCE(L.MAX_END, A.CREATED_TS), CURRENT_TIMESTAMP()),
        0
      ) AS DURATION_IN_MINS
  FROM BO_ATTRS A
  LEFT JOIN LAST_HIST_END L ON L.SFDC_OBJECT_ID = A.SFDC_BENEFIT_ORDER_ID
  WHERE A.CANCEL_FLAG = FALSE
    AND A.FULFILLED_FLAG = FALSE
    AND A.ORDER_STATUS IN (
      -- Same tracked-status list as HIST_BASE FROM_STATUS (both casings kept for safety;
      -- canonicalized above). Statuses not in this list yield no synthetic row → chip shows —.
      'Ready for Implementing Plans','Plans confirmed','Plans Confirmed',
      'OE Verification/Checking Participation',
      'OE Submission','Fulfillment Prep','Fulfillment prep',
      'Ready for Intro','Implementing Plans',
      'Collecting Documents','Plan Review Sent','Plan & enrollment review sent','OE','Balance Collection',
      'OE Prep','Pending ER Signature','OE Extended',
      'Blocked','With Sales','With Advising'
    )
),
HIST AS (
  SELECT * FROM HIST_BASE
  UNION ALL
  SELECT * FROM CURRENT_STATUS_SYNTH
),
LAGGED AS (
  SELECT H.*,
         LAG(STATUS_NAME) OVER (PARTITION BY SFDC_OBJECT_ID, RECORD_TYPE ORDER BY START_TIME) AS LAG_STATUS,
         LAG(END_TIME)    OVER (PARTITION BY SFDC_OBJECT_ID, RECORD_TYPE ORDER BY START_TIME) AS LAG_END
  FROM HIST H
),
FLAGGED AS (
  SELECT *,
         CASE WHEN LAG_STATUS = STATUS_NAME AND ABS(DATEDIFF('DAY', LAG_END, START_TIME)) <= 1
              THEN 0 ELSE 1 END AS IS_NEW_GROUP
  FROM LAGGED
),
GROUPED AS (
  SELECT *,
         SUM(IS_NEW_GROUP) OVER (PARTITION BY SFDC_OBJECT_ID, RECORD_TYPE ORDER BY START_TIME ROWS UNBOUNDED PRECEDING) AS GRP
  FROM FLAGGED
),
STINTS AS (
  SELECT SFDC_OBJECT_ID, RECORD_TYPE, STATUS_NAME,
         MIN(START_TIME) AS STINT_START, MAX(END_TIME) AS STINT_END,
         SUM(DURATION_IN_MINS) AS STINT_MINUTES,
         ROUND(SUM(DURATION_IN_MINS)::FLOAT / 1440, 3) AS STINT_DAYS
  FROM GROUPED
  GROUP BY SFDC_OBJECT_ID, RECORD_TYPE, STATUS_NAME, GRP
  HAVING SUM(DURATION_IN_MINS) > 0
),
STINTS_TARGETS AS (
  SELECT S.*,
      CASE
        WHEN STATUS_NAME IN ('Ready for Implementing Plans','Plans Confirmed','OE Verification/Checking Participation','OE Submission','Fulfillment prep') THEN 'Transition'
        WHEN STATUS_NAME = 'Ready for Intro' THEN 'Ready for Intro'
        WHEN STATUS_NAME = 'Implementing Plans' THEN 'Implementation'
        WHEN STATUS_NAME IN ('Collecting Documents','Plan Review Sent','Plan & enrollment review sent','OE','Balance Collection','OE Prep','Pending ER Signature','OE Extended') THEN 'Customer Facing'
        WHEN STATUS_NAME IN ('Blocked','With Sales','With Advising') THEN 'Blocked'
      END AS STATUS_BUCKET,
      CASE
        WHEN STATUS_NAME IN ('Ready for Implementing Plans','Plans Confirmed','OE Verification/Checking Participation','OE Submission','Fulfillment prep') THEN 2
        WHEN STATUS_NAME = 'Ready for Intro' THEN 3
        WHEN STATUS_NAME = 'Implementing Plans' AND A.ORDER_TYPE = 'New to BYB - No OE' THEN 10
        WHEN STATUS_NAME = 'Implementing Plans' THEN 5
        WHEN STATUS_NAME = 'Collecting Documents' THEN 10
        WHEN STATUS_NAME IN ('Plan Review Sent','Plan & enrollment review sent','OE','Balance Collection','OE Prep','Pending ER Signature','OE Extended') THEN 5
        -- v7.2 (2026-07-02): Blocked bucket target 30d → 15d, promoted to 3-state coloring
        -- (now participates in the primary "at risk or breached (bucket)" KPI)
        WHEN STATUS_NAME IN ('Blocked','With Sales','With Advising') THEN 15
      END AS TARGET_SLA_DAYS
  FROM STINTS S
  INNER JOIN BO_ATTRS A ON S.SFDC_OBJECT_ID = A.SFDC_BENEFIT_ORDER_ID
),
BO_STATUS AS (
  SELECT SFDC_OBJECT_ID, RECORD_TYPE, STATUS_NAME, STATUS_BUCKET, TARGET_SLA_DAYS,
         SUM(STINT_DAYS) AS TOTAL_DAYS, COUNT(*) AS STINT_COUNT,
         CASE WHEN SUM(STINT_DAYS) <= TARGET_SLA_DAYS THEN 1 ELSE 0 END AS SLA_MET
  FROM STINTS_TARGETS
  GROUP BY SFDC_OBJECT_ID, RECORD_TYPE, STATUS_NAME, STATUS_BUCKET, TARGET_SLA_DAYS
),
PIVOTED AS (
  SELECT SFDC_OBJECT_ID, RECORD_TYPE,
      MAX(CASE WHEN STATUS_NAME = 'Ready for Implementing Plans' THEN TOTAL_DAYS  END) AS READY_IMPL_PLANS_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'Ready for Implementing Plans' THEN STINT_COUNT END) AS READY_IMPL_PLANS_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'Ready for Implementing Plans' THEN SLA_MET     END) AS READY_IMPL_PLANS_SLA_MET,
      MAX(CASE WHEN STATUS_NAME = 'Plans Confirmed' THEN TOTAL_DAYS  END) AS PLANS_CONFIRMED_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'Plans Confirmed' THEN STINT_COUNT END) AS PLANS_CONFIRMED_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'Plans Confirmed' THEN SLA_MET     END) AS PLANS_CONFIRMED_SLA_MET,
      MAX(CASE WHEN STATUS_NAME = 'OE Verification/Checking Participation' THEN TOTAL_DAYS  END) AS OE_VERIF_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'OE Verification/Checking Participation' THEN STINT_COUNT END) AS OE_VERIF_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'OE Verification/Checking Participation' THEN SLA_MET     END) AS OE_VERIF_SLA_MET,
      MAX(CASE WHEN STATUS_NAME = 'OE Submission' THEN TOTAL_DAYS  END) AS OE_SUBMISSION_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'OE Submission' THEN STINT_COUNT END) AS OE_SUBMISSION_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'OE Submission' THEN SLA_MET     END) AS OE_SUBMISSION_SLA_MET,
      MAX(CASE WHEN STATUS_NAME = 'Fulfillment prep' THEN TOTAL_DAYS  END) AS FULFILLMENT_PREP_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'Fulfillment prep' THEN STINT_COUNT END) AS FULFILLMENT_PREP_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'Fulfillment prep' THEN SLA_MET     END) AS FULFILLMENT_PREP_SLA_MET,
      MAX(CASE WHEN STATUS_NAME = 'Ready for Intro' THEN TOTAL_DAYS  END) AS READY_INTRO_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'Ready for Intro' THEN STINT_COUNT END) AS READY_INTRO_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'Ready for Intro' THEN SLA_MET     END) AS READY_INTRO_SLA_MET,
      MAX(CASE WHEN STATUS_NAME = 'Implementing Plans' THEN TOTAL_DAYS  END) AS IMPL_PLANS_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'Implementing Plans' THEN STINT_COUNT END) AS IMPL_PLANS_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'Implementing Plans' THEN SLA_MET     END) AS IMPL_PLANS_SLA_MET,
      MAX(CASE WHEN STATUS_NAME = 'Collecting Documents' THEN TOTAL_DAYS  END) AS COLLECT_DOCS_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'Collecting Documents' THEN STINT_COUNT END) AS COLLECT_DOCS_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'Collecting Documents' THEN SLA_MET     END) AS COLLECT_DOCS_SLA_MET,
      MAX(CASE WHEN STATUS_NAME = 'Plan Review Sent' THEN TOTAL_DAYS  END) AS PLAN_REVIEW_SENT_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'Plan Review Sent' THEN STINT_COUNT END) AS PLAN_REVIEW_SENT_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'Plan Review Sent' THEN SLA_MET     END) AS PLAN_REVIEW_SENT_SLA_MET,
      MAX(CASE WHEN STATUS_NAME = 'Plan & enrollment review sent' THEN TOTAL_DAYS  END) AS PLAN_ENROLL_REVIEW_SENT_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'Plan & enrollment review sent' THEN STINT_COUNT END) AS PLAN_ENROLL_REVIEW_SENT_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'Plan & enrollment review sent' THEN SLA_MET     END) AS PLAN_ENROLL_REVIEW_SENT_SLA_MET,
      MAX(CASE WHEN STATUS_NAME = 'OE' THEN TOTAL_DAYS  END) AS OE_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'OE' THEN STINT_COUNT END) AS OE_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'OE' THEN SLA_MET     END) AS OE_SLA_MET,
      MAX(CASE WHEN STATUS_NAME = 'Balance Collection' THEN TOTAL_DAYS  END) AS BALANCE_COLLECTION_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'Balance Collection' THEN STINT_COUNT END) AS BALANCE_COLLECTION_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'Balance Collection' THEN SLA_MET     END) AS BALANCE_COLLECTION_SLA_MET,
      -- v7.1 new: Cust Facing additions
      MAX(CASE WHEN STATUS_NAME = 'OE Prep' THEN TOTAL_DAYS  END) AS OE_PREP_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'OE Prep' THEN STINT_COUNT END) AS OE_PREP_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'OE Prep' THEN SLA_MET     END) AS OE_PREP_SLA_MET,
      MAX(CASE WHEN STATUS_NAME = 'Pending ER Signature' THEN TOTAL_DAYS  END) AS PENDING_ER_SIG_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'Pending ER Signature' THEN STINT_COUNT END) AS PENDING_ER_SIG_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'Pending ER Signature' THEN SLA_MET     END) AS PENDING_ER_SIG_SLA_MET,
      MAX(CASE WHEN STATUS_NAME = 'OE Extended' THEN TOTAL_DAYS  END) AS OE_EXTENDED_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'OE Extended' THEN STINT_COUNT END) AS OE_EXTENDED_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'OE Extended' THEN SLA_MET     END) AS OE_EXTENDED_SLA_MET,
      -- v7.1 new: Blocked bucket sub-status columns
      MAX(CASE WHEN STATUS_NAME = 'Blocked' THEN TOTAL_DAYS  END) AS BLOCKED_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'Blocked' THEN STINT_COUNT END) AS BLOCKED_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'Blocked' THEN SLA_MET     END) AS BLOCKED_SLA_MET_SUB,
      MAX(CASE WHEN STATUS_NAME = 'With Sales' THEN TOTAL_DAYS  END) AS WITH_SALES_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'With Sales' THEN STINT_COUNT END) AS WITH_SALES_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'With Sales' THEN SLA_MET     END) AS WITH_SALES_SLA_MET,
      MAX(CASE WHEN STATUS_NAME = 'With Advising' THEN TOTAL_DAYS  END) AS WITH_ADVISING_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'With Advising' THEN STINT_COUNT END) AS WITH_ADVISING_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'With Advising' THEN SLA_MET     END) AS WITH_ADVISING_SLA_MET,
      COALESCE(MAX(CASE WHEN STATUS_NAME = 'Ready for Implementing Plans' THEN TOTAL_DAYS END), 0)
      + COALESCE(MAX(CASE WHEN STATUS_NAME = 'Plans Confirmed' THEN TOTAL_DAYS END), 0)
      + COALESCE(MAX(CASE WHEN STATUS_NAME = 'OE Verification/Checking Participation' THEN TOTAL_DAYS END), 0)
      + COALESCE(MAX(CASE WHEN STATUS_NAME = 'OE Submission' THEN TOTAL_DAYS END), 0)
      + COALESCE(MAX(CASE WHEN STATUS_NAME = 'Fulfillment prep' THEN TOTAL_DAYS END), 0) AS TRANSITION_TOTAL_DAYS,
      COALESCE(MAX(CASE WHEN STATUS_NAME = 'Ready for Intro' THEN TOTAL_DAYS END), 0) AS READY_INTRO_TOTAL_DAYS,
      COALESCE(MAX(CASE WHEN STATUS_NAME = 'Implementing Plans' THEN TOTAL_DAYS END), 0) AS IMPLEMENTATION_TOTAL_DAYS,
      LEAST(
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'Ready for Implementing Plans' THEN SLA_MET END), 1),
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'Plans Confirmed' THEN SLA_MET END), 1),
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'OE Verification/Checking Participation' THEN SLA_MET END), 1),
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'OE Submission' THEN SLA_MET END), 1),
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'Fulfillment prep' THEN SLA_MET END), 1)
      ) AS TRANSITION_SLA_MET,
      COALESCE(MAX(CASE WHEN STATUS_NAME = 'Ready for Intro'    THEN SLA_MET END), 1) AS READY_INTRO_SLA_MET_BUCKET,
      COALESCE(MAX(CASE WHEN STATUS_NAME = 'Implementing Plans' THEN SLA_MET END), 1) AS IMPLEMENTATION_SLA_MET_BUCKET,
      -- Cust Facing bucket total: v7.1 added OE Prep, Pending ER Sig, OE Extended
      COALESCE(MAX(CASE WHEN STATUS_NAME = 'Collecting Documents' THEN TOTAL_DAYS END), 0)
      + COALESCE(MAX(CASE WHEN STATUS_NAME = 'Plan Review Sent' THEN TOTAL_DAYS END), 0)
      + COALESCE(MAX(CASE WHEN STATUS_NAME = 'Plan & enrollment review sent' THEN TOTAL_DAYS END), 0)
      + COALESCE(MAX(CASE WHEN STATUS_NAME = 'OE' THEN TOTAL_DAYS END), 0)
      + COALESCE(MAX(CASE WHEN STATUS_NAME = 'Balance Collection' THEN TOTAL_DAYS END), 0)
      + COALESCE(MAX(CASE WHEN STATUS_NAME = 'OE Prep' THEN TOTAL_DAYS END), 0)
      + COALESCE(MAX(CASE WHEN STATUS_NAME = 'Pending ER Signature' THEN TOTAL_DAYS END), 0)
      + COALESCE(MAX(CASE WHEN STATUS_NAME = 'OE Extended' THEN TOTAL_DAYS END), 0) AS CUST_FACING_TOTAL_DAYS,
      LEAST(
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'Collecting Documents' THEN SLA_MET END), 1),
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'Plan Review Sent' THEN SLA_MET END), 1),
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'Plan & enrollment review sent' THEN SLA_MET END), 1),
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'OE' THEN SLA_MET END), 1),
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'Balance Collection' THEN SLA_MET END), 1),
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'OE Prep' THEN SLA_MET END), 1),
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'Pending ER Signature' THEN SLA_MET END), 1),
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'OE Extended' THEN SLA_MET END), 1)
      ) AS CUST_FACING_SLA_MET,
      -- Blocked bucket total (v7.1 new): Blocked + With Sales + With Advising; 30d soft target
      COALESCE(MAX(CASE WHEN STATUS_NAME = 'Blocked' THEN TOTAL_DAYS END), 0)
      + COALESCE(MAX(CASE WHEN STATUS_NAME = 'With Sales' THEN TOTAL_DAYS END), 0)
      + COALESCE(MAX(CASE WHEN STATUS_NAME = 'With Advising' THEN TOTAL_DAYS END), 0) AS BLOCKED_TOTAL_DAYS,
      LEAST(
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'Blocked' THEN SLA_MET END), 1),
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'With Sales' THEN SLA_MET END), 1),
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'With Advising' THEN SLA_MET END), 1)
      ) AS BLOCKED_SLA_MET
  FROM BO_STATUS
  GROUP BY SFDC_OBJECT_ID, RECORD_TYPE
),
-- Current status per order — derived from the STATUS column (denormalized; same across all rows
-- for one order). For open orders this is their current in-progress status; for closed orders it's
-- "Canceled"/"Fulfilled"/etc. DAYS_IN_CURRENT_STATUS = days since the order entered that status
-- (i.e., since the MAX(END_TIME) across the order's history — the last transition).
CURRENT_STATUS AS (
  SELECT H.SFDC_OBJECT_ID,
         MAX(H.STATUS) AS CURRENT_STATUS_NAME,
         DATEDIFF('DAY', MAX(H.END_TIME), CURRENT_DATE)::FLOAT AS DAYS_IN_CURRENT_STATUS
  FROM BI.BENEFIT_ORDER_STATUS_CHANGE_HISTORY H
  INNER JOIN BO_ATTRS A ON H.SFDC_OBJECT_ID = A.SFDC_BENEFIT_ORDER_ID
  WHERE H.STATUS IS NOT NULL
  GROUP BY H.SFDC_OBJECT_ID
),
-- v7.4/v8.4 (2026-07-03): OTHER bucket — untracked, non-terminal status time (e.g. Closed Admin).
-- Catch-all so bucket chips reconcile to age. 15d suggested time. Closed = history; open = synth stint.
OTHER_HIST AS (
  SELECT H.SFDC_OBJECT_ID AS OID, SUM(COALESCE(H.DURATION_IN_MINS,0))/1440.0 AS OTHER_DAYS
  FROM BI.BENEFIT_ORDER_STATUS_CHANGE_HISTORY H
  INNER JOIN BO_ATTRS A ON H.SFDC_OBJECT_ID = A.SFDC_BENEFIT_ORDER_ID
  WHERE H.FROM_STATUS IS NOT NULL
    AND H.FROM_STATUS NOT IN ('Ready for Implementing Plans','Plans confirmed','Plans Confirmed','OE Verification/Checking Participation','OE Submission','Fulfillment Prep','Fulfillment prep','Ready for Intro','Implementing Plans','Collecting Documents','Plan Review Sent','Plan & enrollment review sent','OE','Balance Collection','OE Prep','Pending ER Signature','OE Extended','Blocked','With Sales','With Advising')
    AND NOT (H.FROM_STATUS ILIKE '%fulfill%' OR H.FROM_STATUS ILIKE '%cancel%' OR H.FROM_STATUS IN ('Closed Won','Closed Lost'))
  GROUP BY 1
),
OTHER_SYNTH AS (
  SELECT A.SFDC_BENEFIT_ORDER_ID AS OID,
         GREATEST(DATEDIFF('MINUTE', COALESCE(L.MAX_END, A.CREATED_TS), CURRENT_TIMESTAMP()),0)/1440.0 AS OTHER_DAYS
  FROM BO_ATTRS A
  LEFT JOIN LAST_HIST_END L ON L.SFDC_OBJECT_ID = A.SFDC_BENEFIT_ORDER_ID
  WHERE A.CANCEL_FLAG = FALSE AND A.FULFILLED_FLAG = FALSE
    AND A.ORDER_STATUS IS NOT NULL
    AND A.ORDER_STATUS NOT IN ('Ready for Implementing Plans','Plans confirmed','Plans Confirmed','OE Verification/Checking Participation','OE Submission','Fulfillment Prep','Fulfillment prep','Ready for Intro','Implementing Plans','Collecting Documents','Plan Review Sent','Plan & enrollment review sent','OE','Balance Collection','OE Prep','Pending ER Signature','OE Extended','Blocked','With Sales','With Advising')
    AND NOT (A.ORDER_STATUS ILIKE '%fulfill%' OR A.ORDER_STATUS ILIKE '%cancel%' OR A.ORDER_STATUS IN ('Closed Won','Closed Lost'))
),
OTHER_TOTAL AS (
  SELECT OID, SUM(OTHER_DAYS) AS OTHER_DAYS
  FROM (SELECT OID, OTHER_DAYS FROM OTHER_HIST UNION ALL SELECT OID, OTHER_DAYS FROM OTHER_SYNTH) U
  GROUP BY 1
)
SELECT
    A.SFDC_BENEFIT_ORDER_ID, A.BENEFIT_ORDER_NAME, A.RECORD_TYPE_NAME, A.ORDER_TYPE,
    CASE WHEN A.SFDC_BENEFIT_ORDER_ID IS NOT NULL
         THEN 'https://gusto.lightning.force.com/lightning/r/Benefit_Order__c/'
              || A.SFDC_BENEFIT_ORDER_ID || '/view' END AS BO_LINK,
    CASE WHEN A.ZP_COMPANY_ID IS NOT NULL
         THEN CONCAT('https://hippo.gusto.com/companies/', A.ZP_COMPANY_ID) END AS HIPPO_LINK,
    A.ZP_COMPANY_ID,
    A.BENEFIT_ORDER_OWNER, A.SFDC_BENEFIT_ORDER_OWNER_ID,
    A.OWNER_PE_NAME_CURRENT, A.OWNER_PEPE_CURRENT, EE.CURRENT_SFDC_USER_ID,
    A.COVERAGE_EFFECTIVE_DT,
    DATE_TRUNC('MONTH', A.COVERAGE_EFFECTIVE_DT)::DATE AS COHORT_MONTH,
    A.ORIGINAL_EFFECTIVE_DT, A.OPEN_ENROLLMENT_START_DT, A.OPEN_ENROLLMENT_END_DT,
    CONVERT_TIMEZONE('UTC', 'America/Denver', A.CREATED_TS)         AS CREATED_TS_MT,
    CONVERT_TIMEZONE('UTC', 'America/Denver', A.FIRST_END_DT)      AS FIRST_END_DT_MT,
    DATE_TRUNC('MONTH', A.FIRST_END_DT)::DATE                      AS FIRST_END_MONTH,
    CONVERT_TIMEZONE('UTC', 'America/Denver', A.FIRST_FULFILLED_TS) AS FIRST_FULFILLED_TS_MT,
    CONVERT_TIMEZONE('UTC', 'America/Denver', A.LAST_FULFILLED_TS)  AS LAST_FULFILLED_TS_MT,
    CONVERT_TIMEZONE('UTC', 'America/Denver', A.FIRST_CANCEL_TS)    AS FIRST_CANCEL_TS_MT,
    CONVERT_TIMEZONE('UTC', 'America/Denver', A.LAST_CANCEL_TS)     AS LAST_CANCEL_TS_MT,
    A.ORDER_STATUS, A.ORDER_STATUS_DETAIL, A.CANCELLATION_CAUSE_CATEGORY,
    A.CANCEL_FLAG, A.CLOSED_FLAG, A.FULFILLED_FLAG,
    CASE WHEN A.FIRST_FULFILLED_TS IS NOT NULL THEN 1 ELSE 0 END AS EVER_FULFILLED,
    CASE WHEN A.FIRST_CANCEL_TS IS NOT NULL THEN 1 ELSE 0 END    AS EVER_CANCELLED,
    A.DIFOT_FLAG, A.REVISED_DIFOT_FLAG, A.MEDICAL_REVISED_DIFOT_FLAG,
    CASE WHEN A.FIRST_FULFILLED_TS IS NOT NULL
           AND DATEDIFF('DAY', A.CREATED_TS, A.FIRST_FULFILLED_TS) <= 30 THEN 1
         WHEN A.FIRST_FULFILLED_TS IS NOT NULL THEN 0 ELSE NULL END AS FULFILLED_IN_30D_MET,
    DATEDIFF('DAY', A.CREATED_TS, A.FIRST_FULFILLED_TS) AS DAYS_CREATED_TO_FIRST_FULFILLED,
    DATEDIFF('DAY', A.FIRST_FULFILLED_TS, A.LAST_FULFILLED_TS) AS DAYS_FIRST_TO_LAST_FULFILLED,
    DATEDIFF('DAY', A.FIRST_CANCEL_TS, A.LAST_CANCEL_TS) AS DAYS_FIRST_TO_LAST_CANCEL,
    A.SPECIAL_ENROLLMENT_FLAG, A.PUSH_FLAG, A.FUNDING_TYPE, A.MEDDICAL_CARRIER_INFORMATION_STATE,
    CASE
      WHEN A.ORDER_TYPE = 'Gusto to BYB - Midyear' THEN 'Fast'
      WHEN A.ORDER_TYPE IN ('Gusto to BYB - Renewal', 'New to BYB - No OE') THEN 'Standard'
      WHEN A.ORDER_TYPE IN ('BYB Renewal', 'New to BYB - OE') THEN 'Complex'
      ELSE 'N/A'
    END AS ORDER_TYPE_TIER,
    P.READY_IMPL_PLANS_DAYS,  P.READY_IMPL_PLANS_STINTS,  P.READY_IMPL_PLANS_SLA_MET,
    P.PLANS_CONFIRMED_DAYS,   P.PLANS_CONFIRMED_STINTS,   P.PLANS_CONFIRMED_SLA_MET,
    P.OE_VERIF_DAYS,          P.OE_VERIF_STINTS,          P.OE_VERIF_SLA_MET,
    P.OE_SUBMISSION_DAYS,     P.OE_SUBMISSION_STINTS,     P.OE_SUBMISSION_SLA_MET,
    P.FULFILLMENT_PREP_DAYS,  P.FULFILLMENT_PREP_STINTS,  P.FULFILLMENT_PREP_SLA_MET,
    P.READY_INTRO_DAYS,       P.READY_INTRO_STINTS,       P.READY_INTRO_SLA_MET,
    P.IMPL_PLANS_DAYS,        P.IMPL_PLANS_STINTS,        P.IMPL_PLANS_SLA_MET,
    P.TRANSITION_TOTAL_DAYS,       P.TRANSITION_SLA_MET,
    P.READY_INTRO_TOTAL_DAYS,      P.READY_INTRO_SLA_MET_BUCKET,
    P.IMPLEMENTATION_TOTAL_DAYS,   P.IMPLEMENTATION_SLA_MET_BUCKET,
    P.COLLECT_DOCS_DAYS,            P.COLLECT_DOCS_STINTS,            P.COLLECT_DOCS_SLA_MET,
    P.PLAN_REVIEW_SENT_DAYS,        P.PLAN_REVIEW_SENT_STINTS,        P.PLAN_REVIEW_SENT_SLA_MET,
    P.PLAN_ENROLL_REVIEW_SENT_DAYS, P.PLAN_ENROLL_REVIEW_SENT_STINTS, P.PLAN_ENROLL_REVIEW_SENT_SLA_MET,
    P.OE_DAYS,                      P.OE_STINTS,                      P.OE_SLA_MET,
    P.BALANCE_COLLECTION_DAYS,      P.BALANCE_COLLECTION_STINTS,      P.BALANCE_COLLECTION_SLA_MET,
    P.OE_PREP_DAYS,                 P.OE_PREP_STINTS,                 P.OE_PREP_SLA_MET,
    P.PENDING_ER_SIG_DAYS,          P.PENDING_ER_SIG_STINTS,          P.PENDING_ER_SIG_SLA_MET,
    P.OE_EXTENDED_DAYS,             P.OE_EXTENDED_STINTS,             P.OE_EXTENDED_SLA_MET,
    P.CUST_FACING_TOTAL_DAYS,       P.CUST_FACING_SLA_MET,
    -- v7.1 new: Blocked bucket sub-status + roll-up columns
    P.BLOCKED_DAYS,                 P.BLOCKED_STINTS,                 P.BLOCKED_SLA_MET_SUB,
    P.WITH_SALES_DAYS,              P.WITH_SALES_STINTS,              P.WITH_SALES_SLA_MET,
    P.WITH_ADVISING_DAYS,           P.WITH_ADVISING_STINTS,           P.WITH_ADVISING_SLA_MET,
    P.BLOCKED_TOTAL_DAYS,           P.BLOCKED_SLA_MET,
    -- 2026-07-15: E2E SLA is now a single flat 60d target for ALL BYB order types (retired Fast/Standard/Complex tiers).
    60 AS E2E_SLA_TARGET,
    CASE
      WHEN A.FIRST_FULFILLED_TS IS NOT NULL
       AND DATEDIFF('DAY', A.CREATED_TS, A.FIRST_FULFILLED_TS) <= 60 THEN 1
      WHEN A.FIRST_FULFILLED_TS IS NOT NULL THEN 0
      ELSE NULL
    END AS E2E_SLA_MET,
    CS.CURRENT_STATUS_NAME,
    CS.DAYS_IN_CURRENT_STATUS,
    CASE
      -- Transition sub-statuses (2d each)
      WHEN CS.CURRENT_STATUS_NAME IN ('Ready for Implementing Plans','Plans confirmed','Plans Confirmed','OE Verification/Checking Participation','OE Submission','Fulfillment Prep','Fulfillment prep') THEN 2
      WHEN CS.CURRENT_STATUS_NAME = 'Ready for Intro' THEN 3
      WHEN CS.CURRENT_STATUS_NAME = 'Implementing Plans' AND A.ORDER_TYPE = 'New to BYB - No OE' THEN 10
      WHEN CS.CURRENT_STATUS_NAME = 'Implementing Plans' THEN 5
      WHEN CS.CURRENT_STATUS_NAME = 'Collecting Documents' THEN 10
      -- Cust Facing 5d each (v7.1: added OE Prep, Pending ER Signature, OE Extended)
      WHEN CS.CURRENT_STATUS_NAME IN ('Plan Review Sent','Plan & enrollment review sent','OE','Balance Collection','OE Prep','Pending ER Signature','OE Extended') THEN 5
      -- v7.2: Blocked bucket target 30d → 15d (promoted to 3-state coloring)
      WHEN CS.CURRENT_STATUS_NAME IN ('Blocked','With Sales','With Advising') THEN 15
    END AS CURRENT_STATUS_TARGET_DAYS,
    OPP_FACT.OWN_NAME AS SFDC_OPP_OWNER,
    ROUND(OT.OTHER_DAYS, 3) AS OTHER_TOTAL_DAYS,
    CASE WHEN OT.OTHER_DAYS IS NULL THEN 1 WHEN OT.OTHER_DAYS <= 15 THEN 1 ELSE 0 END AS OTHER_SLA_MET
FROM BO_ATTRS A
LEFT JOIN PIVOTED P ON A.SFDC_BENEFIT_ORDER_ID = P.SFDC_OBJECT_ID
LEFT JOIN CURRENT_STATUS CS ON A.SFDC_BENEFIT_ORDER_ID = CS.SFDC_OBJECT_ID
LEFT JOIN BI.SFDC_OPPORTUNITIES_FACT OPP_FACT ON A.SFDC_OPPORTUNITY_ID = OPP_FACT.OPPORTUNITY_ID
LEFT JOIN (SELECT DISTINCT CURRENT_SFDC_USER_ID FROM IC_EE_ID) EE
  ON A.SFDC_BENEFIT_ORDER_OWNER_ID = EE.CURRENT_SFDC_USER_ID
LEFT JOIN OTHER_TOTAL OT ON A.SFDC_BENEFIT_ORDER_ID = OT.OID
ORDER BY CONVERT_TIMEZONE('UTC', 'America/Denver', A.FIRST_END_DT), A.SFDC_BENEFIT_ORDER_ID;
