-- rec_timing: recommendation-cycle dates per opp.
-- Sources (mirrors _renewal_vnext/v4/q_flags_rec.sql + q_hippo_rec.sql):
--   create_date, default_rec_sent (first_recommendation_sent_ts), rfd_date
--     (first_ready_for_default_package_dt) : BI_REPORTING.ADVISING_OPPORTUNITIES
--   cycle_open  : HAWAIIAN_ICE_PRODUCTION_NO_PII.RENEWALS.created_at
--   default_built : min MEDICAL_PACKAGE_OFFERINGS.created_at where "DEFAULT"
-- Grain: one row per opp. Feeds: cycle_open, tl_cycle_open, default_rec_sent,
--   default_rec_built, and (derived) days_to_rec_cycle / time_to_default_rec_days /
--   rfd_to_rec_sent_days.
with o as (
  select sfdc_object_id opp, try_to_number(hi_renewal_id) rid,
    to_char(create_date::date) create_date,
    to_char(first_recommendation_sent_ts::date) default_rec_sent,
    to_char(first_ready_for_default_package_dt::date) rfd_date
  from data_warehouse_rc1.bi_reporting.advising_opportunities
  where renewal_date in ({{cohort_dates}})
),
mpo as (
  select renewal_id,
    to_char(min(case when "DEFAULT" then created_at end)::date) default_built
  from data_warehouse_rc1.hawaiian_ice_production_no_pii.medical_package_offerings
  where renewal_id in (select rid from o where rid is not null)
  group by 1
),
r as (
  select id renewal_id, to_char(created_at::date) cycle_open
  from data_warehouse_rc1.hawaiian_ice_production_no_pii.renewals
  where id in (select rid from o where rid is not null)
)
select o.opp, o.create_date, o.default_rec_sent, o.rfd_date,
  r.cycle_open, mpo.default_built
from o
left join r on r.renewal_id = o.rid
left join mpo on mpo.renewal_id = o.rid;
