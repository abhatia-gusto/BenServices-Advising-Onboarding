with c as (select sfdc_object_id from bi_reporting.advising_opportunities where renewal_date in ({{cohort_dates}})),
rdp as (select oh.opportunity_id, round(sum(datediff(minute,oh.effect_start_dt,least(oh.effect_end_dt,current_timestamp()))::float/1440),2) d
  from bi.sfdc_opportunity_history oh join c on oh.opportunity_id=c.sfdc_object_id
  where oh.stagename='Ready for Default Package' and datediff(minute,oh.effect_start_dt,least(oh.effect_end_dt,current_timestamp()))>0 group by 1),
er as (select oh.opportunity_id, round(sum(datediff(minute,oh.effect_start_dt,least(oh.effect_end_dt,current_timestamp()))::float/1440),2) d
  from bi.sfdc_opportunity_history oh join c on oh.opportunity_id=c.sfdc_object_id
  where oh.stagename='ER Confirm' and datediff(minute,oh.effect_start_dt,least(oh.effect_end_dt,current_timestamp()))>0 group by 1),
alt as (select oh.opportunity_id, round(sum(datediff(minute,oh.effect_start_dt,least(oh.effect_end_dt,current_timestamp()))::float/1440),2) d
  from bi.sfdc_opportunity_history oh join c on oh.opportunity_id=c.sfdc_object_id
  where oh.stagename='Alternates Requested' and datediff(minute,oh.effect_start_dt,least(oh.effect_end_dt,current_timestamp()))>0 group by 1)
select c.sfdc_object_id,
  case when rdp.d is null then '' when rdp.d<=5 then 'Met' else 'Missed' end rfd_met,
  case when er.d is null then '' when er.d<=5 then 'Met' else 'Missed' end erc_met,
  case when alt.d is null then '' when alt.d<=5 then 'Met' else 'Missed' end alt_met
from c left join rdp on rdp.opportunity_id=c.sfdc_object_id
       left join er on er.opportunity_id=c.sfdc_object_id
       left join alt on alt.opportunity_id=c.sfdc_object_id
