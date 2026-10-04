with base as (
  select cxone_agent_id::varchar agent_id, name, pe, current_flag, terminated_at, effect_start_dt,
    row_number() over (partition by cxone_agent_id order by effect_start_dt desc) rn
  from bi.gusto_employees
  where cxone_agent_id is not null
    and (sub_team in ('Benefits Advising','Customer Advising','New Plan & Renewal Onboarding','Onboarding Advocacy','Bring Your Broker','Benefits Transfers','Broker Onboarding')
      or job_title in ('Onboarding Advocacy','Onboarding Advocacy - Captain','Benefits Onboarding','Onboarding Advocacy - Learning and Development'))
),
act as (
  select distinct cxone_agent_id::varchar agent_id from bi.gusto_employees
  where current_flag=true and terminated_at is null
    and (sub_team in ('Benefits Advising','Customer Advising','New Plan & Renewal Onboarding','Onboarding Advocacy','Bring Your Broker','Benefits Transfers','Broker Onboarding')
      or job_title in ('Onboarding Advocacy','Onboarding Advocacy - Captain','Benefits Onboarding','Onboarding Advocacy - Learning and Development'))
)
select b.agent_id, b.name, b.pe last_pe, case when a.agent_id is not null then 1 else 0 end active
from base b left join act a on a.agent_id=b.agent_id where b.rn=1
