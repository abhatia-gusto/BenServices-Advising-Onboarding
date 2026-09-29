-- cases: per-opp (open/PF) renewal-case counts. Feeds case_summary (renewal case
-- counts) + n_rcase/n_open_rcase.
-- FIX (case2 schema drift 2026-09): re-pointed from salesforce_production_no_pii.case2
-- (dropped opportunity__c/record_type_name__c/isclosed/reason) to DATA_WAREHOUSE_RC1.BI.CASES
-- (SFDC_OPPORTUNITY_ID, RECORD_TYPE_NAME, ISCLOSED, STATUS, REASON). Output columns unchanged.
with openpf as (
  select sfdc_object_id from data_warehouse_rc1.bi_reporting.advising_opportunities
  where renewal_date in ({{cohort_dates}}) and status not in ('Closed Won','Closed Lost','Order Lost')
)
select c.sfdc_opportunity_id opp,
  count(*) n_rcase,
  count(case when c.isclosed=false then 1 end) n_open_rcase,
  listagg(distinct nullif(c.status,''), ' / ') within group (order by nullif(c.status,'')) statuses,
  listagg(distinct nullif(c.reason,''), ' / ') within group (order by nullif(c.reason,'')) reasons
from data_warehouse_rc1.bi.cases c
where c.record_type_name = 'Benefits Renewal Case'
  and c.sfdc_opportunity_id in (select sfdc_object_id from openpf)
group by c.sfdc_opportunity_id;
