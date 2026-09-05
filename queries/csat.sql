-- benops_csat_surveys.sql
-- Source for Redash 147811. CSAT survey data joined to BO and opportunity context.
-- Parameters: {{Date Start}}, {{Date End}} — applied to typeform_submitted_at
-- Used by: benops_csat_dashboard_v3.html (importable) and benops_csat_dashboard_v4.html (embedded)
-- See benops_csat_dashboard-README.md for refresh pipeline.

with csat_base as (
    select
        -- survey identifiers / grain
        record_id,
        survey_source,
        survey_name,
        survey_id,
        typeform_submitted_at,
        typeform_submitted_ts,
        -- link key to BO (when applicable)
        sfdc_onboarding_object_id,
        -- interaction + case/company context (from your other queries)
        assignee_name,
        case_owner_role,
        casenumber,
        company_id,
        company_name,
        channel,
        source,
        -- scores + free text
        csat_score,
        oa_csat_score,
        sales_advising_csat_score,
        ces_score,
        handle_time_score,
        expertise_score,
        comment,
        byb_csat_verbatim,   -- BYB Onboarding surveys store CSAT free-text here; COMMENT is NULL for BYB
        byb_ht_verbatim,     -- BYB handle-time free-text (kept for reference/future use)
        -- categories
        case
          when csat_score in (4,5) then 'Positive'
          when csat_score in (1,2,3) then 'Negative'
          when csat_score is null then 'No Score'
        end as csat_category,
        case
          when oa_csat_score in (4,5) then 'Positive'
          when oa_csat_score in (1,2,3) then 'Negative'
          when oa_csat_score is null then 'No Score'
        end as oa_csat_category,
        case
          when sales_advising_csat_score in (4,5) then 'Positive'
          when sales_advising_csat_score in (1,2,3) then 'Negative'
          when sales_advising_csat_score is null then 'No Score'
        end as sales_advising_csat_category,
        case
          when ces_score in (4,5) then 'Positive'
          when ces_score in (1,2,3) then 'Negative'
          when ces_score is null then 'No Score'
        end as ces_category
    from bi_reporting.ces_csat_data
)
select
    -- Survey-grain identifiers
    csat.record_id,
    csat.survey_source,
    csat.survey_name,
    csat.survey_id,
    csat.typeform_submitted_at as survey_submitted_date,
    csat.typeform_submitted_ts as survey_submitted_ts,
    -- extra attributes (from your other queries)
    csat.assignee_name,
    csat.case_owner_role,
    csat.casenumber,
    csat.company_id,
    csat.company_name,
    csat.channel,
    csat.source,
    -- BO columns (similar to your original query)
    bo.benefit_order_name,
    concat('https://gusto.my.salesforce.com/', left(bo.sfdc_benefit_order_id, 15), '?srPos=0&srKp=a0I') as bo_link,
    bo.sfdc_benefit_order_id,
    bo.benefit_order_owner,
    bo.owner_pe_name_current,
    bo.sfdc_benefit_order_owner_id,
    bo.record_type_name,
    bo.cancel_flag,
    bo.coverage_effective_dt,
    bo.original_effective_dt,
    case when bo.coverage_effective_dt <> bo.original_effective_dt then true else false end as order_pushed_flag,
    bo.order_status_detail,
    bo.first_fulfilled_ts::date as first_fulfilled_date,
    bo.last_fulfilled_ts::date as last_fulfilled_date,
    -- survey scores + comment (includes sales/advising csat)
    csat.csat_score as survey_csat_score,
    csat.oa_csat_score as survey_oa_csat_score,
    csat.sales_advising_csat_score as survey_sales_advising_csat_score,
    csat.ces_score,
    csat.handle_time_score,
    csat.expertise_score,
    -- BYB Onboarding surveys land CSAT free-text in BYB_CSAT_VERBATIM (COMMENT is NULL for BYB);
    -- the other three survey types use COMMENT. COALESCE captures both so BYB comments aren't lost.
    coalesce(csat.comment, csat.byb_csat_verbatim) as csat_survey_comment,
    csat.byb_csat_verbatim,   -- raw BYB CSAT verbatim (exposed for transparency)
    csat.byb_ht_verbatim,     -- raw BYB handle-time verbatim
    -- BO-level scores (optional but often useful to compare)
    bo.oa_csat_score as bo_oa_csat_score,
    bo.csat_score as bo_overall_csat_score,
    -- categories (optional)
    csat.csat_category,
    csat.oa_csat_category,
    csat.sales_advising_csat_category,
    csat.ces_category,
    -- opportunity context (broad opp table)
    bo.sfdc_opportunity_id,
    opp.opp_name,
    opp.opportunity_record_type_name,
    opp.own_name as opp_owner_name,
    opp.owner_role as opp_owner_role,
    opp.team as opp_team,
    opp.stagename as opp_stage,
    opp.rep as opp_rep_user_id,
    opp.sold_by_id as opp_sold_by_user_id,
    -- Opp Owner PE (CURRENT) — prefer advising_opportunities (covers Renewals perfectly),
    -- fall back to SFDC user → Gusto employee → PE lookup (covers New Plan, BYB, Transfers).
    -- Both reflect today's manager (not historical), so COALESCE is safe.
    coalesce(ao.opportunity_owner_pe_name, pe_lookup.pe) as opp_owner_pe_name,
    pe_lookup.pepe as opp_owner_pepe_name,   -- opp-owner chain PEPE — used for IN-APP/BSS RCA cc
    -- BO-owner chain (used for CSAT / BO-based RCA cc): join the PEPE table on the Benefit Order Owner.
    -- bo_owner_pe_name matches owner_pe_name_current 100% of recent CSAT rows (validated 2026-07-08),
    -- and bo_owner_pepe_name is that PE's manager = the correct skip-level to cc on BO-based surveys.
    bo_pe_lookup.pe as bo_owner_pe_name,
    bo_pe_lookup.pepe as bo_owner_pepe_name
from csat_base csat
left join bi_reporting.benefit_orders bo
  on bo.sfdc_benefit_order_id = csat.sfdc_onboarding_object_id
left join bi.sfdc_opportunities_fact opp
  on opp.opportunity_id = bo.sfdc_opportunity_id
left join bi_reporting.advising_opportunities ao
  on ao.sfdc_object_id = opp.opportunity_id
left join bi.int_sfdc_user_current_gusto_employees_pepe pe_lookup
  on pe_lookup.sfdc_user_id = opp.opp_owner_id
-- BO-owner chain lookup (for CSAT/BO-based RCA cc): keyed on the Benefit Order Owner, not the opp owner.
left join bi.int_sfdc_user_current_gusto_employees_pepe bo_pe_lookup
  on bo_pe_lookup.sfdc_user_id = bo.sfdc_benefit_order_owner_id
where csat.typeform_submitted_at between '{{Date Start}}' and '{{Date End}}'
