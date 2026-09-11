-- sf_activity: per-opp (open/PF) Salesforce case activity. Feeds intro_connect,
-- connect_date, last_update, case_summary(activity), n_email/n_call/n_connect,
-- last_call_date, last_connect_date, last_call_disp.
-- FIX (case2 schema drift 2026-09): salesforce_production_no_pii.case2 dropped
-- opportunity__c / record_type_name__c. Re-pointed to DATA_WAREHOUSE_RC1.BI.CASES
-- (SFDC_OPPORTUNITY_ID, RECORD_TYPE_NAME, full-length ID) joined to the SF task
-- mirror on task.whatid = cases.id.
--
-- TRUE-CONNECT FIX (2026-09): STATUS='Connect' is self-reported and gets stamped on
-- voicemails too (e.g. a 30s call with a blank disposition, or one explicitly dispositioned
-- 'Left voicemail'). So a call now counts as a *connect* (is_tc=1) only when STATUS='Connect'
-- AND it is not a voicemail/disconnect by disposition AND -- when the disposition is blank --
-- it lasted > 45 seconds. n_connect / connect_date / last_connect_date / last_call_disp all
-- key off is_tc, so intro_connect, the "Connected <=21d" panel, and the gone-quiet call risk
-- signal only credit calls we actually reached someone on.
--   STRICT (current): blank disposition + NULL duration does NOT count (needs dur>45 or a real disp).
--   LENIENT alternative: to keep blank+NULL-duration calls as connects, add
--   `or tk.calldurationinseconds is null` to the `(disp is not null or dur>45)` clause below.
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
  select rc.opp, tk.type, tk.status, tk.calldisposition disp, tk.calldurationinseconds dur, tk.createddate,
    iff(tk.type ilike '%call%' and tk.status='Connect'
        and not (tk.calldisposition ilike '%voicemail%' or tk.calldisposition ilike '%voice mail%'
                 or tk.calldisposition ilike '%left message%' or tk.calldisposition ilike '%left vm%'
                 or tk.calldisposition ilike '%left a vm%'  or tk.calldisposition ilike '%left voice%'
                 or tk.calldisposition ilike '%mailbox%'    or tk.calldisposition ilike '%no answer%'
                 or tk.calldisposition ilike '%disconnect%')
        and (tk.calldisposition is not null or tk.calldurationinseconds > 45), 1, 0) is_tc
  from data_warehouse_rc1.salesforce_production_no_pii.task tk
  join rc on rc.case_id = tk.whatid
  where (tk.type ilike '%call%' or tk.type ilike '%email%' or tk.subject ilike 'Email:%')
)
select opp,
  to_char(max(createddate)::date) last_update,
  count(*) n_activity,
  count(case when type ilike '%email%' or (type is null) then 1 end) n_email,
  count(case when type ilike '%call%' then 1 end) n_call,
  -- connect columns count TRUE connects only (is_tc; see header)
  count(case when is_tc=1 then 1 end) n_connect,
  to_char(min(case when is_tc=1 then createddate end)::date) connect_date,
  to_char(min(case when type ilike '%call%' then createddate end)::date) first_call_date,
  -- Last-call fields (per-opp, call-type tasks only):
  --   last_call_date    = latest date any call-type task was logged.
  --   last_connect_date = latest date a TRUE connect was logged.
  --   last_call_disp    = disposition of the most-recent CALL DAY:
  --       * Connect  when the latest true-connect DATE == the latest call DATE (day granularity);
  --       * else VM   when the latest call is a voicemail (status or disposition);
  --       * else Attempt.
  to_char(max(case when type ilike '%call%' then createddate end)::date) last_call_date,
  to_char(max(case when is_tc=1 then createddate end)::date) last_connect_date,
  case
    when max(case when type ilike '%call%' then createddate end) is null then null
    when max(case when is_tc=1 then createddate::date end)
       = max(case when type ilike '%call%' then createddate::date end) then 'Connect'
    when max_by(status, case when type ilike '%call%' then createddate end) ilike '%voicemail%'
      or max_by(disp,   case when type ilike '%call%' then createddate end) ilike '%voicemail%'
      or max_by(disp,   case when type ilike '%call%' then createddate end) ilike '%left message%'
      or max_by(disp,   case when type ilike '%call%' then createddate end) ilike '%mailbox%' then 'VM'
    else 'Attempt'
  end last_call_disp
from t group by opp;
