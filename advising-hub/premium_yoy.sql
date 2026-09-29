-- premium_yoy: per-opp medical premium change on the CLEAN, Hippo-matching basis.
-- Current = expiring_policies.eligible_employee_cost_breakdown (per-employee employee/dependent/total,
--   eligible basis). Renewal = renewal_plan_recommendations.individual_cost_breakdown on the DEFAULT
--   base plan (is_base). Matched current->renewal via effective_successor_plan_uuid -> benefits_plans.id.
-- Both sides eligible per-employee, so employee-only and with-dependents are apples-to-apples
-- (avoids the eligible-vs-enrolled mixing that corrupts lifecycle-based totals).
-- Feeds (opp-level, medical): prem_ee_pct, prem_dep_pct, prem_book_cur, prem_book_proj, prem_enr,
--   prem_fin_elig_pct (finalized, from fct selected_flag eligible rate — clean).
with o as (
  select sfdc_object_id opp, try_to_number(hi_renewal_id) rid
  from data_warehouse_rc1.bi_reporting.advising_opportunities
  where renewal_date in ({{cohort_dates}}) and hi_renewal_id is not null
),
bp as (select id, uuid from data_warehouse_rc1.hawaiian_ice_production_no_pii.benefits_plans),
-- enrolled headcount per (opp, expiring plan) from the lifecycle expiring stage — the EYO2 weight
enrw as (
  select o.opp, l.benefits_plan_id ep_id, max(l.enrolled_employee_count) w
  from o join data_warehouse_rc1.bi.fct_health_insurance_renewal_lifecycle l on l.renewal_id=o.rid
  where l.benefit_type='medical' and l.renewal_stage_name='expiring'
  group by 1,2
),
-- CURRENT: expiring policy per plan -> avg employee / avg total across its eligible members,
-- carrying the successor plan id (via uuid) and the ENROLLED weight (EYO2-consistent)
cur_plan as (
  select o.opp, ep.effective_successor_plan_uuid, bp.id succ_id,
    coalesce(max(w.w), count(*)) n,          -- enrolled headcount (EYO2 weight); fallback member count
    avg(try_to_double(f.value:employee::string)) cur_ee,
    avg(try_to_double(f.value:total::string))    cur_tot
  from o
  join data_warehouse_rc1.hawaiian_ice_production_no_pii.expiring_policies ep on ep.renewal_id=o.rid
  join bp  on bp.uuid  = ep.effective_successor_plan_uuid
  join bp bp2 on bp2.uuid = ep.benefits_plan_uuid
  left join enrw w on w.opp=o.opp and w.ep_id=bp2.id,
  lateral flatten(input => try_parse_json(ep.eligible_employee_cost_breakdown)) f
  where ep.effective_successor_plan_uuid is not null
  group by 1,2,3
),
-- RENEWAL: default base plan per opp -> avg employee / avg total across its members
ren_plan as (
  select o.opp, rpr.plan_id,
    avg(try_to_double(g.value:employee::string)) ren_ee,
    avg(try_to_double(g.value:total::string))    ren_tot
  from o
  join data_warehouse_rc1.hawaiian_ice_production_no_pii.medical_package_offerings mpo
    on mpo.renewal_id=o.rid and mpo."DEFAULT"=true
  join data_warehouse_rc1.hawaiian_ice_production_no_pii.renewal_plan_recommendations rpr
    on rpr.package_offering_id=mpo.id,
  lateral flatten(input => try_parse_json(rpr.individual_cost_breakdown)) g
  group by 1,2
),
matched as (
  select c.opp, c.n, c.cur_ee, c.cur_tot, r.ren_ee, r.ren_tot
  from cur_plan c join ren_plan r on r.opp=c.opp and r.plan_id=c.succ_id
),
-- finalized eligible rate from fct selected_flag (clean eligible EE, enrollment-weighted)
fin as (
  select e.opp,
    round((sum(e.ee*s.se)/nullif(sum(e.ee*e.ce),0)-1)*100,1) fin_pct
  from (
    select o.opp, l.benefits_plan_id ep, max(l.enrolled_employee_count) ee,
      avg(l.average_eligible_employee_premium_cost_amount) ce
    from o join data_warehouse_rc1.bi.fct_health_insurance_renewal_lifecycle l on l.renewal_id=o.rid
    where l.benefit_type='medical' and l.renewal_stage_name='expiring' and l.average_eligible_employee_premium_cost_amount>0
    group by 1,2
  ) e
  join data_warehouse_rc1.bi.dim_health_insurance_plan m on e.ep=m.benefits_plan_id
  join (
    select o.opp, r.benefits_plan_id np, avg(r.average_eligible_employee_premium_cost_amount) se
    from o join data_warehouse_rc1.bi.fct_health_insurance_renewal_recommendation r on r.renewal_id=o.rid
    where r.benefit_type='medical' and r.selected_flag=true and r.average_eligible_employee_premium_cost_amount>0
    group by 1,2
  ) s on s.np=m.successor_benefits_plan_id and s.opp=e.opp
  group by 1
)
select m.opp,
  round((sum(m.n*m.ren_ee)/nullif(sum(m.n*m.cur_ee),0)-1)*100,1) prem_ee_pct,
  round((sum(m.n*m.ren_tot)/nullif(sum(m.n*m.cur_tot),0)-1)*100,1) prem_dep_pct,
  round(sum(m.n*m.cur_tot)) prem_book_cur,
  round(sum(m.n*m.ren_tot)) prem_book_proj,
  sum(m.n) prem_enr,
  max(fin.fin_pct) prem_fin_elig_pct
from matched m
left join fin on fin.opp=m.opp
group by m.opp
