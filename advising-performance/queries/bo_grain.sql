-- ============================================================================
-- BO-GRAIN SLA DETAIL QUERY — v12 (open BOs now included)
-- ============================================================================
-- Parameters substituted from Redash placeholders:
--   {{Date Range Start}}    → 2024-01-01
--   {{Date Range End}}      → 2026-06-14
--   {{record_type_filter}}  → 'New Plan', 'Renewal'
-- ============================================================================
-- v12 changes vs v11:
--   • Base filter now includes OPEN BOs (fulfilled_flag=FALSE AND cancel_flag=FALSE)
--     with created_ts >= date_start. Same pattern as BO SLA dashboard v7.
--   • Existing closed-BO logic UNCHANGED for backward compat.
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
      BENEFIT_ORDER_OWNER,
      SFDC_BENEFIT_ORDER_OWNER_ID,
      SDFC_LONGEST_BENEFIT_ORDER_OWNER,
      OWNER_PE_NAME_CURRENT,
      OWNER_PEPE_CURRENT,
      NUMBER_OA_ADVOCATES,
      COVERAGE_EFFECTIVE_DT,
      ORIGINAL_EFFECTIVE_DT,
      OPEN_ENROLLMENT_START_DT,
      OPEN_ENROLLMENT_END_DT,
      CREATED_TS,
      FIRST_APPROVED_TS,
      FIRST_FULFILLED_TS,
      LAST_FULFILLED_TS,
      FIRST_PUSH_TS,
      LAST_PUSH_TS,
      FIRST_READY_FOR_SUBMISSION_PREP_TS,
      FIRST_READY_FOR_CONFIRMATION_TS,
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
      MEDDICAL_CARRIER_INFORMATION_STATE,
      TOTAL_IMPLEMENTATION_ADVOCATE_TICKETS,
      TOTAL_ER_OUTREACH_TICKETS,
      TOTAL_UNAVOIDABLE_EXCLUDE_TICKETS,
      TOTAL_BENEFITS_ADVISING_TICKETS,
      TOTAL_NEW_PLAN_SALES_TICKETS
  FROM BI_REPORTING.BENEFIT_ORDERS
  WHERE RECORD_TYPE_NAME IN ('New Plan', 'Renewal')
    AND (
      -- Closed BOs: filter by first fulfilled / first canceled ts in the window
      (
        CONVERT_TIMEZONE('UTC', 'America/Denver',
          CASE
            WHEN FULFILLED_FLAG = TRUE  THEN FIRST_FULFILLED_TS
            WHEN CANCEL_FLAG = TRUE     THEN FIRST_CANCEL_TS
          END)
        BETWEEN '2024-01-01'::TIMESTAMP AND '{{Date Range End}}'::TIMESTAMP
      )
      OR
      -- Open BOs: unfulfilled + uncanceled, created since date_start
      (
        FULFILLED_FLAG = FALSE
        AND CANCEL_FLAG = FALSE
        AND CREATED_TS >= '2024-01-01'::TIMESTAMP
      )
    )
),
HIST AS (
  SELECT
      H.SFDC_OBJECT_ID,
      H.RECORD_TYPE,
      H.FROM_STATUS                     AS STATUS_NAME,
      H.START_TIME,
      COALESCE(H.END_TIME, CURRENT_DATE) AS END_TIME,
      COALESCE(H.DURATION_IN_MINS, 0)  AS DURATION_IN_MINS
  FROM BI.BENEFIT_ORDER_STATUS_CHANGE_HISTORY  H
  INNER JOIN BO_ATTRS                          A
    ON H.SFDC_OBJECT_ID = A.SFDC_BENEFIT_ORDER_ID
  WHERE H.RECORD_TYPE IN ('New Plan', 'Renewal')
    AND H.FROM_STATUS IN (
          'Ready for OE Prep',
          'OE Verification/Checking Participation',
          'ER Outreach Required',
          'Awaiting Routing',
          'Approved',
          'Blocked',
          'With Sales',
          'With Advising',
          'Awaiting ER Response - Pending Item',
          'OE',
          'OE Extended'
        )
),
LAGGED AS (
  SELECT
      H.*,
      LAG(STATUS_NAME) OVER (
        PARTITION BY SFDC_OBJECT_ID, RECORD_TYPE
        ORDER BY START_TIME
      ) AS LAG_STATUS,
      LAG(END_TIME) OVER (
        PARTITION BY SFDC_OBJECT_ID, RECORD_TYPE
        ORDER BY START_TIME
      ) AS LAG_END
  FROM HIST H
),
FLAGGED AS (
  SELECT *,
         CASE
           WHEN LAG_STATUS = STATUS_NAME
            AND ABS(DATEDIFF('DAY', LAG_END, START_TIME)) <= 1
           THEN 0
           ELSE 1
         END AS IS_NEW_GROUP
  FROM LAGGED
),
GROUPED AS (
  SELECT *,
         SUM(IS_NEW_GROUP) OVER (
           PARTITION BY SFDC_OBJECT_ID, RECORD_TYPE
           ORDER BY START_TIME
           ROWS UNBOUNDED PRECEDING
         ) AS GRP
  FROM FLAGGED
),
STINTS AS (
  SELECT
      SFDC_OBJECT_ID,
      RECORD_TYPE,
      STATUS_NAME,
      MIN(START_TIME)                                AS STINT_START,
      MAX(END_TIME)                                  AS STINT_END,
      SUM(DURATION_IN_MINS)                          AS STINT_MINUTES,
      ROUND(SUM(DURATION_IN_MINS)::FLOAT / 1440, 3) AS STINT_DAYS
  FROM GROUPED
  GROUP BY SFDC_OBJECT_ID, RECORD_TYPE, STATUS_NAME, GRP
  HAVING SUM(DURATION_IN_MINS) > 0
),
STINTS_TARGETS AS (
  SELECT
      S.*,
      CASE
        WHEN STATUS_NAME IN ('Blocked', 'With Sales', 'With Advising')
          THEN 'Blocked'
        WHEN STATUS_NAME IN ('Awaiting ER Response - Pending Item', 'OE', 'OE Extended')
          THEN 'Customer Facing'
        ELSE 'With OA'
      END AS STATUS_BUCKET,
      CASE
        WHEN STATUS_NAME = 'Ready for OE Prep'                      THEN 1
        WHEN STATUS_NAME = 'OE Verification/Checking Participation'  THEN 1
        WHEN STATUS_NAME = 'ER Outreach Required'                    THEN 1
        WHEN STATUS_NAME = 'Awaiting Routing'                        THEN 1
        WHEN STATUS_NAME = 'Approved'                                THEN 1
        WHEN STATUS_NAME = 'Blocked'                                 THEN 8
        WHEN STATUS_NAME = 'With Sales'                              THEN 5
        WHEN STATUS_NAME = 'With Advising'                           THEN 5
        WHEN STATUS_NAME = 'Awaiting ER Response - Pending Item'     THEN 2
        WHEN STATUS_NAME = 'OE'                                      THEN 11
        WHEN STATUS_NAME = 'OE Extended'                             THEN 3
      END AS TARGET_SLA_DAYS
  FROM STINTS S
),
BO_STATUS AS (
  SELECT
      SFDC_OBJECT_ID,
      RECORD_TYPE,
      STATUS_NAME,
      STATUS_BUCKET,
      TARGET_SLA_DAYS,
      SUM(STINT_DAYS)  AS TOTAL_DAYS,
      COUNT(*)         AS STINT_COUNT,
      CASE
        WHEN SUM(STINT_DAYS) <= TARGET_SLA_DAYS THEN 1
        ELSE 0
      END              AS SLA_MET
  FROM STINTS_TARGETS
  GROUP BY SFDC_OBJECT_ID, RECORD_TYPE, STATUS_NAME,
           STATUS_BUCKET, TARGET_SLA_DAYS
),
PIVOTED AS (
  SELECT
      SFDC_OBJECT_ID,
      RECORD_TYPE,
      MAX(CASE WHEN STATUS_NAME = 'Ready for OE Prep'                      THEN TOTAL_DAYS  END) AS SLA_READY_OE_PREP_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'Ready for OE Prep'                      THEN STINT_COUNT END) AS SLA_READY_OE_PREP_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'Ready for OE Prep'                      THEN SLA_MET     END) AS SLA_READY_OE_PREP_MET,
      MAX(CASE WHEN STATUS_NAME = 'OE Verification/Checking Participation'  THEN TOTAL_DAYS  END) AS SLA_OE_VERIF_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'OE Verification/Checking Participation'  THEN STINT_COUNT END) AS SLA_OE_VERIF_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'OE Verification/Checking Participation'  THEN SLA_MET     END) AS SLA_OE_VERIF_MET,
      MAX(CASE WHEN STATUS_NAME = 'ER Outreach Required'                    THEN TOTAL_DAYS  END) AS SLA_ER_OUTREACH_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'ER Outreach Required'                    THEN STINT_COUNT END) AS SLA_ER_OUTREACH_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'ER Outreach Required'                    THEN SLA_MET     END) AS SLA_ER_OUTREACH_MET,
      MAX(CASE WHEN STATUS_NAME = 'Awaiting Routing'                        THEN TOTAL_DAYS  END) AS SLA_AWAIT_ROUTING_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'Awaiting Routing'                        THEN STINT_COUNT END) AS SLA_AWAIT_ROUTING_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'Awaiting Routing'                        THEN SLA_MET     END) AS SLA_AWAIT_ROUTING_MET,
      MAX(CASE WHEN STATUS_NAME = 'Approved'                                THEN TOTAL_DAYS  END) AS SLA_APPROVED_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'Approved'                                THEN STINT_COUNT END) AS SLA_APPROVED_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'Approved'                                THEN SLA_MET     END) AS SLA_APPROVED_MET,
      MAX(CASE WHEN STATUS_NAME = 'Blocked'                                 THEN TOTAL_DAYS  END) AS SLA_BLOCKED_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'Blocked'                                 THEN STINT_COUNT END) AS SLA_BLOCKED_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'Blocked'                                 THEN SLA_MET     END) AS SLA_BLOCKED_MET,
      MAX(CASE WHEN STATUS_NAME = 'With Sales'                              THEN TOTAL_DAYS  END) AS SLA_WITH_SALES_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'With Sales'                              THEN STINT_COUNT END) AS SLA_WITH_SALES_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'With Sales'                              THEN SLA_MET     END) AS SLA_WITH_SALES_MET,
      MAX(CASE WHEN STATUS_NAME = 'With Advising'                           THEN TOTAL_DAYS  END) AS SLA_WITH_ADVISING_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'With Advising'                           THEN STINT_COUNT END) AS SLA_WITH_ADVISING_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'With Advising'                           THEN SLA_MET     END) AS SLA_WITH_ADVISING_MET,
      MAX(CASE WHEN STATUS_NAME = 'Awaiting ER Response - Pending Item'     THEN TOTAL_DAYS  END) AS SLA_ER_RESPONSE_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'Awaiting ER Response - Pending Item'     THEN STINT_COUNT END) AS SLA_ER_RESPONSE_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'Awaiting ER Response - Pending Item'     THEN SLA_MET     END) AS SLA_ER_RESPONSE_MET,
      MAX(CASE WHEN STATUS_NAME = 'OE'                                      THEN TOTAL_DAYS  END) AS SLA_OE_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'OE'                                      THEN STINT_COUNT END) AS SLA_OE_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'OE'                                      THEN SLA_MET     END) AS SLA_OE_MET,
      MAX(CASE WHEN STATUS_NAME = 'OE Extended'                             THEN TOTAL_DAYS  END) AS SLA_OE_EXTENDED_DAYS,
      MAX(CASE WHEN STATUS_NAME = 'OE Extended'                             THEN STINT_COUNT END) AS SLA_OE_EXTENDED_STINTS,
      MAX(CASE WHEN STATUS_NAME = 'OE Extended'                             THEN SLA_MET     END) AS SLA_OE_EXTENDED_MET,
      COALESCE(MAX(CASE WHEN STATUS_NAME = 'Ready for OE Prep'                      THEN TOTAL_DAYS END), 0)
      + COALESCE(MAX(CASE WHEN STATUS_NAME = 'OE Verification/Checking Participation' THEN TOTAL_DAYS END), 0)
      + COALESCE(MAX(CASE WHEN STATUS_NAME = 'ER Outreach Required'                  THEN TOTAL_DAYS END), 0)
      + COALESCE(MAX(CASE WHEN STATUS_NAME = 'Awaiting Routing'                      THEN TOTAL_DAYS END), 0)
      + COALESCE(MAX(CASE WHEN STATUS_NAME = 'Approved'                              THEN TOTAL_DAYS END), 0)
        AS SLA_BUCKET_WITH_OA_DAYS,
      COALESCE(MAX(CASE WHEN STATUS_NAME = 'Blocked'        THEN TOTAL_DAYS END), 0)
      + COALESCE(MAX(CASE WHEN STATUS_NAME = 'With Sales'    THEN TOTAL_DAYS END), 0)
      + COALESCE(MAX(CASE WHEN STATUS_NAME = 'With Advising' THEN TOTAL_DAYS END), 0)
        AS SLA_BUCKET_BLOCKED_DAYS,
      COALESCE(MAX(CASE WHEN STATUS_NAME = 'Awaiting ER Response - Pending Item' THEN TOTAL_DAYS END), 0)
      + COALESCE(MAX(CASE WHEN STATUS_NAME = 'OE'                                THEN TOTAL_DAYS END), 0)
      + COALESCE(MAX(CASE WHEN STATUS_NAME = 'OE Extended'                        THEN TOTAL_DAYS END), 0)
        AS SLA_BUCKET_CUST_FACING_DAYS,
      LEAST(
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'Ready for OE Prep'                      THEN SLA_MET END), 1),
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'OE Verification/Checking Participation'  THEN SLA_MET END), 1),
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'ER Outreach Required'                    THEN SLA_MET END), 1),
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'Awaiting Routing'                        THEN SLA_MET END), 1),
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'Approved'                                THEN SLA_MET END), 1)
      ) AS SLA_BUCKET_WITH_OA_MET,
      LEAST(
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'Blocked'        THEN SLA_MET END), 1),
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'With Sales'     THEN SLA_MET END), 1),
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'With Advising'  THEN SLA_MET END), 1)
      ) AS SLA_BUCKET_BLOCKED_MET,
      LEAST(
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'Awaiting ER Response - Pending Item' THEN SLA_MET END), 1),
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'OE'                                  THEN SLA_MET END), 1),
        COALESCE(MAX(CASE WHEN STATUS_NAME = 'OE Extended'                          THEN SLA_MET END), 1)
      ) AS SLA_BUCKET_CUST_FACING_MET
  FROM BO_STATUS
  GROUP BY SFDC_OBJECT_ID, RECORD_TYPE
),
TICKET_DETAIL AS (
  SELECT
      TIX.SFDC_BENEFIT_ORDER_ID,
      TIX.CREATED_TS,
      CASE
        WHEN TIX.REPORTING_TEAM IN ('Fulfillment', 'Submission')
         AND TIX.TEAM = 'Onboarding'
         AND (TIX.SUB_TEAM = 'Implementation Advocate'
              OR (TIX.SUB_TEAM IN ('Fulfillment', 'Submission', 'Confirmation')
                  AND TIX.OA_LONGEST_HELD_OWNER_ID IS NOT NULL))
        THEN 'Ful_to_OA'
        WHEN TIX.REPORTING_TEAM IN ('Fulfillment', 'Submission')
         AND TIX.TEAM = 'Onboarding'
         AND TIX.SUB_TEAM IN ('Fulfillment', 'Submission', 'Confirmation')
         AND TIX.OA_LONGEST_HELD_OWNER_ID IS NULL
        THEN 'Ful_to_Ful'
        WHEN TIX.REPORTING_TEAM = 'Implementation Advocate'
         AND TIX.TEAM IN ('New Plan Sales', 'New Plans')
        THEN 'OA_to_NPS'
        WHEN TIX.REPORTING_TEAM = 'Implementation Advocate'
         AND TIX.TEAM = 'Benefits Advising'
        THEN 'OA_to_BenAdv'
        WHEN TIX.REPORTING_TEAM = 'Implementation Advocate'
         AND TIX.TEAM = 'Advising Fulfillment'
        THEN 'OA_to_AdvFul'
        ELSE 'Other'
      END AS TICKET_CATEGORY
  FROM BI.SFDC_TICKETS TIX
  WHERE TIX.SFDC_BENEFIT_ORDER_ID IN (SELECT SFDC_BENEFIT_ORDER_ID FROM BO_ATTRS)
    AND (TIX.FALSE_POSITIVE = FALSE OR TIX.FALSE_POSITIVE IS NULL)
    AND TIX.REPORTING_TEAM IN ('Fulfillment', 'Submission', 'Implementation Advocate')
),
TICKET_COUNTS AS (
  SELECT
      SFDC_BENEFIT_ORDER_ID,
      COUNT(CASE WHEN TICKET_CATEGORY = 'Ful_to_Ful'    THEN 1 END) AS TICKETS_TBL_FUL_TO_FUL,
      COUNT(CASE WHEN TICKET_CATEGORY = 'OA_to_NPS'     THEN 1 END) AS TICKETS_TBL_OA_TO_NPS,
      COUNT(CASE WHEN TICKET_CATEGORY = 'OA_to_BenAdv'  THEN 1 END) AS TICKETS_TBL_OA_TO_BENADV,
      COUNT(CASE WHEN TICKET_CATEGORY = 'OA_to_AdvFul'  THEN 1 END) AS TICKETS_TBL_OA_TO_ADVFUL,
      COUNT(CASE WHEN TICKET_CATEGORY = 'Other'          THEN 1 END) AS TICKETS_TBL_OTHER
  FROM TICKET_DETAIL
  GROUP BY SFDC_BENEFIT_ORDER_ID
),
OA_MAPPED_REPLICA AS (
  SELECT
      TIX.SFDC_BENEFIT_ORDER_ID,
      COUNT(DISTINCT CASE
        WHEN TIX.SUB_TEAM = 'Implementation Advocate'
        THEN TIX.SFDC_TICKET_ID END)                               AS TICKETS_TBL_IA,
      COUNT(DISTINCT CASE
        WHEN TIX.ER_OUTREACH_COUNT > 0
         AND TIX.SUB_TEAM != 'Implementation Advocate'
        THEN TIX.SFDC_TICKET_ID END)                               AS TICKETS_TBL_ER_OUTREACH,
      COUNT(DISTINCT CASE
        WHEN TIX.SUB_TEAM = 'Implementation Advocate'
        THEN TIX.SFDC_TICKET_ID END)
      + COUNT(DISTINCT CASE
        WHEN TIX.ER_OUTREACH_COUNT > 0
         AND TIX.SUB_TEAM != 'Implementation Advocate'
        THEN TIX.SFDC_TICKET_ID END)                               AS TICKETS_TBL_OA_MAPPED
  FROM BI.SFDC_TICKETS TIX
  WHERE TIX.SFDC_BENEFIT_ORDER_ID IN (SELECT SFDC_BENEFIT_ORDER_ID FROM BO_ATTRS)
    AND (TIX.FALSE_POSITIVE = FALSE OR TIX.FALSE_POSITIVE IS NULL)
  GROUP BY TIX.SFDC_BENEFIT_ORDER_ID
),
OE_TO_SUB AS (
  SELECT
      H.SFDC_OBJECT_ID,
      MIN(CASE WHEN H.FROM_STATUS = 'Ready for OE Prep'
               THEN H.START_TIME END)                           AS FIRST_OE_PREP_START,
      MIN(CASE WHEN H.FROM_STATUS IN ('Ready for Submission Prep', 'Submission Prep')
               THEN H.START_TIME END)                           AS FIRST_SUB_PREP_START,
      MAX(CASE WHEN H.FROM_STATUS IN ('Ready for Submission Prep', 'Submission Prep')
               THEN H.START_TIME END)                           AS LAST_SUB_PREP_START,
      MAX(CASE WHEN H.FROM_STATUS IN ('Ready for Submission Prep', 'Submission Prep')
               THEN H.END_TIME END)                             AS LAST_SUB_PREP_END,
      MAX(CASE WHEN H.FROM_STATUS = 'Ready for Confirmation'
               THEN H.START_TIME END)                           AS LAST_CONF_START
  FROM BI.BENEFIT_ORDER_STATUS_CHANGE_HISTORY H
  INNER JOIN BO_ATTRS A
    ON H.SFDC_OBJECT_ID = A.SFDC_BENEFIT_ORDER_ID
  WHERE H.FROM_STATUS IN ('Ready for OE Prep', 'Ready for Submission Prep',
                           'Submission Prep', 'Ready for Confirmation')
  GROUP BY H.SFDC_OBJECT_ID
),
TICKET_TIMING AS (
  SELECT
      TD.SFDC_BENEFIT_ORDER_ID,
      COUNT(CASE WHEN TD.TICKET_CATEGORY = 'OA_to_NPS'
                  AND CONVERT_TIMEZONE('America/Los_Angeles', 'America/Denver', TD.CREATED_TS)
                    < CONVERT_TIMEZONE('UTC', 'America/Denver', OTS.FIRST_SUB_PREP_START)
                 THEN 1 END)                                    AS TICKETS_TBL_NPS_PRE_SUB,
      COUNT(CASE WHEN TD.TICKET_CATEGORY = 'OA_to_NPS'
                  AND CONVERT_TIMEZONE('America/Los_Angeles', 'America/Denver', TD.CREATED_TS)
                    >= CONVERT_TIMEZONE('UTC', 'America/Denver', OTS.FIRST_SUB_PREP_START)
                 THEN 1 END)                                    AS TICKETS_TBL_NPS_POST_SUB,
      COUNT(CASE WHEN TD.TICKET_CATEGORY = 'OA_to_BenAdv'
                  AND CONVERT_TIMEZONE('America/Los_Angeles', 'America/Denver', TD.CREATED_TS)
                    < CONVERT_TIMEZONE('UTC', 'America/Denver', OTS.FIRST_SUB_PREP_START)
                 THEN 1 END)                                    AS TICKETS_TBL_BENADV_PRE_SUB,
      COUNT(CASE WHEN TD.TICKET_CATEGORY = 'OA_to_BenAdv'
                  AND CONVERT_TIMEZONE('America/Los_Angeles', 'America/Denver', TD.CREATED_TS)
                    >= CONVERT_TIMEZONE('UTC', 'America/Denver', OTS.FIRST_SUB_PREP_START)
                 THEN 1 END)                                    AS TICKETS_TBL_BENADV_POST_SUB
  FROM TICKET_DETAIL TD
  INNER JOIN OE_TO_SUB OTS
    ON TD.SFDC_BENEFIT_ORDER_ID = OTS.SFDC_OBJECT_ID
  WHERE OTS.FIRST_SUB_PREP_START IS NOT NULL
  GROUP BY TD.SFDC_BENEFIT_ORDER_ID
)
SELECT
    A.SFDC_BENEFIT_ORDER_ID,
    A.BENEFIT_ORDER_NAME,
    A.RECORD_TYPE_NAME,
    A.ORDER_TYPE,
    CASE WHEN A.SFDC_BENEFIT_ORDER_ID IS NOT NULL
         THEN 'https://gusto.lightning.force.com/lightning/r/Benefit_Order__c/'
              || A.SFDC_BENEFIT_ORDER_ID || '/view'
    END                                                             AS BO_LINK,
    CASE WHEN A.ZP_COMPANY_ID IS NOT NULL
         THEN CONCAT('https://hippo.gusto.com/companies/', A.ZP_COMPANY_ID)
    END                                                             AS HIPPO_LINK,
    A.ZP_COMPANY_ID,
    A.BENEFIT_ORDER_OWNER,
    A.SFDC_BENEFIT_ORDER_OWNER_ID,
    A.SDFC_LONGEST_BENEFIT_ORDER_OWNER,
    A.OWNER_PE_NAME_CURRENT,
    A.OWNER_PEPE_CURRENT,
    A.NUMBER_OA_ADVOCATES,
    EE.CURRENT_SFDC_USER_ID,
    A.COVERAGE_EFFECTIVE_DT,
    DATE_TRUNC('MONTH', A.COVERAGE_EFFECTIVE_DT)::DATE              AS COHORT_MONTH,
    A.ORIGINAL_EFFECTIVE_DT,
    A.OPEN_ENROLLMENT_START_DT,
    A.OPEN_ENROLLMENT_END_DT,
    CONVERT_TIMEZONE('UTC', 'America/Denver', A.CREATED_TS)         AS CREATED_TS_MT,
    CONVERT_TIMEZONE('UTC', 'America/Denver', A.FIRST_END_DT)      AS FIRST_END_DT_MT,
    DATE_TRUNC('MONTH', A.FIRST_END_DT)::DATE                      AS FIRST_END_MONTH,
    CONVERT_TIMEZONE('UTC', 'America/Denver', A.FIRST_APPROVED_TS)  AS FIRST_APPROVED_TS_MT,
    CONVERT_TIMEZONE('UTC', 'America/Denver', A.FIRST_FULFILLED_TS) AS FIRST_FULFILLED_TS_MT,
    CONVERT_TIMEZONE('UTC', 'America/Denver', A.LAST_FULFILLED_TS)  AS LAST_FULFILLED_TS_MT,
    CONVERT_TIMEZONE('UTC', 'America/Denver', A.FIRST_PUSH_TS)      AS FIRST_PUSH_TS_MT,
    CONVERT_TIMEZONE('UTC', 'America/Denver', A.LAST_PUSH_TS)       AS LAST_PUSH_TS_MT,
    CONVERT_TIMEZONE('UTC', 'America/Denver',
      A.FIRST_READY_FOR_SUBMISSION_PREP_TS)                         AS FIRST_READY_SUB_PREP_TS_MT,
    CONVERT_TIMEZONE('UTC', 'America/Denver',
      OTS.LAST_SUB_PREP_START)                                      AS LAST_READY_SUB_PREP_TS_MT,
    CONVERT_TIMEZONE('UTC', 'America/Denver',
      A.FIRST_READY_FOR_CONFIRMATION_TS)                            AS FIRST_READY_CONF_TS_MT,
    CONVERT_TIMEZONE('UTC', 'America/Denver',
      OTS.LAST_CONF_START)                                          AS LAST_READY_CONF_TS_MT,
    CONVERT_TIMEZONE('UTC', 'America/Denver', A.FIRST_CANCEL_TS)    AS FIRST_CANCEL_TS_MT,
    CONVERT_TIMEZONE('UTC', 'America/Denver', A.LAST_CANCEL_TS)     AS LAST_CANCEL_TS_MT,
    A.ORDER_STATUS,
    A.ORDER_STATUS_DETAIL,
    A.CANCELLATION_CAUSE_CATEGORY,
    CASE
      WHEN A.CANCELLATION_CAUSE_CATEGORY = 'Ambiguous - Other'
      THEN 'Ambiguous - Other'
      WHEN A.CANCELLATION_CAUSE_CATEGORY IN ('Non-responsive ER', 'Post-Signature Cancel')
      THEN 'OA/ Shared'
      WHEN A.CANCELLATION_CAUSE_CATEGORY IN ('Group is ineligible', 'Participation Issue')
      THEN 'NPS'
      ELSE 'Null'
    END                                                             AS CANCELLATION_RESPONSIBLE_TEAM,
    A.CANCEL_FLAG,
    A.CLOSED_FLAG,
    A.FULFILLED_FLAG,
    CASE WHEN A.FIRST_FULFILLED_TS IS NOT NULL THEN 1 ELSE 0 END   AS EVER_FULFILLED,
    CASE WHEN A.FIRST_CANCEL_TS IS NOT NULL THEN 1 ELSE 0 END      AS EVER_CANCELLED,
    A.DIFOT_FLAG,
    A.REVISED_DIFOT_FLAG,
    A.MEDICAL_REVISED_DIFOT_FLAG,
    CASE
      WHEN A.FIRST_FULFILLED_TS IS NOT NULL
       AND DATEDIFF('DAY', A.CREATED_TS, A.FIRST_FULFILLED_TS) <= 30
      THEN 1
      WHEN A.FIRST_FULFILLED_TS IS NOT NULL
      THEN 0
      ELSE NULL
    END                                                             AS FULFILLED_IN_30D_MET,
    A.SPECIAL_ENROLLMENT_FLAG,
    A.PUSH_FLAG,
    A.FUNDING_TYPE,
    A.MEDDICAL_CARRIER_INFORMATION_STATE,
    DATEDIFF('DAY', OTS.FIRST_OE_PREP_START, OTS.FIRST_SUB_PREP_START) AS DAYS_FIRST_OE_PREP_TO_FIRST_SUB_PREP,
    DATEDIFF('DAY', OTS.FIRST_OE_PREP_START, OTS.LAST_SUB_PREP_END)   AS DAYS_FIRST_OE_PREP_TO_LAST_SUB_PREP,
    DATEDIFF('DAY', A.CREATED_TS, A.FIRST_FULFILLED_TS)               AS DAYS_CREATED_TO_FIRST_FULFILLED,
    DATEDIFF('DAY', A.CREATED_TS, A.LAST_FULFILLED_TS)                AS DAYS_CREATED_TO_LAST_FULFILLED,
    DATEDIFF('DAY', A.FIRST_FULFILLED_TS, A.LAST_FULFILLED_TS)        AS DAYS_FIRST_TO_LAST_FULFILLED,
    DATEDIFF('DAY', A.CREATED_TS, A.FIRST_CANCEL_TS)                  AS DAYS_CREATED_TO_FIRST_CANCEL,
    DATEDIFF('DAY', A.CREATED_TS, A.LAST_CANCEL_TS)                   AS DAYS_CREATED_TO_LAST_CANCEL,
    DATEDIFF('DAY', A.FIRST_CANCEL_TS, A.LAST_CANCEL_TS)              AS DAYS_FIRST_TO_LAST_CANCEL,
    P.SLA_READY_OE_PREP_DAYS,      P.SLA_READY_OE_PREP_STINTS,     P.SLA_READY_OE_PREP_MET,
    P.SLA_OE_VERIF_DAYS,           P.SLA_OE_VERIF_STINTS,          P.SLA_OE_VERIF_MET,
    P.SLA_ER_OUTREACH_DAYS,        P.SLA_ER_OUTREACH_STINTS,       P.SLA_ER_OUTREACH_MET,
    P.SLA_AWAIT_ROUTING_DAYS,      P.SLA_AWAIT_ROUTING_STINTS,     P.SLA_AWAIT_ROUTING_MET,
    P.SLA_APPROVED_DAYS,           P.SLA_APPROVED_STINTS,          P.SLA_APPROVED_MET,
    P.SLA_BLOCKED_DAYS,            P.SLA_BLOCKED_STINTS,           P.SLA_BLOCKED_MET,
    P.SLA_WITH_SALES_DAYS,         P.SLA_WITH_SALES_STINTS,        P.SLA_WITH_SALES_MET,
    P.SLA_WITH_ADVISING_DAYS,      P.SLA_WITH_ADVISING_STINTS,     P.SLA_WITH_ADVISING_MET,
    P.SLA_ER_RESPONSE_DAYS,        P.SLA_ER_RESPONSE_STINTS,       P.SLA_ER_RESPONSE_MET,
    P.SLA_OE_DAYS,                 P.SLA_OE_STINTS,                P.SLA_OE_MET,
    P.SLA_OE_EXTENDED_DAYS,        P.SLA_OE_EXTENDED_STINTS,       P.SLA_OE_EXTENDED_MET,
    P.SLA_BUCKET_WITH_OA_DAYS,          P.SLA_BUCKET_WITH_OA_MET,
    P.SLA_BUCKET_BLOCKED_DAYS,          P.SLA_BUCKET_BLOCKED_MET,
    P.SLA_BUCKET_CUST_FACING_DAYS,      P.SLA_BUCKET_CUST_FACING_MET,
    A.TOTAL_IMPLEMENTATION_ADVOCATE_TICKETS                         AS TICKETS_BO_IMPL_ADVOCATE,
    A.TOTAL_ER_OUTREACH_TICKETS                                     AS TICKETS_BO_ER_OUTREACH,
    A.TOTAL_UNAVOIDABLE_EXCLUDE_TICKETS                             AS TICKETS_BO_UNAVOIDABLE_EXCL,
    NVL(A.TOTAL_IMPLEMENTATION_ADVOCATE_TICKETS, 0)
      + NVL(A.TOTAL_ER_OUTREACH_TICKETS, 0)                        AS TICKETS_BO_OA_MAPPED,
    NVL(A.TOTAL_IMPLEMENTATION_ADVOCATE_TICKETS, 0)
      + NVL(A.TOTAL_ER_OUTREACH_TICKETS, 0)
      - NVL(A.TOTAL_UNAVOIDABLE_EXCLUDE_TICKETS, 0)                AS TICKETS_BO_OA_MAPPED_EXCL_UNAVOID,
    A.TOTAL_BENEFITS_ADVISING_TICKETS                               AS TICKETS_BO_BENEFITS_ADVISING,
    A.TOTAL_NEW_PLAN_SALES_TICKETS                                  AS TICKETS_BO_NEW_PLAN_SALES,
    TC.TICKETS_TBL_FUL_TO_FUL,
    TC.TICKETS_TBL_OA_TO_NPS,
    TC.TICKETS_TBL_OA_TO_BENADV,
    TC.TICKETS_TBL_OA_TO_ADVFUL,
    TC.TICKETS_TBL_OTHER,
    OAM.TICKETS_TBL_IA,
    OAM.TICKETS_TBL_ER_OUTREACH,
    OAM.TICKETS_TBL_OA_MAPPED                                      AS TICKETS_TBL_OA_MAPPED_REPLICA,
    TT.TICKETS_TBL_NPS_PRE_SUB,
    TT.TICKETS_TBL_NPS_POST_SUB,
    TT.TICKETS_TBL_BENADV_PRE_SUB,
    TT.TICKETS_TBL_BENADV_POST_SUB,
    OPPT.OWNER_NAME                                                 AS RENEWAL_ADV_OPP_OWNER_NAME,
    OPPT.SFDC_OWNER_ID                                              AS RENEWAL_ADV_OPP_OWNER_ID,
    OPPT.OPPORTUNITY_OWNER_PE_NAME_AT_CLOSE                         AS RENEWAL_ADV_OPP_OWNER_PE_AT_CLOSE,
    OPPT.OPPORTUNITY_OWNER_PEPE_NAME_AT_CLOSE                       AS RENEWAL_ADV_OPP_OWNER_PEPE_AT_CLOSE,
    OPP_FACT.OWN_NAME                                               AS SFDC_OPP_OWNER_NAME
