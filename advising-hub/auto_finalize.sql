-- auto_finalize: default-automation eligibility + rate-parse success, per opp.
-- Recovered from queries/renewal_true_automation_drilldown.sql (same CTE stack,
-- renewal grain). Sources: HAWAIIAN_ICE_PRODUCTION_NO_PII.{carriers, state_carriers,
-- plan_recommendation_engine_new_relationship_supporte, medical_package_offerings,
-- renewal_auto_finalize_records, renewal_rate_parsing_records}, BI.POLICIES_HAWAIIAN_ICE,
-- SALESFORCE_PRODUCTION_NO_PII.OPPORTUNITY (stage timestamps), BI_REPORTING.ADVISING_OPPORTUNITIES.
-- Feeds: automation_eligible (eligible_renewal_flag Y/N), rate_parse_success
--   ('Y' if parse_success_rate=1, 'N' if <1, null if no parse records).
with standard_medical_carriers as (
  with state_carrier as (
    select c.id, c.key, sc.key as carrier_state_key, sc.state, sc.id as carrier_state_id
    from hawaiian_ice_production_no_pii.carriers c
    left join hawaiian_ice_production_no_pii.state_carriers sc on sc.carrier_id = c.id
  ), np as (
    select np.*, rank() over(partition by carrier_key, state_abbreviation order by effective_date desc) as rank
    from hawaiian_ice_production_no_pii.plan_recommendation_engine_new_relationship_supporte np
    where line_of_coverage = 'medical'
    qualify rank = 1
  )
  select np.carrier_key, np.state_abbreviation as carrier_state,
         np.line_of_coverage as benefit_type, sc.id as carrier_id
  from np
  left join state_carrier sc on sc.state = np.state_abbreviation and sc.key = np.carrier_key
  where new_relationship_supported = true
),
policies as (
  select phi.id, phi.benefit_type, phi.carrier_name, phi.carrier_state, phi.renewal_id
  , case when phi.benefit_type = 'medical' and smc.carrier_key is not null then 1
         when phi.benefit_type = 'medical' and smc.carrier_key is null     then 0
         else null end as standard_medical_carrier_flag
  , case when phi.benefit_type <> 'medical' and phi.carrier_key =  'guardian' then 1
         when phi.benefit_type <> 'medical' and phi.carrier_key <> 'guardian' then 0
         else null end as guardian_ancillary_flag
  from bi.policies_hawaiian_ice phi
  left join standard_medical_carriers smc
    on  phi.carrier_key   = smc.carrier_key
    and phi.carrier_state = smc.carrier_state
    and phi.benefit_type  = smc.benefit_type
  where phi.benefit_type in ('medical','dental','vision','life',
                             'short_term_disability','long_term_disability')
),
eligible_renewals as (
  select p.renewal_id
  , sum(case when benefit_type <> 'medical' then 1 else 0 end) as ancillary_count
  , sum(case when benefit_type =  'medical' then 1 else 0 end) as medical_count
  , count(distinct case when benefit_type =  'medical' then carrier_name end) as distinct_medical_carrier_count
  , min(case when is_composite_rated = true then 1 else 0 end) as composite_rate_flag_min
  , min(standard_medical_carrier_flag) as renewal_standard_medical_carrier_flag
  , min(guardian_ancillary_flag)       as renewal_guardian_ancillary_flag
  , case when renewal_standard_medical_carrier_flag = 1 and composite_rate_flag_min = 0
              and renewal_guardian_ancillary_flag = 1 then 1
         when renewal_standard_medical_carrier_flag = 1 and composite_rate_flag_min = 0
              and ancillary_count = 0                 then 1
         when medical_count = 0 and renewal_guardian_ancillary_flag = 1 then 1
         else 0 end as carrier_eligible_flag
  from policies p
  left join hawaiian_ice_production_no_pii.medical_package_offerings med
    on med.renewal_id = p.renewal_id
  group by 1
),
auto_attempts as (
  select renewal_id
  , count(*) as parse_record_count
  , count(case when successful = true then id end) as successful_record_count
  , successful_record_count::float / nullif(parse_record_count,0)::float as parse_success_rate
  from hawaiian_ice_production_no_pii.renewal_rate_parsing_records
  group by 1
),
o as (
  select sfdc_object_id opp, try_to_number(hi_renewal_id) rid, renewal_date
  from bi_reporting.advising_opportunities
  where renewal_date in ({{cohort_dates}})
)
select o.opp,
  case when (nvl(so.answering_survey_start__c, so.awaiting_offerings_start__c) is not null
             and er.carrier_eligible_flag = 1
             and datediff('day', current_date, o.renewal_date) <= 105) then 1
       when afr.id is not null then 1
       else 0 end as eligible_renewal_flag,
  aa.parse_record_count,
  aa.parse_success_rate
from o
left join hawaiian_ice_production_no_pii.renewal_auto_finalize_records afr on afr.renewal_id = o.rid
left join salesforce_production_no_pii.opportunity so
       on so.opportunity_id_18_digit__c::varchar(65535) = o.opp::varchar(65535)
left join eligible_renewals er on er.renewal_id = o.rid
left join auto_attempts    aa on aa.renewal_id = o.rid;
