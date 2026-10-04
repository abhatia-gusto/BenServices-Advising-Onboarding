-- benops_inapp_sentiment.sql
-- Source for Redash 147849. In-app sentiment survey data from BI.APPLICATION_SURVEY_DATA,
-- enriched with renewal opportunity + opportunity owner context.
-- Parameters:
--   {{survey_start_date}} — first day of survey_displayed_at window
--   {{survey_end_date}}   — last day of survey_displayed_at window
--   {{workflow_status}}   — Redash multi-select: 'Completed' and/or 'Abandoned'
-- Used by: benops_csat_dashboard_v3.html (importable) and benops_csat_dashboard_v4.html (embedded)
-- See benops_csat_dashboard-README.md for refresh pipeline.

select
  -- Survey / workflow context
  asd.workflow_name as workflow_name,
  date_trunc('day', asd.survey_displayed_at) as survey_date,
  u.type as user_type,
  asd.rating as rating,
  asd.company_id as company_id,   -- drives the Hippo company link on the Slack card (HIPAA-safe format, 2026-07-23)
  case
    when asd.workflow_completed = true then 'Completed'
    else 'Abandoned'
  end as workflow_status,
  asd.feedback as user_comment,
  -- Renewal opportunity match (best match by renewal_date proximity)
  opp.opportunity_id as renewal_opportunity_id,
  opp.opp_name as renewal_opportunity_name,
  opp.renewal_date as renewal_date,
  -- Opportunity owner from SFDC_OPPORTUNITIES_FACT
  opp.own_name as opportunity_owner_name,
  -- Opportunity owner fields from ADVISING_OPPORTUNITIES (as requested)
  ao.owner_name as advising_opportunity_owner_name,
  -- PE name: prefer advising_opportunities (historical context), fall back to current user lookup.
  -- For BSS this should be ~100% from ao since BSS is renewals-only, but the fallback covers edge cases.
  coalesce(ao.opportunity_owner_pe_name, pe_lookup.pe) as opportunity_owner_pe_name,
  pe_lookup.pepe as opportunity_owner_pepe_name,  -- bonus: PE's PE for skip-level escalation
  -- extra opp context (optional)
  opp.opp_owner_id as opportunity_owner_id,
  opp.owner_role as opportunity_owner_role,
  opp.team as opportunity_team,
  opp.stagename as opportunity_stage
from bi.application_survey_data asd
join bi.user_roles u
  on asd.user_role_id = u.id
left join bi.sfdc_opportunities_fact opp
  on opp.zp_company_id = to_varchar(asd.company_id)
 and opp.renewal_date is not null
left join bi_reporting.advising_opportunities ao
  on ao.sfdc_object_id = opp.opportunity_id
left join bi.int_sfdc_user_current_gusto_employees_pepe pe_lookup
  on pe_lookup.sfdc_user_id = opp.opp_owner_id
where 1 = 1
  -- Date range filter
  and asd.survey_displayed_at >= '{{survey_start_date}}'
  and asd.survey_displayed_at <= '{{survey_end_date}}'
  -- Workflow scope
  and asd.workflow_name = 'Benefits Renewal'
  -- Filter: Completed vs Abandoned (parameter expects values like 'Completed','Abandoned')
  and (
    case
      when asd.workflow_completed = true then 'Completed'
      else 'Abandoned'
    end
  ) in ({{workflow_status}})
  -- NOTE: We are including surveys with or without comments.
  -- NOTE: We are including both accountant and non-accountant user roles.
qualify row_number() over (
  -- Choose one "best" renewal opportunity per survey display instance
  partition by asd.survey_id
  order by
    case
      when opp.renewal_date >= date_trunc('day', asd.survey_displayed_at) then 0
      else 1
    end,
    abs(datediff('day', date_trunc('day', asd.survey_displayed_at), opp.renewal_date))
) = 1
order by asd.survey_displayed_at desc;
