WITH o AS (
  SELECT sfdc_object_id, hi_renewal_id, zp_company_id, sfdc_account_id, status, renewal_date,
         special_enrollment, advising_blocked_reason, sfdc_object_name_or_num, has_medical_before
  FROM BI_REPORTING.ADVISING_OPPORTUNITIES WHERE renewal_date IN ({{cohort_dates}})
),
gid AS (
  SELECT r.id AS renewal_id, c.gusto_id
  FROM HAWAIIAN_ICE_PRODUCTION_NO_PII.RENEWALS r
  JOIN HAWAIIAN_ICE_PRODUCTION_NO_PII.COMPANIES c ON c.id = r.company_id
  WHERE r.id IN (SELECT hi_renewal_id FROM o)
),
fund AS (
  SELECT company_id, MAX_BY(funding_type, COALESCE(effective_date, updated_at)) AS funding
  FROM BI.POLICIES_HAWAIIAN_ICE
  WHERE benefit_type='medical' AND company_id IN (SELECT zp_company_id FROM o)
  GROUP BY company_id
),
lines AS (
  SELECT company_id, COUNT(DISTINCT benefit_type) AS n_lines,
    LISTAGG(DISTINCT benefit_type, ', ') WITHIN GROUP (ORDER BY benefit_type) AS lines_list
  FROM BI.POLICIES_HAWAIIAN_ICE
  WHERE company_id IN (SELECT zp_company_id FROM o) AND current_flag = TRUE
  GROUP BY company_id
),
autofin AS (
  SELECT DISTINCT renewal_id FROM HAWAIIAN_ICE_PRODUCTION_NO_PII.RENEWAL_AUTO_FINALIZE_RECORDS
  WHERE renewal_id IN (SELECT hi_renewal_id FROM o)
),
bo AS (
  SELECT sfdc_opportunity_id, COUNT(*) AS n_bo, MAX(order_status) AS bo_status,
    SUM(COALESCE(total_benefits_advising_tickets,0)) AS tickets_adv, MAX(csat_score) AS bo_csat
  FROM BI_REPORTING.BENEFIT_ORDERS
  WHERE sfdc_opportunity_id IN (SELECT sfdc_object_id FROM o) GROUP BY sfdc_opportunity_id
),
inapp AS (
  SELECT company_id, MAX_BY(rating, response_at) AS in_app_rating, MAX(response_at) AS in_app_ts
  FROM BI.APPLICATION_SURVEY_DATA
  WHERE company_id IN (SELECT zp_company_id FROM o) AND workflow_name ILIKE '%renewal%' GROUP BY company_id
),
ces AS (
  SELECT company_id, MAX_BY(csat_score, COALESCE(typeform_submitted_ts, ticket_solved_at)) AS ces_csat
  FROM BI.CES_CSAT_DATA
  WHERE company_id IN (SELECT zp_company_id FROM o) AND csat_score IS NOT NULL GROUP BY company_id
)
SELECT o.sfdc_object_id, o.hi_renewal_id, o.zp_company_id,
  o.special_enrollment, o.advising_blocked_reason, o.sfdc_object_name_or_num, o.has_medical_before,
  gid.gusto_id, fund.funding AS med_funding, lines.n_lines, lines.lines_list,
  IFF(autofin.renewal_id IS NOT NULL, 'Y','') AS default_automation,
  IFF(bo.n_bo>0,'Y','N') AS bo_exists, bo.bo_status, COALESCE(bo.tickets_adv,0) AS tickets_to_advising, bo.bo_csat,
  inapp.in_app_rating, ces.ces_csat
FROM o
LEFT JOIN gid ON gid.renewal_id = o.hi_renewal_id
LEFT JOIN fund ON fund.company_id = o.zp_company_id
LEFT JOIN lines ON lines.company_id = o.zp_company_id
LEFT JOIN autofin ON autofin.renewal_id = o.hi_renewal_id
LEFT JOIN bo ON bo.sfdc_opportunity_id = o.sfdc_object_id
LEFT JOIN inapp ON inapp.company_id = o.zp_company_id
LEFT JOIN ces ON ces.company_id = o.zp_company_id
