select o.sfdc_object_id, max(c.rating_region) rating_region
from data_warehouse_rc1.bi_reporting.advising_opportunities o
join data_warehouse_rc1.bi.companies_hawaiian_ice c on to_varchar(c.id)=to_varchar(o.zp_company_id)
where o.renewal_date in ({{cohort_dates}})
  and c.rating_region is not null
group by o.sfdc_object_id;
