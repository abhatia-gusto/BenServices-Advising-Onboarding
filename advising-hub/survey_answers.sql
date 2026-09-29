select o.sfdc_object_id, q.question_key, a.answer_key
from data_warehouse_rc1.bi_reporting.advising_opportunities o
join data_warehouse_rc1.hawaiian_ice_production_no_pii.renewals_survey_answers a on a.renewal_id=o.hi_renewal_id
left join data_warehouse_rc1.hawaiian_ice_production_no_pii.renewals_survey_questions q on q.id=a.renewals_survey_question_id
where o.renewal_date in ({{cohort_dates}});
