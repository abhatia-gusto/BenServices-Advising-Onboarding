-- rate_index: medical rate-change index per opp (drives rate_increase_pct, rate_status,
-- rate_structure). Recovered from _renewal_full/sql/rate_tmpl.sql (per-date benchmark
-- ladder) + ratestruct.sql, generalized to all 6 cohort dates in one query.
--
-- Ladder (per renewal): own increase (matched expiring->default plan, enrolled-weighted)
--   -> carrier x state median of prior-6-months paired increases (>=8 pairs)
--   -> national median of that window. STS tags computed / no default built / no successor / no medical.
-- Sources: BI.FCT_HEALTH_INSURANCE_RENEWAL_LIFECYCLE (expiring), FCT_..._RECOMMENDATION
--   (default), BI.DIM_HEALTH_INSURANCE_PLAN (successor map / carrier / state),
--   HAWAIIAN_ICE_PRODUCTION_NO_PII.MEDICAL_PACKAGE_OFFERINGS (rate structure).
-- Grain: one row per cohort opp. Feeds: rate_increase_pct, rate_status, rate_structure.
with cd as (
  select distinct renewal_date::date rd
  from bi_reporting.advising_opportunities
  where renewal_date in ({{cohort_dates}})
),
oppmap as (
  select sfdc_object_id opp, try_to_number(hi_renewal_id) rid, renewal_date::date rd
  from bi_reporting.advising_opportunities
  where renewal_date in ({{cohort_dates}}) and hi_renewal_id is not null
),
base as (
  select renewal_id
  from bi.fct_health_insurance_renewal_lifecycle
  where renewal_date in ({{cohort_dates}}) and benefit_type='medical' and renewal_stage_name='expiring'
  group by 1),
exp as (
  select renewal_id, benefits_plan_id ep, max(enrolled_employee_count) ee,
         avg(average_eligible_employee_premium_cost_amount) op
  from bi.fct_health_insurance_renewal_lifecycle
  where renewal_date in ({{cohort_dates}}) and benefit_type='medical' and renewal_stage_name='expiring'
    and average_eligible_employee_premium_cost_amount>0
  group by 1,2),
map as (select benefits_plan_id, successor_benefits_plan_id, carrier_name, plan_state_code from bi.dim_health_insurance_plan),
new as (
  select renewal_id, benefits_plan_id np, avg(average_eligible_employee_premium_cost_amount) pn
  from bi.fct_health_insurance_renewal_recommendation
  where renewal_date in ({{cohort_dates}}) and benefit_type='medical' and default_flag=TRUE
    and average_eligible_employee_premium_cost_amount>0 group by 1,2),
matched as (
  select e.renewal_id, e.ee, e.op, n.pn from exp e join map m on e.ep=m.benefits_plan_id
  join new n on n.renewal_id=e.renewal_id and n.np=m.successor_benefits_plan_id where e.ee>0),
act as (select renewal_id, sum(ee*pn)/nullif(sum(ee*op),0)-1 inc, sum(ee) ee from matched group by 1 having sum(ee*op)>0),
-- benchmark: historical expiring->default paired increases, tagged with their own renewal_date
be as (
  select renewal_date::date rd, renewal_id, benefits_plan_id ep, max(enrolled_employee_count) ee,
         avg(average_eligible_employee_premium_cost_amount) op
  from bi.fct_health_insurance_renewal_lifecycle
  where benefit_type='medical' and renewal_stage_name='expiring' and average_eligible_employee_premium_cost_amount>0
    and renewal_date >= dateadd(month,-6,(select min(rd) from cd)) and renewal_date < (select max(rd) from cd)
  group by 1,2,3),
bn as (
  select renewal_date::date rd, renewal_id, benefits_plan_id np, avg(average_eligible_employee_premium_cost_amount) pn
  from bi.fct_health_insurance_renewal_recommendation
  where benefit_type='medical' and default_flag=TRUE and average_eligible_employee_premium_cost_amount>0
    and renewal_date >= dateadd(month,-6,(select min(rd) from cd)) and renewal_date < (select max(rd) from cd)
  group by 1,2,3),
paired as (
  select e.rd, m.carrier_name cn, m.plan_state_code st, n.pn/e.op-1 inc
  from be e join map m on e.ep=m.benefits_plan_id
  join bn n on n.renewal_id=e.renewal_id and n.rd=e.rd and n.np=m.successor_benefits_plan_id where e.ee>0),
bench as (
  select c.rd, p.cn, p.st, median(p.inc) est
  from cd c join paired p on p.rd >= dateadd(month,-6,c.rd) and p.rd < c.rd
  group by 1,2,3 having count(*)>=8),
nat as (
  select c.rd, median(p.inc) est
  from cd c join paired p on p.rd >= dateadd(month,-6,c.rd) and p.rd < c.rd
  group by 1),
tgt as (
  select l.renewal_id, p.carrier_name cn, p.plan_state_code st, sum(l.enrolled_employee_count) ee,
         row_number() over (partition by l.renewal_id order by sum(l.enrolled_employee_count) desc) rn
  from bi.fct_health_insurance_renewal_lifecycle l
  join bi.dim_health_insurance_plan p on p.benefits_plan_id=l.benefits_plan_id
  where l.renewal_date in ({{cohort_dates}}) and l.benefit_type='medical' and l.renewal_stage_name='expiring' group by 1,2,3),
ratestruct as (
  select mpo.renewal_id,
    max(case when mpo."DEFAULT" then iff(mpo.is_composite_rated,'Composite','Age-banded') end) as default_pkg_structure
  from hawaiian_ice_production_no_pii.medical_package_offerings mpo
  where mpo.renewal_id in (select rid from oppmap) group by 1)
select om.opp OPP, om.rid RID,
  round(a.inc,4) ACT,
  case when b.renewal_id is not null then round(coalesce(bh.est,(nat.est)),4) end EST,
  coalesce(a.ee,t.ee) EE, t.cn CARRIER, t.st ST,
  case when a.inc is not null then 'computed'
       when b.renewal_id is null then 'no medical'
       when not exists (select 1 from new n where n.renewal_id=om.rid) then 'no default built'
       else 'no successor' end STS,
  rs.default_pkg_structure RATE_STRUCTURE
from oppmap om
left join base b on b.renewal_id=om.rid
left join act a on a.renewal_id=om.rid
left join tgt t on t.renewal_id=om.rid and t.rn=1
left join bench bh on bh.rd=om.rd and bh.cn=t.cn and bh.st=t.st
left join nat on nat.rd=om.rd
left join ratestruct rs on rs.renewal_id=om.rid;
