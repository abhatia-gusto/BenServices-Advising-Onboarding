with opps as (
  select sfdc_object_id, sfdc_account_id
  from data_warehouse_rc1.bi_reporting.advising_opportunities
  where renewal_date in ({{cohort_dates}})
    and sfdc_account_id is not null
)
select o.sfdc_object_id opp,
       coalesce(nullif(trim(c.record_type_summary),''),'Other') rts,
       count(*) open_ct
from opps o
join data_warehouse_rc1.bi.cases c
  on c.sfdc_account_id = o.sfdc_account_id
where c.isclosed = false
group by o.sfdc_object_id, coalesce(nullif(trim(c.record_type_summary),''),'Other');
