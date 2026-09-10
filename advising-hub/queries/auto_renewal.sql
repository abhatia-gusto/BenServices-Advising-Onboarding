-- auto_renewal: canonical CUSTOMER auto-renewal signal from Snowplow.
-- The customer confirmed the default package and skipped the renewal flow, i.e. the
-- Snowplow event CATEGORY='Renewals' AND ACTION='ConfirmDefaultAndSkipFlow'
-- (per Default_Automation_CALC_reference.md footnote + memory/reference_benefits_autorenewal_flag.md).
-- This REPLACES the old REASON_FOR_ADVISING ilike '%Auto-renewed%' derivation, which broke at
-- FY26 Q2 and is unreliable. NOT the same as default_automation / auto-finalize (afr row).
-- Grain: one row per cohort opp. Company/plan grain only -- NO PII columns.
--   auto_renewal      = 'Y' if >=1 ConfirmDefaultAndSkipFlow event fired for the opp's company
--                       (ga_track.company_id = advising_opportunities.zp_company_id) inside the
--                       renewal window [renewal_date-120d, renewal_date+31d); else 'N'.
--   auto_renewal_date = MIN(event date) of those in-window events, else null.
-- Windowing keys the event to THIS renewal (companies renew annually; a prior year's
-- confirm-skip must not leak onto this cohort's opp).
with o as (
  select sfdc_object_id opp, zp_company_id, renewal_date
  from data_warehouse_rc1.bi_reporting.advising_opportunities
  where renewal_date in ({{cohort_dates}})
    and zp_company_id is not null
),
ev as (
  select o.opp, min(t.event_timestamp::date) auto_renewal_date
  from o
  join data_warehouse_rc1.snowplow_facts.ga_track_365_days t
    on to_varchar(t.company_id) = to_varchar(o.zp_company_id)
   and t.category = 'Renewals'
   and t.action   = 'ConfirmDefaultAndSkipFlow'
   and t.event_timestamp >= dateadd(day, -120, o.renewal_date)
   and t.event_timestamp <  dateadd(day,   31, o.renewal_date)
  group by o.opp
)
select o.opp,
  case when ev.opp is not null then 'Y' else 'N' end auto_renewal,
  to_char(ev.auto_renewal_date, 'YYYY-MM-DD') auto_renewal_date
from o
left join ev on ev.opp = o.opp;
