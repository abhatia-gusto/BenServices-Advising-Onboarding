with openpf as (
  select sfdc_object_id from data_warehouse_rc1.bi_reporting.advising_opportunities
  where renewal_date in ({{cohort_dates}}) and status not in ('Closed Won','Closed Lost','Order Lost')
)
select c.opportunity__c opp,
  count(*) n_rcase,
  count(case when c.isclosed=false then 1 end) n_open_rcase,
  listagg(distinct nullif(c.status,''), ' / ') within group (order by nullif(c.status,'')) statuses,
  listagg(distinct nullif(c.reason,''), ' / ') within group (order by nullif(c.reason,'')) reasons
from data_warehouse_rc1.salesforce_production_no_pii.case2 c
where c.record_type_name__c='Benefits Renewal Case'
  and c.opportunity__c in (select sfdc_object_id from openpf)
group by c.opportunity__c;
