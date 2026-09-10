-- lf: Level-Funded signals per opp (drives lf_savings_pct, lf_quote, lf_in_alt).
-- Savings engine = queries/lf_dashboard_data_v1.sql (flat AVG of per-employee savings vs the
--   default medical recommendation, LF group_level_plan_rates matched on company + effective_date
--   with ind-deductible/coinsurance <=110% guard). No classifier needed for the savings number.
-- lf_quote  = LF plan available: a level-funded rate PDF (GROUP_LEVEL_PLAN_RATES) and/or a
--   level-funded plan offered in the renewal recommendation (MEDICAL_PACKAGE_OFFERINGS ->
--   RENEWAL_PLAN_RECOMMENDATIONS -> BENEFITS_PLANS funding_type='level_funded').
-- lf_in_alt = a level-funded plan is offered in a NON-default (alternate) medical package offering.
-- Grain: one row per cohort opp that has any LF signal. lf_savings_band is derived downstream.
with cohort as (
  select sfdc_object_id opp, try_to_number(hi_renewal_id) rid, renewal_date::date rd
  from bi_reporting.advising_opportunities where renewal_date in ({{cohort_dates}})
),
lf_per_ee as (
  select try_parse_json(qco.overridden_configuration):"group_quoting_factors":"employee"::number(18,2) as lf_emp,
    hpd.co_insurance_percentage, try_to_number(hpd.individual_deductible_cents,'$999,999,999.99') as ind_ded,
    glpr.effective_date, c.customer_id as company_id
  from hawaiian_ice_production_no_pii.group_level_plan_rates glpr
  join bi.dim_customer c on glpr.group_uuid=c.customer_uuid
  join hawaiian_ice_production_no_pii.benefits_plans bp on bp.uuid=glpr.benefits_plan_uuid
  join hawaiian_ice_production_no_pii.group_level_quoting_configuration_overrides qco on glpr.group_level_quoting_configuration_override_id=qco.id
  join hawaiian_ice_production_no_pii.health_plan_details hpd on hpd.benefits_plan_id=bp.id
  where lower(glpr.source_type) like '%level%'
  union all
  select try_parse_json(qco.overridden_configuration):"group_quoting_factors":"employee"::number(18,2) as lf_emp,
    hpd.co_insurance_percentage, try_to_number(hpd.individual_deductible_cents,'$999,999,999.99') as ind_ded,
    glpr.effective_date, co.id as company_id
  from hawaiian_ice_production_no_pii.group_level_plan_rates glpr
  join bi.companies co on glpr.group_uuid=co.uuid
  join hawaiian_ice_production_no_pii.benefits_plans bp on bp.uuid=glpr.benefits_plan_uuid
  join hawaiian_ice_production_no_pii.group_level_quoting_configuration_overrides qco on glpr.group_level_quoting_configuration_override_id=qco.id
  join hawaiian_ice_production_no_pii.health_plan_details hpd on hpd.benefits_plan_id=bp.id
  where lower(glpr.source_type) like '%level%'
),
base as (
  select try_parse_json(rpr.individual_cost_breakdown) as bj, hpd.co_insurance_percentage,
    try_to_number(hpd.individual_deductible_cents,'$999,999,999.99') as ind_ded,
    r.company_id, opps.sfdc_object_id opp, opps.renewal_date::date rd
  from hawaiian_ice_production_no_pii.medical_package_offerings mpo
  join hawaiian_ice_production_no_pii.renewal_plan_recommendations rpr on rpr.package_offering_id=mpo.id
  join bi.renewals_hawaiian_ice r on r.id=mpo.renewal_id
  join hawaiian_ice_production_no_pii.benefits_plans bp on rpr.plan_id=bp.id
  join hawaiian_ice_production_no_pii.health_plan_details hpd on hpd.benefits_plan_id=bp.id
  join bi_reporting.advising_opportunities opps on opps.hi_renewal_id=r.id
  where mpo.default=true and rpr.package_offering_type='MedicalPackageOffering'
    and opps.renewal_date in ({{cohort_dates}})
),
ree as (select b.opp, b.company_id, b.rd, b.co_insurance_percentage, b.ind_ded,
    f.key::string as emp_id, f.value:"employee"::number(18,2) as emp_cost
  from base b, lateral flatten(input=>b.bj) f),
-- currently-enrolled (active) medical employees; savings is averaged over ENROLLED only
enrolled as (
  select distinct s.employee_id::string as emp_id
  from hawaiian_ice_production_no_pii.subscriptions s
  where s.details_type='HealthSubscriptionDetail' and s.start_date<=current_date
    and (s.end_date is null or s.end_date>=current_date)
),
cells as (
  select r.opp, iff(en.emp_id is not null,1,0) as is_enrolled,
    case when l.lf_emp<r.emp_cost and r.emp_cost>0 then (r.emp_cost-l.lf_emp)/r.emp_cost else 0 end as sav
  from ree r
  join lf_per_ee l on l.company_id=r.company_id and l.effective_date=r.rd
    and l.ind_ded<=r.ind_ded*1.10 and l.co_insurance_percentage<=r.co_insurance_percentage*1.10
  left join enrolled en on en.emp_id=r.emp_id
),
sav as (select opp, avg(iff(is_enrolled=1,sav,null)) as avg_sav from cells group by opp having avg_sav is not null),
oc as (
  select c.opp, c.rd, c.rid, r.company_id
  from cohort c left join bi.renewals_hawaiian_ice r on r.id=c.rid
),
ratepdf as (select distinct company_id, effective_date from lf_per_ee),
lfoff as (
  -- HAS_LF_REC = level-funded plan offered in the renewal recommendation (default OR alternate;
  --   matches the LF-dashboard "recommended/default/alternate" definition -> lf_quote 'recommendation').
  -- HAS_LF_ALT = level-funded plan in a NON-default (alternate) offering -> lf_in_alt.
  select mpo.renewal_id,
    max(iff(bp.funding_type='level_funded',1,0)) as has_lf_rec,
    max(iff(bp.funding_type='level_funded' and mpo."DEFAULT"=false,1,0)) as has_lf_alt
  from hawaiian_ice_production_no_pii.medical_package_offerings mpo
  join hawaiian_ice_production_no_pii.renewal_plan_recommendations rpr on rpr.package_offering_id=mpo.id
  join hawaiian_ice_production_no_pii.benefits_plans bp on rpr.plan_id=bp.id
  where rpr.package_offering_type='MedicalPackageOffering'
    and mpo.renewal_id in (select rid from cohort where rid is not null)
  group by 1
)
select oc.opp OPP,
  round(sav.avg_sav,4) as LF_SAVINGS_PCT,
  iff(rp.company_id is not null,1,0) as HAS_RATE_PDF,
  coalesce(lfoff.has_lf_rec,0) as HAS_LF_REC,
  coalesce(lfoff.has_lf_alt,0) as HAS_LF_ALT
from oc
left join sav on sav.opp=oc.opp
left join ratepdf rp on rp.company_id=oc.company_id and rp.effective_date=oc.rd
left join lfoff on lfoff.renewal_id=oc.rid
where sav.opp is not null
   or rp.company_id is not null
   or coalesce(lfoff.has_lf_rec,0)=1;
