-- time_in_rfd: total days an opp has dwelled in the SFDC 'Ready for Default Package'
-- stage (sum of all stints, minutes/1440). Source: BI.SFDC_OPPORTUNITY_HISTORY.
-- Grain: one row per opp (SFDC_OBJECT_ID). Feeds JSON field: days_to_default (the
-- "Time in RFD" column). Exactly mirrors hub_queries/time_in_erc.sql.
with c as (
  select sfdc_object_id
  from data_warehouse_rc1.bi_reporting.advising_opportunities
  where renewal_date in ({{cohort_dates}})
)
select oh.opportunity_id opp,
  round(sum(datediff(minute, oh.effect_start_dt, least(oh.effect_end_dt, current_timestamp()))::float/1440),3) time_in_rfd
from data_warehouse_rc1.bi.sfdc_opportunity_history oh
join c on c.sfdc_object_id = oh.opportunity_id
where oh.stagename = 'Ready for Default Package'
  and datediff(minute, oh.effect_start_dt, least(oh.effect_end_dt, current_timestamp())) > 0
group by 1;
