-- premium_lines: per-opp x benefit-type enrollment (before/after) + medical funding
-- (before/after), from the MRR-dashboard renewal lifecycle model. Drives the
-- recomputed per-line enrollment and MRR (enr_before/after, mrr_before/after) and
-- medical funding_after. Grain: one row per (opp, benefit_type).
-- Source: BI.FCT_HEALTH_INSURANCE_RENEWAL_LIFECYCLE + DIM_HEALTH_INSURANCE_SUBSCRIPTION.
with opp as (
  select sfdc_object_id, hi_renewal_id, renewal_date
  from data_warehouse_rc1.bi_reporting.advising_opportunities
  where renewal_date in ({{cohort_dates}})
),
ol as (
  select o.sfdc_object_id, o.renewal_date, p.policy_id, p.benefit_type, p.renewal_stage_name
  from opp o join data_warehouse_rc1.bi.fct_health_insurance_renewal_lifecycle p on o.hi_renewal_id=p.renewal_id
  where p.renewal_stage_name in ('expiring','selected')
    and p.benefit_type in ('medical','dental','vision','life','long_term_disability','short_term_disability','fsa','dca','hsa','voluntary_life')
),
eb as (
  select ol.sfdc_object_id, ol.benefit_type, count(distinct s.hi_employee_id) as enr
  from ol join data_warehouse_rc1.bi.dim_health_insurance_subscription s
    on ol.policy_id=s.policy_id and dateadd('day',-105,ol.renewal_date) between s.start_date and s.end_date
  where ol.renewal_stage_name='expiring' group by 1,2
),
ea as (
  select ol.sfdc_object_id, ol.benefit_type, count(distinct s.hi_employee_id) as enr
  from ol join data_warehouse_rc1.bi.dim_health_insurance_subscription s
    on ol.policy_id=s.policy_id and s.start_date between dateadd('day',-30,ol.renewal_date) and dateadd('day',30,ol.renewal_date)
  where ol.renewal_stage_name='selected' group by 1,2
),
h as (
  select sfdc_object_id, benefit_type,
    max(iff(renewal_stage_name='expiring',1,0)) as has_before,
    max(iff(renewal_stage_name='selected',1,0)) as has_after
  from ol group by 1,2
),
sel_any as (
  select sfdc_object_id, max(iff(renewal_stage_name='selected',1,0)) as has_any_selected from ol group by 1
),
mfund as (
  select o.sfdc_object_id,
    max(iff(p.renewal_stage_name='expiring', bp.funding_type, null)) as before_fund,
    max(iff(p.renewal_stage_name='selected', bp.funding_type, null)) as after_fund
  from opp o join data_warehouse_rc1.bi.fct_health_insurance_renewal_lifecycle p
    on o.hi_renewal_id=p.renewal_id and p.benefit_type='medical'
  join data_warehouse_rc1.hawaiian_ice_production_no_pii.benefits_plans bp on bp.id=p.benefits_plan_id
  where p.renewal_stage_name in ('expiring','selected') group by 1
)
select h.sfdc_object_id opp, h.benefit_type,
  h.has_before, h.has_after, eb.enr as enr_before, ea.enr as enr_after,
  sa.has_any_selected, mf.before_fund, mf.after_fund
from h
left join eb on h.sfdc_object_id=eb.sfdc_object_id and h.benefit_type=eb.benefit_type
left join ea on h.sfdc_object_id=ea.sfdc_object_id and h.benefit_type=ea.benefit_type
left join sel_any sa on h.sfdc_object_id=sa.sfdc_object_id
left join mfund mf on h.sfdc_object_id=mf.sfdc_object_id;
