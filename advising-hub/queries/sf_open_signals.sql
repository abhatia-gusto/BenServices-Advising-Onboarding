-- sf_open_signals (C + E): per-opp open-risk signals re-sourced from Snowflake
-- SF-mirror tables (the original live-SOQL pulls cannot run headlessly).
-- One row per cohort opp. NO note text / PII — flags, dates, and integers only.
--   auto_renewal (E)        <- BI_REPORTING.ADVISING_OPPORTUNITIES.REASON_FOR_ADVISING ('Auto-renewed')
--   lead_days (E)           <- DATEDIFF(create_date -> renewal_date)
--   selection_deadline      <- ADVISING_OPPORTUNITIES.OFFERING_SELECTION_DEADLINE
--   submission_deadline     <- CASE2.OPPORTUNITY_SUBMISSION_DEADLINE__C on the Benefits Renewal Case
--   bor_term (BoR/termination)<- ADVISING_BLOCKED_REASON regex
--   sep                     <- SPECIAL_ENROLLMENT
--   recert_ticket/flag_date/lateness <- BI.SFDC_TICKETS open advising ticket w/ recert reason
-- NOT reconstructable from Snowflake (flagged, still carried-forward):
--   recert_status (Recert_Status__c not mirrored), packets_* (ContentDocumentLink
--   absent), intro_call completion checkbox (Intro_Call_Completed__c not mirrored;
--   live-connect is covered by sf_activity.intro_connect).
with o as (
  select sfdc_object_id opp, renewal_date, create_date, reason_for_advising,
         advising_blocked_reason, special_enrollment, offering_selection_deadline
  from data_warehouse_rc1.bi_reporting.advising_opportunities
  where renewal_date in ({{cohort_dates}})
),
subdl as (
  select b.sfdc_opportunity_id opp, max(c.opportunity_submission_deadline__c) submission_deadline
  from data_warehouse_rc1.bi.cases b
  join data_warehouse_rc1.salesforce_production_no_pii.case2 c on c.id = b.id
  where b.record_type_name = 'Benefits Renewal Case'
    and b.sfdc_opportunity_id in (select opp from o)
  group by b.sfdc_opportunity_id
),
recert as (
  select t.sfdc_opportunity_id opp,
    min(t.created_ts) recert_first_ts
  from data_warehouse_rc1.bi.sfdc_tickets t
  where t.sfdc_opportunity_id in (select opp from o)
    and lower(coalesce(t.escalation_reason,'')||coalesce(t.reason,'')||coalesce(t.confirmed_ticket_reason,'')) like '%recert%'
    and lower(coalesce(t.status,'')) not in ('closed','resolved','solved','complete','completed','cancelled','canceled','duplicate')
  group by t.sfdc_opportunity_id
)
select o.opp,
  case when o.reason_for_advising ilike '%Auto-renewed%' then 'Y' else 'N' end auto_renewal,
  datediff('day', o.create_date, o.renewal_date) lead_days,
  to_char(o.offering_selection_deadline,'YYYY-MM-DD') selection_deadline,
  to_char(subdl.submission_deadline,'YYYY-MM-DD') submission_deadline,
  case when o.advising_blocked_reason ilike '%terminat%' or o.advising_blocked_reason ilike '%bor%'
            or o.advising_blocked_reason ilike '%broker of record%' then 'Y' else 'N' end bor_term,
  case when o.special_enrollment then 'Y' else 'N' end sep,
  case when recert.recert_first_ts is not null then 'Y' else 'N' end recert_ticket,
  to_char(recert.recert_first_ts::date,'YYYY-MM-DD') recert_flag_date,
  case when recert.recert_first_ts is not null then datediff('day', recert.recert_first_ts::date, o.renewal_date) end recert_lateness_days
from o
left join subdl  on subdl.opp = o.opp
left join recert on recert.opp = o.opp;
