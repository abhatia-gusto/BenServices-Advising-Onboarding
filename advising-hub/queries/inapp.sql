select company_id,
  max_by(rating, response_at) in_app_rating,
  max_by(feedback, response_at) in_app_feedback,
  to_char(max(response_at)::date) in_app_date
from data_warehouse_rc1.bi.application_survey_data
where workflow_name='Benefits Renewal'
  and company_id in (select zp_company_id from data_warehouse_rc1.bi_reporting.advising_opportunities where renewal_date in ({{cohort_dates}}))
group by 1;
