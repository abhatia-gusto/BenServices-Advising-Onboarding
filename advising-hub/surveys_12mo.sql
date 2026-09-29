with cos as (select distinct zp_company_id from data_warehouse_rc1.bi_reporting.advising_opportunities where renewal_date in ({{cohort_dates}}))
select company_id, survey, srv_date, rating, verbatim from (
  select c.company_id,
    coalesce(c.survey_name,c.survey_source) survey,
    to_char(coalesce(c.typeform_submitted_ts,c.ticket_solved_at)::date) srv_date,
    to_char(coalesce(c.csat_score,c.ces_score)) rating,
    c.comment verbatim,
    coalesce(c.typeform_submitted_ts,c.ticket_solved_at) ord_ts
  from data_warehouse_rc1.bi.ces_csat_data c
  where c.company_id in (select zp_company_id from cos)
    and coalesce(c.typeform_submitted_ts,c.ticket_solved_at) >= dateadd('month',-12,current_timestamp)
    and (c.csat_score is not null or c.ces_score is not null or c.comment is not null)
  union all
  select a.company_id, 'App: '||a.workflow_name survey,
    to_char(a.response_at::date) srv_date, to_char(a.rating) rating, a.feedback verbatim, a.response_at ord_ts
  from data_warehouse_rc1.bi.application_survey_data a
  where a.company_id in (select zp_company_id from cos)
    and a.response_at >= dateadd('month',-12,current_timestamp)
    and (a.rating is not null or a.feedback is not null)
)
order by company_id, ord_ts desc;
