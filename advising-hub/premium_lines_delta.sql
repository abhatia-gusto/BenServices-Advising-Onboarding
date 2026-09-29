-- premium_lines_delta (D): per-(opp, benefit_type) premium tiers + deltas that feed
-- lines[].pr_exp_e/pr_exp_n/pr_succ/pr_dflt/pr_sel/pr_fin and d_succ/d_dflt/d_sel/d_fin.
-- Reconstructed from the premium methodology doc + FCT renewal tables:
--   pr_exp_e = AVG(average_eligible_employee_premium_cost_amount) over EXPIRING lifecycle rows   (eligible-avg)
--   pr_exp_n = enrollment-weighted AVG(average_enrolled_employee_premium_cost_amount) EXPIRING    (enrolled, dep-loaded)
--   pr_fin   = enrollment-weighted AVG(average_enrolled_employee_premium_cost_amount) SELECTED     (finalized enrolled)
--   pr_dflt  = AVG(eligible-avg) over recommendation rows with DEFAULT_FLAG                        (default menu)
--   pr_sel   = AVG(eligible-avg) over recommendation rows with SELECTED_FLAG                       (selected menu)
--   pr_succ  = AVG(eligible-avg) over recommendation rows on the SUCCESSOR plans
--              (DIM_HEALTH_INSURANCE_PLAN.successor_benefits_plan_id of the expiring plans)
--   d_succ = pr_succ/pr_exp_e-1 ; d_dflt = pr_dflt/pr_exp_e-1 ; d_sel = pr_sel/pr_exp_e-1 ;
--   d_fin  = pr_fin/pr_exp_n-1   (deltas computed from RAW premiums, shown as %)
-- Grain: one row per (opp, benefit_type). Numeric only, no PII.
with opp as (
  select sfdc_object_id opp, hi_renewal_id renewal_id
  from data_warehouse_rc1.bi_reporting.advising_opportunities
  where renewal_date in ({{cohort_dates}}) and hi_renewal_id is not null
),
BT as (
  select column1 bt from values
    ('medical'),('dental'),('vision'),('life'),('long_term_disability'),
    ('short_term_disability'),('fsa'),('dca'),('hsa'),('voluntary_life')
),
life_exp as (
  select o.opp, l.benefit_type bt,
    avg(l.average_eligible_employee_premium_cost_amount) exp_e,
    sum(l.enrolled_employee_count*l.average_enrolled_employee_premium_cost_amount)
      / nullif(sum(l.enrolled_employee_count),0) exp_n
  from opp o
  join data_warehouse_rc1.bi.fct_health_insurance_renewal_lifecycle l on l.renewal_id=o.renewal_id
  where l.renewal_stage_name='expiring' and l.benefit_type in (select bt from BT)
  group by 1,2
),
life_sel as (
  select o.opp, l.benefit_type bt,
    sum(l.enrolled_employee_count*l.average_enrolled_employee_premium_cost_amount)
      / nullif(sum(l.enrolled_employee_count),0) fin_n
  from opp o
  join data_warehouse_rc1.bi.fct_health_insurance_renewal_lifecycle l on l.renewal_id=o.renewal_id
  where l.renewal_stage_name='selected' and l.benefit_type in (select bt from BT)
  group by 1,2
),
rec as (
  select o.opp, r.benefit_type bt,
    avg(case when r.default_flag  then r.average_eligible_employee_premium_cost_amount end) dflt_e,
    avg(case when r.selected_flag then r.average_eligible_employee_premium_cost_amount end) sel_e
  from opp o
  join data_warehouse_rc1.bi.fct_health_insurance_renewal_recommendation r on r.renewal_id=o.renewal_id
  where r.benefit_type in (select bt from BT)
  group by 1,2
),
exp_plans as (
  select distinct o.opp, l.benefit_type bt, l.benefits_plan_id
  from opp o
  join data_warehouse_rc1.bi.fct_health_insurance_renewal_lifecycle l on l.renewal_id=o.renewal_id
  where l.renewal_stage_name='expiring' and l.benefit_type in (select bt from BT)
),
succ_plans as (
  -- distinct successor plan(s) for each (opp, benefit_type)
  select distinct ep.opp, ep.bt, p.successor_benefits_plan_id sp
  from exp_plans ep
  join data_warehouse_rc1.bi.dim_health_insurance_plan p on p.benefits_plan_id=ep.benefits_plan_id
  where p.successor_benefits_plan_id is not null
),
succ as (
  -- avg over the RAW recommendation rows on the successor plan(s) (row grain, not
  -- per-plan dedup — matches the original patch's successor-premium derivation)
  select sp.opp, sp.bt, avg(r.average_eligible_employee_premium_cost_amount) succ_e
  from succ_plans sp
  join opp o on o.opp=sp.opp
  join data_warehouse_rc1.bi.fct_health_insurance_renewal_recommendation r
    on r.renewal_id=o.renewal_id and r.benefit_type=sp.bt and r.benefits_plan_id=sp.sp
  group by 1,2
),
keys as (
  select opp, bt from life_exp
  union select opp, bt from life_sel
  union select opp, bt from rec
)
select k.opp, k.bt benefit_type,
  round(le.exp_e)  pr_exp_e,
  round(le.exp_n)  pr_exp_n,
  round(sc.succ_e) pr_succ,
  round(rc.dflt_e) pr_dflt,
  round(rc.sel_e)  pr_sel,
  round(ls.fin_n)  pr_fin,
  round((sc.succ_e/nullif(le.exp_e,0)-1)*100,1) d_succ,
  round((rc.dflt_e/nullif(le.exp_e,0)-1)*100,1) d_dflt,
  round((rc.sel_e /nullif(le.exp_e,0)-1)*100,1) d_sel,
  round((ls.fin_n /nullif(le.exp_n,0)-1)*100,1) d_fin
from keys k
left join life_exp le on le.opp=k.opp and le.bt=k.bt
left join life_sel ls on ls.opp=k.opp and ls.bt=k.bt
left join rec      rc on rc.opp=k.opp and rc.bt=k.bt
left join succ     sc on sc.opp=k.opp and sc.bt=k.bt;
