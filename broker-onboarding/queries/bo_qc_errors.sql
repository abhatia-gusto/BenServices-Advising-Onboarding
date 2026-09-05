-- ════════════════════════════════════════════════════════════════════════════
-- QC ERRORS QUERY — BYB + BT (Broker Onboarding) — v.5  (canonical, provided by Aman)
-- One row per QC error; SUB_FUNCTION = BYB/BT via text-match + PE-name fallback.
-- Cohort filter on SYSTEM_CREATED_TS. Params: {{ Date Range Start }} / {{ Date Range End }}.
-- Consumed by bo_diag_pull.py which aggregates to bo_qc_month.csv + bo_qc_detail.csv.
-- ════════════════════════════════════════════════════════════════════════════
WITH as_of_owner AS (
    SELECT sfdc_user_id, name AS aoe_name, email AS aoe_email, status AS aoe_status,
        team AS aoe_team, sub_team AS aoe_sub_team, pe AS aoe_pe, job_title AS aoe_job_title,
        hired_at AS aoe_hired_at, effect_start_dt, effect_end_dt
    FROM bi.gusto_employees WHERE sfdc_user_id IS NOT NULL
),
earliest_owner AS (
    SELECT sfdc_user_id, name AS ear_name, email AS ear_email, status AS ear_status,
        team AS ear_team, sub_team AS ear_sub_team, pe AS ear_pe, job_title AS ear_job_title,
        hired_at AS ear_hired_at,
        ROW_NUMBER() OVER (PARTITION BY sfdc_user_id ORDER BY effect_start_dt ASC, etl_update_ts ASC NULLS LAST) AS rn_earliest
    FROM bi.gusto_employees WHERE sfdc_user_id IS NOT NULL
),
latest_owner AS (
    SELECT sfdc_user_id, sfdc_ee_id AS lat_sfdc_ee_id, name AS lat_name, status AS lat_status,
        terminated_at AS lat_terminated_at, team AS lat_team, sub_team AS lat_sub_team,
        pe AS lat_pe, pe_sfdc_ee_id AS lat_pe_sfdc_ee_id,
        ROW_NUMBER() OVER (PARTITION BY sfdc_user_id ORDER BY effect_start_dt DESC, etl_update_ts DESC NULLS LAST) AS rn_latest
    FROM bi.gusto_employees WHERE sfdc_user_id IS NOT NULL
),
pepe_lookup AS (
    SELECT sfdc_ee_id AS pepe_ee_id, pe AS pepe_name,
        ROW_NUMBER() OVER (PARTITION BY sfdc_ee_id ORDER BY effect_start_dt DESC, etl_update_ts DESC NULLS LAST) AS rn
    FROM bi.gusto_employees WHERE sfdc_ee_id IS NOT NULL
),
qa_with_joins AS (
    SELECT q.sfdc_qa_error_id, q.qa_error_name, q.error_type, q.error_type_detail, q.error_severity,
        q.weighted_severity, q.false_positive, q.mark_as_resolved, q.blocking_future_clients, q.summary,
        q.qa_error_team, q.from_sub_team, q.to_sub_team, q.to_team,
        aoe.aoe_name, aoe.aoe_email, aoe.aoe_status, aoe.aoe_team, aoe.aoe_sub_team, aoe.aoe_pe, aoe.aoe_job_title, aoe.aoe_hired_at,
        ear.ear_name, ear.ear_email, ear.ear_status, ear.ear_team, ear.ear_sub_team, ear.ear_pe, ear.ear_job_title, ear.ear_hired_at,
        lat.lat_name, lat.lat_status, lat.lat_terminated_at, lat.lat_team, lat.lat_sub_team, lat.lat_pe, lat.lat_pe_sfdc_ee_id,
        pepe.pepe_name, ro.lat_name AS record_owner_name,
        qar.lat_name AS qa_reviewer_name, qar.lat_team AS qa_reviewer_team, qar.lat_sub_team AS qa_reviewer_sub_team,
        q.sfdc_error_owner_id, q.sfdc_owner_id, q.sfdc_createdby_id, q.sfdc_case_id, q.sfdc_ticket_id,
        q.sfdc_benefit_order_id, q.sfdc_carrier_order_id, q.error_origin_dt, q.effective_date,
        q.system_created_ts, q.system_modified_ts, q.isdeleted
    FROM bi.sfdc_qa_errors q
    LEFT JOIN as_of_owner aoe ON aoe.sfdc_user_id = q.sfdc_error_owner_id
          AND q.system_created_ts::date >= aoe.effect_start_dt
          AND q.system_created_ts::date <  COALESCE(aoe.effect_end_dt, DATE '9999-12-31')
    LEFT JOIN earliest_owner ear ON ear.sfdc_user_id = q.sfdc_error_owner_id AND ear.rn_earliest = 1
    LEFT JOIN latest_owner lat ON lat.sfdc_user_id = q.sfdc_error_owner_id AND lat.rn_latest = 1
    LEFT JOIN pepe_lookup pepe ON pepe.pepe_ee_id = lat.lat_pe_sfdc_ee_id AND pepe.rn = 1
    LEFT JOIN latest_owner ro ON ro.sfdc_user_id = q.sfdc_owner_id AND ro.rn_latest = 1
    LEFT JOIN latest_owner qar ON qar.sfdc_user_id = q.sfdc_createdby_id AND qar.rn_latest = 1
    WHERE q.isdeleted = FALSE
      AND q.system_created_ts::date BETWEEN '{{ Date Range Start }}'::date AND '{{ Date Range End }}'::date
    QUALIFY ROW_NUMBER() OVER (PARTITION BY q.sfdc_qa_error_id ORDER BY aoe.effect_start_dt DESC NULLS LAST) = 1
),
qa_resolved AS (
    SELECT q.*,
        COALESCE(aoe_name, ear_name) AS owner_name,
        COALESCE(aoe_email, ear_email) AS owner_email,
        COALESCE(aoe_status, ear_status) AS status_at_error_logged,
        COALESCE(aoe_team, ear_team) AS team_at_error_logged,
        COALESCE(aoe_sub_team, ear_sub_team) AS sub_team_at_error_logged,
        COALESCE(aoe_pe, ear_pe) AS pe_at_error_logged,
        COALESCE(aoe_job_title, ear_job_title) AS job_title_at_error_logged,
        COALESCE(aoe_hired_at, ear_hired_at) AS hired_at
    FROM qa_with_joins q
),
qa_categorized AS (
    SELECT q.*,
        CASE
          WHEN COALESCE(qa_error_team,'') ILIKE '%bring your broker%'
            OR COALESCE(sub_team_at_error_logged,'') ILIKE '%bring your broker%'
            OR COALESCE(lat_sub_team,'') ILIKE '%bring your broker%'
            OR COALESCE(from_sub_team,'') ILIKE '%bring your broker%'
            OR COALESCE(to_sub_team,'') ILIKE '%bring your broker%' THEN 'BYB'
          WHEN COALESCE(qa_error_team,'') ILIKE '%benefits transfer%'
            OR COALESCE(sub_team_at_error_logged,'') ILIKE '%benefits transfer%'
            OR COALESCE(lat_sub_team,'') ILIKE '%benefits transfer%'
            OR COALESCE(from_sub_team,'') ILIKE '%benefits transfer%'
            OR COALESCE(to_sub_team,'') ILIKE '%benefits transfer%' THEN 'BT'
          WHEN COALESCE(pe_at_error_logged, lat_pe) IN ('Lisa Schulze','Michelle Nguyen','Nataly Kincaid') THEN 'BYB'
          WHEN COALESCE(pe_at_error_logged, lat_pe) IN ('Sasha Lenz','Katreena Kriekenbeek','Martin Ribas') THEN 'BT'
          ELSE 'Unknown — review'
        END AS sub_function,
        (summary ILIKE 'EA Audit %') AS is_ea_audit
    FROM qa_resolved q
)
SELECT
    'Broker Onboarding' AS parent_team, sub_function, is_ea_audit,
    sfdc_qa_error_id, qa_error_name, error_type, error_type_detail, false_positive, summary,
    qa_error_team, from_sub_team, to_sub_team, to_team,
    owner_name, sub_team_at_error_logged, pe_at_error_logged,
    lat_sub_team AS sub_team_current, lat_pe AS pe_current,
    qa_reviewer_name, record_owner_name,
    error_origin_dt, system_created_ts,
    sfdc_case_id, sfdc_ticket_id, sfdc_benefit_order_id, sfdc_carrier_order_id,
    sfdc_error_owner_id, sfdc_createdby_id, sfdc_owner_id
FROM qa_categorized
WHERE sub_function IN ('BT','BYB')
    OR COALESCE(qa_error_team,'') ILIKE '%broker onboarding%'
    OR COALESCE(sub_team_at_error_logged,'') ILIKE '%broker onboarding%'
    OR COALESCE(lat_sub_team,'') ILIKE '%broker onboarding%'
    OR COALESCE(from_sub_team,'') ILIKE '%broker onboarding%'
    OR COALESCE(to_sub_team,'') ILIKE '%broker onboarding%'