FROM BO_ATTRS A
LEFT JOIN PIVOTED P
  ON A.SFDC_BENEFIT_ORDER_ID = P.SFDC_OBJECT_ID
LEFT JOIN BI_REPORTING.ADVISING_OPPORTUNITIES OPPT
  ON A.SFDC_OPPORTUNITY_ID = OPPT.SFDC_OBJECT_ID
LEFT JOIN BI.SFDC_OPPORTUNITIES_FACT OPP_FACT
  ON A.SFDC_OPPORTUNITY_ID = OPP_FACT.OPPORTUNITY_ID
LEFT JOIN (SELECT DISTINCT CURRENT_SFDC_USER_ID FROM IC_EE_ID) EE
  ON A.SFDC_BENEFIT_ORDER_OWNER_ID = EE.CURRENT_SFDC_USER_ID
LEFT JOIN TICKET_COUNTS TC
  ON A.SFDC_BENEFIT_ORDER_ID = TC.SFDC_BENEFIT_ORDER_ID
LEFT JOIN OA_MAPPED_REPLICA OAM
  ON A.SFDC_BENEFIT_ORDER_ID = OAM.SFDC_BENEFIT_ORDER_ID
LEFT JOIN OE_TO_SUB OTS
  ON A.SFDC_BENEFIT_ORDER_ID = OTS.SFDC_OBJECT_ID
LEFT JOIN TICKET_TIMING TT
  ON A.SFDC_BENEFIT_ORDER_ID = TT.SFDC_BENEFIT_ORDER_ID
ORDER BY
  CONVERT_TIMEZONE('UTC', 'America/Denver', A.FIRST_END_DT),
  A.SFDC_BENEFIT_ORDER_ID;
