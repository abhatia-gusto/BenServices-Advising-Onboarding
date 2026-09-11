-- sf_activity: per-opp (open/PF) Salesforce case activity. Feeds intro_connect,
-- connect_date, last_update, case_summary(activity), n_email/n_call/n_connect,
-- last_call_date, last_connect_date, last_call_disp.
-- FIX (case2 schema drift 2026-09): salesforce_production_no_pii.case2 dropped
-- opportunity__c / record_type_name__c. Re-pointed to DATA_WAREHOUSE_RC1.BI.CASES
-- (SFDC_OPPORTUNITY_ID, RECORD_TYPE_NAME, full-length ID) joined to the SF task
-- mirror on task.whatid = cases.id. Output columns unchanged.
with openpf as (
  select sfdc_object_id from data_warehouse_rc1.bi_reporting.advising_opportunities
  where renewal_date in ({{cohort_dates}}) and status not in ('Closed Won','Closed Lost','Order Lost')
),
rc as (
  select c.id case_id, c.sfdc_opportunity_id opp
  from data_warehouse_rc1.bi.cases c
  where c.record_type_name = 'Benefits Renewal Case'
    and c.sfdc_opportunity_id in (select sfdc_object_id from openpf)
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
  to_char(min(case when type ilike '%call%' then createddate end)::date) first_call_date,
  -- Last-call fields (per-opp, call-type tasks only): latest call date, latest connect date,
  -- and the disposition of the latest call mapped to Connect / VM / Attempt.
  --   last_call_date    = latest date any call-type task was logged.
  --   last_connect_date = latest date a Connect call was logged.
  --   last_call_disp    = disposition of the most-recent CALL DAY:
  --       * Connect  when the latest connect DATE == the latest call DATE (i.e. the most recent
  --         call day included a connect — day granularity, so a connect + an auto-logged voicemail
  --         seconds later on the same day still reads as a connect);
  --       * else VM   when the latest call (max createddate; max_by ignores NULL ordering values,
  --         so restricting the ordering to call rows yields the most-recent call's status) is a
  --         voicemail;
  --       * else Attempt (Attempt / Scheduled / Connect-with-Gatekeeper / etc.);
  --       * null when there are no call-type tasks.
  to_char(max(case when type ilike '%call%' then createddate end)::date) last_call_date,
  to_char(max(case when type ilike '%call%' and status='Connect' then createddate end)::date) last_connect_date,
  case
    when max(case when type ilike '%call%' then createddate end) is null then null
    when max(case when type ilike '%call%' and status='Connect' then createddate::date end)
       = max(case when type ilike '%call%' then createddate::date end) then 'Connect'
    when max_by(status, case when type ilike '%call%' then createddate end) ilike '%voicemail%' then 'VM'
    else 'Attempt'
  end last_call_disp
from t group by opp;
