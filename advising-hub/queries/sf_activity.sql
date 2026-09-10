with openpf as (
  select sfdc_object_id from data_warehouse_rc1.bi_reporting.advising_opportunities
  where renewal_date in ({{cohort_dates}}) and status not in ('Closed Won','Closed Lost','Order Lost')
),
rc as (
  select c.id case_id, c.opportunity__c opp
  from data_warehouse_rc1.salesforce_production_no_pii.case2 c
  where c.record_type_name__c='Benefits Renewal Case'
    and c.opportunity__c in (select sfdc_object_id from openpf)
),
t as (
  select rc.opp, tk.type, tk.status, tk.createddate
  from data_warehouse_rc1.salesforce_production_no_pii.task tk
  join rc on rc.case_id = tk.whatid
  where (tk.type ilike '%call%' or tk.type ilike '%email%' or tk.subject ilike 'Email:%')
)
select opp,
  to_char(max(createddate)::date) last_update,
  count(*) n_activity,
  count(case when type ilike '%email%' or (type is null) then 1 end) n_email,
  count(case when type ilike '%call%' then 1 end) n_call,
  count(case when type ilike '%call%' and status='Connect' then 1 end) n_connect,
  to_char(min(case when type ilike '%call%' and status='Connect' then createddate end)::date) connect_date,
  to_char(min(case when type ilike '%call%' then createddate end)::date) first_call_date
from t group by opp;
