WITH opp AS (
  SELECT * FROM BI_REPORTING.ADVISING_OPPORTUNITIES
  WHERE RENEWAL_DATE BETWEEN CURRENT_DATE AND DATEADD('month', 6, CURRENT_DATE)
    AND NOT (STATUS ILIKE '%closed won%' OR STATUS ILIKE '%closed lost%' OR STATUS ILIKE '%order lost%' OR STATUS ILIKE '%closed admin%')
),
lc AS (
  SELECT o.SFDC_OBJECT_ID, o.HI_RENEWAL_ID, o.RENEWAL_DATE,
    p.policy_id, p.benefits_plan_id, p.benefit_type, p.renewal_stage_name
  FROM opp o
  JOIN BI.FCT_HEALTH_INSURANCE_RENEWAL_LIFECYCLE p ON o.HI_RENEWAL_ID = p.renewal_id
  WHERE p.renewal_stage_name = 'expiring'
),
mfund AS ( -- expiring (before) medical plan funding, policy-based
  SELECT lc.SFDC_OBJECT_ID, MAX(bp.funding_type) AS before_fund
  FROM lc JOIN HAWAIIAN_ICE_PRODUCTION_NO_PII.BENEFITS_PLANS bp ON bp.id = lc.benefits_plan_id
  WHERE lc.benefit_type = 'medical'
  GROUP BY 1
),
sb AS (
  SELECT lc.SFDC_OBJECT_ID, lc.benefit_type, COUNT(DISTINCT s.hi_employee_id) AS enr
  FROM lc JOIN BI.DIM_HEALTH_INSURANCE_SUBSCRIPTION s
    ON lc.policy_id = s.policy_id
    AND DATEADD('day',-105,lc.RENEWAL_DATE) BETWEEN s.start_date AND s.end_date
  GROUP BY 1,2
),
sb_wide AS (
  SELECT SFDC_OBJECT_ID,
    MAX(IFF(benefit_type='medical', enr, NULL)) AS enr_med,
    MAX(IFF(benefit_type='dental', enr, NULL)) AS enr_den,
    MAX(IFF(benefit_type='vision', enr, NULL)) AS enr_vis,
    MAX(IFF(benefit_type='life',   enr, NULL)) AS enr_life,
    MAX(IFF(benefit_type='long_term_disability',  enr, NULL)) AS enr_ltd,
    MAX(IFF(benefit_type='short_term_disability', enr, NULL)) AS enr_std,
    MAX(IFF(benefit_type='fsa', enr, NULL)) AS enr_fsa,
    MAX(IFF(benefit_type='dca', enr, NULL)) AS enr_dca,
    MAX(IFF(benefit_type='hsa', enr, NULL)) AS enr_hsa,
    MAX(IFF(benefit_type='voluntary_life', enr, NULL)) AS enr_vlife,
    MAX(IFF(benefit_type='voluntary_long_term_disability',  enr, NULL)) AS enr_vltd,
    MAX(IFF(benefit_type='voluntary_short_term_disability', enr, NULL)) AS enr_vstd
  FROM sb GROUP BY 1
),
vh AS (
  SELECT lc.SFDC_OBJECT_ID,
    MAX(IFF(benefit_type='voluntary_life',                 1, 0))::BOOLEAN AS HAS_VLIFE,
    MAX(IFF(benefit_type='voluntary_long_term_disability', 1, 0))::BOOLEAN AS HAS_VLTD,
    MAX(IFF(benefit_type='voluntary_short_term_disability',1, 0))::BOOLEAN AS HAS_VSTD
  FROM lc GROUP BY 1
),
carr_raw AS ( -- before-side carrier per opp x line (expiring only)
  SELECT lc.SFDC_OBJECT_ID, lc.benefit_type,
    s.carrier_name AS carrier, COALESCE(s.carrier_state,'') AS st,
    COUNT(DISTINCT s.hi_employee_id) AS enr
  FROM lc JOIN BI.DIM_HEALTH_INSURANCE_SUBSCRIPTION s
    ON lc.policy_id = s.policy_id
    AND DATEADD('day',-105,lc.RENEWAL_DATE) BETWEEN s.start_date AND s.end_date
  WHERE s.carrier_name IS NOT NULL
  GROUP BY 1,2,3,4
),
carr_line AS (
  SELECT SFDC_OBJECT_ID, benefit_type,
    OBJECT_CONSTRUCT(
      'b', ARRAY_COMPACT(ARRAY_AGG(OBJECT_CONSTRUCT('c',carrier,'s',st,'e',enr))),
      'a', ARRAY_CONSTRUCT()
    ) AS line_obj
  FROM carr_raw GROUP BY 1,2
),
carr_json AS (
  SELECT SFDC_OBJECT_ID, OBJECT_AGG(benefit_type, line_obj) AS carrier_detail
  FROM carr_line GROUP BY 1
),
per_opp AS (
  SELECT
    o.SFDC_OBJECT_ID,
    o.ZP_COMPANY_ID,
    o.SFDC_OBJECT_NAME_OR_NUM AS COMPANY,
    o.OWNER_NAME AS ADVISOR,
    o.OWNER_ROLE,
    o.OPPORTUNITY_OWNER_PE_NAME AS PE,
    o.STATUS AS STAGE,
    o.STAGE_DETAIL,
    o.RENEWAL_DATE,
    DATEDIFF('day', CURRENT_DATE, o.RENEWAL_DATE) AS DAYS_TO_RENEWAL,
    DATEDIFF('day', o.LAST_STATUS_CHANGE_TS, CURRENT_DATE) AS DAYS_IN_STAGE,
    o.FUNDING_TYPE,
    mfund.before_fund AS BEFORE_FUND,
    o.ACTIVE_EMPLOYEES_BEFORE, o.BENEFITS_ELIGIBLE_EMPLOYEES_BEFORE, o.NUMBER_EMPLOYEES_ENROLLED_BEFORE,
    -- row-display columns (unchanged names used by the table + filters)
    COALESCE(sb_wide.enr_med, 0) AS ENROLLED_MEDICAL,
    o.HAS_MEDICAL_BEFORE AS HAS_MEDICAL,
    o.HAS_DENTAL_BEFORE AS HAS_DENTAL,
    o.HAS_VISION_BEFORE AS HAS_VISION,
    o.HAS_LIFE_BEFORE AS HAS_LIFE,
    o.HAS_LTD_BEFORE AS HAS_LTD,
    o.HAS_STD_BEFORE AS HAS_STD,
    o.HAS_FSA_BEFORE AS HAS_FSA,
    o.HAS_DCA_BEFORE AS HAS_DCA,
    o.HAS_HSA_BEFORE AS HAS_HSA,
    COALESCE(vh.HAS_VLIFE, FALSE) AS HAS_VLIFE,
    COALESCE(vh.HAS_VLTD,  FALSE) AS HAS_VLTD,
    COALESCE(vh.HAS_VSTD,  FALSE) AS HAS_VSTD,
    -- detail HAS_*_BEFORE (read by OppExpansion)
    o.HAS_MEDICAL_BEFORE, o.HAS_DENTAL_BEFORE, o.HAS_VISION_BEFORE, o.HAS_LIFE_BEFORE,
    o.HAS_LTD_BEFORE, o.HAS_STD_BEFORE, o.HAS_FSA_BEFORE, o.HAS_DCA_BEFORE, o.HAS_HSA_BEFORE,
    COALESCE(vh.HAS_VLIFE, FALSE) AS HAS_VLIFE_BEFORE,
    COALESCE(vh.HAS_VLTD,  FALSE) AS HAS_VLTD_BEFORE,
    COALESCE(vh.HAS_VSTD,  FALSE) AS HAS_VSTD_BEFORE,
    -- detail ENROLLED_*_BEFORE
    sb_wide.enr_med AS ENROLLED_MEDICAL_BEFORE,
    sb_wide.enr_den AS ENROLLED_DENTAL_BEFORE,
    sb_wide.enr_vis AS ENROLLED_VISION_BEFORE,
    sb_wide.enr_life AS ENROLLED_LIFE_BEFORE,
    sb_wide.enr_ltd AS ENROLLED_LTD_BEFORE,
    sb_wide.enr_std AS ENROLLED_STD_BEFORE,
    sb_wide.enr_fsa AS ENROLLED_FSA_BEFORE,
    sb_wide.enr_dca AS ENROLLED_DCA_BEFORE,
    sb_wide.enr_hsa AS ENROLLED_HSA_BEFORE,
    sb_wide.enr_vlife AS ENROLLED_VLIFE_BEFORE,
    sb_wide.enr_vltd  AS ENROLLED_VLTD_BEFORE,
    sb_wide.enr_vstd  AS ENROLLED_VSTD_BEFORE,
    -- detail MRR_*_BEFORE (medical priced off the expiring plan funding, like the Closed tab)
    IFF(o.HAS_MEDICAL_BEFORE, COALESCE(sb_wide.enr_med,0) * IFF(LOWER(COALESCE(mfund.before_fund, o.FUNDING_TYPE,'')) LIKE '%level%', 46.53, 33.24), 0) AS MRR_MEDICAL_BEFORE,
    IFF(o.HAS_DENTAL_BEFORE, COALESCE(sb_wide.enr_den,0)  * 6.58, 0) AS MRR_DENTAL_BEFORE,
    IFF(o.HAS_VISION_BEFORE, COALESCE(sb_wide.enr_vis,0)  * 1.20, 0) AS MRR_VISION_BEFORE,
    IFF(o.HAS_LIFE_BEFORE,   COALESCE(sb_wide.enr_life,0) * 1.21, 0) AS MRR_LIFE_BEFORE,
    IFF(o.HAS_LTD_BEFORE,    COALESCE(sb_wide.enr_ltd,0)  * 1.65, 0) AS MRR_LTD_BEFORE,
    IFF(o.HAS_STD_BEFORE,    COALESCE(sb_wide.enr_std,0)  * 1.82, 0) AS MRR_STD_BEFORE,
    IFF(o.HAS_FSA_BEFORE,    COALESCE(sb_wide.enr_fsa,0)  * 4.00, 0) AS MRR_FSA_BEFORE,
    IFF(o.HAS_DCA_BEFORE,    COALESCE(sb_wide.enr_dca,0)  * 4.00, 0) AS MRR_DCA_BEFORE,
    IFF(o.HAS_HSA_BEFORE,    COALESCE(sb_wide.enr_hsa,0)  * 2.50, 0) AS MRR_HSA_BEFORE,
    IFF(COALESCE(vh.HAS_VLIFE,FALSE), COALESCE(sb_wide.enr_vlife,0) * 5.28, 0) AS MRR_VLIFE_BEFORE,
    IFF(COALESCE(vh.HAS_VLTD, FALSE), COALESCE(sb_wide.enr_vltd,0)  * 5.28, 0) AS MRR_VLTD_BEFORE,
    IFF(COALESCE(vh.HAS_VSTD, FALSE), COALESCE(sb_wide.enr_vstd,0)  * 5.28, 0) AS MRR_VSTD_BEFORE,
    TO_JSON(cj.carrier_detail) AS CARRIER_DETAIL
  FROM opp o
  LEFT JOIN sb_wide  ON o.SFDC_OBJECT_ID = sb_wide.SFDC_OBJECT_ID
  LEFT JOIN vh       ON o.SFDC_OBJECT_ID = vh.SFDC_OBJECT_ID
  LEFT JOIN mfund    ON o.SFDC_OBJECT_ID = mfund.SFDC_OBJECT_ID
  LEFT JOIN carr_json cj ON o.SFDC_OBJECT_ID = cj.SFDC_OBJECT_ID
)
SELECT per_opp.*,
  (COALESCE(MRR_MEDICAL_BEFORE,0)+COALESCE(MRR_DENTAL_BEFORE,0)+COALESCE(MRR_VISION_BEFORE,0)
   +COALESCE(MRR_LIFE_BEFORE,0)+COALESCE(MRR_LTD_BEFORE,0)+COALESCE(MRR_STD_BEFORE,0)
   +COALESCE(MRR_FSA_BEFORE,0)+COALESCE(MRR_DCA_BEFORE,0)+COALESCE(MRR_HSA_BEFORE,0)
   +COALESCE(MRR_VLIFE_BEFORE,0)+COALESCE(MRR_VLTD_BEFORE,0)+COALESCE(MRR_VSTD_BEFORE,0))::FLOAT AS MRR_BEFORE
FROM per_opp
ORDER BY RENEWAL_DATE, DAYS_TO_RENEWAL, SFDC_OBJECT_ID
