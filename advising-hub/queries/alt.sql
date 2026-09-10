with ren as (
  select hi_renewal_id from data_warehouse_rc1.bi_reporting.advising_opportunities
  where renewal_date in ({{cohort_dates}}) and hi_renewal_id is not null
),
pub as (
  select m.renewal_id,
    count(*) alt_pub_count,
    to_char(min(m.created_at)::date) alt_pub_first,
    to_char(max(m.created_at)::date) alt_pub_last,
    listagg(distinct nullif(trim(coalesce(m.name, g.name)),''), ' | ') within group (order by nullif(trim(coalesce(m.name,g.name)),'')) alt_pub_carriers
  from data_warehouse_rc1.hawaiian_ice_production_no_pii.medical_package_offerings m
  left join data_warehouse_rc1.hawaiian_ice_production_no_pii.renewals_draft_packages d on d.id=m.draft_package_id
  left join data_warehouse_rc1.hawaiian_ice_production_no_pii.recommended_plan_groups g on g.id=d.recommended_plan_group_id
  where m.renewal_id in (select hi_renewal_id from ren) and not m."DEFAULT"
  group by 1
)
select r.id renewal_id,
  to_char(r.alternate_packages_requested_timestamp::date) alt_req_date,
  coalesce(pub.alt_pub_count,0) alt_pub_count, pub.alt_pub_first, pub.alt_pub_last, pub.alt_pub_carriers
from data_warehouse_rc1.hawaiian_ice_production_no_pii.renewals r
join ren on ren.hi_renewal_id=r.id
left join pub on pub.renewal_id=r.id;
